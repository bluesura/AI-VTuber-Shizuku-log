#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SRT → SBV 変換（YouTube ローリング字幕の重複を「完全一致」だけで整理）

設計方針
────────────────────────────────────────────────────────────────────────
1. 類似度・部分一致・句読点補正は一切使わない。
   隣接字幕の「行単位の完全一致」だけを持ち越しの根拠にする。
2. 解析できないブロックを黙って読み飛ばさない。既定でエラー停止する。
3. 判断できないものは削らない。既定では残して警告し、監査ログに記録する。
   --strict を付けると、判断できない箇所があった時点で中止する。
4. 中止した場合は書きかけの出力ファイルを残さない。
5. 変換後に「入力に存在した全ての行が出力に残っているか」を自動検証する。

使い方
  python srt_to_sbv.py input.srt
  python srt_to_sbv.py input.srt output.sbv.txt

効果音マーカーの削除（既定で有効）
  既定で [音楽] 行を削除する。マーカーを消した結果その字幕の本文が
  空になった場合は、その字幕（タイムライン）ごと削除する。本文が
  残る場合はマーカー行だけを取り除き、タイムラインは維持する。
  何を削除したかは監査ログ（.audit.txt）に記録する（終了コードには影響しない）。

主なオプション
  --strict            断定できない箇所があれば中止（出力を残さない）
  --lenient           壊れたブロックをエラーにせず警告してスキップ
  --preserve-times    元のタイムコードをそのまま使う（既定は中継分を前へ延長）
  --remove-markers L  削除する効果音マーカーを指定（既定: 音楽）
                      例: --remove-markers "音楽,拍手,笑い" / "[音楽]" 形式も可
  --no-remove-markers 効果音マーカーを削除しない（従来動作）
  --no-merge-markers  [拍手] 等の連続マーカーを統合しない
  --report FILE       監査ログの出力先（既定: 出力ファイル名 + .audit.txt）
  --quiet             標準出力を最小限にする

終了コード
  0 = 正常  /  3 = 警告ありで完了  /  1 = エラー  /  2 = --strict による中止

原理
────────────────────────────────────────────────────────────────────────
YouTube 自動字幕は画面に直前の行を残す「ローリング表示」のため、
1 つの発話行が新規キュー・中継キュー・持ち越しの計 3 回出力される。

  (1) 00:01:51,520 --> 00:01:54,510   ご主人様、…見に来て / くれて…先週
  (2) 00:01:54,510 --> 00:01:54,520   くれて…先週                  <- 10ms 中継
  (3) 00:01:54,520 --> 00:02:05,270   くれて…先週 / に引き続き…

直前の表示状態の末尾と、現キューの先頭が行単位で完全一致する分だけを
持ち越しとみなして除去する。一致しない行は必ず残す。

互換性: Python 3.8 以上（f-string 内でバックスラッシュを使わない書き方に統一）
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# Windows コンソール（CP932）でも日本語の表示で落ちないよう UTF-8 に強制する。
# 出力ファイルは常に UTF-8 で書くため、この設定は画面表示のみに影響する。
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# ── 定数 ──────────────────────────────────────────────────────────────────────

# 中継（settle）キューとみなす継続時間の上限。
# YouTube の中継キューは厳密に 10ms、通常キューは実測で最短 228ms あり余裕が大きい。
BRIDGE_MAX_MS = 20

# 連続する同一マーカーを統合してよい最大の間隔。
MARKER_MERGE_MAX_GAP_MS = 20

# タイムコード行。末尾の align:start position:0% 等は許容する。
TIMECODE_RE = re.compile(
    r"^(\d{1,3}:\d{2}:\d{2}[,.]\d{1,3})\s*-->\s*"
    r"(\d{1,3}:\d{2}:\d{2}[,.]\d{1,3})\s*(?:\S.*)?$"
)

# インラインタグ: <00:01:23,456> / <c> / </c> / <c.colorE5E5E5>
INLINE_TAG_RE = re.compile(
    r"<\d{1,3}:\d{2}:\d{2}[,.]\d{1,3}>"
    r"|</?c(?:\.[^>]*)?>"
)
INLINE_TIME_RE = re.compile(r"<\d{1,3}:\d{2}:\d{2}[,.]\d{1,3}>")

