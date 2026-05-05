"""
ライブチャット画像 間引きスクリプト
--------------------------------------
流速: 12秒で2行 → 安全間引き間隔: 10秒(フレーム)に1枚
3800枚 → 約380枚

使い方:
  python thinning.py --input ./frames --output ./thinned
  python thinning.py --input ./frames --output ./thinned --interval 10
"""

import os
import shutil
import argparse
from pathlib import Path

# ============================================================
#  設定（引数なしで直接実行する場合はここを変更）
# ============================================================
INPUT_DIR  = "./frames"      # 元画像フォルダ
OUTPUT_DIR = "./thinned"     # 出力フォルダ
INTERVAL   = 10              # 何フレームに1枚残すか（1枚=1秒想定）
# ============================================================

def thin_images(input_dir: str, output_dir: str, interval: int):
    input_path  = Path(input_dir)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # 画像ファイルをソート取得（jpg / png 両対応）
    exts = {".jpg", ".jpeg", ".png", ".webp"}
    files = sorted([f for f in input_path.iterdir() if f.suffix.lower() in exts])

    if not files:
        print(f"[ERROR] 画像が見つかりません: {input_path}")
        return

    total   = len(files)
    picked  = [f for i, f in enumerate(files) if i % interval == 0]
    count   = len(picked)

    print(f"元ファイル数  : {total} 枚")
    print(f"間引き間隔    : {interval} フレームに1枚")
    print(f"出力ファイル数: {count} 枚")
    print(f"出力先        : {output_path.resolve()}")
    print("処理中...")

    for idx, src in enumerate(picked):
        # ゼロ埋め連番でリネームしてコピー（例: 00001.jpg）
        ext  = src.suffix.lower()
        dest = output_path / f"{idx+1:05d}{ext}"
        shutil.copy2(src, dest)

    print(f"完了: {count} 枚を出力しました")

# ----------------------------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ライブチャット画像 間引きスクリプト")
    parser.add_argument("--input",    default=INPUT_DIR,  help="元画像フォルダ")
    parser.add_argument("--output",   default=OUTPUT_DIR, help="出力フォルダ")
    parser.add_argument("--interval", default=INTERVAL, type=int,
                        help="何フレームに1枚残すか（デフォルト: 10）")
    args = parser.parse_args()

    thin_images(args.input, args.output, args.interval)
