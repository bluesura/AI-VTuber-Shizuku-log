# -*- coding: utf-8 -*-
"""ステップ2a: 抽出パック生成。Claudeチャットに添付するファイルを作る。
使い方:
  python scripts/s2_pack.py --stream <vid> [--split N]  # 配信1本ぶん
  python scripts/s2_pack.py --x YYYY-MM                 # Xログ1ヶ月ぶん
  python scripts/s2_pack.py --all                       # 未抽出のもの全部（配信＋X）を一括生成
  python scripts/s2_pack.py --all --redo                # 抽出済みも作り直す
  python scripts/s2_pack.py --status                    # 進捗一覧だけ表示
生成先: data/packs/ ＋ 作業リスト data/packs/WORKLIST.md
大きいパックは --max-chars（既定9万文字）を超えると自動で分割される。
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

def build_stream(vid, split=1, max_chars=0, quiet=False):
    d = find_stream(vid)
    if not d:
        print(f"raw/streams に {vid} が見つかりません"); return []
    vid = d.name.split("_", 1)[1]
    nd = DATA / "normalized" / "streams" / vid
    if not (nd / "sentences.tsv").exists():
        print(f"  ! {vid}: 先に s1_normalize を実行してください"); return []
    meta = json.loads(read(nd / "meta.json"))
    sig = json.loads(read(nd / "signals.json"))
    tmpl = read(PROMPTS / "extract_stream.md")
    head = (tmpl.replace("{{TITLE}}", meta.get("title", ""))
                .replace("{{DATE}}", meta.get("date", ""))
                .replace("{{VIDEO_ID}}", vid)
                .replace("{{REGISTRY}}", registry_text()))
    caution = []
    if meta.get("chat_source") == "ocr":
        caution.append("【重要】この配信のチャットは実データが残っておらず、映像からのOCR復元です。"
                       "誤字が含まれ、時刻は15秒程度の粒度に丸められ、取りこぼしもあります。"
                       "チャットを『ご主人様のコメント』として逐語引用してはいけません（verbatimは必ずfalse）。"
                       "反応の傾向を読む用途にのみ使ってください。")
    if meta.get("relation") and meta["relation"].get("rel") in ("archive_of", "reupload_of"):
        ev = meta.get("event_date") or "(元配信日)"
        caution.append(f"【重要】この動画は {meta['relation']['other']} のアーカイブ再アップです。"
                       f"投稿日は {meta.get('date')} ですが、**出来事が起きた日は {ev}** です。"
                       f"カードの date_jst には {ev} を使ってください。")
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
    note = ("\n=== この配信固有の注意 ===\n" + "\n".join("- " + c for c in caution) + "\n") if caution else ""
    overhead = len(head) + len(note) + len(signals_text(sig)) + 200
    body_chars = sum(len(l) + 1 for l in body)
    if split <= 1 and max_chars:
        split = max(1, -(-(body_chars + overhead) // max_chars))
    chunks = [body]
    if split > 1:
        n = len(body); step = -(-n // split)
        chunks = [body[i:i+step] for i in range(0, n, step)]
    date = meta.get("date", "")
    made = []
    for i, ch in enumerate(chunks, 1):
        part = f"（パート {i}/{len(chunks)}：時系列の一部。カード抽出はこの範囲から）\n" if len(chunks) > 1 else ""
        out = DATA / "packs" / (f"extract_{date}_{vid}" + (f"_part{i}" if len(chunks) > 1 else "") + ".txt")
        write(out, head + "\n" + note + signals_text(sig) + "\n\n=== タイムライン ===\n" + part + "\n".join(ch) + "\n")
        chars = len(read(out))
        made.append({"path": out, "chars": chars, "vid": vid, "date": date,
                     "title": meta.get("title", ""), "kind": "stream",
                     "part": (i, len(chunks))})
        if not quiet:
            print(f"生成: {out.relative_to(BASE)}  ({chars:,}文字 / {len(ch)}行)")
            print(f"  保存名: data/llm_out/{out.stem}.jsonl （パックと同じ名前・拡張子だけ .jsonl）")
    if not quiet:
        print("→ このファイルをClaudeのチャットに添付し「このファイルの指示に従ってカードをjsonlファイルで抽出して」と送る。"
              "\n→ 返答を上の保存名で data/llm_out/ に置き、s2_ingest へ（名前が違っても --from のIDから探します）。")
    return made

def build_x(month, split=1, max_chars=0, quiet=False):
    p = DATA / "normalized" / "x" / f"{month}.jsonl"
    if not p.exists():
        print(f"{p} がありません（s1_normalize --all を先に）"); return []
    recs = jsonl_read(p)
    tmpl = read(PROMPTS / "extract_x.md").replace("{{MONTH}}", month)
    if split <= 1 and max_chars:
        est = len(tmpl) + sum(len(json.dumps(r, ensure_ascii=False)) for r in recs)
        split = max(1, -(-est // max_chars))
    chunks = [recs]
    if split > 1:
        step = -(-len(recs) // split)
        chunks = [recs[i:i+step] for i in range(0, len(recs), step)]
    made = []
    for i, ch in enumerate(chunks, 1):
        body = "\n".join(json.dumps({k: r[k] for k in
            ("post_id", "url", "date_jst", "time_jst", "type", "text", "quote_text", "likes", "views") if k in r},
            ensure_ascii=False) for r in ch)
        part = f"（パート {i}/{len(chunks)}）\n" if len(chunks) > 1 else ""
        out = DATA / "packs" / (f"extract_x_{month}" + (f"_part{i}" if len(chunks) > 1 else "") + ".txt")
        write(out, tmpl + "\n" + part + body + "\n")
        chars = len(read(out))
        made.append({"path": out, "chars": chars, "vid": month, "date": month,
                     "title": f"Xログ {month}（{len(ch)}ポスト）", "kind": "x",
                     "part": (i, len(chunks))})
        if not quiet:
            print(f"生成: {out.relative_to(BASE)}  ({chars:,}文字 / {len(ch)}ポスト)")
            print(f"  保存名: data/llm_out/{out.stem}.jsonl （パックと同じ名前・拡張子だけ .jsonl）")
    if not quiet:
        print("→ Claudeに添付 → 上の保存名で data/llm_out/ に保存 → s2_ingest --from x:" + month)
    return made

def targets():
    """(kind, key, date, title) の一覧を日付順で返す"""
    out = []
    for d in sorted((DATA / "normalized" / "streams").iterdir()) if (DATA / "normalized" / "streams").exists() else []:
        m = stream_meta(d.name)
        if m: out.append(("stream", d.name, m.get("date", ""), m.get("title", "")))
    for f in sorted((DATA / "normalized" / "x").glob("*.jsonl")):
        out.append(("x", f.stem, f.stem, f"Xログ {f.stem}"))
    return sorted(out, key=lambda r: (r[2], r[1]))

def status_rows():
    done = load_state("extracted.json", {})
    rows = []
    for kind, key, date, title in targets():
        k = f"{kind}:{key}"
        rows.append({"kind": kind, "key": key, "date": date, "title": title,
                     "done": k in done, "cards": done.get(k, {}).get("cards"),
                     "at": done.get(k, {}).get("at")})
    return rows

def show_status():
    rows = status_rows()
    d = sum(1 for r in rows if r["done"])
    print(f"抽出の進捗: {d}/{len(rows)} 済み（未処理 {len(rows)-d}）")
    for r in rows:
        mark = f"済 カード{r['cards']}枚 ({r['at']})" if r["done"] else "未"
        print(f"  [{mark:>22}] {r['date']}  {r['kind']:6} {r['key'][:14]:16} {r['title'][:34]}")

def write_worklist(made):
    lines = ["# 抽出ワークリスト", "",
             "**1配信につき新しいClaudeチャットを1つ**使う。別配信を同じチャットに混ぜない。",
             "同じ配信が `partN` に分かれている場合は、その配信の全partを**同じチャットで順番に**渡す（前半の文脈を保つため）。",
             "Claudeの出力は `data/llm_out/` にパックと同じ名前(.jsonl)で保存。全部揃ったら `python scripts/s2_batch.py --apply` で一括取込（チェックも自動)。", ""]
    for m in made:
        pi, pn = m["part"]
        part = f"（{pi}/{pn}）" if pn > 1 else ""
        save = f"data/llm_out/{m['path'].stem}.jsonl"   # パックと同じ名前で保存（.txt→.jsonl）
        frm = 'stream:' + m['vid'] if m['kind']=='stream' else 'x:' + m['vid']
        cmd = f"python scripts/s2_ingest.py --file {save} --from {frm}"
        lines += [f"- [ ] **{m['date']}** {m['title'][:40]}{part}　`{m['chars']:,}文字`",
                  f"  - 添付: `{m['path'].relative_to(BASE)}`",
                  f"  - 保存: Claudeの返答を `{save}` に保存（**パックと同じ名前で拡張子だけ .jsonl**）",
                  f"  - 取込: `{cmd}`", ""]
    out = DATA / "packs" / "WORKLIST.md"
    write(out, "\n".join(lines))
    return out

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stream"); ap.add_argument("--x")
    ap.add_argument("--all", action="store_true", help="未抽出のもの全部を一括生成")
    ap.add_argument("--redo", action="store_true", help="抽出済みも対象にする")
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--split", type=int, default=1)
    ap.add_argument("--max-chars", type=int, default=90000, help="1パックの上限文字数（超えたら自動分割）")
    a = ap.parse_args()
    if a.status: show_status(); return
    if a.all:
        rows = [r for r in status_rows() if a.redo or not r["done"]]
        if not rows:
            print("未抽出のパックはありません（--redo で作り直せます）"); return
        made = []
        for r in rows:
            if r["kind"] == "stream":
                made += build_stream(r["key"], a.split, a.max_chars, quiet=True)
            else:
                made += build_x(r["key"], a.split, a.max_chars, quiet=True)
        for m in made:
            pi, pn = m["part"]
            tag = f" part{pi}/{pn}" if pn > 1 else ""
            print(f"  {m['date']}  {m['chars']:>7,}文字{tag}  {m['path'].name}")
        wl = write_worklist(made)
        big = [m for m in made if m["chars"] > a.max_chars]
        print(f"\n{len(made)}パックを生成（対象 {len(rows)}件）。作業リスト: {wl.relative_to(BASE)}")
        if big: print(f"  ※上限超過がまだ {len(big)}件あります（--max-chars を下げてください）")
        print("→ WORKLIST.md を上から1つずつ、**1パック=1チャット**で処理してください（理由はMANUAL 2b）。")
        return
    if a.stream: build_stream(a.stream, a.split, a.max_chars)
    elif a.x: build_x(a.x, a.split, a.max_chars)
    else: print("--stream <vid> / --x YYYY-MM / --all / --status のいずれかを指定してください")

if __name__ == "__main__":
    main()
