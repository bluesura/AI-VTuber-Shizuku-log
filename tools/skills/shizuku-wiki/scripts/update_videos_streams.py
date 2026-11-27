#!/usr/bin/env python3
"""しずくWiki「動画・配信」の差分確認と、承認後の安全な反映を行う。

``check`` はWikiを編集せず、現在のソースと公式YouTubeを照合して確認案を保存する。
``apply --yes`` は確認案の基準リビジョンと本文を再検証した後だけ反映する。
Bot Passwordは環境変数からのみ読み、確認案やログには保存しない。
"""

from __future__ import annotations

import argparse
import concurrent.futures
import csv
import dataclasses
import datetime as dt
import difflib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Iterable, Sequence



# ファイルパスから直接ロードする呼び出し元にも対応する。
if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
from audit_wiki import report_saved_revision
from wiki_client import (
    API_URL, DEFAULT_PLAN_DIR, MediaWikiClient, PageSnapshot, UpdateError,
    _json_object, apply_attempt, read_credentials, sanitize_field, sha256_text,
)


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


PAGE_TITLE = "動画・配信"
PAGE_URL = "https://shizuku.fandom.com/wiki/%E5%8B%95%E7%94%BB%E3%83%BB%E9%85%8D%E4%BF%A1"
CORE_CHANNEL_TABS = (
    ("stream", "https://www.youtube.com/@aivtuber_shizuku/streams"),
    ("video", "https://www.youtube.com/@aivtuber_shizuku/videos"),
)
SHORTS_TAB = ("short", "https://www.youtube.com/@aivtuber_shizuku/shorts")
PLAN_SCHEMA = 1
EXCLUDED_STREAMS = Path(__file__).resolve().parents[1] / "config" / "excluded_streams.tsv"
VIDEO_ID_PATTERN = r"[A-Za-z0-9_-]{11}"
VIDEO_ID_RE = re.compile(VIDEO_ID_PATTERN)
YOUTUBE_URL_RE = re.compile(
    rf"https?://(?:www\.)?(?:youtube\.com/watch\?[^\s\]]*?v=|youtu\.be/)({VIDEO_ID_PATTERN})"
)
ROW_RE = re.compile(r"(?ms)^\|-\s*$.*?(?=^\|-\s*$|^\|}\s*$)")
HEADING_RE = re.compile(r"(?m)^==\s*(.+?)\s*==\s*$")
ARCHIVE_HEADING_RE = re.compile(r"(?m)^==\s*(\d{4})年アーカイブ\s*==\s*$")
TOTAL_LINE_RE = re.compile(
    r"(?m)^\* 完了済みライブ配信（公開アーカイブ）:\s*\d+本\s*$"
)
BREAKDOWN_LINE_RE = re.compile(r"(?m)^\* 年別内訳:\s*.*$")
JST = dt.timezone(dt.timedelta(hours=9))

TABLE_HEADER = """{| class="wikitable sortable"
! 公開日時（JST）
! タグ
! 時間
! タイトル
"""


@dataclasses.dataclass(frozen=True)
class Candidate:
    video_id: str
    kind: str
    url: str


@dataclasses.dataclass(frozen=True)
class VideoEntry:
    video_id: str
    kind: str
    published_jst: str
    tag: str
    duration: str
    title: str

    @property
    def url(self) -> str:
        return f"https://www.youtube.com/watch?v={self.video_id}"

    @property
    def section(self) -> str:
        if self.kind == "stream":
            return f"{self.published_jst[:4]}年アーカイブ"
        if self.kind == "short":
            return "ショート"
        return "通常動画"

    def row(self) -> str:
        return (
            "|-\n"
            f"| {self.published_jst}\n"
            f"| {self.tag}\n"
            f"| {self.duration}\n"
            f"| [{self.url} {sanitize_field(self.title)}]\n"
        )


@dataclasses.dataclass(frozen=True)
class ManualItem:
    video_id: str
    kind: str
    reason: str


