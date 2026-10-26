#!/usr/bin/env python3
"""
bili-subtitle-extractor 单元测试（零网络、零第三方依赖）

怎么跑：
    python tests/test_extractor.py          # 或 python -m unittest discover -s tests

为什么只测这些：本工具的核心价值是「BV 号进去，SRT + TXT 出来」，
其中真正容易改坏、且不需要联网就能验的是纯函数层：
BV 号抽取、SRT 时间格式化、文件名消毒、字幕 body → SRT/TXT、
ASR 文本 → SRT/TXT、字幕择优、缓存读写与过期、SSL 上下文。
联网部分（B站 API / ASR）留给手工冒烟，CI 不碰，避免把网络抖动当成红灯。
"""

import os
import sys
import tempfile
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import bili_subtitle_extractor as be  # noqa: E402


class TestExtractBvid(unittest.TestCase):
    def test_plain_bvid(self):
        self.assertEqual(be.extract_bvid("BV1xx411c7mD"), "BV1xx411c7mD")

    def test_bvid_from_url(self):
        url = "https://www.bilibili.com/video/BV1xx411c7mD/?p=2"
        self.assertEqual(be.extract_bvid(url), "BV1xx411c7mD")

    def test_bvid_from_url_with_query_and_spm(self):
        url = "https://www.bilibili.com/video/BV1xx411c7mD?spm_id_from=333.999"
        self.assertEqual(be.extract_bvid(url), "BV1xx411c7mD")

    def test_invalid_input_raises(self):
        with self.assertRaises(ValueError):
            be.extract_bvid("not-a-bvid")

    def test_regex_anchor(self):
        self.assertIsNotNone(be.BV_RE.match("BV1xx411c7mD"))
        self.assertIsNone(be.BV_RE.match("BV1xx411c7"))  # 只有 9 位，不能放行


class TestFmtSrtTime(unittest.TestCase):
    def test_zero(self):
        self.assertEqual(be.fmt_srt_time(0), "00:00:00,000")

    def test_hms_millis(self):
        self.assertEqual(be.fmt_srt_time(3661.5), "01:01:01,500")

    def test_comma_not_dot(self):
        # SRT 规范用逗号分隔毫秒，写成点会让播放器解析失败
        self.assertNotIn(".", be.fmt_srt_time(1.234))
        self.assertIn(",", be.fmt_srt_time(1.234))

    def test_padding(self):
        self.assertEqual(be.fmt_srt_time(5), "00:00:05,000")


class TestSafeFilename(unittest.TestCase):
    def test_strip_illegal_chars(self):
        self.assertEqual(be.safe_filename('a/b:c*d?e"f<g>h|i'), "a_b_c_d_e_f_g_h_i")

    def test_truncate(self):
        self.assertEqual(len(be.safe_filename("x" * 100, max_len=10)), 10)

    def test_keep_chinese(self):
        self.assertEqual(be.safe_filename("视频标题"), "视频标题")


class TestBodyToSrt(unittest.TestCase):
    def setUp(self):
        self.body = [
            {"from": 0.0, "to": 2.0, "content": "第一句"},
            {"from": 2.0, "to": 4.5, "content": "第二句"},
        ]

    def test_srt_structure(self):
        srt, txt = be.body_to_srt(self.body)
        lines = srt.split("\n")
        self.assertEqual(lines[0], "1")
        self.assertEqual(lines[1], "00:00:00,000 --> 00:00:02,000")
        self.assertEqual(lines[2], "第一句")
        self.assertEqual(lines[4], "2")

    def test_txt_content(self):
        _, txt = be.body_to_srt(self.body)
        self.assertEqual(txt, "第一句\n第二句")

    def test_empty_content_skipped(self):
        body = [{"from": 0, "to": 1, "content": ""},
                {"from": 1, "to": 2, "content": "有字"}]
        srt, txt = be.body_to_srt(body)
        self.assertEqual(txt, "有字")
        self.assertNotIn("无", srt)

    def test_missing_to_defaults_to_from_plus_5(self):
        srt, _ = be.body_to_srt([{"from": 10.0, "content": "x"}])
        self.assertIn("00:00:10,000 --> 00:00:15,000", srt)


