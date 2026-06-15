"""FFmpeg 引擎层：命令构建、子进程调用、进度解析。

所有与 FFmpeg 的直接交互都封装在此模块中，上层无需了解 FFmpeg 命令行细节。
长时运行的转码操作使用 QProcess（Qt 原生），避免 subprocess 与 Qt 事件循环的 GIL 竞争。
"""

import os
import re
import subprocess
import sys
from typing import Optional, Callable

from PyQt6.QtCore import QProcess, QEventLoop, QObject

from core.models import VideoInfo, SubtitleTrack, EncodingOptions, OutputResolution


def _get_ffmpeg_path() -> str:
    """获取 FFmpeg 可执行文件路径。"""
    if getattr(sys, 'frozen', False):
        base_dir = os.path.dirname(sys.executable)
    else:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    bundled_path = os.path.join(base_dir, "ffmpeg", "ffmpeg.exe")
    if os.path.exists(bundled_path):
        return bundled_path
    return "ffmpeg"


FFMPEG_PATH = _get_ffmpeg_path()


def detect_gpu_encoder() -> Optional[str]:
    """检测系统可用的 GPU 硬件编码器。"""
    try:
        result = subprocess.run(
            [FFMPEG_PATH, "-encoders"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        )
        output = result.stdout if result.stdout else ""
    except FileNotFoundError:
        return None
    if "h264_nvenc" in output:
        return "h264_nvenc"
    if "h264_amf" in output:
        return "h264_amf"
    if "h264_qsv" in output:
        return "h264_qsv"
    return None


def _parse_duration(duration_str: str) -> float:
    """将 FFmpeg 时长字符串解析为秒数。"""
    if not duration_str or duration_str == "N/A":
        return 0.0
    try:
        parts = duration_str.split(":")
        if len(parts) == 3:
            h, m, s = parts
            return float(h) * 3600 + float(m) * 60 + float(s)
        return float(duration_str)
    except (ValueError, AttributeError):
        return 0.0


def probe_video(file_path: str) -> Optional[VideoInfo]:
    """探测视频文件信息（使用 subprocess.run，短时操作）。"""
    if not os.path.exists(file_path):
        return None

    cmd = [FFMPEG_PATH, "-i", file_path, "-hide_banner"]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        )
    except FileNotFoundError:
        return None

    output = result.stderr if result.stderr else result.stdout
    if not output:
        return None

    info = VideoInfo(
        file_path=file_path,
        file_name=os.path.basename(file_path),
    )

    try:
        info.file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
    except OSError:
        pass

    duration_match = re.search(r"Duration:\s*(\d+:\d+:\d+\.\d+)", output)
    if duration_match:
        info.duration_seconds = _parse_duration(duration_match.group(1))

    # 分辨率（\d{3,5} 防误匹配十六进制编码标签）
    video_match = re.search(
        r"Stream\s+#\d+:\d+.*?Video:\s*(\S+).*?[,\s](\d{3,5})x(\d{3,5})[,\s]",
        output
    )
    if video_match:
        info.video_codec = video_match.group(1).rstrip(",")
        info.width = int(video_match.group(2))
        info.height = int(video_match.group(3))

    # 像素格式
    pix_fmt_match = re.search(
        r"Video:.*?(yuv420p\w*|yuv422p\w*|yuv444p\w*|nv12\w*)",
        output
    )
    if pix_fmt_match:
        info.pixel_format = pix_fmt_match.group(1)

    # 音频编码
    audio_match = re.search(r"Stream\s+#\d+:\d+.*?Audio:\s*(\S+)", output)
    if audio_match:
        info.audio_codec = audio_match.group(1).rstrip(",")

    # 字幕轨道
    subtitle_matches = re.finditer(
        r"Stream\s+#(\d+):(\d+)(?:\((\w+)\))?.*?Subtitle:\s*(\S+)",
        output
    )
    for m in subtitle_matches:
        stream_index = int(m.group(2))
        lang = m.group(3) or "未知"
        codec = m.group(4).rstrip(",")
        title = ""
        title_match = re.search(
            rf"Stream\s+#\d+:{stream_index}.*?\n\s+title\s*:\s*(.+)",
            output
        )
        if title_match:
            title = title_match.group(1).strip()
        info.subtitle_tracks.append(SubtitleTrack(
            index=stream_index, language=lang, codec=codec, title=title,
        ))

    return info


def _build_progress_callback(duration_seconds: float) -> Callable[[str], Optional[float]]:
    """创建进度解析回调，从 FFmpeg stderr 行中提取 time= 计算进度。"""
    time_pattern = re.compile(r"time=(\d+:\d+:\d+\.\d+)")

    def parse_progress(line: str) -> Optional[float]:
        match = time_pattern.search(line)
        if not match or duration_seconds <= 0:
            return None
        current_time = _parse_duration(match.group(1))
        return min(current_time / duration_seconds, 1.0)

    return parse_progress


