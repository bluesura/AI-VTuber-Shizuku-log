"""
ライブチャット画像 横結合 + タイムスタンプ焼き込みスクリプト
--------------------------------------------------------------
間引き済み画像を N 枚ずつ横に並べて結合し、
各パネル上部にタイムスタンプラベルを焼き込む。

使い方:
  python combine.py --input ./thinned --output ./combined
  python combine.py --input ./thinned --output ./combined --per-row 5 --interval 15 --start-sec 0
"""

import argparse
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

# ============================================================
#  設定（引数なしで直接実行する場合はここを変更）
# ============================================================
INPUT_DIR    = "./thinned"      # 間引き済み画像フォルダ
OUTPUT_DIR   = "./combined"     # 出力フォルダ
PER_ROW      = 5                # 1枚の結合画像に何フレーム並べるか
INTERVAL_SEC = 15               # 間引き間隔（秒）
START_SEC    = 0                # 動画の開始オフセット（秒）
SEP_WIDTH    = 4                # 区切り線の幅（px）
SEP_COLOR    = (200, 200, 200)  # 区切り線の色（R,G,B）
LABEL_HEIGHT = 24               # ラベル帯の高さ（px）
LABEL_BG     = (30, 30, 30)     # ラベル背景色
LABEL_FG     = (255, 220, 50)   # ラベル文字色（黄色で視認性◎）
FONT_PATH    = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"
FONT_SIZE    = 14
# ============================================================

AISTUDIO_PROMPT = """\
各画像の上部には区画ごとのタイムスタンプが記載されています（例: [1:02:30]）。
これらはYouTubeライブチャットの画面を時系列順に横に並べたスナップショットです。

以下のルールに従ってコメントを文字起こしてください。

【ルール】
- 縦線で区切られた各区画を左から順に独立したチャット画面として読み取る
- 各コメントが「初めて画面に登場した」区画のタイムスタンプを先頭に付ける
- 同じコメントが複数の区画にまたがっていても1回だけ出力する（初出区画で処理）
- ユーザー名は @ を付けてそのまま記載する
- 読み取れない文字は [?] と記載する
- チャット以外のUI要素（バッジ・アイコン説明など）は出力しない

【出力形式】（1コメント1行）
[H:MM:SS] @ユーザー名: コメント本文"""


def sec_to_hhmmss(sec: int) -> str:
    h = sec // 3600
    m = (sec % 3600) // 60
    s = sec % 60
    return f"{h}:{m:02d}:{s:02d}"