class TestAsrTextToSrt(unittest.TestCase):
    def test_sentence_split(self):
        srt, txt = be.asr_text_to_srt("这是一句足够长的句子用于测试断句。这是第二句足够长的句子。")
        self.assertIn("这是一句足够长的句子用于测试断句。", txt)
        self.assertTrue(srt.startswith("1\n"))

    def test_no_content_dropped(self):
        # 断句不能丢字：把所有条目的文字拼回去应与原文（去空白后）一致
        raw = "第一句话内容足够长。第二句话内容足够长。第三句话内容足够长。"
        srt, txt = be.asr_text_to_srt(raw)
        joined = "".join(txt.split("\n"))
        self.assertEqual(joined.replace(" ", ""), raw.replace(" ", ""))

    def test_empty_input(self):
        srt, txt = be.asr_text_to_srt("")
        self.assertEqual(srt, "")
        self.assertEqual(txt, "")

    def test_estimated_timestamps_increase(self):
        srt, _ = be.asr_text_to_srt("第一句话内容足够长。第二句话内容足够长。")
        starts = [ln.split(" --> ")[0] for ln in srt.split("\n") if " --> " in ln]
        self.assertTrue(len(starts) >= 2)
        self.assertLess(starts[0], starts[1])  # 估算时间戳必须递增，否则播放器会倒放


class TestFindBestSubtitle(unittest.TestCase):
    def test_ai_zh_wins(self):
        subs = [{"lan": "en-US", "lan_doc": "英语"},
                {"lan": "ai-zh", "lan_doc": "中文（自动生成）"}]
        self.assertEqual(be.find_best_subtitle(subs)["lan"], "ai-zh")

    def test_chinese_doc_wins_over_other(self):
        subs = [{"lan": "ja", "lan_doc": "日语"},
                {"lan": "zh-Hans", "lan_doc": "中文（简体）"}]
        self.assertEqual(be.find_best_subtitle(subs)["lan"], "zh-Hans")

    def test_fallback_to_first(self):
        subs = [{"lan": "ko", "lan_doc": "韩语"}]
        self.assertEqual(be.find_best_subtitle(subs)["lan"], "ko")

    def test_empty_returns_none(self):
        self.assertIsNone(be.find_best_subtitle([]))


class TestCache(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cache = be.Cache(os.path.join(self.tmp.name, ".cache"))

    def tearDown(self):
        self.tmp.cleanup()

    def test_roundtrip(self):
        self.cache.set("BV1", 123, {"title": "t"})
        self.assertEqual(self.cache.get("BV1", 123)["title"], "t")

    def test_miss_returns_none(self):
        self.assertIsNone(self.cache.get("BVnope", 1))

    def test_expired_returns_none(self):
        self.cache.set("BV2", 1, {"title": "old"})
        p = os.path.join(self.cache.cache_dir, "BV2_1.json")
        import json
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
        data["_cached_at"] = time.time() - (be.CACHE_TTL + 10)
        with open(p, "w", encoding="utf-8") as f:
            json.dump(data, f)
        self.assertIsNone(self.cache.get("BV2", 1))

    def test_corrupted_file_returns_none(self):
        os.makedirs(self.cache.cache_dir, exist_ok=True)
        with open(os.path.join(self.cache.cache_dir, "BV3_1.json"), "w", encoding="utf-8") as f:
            f.write("{ not json")
        self.assertIsNone(self.cache.get("BV3", 1))


class TestSslContext(unittest.TestCase):
    def test_verify_false_disables_checks(self):
        ctx = be.build_ssl_context(False)
        self.assertFalse(ctx.check_hostname)

    def test_default_verifies(self):
        ctx = be.build_ssl_context(True)
        self.assertTrue(ctx.check_hostname)

    def test_context_is_cached(self):
        self.assertIs(be.build_ssl_context(True), be.build_ssl_context(True))


class TestCliContract(unittest.TestCase):
    def test_version_constant_is_semver(self):
        parts = be.__version__.split(".")
        self.assertEqual(len(parts), 3)
        self.assertTrue(all(p.isdigit() for p in parts))

    def test_asr_model_default(self):
        self.assertEqual(be.SILICONFLOW_ASR_MODEL, "FunAudioLLM/SenseVoiceSmall")


if __name__ == "__main__":
    unittest.main(verbosity=2)
