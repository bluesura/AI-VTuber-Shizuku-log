"""人が確認したペルソナ対照表を使い、下書きの明示的な属性欄を点検する。"""
import argparse
import csv
import re
from pathlib import Path


def main(argv=None):
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("draft", type=Path)
    cli.add_argument("--facts", type=Path, required=True,
                     help="確認済みの field, value, source の3列TSV")
    args = cli.parse_args(argv)
    try:
        with args.facts.open(encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream, delimiter="\t")
            if reader.fieldnames != ["field", "value", "source"]:
                raise ValueError("確認済み対照表のヘッダが不正です。")
            facts = {}
            for row in reader:
                field, value, source = (row[key].strip() for key in reader.fieldnames)
                if not all((field, value, source)):
                    raise ValueError(f"{reader.line_num}行目: 項目、値、確認根拠が必要です。")
                values, sources = facts.setdefault(field, (set(), set()))
                values.add(value)
                sources.add(source)
        for i, line in enumerate(args.draft.read_text(encoding="utf-8-sig").splitlines(), 1):
            match = re.fullmatch(r"\s*(?:[|*-]\s*)?([^|=：:]+?)\s*[=：:]\s*(.+?)\s*", line)
            if match and match[1] in facts:
                values, sources = facts[match[1]]
                if match[2] not in values:
                    print(f"{args.draft}:{i}: WARN {match[1]} を確認（根拠: {', '.join(sorted(sources))}）")
    except (OSError, ValueError, csv.Error) as exc:
        cli.exit(2, f"{exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
