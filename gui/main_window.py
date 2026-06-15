"""主窗口：集成所有面板，提供完整的用户交互界面。"""

import os
from typing import Optional

from PyQt6.QtCore import Qt, QSettings
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QGroupBox,
    QCheckBox, QPushButton, QLabel, QLineEdit, QFileDialog,
    QMessageBox, QSplitter, QSizePolicy, QComboBox,
)
from PyQt6.QtGui import QFont, QIcon

from core.models import VideoTask, TaskStatus, SubtitleOptions, EncodingOptions, EncodingPreset, OutputResolution
from core.scheduler import TaskScheduler
from core.engine import detect_gpu_encoder
from gui.widgets import DropZone, SelectAllCheckBox
from gui.task_panel import TaskPanel
from gui.log_panel import LogPanel


class MainWindow(QMainWindow):
    """视频格式转码工具主窗口。"""

    WINDOW_TITLE = "视频格式转码工具"
    WINDOW_MIN_WIDTH = 1000
    WINDOW_MIN_HEIGHT = 600

    def __init__(self):
        super().__init__()
        self.setWindowTitle(self.WINDOW_TITLE)
        self.setMinimumSize(self.WINDOW_MIN_WIDTH, self.WINDOW_MIN_HEIGHT)
        self.resize(1100, 680)

        # 任务调度器
        self._scheduler = TaskScheduler(max_workers=1)
        self._connect_scheduler_signals()

        # 待处理任务列表（已加入界面但尚未提交到调度器）
        self._pending_tasks: list[VideoTask] = []

        # 设置持久化
        self._settings = QSettings("VideoTranscoder", "MKVtoMP4")

        # GPU 检测
        self._gpu_encoder = detect_gpu_encoder()

        # 构建界面
        self._build_ui()

        # 恢复所有用户偏好设置
        self._restore_settings()

    def _restore_settings(self):
        """从持久化存储恢复所有用户偏好。"""
        s = self._settings

        # 输出目录
        last_dir = s.value("output_dir", "")
        if last_dir and os.path.isdir(last_dir):
            self._output_dir_edit.setText(last_dir)

        # 字幕选项
        self._export_srt_check.setChecked(
            s.value("export_srt", False, type=bool)
        )
        self._embed_sub_check.setChecked(
            s.value("embed_sub", False, type=bool)
        )

        # 编码设置
        resolution = s.value("resolution", OutputResolution.ORIGINAL.value)
        idx = self._resolution_combo.findText(resolution)
        if idx >= 0:
            self._resolution_combo.setCurrentIndex(idx)

        quality = s.value("quality", EncodingPreset.HIGH.value)
        idx = self._quality_combo.findText(quality)
        if idx >= 0:
            self._quality_combo.setCurrentIndex(idx)

        # GPU 加速
        if self._gpu_check.isEnabled():
            self._gpu_check.setChecked(
                s.value("use_gpu", False, type=bool)
            )

    def _save_settings(self):
        """将所有用户偏好保存到持久化存储。"""
        s = self._settings
        s.setValue("output_dir", self._output_dir_edit.text().strip())
        s.setValue("export_srt", self._export_srt_check.isChecked())
        s.setValue("embed_sub", self._embed_sub_check.isChecked())
        s.setValue("resolution", self._resolution_combo.currentText())
        s.setValue("quality", self._quality_combo.currentText())
        if self._gpu_check.isEnabled():
            s.setValue("use_gpu", self._gpu_check.isChecked())

    def _build_ui(self):
        """构建完整界面布局。"""
        central = QWidget()
        self.setCentralWidget(central)

        # 使用水平分割器实现左右可调整布局
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(3)
        splitter.setStyleSheet("QSplitter::handle { background-color: #ddd; }")

        # ===== 左侧面板 =====
        left_panel = self._build_left_panel()
        splitter.addWidget(left_panel)

        # ===== 右侧面板 =====
        right_panel = self._build_right_panel()
        right_panel.setFixedWidth(260)
        splitter.addWidget(right_panel)

        # 设置分割比例（左侧占 70%）
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 0)

        layout = QHBoxLayout(central)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.addWidget(splitter)

        # 所有选项变化时自动保存
        self._export_srt_check.toggled.connect(self._save_settings)
        self._embed_sub_check.toggled.connect(self._save_settings)
        self._resolution_combo.currentTextChanged.connect(self._save_settings)
        self._quality_combo.currentTextChanged.connect(self._save_settings)
        self._gpu_check.toggled.connect(self._save_settings)

    def _build_left_panel(self) -> QWidget:
        """构建左侧面板：拖放区 + 任务列表 + 日志。"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 5, 0)
        layout.setSpacing(8)

        # 拖放区域
        self._drop_zone = DropZone()
        self._drop_zone.files_dropped.connect(self._on_files_dropped)
        layout.addWidget(self._drop_zone)

        # 任务列表
        task_group = QGroupBox("任务列表")
        task_layout = QVBoxLayout(task_group)
        self._task_panel = TaskPanel()
        self._task_panel.remove_task_requested.connect(self._on_remove_task)
        task_layout.addWidget(self._task_panel)
        layout.addWidget(task_group, stretch=2)

        # 日志
        log_group = QGroupBox("处理日志")
        log_layout = QVBoxLayout(log_group)
        self._log_panel = LogPanel()
        log_layout.addWidget(self._log_panel)
        layout.addWidget(log_group, stretch=1)

        return panel

    def _build_right_panel(self) -> QWidget:
        """构建右侧面板：输出选项 + 字幕设置 + 操作按钮。"""
        panel = QWidget()
        panel.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 1px solid #e0e0e0;
                border-radius: 6px;
                margin-top: 12px;
                padding-top: 16px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 6px;
            }
        """)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        # ===== 输出选项 =====
        output_group = QGroupBox("输出选项")
        output_layout = QVBoxLayout(output_group)
        output_layout.setSpacing(8)

        # 导出 SRT 选项
        self._export_srt_check = QCheckBox("导出 SRT 字幕文件")
        self._export_srt_check.setChecked(False)
        self._export_srt_check.toggled.connect(self._on_subtitle_option_changed)
        output_layout.addWidget(self._export_srt_check)

        # 嵌入字幕选项
        self._embed_sub_check = QCheckBox("嵌入字幕到 MP4 文件中")
        self._embed_sub_check.setChecked(False)
        self._embed_sub_check.toggled.connect(self._on_subtitle_option_changed)
        output_layout.addWidget(self._embed_sub_check)

        layout.addWidget(output_group)

        # ===== 编码设置 =====
        encode_group = QGroupBox("编码设置")
        encode_layout = QVBoxLayout(encode_group)
        encode_layout.setSpacing(6)

        # 输出分辨率
        res_label = QLabel("输出分辨率")
        res_label.setStyleSheet("font-size: 12px; color: #555; font-weight: normal;")
        encode_layout.addWidget(res_label)

        self._resolution_combo = QComboBox()
        self._resolution_combo.addItems([r.value for r in OutputResolution])
        self._resolution_combo.setCurrentText(OutputResolution.ORIGINAL.value)
        self._resolution_combo.setStyleSheet("""
            QComboBox {
                border: 1px solid #ddd;
                border-radius: 4px;
                padding: 4px 8px;
                font-size: 12px;
                background-color: #fff;
            }
            QComboBox::drop-down {
                border: none;
            }
            QComboBox:hover {
                border-color: #aaa;
            }
        """)
        encode_layout.addWidget(self._resolution_combo)

        # 编码质量
        quality_label = QLabel("编码质量")
        quality_label.setStyleSheet("font-size: 12px; color: #555; font-weight: normal; margin-top: 6px;")
        encode_layout.addWidget(quality_label)

        self._quality_combo = QComboBox()
        self._quality_combo.addItems([p.value for p in EncodingPreset])
        self._quality_combo.setCurrentText(EncodingPreset.HIGH.value)
        self._quality_combo.setStyleSheet("""
            QComboBox {
                border: 1px solid #ddd;
                border-radius: 4px;
                padding: 4px 8px;
                font-size: 12px;
                background-color: #fff;
            }
            QComboBox::drop-down {
                border: none;
            }
            QComboBox:hover {
                border-color: #aaa;
            }
        """)
        encode_layout.addWidget(self._quality_combo)

        # GPU 硬件加速
        self._gpu_check = QCheckBox("GPU 硬件加速")
        gpu_tooltip = "使用硬件编码器（NVENC/AMF/QSV），速度提升 5-10 倍"
        if self._gpu_encoder:
            gpu_name_map = {
                "h264_nvenc": f"检测到 NVIDIA ({self._gpu_encoder})",
                "h264_amf": f"检测到 AMD ({self._gpu_encoder})",
                "h264_qsv": f"检测到 Intel ({self._gpu_encoder})",
            }
            gpu_tooltip = gpu_name_map.get(self._gpu_encoder, f"检测到 {self._gpu_encoder}")
            self._gpu_check.setEnabled(True)
        else:
            gpu_tooltip = "未检测到可用 GPU 编码器"
            self._gpu_check.setEnabled(False)
        self._gpu_check.setToolTip(gpu_tooltip)
        self._gpu_check.setStyleSheet("font-size: 12px; font-weight: normal;")
        encode_layout.addWidget(self._gpu_check)

        # 提示文字
        hint = QLabel("选择非原始分辨率时将重新编码\nGPU 加速可大幅提升速度")
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #999; font-size: 10px; font-weight: normal;")
        encode_layout.addWidget(hint)

        layout.addWidget(encode_group)

        # ===== 字幕轨道选择 =====
        subtitle_group = QGroupBox("字幕轨道选择")
        subtitle_layout = QVBoxLayout(subtitle_group)
        subtitle_layout.setSpacing(4)

        self._subtitle_track_selector = SelectAllCheckBox()
        self._subtitle_track_selector.selection_changed.connect(self._on_track_selection_changed)
        subtitle_layout.addWidget(self._subtitle_track_selector)

        # 初始状态提示
        self._no_subtitle_label = QLabel("添加 MKV 文件后自动识别字幕轨道")
        self._no_subtitle_label.setWordWrap(True)
        self._no_subtitle_label.setStyleSheet("color: #999; font-size: 11px; font-weight: normal;")
        subtitle_layout.addWidget(self._no_subtitle_label)

        self._subtitle_track_selector.hide()

        layout.addWidget(subtitle_group)

        # ===== 输出目录 =====
        dir_group = QGroupBox("输出目录")
        dir_layout = QVBoxLayout(dir_group)
        dir_layout.setSpacing(6)

        path_layout = QHBoxLayout()
        self._output_dir_edit = QLineEdit()
        self._output_dir_edit.setPlaceholderText("选择输出目录...")
        self._output_dir_edit.setReadOnly(True)
        self._output_dir_edit.setStyleSheet("""
            QLineEdit {
                border: 1px solid #ddd;
                border-radius: 4px;
                padding: 4px 8px;
                font-size: 12px;
                background-color: #fff;
            }
        """)
        path_layout.addWidget(self._output_dir_edit)

        browse_btn = QPushButton("浏览")
        browse_btn.setFixedWidth(50)
        browse_btn.setStyleSheet(self._button_style())
        browse_btn.clicked.connect(self._on_browse_output_dir)
        path_layout.addWidget(browse_btn)

        dir_layout.addLayout(path_layout)
        layout.addWidget(dir_group)

        layout.addStretch()

        # ===== 操作按钮 =====
        btn_layout = QVBoxLayout()
        btn_layout.setSpacing(6)

        self._start_btn = QPushButton("▶ 开始转换")
        self._start_btn.setMinimumHeight(40)
        self._start_btn.setStyleSheet(self._primary_button_style())
        self._start_btn.clicked.connect(self._on_start_convert)
        btn_layout.addWidget(self._start_btn)

        self._clear_btn = QPushButton("清空列表")
        self._clear_btn.setMinimumHeight(32)
        self._clear_btn.setStyleSheet(self._button_style())
        self._clear_btn.clicked.connect(self._on_clear_list)
        btn_layout.addWidget(self._clear_btn)

        layout.addLayout(btn_layout)

        return panel

    def _connect_scheduler_signals(self):
        """连接任务调度器的信号到 GUI 更新方法。"""
        scheduler = self._scheduler
        scheduler.task_status_changed.connect(self._on_task_status_changed)
        scheduler.task_progress.connect(self._on_task_progress)
        scheduler.task_log.connect(self._on_task_log)
        scheduler.probe_finished.connect(self._on_probe_finished)

    # ===== 信号处理 =====

    def _on_files_dropped(self, file_paths: list[str]):
        """处理拖放或选择的 MKV 文件（仅加入列表，不立即开始处理）。"""
        output_dir = self._output_dir_edit.text().strip()
        if not output_dir:
            self._log_panel.append_warning("⚠ 请先选择输出目录")
            QMessageBox.warning(self, "提示", "请先选择输出目录再添加文件。")
            return

        new_count = 0
        for path in file_paths:
            if self._task_panel.task_exists(path):
                self._log_panel.append_warning(f"文件已存在列表中: {os.path.basename(path)}")
                continue

            task = VideoTask(
                input_path=path,
                output_dir=output_dir,
                subtitle_options=self._get_subtitle_options(),
            )
            self._task_panel.add_task(task)
            # 暂存到待处理列表，等待用户点击"开始转换"
            self._pending_tasks.append(task)
            new_count += 1

        if new_count > 0:
            self._log_panel.append_info(f"已添加 {new_count} 个文件到任务列表，点击「开始转换」启动处理")
        else:
            self._log_panel.append_info("没有新文件被添加")

    def _on_task_status_changed(self, task: VideoTask):
        """调度器通知任务状态变化。"""
        self._task_panel.update_task(task)

        # 全部任务完成后恢复按钮状态
        if task.status in (TaskStatus.COMPLETED, TaskStatus.FAILED):
            if (self._scheduler.active_count() == 0 and
                    self._scheduler.queue_size() == 0 and
                    not self._pending_tasks):
                self._start_btn.setEnabled(True)
                self._start_btn.setText("▶ 开始转换")

    def _on_task_progress(self, input_path: str, progress: float):
        """调度器通知进度更新（轻量：仅更新进度条，不刷新整行）。"""
        self._task_panel.update_progress(input_path, int(progress * 100))

    def _on_task_log(self, input_path: str, message: str):
        """调度器转发日志消息。"""
        file_name = os.path.basename(input_path)
        display_msg = f"[{file_name}] {message}"

        # 根据内容判断日志级别
        if "失败" in message or "异常" in message or "错误" in message or "error" in message.lower():
            self._log_panel.append_error(display_msg)
        elif "完成" in message or "成功" in message:
            self._log_panel.append_success(display_msg)
        elif "警告" in message or "warning" in message.lower():
            self._log_panel.append_warning(display_msg)
        else:
            self._log_panel.append_info(display_msg)

    def _on_probe_finished(self, input_path: str, video_info):
        """视频探测完成，更新字幕轨道选择器。"""
        if video_info and video_info.subtitle_tracks:
            self._no_subtitle_label.hide()
            self._subtitle_track_selector.show()
            self._subtitle_track_selector.set_tracks(video_info.subtitle_tracks)
        else:
            self._no_subtitle_label.setText("未检测到字幕轨道")
            self._no_subtitle_label.show()
            self._subtitle_track_selector.hide()

    def _on_subtitle_option_changed(self):
        """字幕选项变化时，更新所有待处理任务的选项。"""
        # 新添加的任务会使用新的选项，已在队列中的任务不修改
        pass

    def _on_track_selection_changed(self, selected_indices: list[int]):
        """用户手动选择字幕轨道时触发。"""
        track_count = len(self._subtitle_track_selector._track_checkboxes)
        if not selected_indices:
            self._log_panel.append_warning("未选中任何字幕轨道，将跳过字幕处理")
        elif len(selected_indices) < track_count:
            self._log_panel.append_info(
                f"已选择 {len(selected_indices)}/{track_count} 条字幕轨道"
            )

    def _on_remove_task(self, input_path: str):
        """移除指定任务。"""
        self._scheduler.remove_task(input_path)
        self._task_panel.remove_task(input_path)
        self._log_panel.append_info(f"已移除: {os.path.basename(input_path)}")

    def _on_browse_output_dir(self):
        """打开目录选择对话框。"""
        current = self._output_dir_edit.text().strip() or os.path.expanduser("~")
        directory = QFileDialog.getExistingDirectory(self, "选择输出目录", current)
        if directory:
            self._output_dir_edit.setText(directory)
            self._save_settings()

    def _on_start_convert(self):
        """开始转换：将所有待处理任务提交到调度器。"""
        output_dir = self._output_dir_edit.text().strip()
        if not output_dir:
            QMessageBox.warning(self, "提示", "请先选择输出目录。")
            return

        if not os.path.isdir(output_dir):
            QMessageBox.warning(self, "提示", f"输出目录不存在: {output_dir}")
            return

        if not self._pending_tasks:
            QMessageBox.information(
                self, "提示",
                "没有待处理的任务。\n请拖放 MKV 文件到列表中添加任务。"
            )
            return

        # 用当前 UI 选项更新所有待处理任务的选项
        current_subtitle_opts = self._get_subtitle_options()
        current_encoding_opts = self._get_encoding_options()
        for task in self._pending_tasks:
            task.subtitle_options = current_subtitle_opts
            task.encoding_options = current_encoding_opts
            task.output_dir = output_dir

        # 批量提交到调度器
        self._scheduler.add_tasks(self._pending_tasks)
        count = len(self._pending_tasks)
        self._log_panel.append_info(f"输出目录: {output_dir}")
        self._log_panel.append_info(f"已提交 {count} 个任务开始处理")
        self._pending_tasks.clear()

        self._start_btn.setEnabled(False)
        self._start_btn.setText("处理中...")

    def _on_clear_list(self):
        """清空任务列表。"""
        active = self._scheduler.active_count()
        if active > 0:
            reply = QMessageBox.question(
                self, "确认",
                f"有 {active} 个任务正在处理中，\n清空列表不会中断正在进行的任务。\n是否继续？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return

        self._scheduler.clear_queue()
        self._task_panel.clear_all()
        self._pending_tasks.clear()
        self._log_panel.append_info("任务列表已清空")
        self._start_btn.setEnabled(True)
        self._start_btn.setText("▶ 开始转换")

    def _get_subtitle_options(self) -> SubtitleOptions:
        """根据当前界面选项构造 SubtitleOptions。"""
        export = self._export_srt_check.isChecked()
        embed = self._embed_sub_check.isChecked()

        # 如果选择了特定轨道，传递选中索引；否则 None 表示全部
        if self._subtitle_track_selector.isHidden():
            selected = None  # 还没有探测到字幕，默认全选
        elif self._subtitle_track_selector.is_all_selected():
            selected = None
        else:
            selected = self._subtitle_track_selector.get_selected_indices()

        return SubtitleOptions(
            export_srt=export,
            embed_in_mp4=embed,
            selected_tracks=selected,
        )

    def _get_encoding_options(self) -> EncodingOptions:
        """根据当前界面选项构造 EncodingOptions。"""
        # 输出分辨率
        resolution_text = self._resolution_combo.currentText()
        resolution = OutputResolution.ORIGINAL
        for r in OutputResolution:
            if r.value == resolution_text:
                resolution = r
                break

        # 编码质量
        quality_text = self._quality_combo.currentText()
        quality = EncodingPreset.HIGH
        for p in EncodingPreset:
            if p.value == quality_text:
                quality = p
                break

        return EncodingOptions(
            output_resolution=resolution,
            quality_preset=quality,
            use_gpu=self._gpu_check.isEnabled() and self._gpu_check.isChecked(),
            gpu_encoder=self._gpu_encoder or "",
        )

    @staticmethod
    def _button_style() -> str:
        """普通按钮样式。"""
        return """
            QPushButton {
                border: 1px solid #ccc;
                border-radius: 4px;
                padding: 6px 12px;
                font-size: 12px;
                background-color: #fff;
            }
            QPushButton:hover {
                background-color: #f5f5f5;
                border-color: #aaa;
            }
            QPushButton:pressed {
                background-color: #e8e8e8;
            }
        """

    @staticmethod
    def _primary_button_style() -> str:
        """主操作按钮样式（蓝色强调）。"""
        return """
            QPushButton {
                border: 1px solid #4a90d9;
                border-radius: 6px;
                padding: 8px 16px;
                font-size: 14px;
                font-weight: bold;
                color: #fff;
                background-color: #4a90d9;
            }
            QPushButton:hover {
                background-color: #357abd;
                border-color: #357abd;
            }
            QPushButton:pressed {
                background-color: #2a6cb5;
            }
            QPushButton:disabled {
                background-color: #a0c4e8;
                border-color: #a0c4e8;
            }
        """

    # ===== 窗口关闭 =====

    def closeEvent(self, event):
        """关闭窗口时的确认（如有活动任务）。"""
        active = self._scheduler.active_count()
        if active > 0:
            reply = QMessageBox.question(
                self, "确认退出",
                f"还有 {active} 个任务正在处理中，\n退出将中断所有任务。\n确定退出吗？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
        event.accept()
