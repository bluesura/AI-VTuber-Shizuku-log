#!/usr/bin/env python3
"""YouTube配信ログから癖・AI語・名言/迷言・物語候補を採掘する前処理スクリプト。

sbv（優先）または srt と live_chat（通常/OCR）を突き合わせ、
1) 通読用 (condensed.txt) と秒確定用 (timeline.txt) を生成
2) info.txt から動画ID・URLを自動取得し、タイムスタンプ付きURL生成を支援
3) AI語・空耳反応を 🟢高確度(3件以上) / 🟡候補(1-2件) で抽出し、直前の外国語フリ有無も確認
4) 連続盛り上がり区間（物語・一連の流れ候補）を自動抽出
"""
from __future__ import annotations

import argparse
import glob
import re
import sys
from collections import Counter
from pathlib import Path

REACT_WORDS = [
    "草", "ｗ", "笑", "泣", "エモ", "すご", "ヤバ", "やば", "マジ", "まじ", "神",
    "かわい", "かわよ", "!?", "！？", "？？", "88", "おめ", "天才", "尊い",
    "たすかる", "助かる", "名言", "迷言", "辛辣", "無慈悲",
]

AI_SLIP_REACT = ["なんて？", "なんて?", "なんて", "AI語", "あき語", "何て", "空耳", "バグ"]
FOREIGN_HINT_RE = re.compile(r"(英語|中国語|中文|韓国語|[A-Za-z]{5,}|[\u4e00-\u9fff]{3,}[？?])")

NOISE_WORDS = [
    "待機", "おつしず", "パンパカ", "ぱんぱか", "お疲れ", "おつかれ",
    "こんばんは", "こんにちは", "こんちわ", "おはよう", "初見", "乙",
]

SBV_TS_RE = re.compile(r"(\d+(?::\d{2})+(?:\.\d+)?),(\d+(?::\d{2})+(?:\.\d+)?)")
SRT_TS_RE = re.compile(r"(\d+(?::\d{2})+(?:[.,]\d+)?)\s*-->\s*(\d+(?::\d{2})+(?:[.,]\d+)?)")
CHAT_RE = re.compile(r"\s*\[(-?\d+(?::\d{2})+)\]\s*@?\s*(.+?)\s*[:：]\s*(.*)")


def to_sec(ts: str) -> int:
    neg = ts.startswith("-")
    s = 0
    for p in ts.lstrip("-").replace(",", ".").split(":"):
        s = s * 60 + int(float(p))
    return -s if neg else s


def fmt(sec: int) -> str:
    h, r = divmod(abs(sec), 3600)
    m, s = divmod(r, 60)
    sign = "-" if sec < 0 else ""
    return f"{sign}{h}:{m:02d}:{s:02d}" if h else f"{sign}{m:02d}:{s:02d}"


def find_files(base_dir: Path, pattern: str, video_id: str | None) -> list[Path]:
    paths = sorted(Path(p) for p in glob.glob(str(base_dir / pattern)))
    if video_id:
        matched = [p for p in paths if video_id in p.name]
        if matched:
            return matched
    return paths


def parse_info(paths: list[Path]) -> tuple[str | None, str | None, str | None]:
    for p in paths:
        text = p.read_text(encoding="utf-8-sig", errors="replace")
        vid = re.search(r"^動画ID\s*:\s*(\S+)", text, re.M)
        url = re.search(r"^URL\s*:\s*(\S+)", text, re.M)
        title = re.search(r"^タイトル\s*:\s*(.+)$", text, re.M)
        return (
            vid.group(1).strip() if vid else None,
            url.group(1).strip() if url else None,
            title.group(1).strip() if title else None,
        )
    return None, None, None


