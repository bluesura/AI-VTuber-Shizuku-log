#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
=============================================================================
YouTube テキストデータダウンローダー (Subtitle / Chat / Comment)  v3

【事前準備】
  pip install -U yt-dlp

【使い方】
  python download_youtube_subtitles.py <URL1> <URL2> ...
  python download_youtube_subtitles.py --file urls.txt
  python download_youtube_subtitles.py                 # 対話モード

【主なオプション】
  --file PATH              URLリストファイル（1行1URL、# でコメント）
  --outdir PATH            出力先の親ディレクトリ（既定: カレント）
  --lang ja,en             字幕の言語（既定: ja）
  --no-comments            通常コメントの取得をスキップ
  --max-comments N         取得するコメント数の上限
  --no-chat                ライブチャットの取得をスキップ
  --chat-all               スパチャ・メンバーシップ等もチャットに含める
  --flat-comments          返信のインデント（スレッド構造）を付けない
  --keep-dup-subs          自動字幕の重複行を除去しない
  --keep-intermediate      中間ファイル(.vtt/.json)を削除せず残す
  --skip-existing          既に処理済みならスキップ
  --cookies-from-browser B 会員限定/年齢制限動画用（chrome, firefox, edge ...）
  --sleep SEC              動画1本ごとの待機秒数（既定: 1.0）

【匿名化オプション】※既定で有効
  --no-anon                匿名化しない（生の表示名をそのまま出力）
  --anon-salt STR          ソルト（環境変数 YT_ANON_SALT でも指定可）
  --anon-key name|channel  ハッシュ対象（既定: name = 表示名）
  --anon-prefix STR        匿名IDの接頭辞（既定: User_）
  --anon-len N             匿名IDのハッシュ桁数（既定: 8）
  --no-mention             著者名の @ を外す（既定は @User_xxxxxxxx 形式）
  --whitelist A,B,C        匿名化しない名前を追加
  --whitelist-file PATH    ホワイトリストファイル（既定: 同フォルダの anon_whitelist.txt）
  --anon-uploader          投稿者本人も匿名化する（既定: 匿名化しない）
  --keep-text-mentions     本文中の @名前 を置換しない
  --anon-map PATH          原名→匿名ID の対応表を書き出す（※個人情報を含む）

【出力フォルダ構成】
  downloads_YYYYMMDD_HHMM/          ← 実行日時の親フォルダ
    YYYY-MM-DD_タイトル/             ← 動画ごとのフォルダ（IDなし）
      <動画ID>.info.txt              ← 動画情報（投稿日・再生時間・タイトル・説明）
      <動画ID>.ja.srt                ← 字幕（SRT形式）
      <動画ID>.live_chat.txt         ← ライブチャット（匿名化済み）
      <動画ID>.comments.txt          ← 通常コメント（匿名化済み・返信はインデント）
