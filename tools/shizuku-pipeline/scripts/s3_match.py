# -*- coding: utf-8 -*-
"""ステップ3: 台帳照合。「未回収の台帳 × 新カード」の短リストを作り、判定はClaudeに委ねる。
使い方:
  python scripts/s3_match.py                 # 短リストのパック生成（前段フィルタ=語彙重なり）
  python scripts/s3_match.py --ingest <判定JSONL>   # Claudeの判定を取り込む（closed→クローズ提案）
  python scripts/s3_match.py --list-open     # 未回収台帳の一覧
計算量は「新カード×open」だけ。全履歴を舐めない。
"""
import argparse, json, sys
from datetime import date
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from shizulib import *

MATCH_KINDS = {"event", "capability", "stream_note", "profile_fact"}

def build():
    opens = [l for l in jsonl_read(DATA / "ledger" / "open.jsonl") if l.get("status") == "open"]
    seen = set(load_state("match_seen.json", []))
    by_id, _ = load_all_cards()
    news = [c for c in by_id.values() if c["kind"] in MATCH_KINDS and c["id"] not in seen]
    pairs = []
    for lo in opens:
        ltok = tokenize((lo.get("text") or "") + " " + (lo.get("expected_signal") or ""))
        for c in news:
            if c["id"] == lo["loop_id"]: continue
            if c.get("date_jst", "") <= lo.get("opened", ""): continue
            ctok = tokenize((c.get("text") or "") + " " + (c.get("summary") or "") + " " + " ".join(c.get("evidence", [])))
            hit = bool(ltok & ctok) or any(
                (a in b or b in a) for a in ltok for b in ctok if len(a) >= 2 and len(b) >= 2)
            if hit:
                pairs.append({"pair_id": f"{lo['loop_id']}__{c['id']}",
                              "loop": {k: lo[k] for k in ("loop_id","opened","loop_type","text","expected_signal") if k in lo},
                              "card": {k: c.get(k) for k in ("id","kind","date_jst","summary","text")}})
    seen |= {c["id"] for c in news}
    save_state("match_seen.json", sorted(seen))
    if not pairs:
        print(f"照合対象なし（新カード{len(news)}枚 × open{len(opens)}件、語彙重なりゼロ）"); return
    out = DATA / "packs" / f"match_{date.today().isoformat()}.txt"
    write(out, read(PROMPTS / "match_pairs.md") + "\n" +
          "\n".join(json.dumps(p, ensure_ascii=False) for p in pairs) + "\n")
    print(f"生成: {out.relative_to(BASE)}  （{len(pairs)}ペア）")
    print("→ Claudeに添付 → 判定JSONLを保存 → python scripts/s3_match.py --ingest <ファイル>")

def ingest(path):
    js = jsonl_read(path)
    by_id, by_file = load_all_cards()
    props, related = [], 0
    for j in js:
        pid = j.get("pair_id", "")
        if "__" not in pid: continue
        lid, cid = pid.split("__", 1)
        if j.get("verdict") == "closed":
            props.append({"loop_id": lid, "card_id": cid,
                          "confidence": j.get("confidence"), "reason": j.get("reason", "")})
        elif j.get("verdict") == "related" and cid in by_id:
            by_id[cid].setdefault("links", [])
            if lid not in by_id[cid]["links"]: by_id[cid]["links"].append(lid); related += 1
    if props: jsonl_append(DATA / "ledger" / "proposals.jsonl", props)
    if related: save_cards(by_file)
    print(f"クローズ提案: {len(props)}件（レビューパケットで確認→ゲート4） / related付与: {related}件")
    print("次: python scripts/s4_packet.py")

def list_open():
    opens = [l for l in jsonl_read(DATA / "ledger" / "open.jsonl") if l.get("status") == "open"]
    print(f"未回収の台帳: {len(opens)}件")
    for l in sorted(opens, key=lambda x: x.get("opened", "")):
        print(f"  [{l.get('opened')}] ({l.get('loop_type')}) {l.get('text','')[:38]}")
        print(f"      回収条件: {l.get('expected_signal','')[:60]}   id={l['loop_id']}")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ingest"); ap.add_argument("--list-open", action="store_true")
    a = ap.parse_args()
    if a.ingest: ingest(a.ingest)
    elif a.list_open: list_open()
    else: build()

if __name__ == "__main__":
    main()