# [音楽] [拍手] [笑い] のような効果音マーカー
MARKER_RE = re.compile(r"^\[[^\[\]\n]+\]$")

# 既定で削除する効果音マーカーのラベル（角括弧の中身。前後の空白は無視して照合）。
# ここに追記するか、--remove-markers で上書きできる。
REMOVE_MARKER_LABELS_DEFAULT = ("音楽",)


class ConversionError(Exception):
    """変換を中止すべき異常。"""


def marker_label(line):
    """行が [ラベル] 形式ならラベル部分（前後空白除去）を返す。違えば None。"""
    if not MARKER_RE.match(line):
        return None
    return line.strip()[1:-1].strip()


def resolve_remove_labels(args):
    """削除対象マーカーのラベル集合を確定する。'[音楽]' でも '音楽' でも受ける。"""
    if args.no_remove_markers:
        return set()
    raw = args.remove_markers
    if raw is None:
        raw = ",".join(REMOVE_MARKER_LABELS_DEFAULT)
    labels = set()
    for tok in raw.split(","):
        tok = tok.strip()
        if tok.startswith("[") and tok.endswith("]"):
            tok = tok[1:-1].strip()
        if tok:
            labels.add(tok)
    return labels


# ── タイムコード ─────────────────────────────────────────────────────────────

def time_to_ms(t: str) -> int:
    h, m, rest = t.split(":")
    s, frac = rest.replace(".", ",").split(",")
    return ((int(h) * 60 + int(m)) * 60 + int(s)) * 1000 + int(frac.ljust(3, "0"))


def ms_to_sbv(value: int) -> str:
    """ミリ秒 -> '1:02:03.456'（SBV 形式: 時の先頭ゼロなし・小数点区切り）"""
    value = max(0, value)
    h, rem = divmod(value, 3600000)
    m, rem = divmod(rem, 60000)
    s, ms = divmod(rem, 1000)
    return "{0}:{1:02d}:{2:02d}.{3:03d}".format(h, m, s, ms)


# ── データ構造 ────────────────────────────────────────────────────────────────

class Cue:
    __slots__ = ("no", "start_ms", "end_ms", "lines", "raw")

    def __init__(self, no, start_ms, end_ms, lines, raw):
        self.no = no
        self.start_ms = start_ms
        self.end_ms = end_ms
        self.lines = lines
        self.raw = raw

    @property
    def duration_ms(self):
        return self.end_ms - self.start_ms

    @property
    def has_inline_timing(self):
        return bool(INLINE_TIME_RE.search(self.raw))


class Block:
    __slots__ = ("start_ms", "end_ms", "lines", "src_no")

    def __init__(self, start_ms, end_ms, lines, src_no):
        self.start_ms = start_ms
        self.end_ms = end_ms
        self.lines = lines
        self.src_no = src_no

    @property
    def text(self):
        return "\n".join(self.lines)


# ── パース ────────────────────────────────────────────────────────────────────

def normalize_lines(text):
    """行頭行末の空白のみ除去し、空行を落とす。本文内部は一切変更しない。"""
    return [ln.strip() for ln in text.splitlines() if ln.strip()]


def parse_srt(text, lenient, warn):
    normalized = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not normalized:
        raise ConversionError("SRT が空です。")

    cues = []
    for block_no, block in enumerate(re.split(r"\n{2,}", normalized), start=1):
        lines = block.splitlines()

        def bad(msg):
            full = "ブロック{0}: {1}".format(block_no, msg)
            if lenient:
                warn(full + "  -> --lenient のためスキップ")
                return None
            detail = "\n".join("    " + ln for ln in lines[:4])
            raise ConversionError(
                full + "\n  該当:\n" + detail
                + "\n  （--lenient を付けると警告してスキップします）"
            )

        if not [ln for ln in lines if ln.strip()]:
            if bad("空のブロックです。") is None:
                continue

        pos = 1 if lines[0].strip().isdigit() else 0
        if pos >= len(lines):
            if bad("タイムコード行がありません。") is None:
                continue

        m = TIMECODE_RE.match(lines[pos].strip())
        if not m:
            if bad("タイムコードを解析できません: {0!r}".format(lines[pos])) is None:
                continue

        start_ms = time_to_ms(m.group(1))
        end_ms = time_to_ms(m.group(2))
        if end_ms < start_ms:
            if bad("終了時刻が開始時刻より前です。") is None:
                continue
        if cues and start_ms < cues[-1].start_ms:
            if bad("開始時刻が直前のブロックより前です（逆順）。") is None:
                continue

        raw_text = "\n".join(lines[pos + 1:])
        cues.append(Cue(block_no, start_ms, end_ms,
                        normalize_lines(INLINE_TAG_RE.sub("", raw_text)),
                        raw_text))

    if not cues:
        raise ConversionError("有効な字幕ブロックが 1 つもありません。")
    return cues


