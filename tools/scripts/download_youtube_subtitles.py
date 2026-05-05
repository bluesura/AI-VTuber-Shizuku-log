#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
=============================================================================
YouTube テキストデータダウンローダー (Subtitle / Chat / Comment)

【事前準備】
  pip install yt-dlp

【使い方】
  # URLを直接指定（複数可）
  python download_youtube_subtitles.py <URL1> <URL2> ...

  # URLリストファイルを指定（1行1URL）
  python download_youtube_subtitles.py --file urls.txt

  # 引数なしで起動すると対話モード
  python download_youtube_subtitles.py

【出力フォルダ構成】
  downloads_YYYYMMDD_HHMM/          ← 実行日時の親フォルダ
    YYYY-MM-DD_タイトル_動画ID/      ← 動画ごとのフォルダ
      *.info.txt                     ← 動画情報（投稿日・タイトル・説明）
      *.ja.srt                       ← 字幕（SRT形式）
      *.live_chat.txt                ← ライブチャット（テキスト形式）
      *.comments.txt                 ← 通常コメント
=============================================================================
"""

import subprocess
import sys
import json
import re
from pathlib import Path
from datetime import datetime, timezone

# Windows コンソールが CP932 でも文字化けしないよう UTF-8 に強制
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


# ============================================================
# ユーティリティ
# ============================================================

def sanitize_filename(name: str, max_len: int = 60) -> str:
    """ファイル名に使えない文字を除去し、長すぎる場合は切り詰める"""
    name = re.sub(r'[\\/*?:"<>|]', "_", name).strip()
    return name[:max_len] if len(name) > max_len else name


def run_cmd(cmd: list[str], label: str) -> subprocess.CompletedProcess:
    """コマンドを実行し、結果を表示する"""
    print(f"\n  ▶ {label}")
    result = subprocess.run(
        cmd, capture_output=True, text=True,
        encoding="utf-8", errors="replace",
    )
    if result.returncode != 0:
        # yt-dlp の WARNING は WARN 扱いで続行、ERROR は表示
        stderr = result.stderr.strip()
        level = "WARN" if "WARNING" in stderr and "ERROR" not in stderr else "WARN"
        print(f"  [{level}] {stderr}")
    else:
        print("    ✅ 完了")
    return result


def find_file(folder: Path, base_name: str, suffix: str) -> Path | None:
    """
    日本語ファイル名で Path.exists() が失敗するケースに対応するため
    glob でファイルを探す。suffix 例: ".live_chat.json", ".ja.vtt"
    """
    matches = list(folder.glob(f"{glob_escape(base_name)}{suffix}"))
    return matches[0] if matches else None


def glob_escape(name: str) -> str:
    """glob のメタ文字をエスケープ"""
    return re.sub(r'([\[\]*?])', r'[\1]', name)


def delete_if_exists(path: Path):
    """ファイルが存在すれば削除する"""
    if path.exists():
        path.unlink()
        print(f"    🗑  削除: {path.name}")


# ============================================================
# VTT → SRT 変換（ffmpeg 不要）
# ============================================================

def vtt_to_srt(vtt_path: Path, srt_path: Path) -> bool:
    """
    .vtt ファイルを .srt に変換する（ffmpeg 不要）。
    タイムスタンプの "." を "," に変換し、シーケンス番号を付与。
    """
    text = vtt_path.read_text(encoding="utf-8", errors="replace")

    # WEBVTT ヘッダーと NOTE ブロックを除去
    text = re.sub(r"^WEBVTT.*?\n\n", "", text, flags=re.DOTALL)
    text = re.sub(r"NOTE\s.*?\n\n", "", text, flags=re.DOTALL)

    # タイムスタンプのミリ秒区切りを "." → ","
    text = re.sub(r"(\d{2}:\d{2}:\d{2})\.(\d{3})", r"\1,\2", text)

    blocks = [b.strip() for b in re.split(r"\n{2,}", text) if b.strip()]
    srt_lines = []
    seq = 1
    for block in blocks:
        lines = block.splitlines()
        if not any(" --> " in l for l in lines):
            continue
        # 先頭が既存シーケンス番号なら除去
        if lines and lines[0].strip().isdigit():
            lines = lines[1:]
        srt_lines.append(f"{seq}\n" + "\n".join(lines))
        seq += 1

    if not srt_lines:
        return False

    srt_path.write_text("\n\n".join(srt_lines) + "\n", encoding="utf-8")
    return True


# ============================================================
# ライブチャット JSON → TXT
# ============================================================

def extract_live_chat(json_path: Path, txt_path: Path, video_title: str, url: str):
    """
    .live_chat.json（1行1JSONオブジェクト）から必要項目だけ抽出し
    [再生時間] 著者名: メッセージ 形式のテキストに変換する。
    """
    messages = []

    with json_path.open(encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue

            for action in obj.get("replayChatItemAction", {}).get("actions", []):
                renderer = (
                    action.get("addChatItemAction", {})
                          .get("item", {})
                          .get("liveChatTextMessageRenderer")
                )
                if not renderer:
                    continue  # スーパーチャット・バナー等はスキップ

                timestamp = renderer.get("timestampText", {}).get("simpleText", "??:??")
                author    = renderer.get("authorName",    {}).get("simpleText", "不明")
                runs      = renderer.get("message",       {}).get("runs", [])
                text      = "".join(
                    r.get("text") or r.get("emoji", {}).get("emojiId", "")
                    for r in runs
                ).strip()

                if text:
                    messages.append((timestamp, author, text))

    if not messages:
        print("    [INFO] ライブチャットのメッセージが見つかりませんでした。")
        return

    with txt_path.open("w", encoding="utf-8") as out:
        out.write(f"# ライブチャット一覧\n")
        out.write(f"# 動画: {video_title}\n")
        out.write(f"# URL : {url}\n")
        out.write(f"# 件数: {len(messages)}\n\n")
        for timestamp, author, text in messages:
            out.write(f"[{timestamp}] {author}: {text}\n")

    print(f"    💬 ライブチャット {len(messages)} 件を保存: {txt_path.name}")


# ============================================================
# 動画1本の処理
# ============================================================

def process_video(url: str, session_dir: Path):
    """1本の動画に対してすべての処理を行う"""

    sep = "─" * 55

    # ── 1. メタ情報を取得 ──────────────────────────────────
    print(f"\n{sep}")
    print(f"  動画情報を取得中: {url}")
    info_result = subprocess.run(
        ["yt-dlp", "--dump-json", "--no-playlist", url],
        capture_output=True, text=True,
        encoding="utf-8", errors="replace",
    )
    if info_result.returncode != 0:
        print(f"  [ERROR] 動画情報の取得に失敗しました:\n{info_result.stderr}")
        return False

    info      = json.loads(info_result.stdout)
    title_raw = info.get("title", "untitled")
    title     = sanitize_filename(title_raw)
    video_id  = info.get("id", "unknown")
    upload    = info.get("upload_date", "")
    date_str  = (
        f"{upload[:4]}-{upload[4:6]}-{upload[6:]}"
        if len(upload) == 8 else "nodate"
    )
    description = info.get("description", "（説明なし）")

    # 動画ごとのフォルダ: YYYY-MM-DD_タイトル_ID
    folder_name = f"{date_str}_{title}_{video_id}"
    video_dir   = session_dir / folder_name
    video_dir.mkdir(parents=True, exist_ok=True)

    base_name       = folder_name
    output_template = str(video_dir / base_name)

    print(f"  タイトル : {title_raw}")
    print(f"  動画ID  : {video_id}")
    print(f"  保存先  : {video_dir}")

    # ── 2. 動画情報テキストを保存 ─────────────────────────
    info_txt_path = video_dir / f"{base_name}.info.txt"
    with info_txt_path.open("w", encoding="utf-8") as out:
        out.write("# 動画情報\n")
        out.write(f"タイトル  : {title_raw}\n")
        out.write(f"投稿日    : {date_str}\n")
        out.write(f"動画ID    : {video_id}\n")
        out.write(f"URL       : {url}\n")
        out.write(f"\n{'─'*40}\n【説明】\n{'─'*40}\n")
        out.write(description + "\n")
    print(f"\n  📄 動画情報を保存: {info_txt_path.name}")

    # ── 3. 字幕（VTT → Python で SRT に変換） ────────────
    run_cmd(
        [
            "yt-dlp",
            "--skip-download", "--no-playlist",
            "--write-sub", "--write-auto-sub",
            "--sub-langs", "ja",
            "--no-part",
            "-o", output_template,
            url,
        ],
        "字幕のダウンロード（VTT）",
    )

    vtt_path = find_file(video_dir, base_name, ".ja.vtt")
    if vtt_path:
        srt_path = video_dir / f"{base_name}.ja.srt"
        if vtt_to_srt(vtt_path, srt_path):
            print(f"    📄 SRT に変換: {srt_path.name}")
            delete_if_exists(vtt_path)          # VTT は不要なので削除
        else:
            print("    [WARN] VTT→SRT 変換に失敗しました（VTT はそのまま残します）")
    else:
        print("    [INFO] VTT ファイルなし（字幕なし動画の場合は正常）")

    # ── 4. ライブチャット ─────────────────────────────────
    run_cmd(
        [
            "yt-dlp",
            "--skip-download", "--no-playlist",
            "--write-sub",
            "--sub-langs", "live_chat",
            "--no-part",
            "-o", output_template,
            url,
        ],
        "ライブチャットのダウンロード",
    )

    live_chat_json = find_file(video_dir, base_name, ".live_chat.json")
    if live_chat_json:
        live_chat_txt = video_dir / f"{base_name}.live_chat.txt"
        print(f"\n  ▶ ライブチャットをテキストに変換中...")
        extract_live_chat(live_chat_json, live_chat_txt, title_raw, url)
        delete_if_exists(live_chat_json)        # JSON は不要なので削除
    else:
        print("    [INFO] ライブチャットなし（通常動画の場合は正常）")

    # ── 5. 通常コメント ───────────────────────────────────
    run_cmd(
        [
            "yt-dlp",
            "--skip-download", "--no-playlist",
            "--write-info-json",
            "--write-comments",
            "--no-write-playlist-metafiles",
            "--no-part",
            "-o", output_template,
            url,
        ],
        "通常コメントのダウンロード",
    )

    info_json_path    = find_file(video_dir, base_name, ".info.json")
    comments_txt_path = video_dir / f"{base_name}.comments.txt"

    if info_json_path:
        with info_json_path.open(encoding="utf-8", errors="replace") as f:
            full_info = json.load(f)

        comments: list[dict] = full_info.get("comments", [])
        if comments:
            comments.sort(key=lambda c: c.get("timestamp", 0))
            with comments_txt_path.open("w", encoding="utf-8") as out:
                out.write("# コメント一覧\n")
                out.write(f"# 動画: {title_raw}\n")
                out.write(f"# URL : {url}\n")
                out.write(f"# 件数: {len(comments)}\n\n")
                for c in comments:
                    ts = c.get("timestamp")
                    dt = (
                        datetime.fromtimestamp(ts, tz=timezone.utc)
                               .strftime("%Y-%m-%d %H:%M UTC")
                        if ts else "不明"
                    )
                    author = c.get("author", "不明")
                    text   = c.get("text",   "")
                    likes  = c.get("like_count", 0)
                    out.write(f"[{dt}] {author}（👍 {likes}）\n{text}\n\n")
            print(f"\n    💬 コメント {len(comments)} 件を保存: {comments_txt_path.name}")
        else:
            print("\n    [INFO] コメントが見つかりませんでした。")

        delete_if_exists(info_json_path)        # info.json は不要なので削除
    else:
        print("    [WARN] info.json が見つからないためコメント抽出をスキップ")

    # ── 6. 完了サマリ ─────────────────────────────────────
    print(f"\n  {'─'*40}")
    print(f"  [{title_raw}] 保存されたファイル:")
    for f in sorted(video_dir.iterdir()):
        print(f"    {f.name}  ({f.stat().st_size / 1024:.1f} KB)")

    return True


# ============================================================
# エントリーポイント
# ============================================================

def collect_urls_from_args() -> list[str]:
    """コマンドライン引数から URL リストを収集する"""
    args = sys.argv[1:]

    # --file urls.txt モード
    if args and args[0] == "--file":
        if len(args) < 2:
            print("[ERROR] --file の後にファイルパスを指定してください。")
            sys.exit(1)
        file_path = Path(args[1])
        if not file_path.exists():
            print(f"[ERROR] ファイルが見つかりません: {file_path}")
            sys.exit(1)
        urls = [
            line.strip()
            for line in file_path.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.startswith("#")
        ]
        return urls

    # 通常の引数モード
    if args:
        return args

    # 対話モード
    print("YouTube URLを1件ずつ入力してください。")
    print("終わったら何も入力せず Enter を押してください。\n")
    urls = []
    while True:
        try:
            url = input(f"URL {len(urls)+1}: ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not url:
            break
        urls.append(url)
    return urls


def main():
    urls = collect_urls_from_args()

    if not urls:
        print("[ERROR] URLが指定されていません。")
        sys.exit(1)

    # 実行日時の親フォルダ（例: downloads_20260429_1430）
    now        = datetime.now()
    session_dir = Path(f"downloads_{now.strftime('%Y%m%d_%H%M')}")
    session_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n{'='*55}")
    print(f"  処理対象: {len(urls)} 件")
    print(f"  保存先  : {session_dir}/")
    print(f"{'='*55}")

    success = 0
    for i, url in enumerate(urls, 1):
        print(f"\n\n{'━'*55}")
        print(f"  [{i}/{len(urls)}] 処理中...")
        if process_video(url, session_dir):
            success += 1

    print(f"\n\n{'='*55}")
    print(f"  完了: {success}/{len(urls)} 件成功")
    print(f"  保存先: {session_dir.resolve()}")
    print(f"{'='*55}\n")


if __name__ == "__main__":
    main()
