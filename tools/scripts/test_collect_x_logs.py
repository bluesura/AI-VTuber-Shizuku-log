import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from collect_x_logs import discover_ids, merge, status_row


class CollectTests(unittest.TestCase):
    handle = "Shizuku_AItuber"

    def page(self, ids, cursor):
        return (200, {"code": 200, "results": [
            {"id": pid, "author": {"screen_name": self.handle}} for pid in ids
        ], "cursor": {"bottom": cursor}})

    def test_discovery_rejects_404_even_with_body_code_200(self):
        client = Mock()
        client.get.side_effect = [self.page(["4"], "a"), (404, {"code": 200, "results": []})]
        with self.assertRaisesRegex(ValueError, "HTTP 404"):
            discover_ids(client, self.handle, "2", allow_gap=True)

    def test_discovery_rejects_longer_cursor_cycle(self):
        client = Mock()
        client.get.side_effect = [self.page(["6"], "a"), self.page(["5"], "b"), self.page(["4"], "a")]
        with self.assertRaisesRegex(ValueError, "循環"):
            discover_ids(client, self.handle, "2", allow_gap=True)

    def test_exact_stop_and_gap(self):
        client = Mock()
        client.get.return_value = self.page(["1", "3", "2", "4"], None)
        self.assertEqual(discover_ids(client, self.handle, "2", allow_gap=False), ["3", "4"])
        with self.assertRaisesRegex(ValueError, "到達"):
            discover_ids(client, self.handle, "5", allow_gap=False)

    def test_status_anonymization_and_idempotent_merge(self):
        client = Mock()
        tweet = {"id": "123", "created_timestamp": 1772397000, "author": {"screen_name": self.handle},
                 "text": "@Viewer に返信", "replying_to": {"status": "122", "screen_name": "Viewer"},
                 "quote": {"id": "121", "author": {"screen_name": "Viewer"}, "text": "private quote"}}
        client.get.return_value = (200, {"code": 200, "status": tweet})
        row = status_row(client, self.handle, "123", {self.handle.lower()}, "2026-11-27")
        self.assertEqual(row["type"], "REPLY")
        self.assertEqual(row["reply_to_post_id"], "122")
        self.assertTrue(row["reply_to_author"].startswith("User_"))
        self.assertNotIn("Viewer", row["text"])
        self.assertEqual(row["quote_text"], "")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.assertEqual(merge(root, self.handle, [row], dry_run=True), 1)
            self.assertFalse(list(root.iterdir()))
            self.assertEqual(merge(root, self.handle, [row], dry_run=False), 1)
            self.assertEqual(merge(root, self.handle, [row], dry_run=False), 0)
