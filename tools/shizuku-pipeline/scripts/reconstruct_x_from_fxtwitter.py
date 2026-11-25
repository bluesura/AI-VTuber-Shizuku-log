# -*- coding: utf-8 -*-
"""既存Xログ(TSV)と保存済みFxTwitter status JSONから、新スキーマTSVを再構築するスクリプト。

使い方:
  # ドライラン（差分サマリのみ表示・ファイル出力なし）
  python tools/shizuku-pipeline/scripts/reconstruct_x_from_fxtwitter.py --src-dir <旧TSVの保存先> --dry-run

  # 出力先ディレクトリを指定して変換実行
  python tools/shizuku-pipeline/scripts/reconstruct_x_from_fxtwitter.py --src-dir <旧TSVの保存先> --out-dir outputs/x_reconstructed

前提:
  - 入力は旧形式TSV。アカウント別サブフォルダがあれば出力先にもそのまま反映する。
  - 保存済みFxTwitter応答: outputs/fxtwitter-audit/responses/status_<post_id>.json
  - ホワイトリスト: tools/scripts/anon_whitelist.txt (+ anon_whitelist_x.txt があれば併用)
  - 入出力の契約: docs/x-log-spec.md / docs/x-data-migration-plan.md（Phase 2）
  - 入力は変更しない。出力先に元ログのディレクトリは指定できない。
"""
import argparse
import csv
import hashlib
import html
import io
import json
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from shizulib import x_log_files

BASE = Path(__file__).resolve().parents[3]
RAW_X_DIR = BASE / "logs" / "twitter(x)"
RESP_DIR = BASE / "outputs" / "fxtwitter-audit" / "responses"
WHITELIST_PATHS = [
    BASE / "tools" / "scripts" / "anon_whitelist.txt",
    BASE / "tools" / "scripts" / "anon_whitelist_x.txt",
]

NEW_HEADER = [
    "post_id",
    "date_utc",
    "author",
    "type",
    "text",
    "extracted_urls",
    "quote_post_id",
    "quote_author",
    "quote_text",
    "reply_to_post_id",
    "reply_to_author",
    "media_urls",
    "likes",
    "reposts",
    "replies",
    "views",
    "snapshot_date",
    "metrics_date",
    "source_method",
    "quality_flags",
]

SALT_DEFAULT = os.environ.get("YT_ANON_SALT", "shizuku_archive_secret_salt_2026")
URL_RE = re.compile(r"https?://[^\s<>\"]+")
MENTION_RE = re.compile(r"(?<![\w@])@([A-Za-z0-9_]{1,32})\b")


def load_whitelist() -> set[str]:
    names = set()
    for p in WHITELIST_PATHS:
        if not p.exists():
            continue
        for line in p.read_text(encoding="utf-8").splitlines():
            s = line.strip()
            if not s or s.startswith("#"):
                continue
            names.add(s.lstrip("@").lower())
    return names


def anonymize_handle(handle: str, whitelist: set[str], salt: str = SALT_DEFAULT) -> str:
    if not handle:
        return ""
    clean = handle.strip().lstrip("@")
    if re.fullmatch(r"User_[0-9a-fA-F]{8}", clean):
        return clean
    if clean.lower() in whitelist:
        return clean
    digest = hashlib.sha256((clean.lower() + salt).encode("utf-8")).hexdigest()[:8]
    return f"User_{digest}"


def sanitize_cell(val: str) -> str:
    if not val:
        return ""
    # TSVの1行1レコードを維持するため、タブと改行を空白に正規化
    return re.sub(r"[\t\r\n]+", " ", val).strip()


def normalize_media_url(url: str) -> str:
    if not url:
        return ""
    parsed = urlsplit(url)
    if parsed.hostname == "pbs.twimg.com" and parsed.path.startswith("/media/"):
        path = re.sub(r":(?:small|medium|large|orig|thumb)$", "", parsed.path)
        query = [(k, v) for k, v in parse_qsl(parsed.query) if k != "name"]
        query.append(("name", "orig"))
        return urlunsplit(parsed._replace(path=path, query=urlencode(query)))
    return url


