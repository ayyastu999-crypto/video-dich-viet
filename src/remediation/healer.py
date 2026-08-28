"""
PipelineHealer — orchestrator chính cho hệ thống tự phục hồi.

Trách nhiệm:
    - Quét workspace định kỳ (configurable interval) hoặc on-demand
    - Phát hiện vấn đề qua 5 hệ thống con
    - Tự sửa những gì có thể sửa (SRT timing, translation re-run, resume jobs)
    - Ghi log đầy đủ vào workspace/logs/healer.log
    - Reconciliation: source == fixed + quarantined (zero-data-loss invariant)

API:
    healer = PipelineHealer(config, work_dir)
    report = healer.scan()
    healer.heal_all()
    healer.heal_video(video_id)
    print(healer.get_status_report())
    healer.start_loop(interval=300)   # tuỳ chọn: chạy nền
"""
from __future__ import annotations

import json
import threading
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

from src.remediation._common import (
    audit, get_logger, ok, warn, err, info, head, colour, C, utc_now_iso,
)
from src.remediation.pipeline_inspector import (
    PipelineInspector, WorkspaceReport, render_state_brief, STEP_ORDER,
)
from src.remediation.srt_validator import SrtValidator
from src.remediation.translation_qc import TranslationQC
from src.remediation.media_validator import MediaValidator
from src.remediation.recovery import RecoveryManager, RecoveryResult


