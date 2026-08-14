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
    ap.add_argument("--until", help="この日(YYYY-MM-DD)までの候補だけを載せる（区切りレビュー）")
    ap.add_argument("--since", help="この日(YYYY-MM-DD)以降の候補だけを載せる")
    ap.add_argument("--kinds", help="載せる種別をカンマ区切りで限定。例 event,capability / quote / profile")
    ap.add_argument("--limit", type=int, default=0, help="各セクションの最大件数（0=無制限）")
    ap.add_argument("--reset", action="store_true",
                    help="in_review をクリアしてから作る（誤って二重生成し空パケットが出たときの作り直し）")
    a = ap.parse_args()
    if a.reset:
        # 旧仕様（パケットに載せた時点でin_reviewへ登録）で溜まった記録を一掃する後方互換用。
        # 新仕様では load_all_cards の status だけで候補を決めるので通常は不要。
        save_state("in_review.json", {})
        print("in_review をクリアしました（旧記録の掃除。新仕様では候補は status で管理します）。")
    by_id, _ = load_all_cards()
    # in_review は「s5で処理済み（採用/却下/確定）としてマークされたID」。パケットに載せただけでは登録しない。
    applied = load_state("in_review.json", {})


    def in_window(c):
        d = c.get("date_jst", "")
        if a.until and d > a.until: return False
        if a.since and d < a.since: return False
        return True
    kind_filter = None
    if a.kinds:
        alias = {"quote": "quote_candidate", "profile": "profile_fact", "note": "stream_note"}
        kind_filter = {alias.get(k.strip(), k.strip()) for k in a.kinds.split(",")}
    def want(kind):
        return kind_filter is None or kind in kind_filter
    def cap(lst):
        return lst[:a.limit] if a.limit else lst

    cands = [c for c in by_id.values()
             if c.get("status") == "candidate" and c["id"] not in applied and in_window(c)]
    cutoff = (date.today() - timedelta(days=a.mature_days)).isoformat()
    ev  = cap(sorted([c for c in cands if c["kind"] == "event" and want("event")], key=lambda c: c["date_jst"]))
    qt  = cap(sorted([c for c in cands if c["kind"] == "quote_candidate" and want("quote_candidate") and c["date_jst"] <= cutoff], key=lambda c: c["date_jst"]))
    qt_young = [c for c in cands if c["kind"] == "quote_candidate" and want("quote_candidate") and c["date_jst"] > cutoff]
    cap_ = cap(sorted([c for c in cands if c["kind"] == "capability" and want("capability")], key=lambda c: c["date_jst"]))
    pf  = cap(sorted([c for c in cands if c["kind"] in ("profile_fact", "stream_note") and (want("profile_fact") or want("stream_note"))], key=lambda c: c["date_jst"]))
    props = jsonl_read(DATA / "ledger" / "proposals.jsonl")
    opens = [l for l in jsonl_read(DATA / "ledger" / "open.jsonl") if l.get("status") == "open"]
    new_opens = [l for l in opens if l["loop_id"] not in applied]

    rid = "RV_" + date.today().strftime("%Y%m%d")
    n = 1
    while (DATA / "review" / f"{rid}-{n:02d}.md").exists(): n += 1
    rid = f"{rid}-{n:02d}"
    L = [f"# レビューパケット {rid}",
         "",
         "記入方法: 実行してよい行の `[ ]` を `[x]` にする。未チェック＝保留（次回また出ます）。",
         "名言は **必ず試聴 → 「逐語:」行を書き直してから** VERIFY に [x]（ゲート1）。",
         "各カードの「補足:」行に書いた内容は、ADOPT採用時に handoff へ引き継がれ、wiki起草の材料になります（任意）。",
         ""]

    L.append(f"## A. 年表候補（event: {len(ev)}件）")
    for c in ev:
        L += [f"- [ ] ADOPT {c['id']}",
              f"      案: * {c['date_jst']}：{c.get('summary','')}{wikiref(c)}",
              f"      根拠発話(ASR): {c.get('text','')[:60]}",
              f"      出典: {c['source'].get('url','')}   ⚠試聴で発言確認",
              f"      補足: （任意。ここに書いた内容はhandoffに引き継がれ、wiki起草の材料になります）",
              f"- [ ] DROP {c['id']}", ""]

    L.append(f"## B. 名言・迷言候補（quote: {len(qt)}件 / 熟成待ち{len(qt_young)}件は次回以降）")
    for c in qt:
        L += [f"- [ ] VERIFY {c['id']}",
              f"      試聴: {c['source'].get('url','')}",
              f"      ASR : {fmt_quote(c)}",
              f"      逐語: （←試聴して正確に書き直す。掛け合いは【発話者】形式のまま）",
              f"      反応: " + " / ".join(as_str_list(c.get("evidence"))[:3]),
              f"      補足: （任意。文脈やニュアンスのメモ。handoffに引き継がれます）",
              f"- [ ] ADOPT {c['id']}   （逐語確定済みのものだけ）",
              f"- [ ] DROP {c['id']}", ""]

    L.append(f"## C. 機能カード候補（capability: {len(cap_)}件）")
    for c in cap_:
        L += [f"- [ ] ADOPT {c['id']}",
              f"      機能仮名: {c.get('feature_hint','?')} / {c.get('summary','')}",
              f"      証拠: " + " / ".join(as_str_list(c.get("evidence"))[:3]),
              f"      出典: {c['source'].get('url','')}   ⚠試聴で確認 → 採用後レジストリに追記",
              f"      補足: （任意。handoffに引き継がれます）",
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
        L += [f"- [ ] ADOPT {c['id']}   [{c['kind']}→{'/'.join(as_str_list(c.get('wiki_target')))}] {c.get('summary','')}",
              f"      出典: {c['source'].get('url','')}",
              f"      補足: （任意。handoffに引き継がれます）",
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
    # ※ここでは in_review に登録しない。処理済みマークは s5_apply が付ける。
    #   これにより「まだ処理していない候補」はパケットを作り直すたびに何度でも出る。
    print(f"生成: {out.relative_to(BASE)}")
    print(f"  年表{len(ev)} / 名言{len(qt)}(熟成待ち{len(qt_young)}) / 機能{len(cap_)} / 供給{len(pf)} / open確認{len(new_opens)} / クローズ提案{len(props)}")
    print("→ エディタで開いて試聴・チェック → python scripts/s5_apply.py --packet " + str(out.relative_to(BASE)))

if __name__ == "__main__":
    main()
