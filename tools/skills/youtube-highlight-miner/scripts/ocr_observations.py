"""保存済みフレームとOCR原本を照合し、分析用の再表示を整理する。"""
from __future__ import annotations

import hashlib
import json
import re
from collections import defaultdict, deque
from dataclasses import dataclass

HEADER = re.compile(r"^\[(\d+(?::\d{2})+(?:\.\d+)?)\]\s*(.*)$")
REVIEW = re.compile(r"\s*\[要確認[^\]\n]*\]")
MAX_GAP_MS = 1250


def milliseconds(timestamp):
    whole, _, fraction = timestamp.replace(",", ".").partition(".")
    seconds = 0
    for part in whole.lstrip("-").split(":"):
        seconds = seconds * 60 + int(part)
    return (-1 if whole.startswith("-") else 1) * (seconds * 1000 + int((fraction + "000")[:3]))


def key(text):
    return " ".join(text.split())


@dataclass(frozen=True)
class Observation:
    time: int
    text: str
    source: str
    line: int


@dataclass
class Track:
    text: str
    segment: int
    first: int
    start_y: int
    last: int
    box: tuple
    moved_up: bool = False


def read_observations(paths):
    observations = []
    for path in paths:
        lines = path.read_text(encoding="utf-8-sig").splitlines()
        for i, line in enumerate(lines):
            match = HEADER.match(line)
            if not match:
                continue
            parts = [match[2]]
            for j in range(i + 1, len(lines)):
                continuation = lines[j]
                if not continuation.strip() or HEADER.match(continuation):
                    break
                parts.append(continuation.strip())
            body = "\n".join(part for part in parts if part)
            if body:
                observations.append(Observation(milliseconds(match[1]), body, path.name, i + 1))
    return sorted(observations, key=lambda item: item.time)


