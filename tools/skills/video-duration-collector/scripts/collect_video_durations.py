#!/usr/bin/env python3
"""Collect video durations from YouTube and other supported video pages.

Backends (auto order):
1. YouTube Data API v3, when an API key is available
2. yt-dlp metadata extraction (no media download)
3. Generic HTML metadata (JSON-LD, itemprop/meta duration, YouTube lengthSeconds)

The script preserves input order, deduplicates network work, and formats every
successful duration as H:MM:SS.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import csv
import html
import io
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable, Iterator, Sequence

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)
YOUTUBE_HOSTS = {
    "youtube.com",
    "www.youtube.com",
    "m.youtube.com",
    "music.youtube.com",
    "youtu.be",
    "www.youtu.be",
    "youtube-nocookie.com",
    "www.youtube-nocookie.com",
}
ISO_DURATION_RE = re.compile(
    r"^P"
    r"(?:(?P<days>\d+(?:\.\d+)?)D)?"
    r"(?:T"
    r"(?:(?P<hours>\d+(?:\.\d+)?)H)?"
    r"(?:(?P<minutes>\d+(?:\.\d+)?)M)?"
    r"(?:(?P<seconds>\d+(?:\.\d+)?)S)?"
    r")?$",
    re.IGNORECASE,
)


@dataclass
class VideoResult:
    index: int
    url: str
    platform: str = ""
    video_id: str = ""
    title: str = ""
    duration: str = ""
    seconds: int | None = None
    status: str = "error"
    source: str = ""
    confidence: str = ""
    note: str = ""

    def clone_for(self, index: int, url: str) -> "VideoResult":
        data = asdict(self)
        data["index"] = index
        data["url"] = url
        return VideoResult(**data)


@dataclass
class CacheEntry:
    saved_at: float
    result: dict[str, Any]


def eprint(*args: object) -> None:
    print(*args, file=sys.stderr)


def normalize_input_url(value: str) -> str:
    value = value.strip()
    if not value:
        return ""
    # Accept bare domain-like inputs while avoiding accidental conversion of IDs.
    if "://" not in value and re.match(r"^(?:www\.)?[A-Za-z0-9.-]+\.[A-Za-z]{2,}/", value):
        value = "https://" + value
    return value


def youtube_video_id(url: str) -> str | None:
    try:
        parsed = urllib.parse.urlparse(url)
    except ValueError:
        return None
    host = parsed.netloc.lower().split(":", 1)[0]
    if host not in YOUTUBE_HOSTS:
        return None

    if host.endswith("youtu.be"):
        candidate = parsed.path.strip("/").split("/", 1)[0]
    else:
        parts = [p for p in parsed.path.split("/") if p]
        if parsed.path == "/watch":
            candidate = urllib.parse.parse_qs(parsed.query).get("v", [""])[0]
        elif len(parts) >= 2 and parts[0] in {"shorts", "live", "embed", "v"}:
            candidate = parts[1]
        else:
            candidate = urllib.parse.parse_qs(parsed.query).get("v", [""])[0]

    candidate = candidate.strip()
    return candidate if re.fullmatch(r"[A-Za-z0-9_-]{6,20}", candidate) else None


def platform_name(url: str) -> str:
    try:
        host = urllib.parse.urlparse(url).netloc.lower().split(":", 1)[0]
    except ValueError:
        return "unknown"
    if youtube_video_id(url):
        return "YouTube"
    aliases = {
        "vimeo.com": "Vimeo",
        "www.vimeo.com": "Vimeo",
        "twitch.tv": "Twitch",
        "www.twitch.tv": "Twitch",
        "nicovideo.jp": "Niconico",
        "www.nicovideo.jp": "Niconico",
        "dailymotion.com": "Dailymotion",
        "www.dailymotion.com": "Dailymotion",
        "instagram.com": "Instagram",
        "www.instagram.com": "Instagram",
        "tiktok.com": "TikTok",
        "www.tiktok.com": "TikTok",
    }
    return aliases.get(host, host or "unknown")


def format_hms(seconds: int | float) -> str:
    total = max(0, int(round(float(seconds))))
    hours, rem = divmod(total, 3600)
    minutes, secs = divmod(rem, 60)
    return f"{hours}:{minutes:02d}:{secs:02d}"


def parse_iso8601_duration(value: str) -> int | None:
    value = value.strip()
    match = ISO_DURATION_RE.fullmatch(value)
    if not match:
        return None
    parts = {name: float(number or 0) for name, number in match.groupdict().items()}
    seconds = (
        parts["days"] * 86400
        + parts["hours"] * 3600
        + parts["minutes"] * 60
        + parts["seconds"]
    )
    return int(round(seconds))


def parse_duration_value(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return max(0, int(round(value)))
    if not isinstance(value, str):
        return None
    text = html.unescape(value).strip()
    if not text:
        return None
    if text.upper().startswith("P"):
        return parse_iso8601_duration(text)
    if re.fullmatch(r"\d+(?:\.\d+)?", text):
        return max(0, int(round(float(text))))
    if re.fullmatch(r"\d+(?::\d{1,2}){1,3}", text):
        nums = [int(part) for part in text.split(":")]
        total = 0
        for number in nums:
            total = total * 60 + number
        return total
    return None


def chunks(values: Sequence[str], size: int) -> Iterator[Sequence[str]]:
    for start in range(0, len(values), size):
        yield values[start : start + size]


def request_json(url: str, timeout: float) -> dict[str, Any]:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.load(response)


def fetch_youtube_api(
    id_to_url: dict[str, str], api_key: str, timeout: float
) -> dict[str, VideoResult]:
    output: dict[str, VideoResult] = {}
    ids = list(id_to_url)
    for group in chunks(ids, 50):
        query = urllib.parse.urlencode(
            {
                "part": "snippet,contentDetails,status,liveStreamingDetails",
                "id": ",".join(group),
                "key": api_key,
            }
        )
        endpoint = "https://www.googleapis.com/youtube/v3/videos?" + query
        try:
            payload = request_json(endpoint, timeout)
        except Exception as exc:  # Network/API detail is captured as a backend note.
            for video_id in group:
                output[video_id] = VideoResult(
                    index=0,
                    url=id_to_url[video_id],
                    platform="YouTube",
                    video_id=video_id,
                    status="error",
                    source="youtube_api",
                    confidence="",
                    note=f"YouTube API error: {exc}",
                )
            continue

        returned: set[str] = set()
        for item in payload.get("items", []):
            video_id = str(item.get("id", ""))
            if not video_id:
                continue
            returned.add(video_id)
            snippet = item.get("snippet") or {}
            details = item.get("contentDetails") or {}
            live = str(snippet.get("liveBroadcastContent", "none"))
            seconds = parse_duration_value(details.get("duration"))
            status = "ok"
            note = ""
            if seconds is None or (seconds == 0 and live in {"live", "upcoming"}):
                status = live if live in {"live", "upcoming"} else "unavailable"
                note = (
                    "Live/upcoming streams do not have a final archived duration yet."
                    if live in {"live", "upcoming"}
                    else "Duration was not returned by the API."
                )
            output[video_id] = VideoResult(
                index=0,
                url=id_to_url[video_id],
                platform="YouTube",
                video_id=video_id,
                title=str(snippet.get("title", "")),
                duration=format_hms(seconds) if seconds is not None and status == "ok" else "",
                seconds=seconds if status == "ok" else None,
                status=status,
                source="youtube_api",
                confidence="high" if status == "ok" else "",
                note=note,
            )

        for video_id in group:
            if video_id not in returned and video_id not in output:
                output[video_id] = VideoResult(
                    index=0,
                    url=id_to_url[video_id],
                    platform="YouTube",
                    video_id=video_id,
                    status="unavailable",
                    source="youtube_api",
                    note="Video was not returned (private, deleted, invalid, or inaccessible).",
                )
    return output


def yt_dlp_command() -> list[str] | None:
    executable = shutil.which("yt-dlp")
    if executable:
        return [executable]
    # Support environments where only the Python package is installed.
    try:
        __import__("yt_dlp")
    except ImportError:
        return None
    return [sys.executable, "-m", "yt_dlp"]


def fetch_one_ytdlp(
    url: str,
    timeout: float,
    cookies_from_browser: str | None,
    extra_args: Sequence[str],
) -> VideoResult:
    command = yt_dlp_command()
    if command is None:
        return VideoResult(
            index=0,
            url=url,
            platform=platform_name(url),
            video_id=youtube_video_id(url) or "",
            status="error",
            source="yt_dlp",
            note="yt-dlp is not installed.",
        )

    args = command + [
        "--simulate",
        "--dump-single-json",
        "--no-playlist",
        "--no-warnings",
        "--ignore-no-formats-error",
        "--socket-timeout",
        str(max(1, int(timeout))),
    ]
    if cookies_from_browser:
        args += ["--cookies-from-browser", cookies_from_browser]
    args += list(extra_args)
    args += ["--", url]

    try:
        completed = subprocess.run(
            args,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=max(10.0, timeout + 10.0),
            check=False,
        )
    except subprocess.TimeoutExpired:
        return VideoResult(
            index=0,
            url=url,
            platform=platform_name(url),
            video_id=youtube_video_id(url) or "",
            status="error",
            source="yt_dlp",
            note="yt-dlp timed out.",
        )
    except OSError as exc:
        return VideoResult(
            index=0,
            url=url,
            platform=platform_name(url),
            video_id=youtube_video_id(url) or "",
            status="error",
            source="yt_dlp",
            note=f"Could not run yt-dlp: {exc}",
        )

    payload: dict[str, Any] | None = None
    # yt-dlp can write informational lines before JSON in unusual environments.
    for line in reversed(completed.stdout.splitlines()):
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            payload = json.loads(line)
            break
        except json.JSONDecodeError:
            continue

    if payload is None:
        error_text = completed.stderr.strip().splitlines()
        note = error_text[-1] if error_text else f"yt-dlp exited with code {completed.returncode}."
        low = note.lower()
        status = "unavailable" if any(word in low for word in ("private", "unavailable", "removed", "deleted")) else "error"
        return VideoResult(
            index=0,
            url=url,
            platform=platform_name(url),
            video_id=youtube_video_id(url) or "",
            status=status,
            source="yt_dlp",
            note=note[:500],
        )

    seconds = parse_duration_value(payload.get("duration"))
    live_status = str(payload.get("live_status") or "")
    if seconds is None and live_status in {"is_live", "is_upcoming", "post_live"}:
        status = "live" if live_status == "is_live" else "upcoming" if live_status == "is_upcoming" else "processing"
        note = "A final VOD duration is not available yet."
    elif seconds is None:
        status = "unavailable"
        note = "yt-dlp did not return a duration."
    else:
        status = "ok"
        note = ""

    extractor = str(payload.get("extractor_key") or payload.get("extractor") or "")
    return VideoResult(
        index=0,
        url=url,
        platform=extractor or platform_name(url),
        video_id=str(payload.get("id") or youtube_video_id(url) or ""),
        title=str(payload.get("title") or payload.get("fulltitle") or ""),
        duration=format_hms(seconds) if seconds is not None and status == "ok" else "",
        seconds=seconds if status == "ok" else None,
        status=status,
        source="yt_dlp",
        confidence="high" if status == "ok" else "",
        note=note,
    )


def _walk_json(value: Any) -> Iterable[Any]:
    yield value
    if isinstance(value, dict):
        for child in value.values():
            yield from _walk_json(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_json(child)


def _jsonld_candidates(document: str) -> list[tuple[int, str, str]]:
    candidates: list[tuple[int, str, str]] = []
    pattern = re.compile(
        r"<script\b[^>]*type\s*=\s*(['\"])application/ld\+json\1[^>]*>(.*?)</script>",
        re.IGNORECASE | re.DOTALL,
    )
    for match in pattern.finditer(document):
        raw = html.unescape(match.group(2)).strip()
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            continue
        for node in _walk_json(payload):
            if not isinstance(node, dict) or "duration" not in node:
                continue
            seconds = parse_duration_value(node.get("duration"))
            if seconds is None:
                continue
            node_type = node.get("@type", "")
            if isinstance(node_type, list):
                types = {str(x).lower() for x in node_type}
            else:
                types = {str(node_type).lower()}
            score = 3 if "videoobject" in types else 2 if "mediaobject" in types else 1
            title = str(node.get("name") or node.get("headline") or "")
            candidates.append((score, title, format_hms(seconds)))
    return candidates


def _extract_meta(document: str) -> tuple[int | None, str, str]:
    # First, a YouTube page's own player metadata. The value is in seconds.
    match = re.search(r'"lengthSeconds"\s*:\s*"(?P<seconds>\d+)"', document)
    if match:
        seconds = int(match.group("seconds"))
        title_match = re.search(r'"title"\s*:\s*"((?:\\.|[^"\\])*)"', document)
        title = ""
        if title_match:
            try:
                title = json.loads('"' + title_match.group(1) + '"')
            except json.JSONDecodeError:
                title = ""
        return seconds, title, "youtube_html"

    candidates = _jsonld_candidates(document)
    if candidates:
        candidates.sort(key=lambda row: row[0], reverse=True)
        score, title, hms = candidates[0]
        seconds = parse_duration_value(hms)
        return seconds, title, "json_ld"

    # Generic metadata. og:video:duration is normally seconds; itemprop duration
    # commonly uses ISO 8601.
    meta_tag_re = re.compile(r"<meta\b[^>]*>", re.IGNORECASE)
    attr_re = re.compile(r"([:\w-]+)\s*=\s*(['\"])(.*?)\2", re.IGNORECASE | re.DOTALL)
    title = ""
    for tag in meta_tag_re.findall(document):
        attrs = {key.lower(): html.unescape(value.strip()) for key, _, value in attr_re.findall(tag)}
        key = (attrs.get("property") or attrs.get("name") or attrs.get("itemprop") or "").lower()
        content = attrs.get("content", "")
        if key in {"og:title", "twitter:title"} and not title:
            title = content
        if key in {"duration", "video:duration", "og:video:duration"}:
            seconds = parse_duration_value(content)
            if seconds is not None:
                return seconds, title, "html_meta"
    return None, title, "html"


def fetch_one_html(url: str, timeout: float) -> VideoResult:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "en-US,en;q=0.8,ja;q=0.6",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            content_type = response.headers.get_content_type()
            if content_type not in {"text/html", "application/xhtml+xml"}:
                return VideoResult(
                    index=0,
                    url=url,
                    platform=platform_name(url),
                    video_id=youtube_video_id(url) or "",
                    status="error",
                    source="html",
                    note=f"Unsupported content type: {content_type}",
                )
            raw = response.read(8 * 1024 * 1024)
            charset = response.headers.get_content_charset() or "utf-8"
            document = raw.decode(charset, errors="replace")
    except urllib.error.HTTPError as exc:
        status = "unavailable" if exc.code in {401, 403, 404, 410, 451} else "error"
        return VideoResult(
            index=0,
            url=url,
            platform=platform_name(url),
            video_id=youtube_video_id(url) or "",
            status=status,
            source="html",
            note=f"HTTP {exc.code}: {exc.reason}",
        )
    except Exception as exc:
        return VideoResult(
            index=0,
            url=url,
            platform=platform_name(url),
            video_id=youtube_video_id(url) or "",
            status="error",
            source="html",
            note=f"HTML fetch error: {exc}",
        )

    seconds, title, source = _extract_meta(document)
    if seconds is None:
        title_match = re.search(r"<title\b[^>]*>(.*?)</title>", document, re.IGNORECASE | re.DOTALL)
        if title_match and not title:
            title = html.unescape(re.sub(r"\s+", " ", title_match.group(1))).strip()
        return VideoResult(
            index=0,
            url=url,
            platform=platform_name(url),
            video_id=youtube_video_id(url) or "",
            title=title,
            status="unavailable",
            source=source,
            note="No trustworthy duration metadata was found in the page.",
        )
    return VideoResult(
        index=0,
        url=url,
        platform=platform_name(url),
        video_id=youtube_video_id(url) or "",
        title=title,
        duration=format_hms(seconds),
        seconds=seconds,
        status="ok",
        source=source,
        confidence="medium" if source in {"json_ld", "html_meta"} else "high",
    )


def load_cache(path: Path | None) -> dict[str, CacheEntry]:
    if path is None or not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    cache: dict[str, CacheEntry] = {}
    for key, value in payload.items():
        if not isinstance(value, dict):
            continue
        try:
            cache[key] = CacheEntry(float(value["saved_at"]), dict(value["result"]))
        except (KeyError, TypeError, ValueError):
            continue
    return cache


def save_cache(path: Path | None, cache: dict[str, CacheEntry]) -> None:
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {key: {"saved_at": entry.saved_at, "result": entry.result} for key, entry in cache.items()}
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(path)


def cacheable(result: VideoResult) -> bool:
    return result.status == "ok" and result.seconds is not None


def result_from_cache(entry: CacheEntry, url: str) -> VideoResult:
    data = dict(entry.result)
    data["index"] = 0
    data["url"] = url
    data["source"] = "cache:" + str(data.get("source", ""))
    return VideoResult(**data)


def collect(
    urls: Sequence[str],
    backend: str,
    api_key: str | None,
    timeout: float,
    workers: int,
    cookies_from_browser: str | None,
    yt_dlp_args: Sequence[str],
    cache_file: Path | None,
    cache_ttl: float,
) -> list[VideoResult]:
    normalized = [normalize_input_url(url) for url in urls]
    unique_urls = list(dict.fromkeys(url for url in normalized if url))
    results: dict[str, VideoResult] = {}

    cache = load_cache(cache_file)
    now = time.time()
    for url in unique_urls:
        entry = cache.get(url)
        if entry and (cache_ttl <= 0 or now - entry.saved_at <= cache_ttl):
            results[url] = result_from_cache(entry, url)

    unresolved = [url for url in unique_urls if url not in results]

    if backend in {"auto", "youtube-api"} and api_key:
        id_to_url = {
            video_id: url
            for url in unresolved
            if (video_id := youtube_video_id(url)) is not None
        }
        api_results = fetch_youtube_api(id_to_url, api_key, timeout)
        for video_id, result in api_results.items():
            # In auto mode, only terminal successes are accepted; failures can fall back.
            if backend == "youtube-api" or result.status == "ok":
                results[id_to_url[video_id]] = result
        unresolved = [url for url in unique_urls if url not in results]
    elif backend == "youtube-api" and not api_key:
        for url in unresolved:
            results[url] = VideoResult(
                index=0,
                url=url,
                platform=platform_name(url),
                video_id=youtube_video_id(url) or "",
                status="error",
                source="youtube_api",
                note="No YouTube API key was provided.",
            )
        unresolved = []

    if backend in {"auto", "yt-dlp"} and unresolved:
        with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, workers)) as executor:
            futures = {
                executor.submit(fetch_one_ytdlp, url, timeout, cookies_from_browser, yt_dlp_args): url
                for url in unresolved
            }
            for future in concurrent.futures.as_completed(futures):
                url = futures[future]
                try:
                    result = future.result()
                except Exception as exc:
                    result = VideoResult(
                        index=0,
                        url=url,
                        platform=platform_name(url),
                        video_id=youtube_video_id(url) or "",
                        status="error",
                        source="yt_dlp",
                        note=f"Unexpected yt-dlp worker error: {exc}",
                    )
                if backend == "yt-dlp" or result.status == "ok":
                    results[url] = result
        unresolved = [url for url in unique_urls if url not in results]

    if backend in {"auto", "html"} and unresolved:
        with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, workers)) as executor:
            futures = {executor.submit(fetch_one_html, url, timeout): url for url in unresolved}
            for future in concurrent.futures.as_completed(futures):
                url = futures[future]
                try:
                    results[url] = future.result()
                except Exception as exc:
                    results[url] = VideoResult(
                        index=0,
                        url=url,
                        platform=platform_name(url),
                        video_id=youtube_video_id(url) or "",
                        status="error",
                        source="html",
                        note=f"Unexpected HTML worker error: {exc}",
                    )

    # Persist successful non-live values only.
    for url, result in results.items():
        if cacheable(result) and not result.source.startswith("cache:"):
            cache[url] = CacheEntry(time.time(), asdict(result))
    save_cache(cache_file, cache)

    ordered: list[VideoResult] = []
    for index, url in enumerate(normalized, start=1):
        if not url:
            ordered.append(VideoResult(index=index, url="", status="error", note="Blank input."))
            continue
        ordered.append(results.get(url, VideoResult(index=0, url=url, note="No backend produced a result.")).clone_for(index, url))
    return ordered


def markdown_escape(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ").replace("\r", " ")


def render_markdown(results: Sequence[VideoResult]) -> str:
    columns = ["No.", "URL", "タイトル", "動画時間", "状態", "取得元", "注記"]
    lines = ["| " + " | ".join(columns) + " |", "|" + "|".join(["---:", "---", "---", "---:", "---", "---", "---"]) + "|"]
    for item in results:
        lines.append(
            "| "
            + " | ".join(
                [
                    str(item.index),
                    markdown_escape(item.url),
                    markdown_escape(item.title),
                    item.duration,
                    item.status,
                    item.source,
                    markdown_escape(item.note),
                ]
            )
            + " |"
        )
    successful = [item for item in results if item.status == "ok" and item.seconds is not None]
    unresolved = len(results) - len(successful)
    total = sum(item.seconds or 0 for item in successful)
    lines += ["", f"取得成功: {len(successful)}/{len(results)}、未取得: {unresolved}、取得済み合計: {format_hms(total)}"]
    return "\n".join(lines) + "\n"


def render_delimited(results: Sequence[VideoResult], delimiter: str) -> str:
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer, delimiter=delimiter, lineterminator="\n")
    writer.writerow(["index", "url", "platform", "video_id", "title", "duration", "seconds", "status", "source", "confidence", "note"])
    for item in results:
        writer.writerow(
            [
                item.index,
                item.url,
                item.platform,
                item.video_id,
                item.title,
                item.duration,
                "" if item.seconds is None else item.seconds,
                item.status,
                item.source,
                item.confidence,
                item.note,
            ]
        )
    return buffer.getvalue()


def render_json(results: Sequence[VideoResult]) -> str:
    successful = [item for item in results if item.status == "ok" and item.seconds is not None]
    payload = {
        "summary": {
            "requested": len(results),
            "succeeded": len(successful),
            "unresolved": len(results) - len(successful),
            "total_seconds": sum(item.seconds or 0 for item in successful),
            "total_duration": format_hms(sum(item.seconds or 0 for item in successful)),
        },
        "items": [asdict(item) for item in results],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"


def read_urls(args: argparse.Namespace) -> list[str]:
    urls: list[str] = list(args.urls)
    if args.input:
        text = Path(args.input).read_text(encoding="utf-8-sig")
        urls.extend(line.strip() for line in text.splitlines() if line.strip() and not line.lstrip().startswith("#"))
    if args.stdin:
        urls.extend(line.strip() for line in sys.stdin if line.strip() and not line.lstrip().startswith("#"))
    return urls


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Collect video durations without downloading media, preserving input order.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("urls", nargs="*", help="Video page URLs")
    parser.add_argument("-i", "--input", help="UTF-8 text file containing one URL per line")
    parser.add_argument("--stdin", action="store_true", help="Also read URLs from standard input")
    parser.add_argument("-o", "--output", help="Output file; stdout when omitted")
    parser.add_argument("--format", choices=["markdown", "csv", "tsv", "json"], default="markdown")
    parser.add_argument("--backend", choices=["auto", "youtube-api", "yt-dlp", "html"], default="auto")
    parser.add_argument(
        "--youtube-api-key",
        default=os.getenv("YOUTUBE_API_KEY"),
        help="YouTube Data API key; defaults to YOUTUBE_API_KEY",
    )
    parser.add_argument("--workers", type=int, default=4, help="Parallel workers for yt-dlp/HTML")
    parser.add_argument("--timeout", type=float, default=20.0, help="Per-request network timeout in seconds")
    parser.add_argument(
        "--cookies-from-browser",
        help="Pass a browser name/profile to yt-dlp for authorized pages, e.g. chrome or firefox",
    )
    parser.add_argument(
        "--yt-dlp-arg",
        action="append",
        default=[],
        help="Additional raw argument passed to yt-dlp; repeat as needed",
    )
    parser.add_argument("--cache", type=Path, help="Optional JSON cache file")
    parser.add_argument(
        "--cache-ttl",
        type=float,
        default=0,
        help="Cache TTL in seconds; 0 means successful VOD durations never expire",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        urls = read_urls(args)
    except OSError as exc:
        parser.error(str(exc))
    if not urls:
        parser.error("Provide at least one URL, --input, or --stdin.")
    if args.workers < 1:
        parser.error("--workers must be at least 1.")

    results = collect(
        urls=urls,
        backend=args.backend,
        api_key=args.youtube_api_key,
        timeout=args.timeout,
        workers=args.workers,
        cookies_from_browser=args.cookies_from_browser,
        yt_dlp_args=args.yt_dlp_arg,
        cache_file=args.cache,
        cache_ttl=args.cache_ttl,
    )

    if args.format == "markdown":
        output = render_markdown(results)
    elif args.format == "json":
        output = render_json(results)
    elif args.format == "csv":
        output = render_delimited(results, ",")
    else:
        output = render_delimited(results, "\t")

    if args.output:
        encoding = "utf-8-sig" if args.format == "csv" else "utf-8"
        Path(args.output).write_text(output, encoding=encoding, newline="")
    else:
        sys.stdout.write(output)

    return 0 if all(item.status == "ok" for item in results) else 2


if __name__ == "__main__":
    raise SystemExit(main())
