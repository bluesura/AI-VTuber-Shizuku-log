# -*- coding: utf-8 -*-
"""ステップ4: レビューパケット生成。status=candidate のカードとクローズ提案を1枚のMarkdownにまとめる。
使い方:
  python scripts/s4_packet.py [--mature-days 30]
- 名言候補は既定で「30日熟成」: 配信日から30日経ったものだけ載せる（月次選考の思想）。0で即時。
- 出力: data/review/RV_*.md   → 人間が試聴し、チェックボックスを埋めて s5_apply へ。
チェック規約: [x]を付けた行だけが実行される。未チェック＝保留（次回また出る）。不要なら DROP に[x]。
"""
import argparse, json, sys
from datetime import date, timedelta
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from shizulib import *

def wikiref(c):
    """スキル§3-3の出典書式で<ref>を組む（起草チャットの下敷き。最終形はスキル側が確定）"""
    s = c.get("source", {})
    if s.get("type") == "yt":
        vid, t = s.get("video_id"), int(s.get("t") or 0)
        meta = stream_meta(vid)
        title = meta.get("title", "配信")
        return (f'<ref name="yt-{vid}-t{t}">[{yt_url(vid,t)} {title}（該当箇所）]'
                f'（YouTube、{jdate(c["date_jst"])}）</ref>')
    if s.get("type") == "x":
        pid = s.get("post_id", "")
        head = (c.get("text") or "")[:20]
        return (f'<ref name="x-{pid}">[{s.get("url","")} しずくのポスト「{head}…」]'
                f'（X、{jdate(c["date_jst"])}）</ref>')
    return ""

