# -*- coding: utf-8 -*-
"""ステップ0: 取り込み。生ログを data/raw/ に規定の形で配置する。
使い方:  python scripts/s0_intake.py --src <ログのあるフォルダ>
- 配信ログ4点セット(_ja_sbv/_live_chat/_info/_comments) → data/raw/streams/{日付}_{動画ID}/
- Xログ(TSV) → data/raw/x/
- 元ファイルはコピーのみ（変更しない）
"""
import argparse, re, shutil, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from shizulib import DATA, read

KIND_MAP = {"ja_sbv": "sbv.txt", "live_chat": "chat.txt", "info": "info.txt", "comments": "comments.txt"}
STREAM_RE = re.compile(r"^(\d{4}-\d{2}-\d{2}).*?([A-Za-z0-9_-]{11})_(ja_sbv|live_chat|info|comments)\.txt$")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True, help="取り込み元フォルダ")
    a = ap.parse_args()
    src = Path(a.src)
    streams, xfiles, skipped = {}, [], []

    for f in sorted(src.iterdir()):
        if not f.is_file(): continue
        m = STREAM_RE.match(f.name)
        if m:
            date, vid, kind = m.groups()
            streams.setdefault((date, vid), {})[kind] = f
        elif re.match(r"^\d{4}", f.name) and f.suffix == ".txt":
            xfiles.append(f)
        else:
            skipped.append(f.name)

    print("=== 配信ログ ===")
    for (date, vid), files in sorted(streams.items()):
        dst = DATA / "raw" / "streams" / f"{date}_{vid}"
        dst.mkdir(parents=True, exist_ok=True)
        got = []
        for kind, fname in KIND_MAP.items():
            if kind in files:
                if not (dst / fname).exists():
                    shutil.copy(files[kind], dst / fname)
                got.append(kind)
        missing = [k for k in KIND_MAP if k not in got]
        mark = "OK " if not missing else "欠落"
        print(f"  [{mark}] {date}_{vid}  取得: {','.join(got)}" + (f"  ※不足: {','.join(missing)}" if missing else ""))

    print("=== Xログ ===")
    for f in xfiles:
        dst = DATA / "raw" / "x" / f.name
        if not dst.exists():
            shutil.copy(f, dst)
        head = read(f).splitlines()[0] if read(f).strip() else ""
        valid = ("URL" in head and "日付" in head)
        print(f"  [{'OK ' if valid else '不正'}] {f.name}" + ("" if valid else "  ※TSVヘッダが無い（doctor.py で詳細確認）"))

    if skipped:
        print("=== 認識できなかったファイル ===")
        for n in skipped: print("  -", n)
    print("\n次: python scripts/s1_normalize.py --all")

if __name__ == "__main__":
    main()