# ── 効果音マーカーの削除 ──────────────────────────────────────────────────────

def strip_markers(cues, remove_labels, info):
    """
    remove_labels に一致するマーカー行（例: [音楽]）をキューから削除する。
    削除の結果そのキューの本文が空になった場合は、キュー（タイムライン）ごと落とす。
    本文が残る場合はマーカー行だけを取り除き、タイムラインは維持する。
    戻り値: (残ったキューのリスト, {"removed": 行数, "dropped": タイムライン数})
    """
    kept = []
    stats = {"removed": 0, "dropped": 0}
    if not remove_labels:
        return cues, stats

    for c in cues:
        new_lines = []
        removed_here = []
        for ln in c.lines:
            lab = marker_label(ln)
            if lab is not None and lab in remove_labels:
                removed_here.append(ln)
            else:
                new_lines.append(ln)

        if not removed_here:
            kept.append(c)
            continue

        stats["removed"] += len(removed_here)
        if new_lines:
            # 本文が残る -> マーカー行だけ削除してタイムラインは維持
            c.lines = new_lines
            info("マーカー行削除 {0}: {1}  (残: {2})".format(
                ms_to_sbv(c.start_ms), " / ".join(removed_here),
                " / ".join(new_lines)))
            kept.append(c)
        else:
            # 本文が空になった -> このタイムラインごと削除
            stats["dropped"] += 1
            info("空タイムライン削除 {0} --> {1}: {2}".format(
                ms_to_sbv(c.start_ms), ms_to_sbv(c.end_ms),
                " / ".join(removed_here)))

    return kept, stats


# ── ローリング重複の除去 ──────────────────────────────────────────────────────

def exact_rolling_overlap(previous, current):
    """直前の表示状態の末尾と現キューの先頭が完全一致する最大行数。"""
    for size in range(min(len(previous), len(current)), 0, -1):
        if previous[-size:] == current[:size]:
            return size
    return 0


def dedupe(cues, preserve_times, strict, warn):
    out = []
    display = []          # 直前キューの表示状態
    stats = {"source": len(cues), "empty": 0, "new": 0,
             "carryover": 0, "ambiguous_kept": 0}

    for cue in cues:
        cur = cue.lines

        # 空キュー = 表示クリア。持ち越し判定の連続性をここで切る。
        if not cur:
            stats["empty"] += 1
            display = []
            continue

        overlap = exact_rolling_overlap(display, cur)
        new_lines = cur[overlap:]

        if new_lines:
            out.append(Block(cue.start_ms, cue.end_ms, new_lines, cue.no))
            stats["new"] += 1
        else:
            # 全行が直前状態からの完全な持ち越し。捨ててよい根拠を確認する。
            is_bridge = (cue.duration_ms <= BRIDGE_MAX_MS
                         and not cue.has_inline_timing)
            is_marker = all(MARKER_RE.match(x) for x in cur)

            if is_bridge or is_marker:
                stats["carryover"] += 1
                # 直前に出力した行がこの持ち越し状態の末尾と一致する時だけ延長。
                if (out and not preserve_times
                        and cur[-len(out[-1].lines):] == out[-1].lines):
                    out[-1].end_ms = max(out[-1].end_ms, cue.end_ms)
            else:
                msg = ("SRT ブロック {0} ({1} / {2}ms): 持ち越しか同一発話の"
                       "繰り返しか断定できません: {3}").format(
                    cue.no, ms_to_sbv(cue.start_ms), cue.duration_ms,
                    " / ".join(cur))
                if strict:
                    raise ConversionError(msg)
                warn(msg + "  -> 削除せず保持しました")
                out.append(Block(cue.start_ms, cue.end_ms, cur, cue.no))
                stats["ambiguous_kept"] += 1

        display = cur

    if not out:
        raise ConversionError("出力可能な字幕本文がありません。")
    return out, stats