@dataclass
class HealReport:
    """Báo cáo tổng hợp 1 lần scan/heal."""
    timestamp: str
    target_lang: str
    workspace: str

    total_videos: int = 0
    completed: int = 0
    stuck: int = 0
    resumable: int = 0
    orphans: int = 0

    srt_issues: dict[str, int] = field(default_factory=dict)
    translation_issues: dict[str, int] = field(default_factory=dict)
    media_issues: dict[str, int] = field(default_factory=dict)

    fixed_count: int = 0
    quarantined_count: int = 0
    recovery_results: list[dict] = field(default_factory=list)

    inspector_report: dict | None = None

    # Reconciliation invariant: source_count == success_count + quarantined_count + in_flight
    source_count: int = 0
    success_count: int = 0
    in_flight_count: int = 0
    reconciliation_ok: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class PipelineHealer:
    """Trình điều phối tự phục hồi pipeline."""

    def __init__(
        self,
        config: dict | None = None,
        work_dir: Path | str | None = None,
        target_lang: str = "vi",
    ):
        self.config = config or {}
        self.work_dir = Path(work_dir) if work_dir else Path("workspace")
        self.target_lang = target_lang
        self.logger = get_logger("healer", self.work_dir)

        self.inspector = PipelineInspector(self.work_dir, target_lang)
        self.srt_validator = SrtValidator(self.work_dir, auto_fix=True)
        self.translation_qc = TranslationQC(self.config, self.work_dir)
        self.media_validator = MediaValidator(self.work_dir)
        self.recovery = RecoveryManager(self.config, self.work_dir, target_lang)

        self._loop_thread: threading.Thread | None = None
        self._loop_stop = threading.Event()
        self._last_report: HealReport | None = None

    # ==================================================================
    # Public API
    # ==================================================================
    def scan(self) -> HealReport:
        """Quét workspace, không sửa gì - chỉ phát hiện."""
        self.logger.info("=== SCAN bắt đầu ===")
        report = HealReport(
            timestamp=utc_now_iso(),
            target_lang=self.target_lang,
            workspace=str(self.work_dir),
        )

        ws = self.inspector.scan()
        report.inspector_report = ws.to_dict()
        report.total_videos = len(ws.videos)
        report.completed = len(ws.completed_ids)
        report.stuck = len(ws.stuck_ids)
        report.resumable = len(ws.resumable_ids)
        report.orphans = len(ws.orphans)
        report.source_count = report.total_videos

        # Quét chi tiết SRT / translation / media cho mỗi video
        for vid, state in ws.videos.items():
            self._scan_video_details(vid, state, report)

        self._last_report = report
        self.logger.info(
            f"SCAN kết thúc: {report.total_videos} video "
            f"(complete={report.completed}, stuck={report.stuck}, "
            f"resumable={report.resumable}, orphans={report.orphans})"
        )
        return report

    def heal_all(self) -> HealReport:
        """Quét + tự sửa tất cả vấn đề có thể sửa."""
        self.logger.info("=== HEAL ALL bắt đầu ===")
        report = self.scan()

        # 1. Sửa SRT trước (auto-fix đã chạy trong scan; chỉ đếm lại)
        # 2. Sửa translation
        for vid, state in self.inspector.scan().videos.items():
            self._heal_translation_for(vid, report)

        # 3. Resume các video chưa hoàn tất
        for vid, state in self.inspector.scan().videos.items():
            if state.is_complete:
                report.success_count += 1
                continue
            if state.is_stuck:
                # Stuck job: thử recovery
                rr = self.recovery.recover_video(vid)
                report.recovery_results.append(rr.to_dict())
                if rr.final_status == "success":
                    report.success_count += 1
                    report.fixed_count += 1
                elif rr.quarantined:
                    report.quarantined_count += 1
            elif state.is_resumable:
                rr = self.recovery.recover_video(vid)
                report.recovery_results.append(rr.to_dict())
                if rr.final_status == "success":
                    report.success_count += 1
                    report.fixed_count += 1
                elif rr.quarantined:
                    report.quarantined_count += 1
            else:
                # Không complete, không resumable, không stuck -> quarantine
                report.quarantined_count += 1

        report.success_count = max(report.success_count,
                                   len(self.inspector.scan().completed_ids))
        self._reconcile(report)

        self._last_report = report
        self.logger.info(
            f"HEAL ALL kết thúc: fixed={report.fixed_count}, "
            f"quarantined={report.quarantined_count}, "
            f"reconciliation={'OK' if report.reconciliation_ok else 'FAIL'}"
        )
        return report

    def heal_video(self, video_id: str, force_step: str | None = None) -> RecoveryResult:
        """Sửa 1 video cụ thể."""
        self.logger.info(f"=== HEAL VIDEO {video_id} (force={force_step}) ===")
        # Validate + auto-fix SRT trước
        srt_orig = self.work_dir / "srt" / f"{video_id}_original.srt"
        srt_trans = self.work_dir / "srt" / f"{video_id}_{self.target_lang}.srt"
        if srt_orig.exists():
            self.srt_validator.validate(srt_orig)
        if srt_orig.exists() and srt_trans.exists():
            qc = self.translation_qc.validate(srt_orig, srt_trans, self.target_lang)
            if qc.bad_segments:
                self.translation_qc.repair(qc, self.target_lang)
        # Resume
        return self.recovery.recover_video(video_id, force_step=force_step)

    def get_status_report(self) -> str:
        """Trả về báo cáo dạng text (Vietnamese, có màu) để in ra console."""
        if self._last_report is None:
            self.scan()
        rep = self._last_report
        return self._format_report(rep)

    # ==================================================================
    # Background loop
    # ==================================================================
    def start_loop(self, interval: int = 300, auto_heal: bool = False) -> None:
        """Chạy quét định kỳ ở luồng nền (interval giây)."""
        if self._loop_thread and self._loop_thread.is_alive():
            self.logger.warning("Loop đã chạy - bỏ qua start mới")
            return
        self._loop_stop.clear()

        def _run():
            while not self._loop_stop.is_set():
                try:
                    if auto_heal:
                        self.heal_all()
                    else:
                        self.scan()
                except Exception as e:
                    self.logger.exception(f"Loop iteration crash: {e}")
                self._loop_stop.wait(interval)

        self._loop_thread = threading.Thread(
            target=_run, name="PipelineHealerLoop", daemon=True
        )
        self._loop_thread.start()
        self.logger.info(f"Loop đã khởi động (interval={interval}s, auto_heal={auto_heal})")

    def stop_loop(self) -> None:
        self._loop_stop.set()
        if self._loop_thread:
            self._loop_thread.join(timeout=5)
        self.logger.info("Loop đã dừng")

    # ==================================================================
    # Internal helpers
    # ==================================================================
    def _scan_video_details(self, vid: str, state, report: HealReport) -> None:
        """Chạy SRT/translation/media checks cho 1 video, gộp đếm vào report."""
        # Media (download)
        if state.download_path:
            mr = self.media_validator.validate(state.download_path, check_silence=False)
            for issue in mr.issues:
                report.media_issues[issue.code] = report.media_issues.get(issue.code, 0) + 1

        # SRT original
        srt_orig = self.work_dir / "srt" / f"{vid}_original.srt"
        if srt_orig.exists():
            sr = self.srt_validator.validate(srt_orig)
            for issue in sr.issues:
                report.srt_issues[issue.code] = report.srt_issues.get(issue.code, 0) + 1
                if issue.fixed:
                    report.fixed_count += 1

        # SRT translated + QC
        srt_trans = self.work_dir / "srt" / f"{vid}_{self.target_lang}.srt"
        if srt_orig.exists() and srt_trans.exists():
            tr = self.translation_qc.validate(srt_orig, srt_trans, self.target_lang)
            for issue in tr.issues:
                report.translation_issues[issue.code] = (
                    report.translation_issues.get(issue.code, 0) + 1
                )

    def _heal_translation_for(self, vid: str, report: HealReport) -> None:
        srt_orig = self.work_dir / "srt" / f"{vid}_original.srt"
        srt_trans = self.work_dir / "srt" / f"{vid}_{self.target_lang}.srt"
        if not (srt_orig.exists() and srt_trans.exists()):
            return
        tr = self.translation_qc.validate(srt_orig, srt_trans, self.target_lang)
        if tr.bad_segments and tr.is_recoverable:
            try:
                self.translation_qc.repair(tr, self.target_lang)
                report.fixed_count += 1
            except Exception as e:
                self.logger.error(f"Repair translation {vid} thất bại: {e}")

    def _reconcile(self, report: HealReport) -> None:
        """Bất biến: source == success + quarantined + in_flight. Lệch -> Sev-1."""
        ws = self.inspector.scan()
        report.source_count = len(ws.videos)
        report.success_count = len(ws.completed_ids)
        report.in_flight_count = len(ws.resumable_ids) + len(ws.stuck_ids)

        accounted = (report.success_count
                     + report.quarantined_count
                     + report.in_flight_count)

        if accounted < report.source_count:
            missing = report.source_count - accounted
            report.reconciliation_ok = False
            self.logger.error(
                f"!!! SEV-1 RECONCILIATION FAIL: thiếu {missing} video không tìm thấy. "
                f"source={report.source_count}, success={report.success_count}, "
                f"quarantined={report.quarantined_count}, in_flight={report.in_flight_count}"
            )
            audit("reconciliation_fail", {
                "missing": missing,
                "source": report.source_count,
                "success": report.success_count,
                "quarantined": report.quarantined_count,
                "in_flight": report.in_flight_count,
            }, self.work_dir)
        else:
            report.reconciliation_ok = True

    # ------------------------------------------------------------------
    def _format_report(self, rep: HealReport) -> str:
        if rep is None:
            return err("Không có báo cáo - hãy gọi scan() trước")

        lines: list[str] = []
        lines.append(head("=" * 64))
        lines.append(head(" BÁO CÁO TỰ PHỤC HỒI PIPELINE DOUYIN "))
        lines.append(head("=" * 64))
        lines.append(f"  Thời gian:      {rep.timestamp}")
        lines.append(f"  Workspace:      {rep.workspace}")
        lines.append(f"  Ngôn ngữ đích:  {rep.target_lang}")
        lines.append("")

        # Tổng quan
        lines.append(head("[ TỔNG QUAN ]"))
        lines.append(f"  Tổng số video:        {rep.total_videos}")
        lines.append(f"  {colour('Hoàn tất:', C.GREEN)}             {rep.completed}")
        lines.append(f"  {colour('Có thể tiếp tục:', C.CYAN)}      {rep.resumable}")
        lines.append(f"  {colour('Bị treo:', C.YELLOW)}              {rep.stuck}")
        lines.append(f"  {colour('File mồ côi:', C.MAGENTA)}          {rep.orphans}")
        lines.append("")

        # SRT
        if rep.srt_issues:
            lines.append(head("[ SRT - Chất lượng phụ đề ]"))
            for code, n in sorted(rep.srt_issues.items()):
                lines.append(f"  {warn(code):42s} x {n}")
            lines.append("")

        # Translation
        if rep.translation_issues:
            lines.append(head("[ TRANSLATION - Bản dịch ]"))
            for code, n in sorted(rep.translation_issues.items()):
                lines.append(f"  {warn(code):42s} x {n}")
            lines.append("")

        # Media
        if rep.media_issues:
            lines.append(head("[ MEDIA - File video/audio ]"))
            for code, n in sorted(rep.media_issues.items()):
                lines.append(f"  {warn(code):42s} x {n}")
            lines.append("")

        # Per-video brief
        if rep.inspector_report and rep.inspector_report.get("videos"):
            lines.append(head("[ TRẠNG THÁI TỪNG VIDEO ]"))
            lines.append(colour(
                f"  Ký hiệu: ● hoàn tất  ◯ chưa  ! treo  … đang chạy  ? unknown",
                C.GREY,
            ))
            lines.append(colour(
                f"  Thứ tự bước: {' '.join(STEP_ORDER)}",
                C.GREY,
            ))
            from src.remediation.pipeline_inspector import VideoState, StepStatus
            for vid, vstate_dict in list(rep.inspector_report["videos"].items())[:50]:
                try:
                    vstate = VideoState(
                        video_id=vstate_dict["video_id"],
                        target_lang=vstate_dict.get("target_lang", "vi"),
                    )
                    vstate.steps = {
                        k: StepStatus(**v) for k, v in vstate_dict.get("steps", {}).items()
                    }
                    vstate.is_complete = vstate_dict.get("is_complete", False)
                    vstate.is_stuck = vstate_dict.get("is_stuck", False)
                    vstate.is_resumable = vstate_dict.get("is_resumable", False)
                except Exception:
                    continue
                badge = (colour(" OK  ", C.GREEN) if vstate.is_complete
                         else colour("STUCK", C.RED) if vstate.is_stuck
                         else colour("RESUM", C.CYAN) if vstate.is_resumable
                         else colour("WAIT ", C.YELLOW))
                lines.append(f"  {vid:24s}  [{render_state_brief(vstate)}]  {badge}")
            if len(rep.inspector_report["videos"]) > 50:
                lines.append(colour(f"  ... và {len(rep.inspector_report['videos']) - 50} video khác", C.GREY))
            lines.append("")

        # Healing summary
        lines.append(head("[ KẾT QUẢ TỰ SỬA ]"))
        lines.append(f"  Đã sửa tự động:   {colour(str(rep.fixed_count), C.GREEN)}")
        lines.append(f"  Cách ly:          {colour(str(rep.quarantined_count), C.YELLOW)}")
        lines.append("")

        # Reconciliation
        recon_label = ok("ĐẠT") if rep.reconciliation_ok else err("LỆCH - SEV-1!")
        lines.append(head("[ RECONCILIATION (Bất biến không-mất-dữ-liệu) ]"))
        lines.append(
            f"  source({rep.source_count}) == success({rep.success_count}) + "
            f"quarantined({rep.quarantined_count}) + in_flight({rep.in_flight_count})  "
            f"=>  {recon_label}"
        )
        lines.append("")
        lines.append(head("=" * 64))

        return "\n".join(lines)
