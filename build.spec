# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller 打包配置文件

使用方式：
    pyinstaller build.spec

或一键打包：
    build.bat

输出位置：dist/视频格式转码工具/
"""

from pathlib import Path

# 项目根目录
_ROOT = Path(__file__).parent

# ========== 通用配置 ==========
APP_NAME = "视频格式转码工具"
APP_EXE_NAME = "VideoTranscoder"

# ========== 检测 FFmpeg ==========
ffmpeg_src = _ROOT / "ffmpeg" / "ffmpeg.exe"
if not ffmpeg_src.exists():
    print("=" * 60)
    print("⚠ 警告: 未找到 ffmpeg/ffmpeg.exe")
    print("  打包后程序将无法正常工作！")
    print("  请从 https://www.gyan.dev/ffmpeg/builds/ 下载 ffmpeg.exe")
    print("  并放置到 ffmpeg/ 目录下")
    print("=" * 60)
    datas_list = []
else:
    print(f"✓ FFmpeg 已就绪: {ffmpeg_src}")
    datas_list = [(str(ffmpeg_src), "ffmpeg")]

# ========== PyInstaller 分析阶段 ==========
a = Analysis(
    # 主入口脚本
    [str(_ROOT / "main.py")],

    # pathex: 让打包后的 exe 能找到项目模块
    pathex=[str(_ROOT)],

    # 二进制文件
    binaries=[],

    # 数据文件：ffmpeg.exe 打包到输出目录的 ffmpeg 子文件夹
    datas=datas_list,

    # 隐藏导入：确保 PyQt6 的模块被打包
    hiddenimports=[
        "PyQt6.QtCore",
        "PyQt6.QtGui",
        "PyQt6.QtWidgets",
        "json",
        "re",
        "os",
        "subprocess",
        "traceback",
        "dataclasses",
        "datetime",
        "pathlib",
        "typing",
        "unittest.mock",  # 如果用到 mock
    ],

    # 忽略不必要的库以减小体积
    excludes=[
        "tkinter",
        "unittest",
        "pytest",
        "setuptools",
        "pip",
        "email",
        "http",
        "xmlrpc",
        "pydoc",
    ],

    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
)

# ========== PYZ ==========
pyz = PYZ(a.pure, a.zipped_data)

# ========== EXE ==========
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name=APP_EXE_NAME,
    icon=None,
    console=False,
    debug=False,
    strip=True,
    upx=True,
)

# ========== 收集为文件夹（非单文件，适合包含 FFmpeg）==========
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name=APP_NAME,
)
