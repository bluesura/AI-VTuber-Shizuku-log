"""回収済みX投稿IDをFxTwitterで照合し、匿名化した20列TSVへ統合する。"""
from __future__ import annotations

import argparse
import csv
import io
import json
import re
import sys
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

from file_state import atomic_write, file_lock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/shizuku-pipeline/scripts"))
sys.path.insert(0, str(ROOT / "tools/skills/fxtwitter-skill/skills/fxtwitter/scripts"))
from fxtwitter import FxClient, FxError, collect_statuses
from reconstruct_x_from_fxtwitter import (
    NEW_HEADER, anonymize_handle, anonymize_text, extract_fx_body, extract_fx_media,
    load_whitelist, sanitize_cell,
)

JST = timezone(timedelta(hours=9))
ID = re.compile(r"[0-9]+")
HANDLE = re.compile(r"[A-Za-z0-9_]{1,15}")


def check_id(value):
    value = str(value)
    if not ID.fullmatch(value):
        raise ValueError("数値の投稿IDが必要です。")
    return value


def get_page(client, path, params=None, *, terminal=False, optional=False):
    http, payload = client.get(path, params)
    if (terminal and http == 204) or (optional and http in {204, 404}):
        return None
    if http != 200 or not isinstance(payload, dict) or payload.get("code") != 200:
        raise ValueError(f"FxTwitterの取得に失敗しました: {path} HTTP {http}")
    return payload


def discover_ids(client, handle, stop_id, allow_gap, max_pages=100):
    """公開タイムラインによる補助的な発見。既知境界を検査してから返す。"""
    seen_cursors = set()
    ids = []
    params = {"count": 100, "with_replies": "1"}
    for _ in range(max_pages):
        page = get_page(client, f"/2/profile/{handle}/statuses", params, terminal=True)
        if page is None:
            break
        if not isinstance(page.get("results"), list):
            raise ValueError("FxTwitterの一覧応答に results がありません。")
        reached = False
        for item in page["results"]:
            pid = check_id(item.get("id"))
            if author_of(item).casefold() != handle.casefold():
                continue
            reached |= pid == stop_id
            if not stop_id or int(pid) > int(stop_id):
                ids.append(pid)
        if reached:
            return list(dict.fromkeys(ids))
        cursor = (page.get("cursor") or {}).get("bottom")
        if not cursor:
            break
        if cursor in seen_cursors:
            raise ValueError("FxTwitterのページングカーソルが循環しています。")
        seen_cursors.add(cursor)
        params["cursor"] = cursor
    else:
        raise ValueError("FxTwitterのページ上限に到達しました。")
    if stop_id and not allow_gap:
        raise ValueError(f"既知の境界 {stop_id} に到達できません。")
    return list(dict.fromkeys(ids))


def author_of(status):
    return str((status.get("author") or {}).get("screen_name") or "")


def parent_of(status):
    parent = status.get("replying_to")
    if isinstance(parent, dict):
        return str(parent.get("status") or status.get("replying_to_status") or ""), str(parent.get("screen_name") or "")
    return str(status.get("replying_to_status") or ""), str(parent or "")


