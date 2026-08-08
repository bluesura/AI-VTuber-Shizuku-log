# -*- coding: utf-8 -*-
"""doctor: データ不備の検査ツール（本工程とは独立に、いつでも実行できる）。
使い方:  python scripts/doctor.py
出力:    data/review/doctor_report.md（各所見に DATA-ISSUES.md の該当節を付す）
検査項目: D01 JST日跨ぎ / D02 ASR固有名詞 / D03 ノイズ・断片 / D04 字幕盲点(非言語音候補) /
          D05 ソース網羅 / D06 期間ギャップ・空ファイル / D07 ファイル完全性 / D10 チャット時刻
"""
import json, re, sys
from collections import Counter
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from shizulib import *

def main():
    R = ["# doctor レポート", ""]
    sev = {"ERROR": 0, "WARN": 0, "INFO": 0}
    def add(level, code, msg):
        sev[level] += 1
        R.append(f"- **[{level}] {code}** {msg}")

    # --- D07 ファイル完全性 ---
    R.append("## D07 ファイル完全性（→ DATA-ISSUES.md §7）")
    need = ["sbv.txt", "chat.txt", "info.txt", "comments.txt"]
    for d in stream_dirs():
        miss = [f for f in need if not (d / f).exists()]
        if miss: add("ERROR", "D07", f"{d.name}: 不足 {','.join(miss)}")
        for f in need:
            p = d / f
            if p.exists():
                try:
                    p.read_text(encoding="utf-8")
                except UnicodeDecodeError:
                    add("WARN", "D07", f"{d.name}/{f}: UTF-8で読めない文字あり（errors=replaceで続行される）")
    if sev["ERROR"] + sev["WARN"] == 0: R.append("- 問題なし")
    R.append("")

    # --- 配信ごとの検査 ---
    R.append("## D02/D03/D04/D10 配信ログ検査")
    fixes = load_fixes()
    for d in stream_dirs():
        vid = d.name.split("_", 1)[1]
        nd = DATA / "normalized" / "streams" / vid
        R.append(f"### {d.name}")
        blocks = parse_sbv(d / "sbv.txt") if (d / "sbv.txt").exists() else []
        chat = parse_chat(d / "chat.txt") if (d / "chat.txt").exists() else []
        if not blocks:
            add("ERROR", "D07", "字幕ブロックが0件"); continue
        # D03 ノイズ率・断片
        noise = sum(1 for _, t in blocks if NOISE_RE.search(t))
        sents = rejoin_sentences(blocks)
        junk = sum(1 for _, s in sents if len(NOISE_RE.sub("", s)) <= 2)
        add("INFO", "D03", f"[音楽]等ノイズ: {noise}/{len(blocks)}ブロック ({100*noise//max(1,len(blocks))}%) / "
                           f"再結合: {len(blocks)}→{len(sents)}文 / 極短文(ゴミ候補): {junk}")
        # D02 辞書ヒット + 未登録候補（字幕頻出なのにチャットに現れない語）
        joined = "".join(s for _, s in sents)
        hits = {w: joined.count(w) for w, _ in fixes if joined.count(w)}
        if hits:
            add("WARN", "D02", "辞書対象の誤記が残存(正規化層では補正済み): " +
                " ".join(f"{w}×{c}" for w, c in hits.items()) + " → §2")
        ctext = "".join(tx for _, _, tx in chat)
        stok = Counter(re.findall(r"[一-龥]{2,4}|[ァ-ヴー]{3,6}", joined))
        cand = [(w, c) for w, c in stok.most_common(400)
                if c >= 5 and w not in ctext and not any(w == a or w == b for a, b in fixes)]
        if cand:
            add("INFO", "D02", "ASR崩れの可能性がある頻出語（チャットに一度も出ない）: " +
                " ".join(f"{w}×{c}" for w, c in cand[:10]) + " …辞書追加は人間判断で（ゲート3）")
        # D04 字幕盲点
        if (nd / "signals.json").exists():
            s = json.loads(read(nd / "signals.json"))
            mm = s.get("asr_silent_chat_dense", [])
            if mm:
                add("INFO", "D04", "字幕沈黙×チャット密集（非言語音イベント候補・仕様であり不備ではない）: " +
                    " / ".join(m["mmss"] for m in mm[:6]) + " → §4")
        # D10 チャット時刻
        neg = sum(1 for t, _, _ in chat if t < 0)
        desc = sum(1 for i in range(1, len(chat)) if chat[i][0] < chat[i-1][0] - 1)
        add("INFO", "D10", f"チャット: {len(chat)}件 / 開始前(負時刻): {neg}件 / 時刻逆行: {desc}箇所")
        R.append("")

    # --- Xログ ---
    R.append("## D01/D05/D06 Xログ検査")
    xr = DATA / "raw" / "x"
    invalid = []
    for f in sorted(xr.glob("*")):
        txt = read(f)
        if not txt.strip() or "URL" not in txt.splitlines()[0]:
            invalid.append(f.name)
    if invalid:
        add("WARN", "D06", f"TSVとして読めないXログ: {', '.join(invalid)} （「なし」等の空記録。休眠期なら正常 → §6）")
    months, authors, cross = {}, Counter(), 0
    for p in sorted((DATA / "normalized" / "x").glob("*.jsonl")):
        recs = jsonl_read(p)
        months[p.stem] = len(recs)
        for r in recs:
            authors[r.get("author", "?")] += 1
            if r.get("date_utc") and r["date_utc"] != r["date_jst"]: cross += 1
    total = sum(months.values())
    if total:
        add("INFO", "D01", f"UTC→JSTで日付が変わったポスト: {cross}/{total}件 ({100*cross//total}%) — s1で変換済み → §1")
        add("INFO", "D05", "投稿者の内訳: " + " ".join(f"{a}:{c}" for a, c in authors.most_common(3)) +
            " ｜ あき先生アカ(@cumulo_autumn)と報道は別経路で収集が必要 → §5")
        ms = sorted(months)
        gaps = []
        if ms:
            y0, m0 = map(int, ms[0].split("-")); y1, m1 = map(int, ms[-1].split("-"))
            cur = y0 * 12 + m0 - 1
            end = y1 * 12 + m1 - 1
            while cur <= end:
                key = f"{cur//12}-{cur%12+1:02d}"
                if key not in months: gaps.append(key)
                cur += 1
        if gaps: add("WARN", "D06", f"ポスト0件の月: {', '.join(gaps)} （取得漏れか休眠かを確認 → §6）")
        R.append("  月別件数: " + " / ".join(f"{m}:{c}" for m, c in sorted(months.items())))
    R.append("")
    R.append(f"---\n集計: ERROR {sev['ERROR']} / WARN {sev['WARN']} / INFO {sev['INFO']}")
    R.append("各所見の意味と対処は DATA-ISSUES.md を参照。")
    out = DATA / "review" / "doctor_report.md"
    write(out, "\n".join(R) + "\n")
    print(f"レポート生成: {out.relative_to(BASE)}   (ERROR {sev['ERROR']} / WARN {sev['WARN']} / INFO {sev['INFO']})")

if __name__ == "__main__":
    main()
