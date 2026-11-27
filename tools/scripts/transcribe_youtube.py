#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""YouTubeログの字幕補完・比較用の文字起こし（標準ライブラリのみ）。

既存ログへの実行: python tools/scripts/transcribe_youtube.py <動画ID>
手順: tools/workflows/字幕なし配信の文字起こし.md
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
import wave
from datetime import datetime, timedelta, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
NEMOTRON_PROFILE = ("nemotron-3.5-transcribe", ("--speakers",))
PROFILES = {
    "japanese": ("qwen3-asr-1.7b", ("--language", "ja", "--vad", "silero-vad",
                                       "--diarize", "nemotron-3-diarization")),
    "nemotron": NEMOTRON_PROFILE,
    "nemotron-comparison": NEMOTRON_PROFILE,
    "qwen-comparison": ("qwen3-asr-1.7b", ("--language", "ja")),
}
COMPARISON_SUFFIXES = {
    "nemotron-comparison": ".nemotron-3.5-transcribe.txt",
    "qwen-comparison": ".qwen3-asr-1.7b.txt",
}
VIDEO_ID_RE = re.compile(r"[A-Za-z0-9_-]{11}")
SUBTITLE_SUFFIXES = (".srt", ".vtt", ".sbv", ".sbv.txt", ".transcribe.txt")


class ModelLimitError(RuntimeError):
    """Speechcppが認識の出力上限に到達した。"""


def has_subtitles(video_dir: Path, video_id: str, *, include_transcript: bool = True) -> bool:
    return any(
        path.is_file() and path.stat().st_size > 0
        and path.name.startswith(video_id + ".")
        and path.name.endswith(SUBTITLE_SUFFIXES)
        and (include_transcript or not path.name.endswith(".transcribe.txt"))
        for path in video_dir.iterdir()
    )


def resolve_speech(explicit: str | None = None) -> str:
    configured = explicit or os.environ.get("SPEECH_EXE")
    if configured:
        found = shutil.which(configured)
        if found:
            return found
        raise RuntimeError("指定されたspeech実行ファイルが見つかりません。")
    found = shutil.which("speech")
    if found:
        return found
    # Windowsの公式インストーラーの配置先。ユーザー固有パスは保存しない。
    local = os.environ.get("LOCALAPPDATA")
    if local:
        candidate = Path(local) / "Programs" / "speech.cpp" / "current" / "speech.exe"
        if candidate.is_file():
            return str(candidate)
    raise RuntimeError("speech.cppが見つかりません。PATHまたはSPEECH_EXEを設定してください。")


def run_logged(command: list[str], run_dir: Path, name: str) -> str:
    """stdout/stderrは非公開の作業フォルダへ保存し、失敗を成功扱いしない。"""
    print(f"  ▶ {name}", flush=True)
    with (run_dir / f"{name}.stdout.txt").open("w", encoding="utf-8") as out, \
            (run_dir / f"{name}.stderr.txt").open("w", encoding="utf-8") as err:
        result = subprocess.run(command, stdout=out, stderr=err)
    if result.returncode == 3 and name.startswith("asr_"):
        raise ModelLimitError(f"{name}がモデルの出力上限に達しました。")
    if result.returncode != 0:
        raise RuntimeError(f"{name}に失敗しました（終了コード {result.returncode}）。作業ログを確認してください。")
    return (run_dir / f"{name}.stdout.txt").read_text(encoding="utf-8-sig")


def split_audio(audio: Path, run_dir: Path, chunk_minutes: float = 55,
                *, force: bool = False, split_at_hour: bool = False) -> list[tuple[Path, float, float]]:
    """1時間超なら短いWAVに分割する。比較用はちょうど1時間の場合も分割する。"""
    if not (0 < chunk_minutes < 60 if force else 1 <= chunk_minutes < 60):
        raise ValueError("分割時間は1〜59分で指定してください。")
    with wave.open(str(audio), "rb") as source:
        rate = source.getframerate()
        frames = source.getnframes()
        if frames == 0:
            raise ValueError("音声が空です。")
        duration = frames / rate
        if not force and (duration < 3600 or (duration == 3600 and not split_at_hour)):
            return [(audio, 0.0, duration)]
        step = max(1, round(chunk_minutes * 60 * rate))
        chunks = []
        for index, start in enumerate(range(0, frames, step), 1):
            end = min(start + step, frames)
            path = run_dir / f"part_{index:03d}.wav"
            with wave.open(str(path), "wb") as target:
                target.setparams(source.getparams())
                remaining = end - start
                while remaining:
                    count = min(remaining, rate * 30)
                    data = source.readframes(count)
                    expected = count * source.getnchannels() * source.getsampwidth()
                    if len(data) != expected:
                        raise ValueError("音声ファイルが途中で途切れています。")
                    target.writeframesraw(data)
                    remaining -= count
            chunks.append((path, start / rate, end / rate))
    return chunks