@dataclasses.dataclass(frozen=True)
class UpdateResult:
    text: str
    additions: tuple[VideoEntry, ...]
    total_before: str
    total_after: str
    breakdown_before: str
    breakdown_after: str


def extract_video_ids(text: str) -> set[str]:
    return set(YOUTUBE_URL_RE.findall(text))


def video_rows(text: str) -> dict[str, str]:
    rows: dict[str, str] = {}
    for match in ROW_RE.finditer(text):
        row = match.group(0)
        for video_id in YOUTUBE_URL_RE.findall(row):
            if video_id in rows:
                raise UpdateError(f"動画IDが複数行に重複しています: {video_id}")
            rows[video_id] = row
    return rows


def _section_bounds(text: str, title: str) -> tuple[int, int]:
    wanted = re.compile(rf"(?m)^==\s*{re.escape(title)}\s*==\s*$")
    match = wanted.search(text)
    if not match:
        raise UpdateError(f"セクション「{title}」が見つかりません。")
    next_heading = HEADING_RE.search(text, match.end())
    return match.start(), next_heading.start() if next_heading else len(text)


def _table_bounds(text: str, title: str) -> tuple[int, int]:
    section_start, section_end = _section_bounds(text, title)
    table_start = text.find('{| class="wikitable sortable"', section_start, section_end)
    if table_start < 0:
        raise UpdateError(f"セクション「{title}」のsortableテーブルが見つかりません。")
    table_end = text.find("|}", table_start, section_end)
    if table_end < 0:
        raise UpdateError(f"セクション「{title}」のテーブル終端が見つかりません。")
    return table_start, table_end


def _create_archive_section(text: str, year: int) -> str:
    headings = [(int(m.group(1)), m.start()) for m in ARCHIVE_HEADING_RE.finditer(text)]
    if not headings:
        raise UpdateError("既存の年別アーカイブセクションが見つかりません。")
    position: int | None = None
    for existing_year, start in headings:
        if existing_year < year:
            position = start
            break
    if position is None:
        try:
            position = _section_bounds(text, "通常動画")[0]
        except UpdateError:
            position = len(text)
    block = f"== {year}年アーカイブ ==\n{TABLE_HEADER}|}}\n\n"
    return text[:position] + block + text[position:]


def _create_short_section(text: str) -> str:
    _, regular_end = _section_bounds(text, "通常動画")
    block = (
        "== ショート ==\n"
        "公式YouTubeで公開されたショート動画。\n\n"
        f"{TABLE_HEADER}|}}\n\n"
    )
    return text[:regular_end] + block + text[regular_end:]


def _first_cell(row: str) -> str:
    lines = row.splitlines()[1:]
    for line in lines:
        if line.startswith("|") and not line.startswith("|-"):
            return line[1:].strip()
    return ""


def insert_entry(text: str, entry: VideoEntry) -> str:
    section = entry.section
    if entry.kind == "stream" and not re.search(
        rf"(?m)^==\s*{re.escape(section)}\s*==\s*$", text
    ):
        text = _create_archive_section(text, int(entry.published_jst[:4]))
    if entry.kind == "short" and not re.search(r"(?m)^==\s*ショート\s*==\s*$", text):
        text = _create_short_section(text)

    table_start, table_end = _table_bounds(text, section)
    # 終端 ``|}`` を含めないと、1行だけのテーブルではROW_REの終端条件が
    # 成立せず、その行を挿入位置の比較対象にできない。
    table = text[table_start:table_end + 2]
    insertion = table_end
    for row_match in ROW_RE.finditer(table):
        existing_date = _first_cell(row_match.group(0))
        if existing_date and existing_date < entry.published_jst:
            insertion = table_start + row_match.start()
            break
    return text[:insertion] + entry.row() + text[insertion:]


