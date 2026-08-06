#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
import sys
from pathlib import Path

MODULE_PATH = Path(__file__).with_name("collect_video_durations.py")
spec = importlib.util.spec_from_file_location("collector", MODULE_PATH)
assert spec and spec.loader
collector = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = collector
spec.loader.exec_module(collector)


class DurationTests(unittest.TestCase):
    def test_format_hms(self) -> None:
        self.assertEqual(collector.format_hms(0), "0:00:00")
        self.assertEqual(collector.format_hms(95), "0:01:35")
        self.assertEqual(collector.format_hms(5728), "1:35:28")
        self.assertEqual(collector.format_hms(100 * 3600 + 2), "100:00:02")

    def test_parse_iso8601(self) -> None:
        self.assertEqual(collector.parse_iso8601_duration("PT1H35M28S"), 5728)
        self.assertEqual(collector.parse_iso8601_duration("P1DT2H"), 93600)
        self.assertEqual(collector.parse_iso8601_duration("PT0.5S"), 0)
        self.assertIsNone(collector.parse_iso8601_duration("1:35:28"))

    def test_parse_common_values(self) -> None:
        self.assertEqual(collector.parse_duration_value("1:35:28"), 5728)
        self.assertEqual(collector.parse_duration_value("35:28"), 2128)
        self.assertEqual(collector.parse_duration_value("5728"), 5728)
        self.assertEqual(collector.parse_duration_value(5728), 5728)


class URLTests(unittest.TestCase):
    def test_youtube_variants(self) -> None:
        video_id = "G1kp2SXuFc4"
        urls = [
            f"https://www.youtube.com/watch?v={video_id}",
            f"https://youtu.be/{video_id}?t=1",
            f"https://www.youtube.com/shorts/{video_id}",
            f"https://www.youtube.com/live/{video_id}",
            f"https://www.youtube-nocookie.com/embed/{video_id}",
        ]
        for url in urls:
            self.assertEqual(collector.youtube_video_id(url), video_id)

    def test_non_youtube(self) -> None:
        self.assertIsNone(collector.youtube_video_id("https://vimeo.com/12345"))


class HtmlMetadataTests(unittest.TestCase):
    def test_youtube_length_seconds(self) -> None:
        document = '<script>var x={"title":"Example","lengthSeconds":"5728"};</script>'
        seconds, title, source = collector._extract_meta(document)
        self.assertEqual((seconds, title, source), (5728, "Example", "youtube_html"))

    def test_json_ld_video_object(self) -> None:
        document = '''
        <script type="application/ld+json">
        {"@context":"https://schema.org","@type":"VideoObject","name":"Demo","duration":"PT1H35M28S"}
        </script>
        '''
        seconds, title, source = collector._extract_meta(document)
        self.assertEqual((seconds, title, source), (5728, "Demo", "json_ld"))

    def test_meta_duration(self) -> None:
        document = '''
        <meta property="og:title" content="Demo">
        <meta property="og:video:duration" content="5728">
        '''
        seconds, title, source = collector._extract_meta(document)
        self.assertEqual((seconds, title, source), (5728, "Demo", "html_meta"))


class OutputTests(unittest.TestCase):
    def test_json_summary(self) -> None:
        rows = [
            collector.VideoResult(index=1, url="a", duration="0:01:00", seconds=60, status="ok"),
            collector.VideoResult(index=2, url="b", status="unavailable"),
        ]
        output = json.loads(collector.render_json(rows))
        self.assertEqual(output["summary"]["total_duration"], "0:01:00")
        self.assertEqual(output["summary"]["succeeded"], 1)

    def test_cache_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "cache.json"
            cache = {
                "https://example.test/v": collector.CacheEntry(
                    123.0,
                    collector.asdict(
                        collector.VideoResult(
                            index=0,
                            url="https://example.test/v",
                            duration="0:02:00",
                            seconds=120,
                            status="ok",
                            source="html_meta",
                        )
                    ),
                )
            }
            collector.save_cache(path, cache)
            loaded = collector.load_cache(path)
            self.assertIn("https://example.test/v", loaded)
            self.assertEqual(loaded["https://example.test/v"].result["seconds"], 120)


if __name__ == "__main__":
    unittest.main()
