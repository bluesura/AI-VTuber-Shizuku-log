"""負時刻を含む再生時刻の読み取りと表記統一。"""
import re

CLOCK = re.compile(r"(-?)(?:([0-9]+):)?([0-9]+):([0-5][0-9])")
URL_TIME = re.compile(r"(?:(\d+)h)?(?:(\d+)m)?(?:(\d+)s)?")


def parse_time(value: str) -> int:
    value = value.strip()
    if re.fullmatch(r"-?[0-9]+", value):
        return int(value)
    match = CLOCK.fullmatch(value)
    if match:
        sign, hours, minutes, seconds = match.groups()
        if hours is not None and int(minutes) >= 60:
            raise ValueError(f"時刻の分が範囲外: {value}")
        return (-1 if sign else 1) * (int(hours or 0) * 3600 + int(minutes) * 60 + int(seconds))
    match = URL_TIME.fullmatch(value)
    if match and any(match.groups()):
        hours, minutes, seconds = (int(item or 0) for item in match.groups())
        return hours * 3600 + minutes * 60 + seconds
    raise ValueError(f"時刻の表記が不正: {value}")


def format_time(seconds: int) -> str:
    hours, remainder = divmod(abs(seconds), 3600)
    minutes, secs = divmod(remainder, 60)
    sign = "-" if seconds < 0 else ""
    return f"{sign}{hours}:{minutes:02}:{secs:02}" if hours else f"{sign}{minutes}:{secs:02}"
