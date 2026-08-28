"""Global model cache - keeps heavy AI models loaded across videos.

Saves 5-15s per video by avoiding reloading:
- EasyOCR Reader (~5s load)
- Demucs model (~3s load)
- faster-whisper (~2s load)
"""
import threading


class ModelCache:
    """Thread-safe singleton cache for heavy AI models."""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._whisper = {}
                    cls._instance._easyocr = None
                    cls._instance._demucs = {}
                    cls._instance._f5tts = None
                    cls._instance._kokoro = None
        return cls._instance

    def get_whisper(self, model_name: str, device: str, compute_type: str):
        key = f"{model_name}:{device}:{compute_type}"
        if key not in self._whisper:
            from faster_whisper import WhisperModel
            self._whisper[key] = WhisperModel(
                model_name, device=device, compute_type=compute_type
            )
        return self._whisper[key]

    def get_easyocr(self, langs: list = None, gpu: bool = True):
        if self._easyocr is None:
            import easyocr
            self._easyocr = easyocr.Reader(
                langs or ["ch_sim", "en"], gpu=gpu, verbose=False
            )
        return self._easyocr

    def get_demucs(self, model_name: str, device: str = "cuda"):
        key = f"{model_name}:{device}"
        if key not in self._demucs:
            import torch
            from demucs.pretrained import get_model
            m = get_model(model_name)
            m.eval()
            if device == "cuda" and torch.cuda.is_available():
                m.cuda()
            self._demucs[key] = m
        return self._demucs[key]

    def get_f5tts(self, model: str = "F5TTS_v1_Base", device: str = "cuda"):
        if self._f5tts is None:
            # Patch torchaudio first
            from src.steps.tts_clone import TTSCloneGenerator
            TTSCloneGenerator._patch_torchaudio()
            from f5_tts.api import F5TTS
            self._f5tts = F5TTS(model=model, device=device)
        return self._f5tts

    def get_kokoro(self, model_path: str, voices_path: str):
        if self._kokoro is None:
            import kokoro_onnx
            self._kokoro = kokoro_onnx.Kokoro(model_path, voices_path)
        return self._kokoro

    def clear(self):
        """Free all cached models (for memory cleanup)."""
        import gc
        self._whisper.clear()
        self._easyocr = None
        self._demucs.clear()
        self._f5tts = None
        self._kokoro = None
        try:
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except ImportError:
            pass
        gc.collect()


# Global singleton instance
model_cache = ModelCache()
