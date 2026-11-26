#!/usr/bin/env python3
"""動画に表示された文字を、元動画の時刻付きでローカルOCRする。"""

from __future__ import annotations

import argparse
import json
import math
import queue
import re
import subprocess
import sys
import threading
from collections import Counter
from dataclasses import dataclass
from decimal import Decimal
from itertools import groupby
from pathlib import Path
from time import monotonic


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MODELS = REPO_ROOT / "outputs" / "shizuku-screen-ocr" / "models"
PTS = re.compile(rb"\bn:\s*(\d+)\s+pts:\s*(-?\d+)\s+pts_time:")
TIME_BASE = re.compile(rb"config in time_base:\s*(\d+)/(\d+)")


@dataclass(frozen=True)
class Region:
    start_ms: int
    end_ms: int
    crop: tuple[int, int, int, int]
    mode: str
    dark_on_light: bool = False


def timecode(ms: int) -> str:
    hours, rest = divmod(ms, 3_600_000)
    minutes, rest = divmod(rest, 60_000)
    seconds, ms = divmod(rest, 1000)
    return f"{hours:02}:{minutes:02}:{seconds:02}.{ms:03}"


def video_info(path: Path) -> tuple[int, int, int]:
    raw = subprocess.check_output([
        "ffprobe", "-v", "error", "-select_streams", "v:0",
        "-show_entries", "stream=width,height:format=duration", "-of", "json", str(path),
    ])
    info = json.loads(raw)
    stream = info["streams"][0]
    return stream["width"], stream["height"], round(Decimal(info["format"]["duration"]) * 1000)


def load_layout(path: Path, width: int, height: int, duration: int) -> tuple[str, list[Region]]:
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    video_id = data["video_id"]
    if not re.fullmatch(r"[A-Za-z0-9_-]{11}", video_id):
        raise ValueError("動画IDの形式が不正です。")
    if data["size"] != [width, height]:
        raise ValueError(f"枠の設定と動画の解像度が異なります（動画は {width}x{height}）。")
    regions = []
    last_end = 0
    for item in data["regions"]:
        x, y, w, h = item["crop"]
        if not all(type(n) is int for n in (x, y, w, h)) or not (0 <= x < x + w <= width and 0 <= y < y + h <= height):
            raise ValueError("切り抜き範囲が画面内にありません。")
        start, end = item.get("start_ms", 0), item.get("end_ms", duration)
        if not all(type(n) is int for n in (start, end)) or not last_end <= start < end <= duration:
            raise ValueError("表示枠の時間帯が動画の範囲外か、前の時間帯と重複しています。")
        mode = item.get("mode", "replace")
        if mode not in ("replace", "scroll"):
            raise ValueError("表示枠の mode は replace または scroll です。")
        dark_on_light = item.get("dark_on_light", False)
        if type(dark_on_light) is not bool:
            raise ValueError("dark_on_light は true または false です。")
        regions.append(Region(start, end, (x, y, w, h), mode, dark_on_light))
        last_end = end
    if not regions:
        raise ValueError("対象の表示枠が指定されていません。")
    return video_id, regions


