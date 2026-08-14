# -*- coding: utf-8 -*-
"""s3_match の「照合済みペア」記録(match_seen.json)をリセットするツール。
巨大な照合を一度実行してしまい、全ペアが判定済み扱いになって先へ進めないときに使う。
使い方:
  python scripts/s3_reset.py            # 現状を表示（変更なし）
  python scripts/s3_reset.py --apply    # match_seen をクリア（.bak を残す）
注意: これは「どのペアを既に短リストに出したか」の記録だけを消す。
  カード・台帳・確定済みのクローズ提案には一切触れない。安全にやり直せる。
"""
import argparse, json, shutil, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from shizulib import DATA, load_state, save_state, jsonl_read

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()
    seen = load_state("match_seen.json", [])
    opens = [l for l in jsonl_read(DATA / "ledger" / "open.jsonl") if l.get("status") == "open"]
    props = jsonl_read(DATA / "ledger" / "proposals.jsonl")
    print(f"照合済みペア記録: {len(seen)}件")
    print(f"未回収ループ(open): {len(opens)}件 / 未確認のクローズ提案: {len(props)}件")
    if not a.apply:
        print("\nこれはドライランです。match_seen をクリアするには: python scripts/s3_reset.py --apply")
        print("（カード・台帳・提案は消えません。次回 s3_match で最初から短リストを出し直せます）")
        return
    p = DATA / "state" / "match_seen.json"
    if p.exists():
        shutil.copy(p, p.with_suffix(".json.bak"))
    save_state("match_seen.json", [])
    print("\nmatch_seen をクリアしました（元は match_seen.json.bak に保存）。")
    print("次: python scripts/s3_match.py --status   → その後 --until で区切って照合")

if __name__ == "__main__":
    main()