def normalize_regions(result: dict) -> dict:
    """VAD・話者分離の区間を共通形式へ変換する。複数話者の本文割当は推定しない。"""
    if "regions" not in result:
        return result
    regions = result["regions"]
    if not isinstance(regions, list):
        raise ValueError("発話区間の形式が不正です。")
    segments = []
    for region in regions:
        if not isinstance(region, dict) or not isinstance(region.get("text"), str):
            raise ValueError("発話区間の本文が不正です。")
        speakers = region.get("speakers") or []
        if not isinstance(speakers, list):
            raise ValueError("発話区間の話者情報が不正です。")
        candidates = set()
        for speaker in speakers:
            value = speaker.get("speaker") if isinstance(speaker, dict) else None
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError("発話区間の話者番号が不正です。")
            candidates.add(value)
        segments.append({"start": region.get("start"), "end": region.get("end"),
                         "text": region["text"], "speaker_candidates": sorted(candidates),
                         "speaker": next(iter(candidates)) if len(candidates) == 1 else None})
    return {**result, "segments": segments,
            "no_speech_detected": not regions and result.get("text") == ""}


def recognize_part(speech: str, model: str, audio: Path, start: float, end: float,
                   run_dir: Path, name: str, *,
                   options: tuple[str, ...] = ("--speakers",),
                   comparison: bool = False) -> list[tuple[dict, float, float]]:
    """出力上限の場合だけ小分けにして再試行し、不完全な本文は採用しない。"""
    try:
        raw = run_logged([speech, "asr", model, *options, "--format", "json", str(audio)],
                         run_dir, name)
        result = json.loads(raw)
        if not isinstance(result, dict):
            raise ValueError("speech.cppの出力がJSONオブジェクトではありません。")
        if result.get("stop") == "model_limit":
            raise ModelLimitError("モデルの出力上限に達しました。")
        result = normalize_regions(result)
        render_part(result, 1, start, end, allow_empty=comparison)
        return [(result, start, end)]
    except ModelLimitError:
        retry_floor_minutes = 0.25 if comparison else 1
        duration = end - start
        if duration <= retry_floor_minutes * 60:
            raise
        retry_minutes = max(retry_floor_minutes, min(5, duration / 120))
        retry_dir = run_dir / f"{name}_retry"
        retry_dir.mkdir()
        print(f"  [再試行] 出力上限のため {retry_minutes:g} 分以下へ分割します。", flush=True)
        results = []
        for index, (path, a, b) in enumerate(split_audio(audio, retry_dir, retry_minutes, force=True), 1):
            print(f"  再試行 [{timecode(start + a)} --> {timecode(start + b)}]", flush=True)
            results.extend(recognize_part(speech, model, path, start + a, start + b,
                                          retry_dir, f"{name}_{index:03d}", options=options,
                                          comparison=comparison))
        return results


def recognize_comparison_chunk(speech: str, model: str, audio: Path, start: float,
                               run_dir: Path, name: str, options: tuple[str, ...]
                               ) -> list[tuple[dict, float, float]]:
    """全音声を1分単位で認識する。モデルは複数WAVに対して一度だけ読み込む。"""
    window_dir = run_dir / f"{name}_windows"
    window_dir.mkdir()
    windows = split_audio(audio, window_dir, 1, force=True)
    command = [speech, "asr", model, *options, "--format", "json", *(str(path) for path, _, _ in windows)]
    try:
        raw = run_logged(command, run_dir, name)
    except ModelLimitError:
        # CLIは一部の出力が上限に達しても全入力の診断と本文を出力する。
        raw = (run_dir / f"{name}.stdout.txt").read_text(encoding="utf-8-sig")
    results = [json.loads(line) for line in raw.split("\n") if line.strip()]
    if len(results) != len(windows):
        raise ValueError("入力した音声と認識結果の件数が一致しません。")
    recognized = []
    for index, ((path, a, b), result) in enumerate(zip(windows, results), 1):
        source = result.get("file") if isinstance(result, dict) else None
        if not isinstance(source, str) or Path(source) != path:
            raise ValueError("認識結果が入力した音声と一致しません。")
        if result.get("stop") == "model_limit":
            recognized.extend(recognize_part(speech, model, path, start + a, start + b,
                                              run_dir, f"{name}_{index:03d}", options=options,
                                              comparison=True))
        else:
            recognized.append((result, start + a, start + b))
    return recognized


