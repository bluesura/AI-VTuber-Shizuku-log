#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


MODULE_PATH = Path(__file__).with_name("update_videos_streams.py")
SPEC = importlib.util.spec_from_file_location("update_videos_streams", MODULE_PATH)
assert SPEC and SPEC.loader
updater = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = updater
SPEC.loader.exec_module(updater)


BASE_SOURCE = """{{DISPLAYTITLE:動画・配信}}
== 配信状況 ==
* 完了済みライブ配信（公開アーカイブ）: 2本
* 年別内訳: 2023年 1本 / 2026年 1本

== 2026年アーカイブ ==
{| class="wikitable sortable"
! 公開日時（JST）
! タグ
! 時間
! タイトル
|-
| 2026-08-01
| 雑談
| 1:00:00
| [https://www.youtube.com/watch?v=AAAAAAAAAAA 既存2026]
|}

== 2023年アーカイブ ==
{| class="wikitable sortable"
! 公開日時（JST）
! タグ
! 時間
! タイトル
|-
| 2023-01-23
| 記念
| 2:00:00
| [https://www.youtube.com/watch?v=BBBBBBBBBBB 既存2023]
|}

== 通常動画 ==
ライブ配信以外の公開動画。

{| class="wikitable sortable"
! 公開日時（JST）
! タグ
! 時間
! タイトル
|-
| 2026-02-23
| 紹介
| 8:56
| [https://www.youtube.com/watch?v=CCCCCCCCCCC 既存動画]
|}

== 更新方針 ==
* 方針
"""


class ParsingTests(unittest.TestCase):
    def test_extract_video_ids(self) -> None:
        self.assertEqual(
            updater.extract_video_ids(BASE_SOURCE),
            {"AAAAAAAAAAA", "BBBBBBBBBBB", "CCCCCCCCCCC"},
        )

    def test_duration_format(self) -> None:
        self.assertEqual(updater._format_duration(59), "0:59")
        self.assertEqual(updater._format_duration(3723), "1:02:03")
        self.assertEqual(updater._format_duration(None), "")

    def test_tag_precedence(self) -> None:
        self.assertEqual(
            updater.classify_tag("【歌枠】登録者1万人突破記念", "stream"), "歌枠"
        )
        self.assertEqual(
            updater.classify_tag("【安田記念】競馬ライブ配信！", "stream"), "同時視聴"
        )
        self.assertEqual(updater.classify_tag("しずくV2.0 初配信", "stream"), "記念")
        self.assertEqual(updater.classify_tag("夏休み総集編", "video"), "まとめ")
        self.assertEqual(updater.classify_tag("AIギャルゲを作る", "short"), "企画")

    def test_was_live_metadata_overrides_videos_tab(self) -> None:
        candidate = updater.Candidate(
            "IIIIIIIIIII", "video", "https://www.youtube.com/watch?v=IIIIIIIIIII"
        )
        metadata = {
            "id": "IIIIIIIIIII",
            "title": "過去配信",
            "live_status": "was_live",
            "release_timestamp": 1_788_800_000,
            "duration": 3600,
        }
        self.assertEqual(updater.entry_from_metadata(candidate, metadata).kind, "stream")

    def test_shorts_are_opt_in(self) -> None:
        requested_urls: list[str] = []

        def fake_ytdlp(command: list[str], timeout: int) -> dict[str, object]:
            del timeout
            requested_urls.append(command[-1])
            return {"entries": []}

        with mock.patch.object(updater, "_run_ytdlp_json", side_effect=fake_ytdlp):
            updater.collect_candidates(["yt-dlp"], set())
        self.assertEqual(requested_urls, [url for _, url in updater.CORE_CHANNEL_TABS])

        requested_urls.clear()
        with mock.patch.object(updater, "_run_ytdlp_json", side_effect=fake_ytdlp):
            updater.collect_candidates(["yt-dlp"], set(), include_shorts=True)
        self.assertEqual(
            requested_urls,
            [url for _, url in updater.CORE_CHANNEL_TABS] + [updater.SHORTS_TAB[1]],
        )


class UpdateTests(unittest.TestCase):
    def test_build_update_only_adds_rows_and_counts(self) -> None:
        before_rows = updater.video_rows(BASE_SOURCE)
        entries = [
            updater.VideoEntry(
                video_id="DDDDDDDDDDD",
                kind="stream",
                published_jst="2026-09-09 21:00",
                tag="雑談",
                duration="1:02:03",
                title="新しい配信",
            ),
            updater.VideoEntry(
                video_id="EEEEEEEEEEE",
                kind="video",
                published_jst="2026-04-01",
                tag="紹介",
                duration="5:00",
                title="新しい動画",
            ),
        ]
        result = updater.build_update(BASE_SOURCE, entries)

        self.assertIn("* 完了済みライブ配信（公開アーカイブ）: 3本", result.text)
        self.assertIn("* 年別内訳: 2023年 1本 / 2026年 2本", result.text)
        self.assertLess(result.text.index("DDDDDDDDDDD"), result.text.index("AAAAAAAAAAA"))
        self.assertLess(result.text.index("EEEEEEEEEEE"), result.text.index("CCCCCCCCCCC"))
        after_rows = updater.video_rows(result.text)
        for video_id, row in before_rows.items():
            self.assertEqual(after_rows[video_id], row)

    def test_new_year_and_short_section(self) -> None:
        entries = [
            updater.VideoEntry(
                video_id="FFFFFFFFFFF",
                kind="stream",
                published_jst="2027-01-02",
                tag="記念",
                duration="1:00:00",
                title="2027年の配信",
            ),
            updater.VideoEntry(
                video_id="GGGGGGGGGGG",
                kind="short",
                published_jst="2026-09-01",
                tag="",
                duration="0:30",
                title="ショート動画",
            ),
        ]
        result = updater.build_update(BASE_SOURCE, entries)
        self.assertLess(result.text.index("== 2027年アーカイブ =="), result.text.index("== 2026年アーカイブ =="))
        self.assertIn("== ショート ==", result.text)
        self.assertIn("2027年 1本", result.breakdown_after)

    def test_duplicate_existing_id_is_rejected(self) -> None:
        entry = updater.VideoEntry(
            video_id="AAAAAAAAAAA",
            kind="stream",
            published_jst="2026-09-01",
            tag="雑談",
            duration="1:00:00",
            title="重複",
        )
        with self.assertRaises(updater.UpdateError):
            updater.build_update(BASE_SOURCE, [entry])

    def test_plan_tampering_is_rejected(self) -> None:
        entry = updater.VideoEntry(
            video_id="HHHHHHHHHHH",
            kind="video",
            published_jst="2026-09-01",
            tag="紹介",
            duration="5:00",
            title="追加動画",
        )
        snapshot = updater.PageSnapshot("動画・配信", 123, "2026-09-01T00:00:00Z", "", BASE_SOURCE)
        result = updater.build_update(BASE_SOURCE, [entry])
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "plan.json"
            updater.save_plan(path, snapshot, result, [])
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["proposed_text"] += "\n予定外"
            path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            plan, additions = updater.load_plan(path)
            with self.assertRaises(updater.UpdateError):
                updater.validate_plan(plan, additions)


if __name__ == "__main__":
    unittest.main()
