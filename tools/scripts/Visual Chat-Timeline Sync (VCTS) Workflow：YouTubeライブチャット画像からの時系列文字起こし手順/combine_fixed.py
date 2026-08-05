#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ライブチャット画像 横結合 + タイムスタンプ焼き込み（縦長/横長画像の混在対応）

通常のチャット画像は横方向に N 枚ずつ並べます。
極端に横長の字幕・テロップ画像は、縦方向に N 枚ずつ積みます。
画像は縦横比を保って配置するため、横長画像が縦に引き伸ばされません。

使い方:
  python combine_mixed.py --input ./thinned --output ./combined
  python combine_mixed.py --input ./thinned --output ./combined \
      --per-row 5 --wide-per-page 5 --interval 15 --start-sec 0

主な調整項目:
  --wide-threshold 3.0   幅/高さがこの値以上なら「横長」と判定
  --output-width 2048   出力画像の基準幅。0なら元画像サイズから自動決定
  --layout auto         auto / horizontal
"""

import argparse
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Sequence, Tuple

from PIL import Image, ImageDraw, ImageFont, ImageOps


# ============================================================
# 設定（引数なしで直接実行する場合はここを変更）
# ============================================================
INPUT_DIR = "./thinned"
OUTPUT_DIR = "./combined"
PER_ROW = 5
WIDE_PER_PAGE = 5
INTERVAL_SEC = 15
START_SEC = 0
SEP_WIDTH = 4
SEP_COLOR = (200, 200, 200)
LABEL_HEIGHT = 24
LABEL_BG = (30, 30, 30)
LABEL_FG = (255, 220, 50)
PANEL_BG = (20, 20, 20)
FONT_PATH = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"
FONT_SIZE = 14
WIDE_THRESHOLD = 3.0
OUTPUT_WIDTH = 2048  # 0 にすると入力画像から自動決定
JPEG_QUALITY = 95
# ============================================================


AISTUDIO_PROMPT = """\
各画像の上部には区画ごとのタイムスタンプが記載されています（例: [1:02:30]）。
これらはYouTubeライブチャットの画面を時系列順に並べたスナップショットです。

【読み取り順】
- 縦長チャット画像のページ: 左から右
- 横長字幕画像のページ: 上から下
- 出力ファイル名の番号順に処理する

以下のルールに従ってコメントを文字起こしてください。

【ルール】
- 各区画を独立した画面として読み取る
- 各コメントが「初めて画面に登場した」区画のタイムスタンプを先頭に付ける
- 同じコメントが複数の区画にまたがっていても1回だけ出力する（初出区画で処理）
- ユーザー名は @ を付けてそのまま記載する
- 読み取れない文字は [?] と記載する
- チャット以外のUI要素（バッジ・アイコン説明など）は出力しない

