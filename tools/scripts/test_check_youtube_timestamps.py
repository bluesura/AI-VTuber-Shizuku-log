from __future__ import annotations

import contextlib
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

import check_youtube_timestamps as module


VID = "13GzMhFse0A"


class DetectionTests(unittest.TestCase):
    def test_post_date_and_header_are_not_playback_timestamps(self):
        text = "# コメント一覧\n# 件数: 1\n[2026-11-02 12:34 JST] @User_12345678（👍 0）\n感想です\n"
        self.assertEqual(module.timestamp_markers(text, VID), 0)

    def test_single_timestamp_is_enough(self):
        self.assertEqual(module.timestamp_markers("27:32 おー！", VID), 1)
        self.assertEqual(module.timestamp_markers("[03:22] 挨拶\n[1:00:25] 告知", VID), 2)

    def test_reply_date_is_not_a_timestamp(self):
        self.assertEqual(module.timestamp_markers("    ↳ [2026-11-02 12:34 JST] @User_12345678", VID), 0)

    def test_fullwidth_timestamp_and_hashtag_body(self):
        self.assertEqual(module.timestamp_markers("#目次\n０３：２２ 挨拶", VID), 1)

    def test_seek_link_must_target_same_video(self):
        self.assertEqual(module.timestamp_markers(f"https://youtu.be/{VID}?t=202", VID), 1)
        self.assertEqual(module.timestamp_markers("https://youtu.be/u2T4jUpRDlM?t=202", VID), 0)


class RefreshTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo = Path(self.tmp.name)
        folder = self.repo / "logs/youtube/2026/2026-10-31_test"
        folder.mkdir(parents=True)
        (folder / f"{VID}.info.txt").write_text(f"タイトル  : テスト配信\n動画ID    : {VID}\n", encoding="utf-8")
        self.target = folder / f"{VID}.comments.txt"
        self.old = "# コメント一覧\n# 件数: 1\n[2026-11-02 12:34 JST] @User_12345678（👍 0）\n感想\n"
        self.target.write_text(self.old, encoding="utf-8")

    def info(self, text):
        return {"id": VID, "comments": [{"id": "comment1", "author": "テスト用表示名",
                                        "text": text, "timestamp": 1760000000}]}

    def check(self, **kwargs):
        with contextlib.redirect_stdout(io.StringIO()):
            return module.check_video(self.repo, VID, **kwargs)

    def test_existing_local_does_not_fetch_or_rewrite(self):
        self.target.write_text(self.old + "[03:22] 挨拶", encoding="utf-8")
        before = self.target.read_bytes()
        fetch = Mock(side_effect=AssertionError("must not fetch"))
        result = self.check(fetcher=fetch)
        self.assertFalse(result["generate"])
        fetch.assert_not_called()
        self.assertEqual(self.target.read_bytes(), before)

    def test_refresh_finds_existing_and_keeps_authors_anonymous(self):
        result = self.check(fetcher=lambda _: self.info("[03:22] 挨拶"))
        self.assertEqual(result["status"], "existing_after_refresh")
        self.assertFalse(result["generate"])
        text = self.target.read_text(encoding="utf-8")
        self.assertIn("@User_", text)
        self.assertNotIn("テスト用表示名", text)
        backups = list((self.repo / "outputs").rglob("*.before.txt"))
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].read_text(encoding="utf-8"), self.old)

    def test_generate_only_after_successful_refresh_without_timestamps(self):
        result = self.check(fetcher=lambda _: self.info("更新された感想"))
        self.assertEqual(result["status"], "needs_generation")
        self.assertTrue(result["generate"])

    def test_force_refresh_even_if_local_has_timestamps(self):
        self.target.write_text(self.old + "03:22 挨拶", encoding="utf-8")
        fetch = Mock(return_value=self.info("04:00 更新版目次"))
        result = self.check(refresh=True, fetcher=fetch)
        fetch.assert_called_once_with(VID)
        self.assertEqual(result["status"], "existing_after_refresh")

    def test_check_only_never_declares_generation_needed(self):
        fetch = Mock()
        result = self.check(check_only=True, fetcher=fetch)
        self.assertEqual(result["status"], "refresh_required")
        self.assertFalse(result["generate"])
        fetch.assert_not_called()

    def test_failed_refresh_preserves_file(self):
        before = self.target.read_bytes()
        with self.assertRaises(RuntimeError):
            self.check(fetcher=Mock(side_effect=RuntimeError("network failure")))
        self.assertEqual(self.target.read_bytes(), before)

    def test_empty_refresh_does_not_erase_old_comments(self):
        before = self.target.read_bytes()
        with self.assertRaises(RuntimeError):
            self.check(fetcher=lambda _: {"id": VID, "comments": []})
        self.assertEqual(self.target.read_bytes(), before)

    def test_concurrent_change_is_not_overwritten(self):
        def fetch(_):
            self.target.write_text("他の作業による変更", encoding="utf-8")
            return self.info("03:22 挨拶")
        with self.assertRaises(RuntimeError):
            self.check(fetcher=fetch)
        self.assertEqual(self.target.read_text(encoding="utf-8"), "他の作業による変更")


if __name__ == "__main__":
    unittest.main()
