# 视频格式转码工具

将视频文件无损转码为 MP4 格式，支持字幕提取/嵌入，4K→1080p 高质量缩放，GPU 硬件加速。

## 功能

- **无损转码**：MKV / MP4 / AVI / MOV 等格式 → MP4，流复制不重新编码
- **字幕处理**：提取为 SRT 文件 + 嵌入 MP4（mov_text）
- **4K 缩放**：→ 1080p / 720p，libx264 + lanczos 缩放，画质损失最小
- **GPU 加速**：自动检测 NVIDIA / AMD / Intel 显卡，速度提升 5-10 倍
- **批量处理**：拖放文件，FIFO 队列，实时进度显示
- **偏好记忆**：所有选项自动保存

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 下载 FFmpeg

从 https://www.gyan.dev/ffmpeg/builds/ 下载 `ffmpeg-release-essentials.zip`，解压后将 `bin/ffmpeg.exe` 放入项目的 `ffmpeg/` 目录。

### 3. 运行

```bash
python main.py
```

## 打包为 EXE

```bash
build.bat
```

输出在 `dist/视频格式转码工具/`。

## 编码质量参考（4K → 1080p）

| 质量预设 | CPU（CRF） | GPU（CQ） | 画质 |
|---------|-----------|----------|------|
| 极高 | CRF 14 | CQ 20 | 主观无损 |
| 高 | CRF 18 | CQ 24 | 肉眼难辨 |
| 标准 | CRF 22 | CQ 28 | 优秀 |

## 项目结构

```
├── main.py              # 程序入口
├── core/
│   ├── engine.py        # FFmpeg 引擎（QProcess 异步架构）
│   ├── scheduler.py     # 任务调度（多线程 + 信号）
│   └── models.py        # 数据模型
├── gui/
│   ├── main_window.py   # 主窗口
│   ├── task_panel.py    # 任务列表
│   ├── log_panel.py     # 日志面板
│   └── widgets.py       # 自定义控件
├── utils/
│   └── __init__.py      # 字幕工具
└── tests/
    └── test_engine.py   # 单元测试
```

## 技术栈

- Python 3.12 + PyQt6
- FFmpeg（QProcess 异步架构，无 UI 卡顿）
- 多线程信号槽（Qt 原生，非 subprocess）
