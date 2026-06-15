"""字幕处理工具：字幕轨道解析、SRT 文件验证与管理。"""

import os
import re
from typing import Optional


# 常见语言代码到中文名称的映射
LANGUAGE_MAP = {
    "chi": "中文",
    "zho": "中文",
    "zh": "中文",
    "chs": "简体中文",
    "cht": "繁体中文",
    "eng": "英语",
    "en": "英语",
    "jpn": "日语",
    "ja": "日语",
    "kor": "韩语",
    "ko": "韩语",
    "fre": "法语",
    "fr": "法语",
    "fra": "法语",
    "ger": "德语",
    "de": "德语",
    "deu": "德语",
    "spa": "西班牙语",
    "es": "西班牙语",
    "ita": "意大利语",
    "it": "意大利语",
    "por": "葡萄牙语",
    "pt": "葡萄牙语",
    "rus": "俄语",
    "ru": "俄语",
    "ara": "阿拉伯语",
    "ar": "阿拉伯语",
    "tha": "泰语",
    "th": "泰语",
    "vie": "越南语",
    "vi": "越南语",
    "ind": "印尼语",
    "id": "印尼语",
}


def language_to_chinese(code: str) -> str:
    """将语言代码转为中文名称。"""
    if not code:
        return "未知"
    code_lower = code.lower().strip()
    return LANGUAGE_MAP.get(code_lower, code)


def is_valid_srt(file_path: str) -> bool:
    """快速检查文件是否为有效 SRT 字幕文件。

    通过检查文件头和内容模式判断。

    Args:
        file_path: SRT 文件路径

    Returns:
        是否为有效 SRT
    """
    if not os.path.exists(file_path):
        return False

    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read(1024)  # 只检查前 1024 字节
    except OSError:
        return False

    # SRT 格式：数字序号 → 时间轴 → 文本
    # 简单检测：包含时间轴格式 "HH:MM:SS,mmm --> HH:MM:SS,mmm"
    srt_pattern = r"\d+:\d+:\d+[,.]\d+\s*-->\s*\d+:\d+:\d+[,.]\d+"
    return bool(re.search(srt_pattern, content))


def get_subtitle_summary(file_path: str, max_lines: int = 50) -> str:
    """读取 SRT 文件的前几行纯文本内容用于预览。

    Args:
        file_path: SRT 文件路径
        max_lines: 最大返回行数

    Returns:
        纯文本摘要
    """
    if not os.path.exists(file_path):
        return ""

    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
    except OSError:
        return ""

    # 移除序号和时间轴行，只保留文本
    lines = content.split("\n")
    text_lines = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        # 跳过数字序号
        if line.isdigit():
            continue
        # 跳过时间轴行
        if "-->" in line and ":" in line:
            continue
        # 跳过常见的格式标签
        if line.startswith("{") or line.startswith("<"):
            continue
        text_lines.append(line)
        if len(text_lines) >= max_lines:
            break

    return "\n".join(text_lines)


def generate_output_name(input_file: str, suffix: str = "") -> str:
    """根据输入文件名生成输出文件名。

    Args:
        input_file: 输入文件路径
        suffix: 文件后缀（不含点），如 "mp4", "srt"

    Returns:
        不含扩展名的输出基础名称
    """
    base = os.path.splitext(os.path.basename(input_file))[0]
    if suffix:
        return f"{base}.{suffix}"
    return base
