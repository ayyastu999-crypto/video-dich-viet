"""
Bộ kiểm tra chất lượng và sửa lỗi tự động cho file SRT.

Phát hiện:
    - SRT rỗng (0 segment)                               -> không thể phục hồi
    - Văn bản ảo giác (Whisper lặp đi lặp lại 1 câu)     -> đánh dấu bỏ
    - Trùng lấn thời gian (segment N.end > segment N+1.start)  -> auto-fix
    - Thời lượng âm (end < start)                        -> auto-fix
    - Mất / sai định dạng timestamp HH:MM:SS,mmm         -> tách dòng hỏng
    - Lệch số dòng giữa SRT gốc và bản dịch              -> báo cáo

Mọi sửa đổi đều được sao lưu ra `<file>.bak` trước khi ghi đè.
"""
from __future__ import annotations

import re
import shutil
from collections import Counter
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

from src.utils.srt import parse_srt, write_srt
from src.remediation._common import audit, get_logger, ok, warn, err


# ---------------------------------------------------------------------------
# Hằng số nhận diện ảo giác Whisper (tiếng Trung Douyin thường gặp)
# ---------------------------------------------------------------------------
HALLUCINATION_PATTERNS = [
    "本歌曲来自",
    "本字幕由",
    "字幕由",
    "提供",
    "請不吝點贊",
    "请不吝点赞",
    "Subscribe to",
    "字幕志愿者",
    "謝謝觀看",
    "谢谢观看",
    "MBC 뉴스",
]

REPEAT_THRESHOLD = 3      # 1 câu lặp >= 3 lần liên tiếp -> ảo giác
TIMESTAMP_RE = re.compile(r"^\d{2}:\d{2}:\d{2},\d{3}$")


# ---------------------------------------------------------------------------
# Báo cáo có cấu trúc
# ---------------------------------------------------------------------------
@dataclass
class SrtIssue:
    code: str                 # vd: "EMPTY", "HALLUCINATION", "OVERLAP"
    severity: str             # "info" | "warn" | "error" | "fatal"
    message: str              # mô tả tiếng Việt
    segment_index: int | None = None
    fixable: bool = False
    fixed: bool = False


@dataclass
class SrtReport:
    path: str
    exists: bool
    segment_count: int = 0
    issues: list[SrtIssue] = field(default_factory=list)
    is_recoverable: bool = True
    is_fatal: bool = False
    fixed_path: str | None = None

    def add(self, issue: SrtIssue) -> None:
        self.issues.append(issue)
        if issue.severity == "fatal":
            self.is_fatal = True
            self.is_recoverable = False

    def has_errors(self) -> bool:
        return any(i.severity in ("error", "fatal") for i in self.issues)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        return d


