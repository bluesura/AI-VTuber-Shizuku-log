"""公開済みFandomページの表示を読み取り専用で監査する。"""
import argparse
import json
import sys
from html.parser import HTMLParser
from pathlib import Path

from wiki_client import MediaWikiClient, UpdateError

# ページ別ガイドで指定されている英語版の内容カテゴリ。
ENGLISH_CONTENT_CATEGORIES = {
    "Shizuku": "基本",
    "Official Links": "基本",
    "Fan Activities": "コミュニティ",
    "Media Coverage": "コンテンツ",
}


class WikiHTML(HTMLParser):
    def __init__(self):
        super().__init__()
        self.redlinks = set()
        self.cite_errors = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        classes = set((attrs.get("class") or "").split())
        if tag in {"a", "span"} and classes & {"new", "newcategory"}:
            self.redlinks.add(attrs.get("title") or attrs.get("href") or str(self.getpos()))
        if (tag == "strong" and "error" in classes) or classes & {"mw-ext-cite-error", "cite-error"}:
            self.cite_errors.append(self.getpos())


def audit(client, title, required, *, revid=None):
    target = {"oldid": str(revid)} if revid is not None else {"page": title}
    page = client.request({"action": "parse", **target, "prop": "text|categories"}).get("parse")
    if not isinstance(page, dict) or not isinstance(page.get("text"), str):
        raise UpdateError(f"表示HTMLを取得できません: {title}")
    if not isinstance(page.get("categories"), list):
        raise UpdateError(f"カテゴリ情報を取得できません: {title}")
    categories = set()
    for item in page["categories"]:
        if not isinstance(item, dict) or not isinstance(item.get("category"), str):
            raise UpdateError(f"カテゴリ情報の形式が不正です: {title}")
        categories.add(item["category"].replace("_", " "))
    return inspect(title, page["text"], required, categories)


def inspect(title, html, required, categories):
    parser = WikiHTML()
    parser.feed(html)
    parser.close()
    return {
        "title": title,
        "redlinks": sorted(parser.redlinks),
        "cite_errors": parser.cite_errors,
        "missing_categories": sorted(required - categories),
    }


def required_categories(title, extra):
    categories = {name.removeprefix("Category:").replace("_", " ") for name in extra}
    if title in ENGLISH_CONTENT_CATEGORIES:
        categories.update(("English", ENGLISH_CONTENT_CATEGORIES[title]))
    return categories


def report_saved_revision(client, title, revid, required=()):
    try:
        result = audit(client, title, required_categories(title, required), revid=revid)
    except (OSError, ValueError, UpdateError) as exc:
        print(f"保存本文は照合済み。表示監査は未確認: {exc}", file=sys.stderr)
        return
    print("表示監査: " + json.dumps(result, ensure_ascii=False))


def main(argv=None):
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("title")
    cli.add_argument("--require-category", action="append", default=[])
    cli.add_argument("--html", type=Path, help="保存済みHTMLでオフライン監査")
    cli.add_argument("--category", action="append", default=[], help="保存済みHTMLと対になるカテゴリ")
    args = cli.parse_args(argv)
    required = required_categories(args.title, args.require_category)
    if args.html:
        result = inspect(args.title, args.html.read_text(encoding="utf-8-sig"), required, {name.removeprefix("Category:").replace("_", " ") for name in args.category})
    else:
        result = audit(MediaWikiClient(), args.title, required)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return int(any(result[key] for key in ("redlinks", "cite_errors", "missing_categories")))


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (UpdateError, OSError, ValueError) as exc:
        print(exc, file=sys.stderr)
        raise SystemExit(2)
