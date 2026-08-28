"""Web UI cho pipeline dich video. Chay local, khong mo ra ngoai mang.

Chay:  .venv/Scripts/python.exe -m uvicorn webui.server:app --port 5177
"""
import asyncio
import json
import os
import subprocess
import sys
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)   # config/ va workspace/ deu tinh tu goc project

from src.config import load_dotenv                    # noqa: E402
from webui.job_runner import JOBS, start_job          # noqa: E402
from webui import settings as cfg_settings            # noqa: E402

# Nap .env ngay khi khoi dong: /api/settings doc key qua os.environ,
# khong nap truoc thi may da cau hinh roi van bao "chua co key".
load_dotenv()

app = FastAPI(title="Video Dich Viet")
STATIC = Path(__file__).parent / "static"


class JobRequest(BaseModel):
    path: str
    lang: str = "vi"
    voice: str | None = None
    src_lang: str = "auto"
    separate_audio: bool = False
    blur_old_captions: bool = False
    export_script: bool = True
    make_voice: bool = True


def _engine_status() -> dict:
    """Bao cho giao dien biet engine nao dung duoc, de khoa nhung cai chua san sang."""
    out = {}
    try:
        import ctranslate2
        out["whisper_gpu"] = ctranslate2.get_cuda_device_count() > 0
    except Exception:
        out["whisper_gpu"] = False
    try:
        from src.config import load_config
        cfg = load_config("config/default.yaml")
        out["gemini"] = bool(cfg.get("translation", {}).get("api_key")
                             or os.getenv("GEMINI_API_KEY"))
    except Exception:
        out["gemini"] = bool(os.getenv("GEMINI_API_KEY"))
    out["deepseek"] = bool(os.getenv("DEEPSEEK_API_KEY"))
    try:
        import demucs  # noqa: F401
        out["demucs"] = True
    except Exception:
        out["demucs"] = False
    return out


class KeyRequest(BaseModel):
    name: str
    value: str = ""


@app.get("/api/settings")
def get_settings():
    """Trang thai cac key. Khong tra key day du, chi 4 ky tu cuoi."""
    return {"keys": cfg_settings.read_all(ROOT)}


@app.post("/api/settings")
def set_setting(req: KeyRequest):
    """Luu key vao .env va nap luon, khong can khoi dong lai server."""
    try:
        cfg_settings.save(ROOT, req.name, req.value)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"ok": True, "keys": cfg_settings.read_all(ROOT), "engines": _engine_status()}


@app.get("/api/health")
def health():
    return {"ok": True, "engines": _engine_status()}


@app.post("/api/upload")
async def upload(file: UploadFile = File(...)):
    """Nhan file keo-tha tu trinh duyet. Trinh duyet khong cho biet duong dan
    that tren may, nen phai chep noi dung len roi lam viec voi ban trong workspace."""
    from src.steps.local_source import VIDEO_EXTS, slugify

    ext = Path(file.filename or "").suffix.lower()
    if ext not in VIDEO_EXTS:
        raise HTTPException(400, f"Duoi file khong ho tro: {ext}")

    dest_dir = ROOT / "workspace" / "downloads"
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"{slugify(file.filename)}{ext}"
    with open(dest, "wb") as f:
        while chunk := await file.read(1 << 20):
            f.write(chunk)

    return {"path": str(dest), "name": dest.name,
            "size": dest.stat().st_size}


@app.post("/api/jobs")
def create_job(req: JobRequest):
    try:
        job = start_job(req.path, req.lang, req.model_dump())
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))
    return {"job_id": job.id}


@app.get("/api/jobs/{job_id}")
def job_status(job_id: str):
    job = JOBS.get(job_id)
    if not job:
        raise HTTPException(404, "Khong co job nay")
    return {"id": job.id, "status": job.status, "step": job.step,
            "error": job.error, "result": job.result}


@app.get("/api/jobs/{job_id}/events")
async def job_events(job_id: str):
    """Day tien trinh ve trinh duyet bang Server-Sent Events."""
    job = JOBS.get(job_id)
    if not job:
        raise HTTPException(404, "Khong co job nay")

    async def stream():
        loop = asyncio.get_event_loop()
        while True:
            try:
                ev = await loop.run_in_executor(None, job.events.get, True, 30)
            except Exception:
                yield ": keepalive\n\n"      # giu ket noi khi step chay lau
                continue
            yield f"data: {json.dumps(ev, ensure_ascii=False)}\n\n"
            if ev.get("type") == "end":
                break

    return StreamingResponse(stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache",
                                      "X-Accel-Buffering": "no"})


def _safe_output(path_str: str) -> Path:
    """Chi cho phep doc file nam trong workspace/ - tranh lo file khac tren may."""
    p = Path(path_str).resolve()
    ws = (ROOT / "workspace").resolve()
    if ws not in p.parents:
        raise HTTPException(403, "Duong dan ngoai workspace")
    if not p.exists():
        raise HTTPException(404, "File khong ton tai")
    return p


@app.get("/api/file")
def get_file(path: str, inline: int = 0):
    """Phuc vu file trong workspace.

    inline=1: khong dat Content-Disposition attachment, de the <video> phat thang
    trong trang. FileResponse cua Starlette da ho tro Range nen tua duoc.
    """
    p = _safe_output(path)
    if inline:
        return FileResponse(p)
    return FileResponse(p, filename=p.name)


@app.post("/api/reveal")
def reveal(path: str):
    """Mo thu muc chua file trong Explorer."""
    p = _safe_output(path)
    subprocess.Popen(["explorer", "/select,", str(p)])
    return {"ok": True}


app.mount("/", StaticFiles(directory=str(STATIC), html=True), name="static")
