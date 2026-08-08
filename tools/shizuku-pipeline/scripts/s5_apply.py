# -*- coding: utf-8 -*-
"""ステップ5: レビュー結果の反映。チェック済みパケットを読み、カード状態と台帳を更新し、
wiki起草チャットへ渡す handoff ファイルを生成する。
使い方:
  python scripts/s5_apply.py --packet data/review/RV_xxxx.md
規約:
  [x] VERIFY <id> … 直後の「逐語:」行の内容でカード本文を確定（verbatim=true, status=verified）
  [x] ADOPT  <id> … 採用（quoteはverified後のみ有効）→ status=approved → handoffに載る
  [x] DROP   <id> … 不採用（カード=rejected / 台帳=dropped）
  [x] KEEP   <id> … 台帳openを維持
  [x] CLOSE <loop_id> BY <card_id> … 回収成立。open→closed.jsonlへ移動、handoffに追補案
  未チェック＝保留（次回パケットに再掲）
"""
import argparse, json, re, sys
from datetime import date
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from shizulib import *

ACT_RE = re.compile(r"^\s*-\s*\[(x|X| )\]\s+(ADOPT|VERIFY|DROP|KEEP|CLOSE)\s+(\S+)(?:\s+BY\s+(\S+))?")

def parse_packet(path):
    acts, verbatims = [], {}
    lines = read(path).splitlines()
    for i, line in enumerate(lines):
        m = ACT_RE.match(line)
        if not m: continue
        checked = m.group(1).lower() == "x"
        act, a1, a2 = m.group(2), m.group(3), m.group(4)
        acts.append((checked, act, a1, a2))
        if act == "VERIFY":
            for j in range(i + 1, min(i + 6, len(lines))):
                mm = re.match(r"\s*逐語[:：]\s*(.*)", lines[j])
                if mm:
                    v = mm.group(1).strip()
                    if v and not v.startswith("（←"):
                        verbatims[a1] = v
                    break
    return acts, verbatims