def extract_subtitle(
    input_path: str, output_dir: str, track_index: int, output_basename: str,
) -> tuple[bool, str]:
    """从 MKV 中提取单个字幕轨道为 SRT（短时操作，用 subprocess.run）。"""
    output_path = os.path.join(output_dir, f"{output_basename}.track{track_index}.srt")
    cmd = [FFMPEG_PATH, "-i", input_path, "-map", f"0:s:{track_index}", "-y", output_path]
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True,
            encoding="utf-8", errors="replace",
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        )
        if result.returncode == 0 and os.path.exists(output_path):
            return True, output_path
        error = result.stderr.strip() or "未知错误"
        return False, f"字幕提取失败: {error[-200:]}"
    except Exception as e:
        return False, f"字幕提取异常: {str(e)}"


def _resolve_output_path(input_path: str, output_dir: str, output_basename: str,
                         suffix: str = "_converted") -> str:
    """解析输出路径，与输入冲突时自动添加后缀。"""
    output_path = os.path.join(output_dir, f"{output_basename}.mp4")
    if os.path.normpath(output_path) == os.path.normpath(input_path):
        output_path = os.path.join(output_dir, f"{output_basename}{suffix}.mp4")
    return output_path


# ===== QProcess 辅助：将 FFmpeg 命令转为 QProcess 可执行的形式 =====

def _start_ffmpeg(process: QProcess, cmd: list[str]):
    """用 QProcess 启动 FFmpeg。"""
    process.setProcessChannelMode(QProcess.ProcessChannelMode.SeparateChannels)
    program = cmd[0]
    args = cmd[1:]
    process.start(program, args)


def _run_ffmpeg_with_callbacks(
    cmd: list[str],
    duration: float,
    progress_callback: Optional[Callable[[float], None]],
    log_callback: Optional[Callable[[str], None]],
) -> tuple[bool, int]:
    """使用 QProcess + 本地事件循环运行 FFmpeg，避免 subprocess GIL 竞争。

    Args:
        cmd: FFmpeg 完整命令行
        duration: 视频时长（用于进度计算）
        progress_callback: 进度回调
        log_callback: 日志回调

    Returns:
        (成功标志, 退出码)
    """
    process = QProcess()
    parse_progress = _build_progress_callback(duration) if duration > 0 else lambda line: None
    loop = QEventLoop()

    # 缓冲区累积
    buf = ""

    def on_ready_read():
        nonlocal buf
        data = bytes(process.readAllStandardError()).decode("utf-8", errors="replace")
        buf += data
        # 按行处理
        while "\n" in buf or "\r" in buf:
            # 找到行尾
            line_end = -1
            for sep in ("\r\n", "\n", "\r"):
                idx = buf.find(sep)
                if idx >= 0:
                    line_end = idx
                    sep_len = len(sep)
                    break
            if line_end < 0:
                break
            line = buf[:line_end].strip()
            buf = buf[line_end + sep_len:]

            if not line:
                continue
            # 进度
            if progress_callback:
                p = parse_progress(line)
                if p is not None:
                    progress_callback(p)
            # 日志（仅错误/警告级别）
            if log_callback:
                lower = line.lower()
                if "error" in lower or "warning" in lower:
                    log_callback(line)

    process.readyReadStandardError.connect(on_ready_read)
    process.finished.connect(loop.quit)

    _start_ffmpeg(process, cmd)

    exit_code = loop.exec()

    # 处理缓冲区残留
    if buf.strip():
        for line in buf.strip().splitlines():
            line = line.strip()
            if not line:
                continue
            if progress_callback:
                p = parse_progress(line)
                if p is not None:
                    progress_callback(p)
            if log_callback:
                lower = line.lower()
                if "error" in lower or "warning" in lower:
                    log_callback(line)

    success = exit_code == 0
    return success, exit_code


# ===== 分辨率映射 =====
_RESOLUTION_MAP = {
    OutputResolution.UHD_4K: (3840, 2160),
    OutputResolution.QHD_2K: (2560, 1440),
    OutputResolution.FHD_1080P: (1920, 1080),
    OutputResolution.HD_720P: (1280, 720),
}


