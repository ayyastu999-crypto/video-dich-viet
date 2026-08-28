"""
Background worker that runs pipeline jobs with progress reporting.
"""
import asyncio
import threading
import traceback
from pathlib import Path
from queue import Queue

from src.config import load_config
from src.web.state import AppState, JobStatus, StepName


class PipelineWorker:
    """Runs pipeline jobs in a background thread with step-by-step progress."""

    def __init__(self, config_path: str = "config/default.yaml"):
        self.config = load_config(config_path)
        self.state = AppState()
        self.work_dir = Path("workspace")
        self._queue: Queue = Queue()
        self._thread: threading.Thread = None
        self._running = False
        self._ensure_dirs()

    def _ensure_dirs(self):
        for subdir in ["downloads", "srt", "tts", "separated", "output", "logs"]:
            (self.work_dir / subdir).mkdir(parents=True, exist_ok=True)

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._worker_loop, daemon=True)
        self._thread.start()
        # Pre-warm models in background (saves 10-15s on first video)
        threading.Thread(target=self._prewarm_models, daemon=True).start()

    def _prewarm_models(self):
        """Pre-load heavy models so first video starts fast."""
        try:
            from src.utils.model_cache import model_cache
            stt = self.config.get("stt", {})
            model_cache.get_whisper(
                stt.get("model", "large-v3"),
                stt.get("device", "cuda"),
                stt.get("compute_type", "float16"),
            )
            model_cache.get_easyocr(["ch_sim", "en"], gpu=True)
            model_cache.get_demucs(
                self.config.get("audio", {}).get("separation_model", "htdemucs"),
                device="cuda",
            )
            print("[Worker] Models pre-warmed (STT + OCR + Demucs ready)")
        except Exception as e:
            print(f"[Worker] Pre-warm failed (non-critical): {e}")

    def stop(self):
        self._running = False
        self._queue.put(None)  # Poison pill

    def enqueue(self, job_id: str):
        self._queue.put(job_id)

    def _worker_loop(self):
        while self._running:
            job_id = self._queue.get()
            if job_id is None:
                break
            try:
                self._run_job(job_id)
            except Exception as e:
                self.state.fail_job(job_id, str(e))
                traceback.print_exc()

    def _run_job(self, job_id: str):
        job = self.state.get_job(job_id)
        if not job:
            return

        self.state.start_job(job_id)
        url = job.url
        target_lang = job.target_lang

        try:
            # Step 1: Download
            self._update(job_id, StepName.DOWNLOAD, JobStatus.RUNNING, 0, "Đang tải video...")
            from src.steps.downloader import Downloader
            dl = Downloader(self.config, self.work_dir)
            dl_result = dl.run(url=url)
            video_path = dl_result["video_path"]
            job.video_path = str(video_path)
            job.metadata = dl_result.get("metadata", {})
            self._update(job_id, StepName.DOWNLOAD, JobStatus.COMPLETED, 100, "Hoàn tất")

            # Step 2: STT
            self._update(job_id, StepName.STT, JobStatus.RUNNING, 0, "Nhận dạng giọng nói...")
            from src.steps.transcriber import Transcriber
            transcriber = Transcriber(self.config, self.work_dir)
            stt_result = transcriber.run(video_path=video_path)
            srt_path = stt_result["srt_path"]
            job.srt_original = str(srt_path)
            self._update(job_id, StepName.STT, JobStatus.COMPLETED, 100,
                         f"{stt_result['segments_count']} đoạn")

            # Step 8 (parallel with translate): Audio separation
            self._update(job_id, StepName.AUDIO_SEPARATE, JobStatus.RUNNING, 0, "Tách nhạc nền...")
            from src.steps.audio_separator import AudioSeparator
            separator = AudioSeparator(self.config, self.work_dir)
            sep_result = separator.run(video_path=video_path)
            instrumental = sep_result["instrumental"]
            self._update(job_id, StepName.AUDIO_SEPARATE, JobStatus.COMPLETED, 100, "Hoàn tất")

            # Step 3: Translate
            self._update(job_id, StepName.TRANSLATE, JobStatus.RUNNING, 0, "Dịch phụ đề...")
            from src.steps.translator import Translator
            translator = Translator(self.config, self.work_dir)
            trans_result = translator.run(srt_path=srt_path, target_lang=target_lang)
            translated_srt = trans_result["translated_srt"]
            job.srt_translated = str(translated_srt)
            self._update(job_id, StepName.TRANSLATE, JobStatus.COMPLETED, 100, "Hoàn tất")

            # Step 4: TTS
            self._update(job_id, StepName.TTS, JobStatus.RUNNING, 0, "Tạo giọng đọc...")
            from src.steps.tts import TTSGenerator
            tts = TTSGenerator(self.config, self.work_dir)
            tts_result = asyncio.run(
                tts.run(translated_srt=translated_srt, target_lang=target_lang)
            )
            tts_audio = tts_result["tts_audio"]
            self._update(job_id, StepName.TTS, JobStatus.COMPLETED, 100, "Hoàn tất")

            # Step 5: Detect captions
            self._update(job_id, StepName.CAPTION_DETECT, JobStatus.RUNNING, 0,
                         "Phát hiện phụ đề cũ...")
            from src.steps.caption_detector import CaptionDetector
            detector = CaptionDetector(self.config, self.work_dir)
            detect_result = detector.run(video_path=video_path)
            caption_region = detect_result["caption_region"]
            self._update(job_id, StepName.CAPTION_DETECT, JobStatus.COMPLETED, 100, "Hoàn tất")

            # Step 6: Blur
            self._update(job_id, StepName.CAPTION_BLUR, JobStatus.RUNNING, 0,
                         "Xóa phụ đề cũ...")
            from src.steps.caption_blur import CaptionBlur
            blur = CaptionBlur(self.config, self.work_dir)
            blur_result = blur.run(video_path=video_path, caption_region=caption_region)
            blurred_video = blur_result["blurred_video"]
            self._update(job_id, StepName.CAPTION_BLUR, JobStatus.COMPLETED, 100, "Hoàn tất")

            # Step 7: Write new captions
            self._update(job_id, StepName.CAPTION_WRITE, JobStatus.RUNNING, 0,
                         "Thêm phụ đề mới...")
            from src.steps.caption_writer import CaptionWriter
            writer = CaptionWriter(self.config, self.work_dir)
            cap_result = writer.run(video_path=blurred_video, translated_srt=translated_srt)
            captioned_video = cap_result["captioned_video"]
            self._update(job_id, StepName.CAPTION_WRITE, JobStatus.COMPLETED, 100, "Hoàn tất")

            # Step 9: Mix audio
            self._update(job_id, StepName.AUDIO_MIX, JobStatus.RUNNING, 0, "Trộn âm thanh...")
            from src.steps.audio_mixer import AudioMixer
            mixer = AudioMixer(self.config, self.work_dir)
            mix_result = mixer.run(tts_audio=tts_audio, instrumental=instrumental)
            mixed_audio = mix_result["mixed_audio"]
            self._update(job_id, StepName.AUDIO_MIX, JobStatus.COMPLETED, 100, "Hoàn tất")

            # Step 10: Compose
            self._update(job_id, StepName.COMPOSE, JobStatus.RUNNING, 0, "Ghép video cuối...")
            from src.steps.composer import Composer
            logo_path = Path("assets/logo.png")
            composer = Composer(self.config, self.work_dir)
            final_result = composer.run(
                captioned_video=captioned_video,
                mixed_audio=mixed_audio,
                logo=logo_path if logo_path.exists() else None,
            )
            final_video = final_result["final_video"]
            self._update(job_id, StepName.COMPOSE, JobStatus.COMPLETED, 100, "Hoàn tất")

            # Step 11: Upload
            platforms = self.config.get("upload", {}).get("platforms", [])
            if platforms:
                self._update(job_id, StepName.UPLOAD, JobStatus.RUNNING, 0, "Upload...")
                from src.steps.uploader import Uploader
                uploader = Uploader(self.config, self.work_dir)
                uploader.run(final_video=Path(final_video), metadata=job.metadata)
                self._update(job_id, StepName.UPLOAD, JobStatus.COMPLETED, 100, "Hoàn tất")
            else:
                self._update(job_id, StepName.UPLOAD, JobStatus.COMPLETED, 100, "Bỏ qua")

            self.state.complete_job(job_id, str(final_video))

        except Exception as e:
            self.state.fail_job(job_id, str(e))
            # Mark current running step as failed
            for step_name, sp in job.steps.items():
                if sp.status == JobStatus.RUNNING:
                    self._update(job_id, step_name, JobStatus.FAILED, sp.progress, str(e))
            raise

    def _update(self, job_id, step, status, progress, message):
        self.state.update_step(job_id, step, status, progress, message)