def parts_from_verbatim(v):
    if "【" not in v: return None
    parts = []
    for m in re.finditer(r"【([^】]+)】([^【]+)", v):
        parts.append({"speaker": m.group(1).strip(), "text": m.group(2).strip(" ／/").strip(), "verbatim": True})
    return parts or None

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--packet", required=True)
    a = ap.parse_args()
    acts, verbatims = parse_packet(a.packet)
    by_id, by_file = load_all_cards()
    opens = jsonl_read(DATA / "ledger" / "open.jsonl")
    props = jsonl_read(DATA / "ledger" / "proposals.jsonl")
    in_rev = load_state("in_review.json", {})
    today = date.today().isoformat()
    n = {"verified": 0, "approved": 0, "rejected": 0, "closed": 0, "kept": 0, "dropped_loop": 0}
    closed_pairs = []

    for checked, act, a1, a2 in acts:
        if not checked: continue
        if act == "VERIFY" and a1 in by_id:
            c = by_id[a1]
            v = verbatims.get(a1)
            if not v:
                print(f"  ⚠ VERIFY {a1}: 「逐語:」行が未記入のためスキップ"); continue
            p_ = parts_from_verbatim(v)
            if p_: c["parts"] = p_; c["text"] = None
            else: c["text"] = v; c.pop("parts", None)
            c["verbatim"] = True
            if c.get("status") == "candidate": c["status"] = "verified"
            n["verified"] += 1
        elif act == "ADOPT" and a1 in by_id:
            c = by_id[a1]
            if c["kind"] == "quote_candidate" and not c.get("verbatim"):
                print(f"  ⚠ ADOPT {a1}: 逐語未確定の名言は採用できません（先にVERIFY）"); continue
            c["status"] = "approved"; n["approved"] += 1
        elif act == "DROP":
            if a1 in by_id:
                by_id[a1]["status"] = "rejected"; n["rejected"] += 1
            for l in opens:
                if l.get("loop_id") == a1 and l.get("status") == "open":
                    l["status"] = "dropped"; l["dropped"] = today; n["dropped_loop"] += 1
        elif act == "KEEP":
            n["kept"] += 1
        elif act == "CLOSE":
            for l in opens:
                if l.get("loop_id") == a1 and l.get("status") == "open":
                    l["status"] = "closed"; l["closed"] = today; l["closed_by"] = a2
                    pr = next((p for p in props if p["loop_id"] == a1 and p["card_id"] == a2), {})
                    closed_pairs.append((l, by_id.get(a2, {}), pr.get("reason", "")))
                    n["closed"] += 1
        in_rev.pop(a1, None)

    # 保存: カード / 台帳（closedはclosed.jsonlへ移す）
    save_cards(by_file)
    still, moved = [], []
    for l in opens:
        (moved if l.get("status") in ("closed", "dropped") else still).append(l)
    jsonl_write(DATA / "ledger" / "open.jsonl", still)
    if moved: jsonl_append(DATA / "ledger" / "closed.jsonl", moved)
    jsonl_write(DATA / "ledger" / "proposals.jsonl",
                [p for p in props if not any(l.get("loop_id") == p["loop_id"] and l.get("closed_by") == p["card_id"] for l in moved)])
    save_state("in_review.json", in_rev)

    # handoff生成（承認済みのみ）
    H = [f"# handoff {Path(a.packet).stem} → wiki起草チャット（prompts/draft_wiki.md 参照）", ""]
    evs = [c for c in by_id.values() if c["status"] == "approved" and c["kind"] == "event"]
    if evs:
        H.append("=== 年表（shizuku-wikiスキルの受け渡し形式のまま渡す） ===")
        for c in sorted(evs, key=lambda c: c["date_jst"]):
            H += [f"【日付】{c['date_jst']}", f"【出来事の概要】{c.get('summary','')}",
                  f"【ソースURL】{c['source'].get('url','')}", "---"]
        H.append("")
    qts = [c for c in by_id.values() if c["status"] == "approved" and c["kind"] == "quote_candidate"]
    if qts:
        H.append("=== 名言・迷言（逐語確定済み） ===")
        for c in sorted(qts, key=lambda c: c["date_jst"]):
            body = (" ／ ".join(f"【{p['speaker']}】{p['text']}" for p in c["parts"])
                    if c.get("parts") else f"【しずく】{c.get('text','')}")
            H += [body, f"出典URL: {c['source'].get('url','')}（{c['date_jst']}配信）", "---"]
        H.append("")
    if closed_pairs:
        H.append("=== 回収成立（年表の既存行への括弧書き追補を起草させる） ===")
        for l, c, reason in closed_pairs:
            H += [f"ループ: [{l.get('opened')}] {l.get('text','')}",
                  f"　回収: [{c.get('date_jst')}] {c.get('summary','')}",
                  f"　両出典: {l.get('source',{}).get('url','')} / {c.get('source',{}).get('url','')}",
                  f"　判定根拠: {reason}", "---"]
        H.append("")
    caps = [c for c in by_id.values() if c["status"] == "approved" and c["kind"] == "capability"]
    if caps:
        H.append("=== 機能（紹介ページ「特殊機能」節の加筆材料。採用後 config/features_registry.tsv にも追記） ===")
        for c in caps:
            H += [f"{c.get('feature_hint','?')}: {c.get('summary','')}",
                  f"出典: {c['source'].get('url','')}　初観測: {c['date_jst']}（※wikiでは「遅くとも」表現を推奨）", "---"]
        H.append("")
    pfs = [c for c in by_id.values() if c["status"] == "approved" and c["kind"] in ("profile_fact", "stream_note")]
    if pfs:
        H.append("=== 紹介ページ補足（該当節ソースと一緒に起草チャットへ） ===")
        for c in pfs:
            H += [f"[{'/'.join(c.get('wiki_target',[]))}] {c.get('summary','')}  出典: {c['source'].get('url','')}", "---"]
    out = DATA / "handoff" / f"handoff_{Path(a.packet).stem}.txt"
    write(out, "\n".join(H) + "\n")
    print("反映: " + " / ".join(f"{k}:{v}" for k, v in n.items() if v))
    print(f"handoff生成: {out.relative_to(BASE)}")
    print("→ prompts/draft_wiki.md の手順で、shizuku-wikiスキル併用チャットに渡して差分を作る。")

if __name__ == "__main__":
    main()
