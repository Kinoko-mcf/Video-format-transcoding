"""数据模型：定义视频任务、字幕轨道、任务状态等核心数据结构。"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class TaskStatus(str, Enum):
    """任务状态枚举"""
    PENDING = "等待中"
    PROCESSING = "处理中"
    COMPLETED = "已完成"
    FAILED = "失败"


@dataclass
class SubtitleTrack:
    """字幕轨道信息"""
    index: int               # 在 MKV 中的流索引（0-based）
    language: str = "未知"    # 语言标签（如 chi, eng）
    codec: str = "未知"       # 编码格式（如 subrip, ass, hdmv_pgs_subtitle）
    title: str = ""          # 轨道标题

    @property
    def display_name(self) -> str:
        """用于界面显示的名称"""
        parts = [f"轨道 #{self.index}"]
        if self.title:
            parts.append(self.title)
        if self.language != "未知":
            parts.append(f"({self.language})")
        return " ".join(parts)


@dataclass
class VideoInfo:
    """视频文件基本信息"""
    file_path: str
    file_name: str = ""
    duration_seconds: float = 0.0   # 视频时长（秒）
    video_codec: str = "未知"        # 视频编码
    audio_codec: str = "未知"        # 音频编码
    width: int = 0                   # 视频宽度
    height: int = 0                  # 视频高度
    pixel_format: str = "yuv420p"    # 像素格式
    file_size_mb: float = 0.0       # 文件大小（MB）
    subtitle_tracks: list[SubtitleTrack] = field(default_factory=list)


@dataclass
class SubtitleOptions:
    """字幕处理选项"""
    export_srt: bool = False           # 是否导出独立 SRT 字幕文件
    embed_in_mp4: bool = False         # 是否将字幕嵌入 MP4
    selected_tracks: Optional[list[int]] = None  # 选中的字幕轨道索引列表，None 表示全部


class EncodingPreset(str, Enum):
    """编码质量预设"""
    NEAR_LOSSLESS = "极高（CRF 14）"
    HIGH = "高（CRF 18）"
    STANDARD = "标准（CRF 22）"


class OutputResolution(str, Enum):
    """输出分辨率选项"""
    ORIGINAL = "保持原始"
    UHD_4K = "4K (3840×2160)"
    QHD_2K = "2K (2560×1440)"
    FHD_1080P = "1080p (1920×1080)"
    HD_720P = "720p (1280×720)"


@dataclass
class EncodingOptions:
    """视频编码选项"""
    output_resolution: OutputResolution = OutputResolution.ORIGINAL
    quality_preset: EncodingPreset = EncodingPreset.HIGH
    use_gpu: bool = False                    # 是否使用 GPU 硬件加速
    # 以下为引擎层使用的内部参数
    gpu_encoder: str = ""                    # GPU 编码器名称（自动检测）
    cpu_encoder: str = "libx264"             # CPU 编码器
    audio_encoder: str = "aac"               # 音频编码器
    audio_bitrate: str = "256k"              # 音频码率
    pixel_format: str = "yuv420p"            # 像素格式（8-bit 默认）

    @property
    def active_encoder(self) -> str:
        """当前实际使用的视频编码器。"""
        if self.use_gpu and self.gpu_encoder:
            return self.gpu_encoder
        return self.cpu_encoder

    @property
    def is_gpu(self) -> bool:
        """是否正在使用 GPU 编码。"""
        return self.use_gpu and bool(self.gpu_encoder)

    @property
    def crf_value(self) -> int:
        """根据质量预设返回 CRF 值（越小质量越高）。"""
        mapping = {
            EncodingPreset.NEAR_LOSSLESS: 14,
            EncodingPreset.HIGH: 18,
            EncodingPreset.STANDARD: 22,
        }
        return mapping.get(self.quality_preset, 18)

    @property
    def gpu_cq_value(self) -> int:
        """GPU 编码的 CQ/QP 值（NVENC/AMF/QSV 质量控制参数）。

        GPU 硬件编码器使用 CQ 而非 CRF，同等级质量下 CQ 值约比 CRF 高 6。
        """
        mapping = {
            EncodingPreset.NEAR_LOSSLESS: 20,
            EncodingPreset.HIGH: 24,
            EncodingPreset.STANDARD: 28,
        }
        return mapping.get(self.quality_preset, 24)

    @property
    def gpu_preset(self) -> str:
        """GPU 编码的速度/质量预设。"""
        mapping = {
            EncodingPreset.NEAR_LOSSLESS: "p4",   # 中速，高质量
            EncodingPreset.HIGH: "p3",            # 中等
            EncodingPreset.STANDARD: "p1",        # 最快
        }
        return mapping.get(self.quality_preset, "p3")

    @property
    def preset_name(self) -> str:
        """根据质量预设返回 x264 preset 名称。"""
        mapping = {
            EncodingPreset.NEAR_LOSSLESS: "slow",
            EncodingPreset.HIGH: "medium",
            EncodingPreset.STANDARD: "faster",
        }
        return mapping.get(self.quality_preset, "medium")

    @property
    def needs_reencode(self) -> bool:
        """是否需要重新编码（非原始分辨率输出即需要）。"""
        return self.output_resolution != OutputResolution.ORIGINAL


@dataclass
class VideoTask:
    """单个视频转码任务"""
    input_path: str
    output_dir: str
    status: TaskStatus = TaskStatus.PENDING
    progress: float = 0.0             # 0.0 ~ 1.0
    error_message: str = ""
    subtitle_options: SubtitleOptions = field(default_factory=SubtitleOptions)
    encoding_options: EncodingOptions = field(default_factory=EncodingOptions)
    video_info: Optional[VideoInfo] = None
    log_lines: list[str] = field(default_factory=list)
    output_files: list[str] = field(default_factory=list)  # 生成的文件列表

    @property
    def file_name(self) -> str:
        """仅文件名（不含路径）"""
        import os
        return os.path.basename(self.input_path)

    @property
    def progress_percent(self) -> int:
        """进度百分比（0-100）"""
        return int(self.progress * 100)

    def add_log(self, message: str):
        """添加一条日志"""
        from datetime import datetime
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_lines.append(f"[{timestamp}] {message}")