=============================================================================
"""

from __future__ import annotations   # Python 3.8/3.9 でも "X | None" 記法を許容

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Windows コンソールが CP932 でも文字化けしないよう UTF-8 に強制
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


# ============================================================
# 匿名化の設定（ここを書き換えるだけで挙動を変えられます）
# ============================================================

# ソルト。変更すると過去アーカイブと匿名IDが一致しなくなるので注意。
ANON_SALT_DEFAULT = os.environ.get("YT_ANON_SALT", "shizuku_archive_secret_salt_2026")

ANON_PREFIX_DEFAULT = "User_"     # 匿名IDの接頭辞
ANON_LEN_DEFAULT = 8              # SHA-256 hexdigest から使う桁数
ANON_MENTION_DEFAULT = True       # 出力を "@User_xxxxxxxx" 形式にする（False で @ なし）
ANON_KEY_DEFAULT = "name"         # "name"（表示名）または "channel"（チャンネルID）

# 匿名化しない名前。ここに追記するか anon_whitelist.txt / --whitelist で拡張。
# 照合は前後空白・先頭 @ ・大文字小文字を無視して行われます。
WHITELIST_DEFAULT = {
    "Aki",
    "aki5503",
    "AIVtuber_Shizuku",
    "Shizuku_AItuber",
    "Shizuku",
    "しずく",
    "あき先生",
}

# スクリプトと同じフォルダに置くと自動で読み込まれる追加ホワイトリスト
WHITELIST_FILE_DEFAULT = "anon_whitelist.txt"

# 名前が不明・欠損のときのプレースホルダ（匿名化対象外）
PLACEHOLDER_NAMES = {"", "不明"}

# コメント日時の表示タイムゾーン（日本標準時 = UTC+9）
JST = timezone(timedelta(hours=9))


class Anonymizer:
    """
    表示名・チャンネルIDを一方向ハッシュで匿名化する。
    同じ人物には常に同じIDが割り当たるため、発言の連続性は保たれる。
    """

    def __init__(
        self,
        enabled: bool = True,
        salt: str = ANON_SALT_DEFAULT,
        prefix: str = ANON_PREFIX_DEFAULT,
        hash_len: int = ANON_LEN_DEFAULT,
        key: str = ANON_KEY_DEFAULT,
        mention: bool = ANON_MENTION_DEFAULT,
        whitelist: set[str] | None = None,
        keep_uploader: bool = True,
    ):
        self.enabled = enabled
        self.salt = salt
        self.prefix = prefix
        self.hash_len = max(4, min(64, int(hash_len)))
        self.key = key if key in ("name", "channel") else "name"
        self.mention = mention
        self.keep_uploader = keep_uploader
        self.whitelist = {self.normalize(w) for w in (whitelist or WHITELIST_DEFAULT)}
        self._cache: dict[str, str] = {}
        self.mapping: dict[str, str] = {}     # 原名 -> 匿名ID（--anon-map 用）
        # 既に匿名化済みの名前を二重ハッシュしないための判定パターン
        self._already = re.compile(
            rf"^{re.escape(self.prefix)}[0-9a-f]{{{self.hash_len}}}$"
        )

    # ---- 照合用の正規化 ----------------------------------
    @staticmethod
    def normalize(name: str | None) -> str:
        name = (name or "").strip()
        name = name.lstrip("@").strip()
        name = re.sub(r"\s+", " ", name)
        return name.casefold()

    def is_whitelisted(self, name: str | None, channel_id: str | None = None) -> bool:
        if self.normalize(name) in self.whitelist:
            return True
        if channel_id and channel_id.strip().casefold() in self.whitelist:
            return True
        return False

    # ---- ハッシュ本体 ------------------------------------
    def _hash(self, value: str) -> str:
        cached = self._cache.get(value)
        if cached:
            return cached
        digest = hashlib.sha256((value + self.salt).encode("utf-8")).hexdigest()
        anon_id = f"{self.prefix}{digest[:self.hash_len]}"
        self._cache[value] = anon_id
        return anon_id

    def anon_id(self, name: str | None, channel_id: str | None = None) -> str:
        """匿名ID（接頭辞付き・@なし）を返す。対象外ならそのままの名前を返す。"""
        raw = (name or "").strip()
        if not self.enabled:
            return raw
        if raw in PLACEHOLDER_NAMES:
            return raw
        if self._already.match(raw):          # 二重処理を防止（冪等）
            return raw
        if self.is_whitelisted(raw, channel_id):
            return raw

        source = channel_id.strip() if (self.key == "channel" and channel_id) else raw
        anon = self._hash(source)
        self.mapping.setdefault(raw, anon)
        return anon

    def author(self, name: str | None, channel_id: str | None = None,
               is_uploader: bool = False) -> str:
        """出力用の著者表記を返す（--anon-mention 指定時は @ 付き）"""
        raw = (name or "").strip() or "不明"
        if is_uploader and self.keep_uploader:
            display = raw
        else:
            display = self.anon_id(raw, channel_id)
        if self.mention and display not in PLACEHOLDER_NAMES:
            return f"@{display}"
        return display

    # ---- 本文中の @メンション置換 ------------------------
    def mention_map(self, entries) -> dict[str, str]:
        """
        本文中の "@原名" を "@匿名ID" に置き換えるための対応表を作る。
        entries は (表示名, チャンネルID, そのまま残すか) のイテラブル。
        著者名の匿名IDと同じ値になるよう、同じキー設定で算出する。
        """
        mapping: dict[str, str] = {}
        if not self.enabled:
            return mapping
        for name, channel_id, keep in entries:
            raw = (name or "").strip()
            if not raw or raw in PLACEHOLDER_NAMES or keep:
                continue
            if self._already.match(raw) or self.is_whitelisted(raw, channel_id):
                continue
            anon = self.anon_id(raw, channel_id)
            if anon != raw:
                mapping[raw] = anon
        return mapping

    @staticmethod
    def build_mention_regex(mapping: dict[str, str]):
        if not mapping:
            return None
        # 長い名前を優先してマッチさせる（部分一致による取りこぼしを防ぐ）
        names = sorted(mapping, key=len, reverse=True)
        return re.compile("@(" + "|".join(re.escape(n) for n in names) + ")")

    @staticmethod
    def scrub(text: str, mapping: dict[str, str], pattern) -> str:
        if not text or not pattern:
            return text
        return pattern.sub(lambda m: "@" + mapping[m.group(1)], text)

    # ---- 対応表の書き出し --------------------------------
    def dump_mapping(self, path: Path):
        if not self.mapping:
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as out:
            out.write("# 原名\t匿名ID\n")
            out.write("# ※このファイルは個人情報を含みます。共有しないでください。\n")
            for raw, anon in sorted(self.mapping.items()):
                out.write(f"{raw}\t{anon}\n")
        print(f"  🔐 匿名化対応表を書き出しました: {path}")


def load_whitelist(args) -> set[str]:
    """既定値 ＋ ファイル ＋ --whitelist を合成する"""
    names = set(WHITELIST_DEFAULT)

    if args.whitelist_file:
        path = Path(args.whitelist_file)
        required = True
    else:
        path = Path(__file__).resolve().with_name(WHITELIST_FILE_DEFAULT)
        required = False

    if path.exists():
        for line in path.read_text(encoding="utf-8", errors="replace") \
                        .lstrip("\ufeff").splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                names.add(line)
        print(f"  🔐 ホワイトリストを読み込みました: {path.name}")
    elif required:
        print(f"  [WARN] ホワイトリストファイルが見つかりません: {path}")

    if args.whitelist:
        names.update(n.strip() for n in args.whitelist.split(",") if n.strip())

    return names


# ============================================================
# yt-dlp の起動コマンドを決定
# ============================================================

def resolve_ytdlp() -> list[str]:
    """PATH 上の yt-dlp を探し、無ければ `python -m yt_dlp` にフォールバックする"""
    exe = shutil.which("yt-dlp")
    if exe:
        return [exe]
    probe = subprocess.run(
        [sys.executable, "-m", "yt_dlp", "--version"],
        capture_output=True, text=True,
    )
    if probe.returncode == 0:
        return [sys.executable, "-m", "yt_dlp"]
    print("[ERROR] yt-dlp が見つかりません。`pip install -U yt-dlp` を実行してください。")
    sys.exit(1)


YTDLP: list[str] = []   # main() で初期化


# ============================================================
# ユーティリティ
# ============================================================

_RESERVED = {
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}


def sanitize_filename(name: str, max_len: int = 60) -> str:
    """ファイル名に使えない文字を除去し、長すぎる場合は切り詰める"""
    name = re.sub(r"[\x00-\x1f\x7f]", "", name)          # 制御文字
    name = re.sub(r'[\\/*?:"<>|]', "_", name)            # 禁止文字
    name = re.sub(r"\s+", " ", name).strip()             # 連続空白を圧縮
    if len(name) > max_len:
        name = name[:max_len]
    name = name.rstrip(" .")                             # 末尾の空白/ピリオドは Windows で不可
    if name.upper() in _RESERVED:
        name = "_" + name
    return name or "untitled"


def glob_escape(name: str) -> str:
    """glob のメタ文字をエスケープ"""
    return re.sub(r"([\[\]*?])", r"[\1]", name)


def find_file(folder: Path, base_name: str, suffix: str) -> Path | None:
    """日本語ファイル名で exists() が失敗するケースに備え glob で探す"""
    matches = sorted(folder.glob(f"{glob_escape(base_name)}{suffix}"))
    return matches[0] if matches else None


def delete_if_exists(path: Path | None, keep: bool = False):
    if path is None or keep:
        return
    try:
        if path.exists():
            path.unlink()
            print(f"    🗑  削除: {path.name}")
    except OSError as e:
        print(f"    [WARN] 削除できませんでした: {path.name} ({e})")


def format_duration(seconds) -> str:
    """
    秒数を [HH:MM:SS] / [MM:SS] 形式に整形する。
    1時間以上なら [HH:MM:SS]、それ未満なら [MM:SS]。取得不能なら [--:--]。
    """
    if seconds is None:
        return "[--:--]"
    try:
        total = int(round(float(seconds)))
    except (TypeError, ValueError):
        return "[--:--]"
    if total < 0:
        total = 0
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    return f"[{h:02d}:{m:02d}:{s:02d}]" if h else f"[{m:02d}:{s:02d}]"


def parse_duration_string(text: str | None):
    """yt-dlp の duration_string ("1:02:03" など) を秒に変換する（保険用）"""
    if not text:
        return None
    parts = text.strip().split(":")
    if not all(p.isdigit() for p in parts) or not 1 <= len(parts) <= 3:
        return None
    total = 0
    for p in parts:
        total = total * 60 + int(p)
    return total


def run_cmd(cmd: list[str], label: str) -> subprocess.CompletedProcess:
    print(f"\n  ▶ {label}")
    result = subprocess.run(
        cmd, capture_output=True, text=True,
        encoding="utf-8", errors="replace",
    )
    if result.returncode != 0:
        stderr = (result.stderr or "").strip()
        level = "ERROR" if re.search(r"\bERROR\b", stderr) else "WARN"
        for line in stderr.splitlines()[-8:]:
            print(f"  [{level}] {line}")
    else:
        print("    ✅ 完了")
    return result


# ============================================================
# VTT → SRT 変換（ffmpeg 不要）
# ============================================================

_TS_RE = re.compile(r"^(?:(\d+):)?(\d{1,2}):(\d{2})[.,](\d{1,3})$")
_CUE_RE = re.compile(r"^(\S+)\s*-->\s*(\S+)")
_TAG_RE = re.compile(r"<[^>]*>")
_ENTITIES = {"&nbsp;": " ", "&amp;": "&", "&lt;": "<", "&gt;": ">",
             "&quot;": '"', "&#39;": "'"}


def _ts_to_srt(ts: str) -> str | None:
    m = _TS_RE.match(ts)
    if not m:
        return None
    h = int(m.group(1) or 0)
    mi, s = int(m.group(2)), int(m.group(3))
    ms = m.group(4).ljust(3, "0")[:3]
    return f"{h:02d}:{mi:02d}:{s:02d},{ms}"


def _clean_text_line(line: str) -> str:
    line = _TAG_RE.sub("", line)
    for k, v in _ENTITIES.items():
        line = line.replace(k, v)
    return line.strip()


def vtt_to_srt(vtt_path: Path, srt_path: Path, dedup: bool = True) -> bool:
    """
    .vtt を .srt に変換する（ffmpeg 不要）。
      - インラインタグ（<c> / <00:00:01.234>）を除去
      - キュー設定（align:start position:0% 等）を除去
      - MM:SS.mmm 形式のタイムスタンプも HH:MM:SS,mmm に正規化
      - dedup=True なら自動字幕特有のローリング重複行をまとめる
    """
    text = vtt_path.read_text(encoding="utf-8", errors="replace")
    text = text.lstrip("\ufeff").replace("\r\n", "\n").replace("\r", "\n")

    cues: list[tuple[str, str, list[str]]] = []
    prev_lines: list[str] = []

    for block in re.split(r"\n{2,}", text):
        block = block.strip("\n")
        if not block:
            continue
        lines = block.split("\n")
        head = lines[0].strip()
        if head.startswith(("WEBVTT", "NOTE", "STYLE", "REGION",
                            "Kind:", "Language:", "X-TIMESTAMP-MAP")):
            continue

        cue_idx = next((i for i, l in enumerate(lines) if "-->" in l), None)
        if cue_idx is None:
            continue

        m = _CUE_RE.match(lines[cue_idx].strip())
        if not m:
            continue
        start, end = _ts_to_srt(m.group(1)), _ts_to_srt(m.group(2))
        if not start or not end:
            continue

        body = [_clean_text_line(l) for l in lines[cue_idx + 1:]]
        body = [l for l in body if l]
        if not body:
            continue

        if dedup:
            new_body = [l for l in body if l not in prev_lines]
            prev_lines = body
            if not new_body:
                if cues:
                    cues[-1] = (cues[-1][0], end, cues[-1][2])
                continue
            body = new_body

        cues.append((start, end, body))

    if not cues:
        return False

    out = []
    for i, (start, end, body) in enumerate(cues, 1):
        out.append(f"{i}\n{start} --> {end}\n" + "\n".join(body))
    srt_path.write_text("\n\n".join(out) + "\n", encoding="utf-8")
    return True


# ============================================================
# ライブチャット JSON → TXT（匿名化つき）
# ============================================================

def _run_text(run: dict) -> str:
    """message.runs の 1 要素をテキスト化（カスタム絵文字は :shortcut: に）"""
    if "text" in run:
        return run["text"]
    emoji = run.get("emoji", {})
    if emoji.get("isCustomEmoji"):
        shortcuts = emoji.get("shortcuts") or []
        return shortcuts[0] if shortcuts else ""
    return emoji.get("emojiId", "")


def _runs_to_text(node: dict | None) -> str:
    if not node:
        return ""
    if "simpleText" in node:
        return node["simpleText"]
    return "".join(_run_text(r) for r in node.get("runs", []))


def _offset_to_timestamp(obj: dict) -> str:
    ms = obj.get("replayChatItemAction", {}).get("videoOffsetTimeMsec")
    try:
        return format_duration(int(ms) / 1000).strip("[]")
    except (TypeError, ValueError):
        return "??:??"


def _is_owner(renderer: dict) -> bool:
    """配信者本人（チャンネル所有者）バッジを持つか"""
    for badge in renderer.get("authorBadges") or []:
        icon = (badge.get("liveChatAuthorBadgeRenderer", {})
                     .get("icon", {}).get("iconType"))
        if icon == "OWNER":
            return True
    return False


def extract_live_chat(json_path: Path, txt_path: Path, video_title: str,
                      url: str, anon: Anonymizer,
                      include_all: bool = False,
                      scrub_text: bool = True) -> int:
    """
    .live_chat.json（1行1JSONオブジェクト）から
    [再生時間] 著者名: メッセージ 形式のテキストに変換する。
    著者名は匿名化され、本文中の "@名前" も同じ匿名IDに置き換えられる。
    """
    records: list[dict] = []
    seen: set[str] = set()

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
                item = action.get("addChatItemAction", {}).get("item", {})
                if not item:
                    continue

                renderer = item.get("liveChatTextMessageRenderer")
                suffix = ""

                if renderer is None and include_all:
                    if "liveChatPaidMessageRenderer" in item:
                        renderer = item["liveChatPaidMessageRenderer"]
                        amount = _runs_to_text(renderer.get("purchaseAmountText"))
                        suffix = f"（💰 {amount}）" if amount else "（💰）"
                    elif "liveChatPaidStickerRenderer" in item:
                        renderer = item["liveChatPaidStickerRenderer"]
                        amount = _runs_to_text(renderer.get("purchaseAmountText"))
                        suffix = f"（🎨 {amount}）" if amount else "（🎨）"
                    elif "liveChatMembershipItemRenderer" in item:
                        renderer = item["liveChatMembershipItemRenderer"]
                        suffix = "（🎫 メンバー）"

                if not renderer:
                    continue

                mid = renderer.get("id")
                if mid:
                    if mid in seen:
                        continue
                    seen.add(mid)

                text = _runs_to_text(renderer.get("message")).strip()
                if not text:
                    text = _runs_to_text(renderer.get("headerSubtext")).strip()
                if not text:
                    continue

                records.append({
                    "ts": (renderer.get("timestampText", {}) or {}).get("simpleText")
                          or _offset_to_timestamp(obj),
                    "name": _runs_to_text(renderer.get("authorName")) or "不明",
                    "channel": renderer.get("authorExternalChannelId"),
                    "owner": _is_owner(renderer),
                    "suffix": suffix,
                    "text": text,
                })

    if not records:
        print("    [INFO] ライブチャットのメッセージが見つかりませんでした。")
        return 0

    mapping = anon.mention_map(
        (r["name"], r["channel"], r["owner"] and anon.keep_uploader) for r in records
    ) if scrub_text else {}
    pattern = anon.build_mention_regex(mapping)

    with txt_path.open("w", encoding="utf-8") as out:
        out.write("# ライブチャット一覧\n")
        out.write(f"# 動画: {video_title}\n")
        out.write(f"# URL : {url}\n")
        out.write(f"# 件数: {len(records)}\n\n")
        for r in records:
            author = anon.author(r["name"], r["channel"], r["owner"]) + r["suffix"]
            text = anon.scrub(r["text"], mapping, pattern)
            out.write(f"[{r['ts']}] {author}: {text}\n")

    label = "匿名化" if anon.enabled else "変換"
    print(f"    💬 ライブチャット {len(records)} 件を{label}して保存: {txt_path.name}")
    return len(records)


# ============================================================
# コメント JSON → TXT（匿名化＋スレッド構造保持）
# ============================================================

REPLY_INDENT = "    "        # 返信 1 階層あたりのインデント
REPLY_MARK = "└ "            # 返信の先頭マーク


def _comment_dt(ts) -> str:
    try:
        return (datetime.fromtimestamp(float(ts), tz=JST)
                .strftime("%Y-%m-%d %H:%M JST")) if ts else "不明"
    except (TypeError, ValueError, OSError):
        return "不明"


def _parent_id(c: dict) -> str | None:
    """親コメントIDを返す（トップレベルなら None）"""
    parent = c.get("parent")
    if parent and parent != "root":
        return parent
    # parent が無い場合は ID の構造 (親ID.返信ID) から推定
    cid = c.get("id") or ""
    if "." in cid:
        return cid.split(".", 1)[0]
    return None


def _format_comment(c: dict, anon: Anonymizer, mapping: dict, pattern,
                    depth: int) -> str:
    author = anon.author(
        c.get("author") or "不明",
        c.get("author_id"),
        bool(c.get("author_is_uploader")),
    )
    dt = _comment_dt(c.get("timestamp"))
    likes = c.get("like_count") or 0
    text = anon.scrub((c.get("text") or "").strip(), mapping, pattern)

    if depth <= 0:
        head = f"[{dt}] {author}（👍 {likes}）"
        body_indent = ""
    else:
        pad = REPLY_INDENT * depth
        head = f"{pad}{REPLY_MARK}[{dt}] {author}（👍 {likes}）"
        body_indent = pad + " " * len(REPLY_MARK)

    body = "\n".join(body_indent + line for line in text.split("\n"))
    return f"{head}\n{body}\n"


def write_comments(comments: list[dict], path: Path, video_title: str, url: str,
                   anon: Anonymizer, threaded: bool = True,
                   scrub_text: bool = True) -> int:
    """
    コメントを保存する。
    threaded=True なら parent フィールドを使って返信を親の直下にインデント表示する。
    """
    mapping = anon.mention_map(
        (
            c.get("author"),
            c.get("author_id"),
            bool(c.get("author_is_uploader")) and anon.keep_uploader,
        )
        for c in comments
    ) if scrub_text else {}
    pattern = anon.build_mention_regex(mapping)

    def key(c):
        return c.get("timestamp") or 0

    children: dict[str, list[dict]] = defaultdict(list)

    if threaded:
        by_id = {c["id"]: c for c in comments if c.get("id")}
        roots: list[dict] = []
        for c in comments:
            pid = _parent_id(c)
            if pid and pid in by_id and pid != c.get("id"):
                children[pid].append(c)
            else:
                roots.append(c)          # 親が取得できなかった返信もここに入る
        roots.sort(key=key)
        for lst in children.values():
            lst.sort(key=key)
    else:
        roots = sorted(comments, key=key)

    with path.open("w", encoding="utf-8") as out:
        out.write("# コメント一覧\n")
        out.write(f"# 動画: {video_title}\n")
        out.write(f"# URL : {url}\n")
        out.write(f"# 件数: {len(comments)}\n\n")

        def emit(c: dict, depth: int, guard: set[str]):
            out.write(_format_comment(c, anon, mapping, pattern, depth) + "\n")
            cid = c.get("id")
            if not cid or cid in guard:
                return
            guard.add(cid)
            for child in children.get(cid, []):
                emit(child, depth + 1, guard)

        for root in roots:
            emit(root, 0, set())

    return len(comments)


# ============================================================
# 動画1本の処理
# ============================================================

def fetch_metadata(url: str) -> dict | None:
    result = subprocess.run(
        YTDLP + ["--dump-json", "--no-playlist", "--no-warnings", url],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    if result.returncode != 0 or not (result.stdout or "").strip():
        print(f"  [ERROR] 動画情報の取得に失敗しました:\n{(result.stderr or '').strip()}")
        return None
    try:
        return json.loads(result.stdout.strip().splitlines()[0])
    except (json.JSONDecodeError, IndexError) as e:
        print(f"  [ERROR] メタ情報の JSON 解析に失敗しました: {e}")
        return None


def process_video(url: str, session_dir: Path, args, anon: Anonymizer) -> bool:
    sep = "─" * 55

    # ── 1. メタ情報を取得 ──────────────────────────────────
    print(f"\n{sep}")
    print(f"  動画情報を取得中: {url}")
    info = fetch_metadata(url)
    if info is None:
        return False

    title_raw = info.get("title") or "untitled"
    title = sanitize_filename(title_raw)
    video_id = info.get("id") or "unknown"
    upload = info.get("upload_date") or ""
    date_str = f"{upload[:4]}-{upload[4:6]}-{upload[6:]}" if len(upload) == 8 else "nodate"
    description = info.get("description") or "（説明なし）"

    seconds = info.get("duration")
    if seconds is None:
        seconds = parse_duration_string(info.get("duration_string"))
    duration_str = format_duration(seconds)

    # フォルダ名は「日付_タイトル」（IDなし）、ファイル名は動画IDのみ
    folder_name = f"{date_str}_{title}"
    video_dir = session_dir / folder_name
    base_name = sanitize_filename(video_id, max_len=40)
    output_template = str(video_dir / base_name)

    info_txt_path = video_dir / f"{base_name}.info.txt"
    if args.skip_existing and info_txt_path.exists():
        print(f"  ⏭  既に処理済みのためスキップ: {folder_name}/{base_name}")
        return True

    video_dir.mkdir(parents=True, exist_ok=True)

    print(f"  タイトル : {title_raw}")
    print(f"  再生時間 : {duration_str}")
    print(f"  動画ID  : {video_id}")
    print(f"  保存先  : {video_dir}")

    # ── 2. 動画情報テキストを保存 ─────────────────────────
    with info_txt_path.open("w", encoding="utf-8") as out:
        out.write("# 動画情報\n")
        out.write(f"タイトル  : {title_raw}\n")
        out.write(f"投稿日    : {date_str}\n")
        out.write(f"再生時間  : {duration_str}\n")
        out.write(f"動画ID    : {video_id}\n")
        out.write(f"URL       : {url}\n")
        out.write(f"\n{'─'*40}\n【説明】\n{'─'*40}\n")
        out.write(description + "\n")
    print(f"\n  📄 動画情報を保存: {info_txt_path.name}")

    common = YTDLP + [
        "--skip-download", "--no-playlist", "--no-part",
        "--retries", "3", "--socket-timeout", "30",
    ]
    if args.cookies_from_browser:
        common += ["--cookies-from-browser", args.cookies_from_browser]

    # ── 3. 字幕 ＋ ライブチャット（1回の呼び出しにまとめる） ──
    sub_langs = args.lang
    if not args.no_chat:
        sub_langs = f"{sub_langs},live_chat"

    run_cmd(
        common + [
            "--write-subs", "--write-auto-subs",
            "--sub-langs", sub_langs,
            "-o", output_template,
            url,
        ],
        f"字幕・ライブチャットのダウンロード（{sub_langs}）",
    )

    vtt_files = sorted(video_dir.glob(f"{glob_escape(base_name)}.*.vtt"))
    if vtt_files:
        for vtt_path in vtt_files:
            srt_path = vtt_path.with_suffix(".srt")
            if vtt_to_srt(vtt_path, srt_path, dedup=not args.keep_dup_subs):
                print(f"    📄 SRT に変換: {srt_path.name}")
                delete_if_exists(vtt_path, keep=args.keep_intermediate)
            else:
                print(f"    [WARN] VTT→SRT 変換に失敗（{vtt_path.name} はそのまま残します）")
    else:
        print("    [INFO] VTT ファイルなし（字幕なし動画の場合は正常）")

    if not args.no_chat:
        live_chat_json = find_file(video_dir, base_name, ".live_chat.json")
        if live_chat_json:
            live_chat_txt = video_dir / f"{base_name}.live_chat.txt"
            print("\n  ▶ ライブチャットをテキストに変換中...")
            extract_live_chat(
                live_chat_json, live_chat_txt, title_raw, url, anon,
                include_all=args.chat_all,
                scrub_text=not args.keep_text_mentions,
            )
            delete_if_exists(live_chat_json, keep=args.keep_intermediate)
        else:
            print("    [INFO] ライブチャットなし（通常動画の場合は正常）")

    # ── 4. 通常コメント ───────────────────────────────────
    if not args.no_comments:
        cmd = common + [
            "--write-info-json", "--write-comments",
            "--no-write-playlist-metafiles",
            "-o", output_template,
        ]
        if args.max_comments:
            cmd += ["--extractor-args", f"youtube:max_comments={args.max_comments}"]
        cmd += [url]

        run_cmd(cmd, "通常コメントのダウンロード")

        info_json_path = find_file(video_dir, base_name, ".info.json")
        comments_txt_path = video_dir / f"{base_name}.comments.txt"

        if info_json_path:
            try:
                with info_json_path.open(encoding="utf-8", errors="replace") as f:
                    full_info = json.load(f)
            except (json.JSONDecodeError, OSError) as e:
                print(f"    [WARN] info.json の読み込みに失敗しました: {e}")
                full_info = {}

            comments = full_info.get("comments") or []
            if comments:
                n = write_comments(
                    comments, comments_txt_path, title_raw, url, anon,
                    threaded=not args.flat_comments,
                    scrub_text=not args.keep_text_mentions,
                )
                label = "匿名化" if anon.enabled else "変換"
                print(f"\n    💬 コメント {n} 件を{label}して保存: {comments_txt_path.name}")
            else:
                print("\n    [INFO] コメントが見つかりませんでした。")

            delete_if_exists(info_json_path, keep=args.keep_intermediate)
        else:
            print("    [WARN] info.json が見つからないためコメント抽出をスキップ")

    # ── 5. 完了サマリ ─────────────────────────────────────
    print(f"\n  {'─'*40}")
    print(f"  [{title_raw}] 保存されたファイル:")
    for f in sorted(video_dir.glob(f"{glob_escape(base_name)}*")):
        try:
            size = f.stat().st_size / 1024
        except OSError:
            size = 0.0
        print(f"    {f.name}  ({size:.1f} KB)")

    return True


# ============================================================
# エントリーポイント
# ============================================================

def read_url_file(file_path: Path) -> list[str]:
    if not file_path.exists():
        print(f"[ERROR] ファイルが見つかりません: {file_path}")
        sys.exit(1)
    raw = file_path.read_text(encoding="utf-8", errors="replace").lstrip("\ufeff")
    urls = []
    for line in raw.splitlines():
        line = line.strip().strip('"').strip("'")
        if line and not line.startswith("#"):
            urls.append(line)
    return urls


def prompt_urls() -> list[str]:
    print("YouTube URLを1件ずつ入力してください。")
    print("終わったら何も入力せず Enter を押してください。\n")
    urls: list[str] = []
    while True:
        try:
            url = input(f"URL {len(urls)+1}: ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not url:
            break
        urls.append(url)
    return urls


def dedupe(seq: list[str]) -> list[str]:
    seen, out = set(), []
    for x in seq:
        if x not in seen:
            seen.add(x)
            out.append(x)
    return out


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="YouTube のテキストデータ（字幕・ライブチャット・コメント）を取得し、"
                    "投稿者IDを匿名化して保存します。",
    )
    p.add_argument("urls", nargs="*", help="YouTube の URL（複数可）")
    p.add_argument("--file", type=Path, help="URLリストファイル（1行1URL）")
    p.add_argument("--outdir", type=Path, default=Path("."), help="出力先の親ディレクトリ")
    p.add_argument("--lang", default="ja", help="字幕の言語（例: ja / ja,en）")
    p.add_argument("--no-comments", action="store_true", help="通常コメントを取得しない")
    p.add_argument("--max-comments", type=int, help="取得するコメント数の上限")
    p.add_argument("--no-chat", action="store_true", help="ライブチャットを取得しない")
    p.add_argument("--chat-all", action="store_true", help="スパチャ・メンバー登録等も含める")
    p.add_argument("--flat-comments", action="store_true",
                   help="返信をインデントせず時系列で並べる")
    p.add_argument("--keep-dup-subs", action="store_true", help="自動字幕の重複行を除去しない")
    p.add_argument("--keep-intermediate", action="store_true", help="中間ファイルを残す")
    p.add_argument("--skip-existing", action="store_true", help="処理済みならスキップ")
    p.add_argument("--cookies-from-browser", metavar="BROWSER",
                   help="会員限定/年齢制限動画用（chrome, firefox, edge ...）")
    p.add_argument("--sleep", type=float, default=1.0, help="動画1本ごとの待機秒数")

    g = p.add_argument_group("匿名化")
    g.add_argument("--no-anon", action="store_true", help="匿名化しない")
    g.add_argument("--anon-salt", default=ANON_SALT_DEFAULT, help="ハッシュのソルト")
    g.add_argument("--anon-key", choices=("name", "channel"), default=ANON_KEY_DEFAULT,
                   help="ハッシュ対象（name=表示名 / channel=チャンネルID）")
    g.add_argument("--anon-prefix", default=ANON_PREFIX_DEFAULT, help="匿名IDの接頭辞")
    g.add_argument("--anon-len", type=int, default=ANON_LEN_DEFAULT, help="ハッシュ桁数")
    g.add_argument("--no-mention", dest="anon_mention", action="store_false",
                   default=ANON_MENTION_DEFAULT,
                   help="著者名の先頭に @ を付けない（既定は @User_xxxxxxxx 形式）")
    g.add_argument("--whitelist", help="匿名化しない名前をカンマ区切りで追加")
    g.add_argument("--whitelist-file", type=Path, help="ホワイトリストファイル")
    g.add_argument("--anon-uploader", action="store_true", help="投稿者本人も匿名化する")
    g.add_argument("--keep-text-mentions", action="store_true",
                   help="本文中の @名前 を置換しない")
    g.add_argument("--anon-map", type=Path,
                   help="原名→匿名IDの対応表を書き出す（個人情報を含みます）")
    return p


def main():
    global YTDLP

    args = build_parser().parse_args()

    urls = list(args.urls)
    if args.file:
        urls += read_url_file(args.file)
    if not urls:
        urls = prompt_urls()
    urls = dedupe(urls)

    if not urls:
        print("[ERROR] URLが指定されていません。")
        sys.exit(1)

    YTDLP = resolve_ytdlp()

    anon = Anonymizer(
        enabled=not args.no_anon,
        salt=args.anon_salt,
        prefix=args.anon_prefix,
        hash_len=args.anon_len,
        key=args.anon_key,
        mention=args.anon_mention,
        whitelist=load_whitelist(args),
        keep_uploader=not args.anon_uploader,
    )

    now = datetime.now()
    session_dir = args.outdir / f"downloads_{now.strftime('%Y%m%d_%H%M')}"
    session_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n{'='*55}")
    print(f"  処理対象: {len(urls)} 件")
    print(f"  保存先  : {session_dir}/")
    if anon.enabled:
        print(f"  匿名化  : 有効（{anon.prefix}xxxxxxxx / 対象={anon.key} / "
              f"除外 {len(anon.whitelist)} 件）")
    else:
        print("  匿名化  : 無効")
    print(f"{'='*55}")

    success = 0
    failed: list[str] = []
    interrupted = False

    for i, url in enumerate(urls, 1):
        print(f"\n\n{'━'*55}")
        print(f"  [{i}/{len(urls)}] 処理中...")
        try:
            if process_video(url, session_dir, args, anon):
                success += 1
            else:
                failed.append(url)
        except KeyboardInterrupt:
            print("\n  [INFO] ユーザーによる中断を検知しました。")
            interrupted = True
            failed.extend(urls[i - 1:])
            break
        except Exception as e:
            print(f"  [ERROR] 予期しないエラー: {type(e).__name__}: {e}")
            failed.append(url)

        if args.sleep > 0 and i < len(urls) and not interrupted:
            time.sleep(args.sleep)

    if args.anon_map:
        anon.dump_mapping(args.anon_map)

    if failed:
        retry_path = session_dir / "_failed_urls.txt"
        retry_path.write_text("\n".join(dedupe(failed)) + "\n", encoding="utf-8")

    print(f"\n\n{'='*55}")
    print(f"  完了: {success}/{len(urls)} 件成功")
    if failed:
        print(f"  失敗: {len(dedupe(failed))} 件 → {session_dir / '_failed_urls.txt'}")
        print(f"        再実行: python {Path(sys.argv[0]).name} "
              f"--file \"{session_dir / '_failed_urls.txt'}\"")
    print(f"  保存先: {session_dir.resolve()}")
    print(f"{'='*55}\n")

    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
