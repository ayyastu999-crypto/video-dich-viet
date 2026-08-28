"""Fast FFmpeg helpers using NVENC hardware acceleration.

NVENC = NVIDIA GPU encoder, 5-10x faster than libx264 CPU encoding.
Uses CUDA hardware decoder + encoder, keeping video entirely in GPU memory.
"""
import subprocess
import shutil


_NVENC_AVAILABLE = None


def nvenc_available() -> bool:
    """Check if h264_nvenc encoder is available (NVIDIA GPU required)."""
    global _NVENC_AVAILABLE
    if _NVENC_AVAILABLE is not None:
        return _NVENC_AVAILABLE

    if not shutil.which("ffmpeg"):
        _NVENC_AVAILABLE = False
        return False

    try:
        result = subprocess.run(
            ["ffmpeg", "-hide_banner", "-encoders"],
            capture_output=True, text=True, timeout=5,
        )
        _NVENC_AVAILABLE = "h264_nvenc" in result.stdout
    except (subprocess.TimeoutExpired, FileNotFoundError):
        _NVENC_AVAILABLE = False

    return _NVENC_AVAILABLE


def get_video_codec_args(preset: str = "fast", crf: int = 20) -> list[str]:
    """Return optimal video codec args (NVENC if available, else libx264)."""
    if nvenc_available():
        # NVENC preset: p1 (fastest) to p7 (slowest). p4 = balanced
        # CQ is like CRF (lower = better quality). 20-24 = good quality
        nvenc_preset = {
            "ultrafast": "p1", "fast": "p4", "medium": "p5",
            "slow": "p6", "veryslow": "p7",
        }.get(preset, "p4")
        return [
            "-c:v", "h264_nvenc",
            "-preset", nvenc_preset,
            "-tune", "hq",
            "-cq", str(crf),
            "-b:v", "0",  # Pure CQ mode
            "-pix_fmt", "yuv420p",
        ]
    else:
        return [
            "-c:v", "libx264",
            "-preset", preset,
            "-crf", str(crf),
            "-pix_fmt", "yuv420p",
        ]


def run_ffmpeg_fast(args: list[str], video_codec_args: list[str] = None,
                    check: bool = True):
    """Run ffmpeg with hardware acceleration where possible."""
    if video_codec_args is None:
        video_codec_args = get_video_codec_args()

    # Insert codec args before output file (last arg)
    cmd = ["ffmpeg", "-y"] + args[:-1] + video_codec_args + [args[-1]]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if check and result.returncode != 0:
        raise RuntimeError(f"FFmpeg failed: {result.stderr[-500:]}")
    return result