def archive_counts(text: str) -> dict[int, int]:
    counts: dict[int, int] = {}
    matches = list(ARCHIVE_HEADING_RE.finditer(text))
    for match in matches:
        next_heading = HEADING_RE.search(text, match.end())
        end = next_heading.start() if next_heading else len(text)
        rows = video_rows(text[match.end():end])
        counts[int(match.group(1))] = len(rows)
    if not counts:
        raise UpdateError("年別アーカイブを集計できませんでした。")
    return counts


def build_update(base_text: str, additions: Sequence[VideoEntry]) -> UpdateResult:
    base_rows = video_rows(base_text)
    addition_ids = [entry.video_id for entry in additions]
    if len(addition_ids) != len(set(addition_ids)):
        raise UpdateError("確認案の追加動画IDが重複しています。")
    duplicated = set(addition_ids) & set(base_rows)
    if duplicated:
        raise UpdateError(f"掲載済みIDを再追加しようとしています: {sorted(duplicated)}")

    text = base_text
    ordered = sorted(
        additions,
        key=lambda item: (item.published_jst, item.video_id),
        reverse=True,
    )
    for entry in ordered:
        text = insert_entry(text, entry)

    total_before_match = TOTAL_LINE_RE.search(base_text)
    breakdown_before_match = BREAKDOWN_LINE_RE.search(base_text)
    if not total_before_match or not breakdown_before_match:
        raise UpdateError("配信状況の総数または年別内訳の行が見つかりません。")

    counts = archive_counts(text)
    total_after = f"* 完了済みライブ配信（公開アーカイブ）: {sum(counts.values())}本"
    breakdown_after = "* 年別内訳: " + " / ".join(
        f"{year}年 {counts[year]}本" for year in sorted(counts)
    )
    text = TOTAL_LINE_RE.sub(total_after, text, count=1)
    text = BREAKDOWN_LINE_RE.sub(breakdown_after, text, count=1)

    after_rows = video_rows(text)
    for video_id, original_row in base_rows.items():
        if after_rows.get(video_id) != original_row:
            raise UpdateError(f"既存行が変更されました: {video_id}")
    if set(after_rows) - set(base_rows) != set(addition_ids):
        raise UpdateError("差分に予定外の動画IDが含まれています。")

    return UpdateResult(
        text=text,
        additions=tuple(ordered),
        total_before=total_before_match.group(0),
        total_after=total_after,
        breakdown_before=breakdown_before_match.group(0),
        breakdown_after=breakdown_after,
    )


