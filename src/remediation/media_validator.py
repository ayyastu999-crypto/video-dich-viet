"""
Media File Validator — tiền-kiểm tra video/audio bằng ffprobe trước khi pipeline xử lý.

Kiểm tra:
    - Video MP4 hợp lệ, có audio stream, duration > 0
    - File không bị corrupt (ffprobe không lỗi)
    - Audio WAV hợp lệ, sample rate, duration
    - Phát hiện video câm (no speech) -> đề nghị bỏ STT
    - Phát hiện video quá ngắn (<3s) -> nghi ngờ hỏng
    - Phát hiện video quá dài (>10min) -> cảnh báo chi phí
"""
from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

from src.remediation._common import audit, get_logger, safe_size

MIN_DURATION_SEC = 3.0
MAX_DURATION_SEC = 600.0      # 10 phút
SILENCE_THRESHOLD_DB = -50.0  # mean_volume thấp hơn -> coi như câm
MIN_FILE_BYTES = 1024


@dataclass
class MediaIssue:
    code: str
    severity: str   # "info" | "warn" | "error" | "fatal"
    message: str


@dataclass
class MediaReport:
    path: str
    exists: bool
    size: int = 0
    duration: float = 0.0
    has_video: bool = False
    has_audio: bool = False
    video_codec: str | None = None
    audio_codec: str | None = None
    width: int | None = None
    height: int | None = None
    sample_rate: int | None = None
    is_silent: bool | None = None
    mean_volume_db: float | None = None
    issues: list[MediaIssue] = field(default_factory=list)
    safe_to_process: bool = True

    def add(self, issue: MediaIssue) -> None:
        self.issues.append(issue)
        if issue.severity == "fatal":
            self.safe_to_process = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class MediaValidator:
    def __init__(self, work_dir: Path | str | None = None):
        self.work_dir = Path(work_dir) if work_dir else Path("workspace")
        self.logger = get_logger("media_validator", self.work_dir)
        self._ffprobe = shutil.which("ffprobe")
        self._ffmpeg = shutil.which("ffmpeg")

    # ------------------------------------------------------------------
    def validate(self, path: Path | str, check_silence: bool = True) -> MediaReport:
        p = Path(path)
        report = MediaReport(path=str(p), exists=p.exists())

        if not report.exists:
            report.add(MediaIssue("MISSING", "fatal", f"File không tồn tại: {p}"))
            return report

        report.size = safe_size(p)
        if report.size < MIN_FILE_BYTES:
            report.add(MediaIssue(
                "TOO_SMALL", "fatal",
                f"File quá nhỏ ({report.size} bytes) - nghi corrupt",
            ))
            return report

        if not self._ffprobe:
            report.add(MediaIssue(
                "FFPROBE_MISSING", "warn",
                "Không tìm thấy ffprobe - bỏ qua kiểm tra sâu",
            ))
            audit("media_validate", {"path": str(p), "skipped": True}, self.work_dir)
            return report

        # Phân tích bằng ffprobe
        meta = self._ffprobe_json(p)
        if meta is None:
            report.add(MediaIssue(
                "PROBE_FAIL", "fatal",
                "ffprobe không đọc được file - file có thể đã hỏng",
            ))
            return report

        self._populate_from_meta(meta, report)

        # Duration checks
        if report.duration <= 0:
            report.add(MediaIssue(
                "ZERO_DURATION", "fatal",
                "Thời lượng = 0 - file bị hỏng",
            ))
        elif report.duration < MIN_DURATION_SEC:
            report.add(MediaIssue(
                "TOO_SHORT", "warn",
                f"Video rất ngắn ({report.duration:.1f}s) - khả năng cao bị hỏng",
            ))
        elif report.duration > MAX_DURATION_SEC:
            report.add(MediaIssue(
                "TOO_LONG", "warn",
                f"Video dài {report.duration:.1f}s ({report.duration/60:.1f} phút) "
                f"- chi phí TTS/dịch sẽ cao",
            ))

        # Video MP4 cần có audio stream
        is_video_file = (p.suffix.lower() in {".mp4", ".mov", ".mkv", ".webm"}
                         or report.has_video)
        if is_video_file and not report.has_audio:
            report.add(MediaIssue(
                "NO_AUDIO_STREAM", "error",
                "Video không có audio stream - không thể STT/dịch",
            ))

        # Silence detection
        if check_silence and report.has_audio and self._ffmpeg:
            mean_db = self._measure_volume(p)
            report.mean_volume_db = mean_db
            if mean_db is not None and mean_db < SILENCE_THRESHOLD_DB:
                report.is_silent = True
                report.add(MediaIssue(
                    "SILENT_AUDIO", "warn",
                    f"Âm lượng trung bình {mean_db:.1f} dB < ngưỡng "
                    f"{SILENCE_THRESHOLD_DB} dB - đề nghị bỏ STT",
                ))
            elif mean_db is not None:
                report.is_silent = False

        audit("media_validate", {
            "path": str(p),
            "duration": report.duration,
            "has_audio": report.has_audio,
            "issues": len(report.issues),
            "safe": report.safe_to_process,
        }, self.work_dir)

        return report

    # ------------------------------------------------------------------
    def _ffprobe_json(self, path: Path) -> dict | None:
        try:
            r = subprocess.run(
                [self._ffprobe, "-v", "error", "-show_format", "-show_streams",
                 "-of", "json", str(path)],
                capture_output=True, text=True, timeout=30,
            )
            if r.returncode != 0 or not r.stdout.strip():
                return None
            return json.loads(r.stdout)
        except (subprocess.TimeoutExpired, json.JSONDecodeError, OSError) as e:
            self.logger.warning(f"ffprobe lỗi {path}: {e}")
            return None

    def _populate_from_meta(self, meta: dict, report: MediaReport) -> None:
        fmt = meta.get("format", {})
        try:
            report.duration = float(fmt.get("duration", 0))
        except (TypeError, ValueError):
            report.duration = 0.0

        for stream in meta.get("streams", []):
            ctype = stream.get("codec_type")
            if ctype == "video" and not report.has_video:
                report.has_video = True
                report.video_codec = stream.get("codec_name")
                report.width = stream.get("width")
                report.height = stream.get("height")
            elif ctype == "audio" and not report.has_audio:
                report.has_audio = True
                report.audio_codec = stream.get("codec_name")
                try:
                    report.sample_rate = int(stream.get("sample_rate", 0))
                except (TypeError, ValueError):
                    report.sample_rate = None

    def _measure_volume(self, path: Path) -> float | None:
        """Dùng ffmpeg volumedetect để lấy mean_volume (dB)."""
        try:
            r = subprocess.run(
                [self._ffmpeg, "-hide_banner", "-nostats",
                 "-i", str(path), "-af", "volumedetect", "-vn",
                 "-f", "null", "-"],
                capture_output=True, text=True, timeout=120,
            )
            text = r.stderr
            for line in text.splitlines():
                if "mean_volume" in line:
                    # vd: "[Parsed_volumedetect_0 @ ...] mean_volume: -27.5 dB"
                    parts = line.split(":")
                    if len(parts) >= 2:
                        val = parts[-1].strip().replace(" dB", "")
                        try:
                            return float(val)
                        except ValueError:
                            return None
            return None
        except (subprocess.TimeoutExpired, OSError) as e:
            self.logger.warning(f"volumedetect lỗi {path}: {e}")
            return None
