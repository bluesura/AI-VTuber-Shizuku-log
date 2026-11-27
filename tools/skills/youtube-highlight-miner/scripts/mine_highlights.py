#!/usr/bin/env python3
"""YouTube配信ログから癖・AI語・名言/迷言・物語候補を採掘する前処理スクリプト。

sbv（優先）または srt、画面OCR（screen-ocr.txt）と live_chat（通常/OCR）を突き合わせ、
1) 通読・時刻照合用 timeline.txt とOCR根拠索引を生成
2) info.txt から動画ID・URLを自動取得し、タイムスタンプ付きURL生成を支援
3) AI語・空耳反応を 🟢高確度(3件以上) / 🟡候補(1-2件) で抽出し、直前の外国語フリ有無も確認
4) 連続盛り上がり区間（物語・一連の流れ候補）を自動抽出
"""
from __future__ import annotations

import argparse
import json
import tempfile
from collections import Counter
import re
import sys
from pathlib import Path

from ocr_observations import group_observations, milliseconds, read_observations, verified_manifests

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
    paths = sorted(p for p in base_dir.glob(pattern) if p.is_file())
    if video_id:
        matched = [p for p in paths if video_id in p.name]
        if matched:
            return matched
        # 元のファイル名を失った添付データは引き続き受け付ける。
        return [p for p in paths if not re.match(r"^[A-Za-z0-9_-]{11}\.", p.name)]
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
                start_ms = milliseconds(m.group(1))
                i += 1
                parts = []
                while i < n and lines[i].strip() and not SBV_TS_RE.fullmatch(lines[i].strip()):
                    parts.append(lines[i].strip())
                    i += 1
                joined = " ".join(parts).strip()
                if joined:
                    entries.append((start_ms, joined))
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
                start_ms = milliseconds(m.group(1))
                i += 1
                parts = []
                while i < n and lines[i].strip() and not SRT_TS_RE.fullmatch(lines[i].strip()):
                    parts.append(lines[i].strip())
                    i += 1
                joined = " ".join(parts).strip()
                if joined:
                    entries.append((start_ms, joined))
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


def fmt_ms(ms):
    seconds, fraction = divmod(ms, 1000)
    return f"{fmt(seconds)}.{fraction:03}" if fraction else fmt(seconds)


