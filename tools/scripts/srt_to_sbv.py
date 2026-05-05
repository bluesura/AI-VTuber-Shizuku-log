#!/usr/bin/env python3
"""
SRT (SubRip) → SBV (SubViewer / YouTube) 変換スクリプト

使い方:
  python srt_to_sbv.py input.srt              # → input.sbv を生成
  python srt_to_sbv.py input.srt output.sbv   # → 出力先を指定
"""

import re
import sys
from pathlib import Path


# ── タイムコード変換 ──────────────────────────────────────────────────────────
# SRT : HH:MM:SS,mmm  →  SBV : H:MM:SS.mmm  (先頭ゼロ除去・カンマ→ピリオド)

def srt_time_to_sbv(t: str) -> str:
    """'01:02:03,456'  →  '1:02:03.456'"""
    t = t.replace(",", ".")          # ミリ秒区切りをピリオドに
    h, m, rest = t.split(":")
    return f"{int(h)}:{m}:{rest}"    # 時間の先頭ゼロを除去


def parse_timecode_line(line: str) -> tuple[str, str]:
    """
    '00:00:01,000 --> 00:00:04,000 align:start position:0%'
    → ('00:00:01,000', '00:00:04,000')  ※ SRT形式のまま返す
    """
    pattern = r"(\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2},\d{3})"
    m = re.match(pattern, line.strip())
    if not m:
        raise ValueError(f"タイムコード行を解析できません: {line!r}")
    return m.group(1), m.group(2)


def format_sbv_timecode(start_srt: str, end_srt: str) -> str:
    """SRT形式の start/end → SBV形式の '0:00:01.000,0:00:04.000'"""
    return f"{srt_time_to_sbv(start_srt)},{srt_time_to_sbv(end_srt)}"


# ── インラインタグ除去 ────────────────────────────────────────────────────────
# YouTube 自動生成字幕などに含まれるカラオケタイミングタグを除去する。
#   例: <00:06:56,280>  <c>  </c>

_INLINE_TAG_RE = re.compile(
    r"<\d{2}:\d{2}:\d{2}[,\.]\d{3}>"   # タイムスタンプタグ  <HH:MM:SS,mmm>
    r"|</?c>"                            # カラオケタグ        <c> / </c>
)

def strip_inline_tags(text: str) -> str:
    """字幕テキストからインラインタイミングタグを取り除く。"""
    return _INLINE_TAG_RE.sub("", text)


# ── SRT パーサー ──────────────────────────────────────────────────────────────

def parse_srt(text: str) -> list[dict]:
    """SRT テキストを字幕ブロックのリストに変換する。"""
    blocks = re.split(r"\n{2,}", text.strip())
    subtitles = []

    for block in blocks:
        lines = block.strip().splitlines()
        if len(lines) < 2:
            continue

        tc_line_idx = 0
        if re.match(r"^\d+$", lines[0].strip()):
            tc_line_idx = 1

        if tc_line_idx >= len(lines):
            continue

        timecode_raw = lines[tc_line_idx]
        text_lines   = lines[tc_line_idx + 1:]

        if "-->" not in timecode_raw:
            continue

        start_srt, end_srt = parse_timecode_line(timecode_raw)
        cleaned_text = strip_inline_tags("\n".join(text_lines))

        subtitles.append({
            "start": start_srt,
            "end":   end_srt,
            "text":  cleaned_text,
        })

    return subtitles


# ── クリーニング処理 ──────────────────────────────────────────────────────────

def is_empty(sub: dict) -> bool:
    """テキストが空白のみのブロックか判定する。"""
    return sub["text"].strip() == ""


def is_music_only(sub: dict) -> bool:
    """テキストが [音楽] のみのブロックか判定する。"""
    return sub["text"].strip() == "[音楽]"


def clean_subtitles(subtitles: list[dict]) -> list[dict]:
    """
    2つのクリーニング処理を適用する：
    1. 空ブロック（テキストが空白のみ）を除去する
    2. 連続する [音楽] ブロックを1つに統合する（開始〜末尾の終了タイムを使用）
    """
    # ステップ1：空ブロック除去
    subtitles = [s for s in subtitles if not is_empty(s)]

    # ステップ2：連続 [音楽] ブロックを統合
    merged: list[dict] = []
    i = 0
    while i < len(subtitles):
        if is_music_only(subtitles[i]):
            # 連続する [音楽] ブロックをまとめて探す
            j = i + 1
            while j < len(subtitles) and is_music_only(subtitles[j]):
                j += 1
            # i〜j-1 を1ブロックに統合
            merged.append({
                "start": subtitles[i]["start"],
                "end":   subtitles[j - 1]["end"],
                "text":  "[音楽]",
            })
            if j > i + 1:
                print(f"  🎵 [音楽] ×{j - i} ブロックを統合: "
                      f"{subtitles[i]['start']} → {subtitles[j-1]['end']}",
                      file=sys.stderr)
            i = j
        else:
            merged.append(subtitles[i])
            i += 1

    return merged


# ── SBV 生成 ─────────────────────────────────────────────────────────────────

def build_sbv(subtitles: list[dict]) -> str:
    """字幕リストから SBV テキストを組み立てる。"""
    blocks = []
    for sub in subtitles:
        tc  = format_sbv_timecode(sub["start"], sub["end"])
        txt = sub["text"]
        blocks.append(f"{tc}\n{txt}")
    return "\n\n".join(blocks) + "\n"


# ── メイン ────────────────────────────────────────────────────────────────────

def convert(src: Path, dst: Path) -> None:
    raw = src.read_text(encoding="utf-8-sig")   # BOM 付き UTF-8 にも対応
    subtitles = parse_srt(raw)

    before = len(subtitles)
    subtitles = clean_subtitles(subtitles)
    after = len(subtitles)

    if not subtitles:
        print("⚠️  字幕ブロックが見つかりませんでした。", file=sys.stderr)
        sys.exit(1)

    sbv_text = build_sbv(subtitles)
    dst.write_text(sbv_text, encoding="utf-8")
    print(f"✅  変換完了: {src}  →  {dst}  "
          f"({before} → {after} ブロック、{before - after} 件削減)")


def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(0)

    src = Path(sys.argv[1])
    if not src.exists():
        print(f"❌  ファイルが見つかりません: {src}", file=sys.stderr)
        sys.exit(1)

    dst = Path(sys.argv[2]) if len(sys.argv) >= 3 else src.with_suffix(".sbv")
    convert(src, dst)


if __name__ == "__main__":
    main()