def timecode(seconds: float) -> str:
    millis = round(seconds * 1000)
    hours, rest = divmod(millis, 3_600_000)
    minutes, rest = divmod(rest, 60_000)
    secs, ms = divmod(rest, 1000)
    return f"{hours:02}:{minutes:02}:{secs:02}.{ms:03}"


def render_part(result: dict, index: int, start: float, end: float, *, allow_empty: bool = False) -> str:
    """話者は分割内の番号として残し、時刻は元動画基準に補正する。"""
    if result.get("stop") != "complete":
        raise ValueError(f"区間{index}の文字起こしが完了していません: {result.get('stop')!r}")
    text = result.get("text")
    if text == "" and result.get("no_speech_detected"):
        return (f"\n## 区間{index:03d} [{timecode(start)} --> {timecode(end)}]\n"
                "[発話区間検出で認識対象なし・要確認]\n")
    if text == "" and allow_empty:
        return f"\n## 区間{index:03d} [{timecode(start)} --> {timecode(end)}]\n[認識本文なし・要確認]\n"
    if not isinstance(text, str) or not text.strip():
        raise ValueError(f"区間{index}の文字起こし結果が空です。")
    lines = [f"\n## 区間{index:03d} [{timecode(start)} --> {timecode(end)}]"]
    segments = result.get("segments")
    if not isinstance(segments, list) or not segments:
        lines += ["[時刻・話者は未取得]", text.strip()]
        return "\n".join(lines) + "\n"
    for segment in segments:
        if not isinstance(segment, dict) or not isinstance(segment.get("text"), str):
            raise ValueError(f"区間{index}に不正なセグメントがあります。")
        body = segment["text"].strip()
        if not body:
            continue
        a, b = segment.get("start"), segment.get("end")
        speaker = segment.get("speaker")
        candidates = segment.get("speaker_candidates") or []
        if len(candidates) > 1:
            label = f"区間{index:03d}/話者" + "・".join(str(value) for value in candidates) + "（本文の話者対応は未確認）"
        elif speaker is None or speaker == -1:
            label = "話者不明"
        elif isinstance(speaker, int) and not isinstance(speaker, bool) and speaker >= 0:
            label = f"区間{index:03d}/話者{speaker}"
        else:
            raise ValueError(f"区間{index}の話者番号が不正です。")
        if a is None and b is None:
            stamp = "時刻未取得"
        elif (isinstance(a, (int, float)) and isinstance(b, (int, float))
              and math.isfinite(a) and math.isfinite(b) and 0 <= a <= b <= end - start + 0.1):
            stamp = f"{timecode(start + a)} --> {timecode(start + b)}"
        else:
            raise ValueError(f"区間{index}の時刻が範囲外または不正です。")
        lines.append(f"[{stamp}] {label}: {body}")
    if len(lines) == 1:
        raise ValueError(f"区間{index}に本文のあるセグメントがありません。")
    return "\n".join(lines) + "\n"


def record_cleanup_receipt(run_dir: Path, output: Path, video_id: str) -> None:
    """追加の音声確認が終わった後に再取得可能な素材を選別するための記録。"""
    from file_state import atomic_write

    media = [p.name for p in run_dir.glob("source.*")
             if p.is_file() and p.suffix.lower() in {".mkv", ".mp4", ".webm", ".mov", ".flv", ".3gp"}]
    receipt = {
        "video_id": video_id,
        "output": output.resolve().relative_to(REPO_ROOT.resolve()).as_posix(),
        "sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
        "files": sorted(media + ["audio.wav"]),
    }
    atomic_write(run_dir / "cleanup-receipt.json", json.dumps(receipt, ensure_ascii=False) + "\n")



def remove_workdir(run_dir: Path, staging_parent: Path) -> None:
    root = staging_parent.resolve()
    target = run_dir.resolve()
    # この実行が作った直下のrun_*だけを消す。動画フォルダには触れない。
    if target.parent != root or not target.name.startswith("run_"):
        raise ValueError("削除対象が専用作業フォルダではありません。")
    shutil.rmtree(target)


