from __future__ import annotations

import contextlib
import io
import json
import subprocess
import tempfile
import unittest
import wave
from pathlib import Path
from unittest.mock import patch

import download_youtube_subtitles as DOWNLOADER
import transcribe_youtube as MODULE


VIDEO_ID = "u2T4jUpRDlM"


def write_wave(path: Path, frames: int, rate: int = 1) -> bytes:
    # 低いサンプルレートで1時間超の分割を小さい実データで検証する。
    data = bytes(range(256)) * ((frames * 2 + 255) // 256)
    data = data[:frames * 2]
    with wave.open(str(path), "wb") as target:
        target.setnchannels(1)
        target.setsampwidth(2)
        target.setframerate(rate)
        target.writeframes(data)
    return data


def result(text="テスト", start=1.25, end=3.0):
    return {"stop": "complete", "text": text,
            "segments": [{"start": start, "end": end, "speaker": 0, "text": text}]}


class TranscribeTests(unittest.TestCase):
    def test_split_preserves_all_frames_in_order(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            audio = root / "audio.wav"
            original = write_wave(audio, 4547)
            chunks = MODULE.split_audio(audio, root)
            self.assertEqual([(a, b) for _, a, b in chunks], [(0, 3300), (3300, 4547)])
            actual = b""
            for path, a, b in chunks:
                self.assertLess(b - a, 3600)
                with wave.open(str(path), "rb") as part:
                    actual += part.readframes(part.getnframes())
            self.assertEqual(actual, original)

    def test_one_hour_splits_only_for_comparison(self):
        with tempfile.TemporaryDirectory() as tmp:
            audio = Path(tmp) / "audio.wav"
            write_wave(audio, 3600)
            self.assertEqual(MODULE.split_audio(audio, Path(tmp)), [(audio, 0, 3600)])
            chunks = MODULE.split_audio(audio, Path(tmp), split_at_hour=True)
            self.assertEqual([(a, b) for _, a, b in chunks], [(0, 3300), (3300, 3600)])

    def test_global_timestamps_and_part_local_speakers(self):
        text = MODULE.render_part(result(), 2, 3300, 4547)
        self.assertIn("00:55:01.250 --> 00:55:03.000", text)
        self.assertIn("区間002/話者0: テスト", text)

    def test_untimed_text_is_preserved_without_inventing_time(self):
        text = MODULE.render_part(result(start=None, end=None), 2, 3300, 4547)
        self.assertIn("[時刻未取得]", text)
        self.assertIn("テスト", text)
        text = MODULE.render_part({"stop": "complete", "text": "本文"}, 1, 0, 10)
        self.assertIn("[時刻・話者は未取得]\n本文", text)

    def test_refuses_incomplete_empty_and_out_of_range_results(self):
        incomplete = result()
        incomplete["stop"] = "model_limit"
        for data in (incomplete, result(text=""), result(start=-1), result(end=11), result(end=float("nan"))):
            with self.subTest(data=data), self.assertRaises(ValueError):
                MODULE.render_part(data, 1, 0, 10)

    def test_cleanup_refuses_parent_and_other_directories(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            other = root / "other"
            other.mkdir()
            for target in (root, other):
                with self.assertRaises(ValueError):
                    MODULE.remove_workdir(target, root)
            self.assertTrue(other.is_dir())

    def _workflow(self, root, fail_second=False, *, profile="japanese", device=None):
        video = root / "video"
        video.mkdir()
        (video / f"{VIDEO_ID}.info.txt").write_text("既存情報", encoding="utf-8")
        (video / f"{VIDEO_ID}.live_chat.txt").write_text("既存チャット", encoding="utf-8")
        staging = root / "staging"
        staging.mkdir()
        untouched = staging / "run_previous"
        untouched.mkdir()
        comparison = profile in MODULE.COMPARISON_SUFFIXES
        if comparison:
            for suffix in (".ja.srt", ".transcribe.txt"):
                (video / (VIDEO_ID + suffix)).write_text("既存の字幕", encoding="utf-8")
        if profile == "qwen-comparison":
            (video / f"{VIDEO_ID}.nemotron-3.5-transcribe.txt").write_text("Nemotron原文", encoding="utf-8")

        def fake_run(command, run_dir, name):
            if name == "download":
                (run_dir / "source.mkv").write_bytes(b"video")
            elif name == "audio":
                write_wave(run_dir / "audio.wav", 4547)
            else:
                if fail_second and name == "asr_002":
                    raise RuntimeError("ASR失敗")
                if profile == "qwen-comparison":
                    self.assertEqual(command[2:9], ["qwen3-asr-1.7b", "--language", "ja",
                                                     "--device", "cpu", "--format", "json"])
                    return "\n".join(json.dumps({"file": path, "stop": "complete", "text": "パンカパンパカポず"},
                                                ensure_ascii=False) for path in command[9:])
                if comparison:
                    self.assertEqual(command[2:6], ["nemotron-3.5-transcribe", "--speakers", "--format", "json"])
                    return "\n".join(json.dumps({"file": path, **result(text="パンカパンパカポず")}, ensure_ascii=False)
                                     for path in command[6:])
                else:
                    self.assertIn("--language", command)
                    self.assertEqual(command[command.index("--language") + 1], "ja")
                    self.assertIn("--vad", command)
                    self.assertIn("--diarize", command)
                return json.dumps(result(text=name), ensure_ascii=False)
            return ""

        with patch.object(MODULE, "resolve_speech", return_value="speech"), \
                patch.object(MODULE.shutil, "which", return_value="ffmpeg"), \
                patch("update_shizuku_logs.resolve_ytdlp", return_value=["yt-dlp"]), \
                patch.object(MODULE, "run_logged", side_effect=fake_run), \
                contextlib.redirect_stdout(io.StringIO()):
            if fail_second:
                with self.assertRaises(RuntimeError):
                    MODULE.transcribe_video(video, VIDEO_ID, staging_parent=staging)
            else:
                MODULE.transcribe_video(video, VIDEO_ID, staging_parent=staging, profile=profile, device=device)
        self.assertTrue(untouched.is_dir())
        self.assertEqual((video / f"{VIDEO_ID}.info.txt").read_text(encoding="utf-8"), "既存情報")
        self.assertEqual((video / f"{VIDEO_ID}.live_chat.txt").read_text(encoding="utf-8"), "既存チャット")
        return video, staging, untouched

    def test_success_installs_only_final_text_and_cleans_own_workdir(self):
        with tempfile.TemporaryDirectory() as tmp:
            video, staging, untouched = self._workflow(Path(tmp))
            self.assertEqual(list(staging.iterdir()), [untouched])
            output = video / f"{VIDEO_ID}.transcribe.txt"
            text = output.read_text(encoding="utf-8")
            self.assertIn("AI生成・未確認", text)
            self.assertIn("00:55:01.250", text)
            self.assertLess(text.index("asr_001"), text.index("asr_002"))
            self.assertNotIn(str(Path(tmp)), text)
            self.assertEqual(len(list(video.iterdir())), 3)

    def test_partial_failure_retains_work_and_does_not_install_transcript(self):
        with tempfile.TemporaryDirectory() as tmp:
            video, staging, _ = self._workflow(Path(tmp), fail_second=True)
            self.assertFalse((video / f"{VIDEO_ID}.transcribe.txt").exists())
            self.assertEqual(len(list(staging.iterdir())), 2)
            self.assertEqual(len(list(staging.rglob("*.wav"))), 3)

    def test_nemotron_comparison_adds_its_own_file_and_skips_it_on_rerun(self):
        with tempfile.TemporaryDirectory() as tmp:
            video, staging, untouched = self._workflow(Path(tmp), profile="nemotron-comparison")
            self.assertEqual(list(staging.iterdir()), [untouched])
            for suffix in (".ja.srt", ".transcribe.txt"):
                self.assertEqual((video / (VIDEO_ID + suffix)).read_text(encoding="utf-8"), "既存の字幕")
            comparison = video / f"{VIDEO_ID}.nemotron-3.5-transcribe.txt"
            text = comparison.read_text(encoding="utf-8")
            self.assertIn("[00:55:01.250 --> 00:55:03.000] 区間056/話者0: パンカパンパカポず", text)
            with patch.object(MODULE, "resolve_speech") as speech, contextlib.redirect_stdout(io.StringIO()):
                self.assertIsNone(MODULE.transcribe_video(video, VIDEO_ID, profile="nemotron-comparison"))
                speech.assert_not_called()

    def test_all_comparisons_continue_after_failure_and_report_ids(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            other_id = "hewYVVuoPyQ"
            for folder, video_id in (("one", VIDEO_ID), ("two", other_id)):
                directory = root / "logs" / "youtube" / "2026" / folder
                directory.mkdir(parents=True)
                (directory / f"{video_id}.info.txt").touch()
            with patch.object(MODULE, "REPO_ROOT", root), \
                    patch.object(MODULE.sys, "argv", ["transcribe_youtube.py", "--all", "--profile", "nemotron-comparison"]), \
                    patch.object(MODULE, "transcribe_video", side_effect=[RuntimeError("取得失敗"), Path("saved")]) as transcribe, \
                    contextlib.redirect_stdout(io.StringIO()) as stdout, \
                    contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(MODULE.main(), 1)
            self.assertEqual([call.args[1] for call in transcribe.call_args_list], [VIDEO_ID, other_id])
            self.assertIn("保存 1 / 保存済み 0 / 失敗 1", stdout.getvalue())
            self.assertIn(f"失敗した動画ID: {VIDEO_ID}", stdout.getvalue())

    def test_qwen_comparison_keeps_nemotron_and_records_input_ranges(self):
        with tempfile.TemporaryDirectory() as tmp:
            video, staging, untouched = self._workflow(Path(tmp), profile="qwen-comparison", device="cpu")
            self.assertEqual(list(staging.iterdir()), [untouched])
            self.assertEqual((video / f"{VIDEO_ID}.nemotron-3.5-transcribe.txt").read_text(encoding="utf-8"), "Nemotron原文")
            text = (video / f"{VIDEO_ID}.qwen3-asr-1.7b.txt").read_text(encoding="utf-8")
            self.assertIn("## 区間056 [00:55:00.000 --> 00:56:00.000]\n[時刻・話者は未取得]\nパンカパンパカポず", text)

    def test_existing_subtitles_and_transcript_skip_all_external_commands(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for suffix in (".ja.srt", ".transcribe.txt", ".sbv.txt"):
                path = root / (VIDEO_ID + suffix)
                path.write_text("既存", encoding="utf-8")
                with patch.object(MODULE, "resolve_speech") as resolve, contextlib.redirect_stdout(io.StringIO()):
                    self.assertIsNone(MODULE.transcribe_video(root, VIDEO_ID))
                    resolve.assert_not_called()
                self.assertEqual(path.read_text(encoding="utf-8"), "既存")
                path.unlink()

    def test_downloader_automatically_transcribes_only_when_absence_is_confirmed(self):
        for code, skip, should_call in ((0, False, True), (1, False, False), (0, True, False)):
            with self.subTest(code=code, skip=skip), tempfile.TemporaryDirectory() as tmp:
                args = DOWNLOADER.build_parser().parse_args(["--no-comments", "--no-chat"])
                args.no_transcribe = skip
                metadata = {"id": VIDEO_ID, "title": "テスト", "upload_date": "20260913"}
                with patch.object(DOWNLOADER, "fetch_metadata", return_value=metadata), \
                        patch.object(DOWNLOADER, "run_cmd", return_value=subprocess.CompletedProcess([], code)), \
                        patch.object(MODULE, "transcribe_video") as transcribe, contextlib.redirect_stdout(io.StringIO()):
                    if code and not skip:
                        with self.assertRaises(RuntimeError):
                            DOWNLOADER.process_video("https://example.com", Path(tmp), args, None)
                    else:
                        self.assertTrue(DOWNLOADER.process_video("https://example.com", Path(tmp), args, None))
                    self.assertEqual(transcribe.called, should_call)

    def test_empty_existing_transcript_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output = root / f"{VIDEO_ID}.transcribe.txt"
            output.touch()
            with patch.object(MODULE, "resolve_speech") as resolve, self.assertRaises(FileExistsError):
                MODULE.transcribe_video(root, VIDEO_ID)
            resolve.assert_not_called()
            self.assertEqual(output.read_bytes(), b"")

    def test_model_limit_retries_smaller_chunks_with_original_offsets(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            audio = root / "audio.wav"
            write_wave(audio, 600)
            outputs = [MODULE.ModelLimitError("limit"), json.dumps(result()), json.dumps(result())]
            with patch.object(MODULE, "run_logged", side_effect=outputs) as run, contextlib.redirect_stdout(io.StringIO()):
                parts = MODULE.recognize_part("speech", "model", audio, 3300, 3900, root, "asr_001")
            self.assertEqual([(a, b) for _, a, b in parts], [(3300, 3600), (3600, 3900)])
            self.assertEqual(run.call_count, 3)

    def test_other_errors_are_not_retried_as_model_limit(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            audio = root / "audio.wav"
            write_wave(audio, 600)
            with patch.object(MODULE, "run_logged", side_effect=RuntimeError("failure")) as run:
                with self.assertRaises(RuntimeError):
                    MODULE.recognize_part("speech", "model", audio, 0, 600, root, "asr_001")
                self.assertEqual(run.call_count, 1)
            self.assertFalse((root / "asr_001_retry").exists())

    def test_resume_reuses_audio_and_cleans_only_verified_workdir(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            video = root / "video"
            video.mkdir()
            staging = root / "staging"
            run_dir = staging / f"run_{VIDEO_ID}_resume"
            run_dir.mkdir(parents=True)
            request = {"video_id": VIDEO_ID, "url": f"https://www.youtube.com/watch?v={VIDEO_ID}"}
            (run_dir / "request.json").write_text(json.dumps(request), encoding="utf-8")
            write_wave(run_dir / "audio.wav", 160000, rate=16000)
            with patch.object(MODULE, "resolve_speech", return_value="speech"), \
                    patch.object(MODULE.shutil, "which", return_value="ffmpeg"), \
                    patch("update_shizuku_logs.resolve_ytdlp", return_value=["yt-dlp"]), \
                    patch.object(MODULE, "run_logged", return_value=json.dumps(result())) as run, \
                    contextlib.redirect_stdout(io.StringIO()):
                MODULE.transcribe_video(video, VIDEO_ID, staging_parent=staging, resume_workdir=run_dir)
                self.assertEqual(run.call_count, 1)
                self.assertEqual(run.call_args.args[2], "asr_001")
            self.assertFalse(run_dir.exists())
            self.assertTrue((video / f"{VIDEO_ID}.transcribe.txt").is_file())

    def test_diarized_regions_keep_speaker_ambiguity_and_global_times(self):
        data = {"stop": "complete", "text": "日本語の本文", "regions": [
            {"start": 1, "end": 3, "text": "日本語の本文", "speakers": [
                {"speaker": 0, "start": 1, "end": 2}, {"speaker": 1, "start": 2, "end": 3}]}]}
        normalized = MODULE.normalize_regions(data)
        self.assertIsNone(normalized["segments"][0]["speaker"])
        text = MODULE.render_part(normalized, 2, 3300, 3600)
        self.assertIn("00:55:01.000 --> 00:55:03.000", text)
        self.assertIn("話者0・1（本文の話者対応は未確認）", text)
        self.assertIn("日本語の本文", text)

    def test_vad_empty_result_is_explicit_and_not_invented_speech(self):
        data = MODULE.normalize_regions({"stop": "complete", "text": "", "regions": []})
        text = MODULE.render_part(data, 1, 0, 10)
        self.assertIn("発話区間検出で認識対象なし・要確認", text)
        with self.assertRaises(ValueError):
            MODULE.render_part({"stop": "complete", "text": ""}, 1, 0, 10)

    def test_replacement_preserves_old_transcript_until_all_recognition_succeeds(self):
        for success in (False, True):
            with self.subTest(success=success), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                video = root / "video"
                video.mkdir()
                output = video / f"{VIDEO_ID}.transcribe.txt"
                output.write_text("old result", encoding="utf-8")
                staging = root / "staging"
                run_dir = staging / f"run_{VIDEO_ID}_replace"
                run_dir.mkdir(parents=True)
                (run_dir / "request.json").write_text(json.dumps({"video_id": VIDEO_ID,
                    "url": f"https://www.youtube.com/watch?v={VIDEO_ID}"}), encoding="utf-8")
                write_wave(run_dir / "audio.wav", 160000, rate=16000)

                def recognize(*args):
                    self.assertEqual(output.read_text(encoding="utf-8"), "old result")
                    if not success:
                        raise RuntimeError("ASR failed")
                    return json.dumps(result())

                with patch.object(MODULE, "resolve_speech", return_value="speech"), \
                        patch.object(MODULE.shutil, "which", return_value="ffmpeg"), \
                        patch("update_shizuku_logs.resolve_ytdlp", return_value=["yt-dlp"]), \
                        patch.object(MODULE, "run_logged", side_effect=recognize), \
                        contextlib.redirect_stdout(io.StringIO()):
                    if success:
                        MODULE.transcribe_video(video, VIDEO_ID, staging_parent=staging,
                                                resume_workdir=run_dir, replace_transcript=True)
                        self.assertIn("再生成", output.read_text(encoding="utf-8"))
                        self.assertFalse(run_dir.exists())
                    else:
                        with self.assertRaises(RuntimeError):
                            MODULE.transcribe_video(video, VIDEO_ID, staging_parent=staging,
                                                    resume_workdir=run_dir, replace_transcript=True)
                        self.assertEqual(output.read_text(encoding="utf-8"), "old result")
                        self.assertEqual((run_dir / "previous.transcribe.txt").read_text(encoding="utf-8"), "old result")


if __name__ == "__main__":
    unittest.main()
