"""
Pipeline State Inspector — quét workspace và xác định trạng thái mỗi video.

Dò 11 bước:
    1.  download              -> workspace/downloads/<id>.mp4
    2.  stt                   -> workspace/srt/<id>_original.srt
    3.  translate             -> workspace/srt/<id>_<lang>.srt
    4.  tts                   -> workspace/tts/<id>_<lang>.{wav,mp3}
    5.  caption_detect        -> workspace/output/<id>_caption_region.json (best-effort)
    6.  caption_blur          -> workspace/output/<id>_blurred.mp4
    7.  caption_write         -> workspace/output/<id>_blurred_captioned.mp4
    8.  audio_separate        -> workspace/separated/htdemucs/<id>/{vocals,no_vocals}.wav
    9.  audio_mix             -> workspace/output/<id>_mixed_audio.wav (or generic)
    10. compose               -> workspace/output/final_<...>.mp4
    11. upload                -> không lưu artifact, đoán qua log

Phát hiện:
    - Stuck job  : có file tạm/empty của bước nhưng artifact chính bị rỗng/cũ
    - Resumable  : đã hoàn tất 1 phần, có thể tiếp tục
    - Orphan     : artifact tồn tại mà không có video gốc tương ứng
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

from src.remediation._common import audit, get_logger, safe_size

# Tuổi tối đa (giây) để 1 file đang viết được coi là "đang chạy"
STUCK_AGE_SECONDS = 60 * 30   # 30 phút không thay đổi -> coi như stuck
MIN_VALID_BYTES = 256          # < 256 bytes coi như rỗng


# Tên các bước theo thứ tự thực thi
STEP_ORDER = [
    "download",
    "stt",
    "audio_separate",
    "translate",
    "tts",
    "caption_detect",
    "caption_blur",
    "caption_write",
    "audio_mix",
    "compose",
    "upload",
]


@dataclass
class StepStatus:
    name: str
    completed: bool = False
    artifact: str | None = None
    size: int = 0
    age_seconds: float | None = None
    issue: str | None = None  # "empty", "stuck", "missing", None


@dataclass
class VideoState:
    video_id: str
    target_lang: str = "vi"
    download_path: str | None = None
    steps: dict[str, StepStatus] = field(default_factory=dict)
    last_completed_step: str | None = None
    next_step: str | None = None
    is_complete: bool = False
    is_stuck: bool = False
    is_resumable: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class WorkspaceReport:
    work_dir: str
    target_lang: str = "vi"
    videos: dict[str, VideoState] = field(default_factory=dict)
    orphans: list[str] = field(default_factory=list)
    stuck_ids: list[str] = field(default_factory=list)
    completed_ids: list[str] = field(default_factory=list)
    resumable_ids: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "work_dir": self.work_dir,
            "target_lang": self.target_lang,
            "videos": {k: v.to_dict() for k, v in self.videos.items()},
            "orphans": self.orphans,
            "stuck_ids": self.stuck_ids,
            "completed_ids": self.completed_ids,
            "resumable_ids": self.resumable_ids,
        }


class PipelineInspector:
    """Quét workspace, dựng VideoState cho từng video_id."""

    def __init__(self, work_dir: Path | str | None = None, target_lang: str = "vi"):
        self.work_dir = Path(work_dir) if work_dir else Path("workspace")
        self.target_lang = target_lang
        self.logger = get_logger("inspector", self.work_dir)

    # ------------------------------------------------------------------
    def scan(self) -> WorkspaceReport:
        report = WorkspaceReport(work_dir=str(self.work_dir), target_lang=self.target_lang)

        downloads = self.work_dir / "downloads"
        if not downloads.exists():
            self.logger.warning(f"Không tồn tại downloads/: {downloads}")
            return report

        # 1. Liệt kê video_id từ mp4 trong downloads
        video_ids: list[str] = []
        for mp4 in downloads.glob("*.mp4"):
            video_ids.append(mp4.stem)

        for vid in sorted(video_ids):
            state = self._inspect_video(vid)
            report.videos[vid] = state
            if state.is_complete:
                report.completed_ids.append(vid)
            elif state.is_stuck:
                report.stuck_ids.append(vid)
            elif state.is_resumable:
                report.resumable_ids.append(vid)

        # 2. Tìm orphan: artifact có nhưng không có MP4 gốc
        report.orphans = self._find_orphans(set(video_ids))

        audit("workspace_scan", {
            "videos": len(report.videos),
            "complete": len(report.completed_ids),
            "stuck": len(report.stuck_ids),
            "resumable": len(report.resumable_ids),
            "orphans": len(report.orphans),
        }, self.work_dir)

        return report

    # ------------------------------------------------------------------
    def _inspect_video(self, vid: str) -> VideoState:
        lang = self.target_lang
        state = VideoState(video_id=vid, target_lang=lang)

        # Định nghĩa artifact mong đợi cho mỗi bước
        candidates: dict[str, list[Path]] = {
            "download": [self.work_dir / "downloads" / f"{vid}.mp4"],
            "stt": [self.work_dir / "srt" / f"{vid}_original.srt"],
            "audio_separate": [
                self.work_dir / "separated" / "htdemucs" / vid / "vocals.wav",
                self.work_dir / "separated" / "htdemucs" / vid / "no_vocals.wav",
            ],
            "translate": [self.work_dir / "srt" / f"{vid}_{lang}.srt"],
            "tts": [
                self.work_dir / "tts" / f"{vid}_{lang}.wav",
                self.work_dir / "tts" / f"{vid}_{lang}.mp3",
                self.work_dir / "tts" / f"{vid}.wav",
            ],
            "caption_detect": [
                self.work_dir / "output" / f"{vid}_caption_region.json",
            ],
            "caption_blur": [self.work_dir / "output" / f"{vid}_blurred.mp4"],
            "caption_write": [self.work_dir / "output" / f"{vid}_blurred_captioned.mp4"],
            "audio_mix": [
                self.work_dir / "output" / f"{vid}_mixed_audio.wav",
                self.work_dir / "output" / "mixed_audio.wav",
            ],
            "compose": [
                self.work_dir / "output" / f"final_{vid}_blurred_captioned.mp4",
                self.work_dir / "output" / f"final_{vid}.mp4",
            ],
            "upload": [],   # không có artifact để dò
        }

        now = time.time()
        for step_name in STEP_ORDER:
            paths = candidates.get(step_name, [])
            status = StepStatus(name=step_name)

            # Bước "upload" và "caption_detect" được coi là optional/best-effort
            if step_name == "upload":
                status.completed = False
                status.issue = "not_tracked"
                state.steps[step_name] = status
                continue

            existing = [p for p in paths if p.exists()]
            if not existing:
                status.completed = False
                status.issue = "missing"
                # caption_detect không bắt buộc phải có file riêng
                if step_name == "caption_detect":
                    status.completed = True
                    status.issue = None
                state.steps[step_name] = status
                continue

            # Lấy artifact lớn nhất / mới nhất
            primary = max(existing, key=lambda p: safe_size(p))
            sz = safe_size(primary)
            age = now - primary.stat().st_mtime
            status.artifact = str(primary)
            status.size = sz
            status.age_seconds = age

            if sz < MIN_VALID_BYTES:
                # File quá nhỏ — đang viết hoặc lỗi
                if age < STUCK_AGE_SECONDS:
                    status.issue = "in_progress"
                    status.completed = False
                else:
                    status.issue = "stuck"
                    status.completed = False
                    state.is_stuck = True
            else:
                # Nếu là multi-file step (audio_separate cần cả 2)
                if step_name == "audio_separate":
                    if len(existing) >= 2 and all(safe_size(p) >= MIN_VALID_BYTES for p in existing):
                        status.completed = True
                    else:
                        status.completed = False
                        status.issue = "partial"
                else:
                    status.completed = True

            state.steps[step_name] = status

        # Xác định bước cuối hoàn thành + bước kế tiếp
        for step_name in STEP_ORDER:
            if step_name == "upload":
                continue
            st = state.steps.get(step_name)
            if st and st.completed:
                state.last_completed_step = step_name
            else:
                state.next_step = step_name
                break
        else:
            # Tất cả đã xong (trừ upload)
            state.next_step = None
            state.is_complete = True

        # Đường dẫn download (tiện cho recovery)
        dl = state.steps.get("download")
        if dl and dl.completed:
            state.download_path = dl.artifact

        # Resumable: có ít nhất download xong, có bước kế tiếp, không bị stuck
        if state.last_completed_step and state.next_step and not state.is_stuck:
            state.is_resumable = True

        return state

    # ------------------------------------------------------------------
    def _find_orphans(self, valid_ids: set[str]) -> list[str]:
        """Tìm artifact có id không nằm trong tập video gốc."""
        orphans: list[str] = []

        # SRT files
        srt_dir = self.work_dir / "srt"
        if srt_dir.exists():
            for f in srt_dir.glob("*.srt"):
                # tách id: <id>_original.srt or <id>_<lang>.srt
                m = re.match(r"^(.+?)_(original|[a-z]{2})\.srt$", f.name)
                if m and m.group(1) not in valid_ids:
                    orphans.append(str(f))

        # Separated dirs
        sep_root = self.work_dir / "separated" / "htdemucs"
        if sep_root.exists():
            for sub in sep_root.iterdir():
                if sub.is_dir() and sub.name not in valid_ids:
                    orphans.append(str(sub))

        # Output mp4
        out_dir = self.work_dir / "output"
        if out_dir.exists():
            for f in out_dir.glob("*.mp4"):
                # tìm id 18-19 chữ số trong tên
                m = re.search(r"(\d{15,20})", f.name)
                if m and m.group(1) not in valid_ids:
                    orphans.append(str(f))

        return sorted(set(orphans))


def render_state_brief(state: VideoState) -> str:
    """Trả về 1 dòng tóm tắt 11 bước dạng ◯/●/!/?."""
    chars = []
    for s in STEP_ORDER:
        st = state.steps.get(s)
        if not st:
            chars.append("?")
        elif st.completed:
            chars.append("●")
        elif st.issue == "stuck":
            chars.append("!")
        elif st.issue == "in_progress":
            chars.append("…")
        else:
            chars.append("◯")
    return "".join(chars)
