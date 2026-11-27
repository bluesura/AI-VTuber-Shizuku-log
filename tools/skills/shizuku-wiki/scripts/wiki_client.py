"""しずくWikiのAPI通信・編集ガード。"""
from __future__ import annotations

import dataclasses
import hashlib
import http.cookiejar
import json
import os
import re
import sqlite3
import time
import urllib.error
import urllib.parse
import urllib.request
from contextlib import closing, contextmanager
from pathlib import Path
from typing import Any

API_URL = "https://shizuku.fandom.com/api.php"
USERNAME_ENV = "SHIZUKU_FANDOM_BOT_USERNAME"
PASSWORD_ENV = "SHIZUKU_FANDOM_BOT_PASSWORD"
_script = Path(__file__).resolve()
_repo = next((parent for parent in _script.parents if (parent / "tools/shizuku-pipeline").is_dir()), None)
DEFAULT_PLAN_DIR = (_repo or Path.cwd()) / "outputs/shizuku-wiki"
MAX_WIKITEXT_CHARS = 500_000


class UpdateError(RuntimeError):
    """安全に処理を継続できない場合のエラー。"""


@dataclasses.dataclass(frozen=True)
class PageSnapshot:
    title: str
    revid: int
    timestamp: str
    server_timestamp: str
    text: str


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _json_object(value: Any, context: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise UpdateError(f"{context}の応答形式が不正です。")
    return value


class MediaWikiClient:
    def __init__(self, api_url: str = API_URL, *, allowed_titles: tuple[str, ...] = ()) -> None:
        if api_url != API_URL:
            raise UpdateError("許可されていないFandom APIです。")
        self.api_url = api_url
        self.allowed_titles = frozenset(allowed_titles)
        self.last_request: dict[bool, float] = {}
        cookie_jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(cookie_jar)
        )
        self.headers = {
            "User-Agent": (
                "ShizukuWikiUpdater/1.0 "
                "(https://github.com/Bluesura/AI-VTuber-Shizuku-log; MediaWiki API)"
            ),
            "Accept": "application/json",
        }

    def require_title(self, title: str) -> None:
        if title not in self.allowed_titles:
            raise UpdateError(f"編集許可のないページです: {title}")

    def request(self, params: dict[str, Any], *, post: bool = False) -> dict[str, Any]:
        if params.get("action") not in ({"login"} if post else {"query", "parse"}):
            raise UpdateError("この公開クライアントで許可されていないAPI操作です。")
        try:
            return self._request(params, post=post)
        except ServiceUnavailable:
            if post:
                raise
            time.sleep(10)
            return self._request(params, post=post)

    def _request(self, params: dict[str, Any], *, post: bool) -> dict[str, Any]:
        interval = 2.0 if post else 0.25
        delay = interval - (time.monotonic() - self.last_request.get(post, float("-inf")))
        if delay > 0:
            time.sleep(delay)
        self.last_request[post] = time.monotonic()
        common = {"format": "json", "formatversion": "2", "errorformat": "plaintext"}
        encoded = urllib.parse.urlencode({**common, **params}).encode("utf-8")
        if post:
            request = urllib.request.Request(
                self.api_url, data=encoded, headers=self.headers, method="POST"
            )
        else:
            request = urllib.request.Request(
                f"{self.api_url}?{encoded.decode('ascii')}", headers=self.headers
            )
        try:
            with self.opener.open(request, timeout=45) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            if exc.code == 429:
                retry_after = exc.headers.get("Retry-After", "不明") if exc.headers else "不明"
                raise UpdateError(f"Fandom HTTP 429。Retry-After: {retry_after}") from exc
            if exc.code == 503:
                raise ServiceUnavailable("Fandom APIがHTTP 503を返しました。") from exc
            raise UpdateError(f"Fandom APIがHTTP {exc.code}を返しました。") from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            raise UpdateError(f"Fandom APIへ接続できませんでした: {getattr(exc, 'reason', exc)}") from exc
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise UpdateError("Fandom APIの応答をJSONとして解析できませんでした。") from exc

        result = _json_object(payload, "Fandom API")
        if "error" in result:
            error = _json_object(result["error"], "Fandom APIエラー")
            code = str(error.get("code") or "unknown")
            message = str(error.get("text") or error.get("info") or "詳細なし")
            raise UpdateError(f"Fandom APIエラー ({code}): {message}")
        return result

    def _token(self, token_type: str) -> str:
        payload = self.request(
            {"action": "query", "meta": "tokens", "type": token_type}
        )
        query = _json_object(payload.get("query"), "トークン")
        tokens = _json_object(query.get("tokens"), "トークン")
        key = f"{token_type}token"
        token = str(tokens.get(key) or "")
        if not token:
            raise UpdateError(f"{token_type}トークンを取得できませんでした。")
        return token

    def login(self, username: str, password: str) -> None:
        token = self._token("login")
        payload = self.request(
            {
                "action": "login",
                "lgname": username,
                "lgpassword": password,
                "lgtoken": token,
            },
            post=True,
        )
        login = _json_object(payload.get("login"), "ログイン")
        if login.get("result") != "Success":
            reason = str(login.get("reason") or login.get("result") or "不明")
            raise UpdateError(f"Bot Passwordでログインできませんでした: {reason}")

    def fetch_page(self, title: str, *, revid: int | None = None) -> PageSnapshot:
        payload = self.request(
            {
                "action": "query",
                "prop": "revisions",
                **({"revids": str(revid)} if revid else {"titles": title}),
                "rvprop": "ids|timestamp|content",
                "rvslots": "main",
                "curtimestamp": "1",
            }
        )
        query = _json_object(payload.get("query"), "ページ取得")
        pages = query.get("pages")
        if not isinstance(pages, list) or len(pages) != 1:
            raise UpdateError("対象ページを一意に取得できませんでした。")
        page = _json_object(pages[0], "ページ")
        if page.get("missing") is True:
            raise UpdateError(f"対象ページ「{title}」が存在しません。")
        revisions = page.get("revisions")
        if not isinstance(revisions, list) or not revisions:
            raise UpdateError("対象ページのリビジョンを取得できませんでした。")
        revision = _json_object(revisions[0], "リビジョン")
        slots = _json_object(revision.get("slots"), "リビジョンスロット")
        main = _json_object(slots.get("main"), "メインスロット")
        text = main.get("content", main.get("*"))
        if not isinstance(text, str):
            raise UpdateError("対象ページのwikiソースを取得できませんでした。")
        if page.get("title") != title or not revision.get("revid"):
            raise UpdateError("取得したページ名またはリビジョンが一致しません。")
        return PageSnapshot(
            title=str(page.get("title") or ""),
            revid=int(revision.get("revid") or 0),
            timestamp=str(revision.get("timestamp") or ""),
            server_timestamp=str(payload.get("curtimestamp") or ""),
            text=text,
        )

    def edit_page(self, snapshot: PageSnapshot, text: str, summary: str) -> int:
        self.require_title(snapshot.title)
        if not snapshot.revid or not snapshot.timestamp or not snapshot.server_timestamp:
            raise UpdateError("編集に必要な基準リビジョン・時刻がありません。")
        if not text or len(text) > MAX_WIKITEXT_CHARS:
            raise UpdateError("編集本文が空か、文字数上限を超えています。")
        try:
            return self._edit_once(snapshot, text, summary)
        except ServiceUnavailable:
            time.sleep(10)
            current = self.fetch_page(snapshot.title)
            if current.text == text:
                return current.revid
            if current.revid != snapshot.revid or current.text != snapshot.text:
                raise UpdateError("503後に基準版からの変更を検出しました。差分を確認してください。")
            return self._edit_once(current, text, summary)

    def _edit_once(self, snapshot: PageSnapshot, text: str, summary: str) -> int:
        token = self._token("csrf")
        payload = self._request(
            {
                "action": "edit",
                "title": snapshot.title,
                "nocreate": "1",
                "text": text,
                "summary": summary,
                "token": token,
                "baserevid": str(snapshot.revid),
                "basetimestamp": snapshot.timestamp,
                "starttimestamp": snapshot.server_timestamp,
                "assert": "user",
            },
            post=True,
        )
        edit = _json_object(payload.get("edit"), "編集")
        if edit.get("result") != "Success":
            raise UpdateError(f"Wikiの編集に失敗しました: {edit.get('result', '不明')}")
        new_revid = int(edit.get("newrevid") or 0)
        if not new_revid:
            raise UpdateError("編集成功応答に新しいリビジョンIDがありません。")
        return new_revid