def resolve_ytdlp() -> list[str]:
    executable = shutil.which("yt-dlp")
    if executable:
        return [executable]
    probe = subprocess.run(
        [sys.executable, "-m", "yt_dlp", "--version"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if probe.returncode == 0:
        return [sys.executable, "-m", "yt_dlp"]
    raise UpdateError("yt-dlpが見つかりません。`python -m pip install -U yt-dlp` が必要です。")


def _run_ytdlp_json(command: list[str], timeout: int) -> dict[str, Any]:
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        raise UpdateError("yt-dlpがタイムアウトしました。") from exc
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "詳細なし").strip().splitlines()
        raise UpdateError(f"yt-dlpエラー: {detail[-1] if detail else '詳細なし'}")
    raw = result.stdout.strip()
    try:
        return _json_object(json.loads(raw), "yt-dlp")
    except json.JSONDecodeError as exc:
        raise UpdateError("yt-dlpのJSONを解析できませんでした。") from exc


def collect_candidates(
    command: list[str], existing_ids: set[str], *, include_shorts: bool = False
) -> list[Candidate]:
    priority = {"video": 1, "stream": 2, "short": 3}
    candidates: dict[str, Candidate] = {}
    channel_tabs = CORE_CHANNEL_TABS + ((SHORTS_TAB,) if include_shorts else ())
    for kind, url in channel_tabs:
        payload = _run_ytdlp_json(
            command + ["--flat-playlist", "--dump-single-json", "--no-warnings", url],
            timeout=180,
        )
        entries = payload.get("entries")
        if not isinstance(entries, list):
            raise UpdateError(f"YouTubeの{kind}一覧にentriesがありません。")
        for raw_entry in entries:
            if not isinstance(raw_entry, dict):
                continue
            video_id = str(raw_entry.get("id") or "").strip()
            if not VIDEO_ID_RE.fullmatch(video_id) or video_id in existing_ids:
                continue
            status = str(raw_entry.get("live_status") or "").lower()
            if status in {"is_live", "is_upcoming", "post_live"}:
                continue
            candidate = Candidate(
                video_id=video_id,
                kind=kind,
                url=f"https://www.youtube.com/watch?v={video_id}",
            )
            previous = candidates.get(video_id)
            if previous is None or priority[kind] > priority[previous.kind]:
                candidates[video_id] = candidate
    return sorted(candidates.values(), key=lambda item: item.video_id)


def _format_duration(value: Any) -> str:
    try:
        seconds = int(round(float(value)))
    except (TypeError, ValueError):
        return ""
    if seconds < 0:
        return ""
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    return f"{minutes}:{seconds:02d}"


def _published_jst(metadata: dict[str, Any], kind: str) -> str:
    timestamp_keys = (
        ("release_timestamp", "timestamp")
        if kind == "stream"
        else ("timestamp", "release_timestamp")
    )
    for key in timestamp_keys:
        value = metadata.get(key)
        try:
            timestamp = float(value)
        except (TypeError, ValueError):
            continue
        local = dt.datetime.fromtimestamp(timestamp, tz=dt.timezone.utc).astimezone(JST)
        return local.strftime("%Y-%m-%d %H:%M")
    for key in ("release_date", "upload_date"):
        value = str(metadata.get(key) or "")
        if re.fullmatch(r"\d{8}", value):
            return f"{value[:4]}-{value[4:6]}-{value[6:8]}"
    return ""


def classify_tag(title: str, kind: str) -> str:
    lowered = title.casefold()
    if any(word in lowered for word in ("asmr", "バイノーラル", "朗読asmr")):
        return "ASMR"
    if kind != "stream" and "歌ってみた" in title:
        return "歌ってみた"
    race_names = ("安田記念", "宝塚記念", "日本ダービー", "有馬記念", "天皇賞")
    if (
        "同時視聴" in title
        or "実況" in title
        or any(name in title for name in race_names)
        or re.search(r"\bvs\.?\b", lowered)
    ):
        return "同時視聴"
    if "耐久" in title:
        return "耐久"
    if any(word in title for word in ("おでかけ", "水族館", "潜入")):
        return "おでかけ"
    if any(
        word in lowered
        for word in ("マインクラフト", "minecraft", "マイクラ", "apex", "ゲーム")
    ):
        return "ゲーム"
    if any(word in title for word in ("歌枠", "歌配信", "歌います")) and kind == "stream":
        return "歌枠"
    if any(word in title for word in ("雑談", "おしゃべり", "お話し", "お喋り")):
        return "雑談"
    if any(
        word in title
        for word in (
            "裁判",
            "AI裁判",
            "大喜利",
            "クイズ",
            "選考会",
            "マシュマロ",
            "エイプリルフール",
            "七夕",
            "ハロウィン",
            "逆転",
            "指導",
            "ギャル化",
            "やばたにえん",
            "AIギャルゲー",
            "AIギャルゲ",
        )
    ):
        return "企画"
    if any(word in title for word in ("初配信", "突破", "ただいま")) or (
        "記念" in title and not any(name in title for name in race_names)
    ):
        return "記念"
    if any(word in title for word in ("初見向け", "分かる", "紹介")):
        return "紹介"
    if any(word in lowered for word in ("gdc", "展示会", "レポート")):
        return "レポート"
    if any(word in title for word in ("まとめ", "総集編")):
        return "まとめ"
    return ""


def entry_from_metadata(candidate: Candidate, metadata: dict[str, Any]) -> VideoEntry:
    status = str(metadata.get("live_status") or "").lower()
    if status in {"is_live", "is_upcoming", "post_live"}:
        raise UpdateError(f"配信が終了していません（状態: {status}）。")
    if candidate.kind == "stream" and status not in {"was_live", "not_live"}:
        try:
            duration = float(metadata.get("duration") or 0)
        except (TypeError, ValueError):
            duration = 0
        if duration <= 0:
            raise UpdateError("終了済み配信であることを確認できませんでした。")
    video_id = str(metadata.get("id") or candidate.video_id).strip()
    if video_id != candidate.video_id:
        raise UpdateError("個別メタデータの動画IDが一覧と一致しません。")
    title = str(metadata.get("title") or "").strip()
    if not title:
        raise UpdateError("正式タイトルを取得できませんでした。")
    # YouTubeでは過去配信がvideosタブにも現れる場合がある。個別メタデータが
    # was_liveなら、一覧タブより強い根拠としてアーカイブへ振り分ける。
    kind = "stream" if status == "was_live" else candidate.kind
    published = _published_jst(metadata, kind)
    if not published:
        raise UpdateError("絶対日付を取得できませんでした。")
    return VideoEntry(
        video_id=candidate.video_id,
        kind=kind,
        published_jst=published,
        tag=classify_tag(title, kind),
        duration=_format_duration(metadata.get("duration")),
        title=title,
    )


def fetch_entries(
    command: list[str], candidates: Sequence[Candidate], workers: int
) -> tuple[list[VideoEntry], list[ManualItem]]:
    def fetch(candidate: Candidate) -> tuple[Candidate, dict[str, Any] | None, str | None]:
        try:
            metadata = _run_ytdlp_json(
                command
                + [
                    "--dump-single-json",
                    "--skip-download",
                    "--no-playlist",
                    "--no-warnings",
                    "--ignore-no-formats-error",
                    candidate.url,
                ],
                timeout=120,
            )
            return candidate, metadata, None
        except UpdateError as exc:
            return candidate, None, str(exc)

    entries: list[VideoEntry] = []
    manual: list[ManualItem] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        for candidate, metadata, error in executor.map(fetch, candidates):
            if error or metadata is None:
                manual.append(ManualItem(candidate.video_id, candidate.kind, error or "取得失敗"))
                continue
            try:
                entries.append(entry_from_metadata(candidate, metadata))
            except UpdateError as exc:
                manual.append(ManualItem(candidate.video_id, candidate.kind, str(exc)))
    return entries, manual


def _entry_from_dict(value: dict[str, Any]) -> VideoEntry:
    allowed_kinds = {"stream", "video", "short"}
    entry = VideoEntry(
        video_id=str(value.get("video_id") or ""),
        kind=str(value.get("kind") or ""),
        published_jst=str(value.get("published_jst") or ""),
        tag=str(value.get("tag") or ""),
        duration=str(value.get("duration") or ""),
        title=str(value.get("title") or ""),
    )
    if not VIDEO_ID_RE.fullmatch(entry.video_id):
        raise UpdateError(f"動画IDが不正です: {entry.video_id}")
    if entry.kind not in allowed_kinds:
        raise UpdateError(f"動画種別が不正です: {entry.kind}")
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}(?: \d{2}:\d{2})?", entry.published_jst):
        raise UpdateError(f"公開日時が不正です: {entry.published_jst}")
    if not entry.title.strip():
        raise UpdateError(f"タイトルが不正です: {entry.video_id}")
    if entry.tag and entry.tag != sanitize_field(entry.tag):
        raise UpdateError("タグにマークアップが含まれています。")
    if entry.duration and not re.fullmatch(r"(?:[0-9]+:)?[0-9]+:[0-5][0-9]", entry.duration):
        raise UpdateError("再生時間が不正です。")
    return entry


