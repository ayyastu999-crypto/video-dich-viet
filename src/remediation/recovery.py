"""
Failed Video Recovery — khôi phục video bị lỗi/treo bằng cách chạy tiếp từ
bước cuối cùng đã hoàn tất.

Triết lý:
    - Không bao giờ chạy lại bước đã hoàn tất (trừ khi force).
    - Trước khi dùng output của bước trước, validate lại.
    - Mỗi lần thử khôi phục đều ghi log đầy đủ.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

from src.remediation._common import audit, get_logger, ok, warn, err, info
from src.remediation.pipeline_inspector import (
    PipelineInspector, VideoState, STEP_ORDER,
)
from src.remediation.srt_validator import SrtValidator
from src.remediation.media_validator import MediaValidator
from src.remediation.translation_qc import TranslationQC


@dataclass
class StepAttempt:
    step: str
    started_at: str
    finished_at: str | None = None
    success: bool = False
    error: str | None = None
    artifact: str | None = None


@dataclass
class RecoveryResult:
    video_id: str
    target_lang: str
    initial_state: dict | None = None
    attempts: list[StepAttempt] = field(default_factory=list)
    final_status: str = "unknown"   # "success" | "partial" | "failed" | "skipped"
    quarantined: bool = False
    quarantine_reason: str | None = None
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class RecoveryManager:
    """Quản lý phục hồi 1 hoặc nhiều video."""

    def __init__(
        self,
        config: dict | None = None,
        work_dir: Path | str | None = None,
        target_lang: str = "vi",
    ):
        self.config = config or {}
        self.work_dir = Path(work_dir) if work_dir else Path("workspace")
        self.target_lang = target_lang
        self.logger = get_logger("recovery", self.work_dir)
        self.inspector = PipelineInspector(self.work_dir, target_lang)
        self.srt_validator = SrtValidator(self.work_dir, auto_fix=True)
        self.media_validator = MediaValidator(self.work_dir)
        self.translation_qc = TranslationQC(self.config, self.work_dir)

    # ------------------------------------------------------------------
    def recover_all(self, force_step: str | None = None) -> list[RecoveryResult]:
        report = self.inspector.scan()
        results: list[RecoveryResult] = []
        for vid, state in report.videos.items():
            if state.is_complete and not force_step:
                continue
            results.append(self.recover_video(vid, force_step=force_step))
        return results

    # ------------------------------------------------------------------
    def recover_video(
        self,
        video_id: str,
        force_step: str | None = None,
    ) -> RecoveryResult:
        """Phục hồi 1 video. force_step: bỏ qua check completed của bước đó."""
        state = self.inspector._inspect_video(video_id)
        result = RecoveryResult(
            video_id=video_id,
            target_lang=self.target_lang,
            initial_state=state.to_dict(),
        )

        # Pre-validate: video gốc tồn tại?
        if not state.download_path:
            result.final_status = "failed"
            result.notes.append("Không có file download - cần chạy lại từ đầu")
            self._quarantine(result, "missing_download")
            return result

        media_rep = self.media_validator.validate(state.download_path, check_silence=False)
        if not media_rep.safe_to_process:
            result.final_status = "skipped"
            result.notes.append(
                f"Video gốc không hợp lệ: {[i.message for i in media_rep.issues if i.severity == 'fatal']}"
            )
            self._quarantine(result, "invalid_source_media")
            return result

        # Xác định danh sách bước cần chạy
        if force_step:
            if force_step not in STEP_ORDER:
                result.final_status = "failed"
                result.notes.append(f"Bước không hợp lệ: {force_step}")
                return result
            steps_to_run = STEP_ORDER[STEP_ORDER.index(force_step):]
        else:
            if state.is_complete:
                result.final_status = "success"
                result.notes.append("Tất cả bước đã hoàn tất")
                return result
            if not state.next_step:
                result.final_status = "success"
                return result
            steps_to_run = STEP_ORDER[STEP_ORDER.index(state.next_step):]

        # Loại upload (không thể tự khôi phục an toàn từ đây)
        steps_to_run = [s for s in steps_to_run if s != "upload"]

        # Chạy tuần tự
        try:
            self._run_steps(state, steps_to_run, result)
        except Exception as e:
            self.logger.exception(f"Recovery {video_id} crash: {e}")
            result.final_status = "failed"
            result.notes.append(f"Crash: {e!s}")
            self._quarantine(result, f"crash:{e!s}")
            return result

        # Đánh giá kết quả
        post_state = self.inspector._inspect_video(video_id)
        if post_state.is_complete:
            result.final_status = "success"
        elif post_state.last_completed_step != state.last_completed_step:
            result.final_status = "partial"
        else:
            result.final_status = "failed"
            self._quarantine(result, "no_progress")

        audit("recovery_attempt", {
            "video_id": video_id,
            "status": result.final_status,
            "attempts": len(result.attempts),
            "quarantined": result.quarantined,
        }, self.work_dir)

        return result

    # ------------------------------------------------------------------
    def _run_steps(
        self,
        state: VideoState,
        steps: list[str],
        result: RecoveryResult,
    ) -> None:
        """Chạy tuần tự các bước, gọi step thật từ src.steps.*"""
        from src.steps.transcriber import Transcriber
        from src.steps.translator import Translator
        from src.steps.tts import TTSGenerator
        from src.steps.caption_detector import CaptionDetector
        from src.steps.caption_blur import CaptionBlur
        from src.steps.caption_writer import CaptionWriter
        from src.steps.audio_separator import AudioSeparator
        from src.steps.audio_mixer import AudioMixer
        from src.steps.composer import Composer
        from src.remediation._common import utc_now_iso

        cfg = self.config
        wd = self.work_dir
        vid = state.video_id
        lang = self.target_lang
        video_path = Path(state.download_path)

        # Chuẩn bị các artifact đã có (đường dẫn dự đoán)
        srt_original = wd / "srt" / f"{vid}_original.srt"
        srt_translated = wd / "srt" / f"{vid}_{lang}.srt"
        sep_dir = wd / "separated" / "htdemucs" / vid
        vocals = sep_dir / "vocals.wav"
        instrumental = sep_dir / "no_vocals.wav"
        blurred = wd / "output" / f"{vid}_blurred.mp4"
        captioned = wd / "output" / f"{vid}_blurred_captioned.mp4"

        # State trung gian (giữ thông tin giữa các step)
        runtime: dict[str, Any] = {}

        for step in steps:
            attempt = StepAttempt(step=step, started_at=utc_now_iso())
            result.attempts.append(attempt)
            self.logger.info(f"[{vid}] -> chạy bước: {step}")

            try:
                if step == "download":
                    attempt.success = video_path.exists()
                    attempt.artifact = str(video_path)

                elif step == "stt":
                    Transcriber(cfg, wd).run(video_path=video_path)
                    rep = self.srt_validator.validate(srt_original)
                    if rep.is_fatal:
                        raise RuntimeError(f"STT cho ra SRT không dùng được: {rep.issues[0].message}")
                    attempt.artifact = str(srt_original)
                    attempt.success = True

                elif step == "audio_separate":
                    AudioSeparator(cfg, wd).run(video_path=video_path)
                    if not (vocals.exists() and instrumental.exists()):
                        raise RuntimeError("Audio separator không tạo đủ file")
                    attempt.artifact = str(instrumental)
                    attempt.success = True

                elif step == "translate":
                    # Pre-validate SRT gốc
                    rep = self.srt_validator.validate(srt_original)
                    if rep.is_fatal:
                        raise RuntimeError(f"SRT gốc không hợp lệ: {rep.issues[0].message}")
                    Translator(cfg, wd).run(srt_path=srt_original, target_lang=lang)
                    # QC bản dịch + auto-repair
                    qc = self.translation_qc.validate(srt_original, srt_translated, lang)
                    if qc.bad_segments:
                        self.translation_qc.repair(qc, lang)
                    attempt.artifact = str(srt_translated)
                    attempt.success = True

                elif step == "tts":
                    provider = cfg.get("tts", {}).get("provider", "edge-tts")
                    if provider == "voice-clone":
                        from src.steps.tts_clone import TTSCloneGenerator
                        tts_res = TTSCloneGenerator(cfg, wd).run(
                            translated_srt=srt_translated,
                            original_srt=srt_original,
                            vocals_path=vocals,
                            target_lang=lang,
                        )
                    else:
                        tts_res = asyncio.run(
                            TTSGenerator(cfg, wd).run(
                                translated_srt=srt_translated, target_lang=lang
                            )
                        )
                    runtime["tts_audio"] = tts_res["tts_audio"]
                    attempt.artifact = str(tts_res["tts_audio"])
                    attempt.success = True

                elif step == "caption_detect":
                    det = CaptionDetector(cfg, wd).run(video_path=video_path)
                    runtime["caption_region"] = det["caption_region"]
                    runtime["detections"] = det.get("detections")
                    attempt.success = True

                elif step == "caption_blur":
                    region = runtime.get("caption_region")
                    if region is None:
                        # phải chạy detect trước
                        det = CaptionDetector(cfg, wd).run(video_path=video_path)
                        region = det["caption_region"]
                        runtime["caption_region"] = region
                        runtime["detections"] = det.get("detections")
                    CaptionBlur(cfg, wd).run(
                        video_path=video_path,
                        caption_region=region,
                        detections=runtime.get("detections"),
                    )
                    attempt.artifact = str(blurred)
                    attempt.success = blurred.exists()

                elif step == "caption_write":
                    region = runtime.get("caption_region")
                    if region is None:
                        det = CaptionDetector(cfg, wd).run(video_path=video_path)
                        region = det["caption_region"]
                    CaptionWriter(cfg, wd).run(
                        video_path=blurred,
                        translated_srt=srt_translated,
                        caption_region=region,
                    )
                    attempt.artifact = str(captioned)
                    attempt.success = captioned.exists()

                elif step == "audio_mix":
                    tts_audio = runtime.get("tts_audio")
                    if tts_audio is None:
                        # lấy từ thư mục tts dự đoán
                        cand = list((wd / "tts").glob(f"{vid}*"))
                        if not cand:
                            raise RuntimeError("Không tìm thấy TTS audio để mix")
                        tts_audio = cand[0]
                    AudioMixer(cfg, wd).run(
                        tts_audio=tts_audio, instrumental=instrumental
                    )
                    attempt.success = True

                elif step == "compose":
                    logo_path = Path("assets/logo.png")
                    composer = Composer(cfg, wd)
                    mixed = wd / "output" / "mixed_audio.wav"
                    if not mixed.exists():
                        # mixer có thể đã đổi tên
                        cand = list((wd / "output").glob("*mixed*"))
                        if cand:
                            mixed = cand[0]
                    composer.run(
                        captioned_video=captioned,
                        mixed_audio=mixed,
                        logo=logo_path if logo_path.exists() else None,
                    )
                    attempt.success = True

                else:
                    attempt.success = False
                    attempt.error = f"Bước không nhận diện: {step}"

            except Exception as e:
                attempt.success = False
                attempt.error = str(e)
                attempt.finished_at = utc_now_iso()
                self.logger.error(f"[{vid}] {step} lỗi: {e}")
                # Dừng dây chuyền - các bước sau phụ thuộc bước này
                break

            attempt.finished_at = utc_now_iso()

    # ------------------------------------------------------------------
    def _quarantine(self, result: RecoveryResult, reason: str) -> None:
        from src.remediation._common import quarantine_dir
        import json as _json

        result.quarantined = True
        result.quarantine_reason = reason
        qdir = quarantine_dir(self.work_dir)
        qfile = qdir / f"{result.video_id}_recovery.json"
        with qfile.open("w", encoding="utf-8") as f:
            _json.dump(result.to_dict(), f, ensure_ascii=False, indent=2)
        self.logger.warning(f"Quarantine {result.video_id}: {reason} -> {qfile}")
