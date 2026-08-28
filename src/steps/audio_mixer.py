from pathlib import Path

from src.steps.base import BaseStep
from src.utils.ffmpeg import run_ffmpeg


class AudioMixer(BaseStep):
    def run(self, tts_audio: Path, instrumental: Path) -> dict:
        output_dir = self.ensure_dir("output")
        # Per-video output name to prevent overwrite in batch
        stem = instrumental.parent.name if instrumental else "mixed"
        out_path = output_dir / f"mixed_{stem}.wav"
        bg_volume = self.config["audio"].get("bg_volume", 0.3)
        dropout = self.config["audio"].get("dropout_transition", 2)

        self.log(f"Mixing TTS + instrumental (bg volume: {bg_volume})")

        run_ffmpeg([
            "-i", str(tts_audio),
            "-i", str(instrumental),
            "-filter_complex",
            f"[1:a]volume={bg_volume}[bg];"
            f"[0:a][bg]amix=inputs=2:duration=first:dropout_transition={dropout}",
            "-ac", "2",
            str(out_path),
        ])

        self.log(f"Mixed audio saved: {out_path.name}")
        return {"mixed_audio": out_path}
