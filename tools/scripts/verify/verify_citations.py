"""カード・handoff・Wiki下書きのローカル出典索引を検証する。"""
import argparse
import csv
import json
import re
from bisect import bisect_left
from functools import lru_cache
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from time_utils import parse_time

ROOT = Path(__file__).resolve().parents[3]
DATA = ROOT / "tools/shizuku-pipeline/data"
URL = re.compile(r"https?://[^\s<>\[\]{}|）】]+")
VIDEO_ID = re.compile(r"[A-Za-z0-9_-]{11}")
YT_HOSTS = {"youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be"}
X_HOSTS = {"twitter.com", "www.twitter.com", "x.com", "www.x.com", "mobile.twitter.com"}


def url_source(url):
    parsed = urlsplit(url.replace("&amp;", "&"))
    query = parse_qs(parsed.query)
    if parsed.hostname in YT_HOSTS:
        parts = parsed.path.strip("/").split("/")
        if parsed.hostname == "youtu.be":
            vid = parts[0]
        elif parsed.path == "/watch":
            vid = query.get("v", [""])[0]
        elif len(parts) == 2 and parts[0] in {"live", "shorts", "embed"}:
            vid = parts[1]
        else:
            return None
        if not VIDEO_ID.fullmatch(vid):
            return None
        time = query.get("t", query.get("start", [None]))[0]
        if time is None and parsed.fragment.startswith("t="):
            time = parsed.fragment[2:]
        return {"type": "yt", "video_id": vid, "t": time, "url_only": True}
    if parsed.hostname in X_HOSTS:
        match = re.search(r"/status/([0-9]+)(?:/|$)", parsed.path)
        if match:
            return {"type": "x", "post_id": match[1]}
    return None


def json_lines(path):
    with path.open(encoding="utf-8-sig") as stream:
        for line in stream:
            if line.strip():
                yield json.loads(line)


def times(path):
    if not path.is_file():
        return []
    return sorted(int(line.split("\t", 1)[0]) for line in path.read_text(encoding="utf-8").splitlines()[1:]
                  if line.strip())


def near(values, t):
    pos = bisect_left(values, t - 60)
    return pos < len(values) and values[pos] <= t + 60


class CitationIndex:
    def __init__(self, data, logs):
        self.data = data
        self.logs = logs
        self.x = {str(row["post_id"]): row for p in (data / "normalized/x").glob("*.jsonl") for row in json_lines(p)}
        self.primary_x = {}
        for path in sorted((logs / "twitter(x)").rglob("*")):
            if not path.is_file() or path.suffix not in {".txt", ".tsv"}:
                continue
            with path.open(encoding="utf-8-sig", newline="") as stream:
                for row in csv.DictReader(stream, delimiter="\t"):
                    source = url_source(row.get("URL") or "")
                    pid = row.get("post_id") or (source or {}).get("post_id")
                    if pid:
                        self.primary_x[pid] = row
        self.primary_videos = {path.name.removesuffix(".info.txt") for path in
                               (logs / "youtube").rglob("*.info.txt")}

    @lru_cache(maxsize=None)
    def stream(self, video):
        folder = self.data / "normalized/streams" / video
        if not (folder / "meta.json").is_file():
            return None
        meta = json.loads((folder / "meta.json").read_text(encoding="utf-8"))
        return meta, times(folder / "sentences.tsv"), times(folder / "chat.tsv")

    def check(self, source):
        kind = source.get("type")
        if kind == "x":
            pid = str(source.get("post_id", ""))
            primary = self.primary_x.get(pid)
            indexed = self.x.get(pid)
            if any(row and (row.get("type") or row.get("種類")) == "RETWEET" for row in (primary, indexed)):
                if source.get("as_speaker", True):
                    return "単純RT。本人発言としては引用できません"
                return None
            if not indexed:
                return "X索引に未反映" if primary else "X投稿IDが見つかりません"
            return None
        if kind not in {"yt", "yt_chat", "yt_description"}:
            return f"未対応の出典種別: {kind}"
        video = str(source.get("video_id", ""))
        if not VIDEO_ID.fullmatch(video):
            return "動画IDが不正です"
        data = self.stream(video)
        if data is None:
            return "動画は収録済み。正規化索引なし" if video in self.primary_videos else "動画IDが見つかりません"
        meta, subs, chat = data
        if kind == "yt_description":
            return None if meta.get("description", "").strip() else "概要欄本文を確認できません"
        raw = source.get("t")
        if raw is None:
            return "チャット出典の時刻がありません" if kind == "yt_chat" else None
        t = parse_time(str(raw))
        if t < 0:
            if chat and chat[0] <= t and near(chat, t):
                return None
            return "開始前チャットの範囲外、または付近にチャットがありません"
        end = max(int(meta.get("duration_sec") or 0), subs[-1] if subs else 0, chat[-1] if chat else 0)
        if t > end:
            return "参照時刻が記録済みの末尾を超えています"
        if t == 0 and source.get("pre_chat"):
            original = parse_time(str(source["pre_chat"]))
            if original > 0:
                return "開始前チャットの元時刻が正の値です"
            return self.check({**source, "type": "yt_chat", "t": original,
                               "pre_chat": None, "url_only": False})
        if t == 0 and source.get("url_only") and not near(subs, 0) and not near(chat[bisect_left(chat, 0):], 0):
            if chat and chat[0] < 0:
                return "0秒へ丸められた待機チャットの可能性。元時刻の確認が必要"
        available = near(chat, t) if kind == "yt_chat" else near(subs, t) or near(chat, t)
        return None if available else "前後60秒以内に対応する記録がありません"


def sources(path):
    if path.suffix == ".jsonl":
        for i, row in enumerate(json_lines(path), 1):
            source = row.get("source")
            if not isinstance(source, dict):
                yield i, {}
            else:
                yield i, source
        return
    for i, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
        for url in URL.findall(line):
            source = url_source(url.rstrip("。.,;)"))
            if source is not None:
                yield i, source


def main(argv=None):
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("paths", type=Path, nargs="+")
    cli.add_argument("--data", type=Path, default=DATA)
    cli.add_argument("--logs", type=Path, default=ROOT / "logs")
    args = cli.parse_args(argv)
    try:
        index = CitationIndex(args.data, args.logs)
        count = failures = 0
        for path in args.paths:
            for line, source in sources(path):
                count += 1
                try:
                    issue = index.check(source)
                except ValueError as exc:
                    issue = str(exc)
                if issue:
                    print(f"{path}:{line}: {issue}")
                    failures += 1
        print(f"参照 {count}件 / 要確認 {failures}件")
        return int(bool(failures))
    except (OSError, ValueError, KeyError, csv.Error) as exc:
        cli.exit(2, f"{exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
