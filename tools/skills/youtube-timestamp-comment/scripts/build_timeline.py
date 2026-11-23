#!/usr/bin/env python3
"""YouTube配信ログ（sbv / srtフォールバック / live_chat / live_chat_ocr）前処理スクリプト。

分割された字幕（sbv優先、無ければsrt）とライブチャットを突き合わせ、
1) 通読用タイムライン (condensed.txt)
2) 秒単位時刻確定用タイムライン (timeline.txt)
3) 運営#コメント・コーナー切れ目候補・チャット反応スパイク
を出力する。
"""
from __future__ import annotations

import argparse
import glob
import re
import sys
from collections import Counter
from pathlib import Path

# 盛り上がりの指標になる語
DEFAULT_REACT = [
    "草", "ｗ", "笑", "泣", "エモ", "すご", "ヤバ", "やば", "マジ", "まじ", "神",
    "かわい", "かわよ", "!?", "！？", "？？", "88", "おめ", "天才", "尊い", "惜し",
    "正解", "不正解", "www", "たすかる", "助かる", "へぇ", "ひゅー", "ヒュー", "えぇ",
]

# 挨拶・定型句はシーンとしては無価値なのでスパイク検出から除外する
DEFAULT_NOISE = [
    "待機", "おつしず", "パンパカ", "ぱんぱか", "お疲れ", "おつかれ",
    "こんばんは", "こんにちは", "こんちわ", "おはよう", "初見", "乙",
]

