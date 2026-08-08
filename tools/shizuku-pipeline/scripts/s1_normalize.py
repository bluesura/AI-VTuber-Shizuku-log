# -*- coding: utf-8 -*-
"""ステップ1: 決定的正規化（LLM不使用）。
使い方:
  python scripts/s1_normalize.py --all            # 未処理の配信を日付順に全部 + Xログ
  python scripts/s1_normalize.py --stream <vid>   # 1配信だけ
出力（配信ごと data/normalized/streams/{vid}/）:
  sentences.tsv  … t秒 / 時刻 / URL / asr(辞書補正前) / norm(補正後)
  chat.tsv       … t秒 / 時刻 / ユーザー / 本文（原文のまま・補正しない）
  signals.json   … バースト / 字幕欠落×チャット密集(ミスマッチ) / 語彙群 / 事後コメントの時刻 / 概要欄の新規行
  meta.json      … タイトル・日付・件数・辞書適用数など
出力（X）: data/normalized/x/{YYYY-MM}.jsonl（UTC→JST変換済み・全TSVから再構築）
"""
import argparse, csv, io, json, re, statistics, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from shizulib import *

def median_nonzero(vals):
    vals = [v for v in vals if v > 0]
    return statistics.median(vals) if vals else 0

def bursts_and_mismatch(chat, sents, duration):
    # バースト: 30秒ビン
    bins = {}
    for t, _, _ in chat:
        if t >= 0: bins[t // 30] = bins.get(t // 30, 0) + 1
    med = median_nonzero(bins.values())
    th = max(10, 2.5 * med)
    hot = sorted([(b, c) for b, c in bins.items() if c >= th])
    bursts, i = [], 0
    while i < len(hot):                       # 隣接ビンを結合
        b0, c = hot[i]; b1 = b0
        while i + 1 < len(hot) and hot[i + 1][0] == b1 + 1:
            i += 1; b1 = hot[i][0]; c = max(c, hot[i][1])
        bursts.append({"t": b0 * 30, "mmss": mmss(b0 * 30), "peak_per30s": c}); i += 1
    bursts = sorted(bursts, key=lambda x: -x["peak_per30s"])[:12]
    # ミスマッチ: チャット密集なのに字幕が沈黙（30秒窓・10秒刻み）→ 非言語音イベント候補
    asr_chars = {}
    for t, s in sents:
        asr_chars[t] = asr_chars.get(t, 0) + len(s)
    wins = []
    t0 = 0
    while t0 < duration:
        c = sum(1 for t, _, _ in chat if t0 <= t < t0 + 30)
        a = sum(v for t, v in asr_chars.items() if t0 <= t < t0 + 30)
        wins.append((t0, c, a)); t0 += 10
    cmed = median_nonzero([c for _, c, _ in wins])
    mm, i = [], 0
    flags = [c >= max(8, 2 * cmed) and a <= 8 for _, c, a in wins]
    while i < len(wins):
        if flags[i]:
            j = i
            while j + 1 < len(wins) and flags[j + 1]: j += 1
            s, e = wins[i][0], wins[j][0] + 30
            mm.append({"t_from": s, "t_to": e, "mmss": f"{mmss(s)}〜{mmss(e)}",
                       "chat_peak": max(w[1] for w in wins[i:j+1])})
            i = j + 1
        else:
            i += 1
    return bursts, mm, round(med, 1)

def lexicon_hits(chat, fams):
    out = []
    for name, kws in fams:
        hits = [(t, tx) for t, _, tx in chat if any(k in tx for k in kws)]
        if hits:
            out.append({"family": name, "count": len(hits),
                        "samples": [f"{mmss(t)}「{tx[:24]}」" for t, tx in hits[:3]]})
    return out

def novel_desc_lines(vid, desc, state):
    lines = [l.strip() for l in desc.split("\n")]
    lines = [l for l in lines if len(l) >= 4 and not set(l) <= set("＿_─-— ")]
    novel = []
    for l in lines:
        if l not in state:
            state[l] = vid
            novel.append(l)
    return novel

def process_stream(d, fixes, fams, desc_state, first):
    date, vid = d.name.split("_", 1)
    out = DATA / "normalized" / "streams" / vid
    meta = parse_info(d / "info.txt") if (d / "info.txt").exists() else {}
    meta.update({"date": meta.get("date") or date, "video_id": vid, "dir": d.name})
    blocks = parse_sbv(d / "sbv.txt")
    chat = parse_chat(d / "chat.txt")
    sents_raw = rejoin_sentences(blocks)
    rows, fix_total = [], 0
    for t, s in sents_raw:
        norm, n = apply_fixes(s, fixes); fix_total += n
        rows.append((t, mmss(t), yt_url(vid, t), s, norm))
    write(out / "sentences.tsv", "t\tmmss\turl\tasr\tnorm\n" +
          "".join("\t".join(map(str, r)) + "\n" for r in rows))
    write(out / "chat.tsv", "t\tmmss\tuser\ttext\n" +
          "".join(f"{t}\t{mmss(t)}\t{u}\t{tx}\n" for t, u, tx in chat))
    duration = blocks[-1][0] if blocks else 0
    bursts, mism, med = bursts_and_mismatch(chat, sents_raw, duration)
    comments = parse_comments(d / "comments.txt")
    novel = ([] if first else novel_desc_lines(vid, meta.get("description", ""), desc_state))
    if first:
        novel_desc_lines(vid, meta.get("description", ""), desc_state)  # 基準線として登録のみ
    signals = {
        "bursts": bursts,
        "chat_median_per30s": med,
        "asr_silent_chat_dense": mism,
        "lexicon": lexicon_hits(chat, fams),
        "comment_timestamps": [{"sec": t, "mmss": mmss(t), "comment": e["text"][:60]}
                               for e in comments for t in e["ts_refs"]],
        "novel_description_lines": novel + (["(この配信が基準線: 全行を登録)"] if first else []),
    }
    write(out / "signals.json", json.dumps(signals, ensure_ascii=False, indent=1))
    meta.update({"blocks": len(blocks), "sentences": len(rows), "chat_msgs": len(chat),
                 "duration_sec": duration, "dict_fixes_applied": fix_total,
                 "noise_blocks": sum(1 for _, t in blocks if NOISE_RE.search(t))})
    write(out / "meta.json", json.dumps(meta, ensure_ascii=False, indent=1))
    print(f"  {date} {vid}: {len(blocks)}ブロック→{len(rows)}文 / チャット{len(chat)}件 / "
          f"辞書適用{fix_total}箇所 / バースト{len(bursts)} / ミスマッチ{len(mism)}区間 / 概要欄新規行{len(novel)}")

def process_x():
    rows_by_id = {}
    for f in sorted((DATA / "raw" / "x").glob("*.tsv")) + sorted((DATA / "raw" / "x").glob("*.txt")):
        txt = read(f).replace("\r\n", "\n")
        if not txt.strip() or "URL" not in txt.splitlines()[0]:
            print(f"  ! {f.name}: TSVとして読めない（doctor.py 参照）"); continue
        rd = csv.reader(io.StringIO(txt), delimiter="\t")
        header = next(rd)
        idx = {h: i for i, h in enumerate(header)}
        def col(r, name):
            i = idx.get(name); return r[i] if i is not None and i < len(r) else ""
        for r in rd:
            if not r or not col(r, "URL"): continue
            url = col(r, "URL"); pid = url.rstrip("/").split("/")[-1]
            try:
                dj, tj, du = utc_to_jst(col(r, "日付"))
            except Exception:
                continue
            def num(name):
                v = col(r, name).replace(",", "").strip()
                return int(v) if v.isdigit() else None
            rows_by_id[pid] = {"post_id": pid, "url": url, "date_jst": dj, "time_jst": tj,
                               "date_utc": du, "type": col(r, "種類"), "author": col(r, "投稿者"),
                               "text": col(r, "本文"), "quote_text": col(r, "引用内容"),
                               "likes": num("いいね数"), "reposts": num("リポスト数"),
                               "replies": num("返信数"), "views": num("表示数")}
    months = {}
    for rec in rows_by_id.values():
        months.setdefault(rec["date_jst"][:7], []).append(rec)
    for m, recs in sorted(months.items()):
        recs.sort(key=lambda r: (r["date_jst"], r["time_jst"]))
        jsonl_write(DATA / "normalized" / "x" / f"{m}.jsonl", recs)
    if months:
        print("  X月別: " + " / ".join(f"{m}:{len(v)}件" for m, v in sorted(months.items())))

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--stream")
    a = ap.parse_args()
    fixes, fams = load_fixes(), load_lexicon()
    manifest = load_state("manifest.json", {})
    desc_state = load_state("desc_lines.json", {})
    dirs = stream_dirs()
    targets = dirs if a.all else ([find_stream(a.stream)] if a.stream else [])
    targets = [d for d in targets if d]
    if not targets and not a.all:
        print("対象なし。--all か --stream <vid> を指定してください。"); return
    print("=== 配信の正規化 ===")
    for d in targets:
        first = (len(desc_state) == 0)
        if manifest.get(d.name, {}).get("s1") and a.all:
            print(f"  {d.name}: 処理済み（再実行は --stream 指定で）"); continue
        process_stream(d, fixes, fams, desc_state, first)
        manifest.setdefault(d.name, {})["s1"] = True
    save_state("manifest.json", manifest)
    save_state("desc_lines.json", desc_state)
    print("=== Xログの正規化（全TSVから再構築） ===")
    process_x()
    print("\n次: python scripts/s2_pack.py --stream <vid>  （抽出パック生成）")

if __name__ == "__main__":
    main()
