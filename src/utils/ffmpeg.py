import subprocess
import shutil
from pathlib import Path


def check_ffmpeg() -> bool:
    """Check if ffmpeg is installed and accessible."""
    return shutil.which("ffmpeg") is not None


def get_duration(file_path: str) -> float:
    """Get audio/video duration in seconds."""
    result = subprocess.run(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(file_path)],
        capture_output=True, text=True
    )
    try:
        return float(result.stdout.strip())
    except (ValueError, AttributeError):
        return 0.0


def run_ffmpeg(args: list[str], check: bool = True):
    """Run ffmpeg command with args. Raises on failure if check=True."""
    cmd = ["ffmpeg", "-y"] + args
    result = subprocess.run(cmd, capture_output=True, text=True)
    if check and result.returncode != 0:
        raise RuntimeError(f"FFmpeg failed: {result.stderr[-500:]}")
    return result


def adjust_tempo(input_path: str, output_path: str, speed: float):
    """Adjust audio playback speed using atempo filter.

    speed > 1.0 = faster, speed < 1.0 = slower.
    atempo range: 0.5 to 2.0. Chain multiple for wider range.
    """
    filters = []
    remaining = speed
    while remaining > 2.0:
        filters.append("atempo=2.0")
        remaining /= 2.0
    while remaining < 0.5:
        filters.append("atempo=0.5")
        remaining /= 0.5
    filters.append(f"atempo={remaining:.4f}")

    run_ffmpeg([
        "-i", str(input_path),
        "-filter:a", ",".join(filters),
        str(output_path)
    ])


def generate_silence(output_path: str, duration: float, sample_rate: int = 44100):
    """Generate a silent audio file of given duration."""
    run_ffmpeg([
        "-f", "lavfi",
        "-i", f"anullsrc=r={sample_rate}:cl=stereo",
        "-t", str(duration),
        "-c:a", "aac",
        str(output_path)
    ])
