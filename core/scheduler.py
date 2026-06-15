"""任务调度层：批量任务队列管理、并发控制、状态追踪。

使用 QThread 工作线程避免阻塞 GUI，通过 Qt 信号与界面通信。
"""

import os
import traceback
from typing import Optional

from PyQt6.QtCore import QObject, QThread, pyqtSignal, QMutex, QMutexLocker

from core.models import VideoTask, TaskStatus, SubtitleOptions
from core.engine import probe_video, extract_subtitle, convert_to_mp4, convert_to_mp4_reencode


class SchedulerWorker(QObject):
    """在后台线程中执行转码任务的工作对象。"""

    # 信号定义
    task_started = pyqtSignal(str)            # 任务开始，参数: input_path
    task_progress = pyqtSignal(str, float)     # 进度更新，参数: input_path, progress(0-1)
    task_completed = pyqtSignal(str, list)     # 任务完成，参数: input_path, output_files
    task_failed = pyqtSignal(str, str)         # 任务失败，参数: input_path, error_message
    task_log = pyqtSignal(str, str)            # 日志消息，参数: input_path, message
    probe_finished = pyqtSignal(str, object)   # 视频探测完成，参数: input_path, VideoInfo

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._last_progress: dict[str, float] = {}  # 节流：每个任务的上次发射进度值

    def _make_progress_cb(self, input_path: str):
        """创建节流的进度回调：时间（≥300ms）和百分比（≥1%）双重限制。"""
        import time
        last_pct = [0.0]
        last_time = [0.0]

        def cb(progress: float):
            now = time.monotonic()
            # 双重节流：时间间隔 ≥300ms，且进度变化 ≥1%，或者已完成
            if (now - last_time[0] >= 0.3 and progress - last_pct[0] >= 0.01) or progress >= 1.0:
                self.task_progress.emit(input_path, progress)
                last_pct[0] = progress
                last_time[0] = now

        return cb

    def process_task(self, task: VideoTask):
        """执行单个转码任务的全部流程。

        流程：探测视频信息 → 提取字幕 → 转码为 MP4
        每个步骤的结果通过信号发送回主线程。

        Args:
            task: 要处理的视频任务
        """
        input_path = task.input_path
        self.task_started.emit(input_path)

        try:
            # ===== 第 1 步：探测视频信息 =====
            self.task_log.emit(input_path, "正在探测视频信息...")
            video_info = probe_video(input_path)
            if video_info is None:
                self.task_failed.emit(input_path, "无法读取视频信息，请检查文件是否损坏")
                return

            task.video_info = video_info
            self.probe_finished.emit(input_path, video_info)
            self.task_log.emit(
                input_path,
                f"视频: {video_info.video_codec} {video_info.width}x{video_info.height}, "
                f"时长: {video_info.duration_seconds:.1f}秒, "
                f"大小: {video_info.file_size_mb:.1f}MB, "
                f"字幕轨道: {len(video_info.subtitle_tracks)}条"
            )

            # ===== 第 2 步：提取字幕 =====
            subtitle_files: list[str] = []
            subtitle_options = task.subtitle_options

            if subtitle_options.export_srt or subtitle_options.embed_in_mp4:
                # 确定要处理的字幕轨道
                tracks_to_process = self._resolve_tracks(video_info, subtitle_options)

                if tracks_to_process:
                    self.task_log.emit(
                        input_path,
                        f"准备处理 {len(tracks_to_process)} 条字幕轨道"
                    )
                    output_basename = os.path.splitext(task.file_name)[0]

                    for i, track_idx in enumerate(tracks_to_process):
                        track = video_info.subtitle_tracks[track_idx]
                        # 构建字幕文件命名
                        if len(tracks_to_process) == 1:
                            srt_name = output_basename
                        else:
                            srt_name = f"{output_basename}.track{track_idx}"
                            if track.language != "未知":
                                srt_name += f".{track.language}"

                        self.task_log.emit(
                            input_path,
                            f"提取字幕: {track.display_name} → {srt_name}.srt"
                        )

                        success, result = extract_subtitle(
                            input_path,
                            task.output_dir,
                            track_idx,
                            srt_name,
                        )

                        if success:
                            subtitle_files.append(result)
                            self.task_log.emit(input_path, f"字幕提取成功: {os.path.basename(result)}")
                        else:
                            self.task_log.emit(input_path, f"字幕提取失败: {result}")
                else:
                    self.task_log.emit(input_path, "未找到字幕轨道")

            # ===== 第 3 步：转码为 MP4 =====
            encoding_options = task.encoding_options
            output_basename = os.path.splitext(task.file_name)[0]
            embed_subs = subtitle_files if subtitle_options.embed_in_mp4 else []

            if encoding_options.needs_reencode:
                # 需要重新编码（缩放分辨率）
                self.task_log.emit(
                    input_path,
                    f"开始重编码: {video_info.width}x{video_info.height} → "
                    f"{encoding_options.output_resolution.value} "
                    f"(CRF {encoding_options.crf_value}, {encoding_options.preset_name})"
                )
                success, result = convert_to_mp4_reencode(
                    input_path=input_path,
                    output_dir=task.output_dir,
                    output_basename=output_basename,
                    encoding_options=encoding_options,
                    subtitle_paths=embed_subs,
                    progress_callback=self._make_progress_cb(input_path),
                    log_callback=lambda msg: self.task_log.emit(input_path, msg),
                )
            else:
                # 流复制，无损
                self.task_log.emit(input_path, "开始转码为 MP4（流复制，无损）...")
                success, result = convert_to_mp4(
                    input_path=input_path,
                    output_dir=task.output_dir,
                    output_basename=output_basename,
                    subtitle_paths=embed_subs,
                    progress_callback=self._make_progress_cb(input_path),
                    log_callback=lambda msg: self.task_log.emit(input_path, msg),
                )

            if success:
                output_files = [result]
                # 加入导出的字幕文件
                if subtitle_options.export_srt:
                    output_files.extend(subtitle_files)

                self.task_log.emit(input_path, f"转码完成: {os.path.basename(result)}")
                self.task_completed.emit(input_path, output_files)
            else:
                self.task_failed.emit(input_path, result)

        except Exception as e:
            error_detail = f"{str(e)}\n{traceback.format_exc()}"
            self.task_log.emit(input_path, f"异常: {error_detail}")
            self.task_failed.emit(input_path, str(e))

    @staticmethod
    def _resolve_tracks(video_info, subtitle_options: SubtitleOptions) -> list[int]:
        """解析需要处理的字幕轨道索引列表。

        Args:
            video_info: 视频信息
            subtitle_options: 字幕选项

        Returns:
            需要处理的轨道索引列表（相对于 subtitle_tracks 列表的索引）
        """
        total_tracks = len(video_info.subtitle_tracks)
        if total_tracks == 0:
            return []

        if subtitle_options.selected_tracks is None:
            # None 表示处理全部轨道
            return list(range(total_tracks))
        else:
            # 只处理用户选中的轨道
            return [i for i in subtitle_options.selected_tracks if 0 <= i < total_tracks]


