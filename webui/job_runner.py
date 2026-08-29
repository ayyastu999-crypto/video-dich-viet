"""Chay pipeline trong thread rieng va phat tien trinh cho web UI.

Cac step trong pipeline bao tien do bang print(), nen o day ta chuyen huong
stdout de bat tung dong log roi doi chieu sang so thu tu buoc tren giao dien.
"""
import io
import queue
import sys
import threading
import time
import uuid
from contextlib import redirect_stdout
from dataclasses import dataclass, field
from pathlib import Path

# Ten class step trong log  ->  thu tu buoc hien tren giao dien
STEP_OF = {
    "LocalSource": 0,
    "Downloader": 0,
    "Transcriber": 1,
    "Translator": 2,
    "ScriptExporter": 2,
    "TTSGenerator": 3,
    "TTSCloneGenerator": 3,
    "AudioSeparator": 3,
    "CaptionDetector": 4,
    "CaptionBlur": 4,
    "CaptionWriter": 4,
    "AudioMixer": 4,
    "Composer": 4,
}
TOTAL_STEPS = 5


@dataclass
class Job:
    id: str
    video: str
    lang: str = "vi"
    status: str = "pending"          # pending | running | done | error
    step: int = -1
    error: str = ""
    result: dict = field(default_factory=dict)
    started: float = field(default_factory=time.time)
    events: queue.Queue = field(default_factory=queue.Queue)

    def emit(self, kind: str, **data):
        self.events.put({"type": kind, **data})


JOBS: dict[str, Job] = {}


class LogPump(io.TextIOBase):
    """Bat tung dong pipeline in ra, day thanh su kien cho trinh duyet."""

    def __init__(self, job: Job, mirror):
        self.job = job
        self.mirror = mirror
        self.buf = ""

    def write(self, text):
        self.mirror.write(text)
        self.buf += text
        while "\n" in self.buf:
            line, self.buf = self.buf.split("\n", 1)
            if line.strip():
                self._handle(line.strip())
        return len(text)

    def _handle(self, line: str):
        self.job.emit("log", line=line)
        for name, idx in STEP_OF.items():
            if f"[{name}]" in line and idx > self.job.step:
                self.job.step = idx
                self.job.emit("step", index=idx, total=TOTAL_STEPS)
                break

    def flush(self):
        self.mirror.flush()


def _work(job: Job, opts: dict):
    """Chay pipeline that. Chay trong thread nen khong chan web server."""
    from src.pipeline import Pipeline

    job.status = "running"
    job.emit("status", status="running")
    pump = LogPump(job, sys.__stdout__)
    try:
        pipe = Pipeline(opts.get("config", "config/default.yaml"))

        # Cho phep giao dien ghi de vai tuy chon ma khong sua file config
        if opts.get("voice"):
            pipe.config.setdefault("tts", {}).setdefault("voices", {})[job.lang] = opts["voice"]
        if opts.get("src_lang") and opts["src_lang"] != "auto":
            pipe.config.setdefault("stt", {})["language"] = opts["src_lang"]
        elif opts.get("src_lang") == "auto":
            pipe.config.setdefault("stt", {})["language"] = None
        for key in ("separate_audio", "blur_old_captions", "export_script", "make_voice"):
            if key in opts:
                pipe.config.setdefault("pipeline", {})[key] = bool(opts[key])

        with redirect_stdout(pump):
            if opts.get("url"):
                result = pipe.run(url=opts["url"], target_lang=job.lang)
            else:
                result = pipe.run(local_video=job.video, target_lang=job.lang)

        job.result = {k: str(v) for k, v in result.items()}
        job.status = "done"
        job.step = TOTAL_STEPS
        job.emit("done", result=job.result, seconds=round(time.time() - job.started))
    except Exception as e:
        job.status = "error"
        job.error = f"{type(e).__name__}: {e}"
        job.emit("error", message=job.error)
    finally:
        job.emit("end")


def start_job(video: str, lang: str = "vi", opts: dict = None) -> Job:
    """Tao job moi va chay nen. Tra ve ngay de web tra job_id cho trinh duyet."""
    opts = opts or {}
    # Nguon la link thi chua co file, khong kiem tra ton tai
    if not opts.get("url") and not Path(video).exists():
        raise FileNotFoundError(f"Khong tim thay file: {video}")
    job = Job(id=uuid.uuid4().hex[:12], video=video, lang=lang)
    JOBS[job.id] = job
    threading.Thread(target=_work, args=(job, opts), daemon=True).start()
    return job