def fmt_quote(c):
    if c.get("parts"):
        return " ／ ".join(f"【{p.get('speaker','?')}】{p.get('text','')}" for p in c["parts"])
    return c.get("text", "")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mature-days", type=int, default=30)
    a = ap.parse_args()
    by_id, _ = load_all_cards()
    in_rev = load_state("in_review.json", {})
    cands = [c for c in by_id.values() if c.get("status") == "candidate" and c["id"] not in in_rev]
    cutoff = (date.today() - timedelta(days=a.mature_days)).isoformat()
    ev  = sorted([c for c in cands if c["kind"] == "event"], key=lambda c: c["date_jst"])
    qt  = sorted([c for c in cands if c["kind"] == "quote_candidate" and c["date_jst"] <= cutoff], key=lambda c: c["date_jst"])
    qt_young = [c for c in cands if c["kind"] == "quote_candidate" and c["date_jst"] > cutoff]
    cap = sorted([c for c in cands if c["kind"] == "capability"], key=lambda c: c["date_jst"])
    pf  = sorted([c for c in cands if c["kind"] in ("profile_fact", "stream_note")], key=lambda c: c["date_jst"])
    props = jsonl_read(DATA / "ledger" / "proposals.jsonl")
    opens = [l for l in jsonl_read(DATA / "ledger" / "open.jsonl") if l.get("status") == "open"]
    new_opens = [l for l in opens if l["loop_id"] not in in_rev]

    rid = "RV_" + date.today().strftime("%Y%m%d")
    n = 1
    while (DATA / "review" / f"{rid}-{n:02d}.md").exists(): n += 1
    rid = f"{rid}-{n:02d}"
    L = [f"# レビューパケット {rid}",
         "",
         "記入方法: 実行してよい行の `[ ]` を `[x]` にする。未チェック＝保留（次回また出ます）。",
         "名言は **必ず試聴 → 「逐語:」行を書き直してから** VERIFY に [x]（ゲート1）。",
         ""]

    L.append(f"## A. 年表候補（event: {len(ev)}件）")
    for c in ev:
        L += [f"- [ ] ADOPT {c['id']}",
              f"      案: * {c['date_jst']}：{c.get('summary','')}{wikiref(c)}",
              f"      根拠発話(ASR): {c.get('text','')[:60]}",
              f"      出典: {c['source'].get('url','')}   ⚠試聴で発言確認",
              f"- [ ] DROP {c['id']}", ""]

    L.append(f"## B. 名言・迷言候補（quote: {len(qt)}件 / 熟成待ち{len(qt_young)}件は次回以降）")
    for c in qt:
        L += [f"- [ ] VERIFY {c['id']}",
              f"      試聴: {c['source'].get('url','')}",
              f"      ASR : {fmt_quote(c)}",
              f"      逐語: （←試聴して正確に書き直す。掛け合いは【発話者】形式のまま）",
              f"      反応: " + " / ".join(c.get("evidence", [])[:3]),
              f"- [ ] ADOPT {c['id']}   （逐語確定済みのものだけ）",
              f"- [ ] DROP {c['id']}", ""]

    L.append(f"## C. 機能カード候補（capability: {len(cap)}件）")
    for c in cap:
        L += [f"- [ ] ADOPT {c['id']}",
              f"      機能仮名: {c.get('feature_hint','?')} / {c.get('summary','')}",
              f"      証拠: " + " / ".join(c.get("evidence", [])[:3]),
              f"      出典: {c['source'].get('url','')}   ⚠試聴で確認 → 採用後レジストリに追記",
              f"- [ ] DROP {c['id']}", ""]

    L.append(f"## D. 台帳")
    L.append(f"### D-1. 新規オープン（自動登録済み・妥当か確認: {len(new_opens)}件）")
    for l in new_opens:
        L += [f"- [ ] KEEP {l['loop_id']}   ({l.get('loop_type')}) {l.get('text','')[:44]}",
              f"      回収条件: {l.get('expected_signal','')}",
              f"- [ ] DROP {l['loop_id']}", ""]
    L.append(f"### D-2. クローズ提案（回収成立の確認 → ゲート4: {len(props)}件）")
    for p_ in props:
        lo = next((l for l in opens if l["loop_id"] == p_["loop_id"]), {})
        ca = by_id.get(p_["card_id"], {})
        L += [f"- [ ] CLOSE {p_['loop_id']} BY {p_['card_id']}",
              f"      ループ: [{lo.get('opened')}] {lo.get('text','')[:44]}",
              f"      回収　: [{ca.get('date_jst')}] {ca.get('summary','')[:52]}",
              f"      判定理由: {p_.get('reason','')} (conf {p_.get('confidence')})", ""]

    L.append(f"## E. 紹介ページ供給メモ（profile_fact / stream_note: {len(pf)}件）")
    for c in pf:
        L += [f"- [ ] ADOPT {c['id']}   [{c['kind']}→{'/'.join(c.get('wiki_target',[]))}] {c.get('summary','')}",
              f"      出典: {c['source'].get('url','')}",
              f"- [ ] DROP {c['id']}", ""]

    L.append("## F. シグナル参考（今回パケットに関係した配信の概要欄新規行など）")
    for d in sorted((DATA / "normalized" / "streams").iterdir()):
        sp = d / "signals.json"
        if sp.exists():
            s = json.loads(read(sp))
            nl = [x for x in s.get("novel_description_lines", []) if not x.startswith("(")]
            if nl: L.append(f"- {d.name}: " + " / ".join(nl[:4]))
    L.append("")
    out = DATA / "review" / f"{rid}.md"
    write(out, "\n".join(L))
    for c in cands: in_rev[c["id"]] = rid
    for l in new_opens: in_rev[l["loop_id"]] = rid
    save_state("in_review.json", in_rev)
    print(f"生成: {out.relative_to(BASE)}")
    print(f"  年表{len(ev)} / 名言{len(qt)}(熟成待ち{len(qt_young)}) / 機能{len(cap)} / 供給{len(pf)} / open確認{len(new_opens)} / クローズ提案{len(props)}")
    print("→ エディタで開いて試聴・チェック → python scripts/s5_apply.py --packet " + str(out.relative_to(BASE)))

if __name__ == "__main__":
    main()