def read_credentials(*, required: bool) -> tuple[str, str] | None:
    username = os.environ.get(USERNAME_ENV, "").strip()
    password = os.environ.get(PASSWORD_ENV, "")
    if not username and not password and os.name == "nt":
        import winreg

        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as key:
            def user_value(name: str) -> str:
                try:
                    return str(winreg.QueryValueEx(key, name)[0])
                except FileNotFoundError:
                    return ""

            username = user_value(USERNAME_ENV).strip()
            password = user_value(PASSWORD_ENV)
    if bool(username) != bool(password):
        raise UpdateError(
            f"{USERNAME_ENV} と {PASSWORD_ENV} は両方設定してください。"
        )
    if not username:
        if required:
            raise UpdateError(
                "反映にはBot Passwordが必要です。"
                f"{USERNAME_ENV} と {PASSWORD_ENV} をユーザー環境変数に設定し、"
                "Codexを再起動してください。"
            )
        return None
    return username, password



class ServiceUnavailable(UpdateError):
    """503応答。編集の場合は再送前に保存状態を確認する。"""


def sanitize_field(text: str) -> str:
    """外部リンクの表示文字など、Wikitextに埋め込むプレーンテキスト用。"""
    entities = {
        "&": "&amp;", "|": "&#124;", "[": "&#91;", "]": "&#93;",
        "{": "&#123;", "}": "&#125;", "<": "&lt;", ">": "&gt;",
        "'": "&#39;", "~": "&#126;", "_": "&#95;",
    }
    return "".join(entities.get(ch, ch) for ch in re.sub(r"[\r\n\t]+", " ", text))


def failure_state_path(title: str, state_dir: Path) -> Path:
    return state_dir / f"apply-{sha256_text(title)[:16]}.sqlite3"


@contextmanager
def apply_attempt(title: str, state_dir: Path = DEFAULT_PLAN_DIR, *, unlock: bool = False):
    """ページ単位で実行を直列化し、承認済みapplyの結果を記録する。"""
    path = failure_state_path(title, state_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(path, timeout=0)) as db:
        try:
            db.execute("BEGIN EXCLUSIVE")
            db.execute("CREATE TABLE IF NOT EXISTS failures (count INTEGER NOT NULL)")
            row = db.execute("SELECT count FROM failures").fetchone()
        except sqlite3.Error as exc:
            raise UpdateError(f"失敗状態を開けません。実行中のapplyや状態ファイルを確認: {path}") from exc
        count = row[0] if row else 0
        if count >= 3 and not unlock:
            raise UpdateError(f"{title} は連続3回失敗でロック中です。人間確認後に unlock --yes を実行してください。")
        try:
            yield
        except (OSError, UpdateError, ValueError):
            db.execute("DELETE FROM failures")
            db.execute("INSERT INTO failures VALUES (?)", (count + 1,))
            db.commit()
            raise
        else:
            db.execute("DELETE FROM failures")
            db.commit()