def parse_sbv(paths: list[Path]) -> list[tuple[int, str]]:
    entries: list[tuple[int, str]] = []
    for path in paths:
        with path.open(encoding="utf-8-sig", errors="replace") as f:
            lines = f.read().replace("\r", "").splitlines()
        i, n = 0, len(lines)
        while i < n:
            m = SBV_TS_RE.fullmatch(lines[i].strip())
            if m:
                start_sec = to_sec(m.group(1))
                i += 1
                parts = []
                while i < n and lines[i].strip() and not SBV_TS_RE.fullmatch(lines[i].strip()):
                    parts.append(lines[i].strip())
                    i += 1
                joined = " ".join(parts).strip()
                if joined:
                    entries.append((start_sec, joined))
            else:
                i += 1
    entries.sort(key=lambda x: x[0])
    return entries


def parse_srt(paths: list[Path]) -> list[tuple[int, str]]:
    entries: list[tuple[int, str]] = []
    for path in paths:
        with path.open(encoding="utf-8-sig", errors="replace") as f:
            lines = f.read().replace("\r", "").splitlines()
        i, n = 0, len(lines)
        while i < n:
            m = SRT_TS_RE.fullmatch(lines[i].strip())
            if m:
                start_sec = to_sec(m.group(1))
                i += 1
                parts = []
                while i < n and lines[i].strip() and not SRT_TS_RE.fullmatch(lines[i].strip()):
                    parts.append(lines[i].strip())
                    i += 1
                joined = " ".join(parts).strip()
                if joined:
                    entries.append((start_sec, joined))
            else:
                i += 1
    entries.sort(key=lambda x: x[0])
    return entries


def parse_chat(paths: list[Path]) -> tuple[list[tuple[int, str, str]], int]:
    chat: list[tuple[int, str, str]] = []
    unparsed = 0
    for path in paths:
        with path.open(encoding="utf-8-sig", errors="replace") as f:
            for raw in f:
                line = raw.replace("\r", "").rstrip("\n")
                if not line.strip() or line.lstrip().startswith("#"):
                    continue
                m = CHAT_RE.match(line)
                if m:
                    chat.append((to_sec(m.group(1)), "@" + m.group(2), m.group(3).strip()))
                else:
                    unparsed += 1
    chat.sort(key=lambda x: x[0])
    return chat, unparsed


