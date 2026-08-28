def seconds_to_srt(seconds: float) -> str:
    """Convert seconds to SRT timestamp: HH:MM:SS,mmm"""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds % 1) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def srt_to_seconds(timestamp: str) -> float:
    """Convert SRT timestamp HH:MM:SS,mmm to seconds."""
    time_part, ms_part = timestamp.replace(".", ",").split(",")
    parts = time_part.split(":")
    h, m, s = int(parts[0]), int(parts[1]), int(parts[2])
    return h * 3600 + m * 60 + s + int(ms_part) / 1000
