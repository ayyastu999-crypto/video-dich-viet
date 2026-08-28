"""
Douyin Video Translation & Dubbing Pipeline

Main orchestrator that runs all steps in sequence with proper parallelization.
"""
import asyncio
from pathlib import Path
from datetime import datetime

from src.config import load_config
from src.steps.downloader import Downloader
from src.steps.local_source import LocalSource
from src.steps.transcriber import Transcriber
from src.steps.translator import Translator
from src.steps.tts import TTSGenerator
from src.steps.caption_detector import CaptionDetector
from src.steps.caption_blur import CaptionBlur
from src.steps.caption_writer import CaptionWriter
from src.steps.audio_separator import AudioSeparator
from src.steps.audio_mixer import AudioMixer
from src.steps.composer import Composer
from src.steps.script_export import ScriptExporter
from src.steps.collector import Collector
from src.steps.uploader import Uploader


class Pipeline:
    def __init__(self, config_path: str = "config/default.yaml"):
        self.config = load_config(config_path)
        self.work_dir = Path("workspace")
        self._ensure_dirs()

    def _ensure_dirs(self):
        for subdir in ["downloads", "srt", "tts", "separated", "output", "logs"]:
            (self.work_dir / subdir).mkdir(parents=True, exist_ok=True)

    def run(self, url: str = None, target_lang: str = "vi", local_video: str = None):
        """Chay full pipeline cho 1 video + 1 ngon ngu dich.

        Nguon vao chon 1 trong 2:
          - url:         tai ve tu Douyin
          - local_video: file video co san tren may
        """
        if not url and not local_video:
            raise ValueError("Can truyen url= hoac local_video=")

        steps_cfg = self.config.get("pipeline", {})
        self._log(f"Starting pipeline: {local_video or url} -> {target_lang}")

        # Step 1: Lay video (tai ve, hoac nap tu may)
        if local_video:
            dl_result = LocalSource(self.config, self.work_dir).run(path=local_video)
        else:
            dl_result = Downloader(self.config, self.work_dir).run(url=url)
        video_path = dl_result["video_path"]
        metadata = dl_result.get("metadata", {})
        self._log(f"Video san sang: {video_path}")

        # Warn for long videos
        try:
            import subprocess
            r = subprocess.run(
                ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
                 "-of", "csv=p=0", str(video_path)],
                capture_output=True, text=True, timeout=10,
            )
            duration = float(r.stdout.strip() or 0)
            if duration > 300:
                self._log(f"⚠ Video dài {duration:.0f}s (>5 phút) - xử lý chậm!")
            # Gioi han do dai chi ap cho video tai ve (tranh tai nham video dai).
            # File local do nguoi dung tu chon nen khong chan.
            if not local_video:
                max_dur = self.config.get("download", {}).get("max_duration_sec", 0)
                if max_dur > 0 and duration > max_dur:
                    raise RuntimeError(f"Video quá dài ({duration:.0f}s > {max_dur}s)")
        except (ValueError, subprocess.TimeoutExpired):
            pass

        # Step 2 + Step 8: STT and Audio separation (sequential due to GPU)
        transcriber = Transcriber(self.config, self.work_dir)
        stt_result = transcriber.run(video_path=video_path)
        srt_path = stt_result["srt_path"]
        self._log(f"Transcribed: {srt_path}")

        # Tach nhac nen khoi giong noi (Demucs). Tat di chay nhanh hon nhieu
        # va khong can torch/demucs.
        if steps_cfg.get("separate_audio", True):
            separator = AudioSeparator(self.config, self.work_dir)
            sep_result = separator.run(video_path=video_path)
            instrumental = sep_result["instrumental"]
            self._log(f"Audio separated: {instrumental}")
        else:
            # Khong tach: dung thang audio goc lam nen (ffmpeg doc duoc tu mp4)
            sep_result = {"instrumental": video_path, "vocals": video_path}
            instrumental = video_path
            self._log("Bo qua tach nhac nen - dung audio goc lam nen")

        # Step 3: Translate
        translator = Translator(self.config, self.work_dir)
        trans_result = translator.run(srt_path=srt_path, target_lang=target_lang)
        translated_srt = trans_result["translated_srt"]
        self._log(f"Translated: {translated_srt}")

        # Xuat kich ban ra text ngay sau khi dich, de du cac buoc render sau
        # co loi thi van co kich ban dung duoc.
        script_result = {}
        if steps_cfg.get("export_script", True):
            try:
                script_result = ScriptExporter(self.config, self.work_dir).run(
                    translated_srt=translated_srt,
                    original_srt=srt_path,
                    metadata=metadata,
                    target_lang=target_lang,
                )
            except Exception as e:
                self._log(f"Xuat kich ban that bai (bo qua): {e}")

        # Step 4: TTS (edge-tts or voice-clone).
        # Tat make_voice khi chi can phu de - bo qua ca TTS lan tron audio,
        # video cuoi giu nguyen tieng goc. Nhanh hon rat nhieu.
        make_voice = steps_cfg.get("make_voice", True)
        tts_audio = None
        tts_provider = self.config.get("tts", {}).get("provider", "edge-tts")
        if not make_voice:
            self._log("Bo qua long tieng - giu nguyen audio goc")
        elif tts_provider == "voice-clone":
            from src.steps.tts_clone import TTSCloneGenerator
            tts = TTSCloneGenerator(self.config, self.work_dir)
            tts_result = tts.run(
                translated_srt=translated_srt,
                original_srt=srt_path,
                vocals_path=sep_result["vocals"],
                target_lang=target_lang,
            )
        else:
            tts = TTSGenerator(self.config, self.work_dir)
            tts_result = asyncio.run(
                tts.run(translated_srt=translated_srt, target_lang=target_lang)
            )
        if make_voice:
            tts_audio = tts_result["tts_audio"]
            self._log(f"TTS generated: {tts_audio}")

        # Step 5+6: Do vi tri phu de cu roi lam mo di.
        # Chi can khi video nguon co phu de chay san. Tat di thi bo qua ca hai buoc,
        # dong thoi khong can paddleocr/opencv.
        if not steps_cfg.get("blur_old_captions", True):
            caption_region = None
            blurred_video = video_path
            self._log("Bo qua do va blur phu de cu (video khong co phu de chay san)")
        else:
            # Step 5: Detect captions (local or RevidAPI)
            revid_cfg = self.config.get("revid", {})
            use_revid = revid_cfg.get("enabled", False) and revid_cfg.get("api_key")
            revid_features = revid_cfg.get("use_for", [])

            if use_revid and "detect_caption" in revid_features:
                from src.steps.revid_api import RevidCaptionDetector
                detector = RevidCaptionDetector(self.config, self.work_dir)
                detect_result = detector.run(video_path=video_path)
            else:
                detector = CaptionDetector(self.config, self.work_dir)
                detect_result = detector.run(video_path=video_path)
            caption_region = detect_result["caption_region"]
            self._log(f"Caption region: {caption_region}")

            # Step 6: Blur old captions (time-based if detections available)
            blur = CaptionBlur(self.config, self.work_dir)
            blur_result = blur.run(
                video_path=video_path,
                caption_region=caption_region,
                detections=detect_result.get("detections"),
            )
            blurred_video = blur_result["blurred_video"]

        # Step 7: Add new captions at detected position
        writer = CaptionWriter(self.config, self.work_dir)
        cap_result = writer.run(
            video_path=blurred_video,
            translated_srt=translated_srt,
            caption_region=caption_region,
        )
        captioned_video = cap_result["captioned_video"]

        # Step 9: Mix audio (chi khi co giong doc moi de tron)
        if make_voice:
            mixer = AudioMixer(self.config, self.work_dir)
            mix_result = mixer.run(tts_audio=tts_audio, instrumental=instrumental)
            mixed_audio = mix_result["mixed_audio"]
        else:
            mixed_audio = video_path   # ffmpeg lay thang audio goc tu file video

        # Step 10: Final compose
        logo_path = Path("assets/logo.png")
        composer = Composer(self.config, self.work_dir)
        final_result = composer.run(
            captioned_video=captioned_video,
            mixed_audio=mixed_audio,
            logo=logo_path if logo_path.exists() else None,
        )
        final_video = final_result["final_video"]
        self._log(f"Final video: {final_video}")

        # Step 11: Upload (if configured)
        if self.config.get("upload", {}).get("platforms"):
            uploader = Uploader(self.config, self.work_dir)
            upload_result = uploader.run(final_video=final_video, metadata=metadata)
            self._log(f"Upload results: {upload_result}")

        # Gom moi thu vao output/<ten-video>/ cho de tim
        result = {"final_video": final_video,
                  "translated_srt": translated_srt,
                  "original_srt": srt_path,
                  "tts_audio": tts_audio,
                  **{k: v for k, v in script_result.items() if k.startswith("script_")}}
        try:
            gathered = Collector(self.config, self.work_dir).run(
                video_id=dl_result.get("video_id") or Path(video_path).stem,
                items=result,
                info={"title": metadata.get("title"),
                      "original_path": metadata.get("original_path"),
                      "duration": dl_result.get("duration"),
                      "engines": f"whisper {self.config['stt']['model']} + "
                                 f"{self.config['translation']['model']} + "
                                 f"{self.config['tts']['provider']}"},
            )
            result["project_dir"] = gathered["project_dir"]
        except Exception as e:
            self._log(f"Gom ket qua that bai (bo qua): {e}")

        self._log("Pipeline complete!")
        return result

    def run_batch(self, urls: list[str], target_langs: list[str]):
        """Process multiple videos x multiple languages."""
        results = []
        total = len(urls) * len(target_langs)
        done = 0
        for url in urls:
            for lang in target_langs:
                done += 1
                self._log(f"[{done}/{total}] Processing: {url} -> {lang}")
                try:
                    result = self.run(url=url, target_lang=lang)
                    results.append({"url": url, "lang": lang, "status": "success", **result})
                except Exception as e:
                    self._log(f"FAILED: {url} -> {lang}: {e}")
                    results.append({"url": url, "lang": lang, "status": "error", "error": str(e)})
        return results

    def run_local_batch(self, paths: list, target_langs: list):
        """Xu ly nhieu file video co san tren may x nhieu ngon ngu."""
        results = []
        total = len(paths) * len(target_langs)
        done = 0
        for path in paths:
            for lang in target_langs:
                done += 1
                self._log(f"[{done}/{total}] Processing: {path} -> {lang}")
                try:
                    result = self.run(local_video=path, target_lang=lang)
                    results.append({"file": path, "lang": lang, "status": "success", **result})
                except Exception as e:
                    self._log(f"FAILED: {path} -> {lang}: {e}")
                    results.append({"file": path, "lang": lang, "status": "error", "error": str(e)})
        return results

    def run_local_folder(self, folder: str, target_langs: list):
        """Quet 1 thu muc, xu ly moi file video tim duoc."""
        from src.steps.local_source import VIDEO_EXTS
        from pathlib import Path as _P
        files = sorted(str(f) for f in _P(folder).iterdir()
                       if f.is_file() and f.suffix.lower() in VIDEO_EXTS)
        if not files:
            raise FileNotFoundError(f"Khong tim thay video nao trong: {folder}")
        self._log(f"Tim thay {len(files)} video trong {folder}")
        return self.run_local_batch(files, target_langs)

    def run_from_file(self, url_file: str, target_langs: list[str]):
        """Read URLs from text file (1 per line), run batch."""
        urls = Path(url_file).read_text(encoding="utf-8").strip().splitlines()
        urls = [u.strip().split("\t")[0] for u in urls if u.strip() and not u.startswith("#")]
        return self.run_batch(urls, target_langs)

    def _log(self, msg: str):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}] [Pipeline] {msg}")
