"""台帳の同一動画リンクだけを短縮し、横断分析用の本文を標準出力へ返す。"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

VIDEO_ID = r"[A-Za-z0-9_-]{11}"
FILENAME = re.compile(rf"({VIDEO_ID})\.highlights\.compiled\.md")
HEADER = re.compile(rf"(?m)^- \*\*動画ID\*\*\s*[:：]\s*`({VIDEO_ID})`[ \t]*$")
LINK = re.compile(rf"\[(\d+:\d{{2}}(?::\d{{2}})?)\]\(<https://www\.youtube\.com/watch\?v=({VIDEO_ID})&t=([0-9]+)s>\)")


def compact(path):
    text = path.read_text(encoding="utf-8-sig")
    filename = FILENAME.fullmatch(path.name)
    header = HEADER.findall(text)
    if filename is None or header != [filename[1]]:
        raise ValueError(f"台帳ファイル名と動画IDの見出しが一致しません: {path}")
    video = filename[1]
    return LINK.sub(lambda m: f"[{m[1]}](t={m[3]}s)" if m[2] == video else m[0], text)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ledgers", type=Path, nargs="+")
    args = parser.parse_args(argv)
    try:
        results = [compact(path) for path in args.ledgers]
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    for text in results:
        sys.stdout.write(text.rstrip("\r\n") + "\n\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