def status_row(client, handle, pid, whitelist, today, *, reply_hint=False):
    page = get_page(client, f"/2/status/{pid}")
    status = page.get("status") or page.get("tweet") or {}
    if str(status.get("id")) != pid:
        raise ValueError(f"投稿IDが入力と一致しません: {pid}")
    if str(status.get("type", "")).upper() == "RETWEET" or status.get("retweeted_status"):
        return None
    if author_of(status).casefold() != handle.casefold():
        raise ValueError(f"投稿者が入力と一致しません: {pid}")

    parent_id, parent_name = parent_of(status)
    is_reply = bool(reply_hint or parent_id or parent_name or status.get("is_reply"))
    method = "fx_status"
    if is_reply and not (parent_id and parent_name):
        for route in ("thread", "conversation"):
            extra = get_page(client, f"/2/{route}/{pid}", optional=True)
            if extra is None:
                continue
            same = next((row for row in collect_statuses(extra)
                         if str(row.get("id")) == pid and author_of(row).casefold() == handle.casefold()), {})
            candidate_id, candidate_name = parent_of(same)
            if candidate_id and parent_id and candidate_id != parent_id:
                raise ValueError(f"返信先IDが補完結果と一致しません: {pid}")
            if candidate_id or candidate_name:
                parent_id = candidate_id or parent_id
                parent_name = candidate_name or parent_name
                method = "fx_thread"
            if parent_id and parent_name:
                break
    quote = status.get("quote") or {}
    q_name = author_of(quote)
    q_id = str(quote.get("id") or "")
    text, urls = extract_fx_body(status)
    date = datetime.fromtimestamp(int(status["created_timestamp"]), tz=timezone.utc)
    row = dict(
        post_id=pid, date_utc=date.isoformat(timespec="milliseconds").replace("+00:00", "Z"),
        author=handle, type="REPLY" if is_reply else ("QUOTE_RETWEET" if q_id else "CONTEXT_TWEET"),
        text=anonymize_text(text, whitelist),
        extracted_urls=" ".join(dict.fromkeys(anonymize_text(url, whitelist) for url in urls)),
        quote_post_id=check_id(q_id) if q_id and q_name.casefold() in whitelist else "",
        quote_author=anonymize_handle(q_name, whitelist),
        quote_text=anonymize_text(extract_fx_body(quote)[0], whitelist) if q_name.casefold() in whitelist else "",
        reply_to_post_id=check_id(parent_id) if parent_id else "",
        reply_to_author=anonymize_handle(parent_name, whitelist),
        media_urls=" ".join(extract_fx_media(status)),
        snapshot_date=today, metrics_date=today, source_method=method,
    )
    for field in ("likes", "reposts", "replies", "views"):
        value = status.get(field, status.get("retweets") if field == "reposts" else None)
        row[field] = "" if value is None else check_id(value)
    flags = []
    if is_reply and not parent_id:
        flags.append("missing_parent")
    if any(not row[key] for key in ("likes", "reposts", "replies")):
        flags.append("count_uncertain")
    if "t.co/" in row["text"] or "t.co/" in row["extracted_urls"]:
        flags.append("short_url")
    row["quality_flags"] = "|".join(flags)
    return {key: sanitize_cell(value) for key, value in row.items()}


def load_archive(root, handle):
    files, ids = {}, {}
    for path in sorted(root.glob("*/*")):
        if path.suffix not in {".txt", ".tsv"} or not path.is_file():
            continue
        if path.is_symlink() or path.resolve().parent != root.resolve() / path.parent.name:
            raise ValueError(f"Xログのパスがアーカイブ外を参照しています: {path}")
        text = path.read_text(encoding="utf-8-sig")
        if text.strip() in {"", "なし", "無し", "なし。"}:
            if path.parent.name == handle:
                files[path] = []
            continue
        reader = csv.DictReader(io.StringIO(text, newline=""), delimiter="\t", strict=True)
        if reader.fieldnames != NEW_HEADER:
            raise ValueError(f"先に20列へ移行してください: {path}")
        rows = list(reader)
        for row in rows:
            pid = check_id(row["post_id"])
            if None in row or None in row.values() or pid in ids or row["author"] != path.parent.name:
                raise ValueError(f"Xログの列・投稿者・IDが不正または重複: {path}")
            ids[pid] = row["author"]
        if path.parent.name.casefold() == handle.casefold():
            if path.parent.name != handle:
                raise ValueError(f"既存フォルダと同じ表記を指定してください: {path.parent.name}")
            files[path] = rows
    return files, ids


def archive_path(folder, files, utc):
    local = datetime.fromisoformat(utc.replace("Z", "+00:00")).astimezone(JST)
    year, month = local.year, local.month
    choices = []
    for path in files:
        match = re.fullmatch(r"(\d{4})(\d{2})?(?:-(\d{2}))?", path.stem)
        if match and int(match[1]) == year:
            start = int(match[2] or 1)
            end = int(match[3] or match[2] or 12)
            if start <= month <= end:
                choices.append(path)
    if len(choices) > 1:
        raise ValueError(f"複数のXログが同じ月を担当しています: {year}-{month:02}")
    return choices[0] if choices else folder / f"{year}{month:02}.txt"