def resolve_input_dir(arg_dir: str | None) -> Path:
    if arg_dir:
        return Path(arg_dir).expanduser().resolve()
    default_cloud = Path("/mnt/user-data/uploads")
    return default_cloud if default_cloud.is_dir() else Path.cwd()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input_dir", nargs="?", help="入力ディレクトリ")
    parser.add_argument("--video-id", help="動画ID（混在防止）")
    parser.add_argument("--out-dir", default="/tmp", help="出力先（既定: /tmp）")
    args = parser.parse_args()

    base_dir = resolve_input_dir(args.input_dir)
    out_dir = Path(args.out_dir).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    info_paths = find_files(base_dir, "*info*.txt", args.video_id)
    vid_info, url_info, title_info = parse_info(info_paths)
    video_id = args.video_id or vid_info
    base_url = url_info or (f"https://www.youtube.com/watch?v={video_id}" if video_id else None)

    sbv_paths = find_files(base_dir, "*sbv*.txt", video_id)
    sub_format = "SBV"
    subs = parse_sbv(sbv_paths)
    if not subs:
        srt_paths = sorted(set(find_files(base_dir, "*.srt", video_id)) | set(find_files(base_dir, "*srt*.txt", video_id)))
        if srt_paths:
            subs = parse_srt(srt_paths)
            sub_format = "SRT (フォールバック)"

    if not subs:
        print(f"ERROR: 字幕（sbv/srt）が見つかりません: {base_dir}", file=sys.stderr)
        return 1

    cand = sorted(set(find_files(base_dir, "*live_chat*.txt", video_id)) | set(find_files(base_dir, "*chat*ocr*.txt", video_id)))
    ocr_paths = [p for p in cand if "ocr" in p.name.lower()]
    raw_paths = [p for p in cand if p not in ocr_paths]
    use_paths = raw_paths or ocr_paths
    ocr_mode = bool(ocr_paths) and not raw_paths

    chat, _ = parse_chat(use_paths)
    if ocr_mode and chat:
        seen, ded = {}, []
        for t, u, c in chat:
            k = (u, c)
            if k in seen and t - seen[k] <= 90:
                seen[k] = t
                continue
            seen[k] = t
            ded.append((t, u, c))
        chat = ded

    pad_b, pad_a, bucket, win = (20, 60, 60, 30) if ocr_mode else (15, 30, 30, 20)

    timeline_path = out_dir / "timeline.txt"
    with timeline_path.open("w", encoding="utf-8") as f:
        for t, text in subs:
            near = [c for ct, _, c in chat if t - pad_b <= ct <= t + pad_a]
            f.write(f"[{fmt(t)}] SUB: {text}\n")
            for c in near[:6]:
                f.write(f"          chat: {c}\n")

    condensed_path = out_dir / "condensed.txt"
    min_t = min([subs[0][0]] + [ct for ct, _, _ in chat]) if chat else subs[0][0]
    t_start = (min_t // win) * win if min_t < 0 else 0
    t_end = subs[-1][0] + win
    with condensed_path.open("w", encoding="utf-8") as f:
        t = t_start
        while t < t_end:
            txt = "".join(x for s, x in subs if t <= s < t + win)
            cs = [c for ct, _, c in chat if t <= ct < t + win]
            if txt.strip() or cs:
                f.write(f"[{fmt(t)}] {txt}\n")
                if cs:
                    f.write("   >> " + " / ".join(cs[:10]) + "\n")
            t += win

    print("== 採掘準備完了 ==")
    print(f"  タイトル: {title_info or '(不明)'}")
    print(f"  ベースURL: {base_url or '(不明)'}")
    print(f"  字幕: {sub_format} {len(subs)}件 (最終 {fmt(subs[-1][0])}) / chat: {len(chat)}件" + (" [OCRモード]" if ocr_mode else ""))
    print(f"  出力: {condensed_path} / {timeline_path}")

    # 1) AI語・空耳反応バケット（🟢高確度 >=3件 / 🟡候補 1-2件）
    slip_buckets: dict[int, set[str]] = {}
    for t, u, c in chat:
        if t >= 0 and any(k in c for k in AI_SLIP_REACT):
            slip_buckets.setdefault(t // bucket, set()).add(u)

    if slip_buckets:
        print("\n== AI語・空耳反応スパイク（🟢高確度=3人以上 / 🟡候補=1-2人） ==")
        ranked = sorted(slip_buckets.items(), key=lambda kv: -len(kv[1]))[:20]
        for b, users in sorted(ranked):
            cnt = len(users)
            tier = "🟢高確度" if cnt >= 3 else "🟡候補  "
            ts = b * bucket
            prev = [s for s in subs if ts - 15 <= s[0] <= ts + bucket]
            sample = prev[0][1][:40] if prev else "(字幕該当なし)"
            foreign_pre = [c for ct, _, c in chat if ts - 45 <= ct <= ts + 15 and FOREIGN_HINT_RE.search(c)]
            note = " [※直前に他言語・質問あり]" if foreign_pre else ""
            link = f"{base_url}&t={ts}s" if base_url else fmt(ts)
            print(f"  {tier} [{fmt(ts)}] users={cnt} | {sample}{note} | {link}")

    # 2) 盛り上がり連続区間（物語・一連の流れ候補）
    hot_buckets: dict[int, list[int]] = {}
    for t, _, c in chat:
        if t < 0 or any(k in c for k in NOISE_WORDS):
            continue
        b = t // bucket
        hit = sum(1 for k in REACT_WORDS if k in c)
        d = hot_buckets.setdefault(b, [0, 0])
        d[0] += 1
        d[1] += hit
    print("\n== ハイライト・物語候補区間（上位20） ==")
    top_hot = sorted(hot_buckets.items(), key=lambda kv: (-kv[1][1], -kv[1][0]))[:20]
    for b, (n, r) in sorted(top_hot):
        ts = b * bucket
        prev = [s for s in subs if s[0] <= ts + bucket]
        line = prev[-1][1][:40] if prev else "(字幕該当なし)"
        link = f"{base_url}&t={ts}s" if base_url else fmt(ts)
        print(f"  [{fmt(ts)}] chat={n} react={r} | {line} | {link}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
