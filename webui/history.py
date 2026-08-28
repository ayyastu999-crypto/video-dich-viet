"""Doc lich su cac video da xu ly xong.

Nguon su that la thu muc output/ - moi video mot thu muc kem job.json.
Khong dung co so du lieu: tat may, xoa thu muc, sao chep sang may khac deu
van dung, vi lich su chinh la file nam do.
"""
import json
from pathlib import Path


def list_projects(root: Path) -> list:
    """Liet ke cac du an da xong, moi nhat truoc."""
    out_dir = root / "output"
    if not out_dir.is_dir():
        return []

    items = []
    for d in out_dir.iterdir():
        if not d.is_dir():
            continue
        rec = _read_record(d)
        if rec:
            items.append(rec)

    items.sort(key=lambda r: r.get("finished_at") or "", reverse=True)
    return items


def _read_record(d: Path) -> dict:
    """Doc job.json. Thu muc cu chua co file nay thi dung lai tu file co san."""
    f = d / "job.json"
    if f.exists():
        try:
            rec = json.loads(f.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            rec = None
        if rec:
            rec["dir"] = str(d).replace(chr(92), "/")
            rec["files"] = _verify(d, rec.get("files") or {})
            rec["size"] = _dir_size(d)
            return rec

    # Thu muc lam truoc khi co job.json - dung lai tu nhung gi con thay
    files = {name: str(d / fn).replace(chr(92), "/")
             for name, fn in KNOWN.items() if (d / fn).exists()}
    if not files:
        return None
    meta = _parse_info(d)
    return {
        "id": d.name,
        "title": meta.get("title") or d.name,
        "finished_at": _mtime(d),
        "duration": meta.get("duration"),
        "engines": meta.get("engines"),
        "files": files,
        "dir": str(d).replace(chr(92), "/"),
        "size": _dir_size(d),
        "legacy": True,
    }


def _parse_info(d: Path) -> dict:
    """Vot lai thong tin tu thong-tin.txt cho thu muc tao truoc khi co job.json."""
    f = d / "thong-tin.txt"
    if not f.exists():
        return {}
    out = {}
    try:
        for line in f.read_text(encoding="utf-8").splitlines():
            if line.startswith("VIDEO:"):
                out["title"] = line.split(":", 1)[1].strip()
            elif line.startswith("Thoi luong:"):
                parts = line.split(":", 1)[1].strip().split(":")
                if len(parts) == 2 and parts[0].strip().isdigit():
                    out["duration"] = int(parts[0]) * 60 + int(parts[1])
            elif line.startswith("Cong cu:"):
                out["engines"] = line.split(":", 1)[1].strip()
    except OSError:
        pass
    return out


KNOWN = {
    "final_video": "video-hoan-chinh.mp4",
    "translated_srt": "phu-de-viet.srt",
    "original_srt": "phu-de-goc.srt",
    "script_plain": "kich-ban-viet.txt",
    "script_bilingual": "kich-ban-song-ngu.txt",
    "tts_audio": "giong-doc-viet.mp3",
}


def _verify(d: Path, files: dict) -> dict:
    """Bo nhung file da bi xoa tay khoi danh sach."""
    ok = {}
    for k, v in files.items():
        p = Path(v)
        if not p.is_absolute():
            p = d.parent.parent / v
        if p.exists():
            ok[k] = str(p).replace(chr(92), "/")
    return ok


def _dir_size(d: Path) -> int:
    return sum(f.stat().st_size for f in d.rglob("*") if f.is_file())


def _mtime(d: Path) -> str:
    from datetime import datetime
    return datetime.fromtimestamp(d.stat().st_mtime).isoformat(timespec="seconds")
