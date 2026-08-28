import pysrt
from pathlib import Path


def format_timestamp(seconds: float) -> str:
    """Convert seconds to SRT timestamp format HH:MM:SS,mmm."""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds % 1) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def parse_srt(path: str) -> list[dict]:
    """Parse SRT file into list of segment dicts."""
    subs = pysrt.open(path, encoding="utf-8")
    results = []
    for sub in subs:
        start_sec = (sub.start.hours * 3600 + sub.start.minutes * 60
                     + sub.start.seconds + sub.start.milliseconds / 1000)
        end_sec = (sub.end.hours * 3600 + sub.end.minutes * 60
                   + sub.end.seconds + sub.end.milliseconds / 1000)
        results.append({
            "index": sub.index,
            "start": start_sec,
            "end": end_sec,
            "start_ts": str(sub.start).replace(".", ","),
            "end_ts": str(sub.end).replace(".", ","),
            "text": sub.text,
        })
    return results


def write_srt(segments: list[dict], path: str):
    """Write segments to SRT file.

    Each segment needs: start (seconds), end (seconds), text.
    """
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for i, seg in enumerate(segments, 1):
            start_ts = seg.get("start_ts") or format_timestamp(seg["start"])
            end_ts = seg.get("end_ts") or format_timestamp(seg["end"])
            f.write(f"{i}\n{start_ts} --> {end_ts}\n{seg['text'].strip()}\n\n")
