"""任务列表面板：使用 QTableWidget 展示所有任务的进度与状态。"""

from typing import Optional, Dict

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView, QPushButton, QHBoxLayout,
)
from PyQt6.QtGui import QFont

from core.models import VideoTask, TaskStatus
from gui.widgets import StatusLabel, TaskProgressBar


class TaskPanel(QWidget):
    """任务列表表格面板。

    列：序号 | 文件名 | 状态 | 进度 | 详情
    """

    remove_task_requested = pyqtSignal(str)  # 请求移除任务，参数: input_path

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # 表格
        self._table = QTableWidget(0, 4)
        self._table.setHorizontalHeaderLabels(["文件名", "状态", "进度", ""])
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setAlternatingRowColors(True)
        self._table.verticalHeader().setVisible(False)
        self._table.setShowGrid(False)

        # 列宽
        header = self._table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        self._table.setColumnWidth(1, 70)
        self._table.setColumnWidth(2, 120)
        self._table.setColumnWidth(3, 60)

        self._table.setStyleSheet("""
            QTableWidget {
                border: 1px solid #e0e0e0;
                font-size: 12px;
            }
            QTableWidget::item {
                padding: 4px;
            }
            QHeaderView::section {
                background-color: #f5f5f5;
                border: none;
                border-bottom: 2px solid #ddd;
                padding: 6px;
                font-weight: bold;
            }
        """)

        layout.addWidget(self._table)

        # 存储任务项与行号的映射
        self._row_map: Dict[str, int] = {}  # input_path → 行号

        # 字体
        self._font = QFont()
        self._font.setPixelSize(13)

    def add_task(self, task: VideoTask):
        """在表格中添加一行新任务。"""
        row = self._table.rowCount()
        self._table.insertRow(row)
        self._table.setRowHeight(row, 36)

        # 文件名
        file_item = QTableWidgetItem(task.file_name)
        file_item.setToolTip(task.input_path)
        file_item.setFont(self._font)
        self._table.setItem(row, 0, file_item)

        # 状态标签
        status_widget = StatusLabel(task.status.value)
        self._table.setCellWidget(row, 1, status_widget)

        # 进度条
        progress_bar = TaskProgressBar()
        progress_bar.setValue(task.progress_percent)
        self._table.setCellWidget(row, 2, progress_bar)

        # 移除按钮
        remove_btn = QPushButton("✕")
        remove_btn.setFixedSize(28, 28)
        remove_btn.setToolTip("移除此任务")
        remove_btn.setStyleSheet("""
            QPushButton {
                border: none;
                color: #999;
                font-size: 14px;
                font-weight: bold;
                border-radius: 4px;
            }
            QPushButton:hover {
                color: #dc3545;
                background-color: #f8d7da;
            }
        """)
        input_path = task.input_path
        remove_btn.clicked.connect(lambda checked=False, p=input_path: self.remove_task_requested.emit(p))
        self._table.setCellWidget(row, 3, remove_btn)

        self._row_map[task.input_path] = row

    def update_progress(self, input_path: str, percent: int):
        """轻量更新进度条（不触发整行重绘，高频调用安全）。"""
        row = self._row_map.get(input_path)
        if row is None or row >= self._table.rowCount():
            return
        progress_bar = self._table.cellWidget(row, 2)
        if isinstance(progress_bar, TaskProgressBar):
            progress_bar.setValue(percent)

    def update_task(self, task: VideoTask):
        """更新某个任务的状态、进度显示。"""
        row = self._row_map.get(task.input_path)
        if row is None or row >= self._table.rowCount():
            return

        # 更新状态
        status_widget = self._table.cellWidget(row, 1)
        if isinstance(status_widget, StatusLabel):
            status_widget.set_status(task.status.value)

        # 更新进度
        progress_bar = self._table.cellWidget(row, 2)
        if isinstance(progress_bar, TaskProgressBar):
            progress_bar.setValue(task.progress_percent)

    def remove_task(self, input_path: str):
        """从表格中移除一行。"""
        row = self._row_map.pop(input_path, None)
        if row is not None and row < self._table.rowCount():
            self._table.removeRow(row)
            # 更新后续行的 row 映射
            new_map = {}
            for path, r in self._row_map.items():
                if r > row:
                    new_map[path] = r - 1
                else:
                    new_map[path] = r
            self._row_map = new_map

    def clear_all(self):
        """清空所有行。"""
        self._table.setRowCount(0)
        self._row_map.clear()

    def task_exists(self, input_path: str) -> bool:
        """检查任务是否已在列表中。"""
        return input_path in self._row_map