def render_review(snapshot: PageSnapshot, result: UpdateResult, manual: Sequence[ManualItem]) -> str:
    count_changes = sum(
        before != after
        for before, after in (
            (result.total_before, result.total_after),
            (result.breakdown_before, result.breakdown_after),
        )
    )
    lines = [
        "【変更サマリー】",
        f"- 基準リビジョン: {snapshot.revid}",
        f"- 追記: {len(result.additions)}件",
        f"- 置換: {count_changes}件（配信状況の再集計）",
    ]
    for index, entry in enumerate(result.additions, 1):
        lines.extend(
            [
                "",
                f"【{index}件目 / 追記】対象ページ: {PAGE_TITLE}",
                f"挿入先: == {entry.section} == のテーブル（日付降順）",
                "追加する行:",
                entry.row().rstrip(),
            ]
        )
    if result.total_before != result.total_after:
        lines.extend(
            [
                "",
                "【置換】対象: 配信状況・完了済みライブ配信",
                f"置換前: {result.total_before}",
                f"置換後: {result.total_after}",
            ]
        )
    if result.breakdown_before != result.breakdown_after:
        lines.extend(
            [
                "",
                "【置換】対象: 配信状況・年別内訳",
                f"置換前: {result.breakdown_before}",
                f"置換後: {result.breakdown_after}",
            ]
        )
    if manual:
        lines.extend(["", "【手動確認が必要な動画・配信】"])
        for item in manual:
            lines.append(
                f"- {item.video_id} ({item.kind}): {item.reason} "
                f"https://www.youtube.com/watch?v={item.video_id}"
            )
    else:
        lines.extend(["", "すべての候補について絶対日付を確認できました。"])

    diff = "\n".join(
        difflib.unified_diff(
            snapshot.text.splitlines(),
            result.text.splitlines(),
            fromfile=f"{PAGE_TITLE}@{snapshot.revid}",
            tofile=f"{PAGE_TITLE}@確認案",
            lineterm="",
            n=2,
        )
    )
    lines.extend(["", "【監査用差分】", diff or "（変更なし）"])
    return "\n".join(lines)


