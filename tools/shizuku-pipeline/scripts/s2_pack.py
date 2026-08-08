# -*- coding: utf-8 -*-
"""ステップ2a: 抽出パック生成。Claudeチャットに添付するファイルを作る。
使い方:
  python scripts/s2_pack.py --stream <vid> [--split N]   # 配信1本ぶん
  python scripts/s2_pack.py --x YYYY-MM                  # Xログ1ヶ月ぶん
生成先: data/packs/
"""
import argparse, json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from shizulib import *

def registry_text():
    p = CONF / "features_registry.tsv"
    if not p.exists(): return "(レジストリ未設定)"
    lines = [l for l in read(p).splitlines() if l.strip() and not l.startswith("#")]
    return "\n".join("- " + " / ".join(l.split("\t")) for l in lines)

def signals_text(sig):
    out = ["=== シグナル（機械検出のヒント） ==="]
    if sig.get("bursts"):
        out.append("▼ チャットが盛り上がった時刻（30秒あたり件数）")
        out += [f"  {b['mmss']}  {b['peak_per30s']}件" for b in sig["bursts"]]
    if sig.get("asr_silent_chat_dense"):
        out.append("▼ 字幕が沈黙しているのにチャットが密集（非言語音イベント候補）")
        out += [f"  {m['mmss']}  チャット最大{m['chat_peak']}件/30秒" for m in sig["asr_silent_chat_dense"]]
    if sig.get("comment_timestamps"):
        out.append("▼ 配信後コメントが指している時刻")
        out += [f"  {c['mmss']}  ←「{c['comment']}」" for c in sig["comment_timestamps"]]
    if sig.get("novel_description_lines"):
        out.append("▼ 概要欄に今回はじめて現れた行（企画・ギミック候補）")
        out += [f"  {l}" for l in sig["novel_description_lines"]]
    if sig.get("lexicon"):
        out.append("▼ チャット語彙群ヒット")
        out += [f"  [{h['family']}] {h['count']}件 例: " + " / ".join(h["samples"]) for h in sig["lexicon"]]
    return "\n".join(out)

def build_stream(vid, split):
    d = find_stream(vid)
    if not d:
        print(f"raw/streams に {vid} が見つかりません"); return
    vid = d.name.split("_", 1)[1]
    nd = DATA / "normalized" / "streams" / vid
    if not (nd / "sentences.tsv").exists():
        print("先に s1_normalize を実行してください"); return
    meta = json.loads(read(nd / "meta.json"))
    sig = json.loads(read(nd / "signals.json"))
    tmpl = read(PROMPTS / "extract_stream.md")
    head = (tmpl.replace("{{TITLE}}", meta.get("title", ""))
                .replace("{{DATE}}", meta.get("date", ""))
                .replace("{{VIDEO_ID}}", vid)
                .replace("{{REGISTRY}}", registry_text()))
    # タイムライン統合（S=字幕norm / C=チャット原文）
    lines = []
    for row in read(nd / "sentences.tsv").splitlines()[1:]:
        c = row.split("\t")
        if len(c) >= 5: lines.append((int(c[0]), 0, f"[S {c[1]}] {c[4]}"))
    for row in read(nd / "chat.tsv").splitlines()[1:]:
        c = row.split("\t", 3)
        if len(c) >= 4: lines.append((int(c[0]), 1, f"[C {c[1]} {c[2][-4:]}] {c[3]}"))
    lines.sort(key=lambda x: (x[0], x[1]))
    body = [l for _, _, l in lines]
    chunks = [body]
    if split > 1:
        n = len(body); step = -(-n // split)
        chunks = [body[i:i+step] for i in range(0, n, step)]
    date = meta.get("date", "")
    for i, ch in enumerate(chunks, 1):
        part = f"（パート {i}/{len(chunks)}：時系列の一部。カード抽出はこの範囲から）\n" if len(chunks) > 1 else ""
        out = DATA / "packs" / (f"extract_{date}_{vid}" + (f"_part{i}" if len(chunks) > 1 else "") + ".txt")
        write(out, head + "\n" + signals_text(sig) + "\n\n=== タイムライン ===\n" + part + "\n".join(ch) + "\n")
        kb = out.stat().st_size // 1024
        print(f"生成: {out.relative_to(BASE)}  ({kb}KB / {len(ch)}行)")
    print("→ このファイルをClaudeのチャットに添付し「このファイルの指示に従ってカードを抽出して」と送る。"
          "\n→ 返ってきたJSONLを data/packs/cards_<配信ID>.jsonl 等の名前で保存し、s2_ingest へ。")

def build_x(month, split=1):
    p = DATA / "normalized" / "x" / f"{month}.jsonl"
    if not p.exists():
        print(f"{p} がありません（s1_normalize --all を先に）"); return
    recs = jsonl_read(p)
    tmpl = read(PROMPTS / "extract_x.md").replace("{{MONTH}}", month)
    chunks = [recs]
    if split > 1:
        step = -(-len(recs) // split)
        chunks = [recs[i:i+step] for i in range(0, len(recs), step)]
    for i, ch in enumerate(chunks, 1):
        body = "\n".join(json.dumps({k: r[k] for k in
            ("post_id", "url", "date_jst", "time_jst", "type", "text", "quote_text", "likes", "views") if k in r},
            ensure_ascii=False) for r in ch)
        part = f"（パート {i}/{len(chunks)}）\n" if len(chunks) > 1 else ""
        out = DATA / "packs" / (f"extract_x_{month}" + (f"_part{i}" if len(chunks) > 1 else "") + ".txt")
        write(out, tmpl + "\n" + part + body + "\n")
        print(f"生成: {out.relative_to(BASE)}  ({out.stat().st_size//1024}KB / {len(ch)}ポスト)")
    print("→ Claudeに添付 → 返ってきたJSONLを保存 → s2_ingest --from x:" + month)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stream"); ap.add_argument("--x"); ap.add_argument("--split", type=int, default=1)
    a = ap.parse_args()
    if a.stream: build_stream(a.stream, a.split)
    elif a.x: build_x(a.x, a.split)
    else: print("--stream <vid> か --x YYYY-MM を指定してください")

if __name__ == "__main__":
    main()
