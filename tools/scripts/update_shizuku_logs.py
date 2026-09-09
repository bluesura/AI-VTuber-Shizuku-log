#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""しずくのYouTube配信一覧とローカルログを動画IDで比較し、未収録分を取得する。

既定は比較結果を表示するだけ。``--apply`` を付けると、未収録URLを
``dys.cmd --auto`` に渡し、取得結果を ``logs/youtube/<年>/<日付_タイトル>/``
へ配置する。
"""

from __future__ import annotations

import argparse
import filecmp
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


CHANNEL_URL = "https://www.youtube.com/@AIVtuber_Shizuku/streams"
VIDEO_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")
FILE_VIDEO_ID_RE = re.compile(r"^([A-Za-z0-9_-]{11})(?:\.|$)")
INFO_VIDEO_ID_RE = re.compile(r"^動画ID\s*:\s*([A-Za-z0-9_-]{11})\s*$", re.MULTILINE)
DATE_DIR_RE = re.compile(r"^(\d{4})-\d{2}-\d{2}_")


@dataclass(frozen=True)
class Stream:
    video_id: str
    title: str
    url: str
    duration: float | None = None


def default_repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def resolve_ytdlp() -> list[str]:
    """PATHのyt-dlpを使い、なければ現在のPythonモジュールへフォールバックする。"""
    executable = shutil.which("yt-dlp")
    if executable:
        return [executable]

    probe = subprocess.run(
        [sys.executable, "-m", "yt_dlp", "--version"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if probe.returncode == 0:
        return [sys.executable, "-m", "yt_dlp"]
    raise RuntimeError("yt-dlp が見つかりません。`pip install -U yt-dlp` が必要です。")


def collect_local_video_ids(library_root: Path) -> set[str]:
    """既存ログのファイル名とinfo本文から動画IDを収集する。"""
    ids: set[str] = set()
    if not library_root.exists():
        return ids

    for path in library_root.rglob("*"):
        if not path.is_file():
            continue
        match = FILE_VIDEO_ID_RE.match(path.name)
        if match:
            ids.add(match.group(1))

        if path.name.endswith(".info.txt"):
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            info_match = INFO_VIDEO_ID_RE.search(text)
            if info_match:
                ids.add(info_match.group(1))
    return ids


def parse_completed_streams(payload: dict[str, Any]) -> list[Stream]:
    """yt-dlpのチャンネルJSONから、終了済みと判断できる配信だけを返す。"""
    streams: list[Stream] = []
    seen: set[str] = set()

    entries = payload.get("entries")
    if not isinstance(entries, list):
        raise ValueError("YouTube配信一覧に entries がありません。")

    for entry in entries:
        if not isinstance(entry, dict):
            continue
        video_id = str(entry.get("id") or "").strip()
        if not VIDEO_ID_RE.fullmatch(video_id) or video_id in seen:
            continue

        live_status = str(entry.get("live_status") or "").lower()
        if live_status in {"is_live", "is_upcoming", "post_live"}:
            continue

        duration_value = entry.get("duration")
        try:
            duration = float(duration_value) if duration_value is not None else None
        except (TypeError, ValueError):
            duration = None

        # streamsタブのflat JSONは通常live_statusを持たない。終了済み配信は
        # durationを持つため、状態も再生時間も不明な項目（配信中・予約枠）は除外する。
        if not live_status and (duration is None or duration <= 0):
            continue

        url = str(entry.get("webpage_url") or entry.get("url") or "").strip()
        if not url.startswith(("https://", "http://")):
            url = f"https://www.youtube.com/watch?v={video_id}"

        streams.append(
            Stream(
                video_id=video_id,
                title=str(entry.get("title") or "（タイトル不明）"),
                url=url,
                duration=duration,
            )
        )
        seen.add(video_id)
    return streams


def fetch_streams(channel_url: str, playlist_end: int | None = None) -> list[Stream]:
    command = resolve_ytdlp() + [
        "--flat-playlist",
        "--dump-single-json",
        "--no-warnings",
    ]
    if playlist_end is not None:
        command += ["--playlist-end", str(playlist_end)]
    command.append(channel_url)

    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=180,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "不明なエラー").strip()
        raise RuntimeError(f"YouTube配信一覧を取得できませんでした:\n{detail}")
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"yt-dlpのJSONを解析できませんでした: {exc}") from exc
    return parse_completed_streams(payload)


def missing_streams(remote: Iterable[Stream], local_ids: set[str]) -> list[Stream]:
    return [stream for stream in remote if stream.video_id not in local_ids]


def _merge_directory(source: Path, destination: Path) -> None:
    """既存ファイルを上書きせず、sourceをdestinationへマージする。"""
    destination.mkdir(parents=True, exist_ok=True)
    for item in source.iterdir():
        target = destination / item.name
        if item.is_dir():
            _merge_directory(item, target)
            if not any(item.iterdir()):
                item.rmdir()
            continue

        if target.exists():
            if target.is_file() and filecmp.cmp(item, target, shallow=False):
                item.unlink()
                continue
            raise FileExistsError(f"既存ファイルと内容が異なるため上書きしません: {target}")
        shutil.move(str(item), str(target))

    if not any(source.iterdir()):
        source.rmdir()


def install_session(session_dir: Path, library_root: Path) -> set[str]:
    """dys.cmdのセッション出力を年別アーカイブへ安全に移す。"""
    library_root = library_root.resolve()
    library_root.mkdir(parents=True, exist_ok=True)
    installed: set[str] = set()

    for source_dir in sorted(path for path in session_dir.iterdir() if path.is_dir()):
        date_match = DATE_DIR_RE.match(source_dir.name)
        if not date_match:
            raise ValueError(f"日付形式を判定できない出力フォルダです: {source_dir.name}")

        year = date_match.group(1)
        destination = (library_root / year / source_dir.name).resolve()
        try:
            destination.relative_to(library_root)
        except ValueError as exc:
            raise RuntimeError(f"保存先がlogs/youtube外になりました: {destination}") from exc

        for info_file in source_dir.glob("*.info.txt"):
            match = FILE_VIDEO_ID_RE.match(info_file.name)
            if match:
                installed.add(match.group(1))

        _merge_directory(source_dir, destination)
    return installed


def _safe_remove_staging(run_dir: Path, staging_parent: Path) -> None:
    resolved_run = run_dir.resolve()
    resolved_parent = staging_parent.resolve()
    try:
        resolved_run.relative_to(resolved_parent)
    except ValueError as exc:
        raise RuntimeError(f"一時フォルダが想定範囲外です: {resolved_run}") from exc
    shutil.rmtree(resolved_run)


def apply_update(
    streams: list[Stream],
    dys_path: Path,
    library_root: Path,
    staging_parent: Path,
    keep_staging: bool = False,
) -> int:
    if os.name != "nt":
        raise RuntimeError("dys.cmdの自動実行はWindows環境でのみ利用できます。")
    if not dys_path.is_file():
        raise FileNotFoundError(f"dys.cmd が見つかりません: {dys_path}")

    staging_parent.mkdir(parents=True, exist_ok=True)
    run_dir = Path(tempfile.mkdtemp(prefix="run_", dir=staging_parent))
    url_file = run_dir / "missing_urls.txt"
    url_file.write_text("\n".join(stream.url for stream in streams) + "\n", encoding="utf-8")

    print(f"\n[dys.cmd] {len(streams)}件を取得します。")
    result = subprocess.run(
        ["cmd.exe", "/d", "/c", str(dys_path), "--auto", str(url_file), str(run_dir)]
    )

    installed: set[str] = set()
    for session_dir in sorted(run_dir.glob("downloads_*")):
        if session_dir.is_dir():
            installed.update(install_session(session_dir, library_root))

    expected = {stream.video_id for stream in streams}
    not_installed = expected - installed
    if not_installed:
        print("\n[Warning] 保存を確認できなかった動画ID:")
        for video_id in sorted(not_installed):
            print(f"  - {video_id}")

    if result.returncode != 0 or not_installed:
        print(f"[Warning] 再確認用に一時出力を保持します: {run_dir}")
        return result.returncode or 1

    if keep_staging:
        print(f"[Info] 一時出力を保持しました: {run_dir}")
    else:
        _safe_remove_staging(run_dir, staging_parent)
    return 0


def build_parser() -> argparse.ArgumentParser:
    repo_root = default_repo_root()
    parser = argparse.ArgumentParser(
        description="しずくのYouTube配信一覧とlogs/youtubeを比較し、未収録ログを取得します。"
    )
    parser.add_argument("--apply", action="store_true", help="未収録分をdys.cmdで取得して保存する")
    parser.add_argument("--channel-url", default=CHANNEL_URL, help="比較するYouTubeのstreams URL")
    parser.add_argument(
        "--library-root",
        type=Path,
        default=repo_root / "logs" / "youtube",
        help="ログ保存先（既定: リポジトリのlogs/youtube）",
    )
    parser.add_argument(
        "--dys",
        type=Path,
        default=Path(__file__).resolve().with_name("dys.cmd"),
        help="実行するdys.cmd",
    )
    parser.add_argument(
        "--playlist-end",
        type=int,
        help="確認する最新配信数。省略時はstreamsタブ全件",
    )
    parser.add_argument(
        "--keep-staging",
        action="store_true",
        help="成功時もoutputs内の一時出力を残す",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    library_root = args.library_root.resolve()
    repo_root = default_repo_root()

    print(f"YouTube : {args.channel_url}")
    print(f"ローカル: {library_root}")
    remote = fetch_streams(args.channel_url, args.playlist_end)
    local_ids = collect_local_video_ids(library_root)
    missing = missing_streams(remote, local_ids)

    print(f"\n終了済み配信: {len(remote)}件")
    print(f"ローカル動画ID: {len(local_ids)}件")
    print(f"未収録: {len(missing)}件")
    for stream in missing:
        print(f"  - {stream.video_id}  {stream.title}")
        print(f"    {stream.url}")

    if not missing:
        print("\n更新はありません。")
        return 0
    if not args.apply:
        print("\n確認のみです。保存するには --apply を付けて再実行してください。")
        return 0

    staging_parent = repo_root / "outputs" / "shizuku-log-update"
    return apply_update(
        missing,
        args.dys.resolve(),
        library_root,
        staging_parent,
        keep_staging=args.keep_staging,
    )


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, RuntimeError, ValueError) as error:
        print(f"[Error] {error}", file=sys.stderr)
        raise SystemExit(1)