# コーナーの切れ目を示す配信者の定型句
DEFAULT_CORNER = [
    "コメントで教えて", "コメントで自慢", "コメントしてください", "ここで1つ",
    "ではこう聞きましょう", "質問です", "コーナー", "でいきますよ", "1つに絞る",
    "お知らせ", "次は", "いってみましょう",
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
    """60分未満は MM:SS（2桁ゼロ埋め）、60分以上は H:MM:SS。"""
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


def parse_sbv(paths: list[Path]) -> list[tuple[int, str]]:
    """SBV標準形式をパースする。1エントリが複数行にまたがる場合も連結して保持する。"""
    entries: list[tuple[int, str]] = []
    for path in paths:
        with path.open(encoding="utf-8-sig", errors="replace") as f:
            lines = f.read().replace("\r", "").splitlines()
        i = 0
        n = len(lines)
        while i < n:
            line = lines[i].strip()
            m = SBV_TS_RE.fullmatch(line)
            if m:
                start_sec = to_sec(m.group(1))
                i += 1
                text_parts: list[str] = []
                while i < n and lines[i].strip():
                    if SBV_TS_RE.fullmatch(lines[i].strip()):
                        break
                    text_parts.append(lines[i].strip())
                    i += 1
                joined = " ".join(text_parts).strip()
                if joined:
                    entries.append((start_sec, joined))
            else:
                i += 1
    entries.sort(key=lambda x: x[0])
    return entries


def parse_srt(paths: list[Path]) -> list[tuple[int, str]]:
    """SRT形式をフォールバックとしてパースする（sbvが無い場合のみ使用）。"""
    entries: list[tuple[int, str]] = []
    for path in paths:
        with path.open(encoding="utf-8-sig", errors="replace") as f:
            lines = f.read().replace("\r", "").splitlines()
        i = 0
        n = len(lines)
        while i < n:
            line = lines[i].strip()
            m = SRT_TS_RE.fullmatch(line)
            if m:
                start_sec = to_sec(m.group(1))
                i += 1
                text_parts: list[str] = []
                while i < n and lines[i].strip():
                    if SRT_TS_RE.fullmatch(lines[i].strip()):
                        break
                    text_parts.append(lines[i].strip())
                    i += 1
                joined = " ".join(text_parts).strip()
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
    if default_cloud.is_dir():
        return default_cloud
    return Path.cwd()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input_dir", nargs="?", help="入力ファイルのあるディレクトリ（省略時は /mnt/user-data/uploads またはカレントディレクトリ）")
    parser.add_argument("--video-id", help="対象の動画ID（同一フォルダに複数動画のログがある場合に混在を防ぐ）")
    parser.add_argument("--out-dir", default="/tmp", help="condensed.txt / timeline.txt の出力先（既定: /tmp）")
    parser.add_argument("--noise", default="", help="追加で除外する挨拶・定型句（カンマ区切り）")
    parser.add_argument("--corner", default="", help="追加で検出するコーナー定型句（カンマ区切り）")
    args = parser.parse_args()

    base_dir = resolve_input_dir(args.input_dir)
    out_dir = Path(args.out_dir).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    noise_words = DEFAULT_NOISE + [w.strip() for w in args.noise.split(",") if w.strip()]
    corner_words = DEFAULT_CORNER + [w.strip() for w in args.corner.split(",") if w.strip()]

    # ---- sbv（優先） / srt（フォールバック） ----
    sbv_paths = find_files(base_dir, "*sbv*.txt", args.video_id)
    sub_format = "SBV"
    sub_paths = sbv_paths
    sbv = parse_sbv(sbv_paths)

    if not sbv:
        srt_paths = sorted(
            set(find_files(base_dir, "*.srt", args.video_id))
            | set(find_files(base_dir, "*srt*.txt", args.video_id))
        )
        if srt_paths:
            sbv = parse_srt(srt_paths)
            sub_format = "SRT (フォールバック)"
            sub_paths = srt_paths

    # ---- live_chat（通常版 / OCR復元版）----
    cand = sorted(
        set(find_files(base_dir, "*live_chat*.txt", args.video_id))
        | set(find_files(base_dir, "*chat*ocr*.txt", args.video_id))
    )
    ocr_paths = [p for p in cand if "ocr" in p.name.lower()]
    raw_paths = [p for p in cand if p not in ocr_paths]
    use_paths = raw_paths or ocr_paths
    ocr_mode = bool(ocr_paths) and not raw_paths

    chat, unparsed = parse_chat(use_paths)

    # ---- OCR: 連続フレームで重複取得された同一コメントを畳む ----
    raw_ts = sorted({t for t, _, _ in chat})
    dup = 0
    if ocr_mode and chat:
        seen: dict[tuple[str, str], int] = {}
        ded: list[tuple[int, str, str]] = []
        for t, u, c in chat:
            k = (u, c)
            if k in seen and t - seen[k] <= 90:
                seen[k] = t
                dup += 1
                continue
            seen[k] = t
            ded.append((t, u, c))
        chat = ded

    # ---- 検証: ここで止まったら先に進まない ----
    if not sbv:
        print(
            f"ERROR: sbv / srt のパースに失敗（0件）。入力ディレクトリ: {base_dir}"
            + (f" / video_id={args.video_id}" if args.video_id else ""),
            file=sys.stderr,
        )
        return 1

    print(f"== 読み込み結果 ({base_dir}) ==")
    print(f"  字幕形式: {sub_format} / ファイル: {', '.join(p.name for p in sub_paths)}")
    print(f"  字幕: {len(sbv)}件 / 最終 {fmt(sbv[-1][0])}")
    print(
        f"  chat: {len(chat)}件"
        + (f" (重複除去 {dup}件)" if dup else "")
        + (f" / 未パース {unparsed}行" if unparsed else "")
    )
    if raw_paths and ocr_paths:
        print("  !! 通常版とOCR版の live_chat が両方あるため、通常版のみを使用した")

    if ocr_mode:
        step = Counter(b - a for a, b in zip(raw_ts, raw_ts[1:])).most_common(1)
        gran = step[0][0] if step else 0
        print(
            f"\n== !! OCR復元チャットモード（タイムスタンプ刻み: 約{gran}秒） !!\n"
            f"  - チャット時刻は丸め済みの概算。出力の時刻は必ず字幕側で確定すること\n"
            f"  - 画面に写った分しか拾えないため件数は実際より少なく、上限で頭打ちになる\n"
            f"  - OCR誤読があるため、チャット文字列を固有名詞の裏取りに使わない"
        )
        pad_b, pad_a, bucket, win = 20, 60, 60, 30
    else:
        pad_b, pad_a, bucket, win = 15, 30, 30, 20

    # ---- 1) 精密タイムライン（最終的な時刻確定用。grepして使う）----
    timeline_path = out_dir / "timeline.txt"
    with timeline_path.open("w", encoding="utf-8") as f:
        for t, text in sbv:
            near = [c for ct, _, c in chat if t - pad_b <= ct <= t + pad_a]
            f.write(f"[{fmt(t)}] SBV: {text}\n")
            for c in near[:6]:
                f.write(f"          chat: {c}\n")

    # ---- 2) 集約タイムライン（通読用。開始前の負の時刻も含む）----
    condensed_path = out_dir / "condensed.txt"
    min_t = min([sbv[0][0]] + [ct for ct, _, _ in chat]) if chat else sbv[0][0]
    t_start = (min_t // win) * win if min_t < 0 else 0
    t_end = sbv[-1][0] + win
    with condensed_path.open("w", encoding="utf-8") as f:
        t = t_start
        while t < t_end:
            txt = "".join(x for s, x in sbv if t <= s < t + win)
            cs = [c for ct, _, c in chat if t <= ct < t + win]
            if txt.strip() or cs:
                f.write(f"[{fmt(t)}] {txt}\n")
                if cs:
                    f.write("   >> " + " / ".join(cs[:10]) + "\n")
            t += win

    print(f"  出力: {condensed_path} / {timeline_path}")

    # ---- 3) 運営候補（# コメントを多く投稿しているアカウント）----
    hashers = Counter(u for _, u, c in chat if c.startswith("#"))
    print("\n== # コメント投稿数（上位＝運営候補。名前は内部判断のみに使う） ==")
    if not hashers:
        print(
            "  なし（コマンド未使用の配信。字幕発言のみを起点にする）"
            + ("／OCRでは先頭記号が脱落することがあるため、info の概要欄にコマンド説明があれば0件と断定しない" if ocr_mode else "")
        )
    for u, n in hashers.most_common(5):
        print(f"  {u}: {n}")

    top = hashers.most_common(1)[0][0] if hashers else None
    if top:
        print("\n== 運営 # コメント（進行の節目） ==")
        for t, u, c in chat:
            if u == top and c.startswith("#"):
                print(f"  [{fmt(t)}] {c}")

    # ---- 4) コーナー検出（配信者の定型句から構成を割り出す）----
    print("\n== コーナーの切れ目候補 ==")
    for t, text in sbv:
        if any(k in text for k in corner_words):
            print(f"  [{fmt(t)}] {text[:45]}")

    # ---- 5) チャットが沸いた区間 上位30（＝ハイライト候補）----
    buckets: dict[int, list[int]] = {}
    for t, _, c in chat:
        if t < 0 or any(k in c for k in noise_words):
            continue
        b = t // bucket
        hit = sum(1 for k in DEFAULT_REACT if k in c)
        d = buckets.setdefault(b, [0, 0])
        d[0] += 1
        d[1] += hit
    hot = sorted(buckets.items(), key=lambda kv: (-kv[1][1], -kv[1][0]))[:30]
    print(f"\n== チャット反応スパイク（{bucket}秒単位 / 件数 / リアクション語数 / 直前のSBV発言） ==")
    if ocr_mode:
        print("  ※件数は画面写り込み分のみ。件数の多寡ではなくリアクション語の中身で判断する")
    for b, (n, r) in sorted(hot):
        t = b * bucket
        prev = [s for s in sbv if s[0] <= t + bucket]
        line = prev[-1][1][:40] if prev else "(SBV該当なし)"
        print(f"  [{fmt(t)}] chat={n} react={r} | {line}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
