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

STOPWORDS = {"しずく", "配信", "ご主人", "ご主人様", "コメント", "みんな", "今日", "今回",
             "本当", "自分", "気持", "感じ", "みなさん", "ありがと", "よろしく", "リスナー"}

def overlap_ok(ltok, ctok, min_len=3):
    """語彙の重なりで前絞り。ストップワードを除き、長さ min_len 以上の共通語（完全一致）を要求。
    部分文字列一致は誤爆が多いので採用しない。"""
    a = {w for w in ltok if len(w) >= min_len and w not in STOPWORDS}
    b = {w for w in ctok if len(w) >= min_len and w not in STOPWORDS}
    return bool(a & b)

def build(until=None, max_pairs=1500, min_overlap_len=3):
    opens = [l for l in jsonl_read(DATA / "ledger" / "open.jsonl") if l.get("status") == "open"]
    if until:                                            # この日までに開いたループだけ（区切り処理）
        opens = [l for l in opens if l.get("opened", "") <= until]
    seen_pairs = set(load_state("match_seen.json", []))
    by_id, _ = load_all_cards()
    cards = [c for c in by_id.values() if c["kind"] in MATCH_KINDS]
    if until:
        cards = [c for c in cards if c.get("date_jst", "") <= until]
    opens.sort(key=lambda l: l.get("opened", ""))        # 開封の古い順（台帳を育てながら閉じる）
    pairs, capped = [], False
    for lo in opens:
        ltok = tokenize(flat_text([lo.get("text"), lo.get("expected_signal")]))
        for c in cards:
            if c["id"] == lo["loop_id"]: continue
            if c.get("date_jst", "") <= lo.get("opened", ""): continue  # 因果: 開封後の出来事のみ
            pid = f"{lo['loop_id']}__{c['id']}"
            if pid in seen_pairs: continue
            ctok = tokenize(flat_text([c.get("text"), c.get("summary"), c.get("evidence")]))
            if not overlap_ok(ltok, ctok, min_overlap_len): continue
            pairs.append({"pair_id": pid,
                          "loop": {k: lo[k] for k in ("loop_id","opened","loop_type","text","expected_signal") if k in lo},
                          "card": {k: c.get(k) for k in ("id","kind","date_jst","summary","text")}})
            if len(pairs) >= max_pairs:
                capped = True; break
        if capped: break
    seen_pairs |= {p["pair_id"] for p in pairs}
    save_state("match_seen.json", sorted(seen_pairs))
    if not pairs:
        print(f"照合対象なし（カード{len(cards)}枚 × open{len(opens)}件、新規ペアなし）"); return
    out = DATA / "packs" / f"match_{date.today().isoformat()}.txt"
    write(out, read(PROMPTS / "match_pairs.md") + "\n" +
          "\n".join(json.dumps(p, ensure_ascii=False) for p in pairs) + "\n")
    print(f"生成: {out.relative_to(BASE)}  （{len(pairs)}ペア）")
    if capped:
        print(f"  ※上限{max_pairs}ペアに達したので今回はここまで。判定→取込のあと、"
              f"もう一度 s3_match を実行すると続きが出ます。")
    print("→ Claudeに添付 → 判定JSONLを data/llm_out/judgments_<日付>.jsonl として保存"
          "\n→ python scripts/s3_match.py --ingest data/llm_out/judgments_<日付>.jsonl")

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
    print("次: python scripts/s4_packet.py  （その後 python scripts/s3_match.py を再実行すると次のバッチが出ます）")

def list_open():
    opens = [l for l in jsonl_read(DATA / "ledger" / "open.jsonl") if l.get("status") == "open"]
    print(f"未回収の台帳: {len(opens)}件")
    for l in sorted(opens, key=lambda x: x.get("opened", "")):
        print(f"  [{l.get('opened')}] ({l.get('loop_type')}) {l.get('text','')[:38]}")
        print(f"      回収条件: {l.get('expected_signal','')[:60]}   id={l['loop_id']}")

def status():
    opens = [l for l in jsonl_read(DATA / "ledger" / "open.jsonl") if l.get("status") == "open"]
    seen = load_state("match_seen.json", [])
    by_id, _ = load_all_cards()
    cards = [c for c in by_id.values() if c["kind"] in MATCH_KINDS]
    props = jsonl_read(DATA / "ledger" / "proposals.jsonl")
    print(f"未回収ループ: {len(opens)}件 / 照合対象カード(event等): {len(cards)}枚")
    print(f"判定済みペア(累計): {len(seen)} / 未確認のクローズ提案: {len(props)}件")
    # 月別のループ数（どこから区切るかの目安）
    from collections import Counter
    by_month = Counter(l.get("opened", "")[:7] for l in opens)
    print("未回収ループの月別分布:")
    for m, n in sorted(by_month.items()):
        print(f"  {m}: {n}")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ingest"); ap.add_argument("--list-open", action="store_true")
    ap.add_argument("--status", action="store_true", help="ループ・カード・判定の残り状況")
    ap.add_argument("--until", help="この日(YYYY-MM-DD)までに開いたループだけ照合（区切り処理）")
    ap.add_argument("--max-pairs", type=int, default=1500, help="1パックの上限ペア数（既定1500）")
    a = ap.parse_args()
    if a.ingest: ingest(a.ingest)
    elif a.list_open: list_open()
    elif a.status: status()
    else: build(until=a.until, max_pairs=a.max_pairs)

if __name__ == "__main__":
    main()
