"""
Shared application state for the web UI.

Manages pipeline jobs, progress tracking, and event communication
between the background pipeline workers and the Gradio frontend.
"""
import time
import threading
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional


class JobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class StepName(str, Enum):
    DOWNLOAD = "download"
    STT = "stt"
    TRANSLATE = "translate"
    TTS = "tts"
    CAPTION_DETECT = "caption_detect"
    CAPTION_BLUR = "caption_blur"
    CAPTION_WRITE = "caption_write"
    AUDIO_SEPARATE = "audio_separate"
    AUDIO_MIX = "audio_mix"
    COMPOSE = "compose"
    UPLOAD = "upload"


STEP_LABELS_VI = {
    StepName.DOWNLOAD: "Tải video",
    StepName.STT: "Nhận dạng giọng nói",
    StepName.TRANSLATE: "Dịch phụ đề",
    StepName.TTS: "Tạo giọng đọc",
    StepName.CAPTION_DETECT: "Phát hiện phụ đề cũ",
    StepName.CAPTION_BLUR: "Xóa phụ đề cũ",
    StepName.CAPTION_WRITE: "Thêm phụ đề mới",
    StepName.AUDIO_SEPARATE: "Tách nhạc nền",
    StepName.AUDIO_MIX: "Trộn âm thanh",
    StepName.COMPOSE: "Ghép video cuối",
    StepName.UPLOAD: "Upload lên nền tảng",
}

PIPELINE_STEPS = list(StepName)


@dataclass
class StepProgress:
    step: StepName
    status: JobStatus = JobStatus.QUEUED
    progress: float = 0.0  # 0-100
    message: str = ""
    started_at: Optional[float] = None
    finished_at: Optional[float] = None


@dataclass
class Job:
    job_id: str
    url: str
    target_lang: str
    status: JobStatus = JobStatus.QUEUED
    steps: dict = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    finished_at: Optional[float] = None
    error: Optional[str] = None
    # File paths produced
    video_path: Optional[str] = None
    srt_original: Optional[str] = None
    srt_translated: Optional[str] = None
    final_video: Optional[str] = None
    metadata: dict = field(default_factory=dict)

    def __post_init__(self):
        if not self.steps:
            for step_name in PIPELINE_STEPS:
                self.steps[step_name] = StepProgress(step=step_name)

    @property
    def current_step(self) -> Optional[StepName]:
        for step_name in PIPELINE_STEPS:
            sp = self.steps[step_name]
            if sp.status == JobStatus.RUNNING:
                return step_name
        return None

    @property
    def overall_progress(self) -> float:
        total = len(PIPELINE_STEPS)
        completed = sum(
            1 for sp in self.steps.values()
            if sp.status == JobStatus.COMPLETED
        )
        running = sum(
            sp.progress / 100.0
            for sp in self.steps.values()
            if sp.status == JobStatus.RUNNING
        )
        return ((completed + running) / total) * 100

    @property
    def elapsed_str(self) -> str:
        if not self.started_at:
            return "--"
        end = self.finished_at or time.time()
        secs = int(end - self.started_at)
        mins, secs = divmod(secs, 60)
        return f"{mins:02d}:{secs:02d}"


class AppState:
    """Thread-safe application state singleton."""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self.jobs: dict[str, Job] = {}
        self.job_order: list[str] = []  # Most recent first
        self._lock = threading.Lock()

    def create_job(self, url: str, target_lang: str) -> Job:
        job_id = str(uuid.uuid4())[:8]
        job = Job(job_id=job_id, url=url, target_lang=target_lang)
        with self._lock:
            self.jobs[job_id] = job
            self.job_order.insert(0, job_id)
        return job

    def get_job(self, job_id: str) -> Optional[Job]:
        return self.jobs.get(job_id)

    def get_all_jobs(self) -> list[Job]:
        with self._lock:
            return [self.jobs[jid] for jid in self.job_order if jid in self.jobs]

    def update_step(self, job_id: str, step: StepName,
                    status: JobStatus = None, progress: float = None,
                    message: str = None):
        job = self.jobs.get(job_id)
        if not job:
            return
        sp = job.steps[step]
        if status is not None:
            sp.status = status
            if status == JobStatus.RUNNING and sp.started_at is None:
                sp.started_at = time.time()
            if status in (JobStatus.COMPLETED, JobStatus.FAILED):
                sp.finished_at = time.time()
        if progress is not None:
            sp.progress = progress
        if message is not None:
            sp.message = message

    def start_job(self, job_id: str):
        job = self.jobs.get(job_id)
        if job:
            job.status = JobStatus.RUNNING
            job.started_at = time.time()

    def complete_job(self, job_id: str, final_video: str = None):
        job = self.jobs.get(job_id)
        if job:
            job.status = JobStatus.COMPLETED
            job.finished_at = time.time()
            if final_video:
                job.final_video = final_video

    def fail_job(self, job_id: str, error: str):
        job = self.jobs.get(job_id)
        if job:
            job.status = JobStatus.FAILED
            job.finished_at = time.time()
            job.error = error
