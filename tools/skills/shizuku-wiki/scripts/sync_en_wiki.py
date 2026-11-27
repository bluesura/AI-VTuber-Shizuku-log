"""同一Fandom内の日英差分を確認し、承認済み英語本文を安全に反映する。"""
from __future__ import annotations

import argparse
import difflib
import json
import re
import sqlite3
import sys
from contextlib import closing
from pathlib import Path

from audit_wiki import report_saved_revision
from wiki_client import (
    API_URL, DEFAULT_PLAN_DIR, MediaWikiClient, UpdateError, apply_attempt,
    read_credentials, sha256_text,
)

GUIDE = Path(__file__).resolve().parents[1] / "references" / "translation-guide.md"
MARKER = re.compile(r"(?m)^<!-- LLM: ja_revid=([1-9][0-9]*) -->[ \t]*$")
LLM_COMMENT = re.compile(r"<!--\s*LLM:", re.I)


def guide_rows(text, section):
    heading = re.search(rf"(?m)^## {section}\. [^\n]+\n", text)
    if not heading:
        raise UpdateError(f"翻訳ガイドに節{section}がありません。")
    block = re.split(r"(?m)^## ", text[heading.end():], maxsplit=1)[0]
    # コード内やWikiリンク内のパイプはセルの区切りにならない。
    separators = re.compile(r"\x60[^\x60]*\x60|\[\[.*?\]\]|\\\||\|")
    for line in block.splitlines():
        if not line.startswith("|"):
            continue
        row, start = [], 1
        for token in separators.finditer(line, start):
            if token.group() == "|":
                row.append(line[start:token.start()].strip())
                start = token.end()
        if row and not all(re.fullmatch(r"[:-]+", column) for column in row):
            yield row


def page_pairs(text):
    return {ja.strip("`"): en.strip("`") for ja, en, _ in list(guide_rows(text, 3))[1:]
            if en.startswith("`") and en.endswith("`")}


def glossary(text, context):
    approved, review = [], []
    for section in (1, 2, 4, 7, 8, 9):
        for row in list(guide_rows(text, section))[1:]:
            source = row[1] if section == 2 else row[0]
            if source not in context:
                continue
            line = " | ".join(row)
            if any(flag in line for flag in ("未合意", "仮訳", "要照合", "要確認", "廃止")):
                review.append(line)
            else:
                approved.append(line)
    return approved, review


def marker_revision(text):
    matches = list(MARKER.finditer(text))
    if len(matches) != len(LLM_COMMENT.findall(text)) or len(matches) > 1:
        raise UpdateError("日英同期マーカーが重複または破損しています。")
    if not matches:
        return None
    if text[matches[0].end():].strip():
        raise UpdateError("日英同期マーカーはページ末尾に置いてください。")
    return int(matches[0][1])


def stamp(text, ja_rev):
    marker_revision(text)
    body = MARKER.sub("", text).rstrip("\r\n")
    if not body.strip():
        raise UpdateError("英語の翻訳本文が空です。")
    return f"{body}\n\n<!-- LLM: ja_revid={ja_rev} -->\n"


def state_path(directory, page):
    return directory / f"sync-{sha256_text(page)[:16]}.sqlite3"


def read_state(directory, page):
    path = state_path(directory, page)
    if not path.is_file():
        return None
    with closing(sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)) as db:
        return db.execute("SELECT ja_rev, en_rev, en_hash FROM sync").fetchone()


def save_state(directory, page, ja_rev, saved):
    path = state_path(directory, page)
    path.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(path)) as db, db:
        db.execute("CREATE TABLE IF NOT EXISTS sync (ja_rev INTEGER, en_rev INTEGER, en_hash TEXT)")
        db.execute("DELETE FROM sync")
        db.execute("INSERT INTO sync VALUES (?, ?, ?)", (ja_rev, saved.revid, sha256_text(saved.text)))


def sync_status(en, previous, *, bootstrap=False):
    marker = marker_revision(en.text)
    if previous is None:
        if not bootstrap:
            raise UpdateError("同期記録がありません。英語版の履歴を確認し、初回のみ --bootstrap を指定してください。")
        return marker
    ja_rev, en_rev, en_hash = previous
    if en.revid != en_rev or sha256_text(en.text) != en_hash or marker != ja_rev:
        raise UpdateError("英語版が保存済み同期記録と異なります。版履歴と差分を確認してください。")
    return ja_rev


def diff(old, new, old_label, new_label):
    return "".join(difflib.unified_diff(old.splitlines(keepends=True), new.splitlines(keepends=True),
                                       fromfile=old_label, tofile=new_label))