def merge_markers(blocks, note):
    """同一の効果音マーカーが極小間隔で連続する場合だけ統合する。"""
    merged = []
    i = 0
    count = 0
    while i < len(blocks):
        cur = blocks[i]
        if len(cur.lines) == 1 and MARKER_RE.match(cur.lines[0]):
            j = i + 1
            end = cur.end_ms
            while (j < len(blocks) and blocks[j].lines == cur.lines
                   and 0 <= blocks[j].start_ms - end <= MARKER_MERGE_MAX_GAP_MS):
                end = blocks[j].end_ms
                j += 1
            if j > i + 1:
                count += j - i - 1
                note("{0} x{1} を統合: {2} -> {3}".format(
                    cur.lines[0], j - i, ms_to_sbv(cur.start_ms), ms_to_sbv(end)))
                cur.end_ms = end
            merged.append(cur)
            i = j
        else:
            merged.append(cur)
            i += 1
    return merged, count


# ── 検証 ──────────────────────────────────────────────────────────────────────

def verify_coverage(cues, blocks):
    """入力に存在した全ての行が出力にも存在するかを確認する。"""
    src_lines = set()
    for c in cues:
        src_lines.update(c.lines)
    out_lines = set()
    for b in blocks:
        out_lines.update(b.lines)
    return sorted(src_lines - out_lines)


def verify_timeline(blocks):
    problems = []
    for a, b in zip(blocks, blocks[1:]):
        if b.start_ms < a.start_ms:
            problems.append("出力時刻が逆順: {0} -> {1}".format(
                ms_to_sbv(a.start_ms), ms_to_sbv(b.start_ms)))
        elif b.start_ms < a.end_ms:
            problems.append("出力時刻が重複: {0} と {1}".format(
                ms_to_sbv(a.start_ms), ms_to_sbv(b.start_ms)))
    return problems


# ── 出力 ──────────────────────────────────────────────────────────────────────

def build_sbv(blocks):
    parts = []
    for b in blocks:
        head = "{0},{1}".format(ms_to_sbv(b.start_ms), ms_to_sbv(b.end_ms))
        parts.append(head + "\n" + b.text)
    return "\n\n".join(parts) + "\n"


# ── メイン ────────────────────────────────────────────────────────────────────