def save_plan(
    path: Path,
    snapshot: PageSnapshot,
    result: UpdateResult,
    manual: Sequence[ManualItem],
) -> None:
    payload = {
        "schema_version": PLAN_SCHEMA,
        "api_url": API_URL,
        "page_title": PAGE_TITLE,
        "page_url": PAGE_URL,
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "base_revid": snapshot.revid,
        "base_timestamp": snapshot.timestamp,
        "base_sha256": sha256_text(snapshot.text),
        "base_text": snapshot.text,
        "proposed_sha256": sha256_text(result.text),
        "proposed_text": result.text,
        "additions": [dataclasses.asdict(item) for item in result.additions],
        "manual": [dataclasses.asdict(item) for item in manual],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_plan(path: Path) -> tuple[dict[str, Any], list[VideoEntry]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise UpdateError(f"確認案を読めません: {path}") from exc
    except json.JSONDecodeError as exc:
        raise UpdateError(f"確認案がJSONではありません: {path}") from exc
    plan = _json_object(payload, "確認案")
    if plan.get("schema_version") != PLAN_SCHEMA:
        raise UpdateError("確認案のスキーマバージョンが一致しません。")
    if plan.get("api_url") != API_URL or plan.get("page_title") != PAGE_TITLE:
        raise UpdateError("確認案の編集先が許可されたページと一致しません。")
    raw_additions = plan.get("additions")
    if not isinstance(raw_additions, list):
        raise UpdateError("確認案に追加項目がありません。")
    additions = [_entry_from_dict(_json_object(item, "追加項目")) for item in raw_additions]
    return plan, additions


def validate_plan(plan: dict[str, Any], additions: Sequence[VideoEntry]) -> UpdateResult:
    base_text = plan.get("base_text")
    proposed_text = plan.get("proposed_text")
    if not isinstance(base_text, str) or not isinstance(proposed_text, str):
        raise UpdateError("確認案に基準本文または反映本文がありません。")
    if sha256_text(base_text) != plan.get("base_sha256"):
        raise UpdateError("確認案の基準本文ハッシュが一致しません。")
    rebuilt = build_update(base_text, additions)
    if rebuilt.text != proposed_text or sha256_text(proposed_text) != plan.get("proposed_sha256"):
        raise UpdateError("確認案を同じ差分から再構築できません。改変の可能性があります。")
    return rebuilt


def excluded_streams(path: Path | None = None) -> dict[str, str]:
    path = path or EXCLUDED_STREAMS
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream, delimiter="\t")
        if reader.fieldnames != ["video_id", "reason"]:
            raise UpdateError("Wiki除外リストのヘッダが不正です。")
        excluded = {}
        for row in reader:
            vid, reason = row["video_id"], row["reason"]
            if not VIDEO_ID_RE.fullmatch(vid or "") or not (reason or "").strip() or vid in excluded or None in row:
                raise UpdateError(f"Wiki除外リストの不正な行: {reader.line_num}")
            excluded[vid] = reason
        return excluded


def command_check(args: argparse.Namespace) -> int:
    client = MediaWikiClient(allowed_titles=(PAGE_TITLE,))
    # 公開ページのソース確認には認証を使わない。Bot Passwordを読むのは
    # auth-checkと、ユーザー承認後のapplyだけに限定する。
    snapshot = client.fetch_page(PAGE_TITLE)
    if snapshot.title != PAGE_TITLE:
        raise UpdateError(f"取得したページ名が一致しません: {snapshot.title}")
    existing_ids = extract_video_ids(snapshot.text)
    command = resolve_ytdlp()
    candidates = collect_candidates(
        command, existing_ids, include_shorts=args.include_shorts
    )
    excluded = excluded_streams()
    omitted = [ManualItem(item.video_id, item.kind, excluded[item.video_id])
               for item in candidates if item.video_id in excluded]
    candidates = [item for item in candidates if item.video_id not in excluded]
    entries, manual = fetch_entries(command, candidates, args.workers)
    manual.extend(omitted)
    result = build_update(snapshot.text, entries)
    plan_path = args.plan or (
        DEFAULT_PLAN_DIR
        / f"video-streams-r{snapshot.revid}-{sha256_text(result.text)[:12]}.json"
    )
    save_plan(plan_path, snapshot, result, manual)
    print(render_review(snapshot, result, manual))
    print(f"\n確認案: {plan_path.resolve()}")
    if result.text == snapshot.text:
        print("\nWikiへ反映する変更はありません。")
    else:
        print("\nまだWikiは変更していません。この差分への明示的な承認を待ってください。")
    return 0


def command_apply(args: argparse.Namespace) -> int:
    if not args.yes:
        raise UpdateError("反映には、表示済み差分への承認後に --yes が必要です。")
    plan, additions = load_plan(args.plan)
    rebuilt = validate_plan(plan, additions)
    excluded = set(excluded_streams()).intersection(entry.video_id for entry in additions)
    if excluded:
        raise UpdateError(f"確認案に現在の除外IDが含まれます。checkから再作成: {sorted(excluded)}")
    if rebuilt.text == plan["base_text"]:
        raise UpdateError("確認案に反映対象の変更がありません。")

    try:
        with apply_attempt(PAGE_TITLE):
            return publish_plan(plan, rebuilt, additions)
    except (OSError, UpdateError, ValueError):
        print("基準版に変更がなく、未反映と確認できた場合の再実行:")
        print(f'python "{Path(__file__)}" apply --plan "{args.plan}" --yes')
        raise


def publish_plan(plan, rebuilt, additions) -> int:
    credentials = read_credentials(required=True)
    assert credentials is not None
    client = MediaWikiClient(allowed_titles=(PAGE_TITLE,))
    client.login(*credentials)
    current = client.fetch_page(PAGE_TITLE)
    if current.text == rebuilt.text:
        print(f"承認済み本文は保存済みです（リビジョン {current.revid}）。")
        report_saved_revision(client, PAGE_TITLE, current.revid)
        return 0
    if current.revid != int(plan.get("base_revid") or 0):
        raise UpdateError(
            f"確認後にWikiが更新されています（確認時 {plan.get('base_revid')} / "
            f"現在 {current.revid}）。checkからやり直してください。"
        )
    if sha256_text(current.text) != plan.get("base_sha256"):
        raise UpdateError("現在のWiki本文が確認時と一致しません。checkからやり直してください。")

    summary = f"動画・配信一覧を更新（YouTube公開分{len(additions)}件を追加）"
    new_revid = client.edit_page(current, rebuilt.text, summary)
    verified = client.fetch_page(PAGE_TITLE)
    if verified.revid != new_revid or verified.text != rebuilt.text:
        raise UpdateError(
            f"編集はリビジョン{new_revid}として受理されましたが、反映後検証が一致しません。"
        )
    missing = {entry.video_id for entry in additions} - extract_video_ids(verified.text)
    if missing:
        raise UpdateError(f"反映後に追加IDを確認できません: {sorted(missing)}")
    print(f"反映しました: {PAGE_TITLE}（新リビジョン {new_revid}）")
    print(f"確認URL: {PAGE_URL}?oldid={new_revid}")
    print("追加動画ID: " + ", ".join(entry.video_id for entry in additions))
    report_saved_revision(client, PAGE_TITLE, new_revid)
    return 0


def command_auth_check(args: argparse.Namespace) -> int:
    del args
    credentials = read_credentials(required=True)
    assert credentials is not None
    client = MediaWikiClient(allowed_titles=(PAGE_TITLE,))
    client.login(*credentials)
    snapshot = client.fetch_page(PAGE_TITLE)
    print(
        f"認証と読み取りに成功しました: {snapshot.title} "
        f"（リビジョン {snapshot.revid}、編集はしていません）"
    )
    return 0


def command_unlock(args: argparse.Namespace) -> int:
    if not args.yes:
        raise UpdateError("失敗原因を確認してから unlock --yes を指定してください。")
    with apply_attempt(PAGE_TITLE, unlock=True):
        pass
    print(f"{PAGE_TITLE} の失敗ロックを解除しました。")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="しずくWiki「動画・配信」の差分を確認し、承認後に反映します。"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    check = subparsers.add_parser("check", help="差分案を作る（Wikiは編集しない）")
    check.add_argument(
        "--plan",
        type=Path,
        help="確認案JSONの保存先（省略時はリビジョンと差分ハッシュを含む名前）",
    )
    check.add_argument("--workers", type=int, default=4, help="個別動画の並列取得数")
    check.add_argument(
        "--include-shorts",
        action="store_true",
        help="通常は除外するショートも照合対象に含める",
    )
    check.set_defaults(handler=command_check)

    apply = subparsers.add_parser("apply", help="表示・承認済みの確認案を反映する")
    apply.add_argument("--plan", type=Path, required=True, help="表示・承認済みの確認案JSON")
    apply.add_argument("--yes", action="store_true", help="表示済み差分への明示承認を示す")
    apply.set_defaults(handler=command_apply)

    auth = subparsers.add_parser("auth-check", help="Bot Passwordで認証と読み取りだけを確認する")
    auth.set_defaults(handler=command_auth_check)
    unlock = subparsers.add_parser("unlock", help="失敗原因を確認した後で連続失敗ロックを解除")
    unlock.add_argument("--yes", action="store_true")
    unlock.set_defaults(handler=command_unlock)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if getattr(args, "workers", 1) < 1 or getattr(args, "workers", 1) > 8:
        raise UpdateError("--workers は1〜8で指定してください。")
    return int(args.handler(args))


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, UpdateError, ValueError) as error:
        print(f"[Error] {error}", file=sys.stderr)
        raise SystemExit(1)
