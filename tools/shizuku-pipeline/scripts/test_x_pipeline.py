"""Xのログ配置・新旧スキーマ・カードの投稿者確認を検証する。"""
import contextlib
import csv
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import doctor
import s0_intake
import s1_normalize
import s2_ingest
import s2_pack
import shizulib


NEW_HEADER = """post_id date_utc author type text extracted_urls quote_post_id quote_author
quote_text reply_to_post_id reply_to_author media_urls likes reposts replies views snapshot_date
metrics_date source_method quality_flags""".split()
LEGACY_HEADER = "id URL 日付 投稿者 種類 本文 抽出URL 引用URL 引用内容 メディアURL いいね数 リポスト数 返信数 表示数 snapshot_date".split()


def write_tsv(path, header, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=header, delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)


class XPipelineTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.data = self.root / "pipeline" / "data"
        for module in (s0_intake, s1_normalize, s2_pack, s2_ingest, doctor, shizulib):
            patcher = patch.object(module, "DATA", self.data)
            patcher.start()
            self.addCleanup(patcher.stop)
        patcher = patch.object(doctor, "BASE", self.data.parent)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.raw = self.data / "raw" / "x"
        self.raw.mkdir(parents=True)
        self.current = {
            "post_id": "123", "date_utc": "2023-01-31T15:05:00.000Z", "author": "Shizuku_AItuber",
            "type": "REPLY", "text": '雖後□... 「💧」だけ\t"引用符"',
            "extracted_urls": "https://example.org/a https://example.org/b",
            "quote_post_id": "120", "quote_author": "cumulo_autumn", "quote_text": "引用元",
            "reply_to_post_id": "122", "reply_to_author": "User_abcdef12",
            "media_urls": "https://pbs.twimg.com/media/a.jpg?name=orig",
            "likes": "42", "reposts": "", "replies": "0", "views": "1034",
            "snapshot_date": "2026-11-25", "metrics_date": "2026-05-22",
            "source_method": "web_dom+fx+fx_thread", "quality_flags": "count_uncertain|error_fixed",
        }
        self.legacy = {
            "id": "1", "URL": "https://x.com/Shizuku_AItuber/status/124?ref=1",
            "日付": "2023-04-02T01:03:00.000Z", "投稿者": "Shizuku_AItuber",
            "種類": "QUOTE_RETWEET", "本文": "旧本文", "抽出URL": "https://example.org",
            "引用URL": "https://x.com/cumulo_autumn/status/121", "引用内容": "旧引用本文",
            "いいね数": "1,200", "表示数": "0", "snapshot_date": "2026-05-22",
        }

    def normalize(self):
        output = io.StringIO()
        with patch.object(sys, "argv", ["s1_normalize.py", "--x"]), contextlib.redirect_stdout(output):
            s1_normalize.main()
        return output.getvalue()

    def test_mixed_schemas_roundtrip_and_empty_record(self):
        write_tsv(self.raw / "current.tsv", list(reversed(NEW_HEADER)), [self.current])
        duplicate = dict(self.legacy, URL="https://x.com/Shizuku_AItuber/status/123")
        retweet = dict(self.legacy, URL="https://x.com/cumulo_autumn/status/125", 種類="RETWEET")
        write_tsv(self.raw / "legacy.txt", LEGACY_HEADER, [self.legacy, duplicate, retweet])
        (self.raw / "2025.txt").write_text("なし", encoding="utf-8")

        self.assertIn("2025.txt: 空記録", self.normalize())
        normalized = self.data / "normalized" / "x"
        self.assertEqual({p.name for p in normalized.iterdir()}, {"2023-02.jsonl", "2023-04.jsonl"})
        current, = shizulib.jsonl_read(normalized / "2023-02.jsonl")
        legacy, = shizulib.jsonl_read(normalized / "2023-04.jsonl")
        expected = dict(self.current, url="https://x.com/i/status/123", date_jst="2023-02-01",
                        time_jst="00:05", date_utc="2023-01-31", likes=42, reposts=None,
                        replies=0, views=1034)
        self.assertEqual(current, expected)
        self.assertEqual((legacy["post_id"], legacy["url"], legacy["text"], legacy["quote_text"]),
                         ("124", self.legacy["URL"], "旧本文", "旧引用本文"))
        self.assertEqual((legacy["likes"], legacy["views"], legacy["quote_post_id"]), (1200, 0, "121"))
        self.assertFalse((self.data / "state").exists())

    def test_rebuild_dry_run_aliases_and_missing_month(self):
        path = self.raw / "current.tsv"
        write_tsv(path, NEW_HEADER, [dict(self.current, type="POST")])
        self.assertEqual(next(s1_normalize.read_x_posts(path))[1]["type"], "CONTEXT_TWEET")
        self.normalize()
        month = self.data / "normalized/x/2023-02.jsonl"
        snapshot = month.read_bytes()
        write_tsv(path, NEW_HEADER, [dict(self.current, type="QUOTE", post_id="456")])
        self.assertEqual(next(s1_normalize.read_x_posts(path))[1]["type"], "QUOTE_RETWEET")
        with patch.object(s1_normalize, "DATA", self.data):
            with self.assertRaisesRegex(ValueError, "123"):
                s1_normalize.process_x(dry_run=True)
            s1_normalize.process_x(dry_run=True, allow_removal=["123"])
        self.assertEqual(month.read_bytes(), snapshot)

    def test_doctor_retains_counts_for_both_headers_and_empty_period(self):
        write_tsv(self.raw / "current.txt", NEW_HEADER, [self.current])
        write_tsv(self.raw / "legacy.tsv", LEGACY_HEADER, [self.legacy])
        (self.raw / "2025.txt").write_text("なし", encoding="utf-8")
        (self.raw / "other.md").write_text("メモ", encoding="utf-8")
        self.normalize()
        with contextlib.redirect_stdout(io.StringIO()):
            doctor.main()
        report = (self.data / "review" / "doctor_report.md").read_text(encoding="utf-8")
        self.assertIn("日付が変わったポスト: 1/2件", report)
        self.assertIn("投稿者の内訳: Shizuku_AItuber:2", report)
        self.assertIn("空記録のXログ: 2025.txt", report)
        self.assertIn("ポスト0件の月: 2023-03", report)
        self.assertIn("月別件数: 2023-02:1 / 2023-04:1", report)
        self.assertIn("count_uncertain:1 / error_fixed:1", report)
        self.assertNotIn("TSVとして読めないXログ", report)
        self.assertNotIn("other.md", report)

    def test_intake_copies_canonical_x_and_updates_same_size(self):
        repo = self.root / "repository"
        canonical = repo / "logs" / "twitter(x)" / "2023.txt"
        archived = repo / "outputs" / "phase2" / "2023.txt"
        write_tsv(canonical, NEW_HEADER, [dict(self.current, text="A")])
        write_tsv(archived, NEW_HEADER, [dict(self.current, text="B")])
        write_tsv(self.raw / canonical.name, NEW_HEADER, [dict(self.current, text="C")])
        (canonical.parent / "2025.txt").write_text("なし", encoding="utf-8")
        self.assertEqual(canonical.stat().st_size, (self.raw / canonical.name).stat().st_size)
        with patch.object(sys, "argv", ["s0_intake.py", "--src", str(repo)]), contextlib.redirect_stdout(io.StringIO()):
            s0_intake.main()
        self.assertEqual((self.raw / canonical.name).read_bytes(), canonical.read_bytes())
        self.assertEqual((self.raw / "2025.txt").read_text(encoding="utf-8"), "なし")

    def test_new_row_with_missing_column_is_reported(self):
        path = self.raw / "ShizukuResearch" / "broken.txt"
        path.parent.mkdir()
        path.write_text("\t".join(NEW_HEADER) + "\n123\t2023-01-31T15:05:00.000Z\n", encoding="utf-8")
        self.assertIn("ShizukuResearch/broken.txt:2: TSVの列数が不一致", self.normalize())
        self.assertFalse((self.data / "normalized" / "x").exists())

    def test_account_files_with_the_same_name_reach_s1_and_doctor(self):
        source = self.root / "repository" / "logs" / "twitter(x)"
        accounts = {"Shizuku_AItuber": "123", "cumulo_autumn": "124", "ShizukuResearch": "125"}
        for author, pid in accounts.items():
            write_tsv(source / author / "2023.txt", NEW_HEADER, [dict(self.current, author=author, post_id=pid)])
        (source / "Shizuku_AItuber" / "2025.txt").write_text("なし", encoding="utf-8")

        for root in (source.parents[1], source, source / "cumulo_autumn"):
            output = io.StringIO()
            with patch.object(sys, "argv", ["s0_intake.py", "--src", str(root)]), contextlib.redirect_stdout(output):
                s0_intake.main()
            self.assertIn("cumulo_autumn/2023.txt", output.getvalue())
        self.assertFalse((self.raw / "2023.txt").exists())
        for author in accounts:
            self.assertEqual((self.raw / author / "2023.txt").read_bytes(), (source / author / "2023.txt").read_bytes())

        self.assertIn("Shizuku_AItuber/2025.txt: 空記録", self.normalize())
        records = shizulib.jsonl_read(self.data / "normalized" / "x" / "2023-02.jsonl")
        self.assertEqual({r["author"]: r["post_id"] for r in records}, accounts)
        with contextlib.redirect_stdout(io.StringIO()):
            doctor.main()
        report = (self.data / "review" / "doctor_report.md").read_text(encoding="utf-8")
        self.assertIn("空記録のXログ: Shizuku_AItuber/2025.txt", report)
        for author in accounts:
            self.assertIn(f"{author}:1", report)

    def test_quote_candidates_use_the_normalized_author(self):
        for author, pid in (("@shizuku_aituber", "123"), ("cumulo_autumn", "124"), ("ShizukuResearch", "125")):
            write_tsv(self.raw / author / "2023.txt", NEW_HEADER, [dict(self.current, author=author, post_id=pid)])
        self.normalize()
        pack, = s2_pack.build_x("2023-02", quiet=True)
        posts = [json.loads(line) for line in pack["path"].read_text(encoding="utf-8").splitlines() if line.startswith('{"post_id"')]
        self.assertEqual({r["author"] for r in posts}, {"@shizuku_aituber", "cumulo_autumn", "ShizukuResearch"})
        self.assertTrue(all(r["quote_author"] == "cumulo_autumn" for r in posts))

        def card(kind, pid):
            source = {"type": "x", "post_id": pid}
            if kind == "quote_candidate":
                source["author"] = "Shizuku_AItuber"
            return {"kind": kind, "source": source, "text": self.current["text"], "date_jst": "2023-02-01"}

        path = self.root / "extract.jsonl"
        shizulib.jsonl_write(path, [card("quote_candidate", pid) for pid in ("123", "124", "125", "999")]
                             + [card("event", "124"), card("capability", "125")])
        output = io.StringIO()
        with patch.object(sys, "argv", ["s2_ingest.py", "--file", str(path), "--from", "x:2023-02"]), contextlib.redirect_stdout(output):
            s2_ingest.main()
        stored = shizulib.jsonl_read(self.data / "cards" / "2023-02.jsonl")
        self.assertEqual([(c["kind"], c["source"]["post_id"]) for c in stored],
                         [("quote_candidate", "123"), ("event", "124"), ("capability", "125")])
        self.assertEqual(output.getvalue().count("X名言候補 → 破棄"), 3)


if __name__ == "__main__":
    unittest.main()