def continuous(track, text, box, time):
    elapsed = time - track.last
    if not 0 < elapsed <= MAX_GAP_MS or track.text != text:
        return False
    left, top, right, bottom = box
    x0, y0, x1, y1 = track.box
    dy = top - y0
    return (abs(left - x0) <= 12 and abs(right - x1) <= 16
            and abs((bottom - top) - (y1 - y0)) <= 8 and -(4 + elapsed // 18) <= dy <= 3)


def attach_frame(row, active, tracks, segment):
    current = []
    time = row["pts_ms"]
    for item in sorted(row["lines"], key=lambda item: (item["box"][1], item["box"][0])):
        text = key(item["text"])
        box = tuple(item["box"])
        candidates = [i for i in active if continuous(tracks[i], text, box, time)]
        if len(candidates) == 1:
            index = candidates[0]
            active.remove(index)
            track = tracks[index]
            track.moved_up |= track.start_y - box[1] >= 9
            track.last, track.box = time, box
        else:
            index = len(tracks)
            tracks.append(Track(text, segment, time, box[1], time, box))
        current.append(index)
    return current


def repeated_tracks(tracks):
    """独立した3行以上が同じ順序と間隔で上へ流れた場合だけ周回とみなす。"""
    stable = [i for i, t in enumerate(tracks)
              if t.moved_up and len(t.text) >= 6 and t.last - t.first >= 500]
    seen = {}
    aliases = {}
    for start in range(len(stable) - 2):
        window = stable[start:start + 3]
        rows = [tracks[i] for i in window]
        signature = tuple(row.text for row in rows)
        if len(set(signature)) != 3 or rows[-1].segment != rows[0].segment:
            continue
        window_key = (rows[0].segment, signature)
        earlier = seen.get(window_key)
        seen[window_key] = window
        if earlier is None:
            continue
        old = [tracks[i] for i in earlier]
        offset = rows[0].first - old[0].first
        if (earlier[-1] >= window[0] or not 1000 <= offset <= 120000
                or old[-1].last >= rows[0].first):
            continue
        if any(abs(new.first - prev.first - offset) > 1200 or abs(new.start_y - prev.start_y) > 16
               for new, prev in zip(rows, old)):
            continue
        for new, prev in zip(window, earlier):
            aliases.setdefault(new, aliases.get(prev, prev))
    return aliases


def frame_matches(manifests, by_time):
    tracks = []
    evidence = {}
    last_time = -1
    for manifest in manifests:
        active, region = [], None
        segment = len(tracks)
        with manifest.open(encoding="utf-8-sig") as stream:
            for line in stream:
                row = json.loads(line)
                time = row["pts_ms"]
                if time <= last_time:
                    raise ValueError(f"フレーム時刻の逆順または区間重複: {manifest}:{time}")
                if region != row["region"] or time - last_time > MAX_GAP_MS:
                    active, region, segment = [], row["region"], len(tracks)
                last_time = time
                current = attach_frame(row, active, tracks, segment)
                for item in by_time.get(time, []):
                    body = key(REVIEW.sub("", item.text))
                    intervals = [tuple(current[a:b]) for a in range(len(current))
                                 for b in range(a + 1, len(current) + 1)
                                 if body in {"".join(tracks[i].text for i in current[a:b]),
                                             " ".join(tracks[i].text for i in current[a:b])}]
                    if len(intervals) == 1:
                        evidence[item] = (intervals[0], {"manifest": str(manifest), "frame": row["frame"]})
                active = current
                if not current:
                    segment = len(tracks)
    return tracks, evidence


def verified_manifests(workdir, video_id, source):
    """正本のSHA-256を検証できる場合だけ、完了記録に載ったフレームを使う。"""
    record = workdir / "verification.json"
    if not record.is_file():
        return []
    data = json.loads(record.read_text(encoding="utf-8-sig"))
    if data.get("video_id") != video_id:
        return []
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    if data.get("output", {}).get("sha256") != digest:
        return []
    processing = data.get("processing", {})
    names = [part["manifest"] for part in processing.get("parts", []) if "manifest" in part]
    if not names and processing.get("evidence_manifest"):
        names = [processing["evidence_manifest"]]
    paths = [(workdir / name).resolve() for name in names]
    return paths if all(p.is_relative_to(workdir.resolve()) and p.is_file() for p in paths) else []


def observed_lines(observations, tracks, matched):
    for item in observations:
        track_ids, frame = matched.get(item, ((), {}))
        parts = [part.strip() for part in REVIEW.sub("", item.text).splitlines() if part.strip()]
        if len(parts) > 1 and [key(part) for part in parts] == [tracks[i].text for i in track_ids]:
            for part, (text, track) in enumerate(zip(parts, track_ids), 1):
                yield item, text, (track,), {**frame, "part": part}
        else:
            yield item, " ".join(parts), track_ids, frame



def group_observations(observations, manifests=()):
    by_time = defaultdict(list)
    for item in observations:
        by_time[item.time].append(item)
    tracks, matched = frame_matches(manifests, by_time)
    aliases = repeated_tracks(tracks)
    groups = []
    by_track = {}
    recent = defaultdict(deque)
    for item, text, track_ids, frame in observed_lines(observations, tracks, matched):
        body = key(text)
        signature = (body, tuple(aliases.get(i, i) for i in track_ids))
        group = by_track.get(signature) if track_ids else None
        if group is None:
            group = {
                "id": f"O{len(groups) + 1:05}",
                "text": text,
                "review": False, "replay_candidate": False,
                "cycle": False, "observations": [],
            }
            groups.append(group)
            if track_ids:
                by_track[signature] = group
            window = recent[body]
            while window and item.time - window[0] > 60000:
                window.popleft()
            window.append(item.time)
            if len(window) >= 3:
                group["replay_candidate"] = True
        group["review"] |= bool(REVIEW.search(item.text))
        group["cycle"] |= any(i in aliases for i in track_ids)
        group["observations"].append({
            "ms": item.time, "source": item.source, "line": item.line, **frame,
        })
    return groups
