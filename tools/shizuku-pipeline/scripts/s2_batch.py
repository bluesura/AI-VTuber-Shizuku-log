# -*- coding: utf-8 -*-
"""ステップ2の一括処理。data/llm_out/ に置いた抽出結果(JSONL)を全部まとめて取り込む。
ファイル名から取込先(--from)を自動判定するので、1つずつコマンドを打つ必要がない。

使い方:
  python scripts/s2_batch.py            # 何を取り込むか表示（ドライラン・書き込みなし）
  python scripts/s2_batch.py --apply    # 実際に全部取り込む + WORKLIST.md のチェックを自動更新
  python scripts/s2_batch.py --status   # llm_out の取込状況だけ表示

ファイル名の規約（s2_pack が付ける保存名と同じ）:
  extract_<date>_<vid>[_partN].jsonl   → stream:<vid>
  extract_x_<YYYY-MM>[_partN].jsonl    → x:<YYYY-MM>
判定できない名前は skip し、理由を表示する（手動で s2_ingest すればよい）。
判定は s2_ingest と同じロジックを呼ぶので、逐語検証・重複除外・台帳登録・日付補正は全部そのまま効く。
"""
import argparse, re, sys, io
from pathlib import Path
from contextlib import redirect_stdout
sys.path.insert(0, str(Path(__file__).parent))
from shizulib import DATA, read, write
import s2_ingest

STREAM_RE = re.compile(r"^extract_\d{4}-\d{2}-\d{2}_([A-Za-z0-9_-]{11})(?:_part\d+)?$")
X_RE      = re.compile(r"^extract_x_(\d{4}-\d{2})(?:_part\d+)?$")

def infer_from(stem):
    """保存名 stem から (mode, key, from文字列) を返す。判定不能なら None。"""
    m = STREAM_RE.match(stem)
    if m: return ("stream", m.group(1), f"stream:{m.group(1)}")
    m = X_RE.match(stem)
    if m: return ("x", m.group(1), f"x:{m.group(1)}")
    return None

def scan():
    """llm_out の *.jsonl を走査。judgments 等は除外。"""
    out = DATA / "llm_out"
    items = []
    if out.exists():
        for f in sorted(out.glob("*.jsonl")):
            if "judg" in f.name.lower(): continue      # 照合判定はStep3の担当
            items.append((f, infer_from(f.stem)))
    return items

def update_worklist(done_keys):
    """WORKLIST.md の該当行に [x] を付ける。done_keys = {'stream:vid'|'x:month', ...}"""
    wl = DATA / "packs" / "WORKLIST.md"
    if not wl.exists(): return 0
    lines = read(wl).splitlines()
    checked = 0
    for i, line in enumerate(lines):
        m = re.match(r"^- \[ \] ", line)
        if not m: continue
        # 直後の数行にある取込コマンドから from を拾う
        frm = None
        for j in range(i, min(i + 5, len(lines))):
            mm = re.search(r"--from (stream:[A-Za-z0-9_-]{11}|x:\d{4}-\d{2})", lines[j])
            if mm: frm = mm.group(1); break
        if frm and frm in done_keys:
            lines[i] = line.replace("- [ ] ", "- [x] ", 1); checked += 1
    write(wl, "\n".join(lines) + "\n")
    return checked

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--status", action="store_true")
    a = ap.parse_args()
    items = scan()
    if not items:
        print("data/llm_out/ に取り込めるJSONLがありません（judgments_* は対象外）。"); return

    ok = [(f, inf) for f, inf in items if inf]
    bad = [f for f, inf in items if not inf]

    if a.status or not a.apply:
        print(f"llm_out の抽出結果: {len(items)}ファイル（取込可 {len(ok)} / 判定不能 {len(bad)}）")
        for f, inf in ok:
            print(f"  [取込可] {f.name}  → --from {inf[2]}")
        for f in bad:
            print(f"  [不能  ] {f.name}  ← 名前から判定できず（手動で s2_ingest してください）")
        if not a.apply:
            print("\nこれはドライランです。実際に取り込むには: python scripts/s2_batch.py --apply")
        return

    # 実行: s2_ingest を1件ずつ呼ぶ（sys.argv を組み替えて main を再利用）
    done_keys, totals = set(), {"取込": 0, "重複スキップ": 0, "破棄": 0}
    for f, inf in ok:
        mode, key, frm = inf
        print(f"\n──── {f.name}  (--from {frm}) ────")
        argv_bak = sys.argv[:]
        sys.argv = ["s2_ingest.py", "--file", str(f), "--from", frm]
        buf = io.StringIO()
        try:
            with redirect_stdout(buf):
                s2_ingest.main()
        finally:
            sys.argv = argv_bak
        out = buf.getvalue()
        print(out, end="")
        done_keys.add(frm)
        m = re.search(r"取込: (\d+)枚", out)
        if m: totals["取込"] += int(m.group(1))
        totals["重複スキップ"] += out.count("重複 →") + out.count("重複 → スキップ")
        totals["破棄"] += out.count("→ 破棄")

    checked = update_worklist(done_keys)
    for f in bad:
        print(f"\n[SKIP] {f.name} は名前から取込先を判定できませんでした。手動で: "
              f"python scripts/s2_ingest.py --file {Path('data/llm_out')/f.name} --from stream:<vid>|x:<month>")
    print("\n========== 一括取込のまとめ ==========")
    print(f"  取込ファイル: {len(ok)} / カード合計: {totals['取込']}枚 "
          f"(重複スキップ {totals['重複スキップ']} / 破棄 {totals['破棄']})")
    print(f"  WORKLIST.md のチェック更新: {checked}行")
    print("次: python scripts/s3_match.py  （台帳との照合）")

if __name__ == "__main__":
    main()
