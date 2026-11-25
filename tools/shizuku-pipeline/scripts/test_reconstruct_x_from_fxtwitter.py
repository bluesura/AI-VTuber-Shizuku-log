"""保存済み応答の形式、本文復元、匿名化に関する回帰テスト（ネットワーク不要）。"""
import csv
import io
import json
import tempfile
import unittest
import contextlib
from pathlib import Path
from unittest.mock import patch

import reconstruct_x_from_fxtwitter as reconstruct


class ReconstructionTests(unittest.TestCase):
    whitelist = {"shizuku_aituber", "cumulo_autumn"}

    def test_display_range_emoji_and_url_facets(self):
        raw = "@viewer 💧 https://t.co/a https://t.co/b"
        a = raw.index("https://t.co/a")
        b = raw.index("https://t.co/b")
        tweet = {"raw_text": {
            "text": raw, "display_text_range": [8, len(raw)],
            "facets": [
                {"type": "url", "indices": [a, a + 14], "replacement": "https://example.com/a?x=1&amp;y=2"},
                {"type": "url", "indices": [b, b + 14], "original": "https://t.co/b", "replacement": "https://example.com/b"},
            ],
        }}
        text, urls = reconstruct.extract_fx_body(tweet)
        self.assertEqual(text, "💧 https://example.com/a?x=1&y=2 https://example.com/b")
        self.assertEqual(urls, ["https://example.com/a?x=1&y=2", "https://example.com/b"])
        self.assertEqual(reconstruct.extract_fx_body({"text": "fallback", "raw_text": {"text": "", "display_text_range": [0, 0]}}), ("", []))

    def test_media_only_body_stays_empty(self):
        self.assertEqual(reconstruct.extract_fx_body({"raw_text": {
            "text": "https://t.co/a", "display_text_range": [0, 0],
            "facets": [{"type": "media", "original": "https://t.co/a", "replacement": "photo"}],
        }}), ("", []))

    def test_media_facet_inside_display_range_is_expanded(self):
        text, urls = reconstruct.extract_fx_body({"raw_text": {
            "text": "😦 https://t.co/a", "display_text_range": [0, 16],
            "facets": [{"type": "media", "indices": [2, 16], "original": "https://t.co/a", "replacement": "https://x.com/viewer/status/123/video/1"}],
        }})
        self.assertEqual(text, "😦 https://x.com/viewer/status/123/video/1")
        self.assertEqual(urls, ["https://x.com/viewer/status/123/video/1"])

    def test_media_size_and_video_thumbnail(self):
        self.assertEqual(reconstruct.normalize_media_url("https://pbs.twimg.com/media/a.jpg"), "https://pbs.twimg.com/media/a.jpg?name=orig")
        self.assertEqual(reconstruct.normalize_media_url("https://pbs.twimg.com/media/a?format=jpg&name=small"), "https://pbs.twimg.com/media/a?format=jpg&name=orig")
        self.assertEqual(reconstruct.normalize_media_url("https://pbs.twimg.com/media/a.jpg:large"), "https://pbs.twimg.com/media/a.jpg?name=orig")
        self.assertEqual(reconstruct.extract_fx_media({"media": {"photos": [{"type": "photo", "url": "https://pbs.twimg.com/media/a.jpg"}], "videos": [{"type": "video", "url": "movie.mp4", "thumbnail_url": "thumb.jpg"}]}}), ["https://pbs.twimg.com/media/a.jpg?name=orig", "thumb.jpg"])

    def test_anonymization_is_case_insensitive_and_idempotent(self):
        anon = reconstruct.anonymize_handle("Viewer", self.whitelist)
        self.assertRegex(anon, r"^User_[0-9a-f]{8}$")
        self.assertEqual(anon, reconstruct.anonymize_handle("@VIEWER", self.whitelist))
        self.assertEqual(anon, reconstruct.anonymize_handle(anon, self.whitelist))
        text = reconstruct.anonymize_text("@Viewer @cumulo_autumn https://x.com/Viewer/status/123 https://twitter.com/Viewer", self.whitelist)
        self.assertEqual(text, f"@{anon} @cumulo_autumn https://x.com/i/status/123 @{anon}")

    def test_wrapped_response_validation_and_acquisition_date(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "status_123.json"
            data = {"http_status": 200, "finished_at_jst": "2026-11-24T16:00:00+00:00", "payload": {"code": 200, "status": {"id": "123", "type": "status"}}}
            path.write_text(json.dumps(data), encoding="utf-8")
            self.assertEqual(reconstruct.load_fx_status(path, "123")[1], "2026-11-25")
            with self.assertRaises(ValueError):
                reconstruct.load_fx_status(path, "999")
            data["http_status"] = 404
            path.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaises(ValueError):
                reconstruct.load_fx_status(path, "123")

    def test_dry_run_does_not_create_output_and_source_destination_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            raw = root / "raw"
            raw.mkdir()
            (raw / "2025.txt").write_text("なし", encoding="utf-8")
            with patch.object(reconstruct, "BASE", root), patch.object(reconstruct, "RAW_X_DIR", raw), patch("sys.argv", ["reconstruct", "--dry-run", "--out-dir", "out"]), contextlib.redirect_stdout(io.StringIO()):
                reconstruct.main()
                self.assertFalse((root / "out").exists())
            with patch.object(reconstruct, "BASE", root), patch.object(reconstruct, "RAW_X_DIR", raw), patch("sys.argv", ["reconstruct", "--out-dir", "raw"]), contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as exc:
                    reconstruct.main()
                self.assertEqual(exc.exception.code, 2)
                self.assertEqual((raw / "2025.txt").read_text(encoding="utf-8"), "なし")

    def test_private_quote_is_not_saved_and_parent_id_is_kept(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            src = root / "input.txt"
            fields = ["URL", "日付", "投稿者", "種類", "本文", "引用URL", "引用内容", "メディアURL", "snapshot_date"]
            buf = io.StringIO()
            writer = csv.DictWriter(buf, fieldnames=fields, delimiter="\t")
            writer.writeheader()
            writer.writerow({"URL": "https://x.com/Shizuku_AItuber/status/123", "日付": "2026-01-01T00:00:00.000Z", "投稿者": "Shizuku_AItuber", "種類": "REPLY", "本文": "引用元だけの文章", "引用内容": "引用元だけの文章", "メディアURL": "https://pbs.twimg.com/media/quoted.jpg", "snapshot_date": "2026-05-22"})
            src.write_text(buf.getvalue(), encoding="utf-8")
            status = {"id": "123", "author": {"screen_name": "Shizuku_AItuber"}, "text": "@Viewer 返信", "raw_text": {"text": "@Viewer 返信", "display_text_range": [8, 10]}, "replying_to": {"screen_name": "Viewer", "status": "122"}, "quote": {"id": "121", "author": {"screen_name": "Viewer"}, "text": "引用元だけの文章"}}
            response = root / "status_123.json"
            response.write_text(json.dumps({"payload": {"code": 200, "status": status}, "http_status": 200, "finished_at_jst": "2026-11-25T14:00:00+09:00"}), encoding="utf-8")
            with patch.object(reconstruct, "RESP_DIR", root):
                rows, stats = reconstruct.process_file(src, self.whitelist, False, True)
                self.assertEqual(rows[0]["quote_text"], "")
                self.assertRegex(rows[0]["quote_author"], r"^User_[0-9a-f]{8}$")
                self.assertEqual(rows[0]["reply_to_post_id"], "122")
                self.assertEqual(rows[0]["media_urls"], "")
                self.assertIn("dom_swapped_fixed", rows[0]["quality_flags"])
                self.assertEqual(stats["quote_swapped_fixed"], 1)
                # 応答がない場合も、投稿者不明の旧引用本文を公開出力へ混ぜない。
                with patch.object(reconstruct, "RESP_DIR", root / "missing"):
                    rows, _ = reconstruct.process_file(src, self.whitelist, False, True)
                    self.assertEqual(rows[0]["quote_text"], "")

    def test_legacy_conversion_keeps_account_paths(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for author, pid in (("Shizuku_AItuber", "123"), ("cumulo_autumn", "124")):
                src = root / "legacy" / author / "2026.txt"
                src.parent.mkdir(parents=True)
                src.write_text(f"URL\t日付\t投稿者\nhttps://x.com/{author}/status/{pid}\t2026-01-01T00:00:00.000Z\t{author}\n",
                               encoding="utf-8")
            args = ["reconstruct", "--src-dir", "legacy", "--out-dir", "out"]
            with patch.object(reconstruct, "BASE", root), patch.object(reconstruct, "RESP_DIR", root), \
                    patch("sys.argv", args), contextlib.redirect_stdout(io.StringIO()):
                reconstruct.main()
            self.assertEqual({p.relative_to(root / "out").as_posix() for p in (root / "out").rglob("*.txt")},
                             {"Shizuku_AItuber/2026.txt", "cumulo_autumn/2026.txt"})


if __name__ == "__main__":
    unittest.main()