def write_timeline(path, video_id, base_url, subtitles, sub_format, groups, chat, window):
    events = [(ms, f"SUB {text}") for ms, text in subtitles]
    for group in groups:
        observations = group["observations"]
        first, last = observations[0]["ms"], observations[-1]["ms"]
        notes = []
        if len(observations) > 1:
            label = "周回" if group["cycle"] else "連続表示"
            notes.append(f"{label}×{len(observations)} ～{fmt_ms(last)}")
        if group["replay_candidate"]:
            notes.append("再表示候補")
        if group["review"]:
            notes.append("要確認")
        suffix = " [" + "／".join(notes) + "]" if notes else ""
        events.append((first, f"{group['id']} {group['text']}{suffix}"))

    chat_counts = Counter()
    for seconds, _, text in chat:
        slot = seconds // window
        if chat_counts[slot] < 10:
            events.append((seconds * 1000, f"CHAT {text}"))
            chat_counts[slot] += 1

    with path.open("w", encoding="utf-8", newline="\n") as stream:
        stream.write(f"# 動画ID: {video_id or '不明'}\n# URL: {base_url or '不明'}\n"
                     f"# SUB={sub_format or 'なし'} / O番号=画面OCR（表示時刻） / CHAT=文脈用\n"
                     "# O番号の元ファイル・行・確認フレームは ocr-evidence.json。再表示回数は発話回数ではない。\n")
        for ms, text in sorted(events, key=lambda row: row[0]):
            stream.write(f"[{fmt_ms(ms)}] {text}\n")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input_dir", nargs="?", help="入力ディレクトリ")
    parser.add_argument("--video-id", help="動画ID（混在防止）")
    parser.add_argument("--out-dir", type=Path, help="派生出力先（既定: 新規の一時フォルダ）")
    evidence = parser.add_mutually_exclusive_group()
    evidence.add_argument("--frames", action="append", type=Path, help="照合用frames.jsonlを動画時刻順に複数指定可")
    evidence.add_argument("--no-frames", action="store_true", help="フレームを使わず、再表示候補を保持する")
    args = parser.parse_args(argv)

    base_dir = resolve_input_dir(args.input_dir)

    info_paths = find_files(base_dir, "*info*.txt", args.video_id)
    vid_info, url_info, title_info = parse_info(info_paths)
    video_id = args.video_id or vid_info
    if video_id and not re.fullmatch(r"[A-Za-z0-9_-]{11}", video_id):
        parser.error("動画IDは11文字のYouTube IDを指定してください。")
    if args.video_id and vid_info and args.video_id != vid_info:
        parser.error("指定した動画IDと動画情報が一致しません。")
    base_url = url_info or (f"https://www.youtube.com/watch?v={video_id}" if video_id else None)

    sbv_paths = find_files(base_dir, "*sbv*.txt", video_id)
    sub_format = "SBV"
    subs = parse_sbv(sbv_paths)
    if not subs:
        srt_paths = sorted(set(find_files(base_dir, "*.srt", video_id)) | set(find_files(base_dir, "*srt*.txt", video_id)))
        if srt_paths:
            subs = parse_srt(srt_paths)
            sub_format = "SRT (フォールバック)"

    screen_ocr_paths = find_files(base_dir, "*screen-ocr*.txt", video_id)
    observations = read_observations(screen_ocr_paths)
    manifests = args.frames or []
    if not manifests and not args.no_frames and video_id and len(screen_ocr_paths) == 1:
        repo = Path(__file__).resolve().parents[4]
        try:
            manifests = verified_manifests(repo / "outputs/shizuku-screen-ocr" / video_id,
                                           video_id, screen_ocr_paths[0])
        except (OSError, ValueError, KeyError) as exc:
            print(f"画面OCRの完了記録を利用できません: {exc}", file=sys.stderr)
    try:
        groups = group_observations(observations, manifests)
    except (OSError, ValueError, TypeError, KeyError) as exc:
        if args.frames:
            parser.error(str(exc))
        print(f"画面OCRのフレームを照合できません。本文は保持します: {exc}", file=sys.stderr)
        manifests = []
        groups = group_observations(observations)

    if not subs and not groups:
        print(f"ERROR: 字幕（sbv/srt/screen-ocr）が見つかりません: {base_dir}", file=sys.stderr)
        return 1
    if not subs:
        sub_format = None

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

    bucket, window = (60, 30) if ocr_mode else (30, 20)
    if args.out_dir:
        out_dir = args.out_dir.expanduser().resolve()
        if out_dir.is_relative_to(base_dir):
            parser.error("出力先は入力ディレクトリの外に指定してください。")
        out_dir.mkdir(parents=True, exist_ok=True)
    else:
        out_dir = Path(tempfile.mkdtemp(prefix="shizuku-highlights-"))
    timeline_path = out_dir / "timeline.txt"
    evidence_path = out_dir / "ocr-evidence.json"
    write_timeline(timeline_path, video_id, base_url, subs, sub_format, groups, chat, window)
    with evidence_path.open("w", encoding="utf-8", newline="\n") as stream:
        json.dump({"video_id": video_id, "items": {
            group["id"]: {k: v for k, v in group.items() if k not in {"id", "text"}}
            for group in groups
        }}, stream, ensure_ascii=False, separators=(",", ":"))
        stream.write("\n")

    print(f"タイトル: {title_info or '不明'} / 動画ID: {video_id or '不明'}")
    print(f"音声字幕 {len(subs)}件 / 画面OCR {len(observations)}観測から{len(groups)}行を構成 / フレーム記録 {len(manifests)}区間")
    print(f"通読・照合: {timeline_path} / OCR根拠: {evidence_path}")
    subs = ([(ms // 1000, text) for ms, text in subs] if subs else
            [(group["observations"][0]["ms"] // 1000, group["text"]) for group in groups])

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
            print(f"  {tier} [{fmt(ts)}] users={cnt} | {sample}{note}")

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
        print(f"  [{fmt(ts)}] chat={n} react={r} | {line}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
