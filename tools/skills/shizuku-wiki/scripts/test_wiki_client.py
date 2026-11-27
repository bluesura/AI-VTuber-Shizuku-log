import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from urllib.error import HTTPError

from audit_wiki import inspect
from wiki_client import API_URL, MediaWikiClient, PageSnapshot, UpdateError, apply_attempt, sanitize_field


class ClientTests(unittest.TestCase):
    def setUp(self):
        self.client = MediaWikiClient(allowed_titles=("動画・配信",))
        self.base = PageSnapshot("動画・配信", 81, "base-time", "server-time", "old")
        self.client.opener = Mock()

    def test_rejects_unapproved_target_before_token_request(self):
        with self.assertRaises(UpdateError):
            self.client.edit_page(PageSnapshot("年表", 1, "a", "b", "old"), "new", "update")
        self.client.opener.open.assert_not_called()

    def test_structural_text_is_escaped_as_a_field(self):
        self.assertEqual(sanitize_field("a|[[x]]\n{{T}}<a>"),
                         "a&#124;&#91;&#91;x&#93;&#93; &#123;&#123;T&#125;&#125;&lt;a&gt;")

    def test_read_503_is_retried_once(self):
        self.client.opener.open.side_effect = [
            HTTPError(API_URL, 503, "", {}, None),
            io.BytesIO(b'{"query": {}}'),
        ]
        with patch("wiki_client.time.sleep") as sleep:
            self.assertEqual(self.client.request({"action": "query"}), {"query": {}})
        self.assertEqual(self.client.opener.open.call_count, 2)
        sleep.assert_any_call(10)

    def test_429_mentions_retry_after_and_stops(self):
        self.client.opener.open.side_effect = HTTPError(API_URL, 429, "", {"Retry-After": "540"}, None)
        with patch("wiki_client.time.sleep") as sleep, self.assertRaisesRegex(UpdateError, "Retry-After: 540"):
            self.client.request({"action": "query"})
        sleep.assert_not_called()
        self.assertEqual(self.client.opener.open.call_count, 1)

    def test_edit_503_when_already_saved_never_reposts(self):
        from wiki_client import ServiceUnavailable

        saved = PageSnapshot(self.base.title, 82, "a", "b", "new")
        with patch.object(self.client, "_edit_once", side_effect=ServiceUnavailable) as edit, \
                patch.object(self.client, "fetch_page", return_value=saved), patch("wiki_client.time.sleep"):
            self.assertEqual(self.client.edit_page(self.base, "new", "update"), 82)
        edit.assert_called_once()

    def test_edit_503_reposts_only_when_base_matches(self):
        from wiki_client import ServiceUnavailable

        with patch.object(self.client, "_edit_once", side_effect=[ServiceUnavailable, 82]) as edit, \
                patch.object(self.client, "fetch_page", return_value=self.base), patch("wiki_client.time.sleep"):
            self.assertEqual(self.client.edit_page(self.base, "new", "update"), 82)
        self.assertEqual(edit.call_count, 2)

    def test_failures_lock_and_can_be_unlocked(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            for _ in range(3):
                with self.assertRaisesRegex(UpdateError, "attempt failed"), apply_attempt(self.base.title, directory):
                    raise UpdateError("attempt failed")
            with self.assertRaisesRegex(UpdateError, "ロック中"), apply_attempt(self.base.title, directory):
                self.fail("locked execution entered")
            with apply_attempt(self.base.title, directory, unlock=True):
                pass
            with apply_attempt(self.base.title, directory):
                pass

    def test_audit_reads_class_tokens_and_required_categories(self):
        result = inspect("title", '<span class="foo new" title="A"></span><a class="newcategory" title="B"></a>'
                                   '<strong class="error mw-ext-cite-error"></strong>',
                         {"English"}, {"基本"})
        self.assertEqual(result["redlinks"], ["A", "B"])
        self.assertEqual(result["missing_categories"], ["English"])
        self.assertEqual(len(result["cite_errors"]), 1)
