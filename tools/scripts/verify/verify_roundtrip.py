"""XのJSONL・TSVまたはWikiの行キーを比較し、既存エントリの欠落を検出する。"""
import argparse
import csv
import json
import re
from collections import Counter
from pathlib import Path

VIDEO_URL = re.compile(r"https?://(?:www\.)?(?:youtube\.com/watch\?[^\s\]]*?v=|youtu\.be/)([A-Za-z0-9_-]{11})(?![A-Za-z0-9_-])")
VIDEO_ROW = re.compile(r"(?ms)^\|-[ \t]*$.*?(?=^\|-[ \t]*$|^\|\}[ \t]*$)")
TIMELINE_ROW = re.compile(r"(?m)^\*\s+(\d{4})-(\d{1,2})-(\d{1,2})\s*[:：]\s*(.+)$")


def keys(path, input_format, field):
    if path.is_dir():
        if input_format.startswith("wiki-"):
            raise ValueError("Wiki形式は前後のソースファイルを指定してください。")
        suffix = {"jsonl": ".jsonl", "tsv": ".tsv", "lines": ".txt"}[input_format]
        for child in sorted(path.rglob("*")):
            if child.is_file() and (child.suffix == suffix or input_format == "tsv" and child.suffix == ".txt"):
                yield from keys(child, input_format, field)
        return
    with path.open(encoding="utf-8-sig", newline="") as stream:
        if input_format == "tsv":
            reader = csv.DictReader(stream, delimiter="\t")
            if reader.fieldnames in (["なし"], ["無し"], ["なし。"]) or not reader.fieldnames:
                return
            if field not in reader.fieldnames:
                raise ValueError(f"{path}: 列 {field} がありません")
            yield from (row[field] for row in reader)
        elif input_format == "jsonl":
            for line in stream:
                if line.strip():
                    row = json.loads(line)
                    yield str(row[field])
        elif input_format == "wiki-videos":
            for row in VIDEO_ROW.finditer(stream.read()):
                yield from VIDEO_URL.findall(row.group())
        elif input_format == "wiki-timeline":
            for year, month, day, body in TIMELINE_ROW.findall(stream.read()):
                yield f"{year}-{int(month):02}-{int(day):02}：{body.strip()}"
        else:
            yield from (line.rstrip("\r\n") for line in stream if line.strip())


def main(argv=None):
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("before", type=Path)
    cli.add_argument("after", type=Path)
    cli.add_argument("--format", choices=["tsv", "jsonl", "lines", "wiki-videos", "wiki-timeline"], default="jsonl")
    cli.add_argument("--key", default="post_id")
    cli.add_argument("--allow-removal", action="append", default=[], metavar="KEY")
    args = cli.parse_args(argv)
    try:
        before = Counter(keys(args.before, args.format, args.key))
        after = Counter(keys(args.after, args.format, args.key))
    except (ValueError, OSError, KeyError, csv.Error) as exc:
        cli.exit(2, f"{exc}\n")
    if args.format.startswith("wiki-") and not before:
        cli.exit(2, "基準Wikiソースから行キーを抽出できません。\n")
    if any(key in before or key in after for key in ("", None)):
        cli.exit(2, "空のキーを含む入力です。\n")
    missing = before - after
    for key in args.allow_removal:
        missing.pop(key, None)
    for key, count in sorted(missing.items()):
        print(f"欠落 ×{count}: {key}")
    print(f"基準 {sum(before.values())}件 / 再構築 {sum(after.values())}件 / 未承認欠落 {sum(missing.values())}件")
    return int(bool(missing))


if __name__ == "__main__":
    raise SystemExit(main())
