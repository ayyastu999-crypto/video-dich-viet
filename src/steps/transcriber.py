from pathlib import Path

from src.steps.base import BaseStep
from src.utils.srt import write_srt
from src.utils.timestamp import seconds_to_srt


class Transcriber(BaseStep):
    def __init__(self, config: dict, work_dir: Path):
        super().__init__(config, work_dir)
        self._model = None

    def _get_model(self):
        from src.utils.model_cache import model_cache
        from src.utils.device import pick_device, pick_compute_type, describe

        stt_cfg = self.config["stt"]
        # Tu do phan cung thay vi tin cau hinh: config dat cuda/float16 ma may
        # khong co NVIDIA thi vo ngay o buoc nay.
        device = pick_device(stt_cfg.get("device", "auto"))
        compute = pick_compute_type(device, stt_cfg.get("compute_type", "auto"))
        self.log(f"May: {describe()} -> chay {device}/{compute}")
        return model_cache.get_whisper(stt_cfg["model"], device, compute)

    def run(self, video_path: Path) -> dict:
        model = self._get_model()
        stt_cfg = self.config["stt"]

        self.log(f"Transcribing: {video_path.name}")

        segments, info = model.transcribe(
            str(video_path),
            language=stt_cfg.get("language", "zh"),
            vad_filter=stt_cfg.get("vad_filter", True),
            vad_parameters=dict(
                min_silence_duration_ms=stt_cfg.get("vad_min_silence_ms", 500)
            ),
        )

        srt_segments = []
        for seg in segments:
            srt_segments.append({
                "start": seg.start,
                "end": seg.end,
                "text": seg.text.strip(),
            })

        srt_dir = self.ensure_dir("srt")
        srt_path = srt_dir / f"{video_path.stem}_original.srt"
        write_srt(srt_segments, str(srt_path))

        self.log(f"Transcribed {len(srt_segments)} segments -> {srt_path.name}")
        return {
            "srt_path": srt_path,
            "language": info.language,
            "segments_count": len(srt_segments),
        }
