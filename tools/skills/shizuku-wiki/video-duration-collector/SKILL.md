---
name: video-duration-collector
description: Collect exact video runtimes from batches of YouTube and other video URLs without downloading media; preserve URL order, normalize durations to H:MM:SS, report failures explicitly, and optionally total successful durations.
---

# Video Duration Collector

Use this skill when the user supplies one or more video-page URLs and asks for video length, viewing time, runtime, a duration table, CSV/JSON output, or a total duration.

## Reliability principles

1. **Never infer duration from search snippets, thumbnails, channel pages, or a different video URL.**
2. Match every result to the original URL and, for YouTube, to the extracted video ID.
3. Preserve the user's input order. Deduplicate network requests internally, but reproduce duplicate inputs in the output.
4. Store duration internally as integer seconds and display it as `H:MM:SS`, including `0:` for videos shorter than one hour.
5. Do not guess. Mark private, deleted, geo-blocked, login-required, live, upcoming, processing, and extraction failures explicitly.
6. A live or upcoming stream has no stable final duration. Report that state rather than the elapsed live time unless the user specifically requests elapsed time.
7. Do not download audio or video. Retrieve metadata only.

## Preferred retrieval order

### 1. YouTube Data API v3 for YouTube URLs

Use this when `YOUTUBE_API_KEY` or `--youtube-api-key` is available.

- Parse the video ID from `watch?v=`, `youtu.be/`, `/shorts/`, `/live/`, or `/embed/` URLs.
- Call `videos.list` with `part=snippet,contentDetails,status,liveStreamingDetails`.
- Send up to 50 IDs per request.
- Read `contentDetails.duration`, which is an ISO 8601 duration.
- Treat missing IDs as inaccessible, invalid, private, or deleted; in `auto` mode, allow fallback to another backend.

### 2. yt-dlp for YouTube and other supported platforms

Use metadata-only extraction:

```bash
yt-dlp --simulate --dump-single-json --no-playlist --no-warnings --ignore-no-formats-error -- URL
```

Read the numeric `duration` field in seconds. `duration_string` may be displayed for reference, but normalize output from numeric seconds yourself.

For authenticated pages, use cookies only when the user is authorized to access the content and has explicitly chosen that approach:

```bash
--cookies-from-browser chrome
```

Never use cookies or other techniques to bypass access controls the user is not entitled to pass.

### 3. Structured HTML metadata fallback

Fetch the exact page URL and inspect, in this order:

- YouTube page metadata `lengthSeconds`
- JSON-LD `VideoObject.duration` or `MediaObject.duration`
- `<meta itemprop="duration">`
- `og:video:duration` / `video:duration`

Accept ISO 8601 durations such as `PT1H35M28S`, numeric seconds, or colon-delimited times. Label generic page metadata as medium confidence.

### 4. Stop and report failure

If no trustworthy duration field is found, return `unavailable` or `error` with the reason. Do not substitute a nearby video's duration.

## Included command-line tool

Run:

```bash
python scripts/collect_video_durations.py --input urls.txt --format markdown
```

Recommended batch command:

```bash
python scripts/collect_video_durations.py \
  --input urls.txt \
  --format csv \
  --output durations.csv \
  --workers 6 \
  --cache .video-duration-cache.json
```

With the YouTube API:

```bash
export YOUTUBE_API_KEY="..."
python scripts/collect_video_durations.py --input urls.txt --backend auto
```

For a supported non-YouTube site or when no API key exists, install `yt-dlp`:

```bash
python -m pip install -U yt-dlp
```

## Output contract

Return a table with at least:

| No. | URL | Title | Duration | Status | Source | Note |
|---:|---|---|---:|---|---|---|

Rules:

- `Duration`: always `H:MM:SS`, for example `0:04:12` or `12:07:03`.
- `Status`: `ok`, `live`, `upcoming`, `processing`, `unavailable`, or `error`.
- `Source`: `youtube_api`, `yt_dlp`, `youtube_html`, `json_ld`, `html_meta`, or `cache:<source>`.
- Leave duration blank when status is not `ok`.
- Sum only rows with `status=ok`; state both the successful count and unresolved count.

## Efficiency rules

- Batch YouTube API IDs in groups of 50.
- Run independent yt-dlp/HTML requests concurrently with a modest worker count, normally 4-8.
- Cache only successful fixed VOD durations. Do not cache live, upcoming, processing, or failed results.
- Keep the original order after concurrent work completes.
- Prefer one authoritative source per row. Use a second source only when verification is requested or the first result is suspicious.

## Suspicious-result checks

Flag the result instead of silently accepting it when:

- the extracted YouTube ID differs from the requested ID;
- duration is missing or negative;
- the page is live/upcoming/processing;
- two explicitly requested verification sources differ by more than one second;
- a backend returned playlist/channel metadata despite an individual-video request;
- the source URL in the evidence is not the exact requested URL.

## Test

```bash
python scripts/test_collect_video_durations.py -v
```

The test suite covers YouTube URL variants, ISO 8601 parsing, colon times, JSON-LD, HTML metadata, `H:MM:SS` formatting, JSON summaries, and cache persistence.

## Primary references

- YouTube Data API `videos.list`: https://developers.google.com/youtube/v3/docs/videos/list
- YouTube video `contentDetails.duration`: https://developers.google.com/youtube/v3/docs/videos
- yt-dlp README and output fields: https://github.com/yt-dlp/yt-dlp/blob/master/README.md
- Schema.org `duration`: https://schema.org/duration
- Schema.org `VideoObject`: https://schema.org/VideoObject