def convert_to_mp4(
    input_path: str,
    output_dir: str,
    output_basename: str,
    subtitle_paths: list[str],
    progress_callback: Optional[Callable[[float], None]] = None,
    log_callback: Optional[Callable[[str], None]] = None,
) -> tuple[bool, str]:
    """MKV → MP4 流复制（无损），使用 QProcess 避免 UI 卡顿。"""
    output_path = _resolve_output_path(input_path, output_dir, output_basename)
    if output_path != os.path.join(output_dir, f"{output_basename}.mp4"):
        if log_callback:
            log_callback("注意: 输出路径与输入相同，已自动添加 _converted 后缀")

    duration = 0.0
    info = probe_video(input_path)
    if info:
        duration = info.duration_seconds

    cmd = [FFMPEG_PATH, "-i", input_path]
    for sub_path in subtitle_paths:
        if os.path.exists(sub_path):
            cmd.extend(["-i", sub_path])

    cmd.extend(["-map", "0:v", "-c:v", "copy"])
    cmd.extend(["-map", "0:a?", "-c:a", "copy"])

    for i, sub_path in enumerate(subtitle_paths):
        if os.path.exists(sub_path):
            input_index = i + 1
            cmd.extend([
                "-map", f"{input_index}:s", "-c:s", "mov_text",
                f"-metadata:s:s:{i}", "language=chi",
            ])

    cmd.extend(["-movflags", "+faststart", "-y", output_path])

    if log_callback:
        log_callback(f"FFmpeg 流复制: {' '.join(cmd)}")

    success, exit_code = _run_ffmpeg_with_callbacks(
        cmd, duration, progress_callback, log_callback
    )

    if success and os.path.exists(output_path):
        if progress_callback:
            progress_callback(1.0)
        return True, output_path
    else:
        return False, f"转码失败，FFmpeg 返回码: {exit_code}"


def convert_to_mp4_reencode(
    input_path: str,
    output_dir: str,
    output_basename: str,
    encoding_options: EncodingOptions,
    subtitle_paths: list[str],
    progress_callback: Optional[Callable[[float], None]] = None,
    log_callback: Optional[Callable[[str], None]] = None,
) -> tuple[bool, str]:
    """MKV → MP4 重编码（缩放分辨率），使用 QProcess 避免 UI 卡顿。"""
    output_path = _resolve_output_path(input_path, output_dir, output_basename)
    if output_path != os.path.join(output_dir, f"{output_basename}.mp4"):
        if log_callback:
            log_callback("注意: 输出路径与输入相同，已自动添加 _converted 后缀")

    duration = 0.0
    info = probe_video(input_path)
    if info:
        duration = info.duration_seconds

    target_w, target_h = _RESOLUTION_MAP.get(
        encoding_options.output_resolution, (0, 0)
    )

    # 视频滤镜链
    filters = []
    if target_w > 0 and target_h > 0:
        filters.append(
            f"scale={target_w}:{target_h}:flags=lanczos"
            f":force_original_aspect_ratio=decrease"
            f",pad={target_w}:{target_h}:(ow-iw)/2:(oh-ih)/2"
            f":color=black"
        )

    if info and ("p10" in info.pixel_format or "p12" in info.pixel_format):
        pix_fmt = info.pixel_format
    else:
        pix_fmt = info.pixel_format if info else encoding_options.pixel_format

    filters.append(f"format={pix_fmt}")
    filter_chain = ",".join(filters)

    cmd = [FFMPEG_PATH, "-i", input_path]
    for sub_path in subtitle_paths:
        if os.path.exists(sub_path):
            cmd.extend(["-i", sub_path])

    encoder = encoding_options.active_encoder
    cmd.extend(["-map", "0:v", "-c:v", encoder])

    if encoding_options.is_gpu:
        if "nvenc" in encoder:
            cmd.extend(["-cq", str(encoding_options.gpu_cq_value)])
            cmd.extend(["-preset", encoding_options.gpu_preset])
            cmd.extend(["-bf", "0"])
        elif "amf" in encoder:
            cmd.extend(["-qp_i", str(encoding_options.gpu_cq_value)])
            cmd.extend(["-qp_p", str(encoding_options.gpu_cq_value)])
            cmd.extend(["-quality", "quality"])
        elif "qsv" in encoder:
            cmd.extend(["-global_quality", str(encoding_options.gpu_cq_value)])
            cmd.extend(["-preset", "medium"])
        cmd.extend(["-vf", filter_chain])
    else:
        cmd.extend(["-crf", str(encoding_options.crf_value)])
        cmd.extend(["-preset", encoding_options.preset_name])
        cmd.extend(["-pix_fmt", pix_fmt])
        cmd.extend(["-vf", filter_chain])

    cmd.extend(["-map", "0:a?"])
    cmd.extend(["-c:a", encoding_options.audio_encoder])
    cmd.extend(["-b:a", encoding_options.audio_bitrate])

    for i, sub_path in enumerate(subtitle_paths):
        if os.path.exists(sub_path):
            input_index = i + 1
            cmd.extend([
                "-map", f"{input_index}:s", "-c:s", "mov_text",
                f"-metadata:s:s:{i}", "language=chi",
            ])

    cmd.extend(["-movflags", "+faststart", "-map_metadata", "0",
                "-map_chapters", "0", "-y", output_path])

    if log_callback:
        mode = "GPU" if encoding_options.is_gpu else "CPU"
        log_callback(f"重编码({mode}): {cmd[0]} ... -y {os.path.basename(output_path)}")

    success, exit_code = _run_ffmpeg_with_callbacks(
        cmd, duration, progress_callback, log_callback
    )

    if success and os.path.exists(output_path):
        if progress_callback:
            progress_callback(1.0)
        return True, output_path
    else:
        return False, f"重编码失败，FFmpeg 返回码: {exit_code}"
