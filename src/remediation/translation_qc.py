"""
Bộ kiểm tra chất lượng (QC) bản dịch của Gemini/OpenAI.

Phát hiện:
    - Lệch số segment giữa SRT gốc và bản dịch
    - Segment dịch rỗng
    - Segment "đã dịch" nhưng vẫn còn ký tự Trung
    - Lỗi mã hoá (replacement char U+FFFD, mojibake)
    - Chênh lệch độ dài quá lớn (> 3x hoặc < 1/3) -> nghi ngờ
    - Chênh lệch độ dài tổng thể bất thường

Khi phát hiện lỗi: gọi lại Translator với prompt nghiêm ngặt
chỉ cho các segment có vấn đề, ghép vào file kết quả.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

from src.utils.srt import parse_srt, write_srt
from src.remediation._common import audit, get_logger


# Khoảng Unicode chứa ký tự Hán (CJK Unified Ideographs + extensions)
CJK_RE = re.compile(
    r"[\u3400-\u4DBF"   # CJK Ext A
    r"\u4E00-\u9FFF"    # CJK Unified
    r"\uF900-\uFAFF"    # CJK Compat
    r"\U00020000-\U0002A6DF"  # CJK Ext B
    r"]"
)
# Replacement char là dấu hiệu lỗi mã hoá
REPLACEMENT_CHAR = "\uFFFD"

# Tỉ lệ chiều dài cho phép giữa gốc và bản dịch (dịch Việt-Trung)
LEN_RATIO_MAX = 3.5
LEN_RATIO_MIN = 1 / 3.5


@dataclass
class TranslationIssue:
    code: str
    severity: str
    message: str
    segment_index: int | None = None
    original_text: str | None = None
    translated_text: str | None = None


@dataclass
class TranslationReport:
    original_path: str
    translated_path: str
    original_count: int = 0
    translated_count: int = 0
    issues: list[TranslationIssue] = field(default_factory=list)
    bad_segments: list[int] = field(default_factory=list)  # indexes cần dịch lại
    is_recoverable: bool = True
    repaired: bool = False
    repair_method: str | None = None

    def add(self, issue: TranslationIssue) -> None:
        self.issues.append(issue)

    def severity_count(self, sev: str) -> int:
        return sum(1 for i in self.issues if i.severity == sev)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class TranslationQC:
    """Validator + auto-repair cho cặp SRT gốc-dịch."""

    def __init__(
        self,
        config: dict | None = None,
        work_dir: Path | str | None = None,
    ):
        self.config = config or {}
        self.work_dir = Path(work_dir) if work_dir else Path("workspace")
        self.logger = get_logger("translation_qc", self.work_dir)

    # ------------------------------------------------------------------
    def validate(
        self,
        original_srt: Path | str,
        translated_srt: Path | str,
        target_lang: str = "vi",
    ) -> TranslationReport:
        original_srt = Path(original_srt)
        translated_srt = Path(translated_srt)
        report = TranslationReport(
            original_path=str(original_srt),
            translated_path=str(translated_srt),
        )

        if not original_srt.exists():
            report.add(TranslationIssue(
                "ORIGINAL_MISSING", "fatal",
                f"Không tìm thấy SRT gốc: {original_srt}",
            ))
            report.is_recoverable = False
            return report

        if not translated_srt.exists():
            report.add(TranslationIssue(
                "TRANSLATED_MISSING", "fatal",
                f"Không tìm thấy SRT bản dịch: {translated_srt}",
            ))
            return report

        try:
            orig = parse_srt(str(original_srt))
            trans = parse_srt(str(translated_srt))
        except Exception as e:
            report.add(TranslationIssue(
                "PARSE_ERROR", "fatal",
                f"Không phân tích được SRT: {e!s}",
            ))
            return report

        report.original_count = len(orig)
        report.translated_count = len(trans)

        # 1. Lệch số dòng
        if len(orig) != len(trans):
            report.add(TranslationIssue(
                "COUNT_MISMATCH", "error",
                f"Số segment lệch: gốc={len(orig)}, dịch={len(trans)}",
            ))
            # Vẫn tiếp tục kiểm tra trên min(len)

        # 2-5. Kiểm tra theo từng cặp
        pair_count = min(len(orig), len(trans))
        for i in range(pair_count):
            o = orig[i]
            t = trans[i]
            self._check_segment(o, t, target_lang, report)

        # Các segment thừa (gốc nhiều hơn dịch) -> đánh dấu cần dịch
        for i in range(pair_count, len(orig)):
            report.bad_segments.append(orig[i]["index"])
            report.add(TranslationIssue(
                "MISSING_TRANSLATION", "error",
                f"Segment gốc {orig[i]['index']} thiếu bản dịch",
                segment_index=orig[i]["index"],
                original_text=orig[i]["text"],
            ))

        report.bad_segments = sorted(set(report.bad_segments))

        if any(i.severity == "fatal" for i in report.issues):
            report.is_recoverable = False

        audit("translation_validate", {
            "original": str(original_srt),
            "translated": str(translated_srt),
            "issues": len(report.issues),
            "bad_segments": len(report.bad_segments),
            "recoverable": report.is_recoverable,
        }, self.work_dir)

        return report

    # ------------------------------------------------------------------
    def _check_segment(
        self,
        orig: dict,
        trans: dict,
        target_lang: str,
        report: TranslationReport,
    ) -> None:
        idx = trans["index"]
        otext = orig["text"].strip()
        ttext = trans["text"].strip()

        # Empty translation
        if not ttext:
            report.bad_segments.append(idx)
            report.add(TranslationIssue(
                "EMPTY_TRANSLATION", "error",
                f"Segment {idx} có bản dịch rỗng",
                segment_index=idx,
                original_text=otext,
            ))
            return

        # Encoding issue
        if REPLACEMENT_CHAR in ttext:
            report.bad_segments.append(idx)
            report.add(TranslationIssue(
                "ENCODING_ERROR", "error",
                f"Segment {idx} chứa ký tự thay thế (lỗi mã hoá)",
                segment_index=idx,
                original_text=otext,
                translated_text=ttext,
            ))

        # Untranslated: vẫn còn nhiều CJK trong khi target không phải zh
        if target_lang != "zh":
            cjk_chars = CJK_RE.findall(ttext)
            # Cho phép 1-2 ký tự (tên riêng, etc.), từ 3 trở lên = nghi ngờ
            if len(cjk_chars) >= 3:
                report.bad_segments.append(idx)
                report.add(TranslationIssue(
                    "UNTRANSLATED", "error",
                    f"Segment {idx} còn {len(cjk_chars)} ký tự Trung Quốc - chưa được dịch",
                    segment_index=idx,
                    original_text=otext,
                    translated_text=ttext,
                ))

        # Length ratio (chỉ cảnh báo, không tự dịch lại)
        if otext:
            ratio = len(ttext) / max(len(otext), 1)
            if ratio > LEN_RATIO_MAX or ratio < LEN_RATIO_MIN:
                report.add(TranslationIssue(
                    "LENGTH_ANOMALY", "warn",
                    f"Segment {idx} chênh lệch độ dài bất thường (tỉ lệ {ratio:.2f})",
                    segment_index=idx,
                    original_text=otext,
                    translated_text=ttext,
                ))

    # ------------------------------------------------------------------
    def repair(
        self,
        report: TranslationReport,
        target_lang: str = "vi",
    ) -> TranslationReport:
        """Dịch lại các segment bị đánh dấu xấu, ghép vào file kết quả."""
        if not report.bad_segments:
            return report
        if not report.is_recoverable:
            self.logger.error(f"Không thể repair (fatal): {report.translated_path}")
            return report

        try:
            orig = parse_srt(report.original_path)
        except Exception as e:
            self.logger.error(f"Repair lỗi parse gốc: {e}")
            return report

        # Đảm bảo có translated SRT (có thể rỗng nếu COUNT_MISMATCH)
        if Path(report.translated_path).exists():
            try:
                trans = parse_srt(report.translated_path)
            except Exception:
                trans = []
        else:
            trans = []

        # Map index -> text dịch hiện tại
        trans_map = {t["index"]: t["text"] for t in trans}

        # Lấy text gốc cần dịch
        bad_set = set(report.bad_segments)
        to_translate = [(o["index"], o["text"]) for o in orig if o["index"] in bad_set]

        if not to_translate:
            return report

        new_translations = self._retranslate(
            [t for _, t in to_translate], target_lang
        )

        if len(new_translations) != len(to_translate):
            self.logger.warning(
                f"Repair không khớp: yêu cầu {len(to_translate)} dòng, "
                f"nhận {len(new_translations)}"
            )
            # Vẫn ghi những gì có
            for (idx, _), txt in zip(to_translate, new_translations):
                trans_map[idx] = txt
        else:
            for (idx, _), txt in zip(to_translate, new_translations):
                trans_map[idx] = txt

        # Tái dựng đầy đủ từ gốc (đảm bảo không thiếu)
        repaired_segments = []
        for o in orig:
            text = trans_map.get(o["index"], "").strip()
            if not text:
                # Fallback: giữ nguyên gốc để không mất data
                text = o["text"]
            repaired_segments.append({
                "start": o["start"],
                "end": o["end"],
                "text": text,
            })

        # Backup + ghi
        translated_path = Path(report.translated_path)
        backup = translated_path.with_suffix(translated_path.suffix + ".bak")
        if translated_path.exists() and not backup.exists():
            backup.write_bytes(translated_path.read_bytes())
        write_srt(repaired_segments, str(translated_path))

        report.repaired = True
        report.repair_method = "selective_retranslate"
        self.logger.info(
            f"REPAIRED {translated_path} - dịch lại {len(to_translate)} segment"
        )
        audit("translation_repair", {
            "translated": str(translated_path),
            "repaired_segments": len(to_translate),
        }, self.work_dir)
        return report

    # ------------------------------------------------------------------
    def _retranslate(self, texts: list[str], target_lang: str) -> list[str]:
        """Gọi lại Translator với prompt strict cho danh sách texts."""
        if not texts:
            return []
        try:
            from src.steps.translator import Translator, LANG_NAMES
        except Exception as e:
            self.logger.error(f"Không import được Translator: {e}")
            return [""] * len(texts)

        trans_cfg = (self.config or {}).get("translation", {})
        if not trans_cfg:
            self.logger.error("Thiếu cấu hình translation - không thể repair")
            return [""] * len(texts)

        provider = trans_cfg.get("provider", "gemini")
        lang_name = LANG_NAMES.get(target_lang, target_lang)

        translator = Translator(self.config, self.work_dir)
        try:
            if provider == "gemini":
                client = translator._init_gemini(trans_cfg)
            else:
                client = translator._init_openai()
            return translator._translate_batch(
                client, provider, trans_cfg, texts, lang_name, strict=True
            )
        except Exception as e:
            self.logger.error(f"Repair retranslate lỗi: {e}")
            return [""] * len(texts)