【出力形式】（1コメント1行）
[H:MM:SS] @ユーザー名: コメント本文"""


@dataclass(frozen=True)
class FrameInfo:
    index: int
    path: Path
    width: int
    height: int
    is_wide: bool


@dataclass(frozen=True)
class Page:
    kind: str  # "normal" or "wide"
    frames: Tuple[FrameInfo, ...]


def sec_to_hhmmss(sec: int) -> str:
    h = sec // 3600
    m = (sec % 3600) // 60
    s = sec % 60
    return f"{h}:{m:02d}:{s:02d}"


def natural_key(path: Path):
    """1, 2, 10 の順になる自然順ソート。"""
    parts = re.split(r"(\d+)", path.name.lower())
    return [int(part) if part.isdigit() else part for part in parts]


def most_common_size(frames: Sequence[FrameInfo]) -> Tuple[int, int]:
    if not frames:
        raise ValueError("サイズ判定対象の画像がありません")
    return Counter((f.width, f.height) for f in frames).most_common(1)[0][0]


def load_font(font_path: str, font_size: int):
    try:
        return ImageFont.truetype(font_path, font_size)
    except Exception:
        print(f"[WARN] フォントが読み込めません（{font_path}）。デフォルトフォントを使用します。")
        return ImageFont.load_default()


def inspect_images(input_path: Path, wide_threshold: float) -> List[FrameInfo]:
    exts = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}
    paths = sorted(
        (p for p in input_path.iterdir() if p.is_file() and p.suffix.lower() in exts),
        key=natural_key,
    )

    frames: List[FrameInfo] = []
    for path in paths:
        try:
            with Image.open(path) as img:
                img = ImageOps.exif_transpose(img)
                width, height = img.size
            if width <= 0 or height <= 0:
                raise ValueError("画像サイズが不正です")
        except Exception as exc:
            print(f"[WARN] 読み込めないためスキップ: {path.name} ({exc})")
            continue

        ratio = width / height
        frames.append(
            FrameInfo(
                index=len(frames),
                path=path,
                width=width,
                height=height,
                is_wide=(ratio >= wide_threshold),
            )
        )

    return frames


def split_pages(
    frames: Sequence[FrameInfo],
    per_row: int,
    wide_per_page: int,
    layout: str,
) -> List[Page]:
    """
    入力順を壊さずにページへ分割する。

    auto:
      通常画像は横並び、横長画像は縦積み。種類が切り替わる時点でページを確定。
    horizontal:
      すべて横並び。ただし画像は縦横比を保持してセル内に収める。
    """
    if layout == "horizontal":
        return [
            Page("normal", tuple(frames[i : i + per_row]))
            for i in range(0, len(frames), per_row)
        ]

    pages: List[Page] = []
    current_kind = None
    current: List[FrameInfo] = []

    def flush():
        nonlocal current, current_kind
        if current:
            pages.append(Page(current_kind, tuple(current)))
            current = []

    for frame in frames:
        kind = "wide" if frame.is_wide else "normal"
        limit = wide_per_page if kind == "wide" else per_row

        if current_kind is None:
            current_kind = kind

        if kind != current_kind or len(current) >= limit:
            flush()
            current_kind = kind

        current.append(frame)

    flush()
    return pages


def draw_timestamp(
    draw: ImageDraw.ImageDraw,
    x: int,
    y: int,
    width: int,
    label_height: int,
    sec: int,
    font,
    label_bg,
    label_fg,
):
    label = f"[{sec_to_hhmmss(sec)}]"
    draw.rectangle([x, y, x + width - 1, y + label_height - 1], fill=label_bg)

    bbox = draw.textbbox((0, 0), label, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    tx = x + (width - text_w) // 2
    ty = y + (label_height - text_h) // 2 - bbox[1]
    draw.text((tx, ty), label, font=font, fill=label_fg)


def fit_image(path: Path, target_w: int, target_h: int, background) -> Image.Image:
    """縦横比を保ったまま target_w x target_h に収め、余白を付ける。"""
    with Image.open(path) as src:
        src = ImageOps.exif_transpose(src).convert("RGB")
        contained = ImageOps.contain(src, (target_w, target_h), method=Image.Resampling.LANCZOS)

    cell = Image.new("RGB", (target_w, target_h), background)
    x = (target_w - contained.width) // 2
    y = (target_h - contained.height) // 2
    cell.paste(contained, (x, y))
    contained.close()
    return cell


def resize_to_width(path: Path, target_w: int) -> Image.Image:
    """縦横比を保って指定幅へリサイズする。"""
    with Image.open(path) as src:
        src = ImageOps.exif_transpose(src).convert("RGB")
        target_h = max(1, round(src.height * target_w / src.width))
        return src.resize((target_w, target_h), Image.Resampling.LANCZOS)


def determine_geometry(
    frames: Sequence[FrameInfo],
    per_row: int,
    sep_width: int,
    output_width: int,
) -> Tuple[int, int, int]:
    """通常画像のセル幅・高さとページ幅を決める。"""
    normal_frames = [f for f in frames if not f.is_wide]

    if normal_frames:
        ref_w, ref_h = most_common_size(normal_frames)
    else:
        # 横長画像だけの場合も、基準比率が必要な場面に備える
        ref_w, ref_h = most_common_size(frames)

    if output_width > 0:
        cell_w = max(1, (output_width - sep_width * (per_row - 1)) // per_row)
        # 指定幅は横長ページでは厳密に使用する。通常ページでは端数ぶんが
        # 右端のごく小さい余白になる場合がある。
        page_w = output_width
        cell_h = max(1, round(cell_w * ref_h / ref_w))
    else:
        cell_w, cell_h = ref_w, ref_h
        page_w = cell_w * per_row + sep_width * (per_row - 1)

    return cell_w, cell_h, page_w


def render_normal_page(
    page: Page,
    page_w: int,
    cell_w: int,
    cell_h: int,
    per_row: int,
    interval_sec: int,
    start_sec: int,
    sep_width: int,
    sep_color,
    label_height: int,
    label_bg,
    label_fg,
    panel_bg,
    font,
) -> Image.Image:
    # 種類の切り替わりや最終ページで枚数が少ない場合は、
    # 不要な空白セルを作らず実際の枚数ぶんだけの幅にする。
    used_page_w = cell_w * len(page.frames) + sep_width * max(0, len(page.frames) - 1)
    actual_page_w = page_w if len(page.frames) == per_row else used_page_w
    page_h = label_height + cell_h
    canvas = Image.new("RGB", (actual_page_w, page_h), label_bg)
    draw = ImageDraw.Draw(canvas)

    x = 0
    for panel_idx, frame in enumerate(page.frames):
        sec = start_sec + frame.index * interval_sec
        draw_timestamp(
            draw, x, 0, cell_w, label_height, sec, font, label_bg, label_fg
        )

        fitted = fit_image(frame.path, cell_w, cell_h, panel_bg)
        canvas.paste(fitted, (x, label_height))
        fitted.close()

        if panel_idx < len(page.frames) - 1:
            x += cell_w
            draw.rectangle(
                [x, 0, x + sep_width - 1, page_h - 1],
                fill=sep_color,
            )
            x += sep_width

    return canvas


def render_wide_page(
    page: Page,
    page_w: int,
    interval_sec: int,
    start_sec: int,
    sep_width: int,
    sep_color,
    label_height: int,
    label_bg,
    label_fg,
    font,
) -> Image.Image:
    resized: List[Tuple[FrameInfo, Image.Image]] = []
    try:
        for frame in page.frames:
            resized.append((frame, resize_to_width(frame.path, page_w)))

        page_h = sum(label_height + img.height for _, img in resized)
        page_h += sep_width * max(0, len(resized) - 1)

        canvas = Image.new("RGB", (page_w, page_h), label_bg)
        draw = ImageDraw.Draw(canvas)

        y = 0
        for idx, (frame, img) in enumerate(resized):
            sec = start_sec + frame.index * interval_sec
            draw_timestamp(
                draw, 0, y, page_w, label_height, sec, font, label_bg, label_fg
            )
            y += label_height
            canvas.paste(img, (0, y))
            y += img.height

            if idx < len(resized) - 1:
                draw.rectangle(
                    [0, y, page_w - 1, y + sep_width - 1],
                    fill=sep_color,
                )
                y += sep_width

        return canvas
    finally:
        for _, img in resized:
            img.close()


def combine_images(
    input_dir,
    output_dir,
    per_row,
    wide_per_page,
    interval_sec,
    start_sec,
    sep_width,
    sep_color,
    label_height,
    label_bg,
    label_fg,
    panel_bg,
    font_path,
    font_size,
    wide_threshold,
    output_width,
    layout,
    jpeg_quality,
):
    if per_row <= 0:
        raise ValueError("--per-row は1以上を指定してください")
    if wide_per_page <= 0:
        raise ValueError("--wide-per-page は1以上を指定してください")
    if interval_sec < 0:
        raise ValueError("--interval は0以上を指定してください")
    if wide_threshold <= 0:
        raise ValueError("--wide-threshold は0より大きい値を指定してください")
    if label_height <= 0:
        raise ValueError("--label-height は1以上を指定してください")
    if sep_width < 0:
        raise ValueError("--sep-width は0以上を指定してください")

    input_path = Path(input_dir)
    output_path = Path(output_dir)

    if not input_path.exists() or not input_path.is_dir():
        raise FileNotFoundError(f"入力フォルダが見つかりません: {input_path}")

    output_path.mkdir(parents=True, exist_ok=True)

    frames = inspect_images(input_path, wide_threshold)
    if not frames:
        print(f"[ERROR] 画像が見つかりません: {input_path}")
        return

    pages = split_pages(frames, per_row, wide_per_page, layout)
    cell_w, cell_h, page_w = determine_geometry(
        frames, per_row, sep_width, output_width
    )
    font = load_font(font_path, font_size)

    normal_count = sum(not f.is_wide for f in frames)
    wide_count = len(frames) - normal_count

    print(f"入力ファイル数       : {len(frames)} 枚")
    print(f"通常画像             : {normal_count} 枚")
    print(f"横長画像             : {wide_count} 枚  (判定: 幅/高さ >= {wide_threshold:g})")
    print(f"通常ページのセル     : {cell_w} x {cell_h} px")
    print(f"出力ページ幅         : {page_w} px")
    print(f"出力結合画像数       : {len(pages)} 枚")
    print(f"出力先               : {output_path.resolve()}")
    print("処理中...")

    for page_idx, page in enumerate(pages, start=1):
        if page.kind == "wide" and layout == "auto":
            canvas = render_wide_page(
                page=page,
                page_w=page_w,
                interval_sec=interval_sec,
                start_sec=start_sec,
                sep_width=sep_width,
                sep_color=sep_color,
                label_height=label_height,
                label_bg=label_bg,
                label_fg=label_fg,
                font=font,
            )
        else:
            canvas = render_normal_page(
                page=page,
                page_w=page_w,
                cell_w=cell_w,
                cell_h=cell_h,
                per_row=per_row,
                interval_sec=interval_sec,
                start_sec=start_sec,
                sep_width=sep_width,
                sep_color=sep_color,
                label_height=label_height,
                label_bg=label_bg,
                label_fg=label_fg,
                panel_bg=panel_bg,
                font=font,
            )

        out_name = output_path / f"combined_{page_idx:04d}.jpg"
        canvas.save(out_name, "JPEG", quality=jpeg_quality, subsampling=0)
        canvas.close()

        kind_label = "横長・縦積み" if page.kind == "wide" and layout == "auto" else "通常・横並び"
        print(
            f"  {page_idx}/{len(pages)}: {out_name.name} "
            f"({kind_label}, {len(page.frames)} 枚)"
        )

    print(f"\n完了: {len(pages)} 枚の結合画像を出力しました")
    print()
    print("=" * 60)
    print("【AI Studio に貼るプロンプト】")
    print("=" * 60)
    print(AISTUDIO_PROMPT)
    print("=" * 60)


def parse_color(s):
    try:
        parts = [int(x.strip()) for x in s.split(",")]
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            "色は R,G,B 形式で指定してください（例: 200,200,200）"
        ) from exc

    if len(parts) != 3 or any(not 0 <= value <= 255 for value in parts):
        raise argparse.ArgumentTypeError(
            "色は各値0～255の R,G,B 形式で指定してください（例: 200,200,200）"
        )
    return tuple(parts)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="横結合 + タイムスタンプ焼き込み（縦長/横長画像の混在対応）"
    )
    parser.add_argument("--input", default=INPUT_DIR, help="入力画像フォルダ")
    parser.add_argument("--output", default=OUTPUT_DIR, help="出力フォルダ")
    parser.add_argument(
        "--per-row", default=PER_ROW, type=int,
        help="通常画像を1ページに横並びする枚数（デフォルト: 5）",
    )
    parser.add_argument(
        "--wide-per-page", default=WIDE_PER_PAGE, type=int,
        help="横長画像を1ページに縦積みする枚数（デフォルト: 5）",
    )
    parser.add_argument(
        "--interval", default=INTERVAL_SEC, type=int,
        help="画像間隔 秒（デフォルト: 15）",
    )
    parser.add_argument(
        "--start-sec", default=START_SEC, type=int,
        help="開始オフセット 秒（デフォルト: 0）",
    )
    parser.add_argument(
        "--sep-width", default=SEP_WIDTH, type=int,
        help="区切り線の幅 px（デフォルト: 4）",
    )
    parser.add_argument(
        "--sep-color", default=SEP_COLOR, type=parse_color,
        help="区切り線の色 R,G,B",
    )
    parser.add_argument(
        "--label-height", default=LABEL_HEIGHT, type=int,
        help="タイムスタンプ帯の高さ px（デフォルト: 24）",
    )
    parser.add_argument(
        "--wide-threshold", default=WIDE_THRESHOLD, type=float,
        help="幅/高さがこの値以上なら横長画像（デフォルト: 3.0）",
    )
    parser.add_argument(
        "--output-width", default=OUTPUT_WIDTH, type=int,
        help="出力画像の基準幅 px。0なら自動（デフォルト: 2048）",
    )
    parser.add_argument(
        "--layout", choices=("auto", "horizontal"), default="auto",
        help="auto: 横長を縦積み / horizontal: 全画像を横並び",
    )
    parser.add_argument(
        "--font-path", default=FONT_PATH,
        help="タイムスタンプ用フォントファイル",
    )
    parser.add_argument(
        "--font-size", default=FONT_SIZE, type=int,
        help="タイムスタンプ文字サイズ",
    )
    parser.add_argument(
        "--jpeg-quality", default=JPEG_QUALITY, type=int,
        help="JPEG品質（デフォルト: 95）",
    )
    args = parser.parse_args()

    combine_images(
        input_dir=args.input,
        output_dir=args.output,
        per_row=args.per_row,
        wide_per_page=args.wide_per_page,
        interval_sec=args.interval,
        start_sec=args.start_sec,
        sep_width=args.sep_width,
        sep_color=args.sep_color,
        label_height=args.label_height,
        label_bg=LABEL_BG,
        label_fg=LABEL_FG,
        panel_bg=PANEL_BG,
        font_path=args.font_path,
        font_size=args.font_size,
        wide_threshold=args.wide_threshold,
        output_width=args.output_width,
        layout=args.layout,
        jpeg_quality=args.jpeg_quality,
    )
