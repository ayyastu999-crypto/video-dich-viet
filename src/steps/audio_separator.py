from pathlib import Path

from src.steps.base import BaseStep
from src.utils.ffmpeg import run_ffmpeg


class AudioSeparator(BaseStep):
    def run(self, video_path: Path) -> dict:
        output_dir = self.ensure_dir("separated")
        model_name = self.config["audio"].get("separation_model", "htdemucs")

        # Extract audio as WAV first
        audio_wav = output_dir / f"{video_path.stem}.wav"
        if not audio_wav.exists():
            self.log("Extracting audio from video...")
            run_ffmpeg([
                "-i", str(video_path),
                "-vn", "-acodec", "pcm_s16le", "-ar", "44100", "-ac", "2",
                str(audio_wav),
            ])

        stem_dir = output_dir / model_name / audio_wav.stem
        vocals_path = stem_dir / "vocals.wav"
        instrumental_path = stem_dir / "no_vocals.wav"

        if instrumental_path.exists() and vocals_path.exists():
            self.log("Using cached separated audio")
            return {"vocals": vocals_path, "instrumental": instrumental_path}

        self.log(f"Separating audio with {model_name}...")
        stem_dir.mkdir(parents=True, exist_ok=True)

        # Use demucs API directly + save with soundfile (bypass torchcodec)
        self._separate_with_soundfile(audio_wav, model_name, stem_dir)

        self.log(f"Separated: vocals={vocals_path.exists()}, instrumental={instrumental_path.exists()}")
        return {"vocals": vocals_path, "instrumental": instrumental_path}

    def _separate_with_soundfile(self, audio_path, model_name, output_dir):
        import torch
        import soundfile as sf
        from demucs.apply import apply_model
        from demucs.audio import AudioFile
        from src.utils.model_cache import model_cache

        device = "cuda" if torch.cuda.is_available() else "cpu"
        model = model_cache.get_demucs(model_name, device=device)

        # Load audio
        wav = AudioFile(str(audio_path)).read(
            streams=0, samplerate=model.samplerate, channels=model.audio_channels
        )
        ref = wav.mean(0)
        wav = (wav - ref.mean()) / ref.std()
        if device == "cuda":
            wav = wav.cuda()

        # Separate
        with torch.no_grad():
            sources = apply_model(model, wav[None], progress=True)[0]

        # sources shape: [num_sources, channels, samples]
        # Find vocals index
        source_names = model.sources
        vocals_idx = source_names.index("vocals") if "vocals" in source_names else 0

        # Denormalize
        sources = sources * ref.std() + ref.mean()

        vocals = sources[vocals_idx].cpu().numpy().T  # [samples, channels]
        # Sum all non-vocal sources for instrumental
        non_vocal_indices = [i for i in range(len(source_names)) if i != vocals_idx]
        instrumental = sum(sources[i] for i in non_vocal_indices).cpu().numpy().T

        # Save with soundfile
        sf.write(str(output_dir / "vocals.wav"), vocals, model.samplerate)
        sf.write(str(output_dir / "no_vocals.wav"), instrumental, model.samplerate)