def anonymize_text(text: str, whitelist: set[str]) -> str:
    """本文中の明示的なメンションとXリンクにも同じ匿名化を適用する。"""
    def replace_url(match):
        url = match.group()
        parsed = urlsplit(url)
        if parsed.hostname not in {"x.com", "www.x.com", "twitter.com", "www.twitter.com", "mobile.twitter.com"}:
            return url
        parts = parsed.path.strip("/").split("/")
        if not parts or parts[0].lower() in {"i", "intent", "search", "hashtag", "share", "home"}:
            return url
        handle = parts[0]
        if handle.lower() in whitelist:
            return url
        if len(parts) >= 3 and parts[1] == "status" and parts[2].isdigit():
            return "https://x.com/i/status/" + "/".join(parts[2:])
        return "@" + anonymize_handle(handle, whitelist)

    text = URL_RE.sub(replace_url, text)
    return MENTION_RE.sub(lambda m: "@" + anonymize_handle(m[1], whitelist), text)


def extract_fx_body(tweet: dict) -> tuple[str, list[str]]:
    """FxTwitterのtweetオブジェクトから表示範囲内の本文と展開済みURLリストを返す。"""
    raw = tweet.get("raw_text") or {}
    full_text = raw.get("text", tweet.get("text") or "")
    rng = raw.get("display_text_range")
    if isinstance(rng, list) and len(rng) == 2:
        start, end = rng
        if not (isinstance(start, int) and isinstance(end, int) and 0 <= start <= end and start <= len(full_text)):
            raise ValueError("Invalid display_text_range")
        # 一部の応答は末尾が本文長を超える。本文末尾で止め、文字を補わない。
        end = min(end, len(full_text))
    else:
        start, end = 0, len(full_text)

    urls = []
    edits = []
    for f in raw.get("facets") or []:
        if f.get("type") in {"url", "media"}:
            repl = f.get("replacement") or f.get("original") or ""
            if repl:
                if f.get("type") == "url":
                    urls.append(repl)
                indices = f.get("indices")
                if isinstance(indices, list) and len(indices) == 2:
                    a, b = indices
                    if start <= a < b <= end:
                        edits.append((a, b, repl))
                        urls.append(repl)
                else:
                    orig = f.get("original") or ""
                    if orig:
                        a = full_text.find(orig, start, end)
                        if a >= 0:
                            edits.append((a, a + len(orig), repl))
                            urls.append(repl)

    # 添字は取得済みv2応答のUnicodeコードポイント単位。後方から置換し範囲をずらさない。
    body = full_text[start:end]
    for a, b, repl in sorted(edits, reverse=True):
        body = body[:a-start] + repl + body[b-start:]

    body = html.unescape(body)
    urls.extend(URL_RE.findall(body))
    return sanitize_cell(body), list(dict.fromkeys(html.unescape(u) for u in urls))


def extract_fx_media(tweet: dict) -> list[str]:
    media = tweet.get("media") or {}
    out = []
    items = media.get("all") or (media.get("photos") or []) + (media.get("videos") or [])
    if isinstance(media.get("external"), dict):
        items = items + [media["external"]]
    for item in items:
        u = (item.get("thumbnail_url") or item.get("url") or "") if item.get("type") != "photo" else (item.get("url") or "")
        if u:
            out.append(normalize_media_url(u))
    return list(dict.fromkeys(out))


