# -*- coding: utf-8 -*-
"""既に取り込み済みのカードを正規化して修復するツール。
LLMが evidence/wiki_target を dict や入れ子で返したせいで、後段（s3/s4）が落ちる場合に使う。
使い方:
  python scripts/repair_cards.py            # 何を直すか表示（書き込みなし・ドライラン）
  python scripts/repair_cards.py --apply    # 実際に修復して保存
やること:
  - 全カードの evidence / wiki_target を必ず「文字列のリスト」に整える
  - guess が dict/list なら文字列化
  - 台帳(open/closed) の text / expected_signal が非文字列なら文字列化
元のファイルは --apply 時に .bak を作ってから上書きする。
"""
import argparse, sys, shutil
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from shizulib import *

def needs_fix(v):
    if v is None: return False
    if isinstance(v, list): return any(not isinstance(x, str) for x in v)
    return not isinstance(v, str)  # str以外（dict/数値等）は要修復

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()
    fixes = []

    # カード庫
    for f in all_card_files():
        cards = jsonl_read(f); changed = False
        for c in cards:
            for field in ("evidence", "wiki_target"):
                if needs_fix(c.get(field)):
                    fixes.append(f"{f.name}:{c.get('id','?')} {field}={c.get(field)!r} → 文字列化")
                    c[field] = as_str_list(c.get(field)); changed = True
            if isinstance(c.get("guess"), (dict, list)):
                fixes.append(f"{f.name}:{c.get('id','?')} guess を文字列化")
                c["guess"] = flat_text(c.get("guess")); changed = True
        if changed and a.apply:
            shutil.copy(f, f.with_suffix(f.suffix + ".bak"))
            jsonl_write(f, cards)

    # 台帳
    for name in ("open.jsonl", "closed.jsonl"):
        p = DATA / "ledger" / name
        if not p.exists(): continue
        loops = jsonl_read(p); changed = False
        for lo in loops:
            for field in ("text", "expected_signal"):
                if needs_fix(lo.get(field)) and lo.get(field) is not None:
                    fixes.append(f"{name}:{lo.get('loop_id','?')} {field} を文字列化")
                    lo[field] = flat_text(lo.get(field)); changed = True
        if changed and a.apply:
            shutil.copy(p, p.with_suffix(p.suffix + ".bak"))
            jsonl_write(p, loops)

    if not fixes:
        print("修復の必要はありません（全カード・台帳とも正常な形です）。"); return
    print(f"修復対象 {len(fixes)}件:")
    for x in fixes[:40]: print("  -", x)
    if len(fixes) > 40: print(f"  … 他 {len(fixes)-40}件")
    if a.apply:
        print("\n修復して保存しました（元ファイルは .bak として残しています）。")
        print("次: python scripts/s3_match.py")
    else:
        print("\nこれはドライランです。実際に直すには: python scripts/repair_cards.py --apply")

if __name__ == "__main__":
    main()
