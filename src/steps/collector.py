"""Gom ket qua cua 1 video vao mot thu muc rieng, ten file de hieu.

Cac buoc truoc rai file khap workspace/srt, workspace/tts, workspace/output.
Buoc nay chep ban cuoi vao  output/<ten-video>/  de nguoi dung mo mot cho la
thay du, va moi video mot thu muc rieng khong lan nhau.
"""
import shutil
from datetime import datetime
from pathlib import Path

from src.steps.base import BaseStep

# ten trong ket qua pipeline -> ten file dat cho nguoi dung
RENAME = [
    ("final_video",      "video-hoan-chinh.mp4"),
    ("translated_srt",   "phu-de-viet.srt"),
    ("original_srt",     "phu-de-goc.srt"),
    ("script_plain",     "kich-ban-viet.txt"),
    ("script_bilingual", "kich-ban-song-ngu.txt"),
    ("tts_audio",        "giong-doc-viet.mp3"),
]


class Collector(BaseStep):
    def run(self, video_id: str, items: dict, info: dict = None) -> dict:
        # output/ dat o goc du an cho de tim, khong chon trong workspace/
        base = Path("output") / video_id
        base.mkdir(parents=True, exist_ok=True)

        copied = {}
        for key, nice_name in RENAME:
            src = items.get(key)
            if not src:
                continue
            src = Path(src)
            if not src.exists():
                continue
            dest = base / nice_name
            if src.resolve() != dest.resolve():
                shutil.copy2(src, dest)
            copied[key] = dest

        self._write_info(base, video_id, info or {}, copied)
        self.log(f"Da gom {len(copied)} file vao: {base}")
        return {"project_dir": base, "collected": copied}

    def _write_info(self, base: Path, video_id: str, info: dict, copied: dict):
        """Ghi chu ngan de sau mo lai con biet video nay lam tu dau, bang gi."""
        lines = [
            f"VIDEO: {info.get('title') or video_id}",
            f"Xu ly luc: {datetime.now().strftime('%d/%m/%Y %H:%M')}",
        ]
        if info.get("original_path"):
            lines.append(f"File goc: {info['original_path']}")
        if info.get("duration"):
            lines.append(f"Thoi luong: {int(info['duration'] // 60)}:"
                         f"{int(info['duration'] % 60):02d}")
        if info.get("cues"):
            lines.append(f"So cau thoai: {info['cues']}")
        if info.get("engines"):
            lines.append(f"Cong cu: {info['engines']}")
        lines.append("")
        lines.append("File trong thu muc nay:")
        for key, nice in RENAME:
            if key in copied:
                lines.append(f"  - {nice}")
        (base / "thong-tin.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