def load_fx_status(path: Path, post_id: str) -> tuple[dict, str]:
    data = json.loads(path.read_text(encoding="utf-8"))
    payload = data.get("payload", data)
    if data.get("http_status", 200) != 200 or payload.get("code", 200) != 200:
        raise ValueError(f"{path.name}: unsuccessful FxTwitter response")
    tweet = payload.get("status") or payload.get("tweet")
    if not isinstance(tweet, dict) or str(tweet.get("id")) != post_id or tweet.get("type", "status") != "status":
        raise ValueError(f"{path.name}: missing/mismatched status")
    fetched = data.get("finished_at_jst")
    if not fetched:
        raise ValueError(f"{path.name}: acquisition date is unknown")
    snapshot = datetime.fromisoformat(fetched).astimezone(timezone(timedelta(hours=9))).date().isoformat()
    return tweet, snapshot


def comparison_text(text: str) -> str:
    """旧DOMの空白・URL表示差だけを許容し、短い先頭一致では修復判定しない。"""
    return re.sub(r"\s+", " ", URL_RE.sub("", html.unescape(text))).strip()


def process_file(
    src_path: Path,
    whitelist: set[str],
    hide_general_reply_id: bool,
    metrics_from_old: bool,
) -> tuple[list[dict], dict]:
    raw_txt = src_path.read_text(encoding="utf-8-sig")
    if raw_txt.strip() in ("なし", "無し", "なし。", ""):
        return [], {"skipped": True, "reason": "empty_record"}

    lines = raw_txt.splitlines()
    if not lines or not {"URL", "日付"}.issubset(lines[0].split("\t")):
        raise ValueError(f"{src_path.name}: 旧形式のTSVを --src-dir で指定してください（URL・日付列が必要）")

    rd = csv.DictReader(io.StringIO(raw_txt), delimiter="\t")
    rows_out = []
    stats = {
        "total": 0,
        "fx_found": 0,
        "empty_text_fixed": 0,
        "error_fixed": 0,
        "quote_swapped_fixed": 0,
        "missing_parent": 0,
    }

    seen_ids = set()
    for r in rd:
        if None in r or any(v is None for v in r.values()):
            raise ValueError(f"{src_path.name}:{rd.line_num}: inconsistent TSV columns")
        url = (r.get("URL") or "").strip()
        match = re.search(r"/status/(\d+)(?:[/?#]|$)", url)
        if not match:
            raise ValueError(f"{src_path.name}:{rd.line_num}: invalid post URL")
        pid = match[1]
        if pid in seen_ids:
            raise ValueError(f"{src_path.name}:{rd.line_num}: duplicate post_id={pid}")
        seen_ids.add(pid)
        stats["total"] += 1

        old_text = (r.get("本文") or "").strip()
        old_type = (r.get("種類") or "").strip()
        old_quote_url = (r.get("引用URL") or "").strip()
        old_snap = (r.get("snapshot_date") or "").strip()

        flags = []
        resp_file = RESP_DIR / f"status_{pid}.json"
        if resp_file.exists():
            stats["fx_found"] += 1
            tw, snapshot_date = load_fx_status(resp_file, pid)

            date_utc = (r.get("日付") or "").strip()
            author = (tw.get("author") or {}).get("screen_name") or (r.get("投稿者") or "").strip()
            if author.lower() != (r.get("投稿者") or "").strip().lower():
                raise ValueError(f"{pid}: author mismatch")
            if tw.get("created_timestamp") is not None and int(datetime.fromisoformat(date_utc.replace("Z", "+00:00")).timestamp()) != tw["created_timestamp"]:
                raise ValueError(f"{pid}: creation date mismatch")
            text, ext_urls = extract_fx_body(tw)

            if old_text == "" and text != "":
                stats["empty_text_fixed"] += 1
            if old_text == "#ERROR!" and text != "#ERROR!":
                stats["error_fixed"] += 1
                flags.append("error_fixed")

            quote_obj = tw.get("quote")
            quote_post_id = ""
            quote_author = ""
            quote_text = ""
            if isinstance(quote_obj, dict) and quote_obj.get("id"):
                quote_post_id = str(quote_obj["id"])
                q_screen = (quote_obj.get("author") or {}).get("screen_name") or ""
                quote_author = anonymize_handle(q_screen, whitelist)
                q_body, _ = extract_fx_body(quote_obj)
                # 非ホワイトリスト・投稿者不明の引用本文は保存しない。
                quote_text = anonymize_text(q_body, whitelist) if q_screen.lower() in whitelist else ""
                # 旧ログの本文欄に引用先本文が誤混入していたケースを検知
                if comparison_text(old_text) and comparison_text(old_text) == comparison_text(q_body) and comparison_text(text) != comparison_text(old_text):
                    stats["quote_swapped_fixed"] += 1
                    flags.append("dom_swapped_fixed")
            elif old_quote_url:
                m = re.search(r"/status/(\d+)", old_quote_url)
                if m:
                    quote_post_id = m.group(1)
                # 引用元が確認できない旧本文を転載しない。

            reply_to_post_id = ""
            reply_to_author = ""
            if old_type == "REPLY" or tw.get("replying_to"):
                parent = tw.get("replying_to") or {}
                r_screen = parent.get("screen_name") if isinstance(parent, dict) else parent
                r_pid = str(parent.get("status") or "") if isinstance(parent, dict) else str(tw.get("replying_to_status") or "")
                if r_screen:
                    anon_r = anonymize_handle(r_screen, whitelist)
                    reply_to_author = anon_r
                    if not (hide_general_reply_id and anon_r.startswith("User_")):
                        reply_to_post_id = r_pid
                if not reply_to_post_id:
                    stats["missing_parent"] += 1
                    flags.append("missing_parent")

            media_list = extract_fx_media(tw)
            # 旧DOMのメディアには引用元の画像も混入しているため補完には使わない。

            if metrics_from_old:
                likes = (r.get("いいね数") or "").strip()
                reposts = (r.get("リポスト数") or "").strip()
                replies = (r.get("返信数") or "").strip()
                views = (r.get("表示数") or "").strip()
                metrics_date = old_snap
                if not likes or not reposts or not replies:
                    flags.append("count_uncertain")
            else:
                likes = str(tw.get("likes") if tw.get("likes") is not None else "")
                fx_reposts = tw.get("reposts", tw.get("retweets"))
                reposts = str(fx_reposts if fx_reposts is not None else "")
                replies = str(tw.get("replies") if tw.get("replies") is not None else "")
                views = str(tw.get("views") if tw.get("views") is not None else "")
                metrics_date = snapshot_date
                if not likes or not reposts or not replies:
                    flags.append("count_uncertain")

            source_method = "web_dom+fx"
        else:
            # FxTwitter応答がない場合は旧ログから安全に移行
            date_utc = (r.get("日付") or "").strip()
            author = (r.get("投稿者") or "").strip()
            text = sanitize_cell(old_text)
            ext_urls = (r.get("抽出URL") or "").split()
            m = re.search(r"/status/(\d+)", old_quote_url)
            quote_post_id = m.group(1) if m else ""
            quote_author = ""
            quote_text = ""
            reply_to_post_id = ""
            reply_to_author = ""
            if old_type == "REPLY":
                stats["missing_parent"] += 1
                flags.append("missing_parent")
            media_list = [normalize_media_url(u) for u in (r.get("メディアURL") or "").split()]
            likes = (r.get("いいね数") or "").strip()
            reposts = (r.get("リポスト数") or "").strip()
            replies = (r.get("返信数") or "").strip()
            views = (r.get("表示数") or "").strip()
            metrics_date = old_snap
            snapshot_date = old_snap
            source_method = "web_dom"
            flags.append("no_emoji")
            if not likes or not reposts or not replies:
                flags.append("count_uncertain")

        text = anonymize_text(text, whitelist)
        ext_urls = list(dict.fromkeys(anonymize_text(u, whitelist) for u in ext_urls))
        if any("t.co/" in v or "…" in v for v in ext_urls) or "t.co/" in text:
            flags.append("short_url")
        rows_out.append({
            "post_id": pid,
            "date_utc": date_utc,
            "author": author,
            "type": old_type,
            "text": text,
            "extracted_urls": " ".join(ext_urls),
            "quote_post_id": quote_post_id,
            "quote_author": quote_author,
            "quote_text": quote_text,
            "reply_to_post_id": reply_to_post_id,
            "reply_to_author": reply_to_author,
            "media_urls": " ".join(media_list),
            "likes": likes,
            "reposts": reposts,
            "replies": replies,
            "views": views,
            "snapshot_date": snapshot_date,
            "metrics_date": metrics_date,
            "source_method": source_method,
            "quality_flags": "|".join(dict.fromkeys(flags)),
        })
        rows_out[-1] = {k: sanitize_cell(str(v)) for k, v in rows_out[-1].items()}

    # 日時降順（新しい順）で統一ソート
    rows_out.sort(key=lambda x: (x["date_utc"], x["post_id"]), reverse=True)
    return rows_out, stats


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="ファイルを書き出さず統計のみ表示")
    ap.add_argument("--src-dir", default=RAW_X_DIR, help="旧形式TSVの入力ディレクトリ")
    ap.add_argument("--out-dir", default="outputs/x_reconstructed", help="出力先ディレクトリ")
    ap.add_argument("--hide-general-reply-id", action="store_true", help="一般視聴者のreply_to_post_idも非公開化する")
    ap.add_argument("--use-fx-metrics", action="store_true", help="反応数もFxTwitter取得時点の値で上書きする")
    args = ap.parse_args()

    whitelist = load_whitelist()
    out_dir = (BASE / args.out_dir).resolve()
    raw_dir = RAW_X_DIR.resolve()
    src_dir = (BASE / args.src_dir).resolve()
    if not src_dir.is_dir():
        ap.error("入力ディレクトリが存在しません")
    protected = (raw_dir, src_dir)
    if any(out_dir == path or path in out_dir.parents for path in protected):
        ap.error("元ログのディレクトリは出力先に指定できません")

    converted = []
    all_ids = set()
    for src in x_log_files(src_dir):
        relative = src.relative_to(src_dir)
        rows, stats = process_file(
            src,
            whitelist=whitelist,
            hide_general_reply_id=args.hide_general_reply_id,
            metrics_from_old=not args.use_fx_metrics,
        )
        if stats.get("skipped"):
            print(f"[SKIP] {relative.as_posix()}: {stats['reason']}")
            continue
        ids = {r["post_id"] for r in rows}
        if ids & all_ids:
            raise ValueError("Duplicate post_id across source files")
        all_ids.update(ids)
        out_path = (out_dir / relative).resolve()
        if any(out_path == path or path in out_path.parents for path in protected):
            ap.error("元ログのディレクトリは出力先に指定できません")
        converted.append((out_path, rows))
        print(
            f"[OK] {relative.as_posix()}: total={stats['total']}, fx_found={stats['fx_found']}, "
            f"empty_fixed={stats['empty_text_fixed']}, error_fixed={stats['error_fixed']}, "
            f"quote_swapped_fixed={stats['quote_swapped_fixed']}, missing_parent={stats['missing_parent']}"
        )
    if not args.dry_run:
        out_dir.mkdir(parents=True, exist_ok=True)
        for out_path, rows in converted:
            out_path.parent.mkdir(parents=True, exist_ok=True)
            buf = io.StringIO()
            wr = csv.DictWriter(buf, fieldnames=NEW_HEADER, delimiter="\t", lineterminator="\n")
            wr.writeheader()
            wr.writerows(rows)
            with out_path.open("w", encoding="utf-8", newline="\n") as output:
                output.write(buf.getvalue())


if __name__ == "__main__":
    main()