def run(args, dst):
    warnings = []
    infos = []

    def warn(msg):
        warnings.append(msg)

    def info(msg):
        pass
        # infos.append(msg)

    def note(msg):
        if not args.quiet:
            print("  " + msg, file=sys.stderr)

    report = Path(args.report) if args.report else Path(str(dst) + ".audit.txt")

    raw = args.input.read_text(encoding="utf-8-sig")
    cues = parse_srt(raw, args.lenient, warn)
    src_blocks_total = len(cues)   # 削除前の元ブロック数

    # 効果音マーカー（既定: [音楽]）を削除。空になったタイムラインは丸ごと落とす。
    remove_labels = resolve_remove_labels(args)
    cues, marker_stats = strip_markers(cues, remove_labels, info)
    if not cues:
        raise ConversionError(
            "マーカー（{0}）を削除した結果、字幕が 1 つも残りませんでした。".format(
                "、".join("[" + x + "]" for x in sorted(remove_labels))))

    blocks, stats = dedupe(cues, args.preserve_times, args.strict, warn)

    merged = 0
    if not args.no_merge_markers:
        blocks, merged = merge_markers(blocks, note)

    lost = verify_coverage(cues, blocks)
    if lost:
        raise ConversionError(
            "内部検証エラー: 入力にあった {0} 行が出力から失われました。\n  例: {1}".format(
                len(lost), lost[:5]))

    for p in verify_timeline(blocks):
        warn("タイムライン検証: " + p)

    dst.write_text(build_sbv(blocks), encoding="utf-8")

    if not args.quiet:
        chars = sum(len(b.text) for b in blocks)
        kinds = len(set(l for c in cues for l in c.lines))
        print("[完了] {0} -> {1}".format(args.input.name, dst.name))
        print("  元SRTブロック        : {0}".format(src_blocks_total))
        if remove_labels:
            print("  マーカー削除         : {0} 行（{1}）".format(
                marker_stats["removed"],
                "、".join("[" + x + "]" for x in sorted(remove_labels))))
            print("  空タイムライン削除   : {0}".format(marker_stats["dropped"]))
        print("  空ブロック           : {0}".format(stats["empty"]))
        print("  完全一致の持ち越し   : {0}".format(stats["carryover"]))
        print("  マーカー統合         : {0}".format(merged))
        print("  断定できず保持       : {0}".format(stats["ambiguous_kept"]))
        print("  出力SBVブロック      : {0}  (本文 {1:,} 文字)".format(
            len(blocks), chars))
        print("  取りこぼし検証       : OK（入力の全 {0} 種の行が出力に存在）".format(kinds))

    # 監査ログ: 削除したマーカーの明細（情報）と警告を別セクションで記録する。
    sections = []
    if infos:
        sections.append(
            "── 削除した効果音マーカー（{0} 行 / 空タイムライン {1} 個）──\n".format(
                marker_stats["removed"], marker_stats["dropped"])
            + "\n".join(infos))
    if warnings:
        sections.append("── 警告（{0} 件）──\n".format(len(warnings))
                        + "\n".join(warnings))

    if warnings:
        report.write_text("\n\n".join(sections) + "\n", encoding="utf-8")
        print("  [警告] {0} 件 -> {1}".format(len(warnings), report.name),
              file=sys.stderr)
        for w in warnings[:5]:
            print("      " + w, file=sys.stderr)
        if len(warnings) > 5:
            print("      …他 {0} 件".format(len(warnings) - 5), file=sys.stderr)
        return 3

    # 警告なし（終了コード 0）。マーカーを削除した場合は明細を記録して案内する。
    if sections:
        report.write_text("\n\n".join(sections) + "\n", encoding="utf-8")
        if infos and not args.quiet:
            print("  削除ログ             : {0}".format(report.name))
    elif args.report:
        report.write_text("警告なし：全ブロック検証済み\n", encoding="utf-8")
    return 0


def main():
    p = argparse.ArgumentParser(
        description="SRT → SBV 変換（ローリング字幕の重複を完全一致だけで整理）")
    p.add_argument("input", type=Path)
    p.add_argument("output", type=Path, nargs="?")
    p.add_argument("--strict", action="store_true",
                   help="断定できない箇所があれば中止する")
    p.add_argument("--lenient", action="store_true",
                   help="壊れたブロックをエラーにせず警告してスキップ")
    p.add_argument("--preserve-times", action="store_true",
                   help="元のタイムコードをそのまま使う")
    p.add_argument("--remove-markers", metavar="LABELS",
                   help="削除する効果音マーカーをカンマ区切りで指定（既定: 音楽）")
    p.add_argument("--no-remove-markers", action="store_true",
                   help="効果音マーカーを削除しない（従来動作）")
    p.add_argument("--no-merge-markers", action="store_true",
                   help="[拍手] 等の連続マーカーを統合しない")
    p.add_argument("--report", metavar="FILE", help="監査ログの出力先")
    p.add_argument("--quiet", action="store_true")
    args = p.parse_args()

    if not args.input.is_file():
        print("[エラー] ファイルが見つかりません: {0}".format(args.input),
              file=sys.stderr)
        raise SystemExit(1)

    dst = args.output or args.input.with_suffix(".sbv.txt")
    try:
        raise SystemExit(run(args, dst))
    except SystemExit:
        raise
    except ConversionError as exc:
        print("[中止] {0}".format(exc), file=sys.stderr)
        try:
            if dst.exists():
                dst.unlink()      # 書きかけを残さない
        except OSError:
            pass
        raise SystemExit(2 if args.strict else 1)
    except (OSError, UnicodeError, ValueError) as exc:
        print("[エラー] {0}".format(exc), file=sys.stderr)
        try:
            if dst.exists():
                dst.unlink()
        except OSError:
            pass
        raise SystemExit(1)


if __name__ == "__main__":
    main()