def prepare(args, client, ja_title, en_title, guide):
    ja = client.fetch_page(ja_title)
    en = client.fetch_page(en_title)
    base = sync_status(en, read_state(args.state_dir, en_title), bootstrap=args.bootstrap)
    if base == ja.revid and not args.bootstrap:
        print(f"同期済み: {ja_title}@{ja.revid} → {en_title}@{en.revid}")
        return 0
    if args.command == "check":
        source = ja.text
        if base is not None and base != ja.revid:
            old_ja = client.fetch_page(ja_title, revid=base)
            source = diff(old_ja.text, ja.text, str(base), str(ja.revid))
        approved, review = glossary(guide, ja.text)
        print(f"翻訳対象: {ja_title}@{ja.revid} → {en_title}@{en.revid}")
        print("合意済みの対訳\n" + "\n".join(approved))
        if review:
            print("訳語の確認が必要\n" + "\n".join(review))
        print("日本語の更新内容\n" + source)
        print("現在の英語本文\n" + en.text)
        return 0
    text = stamp(args.translation.read_text(encoding="utf-8-sig"), ja.revid)
    plan = {
        "api_url": API_URL, "ja": ja_title, "en": en_title, "ja_rev": ja.revid,
        "ja_hash": sha256_text(ja.text), "en_rev": en.revid, "en_hash": sha256_text(en.text),
        "proposed": text, "proposed_hash": sha256_text(text), "bootstrap": args.bootstrap,
    }
    args.plan.parent.mkdir(parents=True, exist_ok=True)
    with args.plan.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(plan, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    print(diff(en.text, text, f"{en_title}@{en.revid}", "承認用"))
    print(f"承認対象の差分を保存: {args.plan}")
    return 0


def apply(args, pairs):
    if not args.yes:
        raise UpdateError("表示した差分の承認後に apply --yes を指定してください。")
    plan = json.loads(args.plan.read_text(encoding="utf-8-sig"))
    en_title = plan["en"]
    ja_title = plan["ja"]
    text = plan["proposed"]
    if (plan.get("api_url") != API_URL or pairs.get(ja_title) != en_title
            or sha256_text(text) != plan["proposed_hash"] or marker_revision(text) != plan["ja_rev"]):
        raise UpdateError("確認案の編集先、本文ハッシュ、同期マーカーを確認してください。")
    with apply_attempt(en_title, args.state_dir):
        client = MediaWikiClient(allowed_titles=(en_title,))
        client.login(*read_credentials(required=True))
        ja = client.fetch_page(ja_title)
        en = client.fetch_page(en_title)
        if ja.revid != plan["ja_rev"] or sha256_text(ja.text) != plan["ja_hash"]:
            raise UpdateError("日本語版が変わりました。確認案を作り直してください。")
        if en.text != text:
            sync_status(en, read_state(args.state_dir, en_title), bootstrap=plan["bootstrap"] is True)
            if en.revid != plan["en_rev"] or sha256_text(en.text) != plan["en_hash"]:
                raise UpdateError("英語版が確認案の基準から変わりました。")
            new_rev = client.edit_page(en, text, f"{ja_title} の版 {ja.revid} に同期")
            en = client.fetch_page(en_title)
            if en.revid != new_rev or en.text != text:
                raise UpdateError("保存後の英語版を照合できません。最新版を確認してください。")
        save_state(args.state_dir, en_title, ja.revid, en)
    print(f"同期を確認: {ja_title}@{ja.revid} → {en_title}@{en.revid}")
    report_saved_revision(client, en_title, en.revid, ("English",))
    return 0


def main(argv=None):
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--state-dir", type=Path, default=DEFAULT_PLAN_DIR)
    sub = cli.add_subparsers(dest="command", required=True)
    for command in ("check", "draft"):
        mode = sub.add_parser(command)
        mode.add_argument("ja_title")
        mode.add_argument("--bootstrap", action="store_true", help="履歴を確認済みの初回同期")
        if command == "draft":
            mode.add_argument("--translation", type=Path, required=True)
            mode.add_argument("--plan", type=Path, required=True)
    mode = sub.add_parser("apply")
    mode.add_argument("--plan", type=Path, required=True)
    mode.add_argument("--yes", action="store_true")
    mode = sub.add_parser("unlock")
    mode.add_argument("ja_title")
    mode.add_argument("--yes", action="store_true")
    args = cli.parse_args(argv)
    guide = GUIDE.read_text(encoding="utf-8")
    pairs = page_pairs(guide)
    try:
        if args.command == "apply":
            return apply(args, pairs)
        en_title = pairs.get(args.ja_title)
        if not en_title:
            raise UpdateError("翻訳ガイドに英語版の正式ページ名がありません。")
        if args.command == "unlock":
            if not args.yes:
                raise UpdateError("失敗原因を確認してから unlock --yes を指定してください。")
            with apply_attempt(en_title, args.state_dir, unlock=True):
                pass
            return 0
        return prepare(args, MediaWikiClient(), args.ja_title, en_title, guide)
    except (OSError, ValueError, KeyError, UpdateError, sqlite3.Error) as exc:
        cli.exit(1, f"{exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
