"""Nhan video co san tren may lam dau vao, thay cho buoc tai Douyin.

Tra ve dung contract nhu Downloader.run() de cac step phia sau khong phai sua gi.
"""
import re
import shutil
import subprocess
from pathlib import Path

from src.steps.base import BaseStep

VIDEO_EXTS = {".mp4", ".mkv", ".mov", ".avi", ".webm", ".m4v", ".flv", ".wmv", ".ts"}


def slugify(name: str) -> str:
    """Ten file an toan cho ffmpeg va duong dan Windows."""
    stem = Path(name).stem
    stem = re.sub(r"[^0-9A-Za-z._-]+", "_", stem).strip("_")
    return (stem or "video")[:60]


class LocalSource(BaseStep):
    def run(self, path: str) -> dict:
        src = Path(path).expanduser()
        if not src.exists():
            raise FileNotFoundError(f"Khong tim thay file: {src}")
        if not src.is_file():
            raise ValueError(f"Duong dan khong phai file: {src}")
        if src.suffix.lower() not in VIDEO_EXTS:
            raise ValueError(
                f"Duoi file khong duoc ho tro: {src.suffix} "
                f"(chap nhan: {', '.join(sorted(VIDEO_EXTS))})"
            )

        out_dir = self.ensure_dir("downloads")
        video_id = slugify(src.name)
        dest = out_dir / f"{video_id}{src.suffix.lower()}"

        # Chi copy khi file chua nam san trong workspace (tranh copy thua)
        if src.resolve() != dest.resolve():
            if dest.exists() and dest.stat().st_size == src.stat().st_size:
                self.log(f"Da co san trong workspace: {dest.name}")
            else:
                shutil.copy2(src, dest)
                self.log(f"Da nap: {src.name} -> {dest.name}")
        else:
            dest = src

        size_mb = dest.stat().st_size / 1024 / 1024
        duration = self._probe_duration(dest)
        self.log(f"Video local: {dest.name} ({size_mb:.1f} MB, {duration:.0f}s)")

        return {
            "video_path": dest,
            "video_id": video_id,
            "duration": duration,
            "metadata": {
                "id": video_id,
                "title": src.stem,
                "description": "",
                "source": "local",
                "original_path": str(src),
            },
        }

    def _probe_duration(self, path: Path) -> float:
        try:
            r = subprocess.run(
                ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
                 "-of", "csv=p=0", str(path)],
                capture_output=True, text=True, timeout=20,
            )
            return float(r.stdout.strip() or 0)
        except (ValueError, subprocess.TimeoutExpired, FileNotFoundError):
            return 0.0