def combine_images(input_dir, output_dir, per_row, interval_sec, start_sec,
                   sep_width, sep_color, label_height, label_bg, label_fg,
                   font_path, font_size):

    input_path  = Path(input_dir)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    exts  = {".jpg", ".jpeg", ".png", ".webp"}
    files = sorted([f for f in input_path.iterdir() if f.suffix.lower() in exts])

    if not files:
        print(f"[ERROR] 画像が見つかりません: {input_path}")
        return

    # フォント読み込み
    try:
        font = ImageFont.truetype(font_path, font_size)
    except Exception:
        print(f"[WARN] フォントが読み込めません（{font_path}）。デフォルトフォントを使用します。")
        font = ImageFont.load_default()

    # 基準サイズを先頭画像から取得
    sample = Image.open(files[0])
    frame_w, frame_h = sample.size
    sample.close()

    combined_w = frame_w * per_row + sep_width * (per_row - 1)
    combined_h = label_height + frame_h

    total       = len(files)
    batch_count = (total + per_row - 1) // per_row

    print(f"入力ファイル数    : {total} 枚")
    print(f"1結合画像あたり   : {per_row} フレーム")
    print(f"出力結合画像数    : {batch_count} 枚")
    print(f"1枚のサイズ       : {combined_w} x {combined_h} px  (ラベル {label_height}px + チャット {frame_h}px)")
    print(f"出力先            : {output_path.resolve()}")
    print("処理中...")

    for batch_idx in range(batch_count):
        batch_files = files[batch_idx * per_row : (batch_idx + 1) * per_row]
        base_frame  = batch_idx * per_row

        canvas = Image.new("RGB", (combined_w, combined_h), label_bg)
        draw   = ImageDraw.Draw(canvas)

        x_offset = 0
        for panel_idx, fpath in enumerate(batch_files):

            # ---- タイムスタンプラベル描画 ----
            sec   = start_sec + (base_frame + panel_idx) * interval_sec
            label = f"[{sec_to_hhmmss(sec)}]"

            draw.rectangle(
                [x_offset, 0, x_offset + frame_w - 1, label_height - 1],
                fill=label_bg,
            )

            bbox   = draw.textbbox((0, 0), label, font=font)
            text_w = bbox[2] - bbox[0]
            text_h = bbox[3] - bbox[1]
            tx = x_offset + (frame_w - text_w) // 2
            ty = (label_height - text_h) // 2
            draw.text((tx, ty), label, font=font, fill=label_fg)

            # ---- チャット画像を貼り付け ----
            img = Image.open(fpath).convert("RGB")
            if img.size != (frame_w, frame_h):
                img = img.resize((frame_w, frame_h), Image.LANCZOS)
            canvas.paste(img, (x_offset, label_height))
            img.close()

            # ---- 区切り線（最後のパネル以外）----
            if panel_idx < len(batch_files) - 1:
                x_offset += frame_w
                draw.rectangle(
                    [x_offset, 0, x_offset + sep_width - 1, combined_h - 1],
                    fill=sep_color,
                )
                x_offset += sep_width

        out_name = output_path / f"combined_{batch_idx + 1:04d}.jpg"
        canvas.save(out_name, "JPEG", quality=95)
        canvas.close()

        if (batch_idx + 1) % 10 == 0 or (batch_idx + 1) == batch_count:
            print(f"  {batch_idx + 1}/{batch_count} 枚完了")

    print(f"\n完了: {batch_count} 枚の結合画像を出力しました")
    print()
    print("=" * 60)
    print("【AI Studio に貼るプロンプト（これ1つで全画像に対応）】")
    print("=" * 60)
    print(AISTUDIO_PROMPT)
    print("=" * 60)


# ============================================================

def parse_color(s):
    parts = [int(x.strip()) for x in s.split(",")]
    if len(parts) != 3:
        raise argparse.ArgumentTypeError("色は R,G,B 形式で指定してください（例: 200,200,200）")
    return tuple(parts)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="横結合 + タイムスタンプ焼き込みスクリプト")
    parser.add_argument("--input",        default=INPUT_DIR,     help="間引き済み画像フォルダ")
    parser.add_argument("--output",       default=OUTPUT_DIR,    help="出力フォルダ")
    parser.add_argument("--per-row",      default=PER_ROW,      type=int,         help="パネル数（デフォルト: 5）")
    parser.add_argument("--interval",     default=INTERVAL_SEC, type=int,         help="間引き間隔 秒（デフォルト: 15）")
    parser.add_argument("--start-sec",    default=START_SEC,    type=int,         help="開始オフセット 秒（デフォルト: 0）")
    parser.add_argument("--sep-width",    default=SEP_WIDTH,    type=int,         help="区切り線の幅 px（デフォルト: 4）")
    parser.add_argument("--sep-color",    default="200,200,200",type=parse_color, help="区切り線の色 R,G,B")
    parser.add_argument("--label-height", default=LABEL_HEIGHT, type=int,         help="ラベル帯の高さ px（デフォルト: 24）")
    args = parser.parse_args()

    combine_images(
        input_dir    = args.input,
        output_dir   = args.output,
        per_row      = args.per_row,
        interval_sec = args.interval,
        start_sec    = args.start_sec,
        sep_width    = args.sep_width,
        sep_color    = args.sep_color,
        label_height = args.label_height,
        label_bg     = LABEL_BG,
        label_fg     = LABEL_FG,
        font_path    = FONT_PATH,
        font_size    = FONT_SIZE,
    )
