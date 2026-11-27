"""公開用テキストの未完了タグ、マーカー残存、匿名化漏れを検査する。"""
import argparse
import bisect
import re
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1]
COMMENT = re.compile(r"<!--.*?(?:-->|\Z)", re.DOTALL)
TODO = re.compile(r"<!--\s*(?:TODO|FIXME|XXX|TBD)\b|<!--\s*(?:要確認|仮)(?=[\s:：\]】]|-->|$)", re.I)
QUOTED = re.compile(
    r"(?is)<(blockquote|pre|nowiki)\b[^>]*>.*?</\1\s*>"
    r"|(?m:^[ \t]*```(?:verbatim|quote)[ \t]*$[\s\S]*?^[ \t]*```[ \t]*$)"
    r"|(?m:^[ \t]*>(?!>)[^\n]*)|「[^」]*」"
)
PLACEHOLDER = re.compile(r"\[(?:TBD|要確認|ここにURL)\]|#ERROR!|以下に[^\n。]{0,80}をまとめます", re.I)
RESIDUE = re.compile(r"\uFFFD|⟦MW[0-9]{4,}⟧")
LINK = re.compile(r"\[\[[^\]\n]+\]\]|\[https?://[^\]\n]+\]|https?://[^\s<>{}\[\]]+")
MENTION = re.compile(r"(?<![\w@])@([A-Za-z0-9_]+)\b")
ANON = re.compile(r"User_[0-9A-Fa-f]{8}")


def whitelist():
    return {
        line.strip().lstrip("@").casefold()
        for name in ("anon_whitelist.txt", "anon_whitelist_x.txt")
        for line in (SCRIPTS / name).read_text(encoding="utf-8-sig").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }


def blank(text):
    return re.sub(r"[^\n]", " ", text)


def scan(text, allowed):
    newlines = [m.start() for m in re.finditer("\n", text)]
    findings = []

    def add(match, level, message):
        findings.append((bisect.bisect_left(newlines, match.start()) + 1, level, message))

    for match in COMMENT.finditer(text):
        if TODO.match(match.group()):
            add(match, "ERROR", "未完了のHTMLコメント")
    visible = COMMENT.sub(lambda m: blank(m.group()), text)
    prose = QUOTED.sub(lambda m: blank(m.group()), visible)
    for match in PLACEHOLDER.finditer(prose):
        add(match, "ERROR", "プレースホルダーまたは生成時の説明")
    for match in RESIDUE.finditer(text):
        add(match, "ERROR", "置換文字または未復元マーカー")
    links = list(LINK.finditer(visible))
    for match in MENTION.finditer(visible):
        name = match[1]
        if name.casefold() in allowed or ANON.fullmatch(name):
            continue
        linked = False
        for link in links:
            if link.start() <= match.start() < link.end():
                linked = True
                break
            start, stop = (link.end(), match.start()) if link.end() <= match.start() else (match.end(), link.start())
            if 0 <= stop - start <= 8 and re.fullmatch(r"[ \t()（）・:：]*", visible[start:stop]):
                linked = True
                break
        if not linked:
            add(match, "WARN", f"未確認のハンドル @{name}")
    return sorted(findings)


def main(argv=None):
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("paths", type=Path, nargs="+")
    cli.add_argument("--strict", action="store_true", help="WARNでも終了コード1")
    args = cli.parse_args(argv)
    failed = False
    try:
        allowed = whitelist()
        for path in args.paths:
            for line, level, message in scan(path.read_text(encoding="utf-8-sig"), allowed):
                print(f"{path}:{line}: {level} {message}")
                failed |= level == "ERROR" or args.strict
    except (OSError, ValueError) as exc:
        cli.exit(2, f"{exc}\n")
    return int(failed)


if __name__ == "__main__":
    raise SystemExit(main())
