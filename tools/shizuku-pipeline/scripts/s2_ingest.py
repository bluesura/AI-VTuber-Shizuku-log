# -*- coding: utf-8 -*-
"""ステップ2b: Claudeが出力したカードJSONLを検証してカード庫に取り込む。
使い方:
  python scripts/s2_ingest.py --file <カードJSONL> --from stream:<vid>
  python scripts/s2_ingest.py --file <カードJSONL> --from x:<YYYY-MM>
やること:
  - JSONLの寛容パース（コードフェンス等は無視）
  - スキーマ検査 / 逐語ルールの機械検証:
      * yt由来 → verbatim は強制false（ゲート1: 逐語は人間の試聴でしか確定しない）
      * チャット/X由来 → 原文照合。原文に無い文字列なら verbatim=false に落として警告
  - 安定ID付与・重複除外 → data/cards/{YYYY-MM}.jsonl へ追記
  - open_loop は data/ledger/open.jsonl にも登録
"""
import argparse, json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from shizulib import *

VALID_KINDS = {"event", "quote_candidate", "open_loop", "capability", "profile_fact", "stream_note"}
LOOP_TYPES = {"目標宣言", "願望", "不能表明", "予告・約束", "過去参照", "定型ネタ", "関係マーカー"}

def load_chat_index(vid):
    p = DATA / "normalized" / "streams" / vid / "chat.tsv"
    idx = []
    if p.exists():
        for row in read(p).splitlines()[1:]:
            c = row.split("\t", 3)
            if len(c) >= 4: idx.append((int(c[0]), c[3]))
    return idx

def load_x_index(month):
    p = DATA / "normalized" / "x" / f"{month}.jsonl"
    return {r["post_id"]: r for r in jsonl_read(p)} if p.exists() else {}

def verify_chat_text(idx, t, text):
    if not text: return False
    for ct, ctext in idx:
        if abs(ct - (t or 0)) <= 60 and (text in ctext or ctext in text and len(ctext) >= 6):
            return True
    return any(text in ctext for _, ctext in idx)  # 時刻ずれ救済（全体照合）

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", required=True)
    ap.add_argument("--from", dest="src", required=True, help="stream:<vid> か x:<YYYY-MM>")
    a = ap.parse_args()
    mode, key = a.src.split(":", 1)
    raw = jsonl_read(a.file)
    if not raw:
        print("カードが読めませんでした"); return

    chat_idx = load_chat_index(key) if mode == "stream" else []
    x_idx = load_x_index(key) if mode == "x" else {}
    by_id, _ = load_all_cards()
    warns, add, loops = [], [], []

    for i, c in enumerate(raw, 1):
        kind = c.get("kind")
        if kind not in VALID_KINDS:
            warns.append(f"{i}行目: kind不正 '{kind}' → 破棄"); continue
        src = c.get("source") or {}
        # source補完
        if mode == "stream":
            src.setdefault("type", "yt"); src.setdefault("video_id", key)
            if src.get("t") is not None: src["url"] = yt_url(src["video_id"], src["t"])
            base = f"yt-{src['video_id']}-t{src.get('t','x')}"
        else:
            src.setdefault("type", "x")
            base = f"x-{src.get('post_id','unknown')}"
            if src.get("post_id") in x_idx: src.setdefault("url", x_idx[src["post_id"]]["url"])
        c["source"] = src
        # 逐語ルールの機械検証（ゲート1の前段）
        def check_part(text, claimed):
            if mode == "stream":
                if src.get("type") == "yt" and claimed and not verify_chat_text(chat_idx, src.get("t"), text):
                    return False, "yt由来のverbatim=trueをfalseへ（試聴で確定するまで逐語扱いしない）"
                if claimed and verify_chat_text(chat_idx, src.get("t"), text): return True, None
                if claimed: return False, "チャット原文と一致せず → verbatim=false"
                return False, None
            else:
                rec = x_idx.get(src.get("post_id"))
                pool = ((rec.get("text","") + "\n" + rec.get("quote_text","")) if rec
                        else "\n".join(r["text"] + "\n" + (r.get("quote_text") or "") for r in x_idx.values()))
                if text and text in pool: return True, None
                return False, "X原文と一致せず → verbatim=false"
        if c.get("parts"):
            for p_ in c["parts"]:
                ok, w = check_part(p_.get("text",""), p_.get("verbatim", False))
                p_["verbatim"] = ok
                if w: warns.append(f"{i}行目({kind}): {w}")
            c["verbatim"] = all(p_.get("verbatim") for p_ in c["parts"])
        else:
            ok, w = check_part(c.get("text",""), c.get("verbatim", False))
            c["verbatim"] = ok if mode == "x" else (ok and src.get("type") != "yt")
            if src.get("type") == "yt" and c.get("verbatim"): c["verbatim"] = False
            if w: warns.append(f"{i}行目({kind}): {w}")
        if kind == "open_loop":
            if c.get("loop_type") not in LOOP_TYPES:
                warns.append(f"{i}行目: loop_type不正 '{c.get('loop_type')}' → 破棄"); continue
            if not c.get("expected_signal"):
                warns.append(f"{i}行目: expected_signal欠落 → 破棄"); continue
        if not c.get("date_jst"):
            warns.append(f"{i}行目: date_jst欠落 → 破棄"); continue
        # 安定ID・状態
        body = c.get("text") or json.dumps(c.get("parts", ""), ensure_ascii=False)
        c["id"] = f"{base}-{kind[:2]}{sha8(kind + body)[:6]}"
        c.setdefault("status", "candidate")
        if c["id"] in by_id:
            warns.append(f"{i}行目: 既存カード {c['id']} と重複 → スキップ"); continue
        by_id[c["id"]] = c
        add.append(c)
        if kind == "open_loop":
            loops.append({"loop_id": c["id"], "opened": c["date_jst"], "loop_type": c["loop_type"],
                          "text": c.get("text",""), "expected_signal": c["expected_signal"],
                          "antecedent_hint": c.get("antecedent_hint"),
                          "source": src, "status": "open"})
    # 保存（date_jstの月ごと）
    months = {}
    for c in add: months.setdefault(c["date_jst"][:7], []).append(c)
    for m, cs in months.items(): jsonl_append(DATA / "cards" / f"{m}.jsonl", cs)
    if loops: jsonl_append(DATA / "ledger" / "open.jsonl", loops)

    kinds = {}
    for c in add: kinds[c["kind"]] = kinds.get(c["kind"], 0) + 1
    print(f"取込: {len(add)}枚 " + " ".join(f"{k}:{v}" for k, v in sorted(kinds.items())))
    if loops: print(f"台帳open登録: {len(loops)}件")
    for w in warns: print("  ⚠ " + w)
    print("\n次: python scripts/s3_match.py  （台帳との照合）")

if __name__ == "__main__":
    main()
