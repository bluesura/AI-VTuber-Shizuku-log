from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).with_name("update_shizuku_logs.py")
SPEC = importlib.util.spec_from_file_location("update_shizuku_logs", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class UpdateShizukuLogsTests(unittest.TestCase):
    def test_collect_local_video_ids_from_names_and_info(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            folder = root / "2026" / "2026-09-01_テスト"
            folder.mkdir(parents=True)
            (folder / "abcdefghijk.live_chat.txt").write_text("", encoding="utf-8")
            (folder / "legacy.info.txt").write_text(
                "動画ID    : ZYXWVUTSRQP\n", encoding="utf-8"
            )

            self.assertEqual(
                MODULE.collect_local_video_ids(root),
                {"abcdefghijk", "ZYXWVUTSRQP"},
            )

    def test_parse_completed_streams_excludes_live_and_upcoming(self):
        payload = {
            "entries": [
                {"id": "abcdefghijk", "title": "終了", "duration": 120, "url": "abcdefghijk"},
                {"id": "ABCDEFGHIJK", "title": "配信中", "live_status": "is_live"},
                {"id": "12345678901", "title": "予約", "duration": None},
            ]
        }
        streams = MODULE.parse_completed_streams(payload)

        self.assertEqual([stream.video_id for stream in streams], ["abcdefghijk"])
        self.assertEqual(streams[0].url, "https://www.youtube.com/watch?v=abcdefghijk")

    def test_install_session_organizes_by_year(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            session = root / "downloads_20260909_1200"
            source = session / "2026-09-08_新しい配信"
            source.mkdir(parents=True)
            (source / "abcdefghijk.info.txt").write_text(
                "動画ID    : abcdefghijk\n", encoding="utf-8"
            )
            (source / "abcdefghijk.ja.srt").write_text("subtitle\n", encoding="utf-8")
            library = root / "logs" / "youtube"

            installed = MODULE.install_session(session, library)

            self.assertEqual(installed, {"abcdefghijk"})
            destination = library / "2026" / "2026-09-08_新しい配信"
            self.assertTrue((destination / "abcdefghijk.info.txt").is_file())
            self.assertTrue((destination / "abcdefghijk.ja.srt").is_file())

    def test_install_session_does_not_overwrite_different_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            folder_name = "2026-09-08_新しい配信"
            session_source = root / "downloads_1" / folder_name
            session_source.mkdir(parents=True)
            (session_source / "abcdefghijk.info.txt").write_text("new\n", encoding="utf-8")
            destination = root / "library" / "2026" / folder_name
            destination.mkdir(parents=True)
            (destination / "abcdefghijk.info.txt").write_text("old\n", encoding="utf-8")

            with self.assertRaises(FileExistsError):
                MODULE.install_session(root / "downloads_1", root / "library")


if __name__ == "__main__":
    unittest.main()
