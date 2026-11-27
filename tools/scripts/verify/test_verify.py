import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import clean_cache
from sweep_text import scan
from time_utils import format_time, parse_time
from verify_citations import CitationIndex, url_source
from verify_roundtrip import main as roundtrip


class VerifyTests(unittest.TestCase):
    def test_time_shapes(self):
        for text, seconds in (("65:30", 3930), ("1:05:30", 3930), ("0:45", 45), ("-02:15", -135)):
            self.assertEqual(parse_time(text), seconds)
            self.assertEqual(parse_time(format_time(seconds)), seconds)
        for text in ("1:60:00", "0:61", ""):
            with self.assertRaises(ValueError):
                parse_time(text)

    def test_negative_chat_and_video_tail(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            vid = "ABCDEFGHIJK"
            stream = root / "normalized/streams" / vid
            stream.mkdir(parents=True)
            (stream / "meta.json").write_text('{"duration_sec":100,"description":"info"}', encoding="utf-8")
            (stream / "chat.tsv").write_text("t\n-135\n-70\n150\n", encoding="utf-8")
            index = CitationIndex(root, root)
            for t in (-135, -10, 90, 150):
                self.assertIsNone(index.check({"type": "yt_chat", "video_id": vid, "t": t}))
            for t in (-136, -2, 89, 151):
                self.assertIsNotNone(index.check({"type": "yt_chat", "video_id": vid, "t": t}))
            source = url_source(f"https://youtu.be/{vid}?t=0")
            self.assertIn("待機チャット", index.check(source))
            self.assertIsNone(index.check({**source, "pre_chat": "-02:15"}))
            self.assertIsNone(index.check({"type": "yt_description", "video_id": vid}))

    def test_sweep_preserves_markers_quotes_and_linked_credits(self):
        text = ("<!-- LLM: ja_revid=10 -->\n<!-- ここまで自動更新 -->\n"
                "「以下に結果をまとめます #ERROR! □」\n"
                "[https://example.org/art @Creator]\n"
                "生ハンドル @Viewer\n<!-- 要確認：出典 -->\n[TBD] ⟦MW0001⟧")
        result = scan(text, set())
        self.assertEqual([(line, level) for line, level, _ in result],
                         [(5, "WARN"), (6, "ERROR"), (7, "ERROR"), (7, "ERROR")])

    def test_roundtrip_checks_multiplicity(self):
        with tempfile.TemporaryDirectory() as temp:
            before, after = (Path(temp) / name for name in ("before.jsonl", "after.jsonl"))
            after.write_text('{"post_id":"1"}\n', encoding="utf-8")
            before.write_text(after.read_text(encoding="utf-8") * 2, encoding="utf-8")
            self.assertEqual(roundtrip([str(before), str(after)]), 1)
            self.assertEqual(roundtrip([str(before), str(after), "--allow-removal", "1"]), 0)

    def test_cleanup_reports_verified_media_and_preserves_backup(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            vid = "ABCDEFGHIJK"
            run = root / "outputs/shizuku-transcribe" / f"run_{vid}_test"
            run.mkdir(parents=True)
            audio = run / "audio.wav"
            previous = run / "previous.transcribe.txt"
            for path in (audio, previous):
                path.write_bytes(b"fixture")
            output = root / "logs/youtube/2026/test" / f"{vid}.transcribe.txt"
            output.parent.mkdir(parents=True)
            output.write_bytes(b"saved")
            receipt = run / "cleanup-receipt.json"
            receipt.write_text(json.dumps({
                "video_id": vid, "files": [audio.name], "output": output.relative_to(root).as_posix(),
                "sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
            }), encoding="utf-8")
            with patch.object(clean_cache, "ROOT", root):
                self.assertEqual(clean_cache.main(["--run", str(run), "--dry-run"]), 0)
                self.assertTrue(audio.exists())
                self.assertEqual(clean_cache.main(["--run", str(run), "--execute"]), 0)
            self.assertFalse(audio.exists())
            self.assertTrue(previous.exists())
            self.assertTrue(output.exists())
