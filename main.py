"""视频格式转码工具 - 程序入口

将 MKV 视频无损转码为 MP4 格式，支持字幕提取与嵌入。
使用 FFmpeg 流复制，不重新编码，不损失画质。
"""

import sys
import os

# 将项目根目录加入 Python 路径，确保打包后也能正常导入
if getattr(sys, 'frozen', False):
    # 打包后的 exe 运行
    _base_dir = os.path.dirname(sys.executable)
else:
    # 开发环境运行
    _base_dir = os.path.dirname(os.path.abspath(__file__))

sys.path.insert(0, _base_dir)

from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QFont

from gui.main_window import MainWindow


def main():
    """应用程序主入口。"""
    app = QApplication(sys.argv)
    app.setApplicationName("视频格式转码工具")
    app.setOrganizationName("VideoTranscoder")

    # 设置全局默认字体（中文字体优先）
    font = QFont("Microsoft YaHei UI", 10)
    app.setFont(font)

    # 应用全局样式表
    app.setStyleSheet("""
        QMainWindow {
            background-color: #fff;
        }
        QToolTip {
            font-size: 11px;
            padding: 2px 6px;
            border: 1px solid #ccc;
            background-color: #fff;
        }
    """)

    # 创建并显示主窗口
    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