class TaskScheduler(QObject):
    """任务调度器：管理任务队列和后台处理线程。

    负责接收用户提交的任务、按 FIFO 顺序调度执行、
    控制并发数量、转发工作线程的信号给 GUI。

    使用方法:
        scheduler = TaskScheduler()
        scheduler.task_status_changed.connect(on_status_changed)
        scheduler.add_task(task)
    """

    # 转发给 GUI 的信号
    task_status_changed = pyqtSignal(VideoTask)   # 任务状态变化
    task_progress = pyqtSignal(str, float)         # 进度更新
    task_log = pyqtSignal(str, str)                # 日志消息
    probe_finished = pyqtSignal(str, object)       # 视频探测完成

    def __init__(self, parent: Optional[QObject] = None, max_workers: int = 1):
        super().__init__(parent)
        self.max_workers = max_workers
        self._queue: list[VideoTask] = []
        self._active_count = 0
        self._mutex = QMutex()

    def add_task(self, task: VideoTask):
        """添加任务到队列。"""
        with QMutexLocker(self._mutex):
            self._queue.append(task)
        # 尝试立即启动
        self._process_next()

    def add_tasks(self, tasks: list[VideoTask]):
        """批量添加任务。"""
        with QMutexLocker(self._mutex):
            self._queue.extend(tasks)
        self._process_next()

    def clear_queue(self):
        """清空等待中的任务队列（不影响正在处理的任务）。"""
        with QMutexLocker(self._mutex):
            self._queue = [t for t in self._queue if t.status == TaskStatus.PROCESSING]

    def remove_task(self, input_path: str):
        """从队列中移除指定任务（仅限等待中的）。"""
        with QMutexLocker(self._mutex):
            self._queue = [
                t for t in self._queue
                if not (t.input_path == input_path and t.status == TaskStatus.PENDING)
            ]

    def queue_size(self) -> int:
        """当前排队任务数。"""
        with QMutexLocker(self._mutex):
            return len([t for t in self._queue if t.status == TaskStatus.PENDING])

    def active_count(self) -> int:
        """正在处理的任务数。"""
        with QMutexLocker(self._mutex):
            return self._active_count

    def _process_next(self):
        """取出队列中的下一个等待任务并启动处理。"""
        with QMutexLocker(self._mutex):
            if self._active_count >= self.max_workers:
                return

            # 找到第一个等待中的任务
            pending_tasks = [t for t in self._queue if t.status == TaskStatus.PENDING]
            if not pending_tasks:
                return

            task = pending_tasks[0]
            task.status = TaskStatus.PROCESSING
            self._active_count += 1

        # 通知 GUI 状态更新
        self.task_status_changed.emit(task)

        # 创建后台线程
        thread = QThread()
        worker = SchedulerWorker()

        # 将 worker 移动到后台线程
        worker.moveToThread(thread)

        # 连接信号
        worker.task_started.connect(self._on_task_started)
        worker.task_progress.connect(self._on_task_progress)
        worker.task_completed.connect(self._on_task_completed)
        worker.task_failed.connect(self._on_task_failed)
        worker.task_log.connect(self._on_task_log)
        worker.probe_finished.connect(self._on_probe_finished)

        # 线程结束时清理
        thread.started.connect(lambda t=task, w=worker: w.process_task(t))
        worker.task_completed.connect(thread.quit)
        worker.task_failed.connect(thread.quit)
        thread.finished.connect(thread.deleteLater)
        worker.task_completed.connect(worker.deleteLater)
        worker.task_failed.connect(worker.deleteLater)

        # 保存线程引用防止被 GC 回收
        task._thread = thread  # type: ignore
        task._worker = worker  # type: ignore

        thread.start()

    def _on_task_started(self, input_path: str):
        """工作线程通知任务开始。"""
        pass  # 状态已在 _process_next 中更新

    def _on_task_progress(self, input_path: str, progress: float):
        """工作线程通知进度更新（已节流，仅发射轻量进度信号）。"""
        for task in self._queue:
            if task.input_path == input_path:
                task.progress = progress
                # 仅发射进度信号（轻量），不触发完整状态刷新
                self.task_progress.emit(input_path, progress)
                break

    def _on_task_completed(self, input_path: str, output_files: list[str]):
        """工作线程通知任务完成。"""
        self._finish_task(input_path, TaskStatus.COMPLETED, output_files=output_files)

    def _on_task_failed(self, input_path: str, error_message: str):
        """工作线程通知任务失败。"""
        self._finish_task(input_path, TaskStatus.FAILED, error_message=error_message)

    def _on_task_log(self, input_path: str, message: str):
        """工作线程发出日志消息。"""
        for task in self._queue:
            if task.input_path == input_path:
                task.add_log(message)
                break
        self.task_log.emit(input_path, message)

    def _on_probe_finished(self, input_path: str, video_info):
        """工作线程通知视频探测完成。"""
        self.probe_finished.emit(input_path, video_info)

    def _finish_task(self, input_path: str, status: TaskStatus,
                     output_files: list[str] = None,
                     error_message: str = ""):
        """完成或失败任务的收尾工作。"""
        finished_task = None
        with QMutexLocker(self._mutex):
            self._active_count = max(0, self._active_count - 1)
            for task in self._queue:
                if task.input_path == input_path:
                    task.status = status
                    if output_files:
                        task.output_files = output_files
                    if error_message:
                        task.error_message = error_message
                    finished_task = task
                    break

        # 在锁外发射信号，避免死锁（信号槽会回查 active_count/queue_size）
        if finished_task is not None:
            self.task_status_changed.emit(finished_task)

        # 处理队列中的下一个任务
        self._process_next()