# ---------------------------------------------------------------------------
# Validator chính
# ---------------------------------------------------------------------------
class SrtValidator:
    """Kiểm tra + auto-fix một file SRT (hoặc cặp original/translated)."""

    def __init__(self, work_dir: Path | str | None = None, auto_fix: bool = True):
        self.work_dir = Path(work_dir) if work_dir else Path("workspace")
        self.auto_fix = auto_fix
        self.logger = get_logger("srt_validator", self.work_dir)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def validate(self, srt_path: Path | str) -> SrtReport:
        srt_path = Path(srt_path)
        report = SrtReport(path=str(srt_path), exists=srt_path.exists())

        if not report.exists:
            report.add(SrtIssue("MISSING", "fatal", f"File SRT không tồn tại: {srt_path}"))
            self.logger.error(f"MISSING {srt_path}")
            return report

        # Đọc thô để bắt timestamp hỏng (pysrt có thể nuốt lỗi)
        self._scan_raw_format(srt_path, report)

        # Parse có cấu trúc
        try:
            segments = parse_srt(str(srt_path))
        except Exception as e:
            report.add(SrtIssue(
                "PARSE_ERROR", "fatal",
                f"Không phân tích được SRT: {e!s}",
            ))
            self.logger.error(f"PARSE_ERROR {srt_path}: {e}")
            return report

        report.segment_count = len(segments)

        if len(segments) == 0:
            report.add(SrtIssue(
                "EMPTY", "fatal",
                "SRT rỗng (0 segment) - đề nghị bỏ qua video này",
            ))
            self.logger.error(f"EMPTY {srt_path}")
            return report

        # Các kiểm tra ngữ nghĩa
        self._check_hallucination(segments, report)
        self._check_timing(segments, report)
        self._check_text_quality(segments, report)

        # Auto-fix nếu được phép
        if self.auto_fix and any(i.fixable for i in report.issues):
            fixed_segments = self._apply_fixes(segments, report)
            if fixed_segments is not None:
                fixed_path = self._write_fixed(srt_path, fixed_segments)
                report.fixed_path = str(fixed_path)
                self.logger.info(f"FIXED {srt_path} -> {fixed_path}")

        audit("srt_validate", {
            "path": str(srt_path),
            "segments": report.segment_count,
            "issues": len(report.issues),
            "fatal": report.is_fatal,
            "recoverable": report.is_recoverable,
        }, self.work_dir)

        return report

    def validate_pair(self, original: Path | str, translated: Path | str) -> tuple[SrtReport, SrtReport]:
        """Kiểm tra cặp SRT gốc + bản dịch và đối chiếu số dòng."""
        rep_orig = self.validate(original)
        rep_trans = self.validate(translated)

        if rep_orig.segment_count and rep_trans.segment_count:
            if rep_orig.segment_count != rep_trans.segment_count:
                msg = (f"Lệch số segment: gốc={rep_orig.segment_count}, "
                       f"dịch={rep_trans.segment_count}")
                rep_trans.add(SrtIssue(
                    "COUNT_MISMATCH", "error", msg,
                    fixable=False,
                ))
                self.logger.warning(f"COUNT_MISMATCH {translated}: {msg}")

        return rep_orig, rep_trans

    # ------------------------------------------------------------------
    # Kiểm tra cụ thể
    # ------------------------------------------------------------------
    def _scan_raw_format(self, srt_path: Path, report: SrtReport) -> None:
        """Tìm timestamp sai định dạng ở mức raw (trước khi pysrt loại bỏ)."""
        try:
            text = srt_path.read_text(encoding="utf-8", errors="replace")
        except OSError as e:
            report.add(SrtIssue("IO_ERROR", "fatal", f"Không đọc được file: {e}"))
            return

        for lineno, line in enumerate(text.splitlines(), 1):
            if "-->" in line:
                parts = [p.strip() for p in line.split("-->")]
                if len(parts) != 2 or not all(TIMESTAMP_RE.match(p) for p in parts):
                    report.add(SrtIssue(
                        "BAD_TIMESTAMP", "warn",
                        f"Timestamp sai định dạng ở dòng {lineno}: '{line}'",
                        fixable=False,
                    ))

    def _check_hallucination(self, segments: list[dict], report: SrtReport) -> None:
        """Phát hiện văn bản ảo giác của Whisper."""
        # 1. Cụm từ đặc trưng
        for seg in segments:
            text = seg["text"].strip()
            for pat in HALLUCINATION_PATTERNS:
                if pat in text:
                    report.add(SrtIssue(
                        "HALLUCINATION_PATTERN", "error",
                        f"Phát hiện cụm ảo giác '{pat}' tại segment {seg['index']}: {text!r}",
                        segment_index=seg["index"],
                        fixable=True,
                    ))
                    break

        # 2. Lặp lại liên tiếp
        run_text: str | None = None
        run_start: int = -1
        run_len: int = 0
        for seg in segments:
            t = seg["text"].strip()
            if t == run_text:
                run_len += 1
            else:
                if run_len >= REPEAT_THRESHOLD:
                    report.add(SrtIssue(
                        "HALLUCINATION_REPEAT", "error",
                        f"Câu '{run_text}' lặp {run_len} lần liên tiếp từ segment {run_start}",
                        segment_index=run_start,
                        fixable=True,
                    ))
                run_text = t
                run_start = seg["index"]
                run_len = 1
        if run_len >= REPEAT_THRESHOLD:
            report.add(SrtIssue(
                "HALLUCINATION_REPEAT", "error",
                f"Câu '{run_text}' lặp {run_len} lần liên tiếp từ segment {run_start}",
                segment_index=run_start,
                fixable=True,
            ))

        # 3. Cùng 1 câu chiếm > 50% toàn file
        counter = Counter(seg["text"].strip() for seg in segments)
        most_common, freq = counter.most_common(1)[0]
        if len(segments) >= 6 and freq / len(segments) > 0.5:
            report.add(SrtIssue(
                "HALLUCINATION_DOMINANT", "fatal",
                f"Câu '{most_common}' chiếm {freq}/{len(segments)} ({freq/len(segments)*100:.0f}%) toàn file",
                fixable=False,
            ))

    def _check_timing(self, segments: list[dict], report: SrtReport) -> None:
        for i, seg in enumerate(segments):
            # Negative duration
            if seg["end"] < seg["start"]:
                report.add(SrtIssue(
                    "NEGATIVE_DURATION", "error",
                    f"Segment {seg['index']} có thời lượng âm: "
                    f"start={seg['start']:.3f} > end={seg['end']:.3f}",
                    segment_index=seg["index"],
                    fixable=True,
                ))
            # Zero duration
            elif seg["end"] == seg["start"]:
                report.add(SrtIssue(
                    "ZERO_DURATION", "warn",
                    f"Segment {seg['index']} có thời lượng = 0",
                    segment_index=seg["index"],
                    fixable=True,
                ))

            # Overlap với segment kế tiếp
            if i + 1 < len(segments):
                nxt = segments[i + 1]
                if seg["end"] > nxt["start"]:
                    report.add(SrtIssue(
                        "OVERLAP", "warn",
                        f"Segment {seg['index']} chồng lấn segment {nxt['index']}: "
                        f"end={seg['end']:.3f} > next.start={nxt['start']:.3f}",
                        segment_index=seg["index"],
                        fixable=True,
                    ))

    def _check_text_quality(self, segments: list[dict], report: SrtReport) -> None:
        for seg in segments:
            text = seg["text"].strip()
            if not text:
                report.add(SrtIssue(
                    "EMPTY_TEXT", "warn",
                    f"Segment {seg['index']} không có nội dung",
                    segment_index=seg["index"],
                    fixable=True,
                ))
            elif len(text) > 500:
                report.add(SrtIssue(
                    "TEXT_TOO_LONG", "warn",
                    f"Segment {seg['index']} quá dài ({len(text)} ký tự)",
                    segment_index=seg["index"],
                    fixable=False,
                ))

    # ------------------------------------------------------------------
    # Auto-fix
    # ------------------------------------------------------------------
    def _apply_fixes(self, segments: list[dict], report: SrtReport) -> list[dict] | None:
        """Áp dụng các sửa lỗi xác định, trả về danh sách segment mới."""
        # Tập segment cần loại bỏ
        drop_indices: set[int] = set()
        for issue in report.issues:
            if issue.code in ("HALLUCINATION_PATTERN", "EMPTY_TEXT") and issue.segment_index:
                drop_indices.add(issue.segment_index)
            if issue.code == "HALLUCINATION_REPEAT" and issue.segment_index:
                # Loại tất cả segment lặp lại liên tiếp bắt đầu từ index này
                start_idx = issue.segment_index
                # Tìm tất cả segment sau start_idx có cùng nội dung
                start_pos = next((i for i, s in enumerate(segments) if s["index"] == start_idx), None)
                if start_pos is not None:
                    target_text = segments[start_pos]["text"].strip()
                    # Giữ lại 1 segment đầu, bỏ các bản sao
                    for j in range(start_pos + 1, len(segments)):
                        if segments[j]["text"].strip() == target_text:
                            drop_indices.add(segments[j]["index"])
                        else:
                            break

        cleaned = [s for s in segments if s["index"] not in drop_indices]

        # Sửa thời gian
        for i, seg in enumerate(cleaned):
            if seg["end"] < seg["start"]:
                # Đảo lại: dùng start làm anchor, gán end = start + 1s
                seg["end"] = seg["start"] + 1.0
            if seg["end"] == seg["start"]:
                seg["end"] = seg["start"] + 0.5
            if i + 1 < len(cleaned):
                nxt = cleaned[i + 1]
                if seg["end"] > nxt["start"]:
                    # Cắt end về đúng start của segment kế
                    seg["end"] = max(seg["start"] + 0.1, nxt["start"] - 0.001)

        # Đánh dấu các issue đã sửa
        fixed_codes = {"HALLUCINATION_PATTERN", "HALLUCINATION_REPEAT",
                       "EMPTY_TEXT", "NEGATIVE_DURATION", "ZERO_DURATION", "OVERLAP"}
        for issue in report.issues:
            if issue.code in fixed_codes and issue.fixable:
                issue.fixed = True

        if not cleaned:
            # Sau khi sửa không còn segment nào -> báo fatal
            report.add(SrtIssue(
                "EMPTY_AFTER_FIX", "fatal",
                "Sau khi sửa lỗi, không còn segment hợp lệ nào",
            ))
            return None

        return cleaned

    def _write_fixed(self, original_path: Path, segments: list[dict]) -> Path:
        """Sao lưu file gốc và ghi đè bằng phiên bản đã sửa."""
        backup = original_path.with_suffix(original_path.suffix + ".bak")
        if not backup.exists():
            shutil.copy2(original_path, backup)
        write_srt(segments, str(original_path))
        return original_path


# ---------------------------------------------------------------------------
# Quick CLI for ad-hoc testing
# ---------------------------------------------------------------------------
def _cli() -> int:
    import sys
    if len(sys.argv) < 2:
        print(err("Sử dụng: python -m src.remediation.srt_validator <file.srt>"))
        return 1
    v = SrtValidator(auto_fix=False)
    rep = v.validate(sys.argv[1])
    print(f"Segments: {rep.segment_count}, fatal: {rep.is_fatal}")
    for i in rep.issues:
        line = f"  [{i.severity}] {i.code}: {i.message}"
        print(warn(line) if i.severity == "warn" else err(line))
    return 0 if rep.is_recoverable and not rep.has_errors() else 1


if __name__ == "__main__":
    raise SystemExit(_cli())
