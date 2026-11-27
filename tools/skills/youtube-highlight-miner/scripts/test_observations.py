import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from compact_ledgers import compact
from mine_highlights import find_files, main
from ocr_observations import Observation, group_observations

VID = "ABCDEFGHIJK"


def frame(ms, *lines):
    return {"pts_ms": ms, "region": 0, "frame": f"frames/{ms}.png", "lines": [
        {"text": text, "box": [8, y, 120, y + 25]} for text, y in lines
    ]}


def group(root, frames, observations):
    manifest = root / "frames.jsonl"
    manifest.write_text("".join(json.dumps(f) + "\n" for f in frames), encoding="utf-8")
    return group_observations(
        [Observation(ms, text, VID + ".screen-ocr.txt", i) for i, (ms, text) in enumerate(observations, 1)],
        [manifest],
    )


class OCRTests(unittest.TestCase):
    def test_shared_scrolling_line_survives_neighbor_ocr_variation(self):
        with tempfile.TemporaryDirectory() as temp:
            groups = group(Path(temp), [
                frame(0, ("上へ流れる同じ行", 80), ("一行目の断片", 110)),
                frame(250, ("上へ流れる同じ行", 75), ("異なる行の断片", 105)),
            ], [(0, "上へ流れる同じ行\n一行目の断片"),
                (250, "上へ流れる同じ行\n異なる行の断片 [要確認: f2]")])
        self.assertEqual([g["text"] for g in groups],
                         ["上へ流れる同じ行", "一行目の断片", "異なる行の断片"])
        self.assertEqual([x["ms"] for x in groups[0]["observations"]], [0, 250])
        self.assertEqual([x["part"] for x in groups[0]["observations"]], [1, 1])
        self.assertTrue(groups[0]["review"])

    def test_cycle_has_position_and_three_line_sequence_evidence(self):
        lines = ["最初の長い字幕です", "次の長い字幕です", "最後の長い字幕です"]
        frames = [frame(i * 1000 + offset, (text, position))
                  for i, text in enumerate(lines * 2)
                  for offset, position in ((0, 90), (250, 84), (500, 78), (750, 72))]
        observations = [(i * 1000, text) for i, text in enumerate(lines * 2)]
        with tempfile.TemporaryDirectory() as temp:
            groups = group(Path(temp), frames, observations)
            self.assertEqual([g["text"] for g in groups], lines)
            self.assertTrue(all(g["cycle"] and len(g["observations"]) == 2 for g in groups))
            # 空白で前の表示が消えた後の言い直しは別の観測として残る。
            distinct = group(Path(temp), frames[:12] + [frame(2900)] + frames[12:], observations)
            self.assertEqual(len(distinct), 6)

    def test_text_only_repeats_are_candidates_and_remain_separate(self):
        observations = [Observation(i * 1000, "同じ短いセリフ", "src", i + 1) for i in range(3)]
        groups = group_observations(observations)
        self.assertEqual(len(groups), 3)
        self.assertTrue(groups[-1]["replay_candidate"])
        self.assertFalse(any(g["cycle"] for g in groups))

    def test_ocr_only_cli_keeps_milliseconds_and_outputs_each_piece_once(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp) / "input"
            base.mkdir()
            (base / f"{VID}.screen-ocr.txt").write_text(
                "[00:00:00.250] 単独の発言 [要確認: f1]\n"
                "[00:00:02.500] 本当に繰り返した発言\n"
                "[00:00:04.750] 本当に繰り返した発言\n", encoding="utf-8")
            out = Path(temp) / "out"
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main([str(base), "--out-dir", str(out), "--video-id", VID, "--no-frames"]), 0)
            text = (out / "timeline.txt").read_text(encoding="utf-8")
            self.assertIn("[00:00.250] O00001 単独の発言 [要確認]", text)
            self.assertEqual(text.count("単独の発言"), 1)
            self.assertEqual(text.count("本当に繰り返した発言"), 2)
            self.assertFalse((out / "condensed.txt").exists())

    def test_compact_retains_other_videos_and_external_links(self):
        with tempfile.TemporaryDirectory() as temp:
            p = Path(temp) / f"{VID}.highlights.compiled.md"
            own = f"[1:00](<https://www.youtube.com/watch?v={VID}&t=61s>)"
            other = "[1:20](<https://www.youtube.com/watch?v=BCDEFGHIJKL&t=80s>)"
            external = "[参考](https://example.org/source)"
            data = f"- **動画ID**: `{VID}`\n{own} {other} {external}\n"
            p.write_text(data, encoding="utf-8")
            self.assertEqual(compact(p), data.replace(own, "[1:00](t=61s)"))
            self.assertEqual(p.read_text(encoding="utf-8"), data)

    def test_video_selection_does_not_fall_back_to_other_ids(self):
        with tempfile.TemporaryDirectory() as temp:
            p = Path(temp)
            other = p / "BCDEFGHIJKL.ja.srt"
            other.touch()
            self.assertEqual(find_files(p, "*.srt", VID), [])
            neutral = p / "subtitle.srt"
            neutral.touch()
            self.assertEqual(find_files(p, "*.srt", VID), [neutral])
