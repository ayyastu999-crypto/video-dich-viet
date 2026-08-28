"""Xuat kich ban ra file text de copy va viet lai content.

Khac voi file .srt: bo timestamp, gop cac cau roi thanh doan van lien mach
nen dan thang vao ChatGPT/Claude de viet lai duoc ngay.
"""
from pathlib import Path

from src.steps.base import BaseStep
from src.utils.srt import parse_srt

# Ket cau -> duoc phep ngat doan tai day
SENTENCE_END = (".", "!", "?", "…", ":")

# Nghi lau hon nguong nay (giay) thi coi la sang y moi
PARA_GAP_SEC = 1.6
# Doan qua dai thi ngat du chua nghi lau
PARA_MAX_CHARS = 420
# Doan qua ngan thi khong ngat, gop tiep
PARA_MIN_CHARS = 90


def _clean(text: str) -> str:
    """Bo xuong dong trong 1 cue, gop thanh 1 dong."""
    return " ".join(text.replace("\n", " ").split())


def merge_paragraphs(cues: list[dict]) -> list[str]:
    """Gop cue thanh doan van doc duoc.

    Ngat doan khi: nghi lau + da du dai, hoac doan qua dai va vua het cau.
    """
    paras, buf = [], ""
    for i, cue in enumerate(cues):
        text = _clean(cue["text"])
        if not text:
            continue
        buf = (buf + " " + text).strip() if buf else text

        nxt = cues[i + 1] if i + 1 < len(cues) else None
        gap = (nxt["start"] - cue["end"]) if nxt else 999
        ends_sentence = buf.endswith(SENTENCE_END)

        long_pause = gap >= PARA_GAP_SEC and len(buf) >= PARA_MIN_CHARS
        too_long = len(buf) >= PARA_MAX_CHARS and ends_sentence
        if nxt is None or long_pause or too_long:
            paras.append(buf)
            buf = ""
    if buf:
        paras.append(buf)
    return paras


def fmt_clock(seconds: float) -> str:
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    return f"{h:d}:{m:02d}:{s:02d}" if h else f"{m:d}:{s:02d}"


class ScriptExporter(BaseStep):
    """Xuat 2 file text: kich ban thuan tieng Viet, va ban song ngu doi chieu."""

    def run(self, translated_srt, original_srt=None, metadata=None,
            target_lang: str = "vi") -> dict:
        out_dir = self.ensure_dir("output")
        meta = metadata or {}
        stem = Path(translated_srt).stem.replace("_translated", "").replace(f"_{target_lang}", "")

        vi_cues = parse_srt(str(translated_srt))
        if not vi_cues:
            raise ValueError(f"File phu de rong: {translated_srt}")

        title = meta.get("title") or stem
        duration = vi_cues[-1]["end"]
        header = [
            f"KỊCH BẢN — {title}",
            f"Thời lượng {fmt_clock(duration)} · {len(vi_cues)} câu thoại",
        ]
        if meta.get("original_path"):
            header.append(f"Nguồn: {meta['original_path']}")
        elif meta.get("source"):
            header.append(f"Nguồn: {meta['source']}")
        header.append("-" * 60)

        # 1) Kich ban van xuoi - de copy di viet lai content
        paras = merge_paragraphs(vi_cues)
        plain_path = out_dir / f"{stem}_kich-ban-{target_lang}.txt"
        plain_path.write_text(
            "\n".join(header) + "\n\n" + "\n\n".join(paras) + "\n",
            encoding="utf-8",
        )
        self.log(f"Kich ban van xuoi: {plain_path.name} ({len(paras)} doan)")

        result = {"script_plain": plain_path, "paragraphs": len(paras)}

        # 2) Ban song ngu doi chieu (neu co phu de goc)
        if original_srt and Path(original_srt).exists():
            src_cues = parse_srt(str(original_srt))
            lines = list(header)
            lines[0] = f"KỊCH BẢN SONG NGỮ — {title}"
            lines.append("")
            for i, cue in enumerate(vi_cues):
                ts = fmt_clock(cue["start"])
                lines.append(f"[{ts}] {_clean(cue['text'])}")
                if i < len(src_cues):
                    lines.append(f"        {_clean(src_cues[i]['text'])}")
                lines.append("")
            bi_path = out_dir / f"{stem}_kich-ban-song-ngu.txt"
            bi_path.write_text("\n".join(lines), encoding="utf-8")
            self.log(f"Kich ban song ngu: {bi_path.name}")
            result["script_bilingual"] = bi_path

        return result