def transcribe_video(
    video_dir: Path, video_id: str, *, speech_exe: str | None = None,
    model: str | None = None, chunk_minutes: int = 55, staging_parent: Path | None = None,
    resume_workdir: Path | None = None,
    replace_transcript: bool = False, profile: str = "japanese", keep_staging: bool = False,
    device: str | None = None,
) -> Path | None:
    if not VIDEO_ID_RE.fullmatch(video_id):
        raise ValueError("動画IDの形式が不正です。")
    video_dir = video_dir.resolve(strict=True)
    comparison = profile in COMPARISON_SUFFIXES
    if comparison and replace_transcript:
        raise ValueError("比較用の文字起こしでは --replace-transcript を指定できません。")
    suffix = COMPARISON_SUFFIXES.get(profile, ".transcribe.txt")
    output = video_dir / f"{video_id}{suffix}"
    if comparison and output.is_file() and output.stat().st_size > 0:
        print(f"  ⏭ {output.name}: 比較用の文字起こしを保存済み", flush=True)
        return None
    if not comparison and has_subtitles(video_dir, video_id, include_transcript=not replace_transcript):
        print(f"  ⏭ {video_id}: 字幕または文字起こしがあるためスキップ", flush=True)
        return None
    if output.exists() and not replace_transcript:
        raise FileExistsError("空の文字起こしファイルが既にあります。内容を確認してください（上書きしません）。")
    previous_digest = hashlib.sha256(output.read_bytes()).hexdigest() if output.exists() else None
    if not 1 <= chunk_minutes < 60:
        raise ValueError("分割時間は1〜59分で指定してください。")
    if profile not in PROFILES:
        raise ValueError("認識プロファイルが不正です。")
    default_model, options = PROFILES[profile]
    model = model or default_model
    if device:
        options = (*options, "--device", device)
    speech = resolve_speech(speech_exe)
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("ffmpegが見つかりません。PATHを設定してください。")
    # 既存のyt-dlp解決方法を再利用する（import時にはダウンロードしない）。
    from update_shizuku_logs import resolve_ytdlp
    ytdlp = resolve_ytdlp()
    staging_name = f"shizuku-{profile}" if comparison else "shizuku-transcribe"
    staging_parent = (staging_parent or REPO_ROOT / "outputs" / staging_name).resolve()
    staging_parent.mkdir(parents=True, exist_ok=True)
    url = f"https://www.youtube.com/watch?v={video_id}"
    if resume_workdir:
        run_dir = resume_workdir.resolve(strict=True)
        if run_dir.parent != staging_parent or not run_dir.name.startswith(f"run_{video_id}_"):
            raise ValueError("再開対象がこの動画の専用作業フォルダではありません。")
        request = json.loads((run_dir / "request.json").read_text(encoding="utf-8"))
        if request != {"video_id": video_id, "url": url}:
            raise ValueError("再開対象の動画IDまたはURLが一致しません。")
        with wave.open(str(run_dir / "audio.wav"), "rb") as audio_check:
            if (audio_check.getframerate(), audio_check.getnchannels(), audio_check.getsampwidth()) != (16000, 1, 2):
                raise ValueError("再開用の音声が16kHz・モノラル・16bit WAVではありません。")
    else:
        run_dir = Path(tempfile.mkdtemp(prefix=f"run_{video_id}_", dir=staging_parent))
        (run_dir / "request.json").write_text(json.dumps({"video_id": video_id, "url": url}), encoding="utf-8")
    from contextlib import ExitStack
    from file_state import file_lock

    locks = ExitStack()
    if resume_workdir:
        locks.enter_context(file_lock(staging_parent / f".{run_dir.name}.lock"))
    print(f"  作業フォルダ: {run_dir}", flush=True)
    try:
        (run_dir / "cleanup-receipt.json").unlink(missing_ok=True)
        if previous_digest is not None:
            backup = run_dir / "previous.transcribe.txt"
            if backup.exists():
                if hashlib.sha256(backup.read_bytes()).hexdigest() != previous_digest:
                    raise RuntimeError("退避済みの文字起こしと現在のファイルが異なります。変更を確認してください。")
            else:
                backup.write_bytes(output.read_bytes())
        audio = run_dir / "audio.wav"
        if not resume_workdir:
            # 映像は文字起こしに使わないため、ダウンロード容量を480p以下へ抑える。
            run_logged(ytdlp + [
                "--ignore-config", "--no-playlist", "--no-part", "--no-overwrites",
                "--retries", "3", "--socket-timeout", "30", "--ffmpeg-location", ffmpeg,
                "-f", "bv*[height<=480]+ba/b[height<=480]/b", "--merge-output-format", "mkv",
                "-o", str(run_dir / "source.%(ext)s"), url,
            ], run_dir, "download")
            media = [p for p in run_dir.glob("source.*") if p.suffix.lower() in {".mkv", ".mp4", ".webm", ".mov", ".flv", ".3gp"}]
            if len(media) != 1:
                raise RuntimeError("取得した動画ファイルを一意に特定できません。")
            run_logged([ffmpeg, "-nostdin", "-hide_banner", "-loglevel", "error", "-n",
                        "-i", str(media[0]), "-vn", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", str(audio)],
                       run_dir, "audio")
        attempt_dir = Path(tempfile.mkdtemp(prefix="attempt_", dir=run_dir))
        chunks = split_audio(audio, attempt_dir, chunk_minutes, split_at_hour=comparison)
        now = datetime.now(timezone(timedelta(hours=9))).isoformat(timespec="seconds")
        # ローカルパス・CLIの診断文・生JSONは公開成果物に含めない。
        header = (f"# 自動文字起こし [AI生成・未確認]\n# 動画ID: {video_id}\n# URL: {url}\n"
                  f"# 作成日時: {now}\n# エンジン: speech.cpp / モデル: {Path(model).name}\n"
                  f"# 認識設定: {profile} / {' '.join(options)}\n"
                  "# YouTube提供字幕ではありません。誤認識・欠落・幻覚の可能性があります。\n"
                  "# 時刻は元動画基準。話者番号は各区間内のみ有効で、本人の同定ではありません。\n"
                  + ("# 時刻は発話検出区間の境界です。単語単位の時刻ではありません。\n" if profile == "japanese" else "")
                  + ("# 比較用。発話検出による選別をせず、全音声を1分ずつ認識しました。\n"
                     "# 発話時刻を取得できなかった本文には、認識に使った音声範囲を示します。\n" if comparison else "")
                  + ("# 再生成: 旧ASRの表記変換ではなく、音声から再認識しました。\n" if replace_transcript else "")
                  +
                  "# 区切り付近の語や話者は要確認。歌唱の認識精度は未確認です。\n")
        recognized = []
        for index, (path, start, end) in enumerate(chunks, 1):
            print(f"  文字起こし {index}/{len(chunks)} [{timecode(start)} --> {timecode(end)}]", flush=True)
            if comparison:
                recognized.extend(recognize_comparison_chunk(speech, model, path, start, attempt_dir,
                                                             f"asr_{index:03d}", options))
            else:
                recognized.extend(recognize_part(speech, model, path, start, end, attempt_dir,
                                                  f"asr_{index:03d}", options=options))
        combined = header + "".join(render_part(result, index, start, end, allow_empty=comparison)
                                    for index, (result, start, end) in enumerate(recognized, 1))
        # 同じ動画フォルダの一時ファイルを検証後、上書きなしで一括公開する。
        descriptor, tmp_name = tempfile.mkstemp(prefix=f".{video_id}_", suffix=".tmp", dir=video_dir)
        candidate = Path(tmp_name)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as target:
                target.write(combined)
            if candidate.read_text(encoding="utf-8") != combined:
                raise RuntimeError("文字起こしの再読込検証に失敗しました。")
            if replace_transcript and previous_digest is not None:
                if not output.exists() or hashlib.sha256(output.read_bytes()).hexdigest() != previous_digest:
                    raise RuntimeError("処理中に既存の文字起こしが変更されたため、置き換えを中止しました。")
                os.replace(candidate, output)
            elif os.name == "nt":
                # Windowsのrenameは既存ファイルを上書きせず、リンク権限も不要。
                os.rename(candidate, output)
            else:
                os.link(candidate, output)
        finally:
            candidate.unlink(missing_ok=True)
        if output.read_text(encoding="utf-8") != combined:
            raise RuntimeError("保存した文字起こしの再読込検証に失敗しました。")
        if keep_staging:
            try:
                record_cleanup_receipt(run_dir, output, video_id)
            except (OSError, ValueError) as exc:
                print(f"  整理候補の記録を作成できません: {exc}", flush=True)
    except BaseException:
        print(f"  [失敗] 再確認用に中間ファイルを保持しました: {run_dir}", flush=True)
        raise
    finally:
        locks.close()
    if keep_staging:
        print(f"  ✅ 文字起こしを保存し、内容確認用に中間ファイルを保持しました: {output}", flush=True)
    else:
        remove_workdir(run_dir, staging_parent)
        print(f"  ✅ 文字起こしを保存し、中間ファイルを削除しました: {output}", flush=True)
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("video_ids", nargs="*", help="既存ログの動画ID")
    parser.add_argument("--all", action="store_true", help="収録済みの全動画を比較用プロファイルで順に処理")
    parser.add_argument("--speech-exe", help="speech実行ファイル（既定: SPEECH_EXE、PATH、Windows標準配置先）")
    parser.add_argument("--profile", choices=PROFILES, default="japanese",
                        help="japanese: 日本語指定のQwen3-ASR＋発話検出・話者分離 / nemotron: 従来の字幕補完 / nemotron-comparison・qwen-comparison: 既存字幕と併存する比較用ASR")
    parser.add_argument("--model", help="選択プロファイルのASRモデルを名前またはローカルGGUFパスで変更")
    parser.add_argument("--device", help="speech.cppの認識デバイス（cpu、gpuなど。既定は自動選択）")
    parser.add_argument("--chunk-minutes", type=int, default=55, choices=range(1, 60), metavar="1-59")
    parser.add_argument("--resume-workdir", type=Path, help="同じ動画の取得済みWAVがある専用作業フォルダから再開")
    parser.add_argument("--replace-transcript", action="store_true", help="既存ASRを退避し、全区間成功後に再生成結果へ置き換える（YouTube字幕は対象外）")
    parser.add_argument("--keep-staging", action="store_true", help="成功後も内容確認用に専用作業フォルダを保持する")
    args = parser.parse_args()
    if args.all and (args.video_ids or args.profile != "nemotron-comparison"):
        parser.error("--all は動画IDを指定せず、--profile nemotron-comparison と併用してください。")
    if not args.all and not args.video_ids:
        parser.error("動画IDまたは --all を指定してください。")
    if args.resume_workdir and len(args.video_ids) != 1:
        parser.error("--resume-workdirでは動画IDを1件だけ指定してください。")
    if args.profile in COMPARISON_SUFFIXES and args.replace_transcript:
        parser.error("比較用の文字起こしでは --replace-transcript を指定できません。")
    library = REPO_ROOT / "logs" / "youtube"
    infos_by_id: dict[str, list[Path]] = {}
    info_suffix = ".info.txt"
    for info in sorted(library.rglob(f"*{info_suffix}")):
        video_id = info.name[:-len(info_suffix)]
        if VIDEO_ID_RE.fullmatch(video_id):
            infos_by_id.setdefault(video_id, []).append(info)
    video_ids = list(infos_by_id) if args.all else list(dict.fromkeys(args.video_ids))
    if not video_ids:
        parser.error("収録済みの動画情報ファイルが見つかりません。")
    saved = skipped = 0
    failed = []
    for index, video_id in enumerate(video_ids, 1):
        print(f"[{index}/{len(video_ids)}] {video_id}", flush=True)
        try:
            if not VIDEO_ID_RE.fullmatch(video_id):
                raise ValueError("動画IDの形式が不正です。")
            infos = infos_by_id.get(video_id, [])
            if len(infos) != 1:
                raise ValueError("対応する動画情報ファイルが一意に見つかりません。")
            output = transcribe_video(infos[0].parent, video_id, speech_exe=args.speech_exe,
                                      model=args.model, chunk_minutes=args.chunk_minutes,
                                      resume_workdir=args.resume_workdir, replace_transcript=args.replace_transcript,
                                      profile=args.profile, keep_staging=args.keep_staging, device=args.device)
            if output is None:
                skipped += 1
            else:
                saved += 1
        except (OSError, RuntimeError, ValueError, wave.Error) as error:
            print(f"[Error] {video_id}: {error}", file=sys.stderr, flush=True)
            failed.append(video_id)
    if args.all:
        print(f"保存 {saved} / 保存済み {skipped} / 失敗 {len(failed)}", flush=True)
        if failed:
            print(f"失敗した動画ID: {' '.join(failed)}", flush=True)
    return int(bool(failed))


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(main())