def merge(root, handle, rows, *, dry_run):
    folder = root / handle
    if folder.resolve() != root.resolve() / handle:
        raise ValueError("保存先がアーカイブ外を参照しています。")
    files, known = load_archive(root, handle)
    changed = defaultdict(list)
    for row in rows:
        owner = known.get(row["post_id"])
        if owner and owner.casefold() != handle.casefold():
            raise ValueError(f"別アカウントのTSVに既存IDがあります: {row['post_id']}")
        if not owner:
            changed[archive_path(folder, files, row["date_utc"])].append(row)
    prepared = {}
    for path, additions in sorted(changed.items()):
        if path.is_symlink() or path.resolve().parent != folder.resolve():
            raise ValueError(f"保存先がアカウントフォルダ外です: {path}")
        out = io.StringIO(newline="")
        writer = csv.DictWriter(out, NEW_HEADER, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(sorted(files.get(path, []) + additions,
                                key=lambda row: (row["date_utc"], int(row["post_id"])), reverse=True))
        prepared[path] = out.getvalue()
    for path, payload in prepared.items():
        if not dry_run:
            atomic_write(path, payload)
        print(f"{path}: +{len(changed[path])}件")
    return sum(map(len, changed.values()))


def main(argv=None):
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("handle")
    mode = cli.add_mutually_exclusive_group(required=True)
    mode.add_argument("--ids", type=Path, help="1行1ID。返信と判明していれば ID にタブと REPLY を添える")
    mode.add_argument("--discover", action="store_true", help="補助タイムラインからIDを発見する")
    cli.add_argument("--stop-id")
    cli.add_argument("--allow-gap", action="store_true")
    cli.add_argument("--execute", action="store_true")
    cli.add_argument("--dry-run", action="store_true")
    args = cli.parse_args(argv)
    if args.execute and args.dry_run:
        cli.error("--execute と --dry-run は同時に指定できません。")
    if not HANDLE.fullmatch(args.handle):
        cli.error("ハンドル形式が不正です。")
    root = ROOT / "logs/twitter(x)"
    state = ROOT / "outputs/shizuku-x-collection"
    _, known = load_archive(root, args.handle)
    client = FxClient(retries=0)
    hints = set()
    if args.ids:
        ids = []
        for line in args.ids.read_text(encoding="utf-8-sig").splitlines():
            if not line.strip():
                continue
            fields = line.split("\t")
            pid = check_id(fields[0].strip())
            if len(fields) > 1:
                if fields[1:] != ["REPLY"]:
                    raise ValueError("IDファイルの任意の第2列は REPLY です。")
                hints.add(pid)
            ids.append(pid)
        if args.stop_id:
            stop_id = check_id(args.stop_id)
            if stop_id in ids:
                ids = [pid for pid in ids if int(pid) > int(stop_id)]
            elif not args.allow_gap:
                raise ValueError("IDファイルに指定した境界がありません。")
    else:
        if not args.stop_id and not args.allow_gap:
            cli.error("--discover には --stop-id が必要です。空白期間の補完には --allow-gap を指定できます。")
        ids = discover_ids(client, args.handle, check_id(args.stop_id) if args.stop_id else None, args.allow_gap)
    rows = []
    today = datetime.now(JST).date().isoformat()
    whitelist = load_whitelist()
    for pid in dict.fromkeys(ids):
        if pid in known:
            if known[pid].casefold() != args.handle.casefold():
                raise ValueError(f"別アカウントのTSVに既存IDがあります: {pid}")
            continue
        row = status_row(client, args.handle, pid, whitelist, today, reply_hint=pid in hints)
        if row is not None:
            rows.append(row)
        time.sleep(0.25)
    if not args.execute:
        added = merge(root, args.handle, rows, dry_run=True)
    else:
        with file_lock(state / "merge.lock"):
            added = merge(root, args.handle, rows, dry_run=False)
            atomic_write(state / f"{args.handle}.json", json.dumps(
                {"snapshot_date": today, "verified_ids": [row["post_id"] for row in rows], "added": added},
                ensure_ascii=False, indent=2) + "\n")
    print(f"{'保存' if args.execute else '保存候補'}: {added}件")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, OSError, FxError, KeyError, csv.Error) as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1)