def read_frames(path: Path, region: Region, fps: float, diagnostics):
    """同じFFmpegプロセスの画像とPTSを順番に対応させる。"""
    import numpy as np

    x, y, w, h = region.crop
    select = f"isnan(prev_selected_t)+gt(floor(t*{fps}+0.00001),floor(prev_selected_t*{fps}+0.00001))"
    filters = f"select='{select}',crop={w}:{h}:{x}:{y}:exact=1,format=bgr24,showinfo=checksum=0"
    command = [
        "ffmpeg", "-hide_banner", "-nostdin", "-nostats", "-loglevel", "info",
        "-copyts", "-start_at_zero", "-ss", f"{region.start_ms / 1000:.3f}",
        "-t", f"{(region.end_ms - region.start_ms) / 1000:.3f}", "-i", str(path),
        "-map", "0:v:0", "-an", "-vf", filters, "-fps_mode", "passthrough",
        "-threads:v", "1", "-f", "rawvideo", "-pix_fmt", "bgr24", "pipe:1",
    ]
    with subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE) as process:
        timestamps = queue.SimpleQueue()

        def read_timestamps():
            time_base = None
            try:
                for line in process.stderr:
                    if b"Parsed_showinfo" in line:
                        if match := TIME_BASE.search(line):
                            time_base = Decimal(int(match[1])) / int(match[2])
                        elif (match := PTS.search(line)) and time_base is not None:
                            timestamps.put((int(match[1]), round(int(match[2]) * time_base * 1000)))
                            continue
                    diagnostics.write(line)
            finally:
                timestamps.put(None)

        reader = threading.Thread(target=read_timestamps, daemon=True)
        reader.start()
        size = w * h * 3
        previous = -1
        count = 0
        try:
            while data := process.stdout.read(size):
                item = timestamps.get(timeout=15)
                if len(data) != size or item is None or item[0] != count:
                    raise RuntimeError("映像フレームとFFmpegの時刻を対応させられません。")
                count += 1
                pts = item[1]
                if pts < previous:
                    raise RuntimeError("映像フレームの時刻が逆行しました。")
                previous = pts
                if region.start_ms <= pts < region.end_ms:
                    yield pts, np.frombuffer(data, dtype=np.uint8).reshape(h, w, 3)
            if process.wait() != 0 or not count:
                raise RuntimeError("FFmpegで画像を取得できません。作業ログを確認してください。")
        finally:
            if process.poll() is None:
                process.kill()
                process.wait()
            reader.join()


def selection_reason(image, previous, elapsed_ms: int, all_frames: bool, change_pixels: int) -> str | None:
    import cv2
    import numpy as np

    if all_frames:
        return "all"
    if previous is None:
        return "first"
    if np.count_nonzero(cv2.absdiff(image, previous) >= 20) >= change_pixels:
        return "change"
    if elapsed_ms >= 5000:
        return "checkpoint"
    return None


def make_ocr(models: Path):
    from rapidocr import LangRec, ModelType, OCRVersion, RapidOCR

    return RapidOCR(params={
        "Global.model_root_dir": str(models.resolve()), "Global.use_cls": False,
        "Det.ocr_version": OCRVersion.PPOCRV4, "Det.model_type": ModelType.MOBILE,
        "Rec.ocr_version": OCRVersion.PPOCRV5, "Rec.model_type": ModelType.MOBILE, "Rec.lang_type": LangRec.CH,
        "EngineConfig.onnxruntime.intra_op_num_threads": 2,
        "EngineConfig.onnxruntime.inter_op_num_threads": 1,
        "EngineConfig.onnxruntime.use_cuda": False,
        "EngineConfig.onnxruntime.use_dml": False,
    })


def dark_text_boxes(gray):
    """白地に黒字の水平な表示枠で、文字のある行を上下方向に分ける。"""
    import numpy as np

    ink = gray < 150
    rows = np.flatnonzero(np.count_nonzero(ink, axis=1) >= 4)
    height, width = gray.shape
    for group in np.split(rows, np.flatnonzero(np.diff(rows) > 4) + 1):
        # 枠の端で切れた数ピクセルの帯は、縦横比が極端になり認識できないため除く。
        if len(group) < 12:
            continue
        top, bottom = int(group[0]), int(group[-1]) + 1
        cols = np.flatnonzero(np.any(ink[top:bottom], axis=0))
        if not len(cols):
            continue
        left, right = max(0, int(cols[0]) - 6), min(width, int(cols[-1]) + 7)
        if right - left < 12:
            continue
        yield left, max(0, top - 3), right, min(height, bottom + 3)


