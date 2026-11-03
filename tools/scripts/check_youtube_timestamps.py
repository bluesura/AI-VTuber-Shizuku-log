#!/usr/bin/env python3
"""既存のタイムスタンプを確認し、未収録なら公開コメントを再取得する。

既定: ローカルにタイムスタンプがあれば取得も生成も不要。
なければ通常コメントだけを再取得・匿名化して保存し、再判定する。
--refresh は既存タイムスタンプの有無にかかわらず再取得する。
このツールはタイムスタンプ本文の生成・YouTubeへの投稿は行わない。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import tempfile
import unicodedata
from pathlib import Path
from types import SimpleNamespace

import download_youtube_subtitles as archive


ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")
TIME_RE = re.compile(r"(?<![\d:])(?:\d{1,3}:[0-5]\d:[0-5]\d|\d{1,3}:[0-5]\d)(?![\d:])")
AUTHOR_RE = re.compile(r"^\s*(?:[└├│─↳>]+\s*)?\[\d{4}-\d{2}-\d{2}\s[^\]]+\]")
META_RE = re.compile(r"^#\s*(?:コメント一覧|動画\s*:|URL\s*:|件数\s*:)")


def timestamp_markers(text: str, video_id: str) -> int:
    """投稿日時・ヘッダーは除外。本文の1時刻だけでも既存ありとする。"""
    body = "\n".join(line for line in text.splitlines()
                     if not AUTHOR_RE.match(line) and not META_RE.match(line))
    body = unicodedata.normalize("NFKC", body)
    count = len(TIME_RE.findall(body))
    for url in re.findall(r"https?://[^\s<>]+", body):
        if (f"watch?v={video_id}" in url or f"youtu.be/{video_id}" in url) and re.search(
                r"[?&](?:t|start)=\d", url):
            count += 1
    return count


def find_video(repo: Path, video_id: str) -> tuple[Path, str]:
    if not ID_RE.fullmatch(video_id):
        raise ValueError("11文字の動画IDを指定してください。")
    matches = list((repo / "logs/youtube").glob(f"*/*/{video_id}.info.txt"))
    if len(matches) != 1:
        raise ValueError(f"動画情報が一意に見つかりません: {video_id}")
    info = matches[0]
    text = info.read_text(encoding="utf-8-sig")
    stored_id = re.search(r"^動画ID\s*:\s*(\S+)\s*$", text, re.M)
    title = re.search(r"^タイトル\s*:\s*(.+)$", text, re.M)
    if not stored_id or stored_id[1] != video_id or not title:
        raise ValueError("動画情報のIDまたはタイトルを確認できません。")
    return info.with_name(f"{video_id}.comments.txt"), title[1].strip()


def fetch_comments(video_id: str) -> dict:
    # 生の著者名を含むJSONはメモリ内だけで扱い、ファイルへ出力しない。
    from yt_dlp import YoutubeDL

    class Logger:
        def __init__(self):
            self.problems = []

        def debug(self, message):
            pass

        def warning(self, message):
            if re.search(r"comment|incomplete|HTTP Error 429", message, re.I):
                self.problems.append(message)

        def error(self, message):
            self.problems.append(message)

    logger = Logger()
    with YoutubeDL({"skip_download": True, "getcomments": True, "noplaylist": True,
                    "quiet": True, "logger": logger,
                    "extractor_args": {"youtube": {"comment_sort": ["new"]}}}) as ydl:
        info = ydl.extract_info(f"https://www.youtube.com/watch?v={video_id}", download=False)
        ydl.post_extract(info)
    if logger.problems:
        raise RuntimeError("コメント取得に警告・エラーがあり、完全な取得を確認できません。旧ファイルは保持します。")
    if not info or info.get("id") != video_id or not isinstance(info.get("comments"), list):
        raise RuntimeError("公開コメントの取得結果を確認できません。旧ファイルは保持します。")
    return info


def check_video(repo: Path, video_id: str, *, refresh=False, check_only=False,
                fetcher=fetch_comments) -> dict:
    target, title = find_video(repo, video_id)
    before = target.read_bytes() if target.exists() else None
    old_text = before.decode("utf-8-sig") if before is not None else ""
    old_markers = timestamp_markers(old_text, video_id)
    result = {"video_id": video_id, "comments_file": target.relative_to(repo).as_posix(),
              "local_timestamp_markers": old_markers, "comments_refreshed": False}
    if old_markers and not refresh:
        return {**result, "status": "existing_local", "generate": False}
    if check_only:
        return {**result, "status": "refresh_required", "generate": False}

    info = fetcher(video_id)
    comments = info.get("comments")
    if info.get("id") != video_id or not isinstance(comments, list):
        raise RuntimeError("取得結果が対象動画のコメントではありません。")
    if not comments and re.search(r"^# 件数:\s*[1-9]\d*", old_text, re.M):
        raise RuntimeError("再取得が0件のため、既存のコメントを空にせず保持します。")
    workroot = (repo / "outputs/youtube-timestamps/comment-refresh").resolve()
    workroot.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=f"{video_id}_", dir=workroot) as tmp:
        work = Path(tmp).resolve()
        work.relative_to(workroot)  # 後片付けの対象が専用作業領域内であることを確認。
        staged = work / target.name
        anon = archive.Anonymizer(whitelist=archive.load_whitelist(
            SimpleNamespace(whitelist_file=None, whitelist=None)))
        archive.write_comments(comments, staged, title,
                               f"https://www.youtube.com/watch?v={video_id}", anon)
        new_bytes = staged.read_bytes()
        new_markers = timestamp_markers(new_bytes.decode("utf-8"), video_id)
        current = target.read_bytes() if target.exists() else None
        if current != before:
            raise RuntimeError("取得中にコメントファイルが変更されました。上書きを停止します。")
        if before is not None:
            backup = workroot / f"{video_id}.{hashlib.sha256(before).hexdigest()[:16]}.before.txt"
            if backup.exists():
                if backup.read_bytes() != before:
                    raise RuntimeError("退避先の内容が一致しません。")
            else:
                backup.write_bytes(before)
        if new_bytes != before:
            staged.replace(target)
        result.update({"comments_refreshed": True, "comments_count": len(comments),
                       "reported_comments_count": info.get("comment_count"),
                       "timestamp_markers": new_markers, "file_changed": new_bytes != before,
                       "sha256": hashlib.sha256(new_bytes).hexdigest(),
                       "status": "existing_after_refresh" if new_markers else "needs_generation",
                       "generate": not bool(new_markers)})
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("video_ids", nargs="+")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--refresh", action="store_true", help="既存タイムスタンプがあっても再取得")
    group.add_argument("--check-only", action="store_true", help="ローカルだけ確認し、変更しない")
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[2]
    failed = False
    for video_id in dict.fromkeys(args.video_ids):
        try:
            result = check_video(repo, video_id, refresh=args.refresh, check_only=args.check_only)
        except Exception as exc:
            failed = True
            result = {"video_id": video_id, "status": "refresh_failed", "generate": False,
                      "error": str(exc)}
        print(json.dumps(result, ensure_ascii=False), flush=True)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
