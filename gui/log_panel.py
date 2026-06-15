"""日志面板：实时滚动显示处理过程中的日志信息。"""

from typing import Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QTextEdit, QLabel, QHBoxLayout, QPushButton,
)
from PyQt6.QtGui import QFont, QTextCursor, QColor


class LogPanel(QWidget):
    """日志输出面板，支持颜色标记和自动滚动。

    不同级别的日志使用不同颜色：
    - 普通信息：黑色
    - 成功信息：绿色
    - 错误信息：红色
    - 警告信息：橙色
    """

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # 标题栏
        header_layout = QHBoxLayout()
        title_label = QLabel("📋 处理日志")
        title_label.setStyleSheet("font-weight: bold; font-size: 13px;")
        header_layout.addWidget(title_label)

        header_layout.addStretch()

        clear_btn = QPushButton("清空")
        clear_btn.setFixedSize(50, 24)
        clear_btn.setStyleSheet("""
            QPushButton {
                border: 1px solid #ddd;
                border-radius: 4px;
                font-size: 11px;
                padding: 1px 6px;
            }
            QPushButton:hover {
                background-color: #f0f0f0;
            }
        """)
        clear_btn.clicked.connect(self.clear)
        header_layout.addWidget(clear_btn)

        layout.addLayout(header_layout)

        # 日志文本框
        self._text_edit = QTextEdit()
        self._text_edit.setReadOnly(True)
        self._text_edit.setFont(QFont("Consolas", 10))
        self._text_edit.setStyleSheet("""
            QTextEdit {
                border: 1px solid #e0e0e0;
                border-radius: 4px;
                background-color: #fafafa;
                padding: 4px;
            }
        """)
        self._text_edit.setMinimumHeight(120)

        layout.addWidget(self._text_edit)

        self._max_lines = 500  # 最多保留行数，防内存溢出
        self._line_count = 0

    def append(self, message: str, color: str = "#333"):
        """追加一条日志。

        Args:
            message: 日志内容
            color: 文字颜色（CSS 颜色值）
        """
        self._text_edit.moveCursor(QTextCursor.MoveOperation.End)
        self._text_edit.setTextColor(QColor(color))
        self._text_edit.insertPlainText(message + "\n")
        self._text_edit.moveCursor(QTextCursor.MoveOperation.End)

        # 超出最大行数时，删除最旧的内容
        self._line_count += 1
        if self._line_count > self._max_lines:
            cursor = self._text_edit.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.Start)
            cursor.movePosition(
                QTextCursor.MoveOperation.Down,
                QTextCursor.MoveMode.KeepAnchor,
                self._line_count - self._max_lines
            )
            cursor.removeSelectedText()
            self._line_count = self._max_lines

    def append_info(self, message: str):
        """追加信息日志（默认颜色）。"""
        self.append(message, "#333")

    def append_success(self, message: str):
        """追加成功日志（绿色）。"""
        self.append(message, "#198754")

    def append_error(self, message: str):
        """追加错误日志（红色）。"""
        self.append(message, "#dc3545")

    def append_warning(self, message: str):
        """追加警告日志（橙色）。"""
        self.append(message, "#fd7e14")

    def clear(self):
        """清空所有日志。"""
        self._text_edit.clear()
        self._line_count = 0
