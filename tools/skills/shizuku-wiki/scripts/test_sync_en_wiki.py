import contextlib
import io
import json
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path
from unittest.mock import Mock, patch

from sync_en_wiki import GUIDE, apply, glossary, marker_revision, page_pairs, prepare, read_state, save_state, stamp
from wiki_client import API_URL, PageSnapshot, UpdateError, sha256_text


def snapshot(title, rev, text):
    return PageSnapshot(title, rev, "revision-time", "server-time", text)


class SyncTests(unittest.TestCase):
    def test_guide_tables_and_provisional_terms(self):
        guide = GUIDE.read_text(encoding="utf-8")
        self.assertEqual(page_pairs(guide)["Shizuku Lab"], "Shizuku Lab (EN)")
        self.assertNotIn("編集者の方へ", page_pairs(guide))
        approved, review = glossary(guide, "しずくからのおねがいとご主人様")
        self.assertTrue(any("goshujin-sama" in line for line in approved))
        self.assertTrue(any("仮訳" in line for line in review))

    def test_marker_replaces_only_own_line(self):
        text = "content\n<!-- メモ -->\n"
        first = stamp(text, 3)
        second = stamp(first, 4)
        self.assertEqual(marker_revision(second), 4)
        self.assertEqual(second.count("LLM:"), 1)
        self.assertIn("<!-- メモ -->", second)
        with self.assertRaises(UpdateError):
            marker_revision(first + second)

    def test_run_after_save_then_third_party_edit(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            saved = snapshot("Shizuku", 12, stamp("English", 9))
            save_state(directory, saved.title, 9, saved)
            args = Namespace(command="check", state_dir=directory, bootstrap=False)
            client = Mock()
            ja = snapshot("しずく", 9, "日本語")
            client.fetch_page.side_effect = [ja, saved, ja, snapshot("Shizuku", 13, saved.text + "\n")]
            with contextlib.redirect_stdout(io.StringIO()) as output:
                self.assertEqual(prepare(args, client, ja.title, saved.title, ""), 0)
            self.assertIn("同期済み", output.getvalue())
            with self.assertRaisesRegex(UpdateError, "同期記録と異なります"):
                prepare(args, client, ja.title, saved.title, "")
            client.edit_page.assert_not_called()

    def test_apply_records_returned_revision_and_does_not_repost_after_save(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            ja = snapshot("しずく", 9, "日本語")
            en = snapshot("Shizuku", 11, "Old English")
            saved = snapshot("Shizuku", 12, stamp("English", 9))
            plan = directory / "en.json"
            plan.write_text(json.dumps({
                "api_url": API_URL, "ja": ja.title, "en": en.title,
                "ja_rev": ja.revid, "ja_hash": sha256_text(ja.text),
                "en_rev": en.revid, "en_hash": sha256_text(en.text), "bootstrap": True,
                "proposed": saved.text, "proposed_hash": sha256_text(saved.text),
            }), encoding="utf-8")
            args = Namespace(state_dir=directory, plan=plan, yes=True)
            client = Mock()
            client.fetch_page.side_effect = [ja, en, saved, ja, saved]
            client.edit_page.return_value = 12
            with patch("sync_en_wiki.MediaWikiClient", return_value=client), \
                    patch("sync_en_wiki.read_credentials", return_value=("test", "fixture")), \
                    patch("sync_en_wiki.report_saved_revision"), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(apply(args, {ja.title: en.title}), 0)
                self.assertEqual(apply(args, {ja.title: en.title}), 0)
            self.assertEqual(read_state(directory, en.title), (9, 12, sha256_text(saved.text)))
            client.edit_page.assert_called_once()
