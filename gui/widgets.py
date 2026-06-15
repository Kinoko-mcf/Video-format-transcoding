"""自定义 PyQt6 控件：拖放区域、进度条单元格、状态标签等。"""

import os
from typing import Optional

from PyQt6.QtCore import Qt, pyqtSignal, QSize
from PyQt6.QtGui import QDragEnterEvent, QDropEvent, QColor, QFont
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QProgressBar,
    QStyle, QSizePolicy,
)


class DropZone(QWidget):
    """拖放文件区域，支持拖入多个 MKV 文件。

    发射 files_dropped 信号携带文件路径列表。
    """

    files_dropped = pyqtSignal(list)

    STYLE_DEFAULT = """
        DropZone {
            border: 2px dashed #888;
            border-radius: 8px;
            background-color: #f8f9fa;
        }
    """
    STYLE_HOVER = """
        DropZone {
            border: 2px dashed #4a90d9;
            border-radius: 8px;
            background-color: #e8f0fe;
        }
    """

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setMinimumHeight(120)
        self.setMaximumHeight(150)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # 图标标签
        self._icon_label = QLabel("📂")
        self._icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._icon_label.setStyleSheet("font-size: 32px;")
        layout.addWidget(self._icon_label)

        # 提示文字
        self._hint_label = QLabel("拖放视频文件到此处")
        self._hint_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._hint_label.setStyleSheet("color: #666; font-size: 13px;")
        layout.addWidget(self._hint_label)

        # 副提示
        self._sub_hint = QLabel("支持 MKV / MP4 / AVI / MOV 等常见格式")
        self._sub_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._sub_hint.setStyleSheet("color: #999; font-size: 11px;")
        layout.addWidget(self._sub_hint)

        self.setStyleSheet(self.STYLE_DEFAULT)

    def dragEnterEvent(self, event: QDragEnterEvent):
        """拖拽进入区域时高亮显示。"""
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self.setStyleSheet(self.STYLE_HOVER)

    def dragLeaveEvent(self, event):
        """拖拽离开区域时恢复默认样式。"""
        self.setStyleSheet(self.STYLE_DEFAULT)

    def dropEvent(self, event: QDropEvent):
        """放下文件时收集 MKV 文件路径并发射信号。"""
        self.setStyleSheet(self.STYLE_DEFAULT)

        # 支持的视频格式
        _supported_formats = (
            ".mkv", ".mp4", ".avi", ".mov", ".wmv",
            ".flv", ".webm", ".m4v", ".ts", ".m2ts",
            ".mts", ".vob", ".ogv", ".divx", ".xvid",
        )
        video_files = []
        for url in event.mimeData().urls():
            file_path = url.toLocalFile()
            if os.path.isfile(file_path) and file_path.lower().endswith(_supported_formats):
                video_files.append(file_path)

        if video_files:
            self.files_dropped.emit(video_files)


class StatusLabel(QLabel):
    """带颜色标记的任务状态标签。"""

    COLORS = {
        "等待中": ("#6c757d", "#e9ecef"),   # 灰底黑字
        "处理中": ("#0d6efd", "#cfe2ff"),   # 蓝底蓝字
        "已完成": ("#198754", "#d1e7dd"),   # 绿底绿字
        "失败":   ("#dc3545", "#f8d7da"),   # 红底红字
    }

    def __init__(self, text: str = "", parent: Optional[QWidget] = None):
        super().__init__(text, parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setFixedHeight(26)
        self.setMinimumWidth(60)
        self._apply_style(text)

    def set_status(self, status: str):
        """设置状态文本并更新样式。"""
        self.setText(status)
        self._apply_style(status)

    def _apply_style(self, status: str):
        """应用对应状态的颜色样式。"""
        fg, bg = self.COLORS.get(status, ("#333", "#eee"))
        self.setStyleSheet(f"""
            QLabel {{
                color: {fg};
                background-color: {bg};
                border-radius: 4px;
                padding: 2px 8px;
                font-weight: bold;
                font-size: 12px;
            }}
        """)


class TaskProgressBar(QProgressBar):
    """自定义进度条，纯文本百分比显示。"""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setRange(0, 100)
        self.setValue(0)
        self.setTextVisible(True)
        self.setFormat("%p%")
        self.setFixedHeight(22)
        self.setMinimumWidth(80)
        self.setStyleSheet("""
            QProgressBar {
                border: 1px solid #ddd;
                border-radius: 3px;
                text-align: center;
                font-size: 11px;
                background-color: #f5f5f5;
            }
            QProgressBar::chunk {
                background-color: #4a90d9;
                border-radius: 2px;
            }
        """)


class SelectAllCheckBox(QWidget):
    """带全选/取消全选功能的复选框组，用于字幕轨道选择。"""

    selection_changed = pyqtSignal(list)  # 发射选中的索引列表

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        from PyQt6.QtWidgets import QCheckBox

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(2)

        self._select_all_cb = QCheckBox("全选")
        self._select_all_cb.setChecked(True)
        self._select_all_cb.toggled.connect(self._on_select_all)
        self._layout.addWidget(self._select_all_cb)

        self._track_checkboxes: list = []  # QCheckBox 列表
        self._all_mode = True  # True 表示"所有轨道"模式

    def set_tracks(self, tracks: list) -> None:
        """根据字幕轨道列表重建复选框。"""
        from PyQt6.QtWidgets import QCheckBox

        # 清除旧复选框
        for cb in self._track_checkboxes:
            self._layout.removeWidget(cb)
            cb.deleteLater()
        self._track_checkboxes.clear()

        # 创建新复选框
        for track in tracks:
            cb = QCheckBox(track.display_name)
            cb.setChecked(True)
            cb.toggled.connect(self._emit_selection)
            self._layout.addWidget(cb)
            self._track_checkboxes.append(cb)

        self._select_all_cb.setChecked(True)
        self._emit_selection()

    def get_selected_indices(self) -> list[int]:
        """获取当前选中的轨道索引列表。"""
        return [
            i for i, cb in enumerate(self._track_checkboxes)
            if cb.isChecked()
        ]

    def is_all_selected(self) -> bool:
        """是否所有轨道都被选中。"""
        if not self._track_checkboxes:
            return True
        return all(cb.isChecked() for cb in self._track_checkboxes)

    def _on_select_all(self, checked: bool):
        """全选/取消全选切换。"""
        self._all_mode = checked
        for cb in self._track_checkboxes:
            cb.blockSignals(True)
            cb.setChecked(checked)
            cb.blockSignals(False)
        self._emit_selection()

    def _emit_selection(self):
        """发射选中变化信号。"""
        self.selection_changed.emit(self.get_selected_indices())

    def clear(self):
        """清空所有轨道复选框。"""
        self.set_tracks([])