def recognize(engine, frame, gray, dark_on_light=False):
    import cv2

    lines = []
    if dark_on_light:
        for left, top, right, bottom in dark_text_boxes(gray):
            line = frame[top:bottom, left:right]
            large = cv2.resize(line, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
            result = engine(large, use_det=False, use_cls=False)
            for text, score in zip(result.txts or (), result.scores or ()):
                if text.strip():
                    lines.append({"text": text.strip(), "score": float(score), "box": [left, top, right, bottom]})
        return lines
    # 輪郭を保ったまま小さな字を拡大し、元画像は検証用に保存する。
    large = cv2.resize(frame, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
    result = engine(large, use_cls=False, text_score=0.35)
    if result.txts is None:
        return []
    for text, score, box in zip(result.txts, result.scores, result.boxes):
        if text.strip():
            left, top = (int(n / 2) for n in box.min(axis=0))
            right, bottom = (int(n / 2) for n in box.max(axis=0))
            lines.append({"text": text.strip(), "score": float(score), "box": [left, top, right, bottom]})
    return sorted(lines, key=lambda line: (line["box"][1], line["box"][0]))


def new_scroll_lines(previous: list[dict], current: list[dict]) -> list[dict]:
    """表示順が連続する範囲だけ同一とみなす。"""
    for count in range(min(len(previous), len(current)), 0, -1):
        if all(a["text"] == b["text"] and abs(a["box"][0] - b["box"][0]) <= 12
               for a, b in zip(previous[-count:], current[:count])):
            return current[count:]
    return current


def same_ink(a, b) -> bool:
    import cv2
    import numpy as np

    kernel = np.ones((3, 3), dtype=np.uint8)
    return not (np.any(a > cv2.dilate(b, kernel)) or np.any(b > cv2.dilate(a, kernel)))


def merge_display_readings(records):
    """同じ字形が続く間の読みが揺れたら、元のOCRを残して要確認にする。"""
    for _, group in groupby(records, lambda r: (r["region"], r.get("display", r["pts_ms"]))):
        observations = list(group)
        bodies = [tuple(line["text"] for line in row["lines"]) for row in observations]
        counts = Counter(bodies)
        scores = [min((line["score"] for line in row["lines"]), default=0) for row in observations]
        best = max(range(len(bodies)), key=lambda i: (bool(bodies[i]), counts[bodies[i]], scores[i]))
        first = bodies.index(bodies[best])
        yield {**observations[first], "disagreement": len(counts) > 1}


def timeline_events(records):
    previous = []
    previous_region = None
    pending = None
    for row in merge_display_readings(records):
        if row["region"] != previous_region:
            if pending is not None:
                yield pending
            pending, previous = None, []
            previous_region = row["region"]
        lines = row["lines"]
        if row["mode"] == "scroll":
            for line in new_scroll_lines(previous, lines):
                yield (row["pts_ms"], line["text"], line["score"], row["frame"], False)
            previous = lines
            continue
        body = "\n".join(line["text"] for line in lines)
        if body and pending is not None and body == pending[1]:
            if row["disagreement"] and not pending[4]:
                pending = (*pending[:4], True)
            continue
        if pending is not None:
            # 短い間隔で同じ枠の文章が伸びるときは、最後の表示を残す。
            if not body.startswith(pending[1]) or row["pts_ms"] - pending[0] > 1000:
                yield pending
            pending = None
        if body:
            pending = (row["pts_ms"], body, min(line["score"] for line in lines), row["frame"], row["disagreement"])
    if pending is not None:
        yield pending


def write_timeline(manifest: Path, timeline: Path, video_id: str) -> int:
    with manifest.open(encoding="utf-8") as source:
        events = list(timeline_events(json.loads(line) for line in source))
    with timeline.open("x", encoding="utf-8", newline="\n") as target:
        target.write(f"# 画面OCR・未確認\n# 動画ID: {video_id}\n"
                     f"# URL: https://www.youtube.com/watch?v={video_id}\n"
                     "# OCR: RapidOCR / PP-OCRv5 mobile / CPU\n"
                     "# 時刻は画面の文字を確認したフレームの時刻です。\n\n")
        for pts, body, score, frame, disagreement in events:
            target.write(f"[{timecode(pts)}] {body}")
            if score < 0.85 or disagreement:
                target.write(f" [要確認: {Path(frame).stem}]")
            target.write("\n\n")
    return len(events)


def run(args: argparse.Namespace):
    import cv2

    if not math.isfinite(args.fps) or not 0 < args.fps <= 60:
        raise ValueError("サンプル頻度は毎秒0超〜60枚で指定してください。")
    if args.change_pixels < 1:
        raise ValueError("変化判定のピクセル数は1以上で指定してください。")
    width, height, duration = video_info(args.input)
    video_id, layout = load_layout(args.layout, width, height, duration)
    start, end = args.start_ms, duration if args.end_ms is None else args.end_ms
    if not 0 <= start < end <= duration:
        raise ValueError("処理する時刻範囲が元動画の範囲外です。")
    ranges = [Region(max(start, r.start_ms), min(end, r.end_ms), r.crop, r.mode, r.dark_on_light)
              for r in layout if r.start_ms < end and r.end_ms > start]
    if not ranges:
        raise ValueError("処理する時刻範囲に対象の表示枠がありません。")
    args.workdir.mkdir(parents=True, exist_ok=False)
    images = args.workdir / "frames"
    images.mkdir()
    cv2.setNumThreads(1)
    engine = make_ocr(args.models)
    started = monotonic()
    sampled, selected = 0, 0
    manifest = args.workdir / "frames.jsonl"
    with manifest.open("x", encoding="utf-8", newline="\n") as output, \
            (args.workdir / "ffmpeg.log").open("xb") as diagnostics:
        for region_id, region in enumerate(ranges):
            previous = None
            display_mask = None
            display = 0
            last_pts = 0
            for pts, frame in read_frames(args.input, region, args.fps, diagnostics):
                sampled += 1
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                mask = ((gray < 150).astype("uint8") * 255) if region.dark_on_light else gray
                reason = selection_reason(mask, previous, pts - last_pts, args.all_frames, args.change_pixels)
                if reason is None:
                    continue
                selected += 1
                if region.dark_on_light and region.mode == "replace":
                    if display_mask is None or not same_ink(mask, display_mask):
                        display_mask, display = mask, sampled
                else:
                    display = sampled
                filename = f"f{sampled:07}_{timecode(pts).replace(':', '-')}.png"
                ok, png = cv2.imencode(".png", frame)
                if not ok:
                    raise RuntimeError("検証用の切り抜き画像を保存できません。")
                (images / filename).write_bytes(png.tobytes())
                row = {"frame": f"frames/{filename}", "pts_ms": pts, "region": region_id, "display": display,
                       "mode": region.mode, "reason": reason, "lines": recognize(engine, frame, gray, region.dark_on_light)}
                output.write(json.dumps(row, ensure_ascii=False) + "\n")
                previous, last_pts = mask, pts
                if selected % 100 == 0:
                    print(f"{timecode(pts)}  比較 {sampled}枚 / OCR {selected}枚", flush=True)
    if not sampled:
        raise RuntimeError("指定された範囲でサンプルが取得できませんでした。")
    timeline = args.workdir / f"{video_id}.screen-ocr.txt"
    events = write_timeline(manifest, timeline, video_id)
    stats = {"sampled": sampled, "ocr_frames": selected, "timeline_entries": events,
             "seconds": round(monotonic() - started, 2)}
    (args.workdir / "stats.json").write_text(json.dumps(stats) + "\n", encoding="utf-8")
    print(stats, flush=True)
    print(timeline.resolve(), flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="取得済みの動画ファイル")
    parser.add_argument("--layout", type=Path, required=True, help="表示枠のJSON設定")
    parser.add_argument("--workdir", type=Path, required=True, help="結果と確認画像を置く新規フォルダ")
    parser.add_argument("--models", type=Path, default=DEFAULT_MODELS)
    parser.add_argument("--start-ms", type=int, default=0)
    parser.add_argument("--end-ms", type=int)
    parser.add_argument("--fps", type=float, default=4)
    parser.add_argument("--change-pixels", type=int, default=6, help="OCRを再実行する最小の差分画素数")
    parser.add_argument("--all-frames", action="store_true", help="比較試験用に全サンプルをOCRする")
    try:
        run(parser.parse_args())
    except (OSError, ValueError, RuntimeError, ImportError, KeyError, IndexError,
            queue.Empty, subprocess.CalledProcessError) as error:
        print(f"[Error] {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(main())
