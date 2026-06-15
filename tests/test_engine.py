"""FFmpeg 引擎层的单元测试。"""

import os
import unittest
from unittest.mock import patch, MagicMock

# 添加项目路径
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.engine import _parse_duration, probe_video, _get_ffmpeg_path
from utils import language_to_chinese, is_valid_srt


class TestDurationParsing(unittest.TestCase):
    """测试时长解析函数。"""

    def test_standard_format(self):
        """测试标准 HH:MM:SS.mm 格式。"""
        self.assertAlmostEqual(_parse_duration("01:30:45.500"), 5445.5)
        self.assertAlmostEqual(_parse_duration("00:00:00.000"), 0.0)
        self.assertAlmostEqual(_parse_duration("02:00:00.000"), 7200.0)

    def test_edge_cases(self):
        """测试边界情况。"""
        self.assertEqual(_parse_duration(""), 0.0)
        self.assertEqual(_parse_duration("N/A"), 0.0)
        self.assertEqual(_parse_duration(None), 0.0)

    def test_bare_seconds(self):
        """测试纯秒数格式。"""
        self.assertEqual(_parse_duration("123.45"), 123.45)


class TestFFmpegPath(unittest.TestCase):
    """测试 FFmpeg 路径获取。"""

    def test_returns_string(self):
        """测试返回值为字符串。"""
        path = _get_ffmpeg_path()
        self.assertIsInstance(path, str)
        self.assertTrue(len(path) > 0)

    def test_prefer_bundled(self):
        """测试优先返回内置路径。"""
        # 在没有冻结打包的环境下，应返回项目目录下的路径
        path = _get_ffmpeg_path()
        self.assertTrue("ffmpeg" in path)


class TestProbeVideo(unittest.TestCase):
    """测试视频探测功能（需要 FFmpeg）。"""

    def test_nonexistent_file(self):
        """测试不存在的文件返回 None。"""
        result = probe_video("Z:/nonexistent/path/video.mkv")
        self.assertIsNone(result)


class TestLanguageMapping(unittest.TestCase):
    """测试语言代码映射。"""

    def test_known_languages(self):
        """测试已知语言代码。"""
        self.assertEqual(language_to_chinese("chi"), "中文")
        self.assertEqual(language_to_chinese("eng"), "英语")
        self.assertEqual(language_to_chinese("jpn"), "日语")

    def test_unknown_language(self):
        """测试未知语言代码。"""
        self.assertEqual(language_to_chinese("xyz"), "xyz")

    def test_empty_language(self):
        """测试空语言代码。"""
        self.assertEqual(language_to_chinese(""), "未知")
        self.assertEqual(language_to_chinese(None), "未知")


class TestSRTValidation(unittest.TestCase):
    """测试 SRT 文件验证。"""

    def test_nonexistent_file(self):
        """测试不存在的文件。"""
        self.assertFalse(is_valid_srt("nonexistent.srt"))

    def test_valid_srt(self):
        """测试有效的 SRT 文件。"""
        content = """1
00:00:01,000 --> 00:00:04,000
这是一条测试字幕

2
00:00:05,000 --> 00:00:08,000
这是第二条字幕
"""
        with patch("os.path.exists", return_value=True):
            with patch("builtins.open", unittest.mock.mock_open(read_data=content)):
                self.assertTrue(is_valid_srt("test.srt"))

    def test_invalid_content(self):
        """测试无效内容。"""
        with patch("os.path.exists", return_value=True):
            with patch("builtins.open", unittest.mock.mock_open(read_data="这不是字幕文件")):
                self.assertFalse(is_valid_srt("test.srt"))


if __name__ == "__main__":
    unittest.main()
