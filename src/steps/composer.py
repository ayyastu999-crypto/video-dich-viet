from pathlib import Path

from src.steps.base import BaseStep
from src.utils.ffmpeg import run_ffmpeg
from src.utils.ffmpeg_fast import get_video_codec_args


class Composer(BaseStep):
    def run(self, captioned_video: Path, mixed_audio: Path, logo: Path = None) -> dict:
        output_dir = self.ensure_dir("output")
        out_path = output_dir / f"final_{captioned_video.stem}.mp4"
        out_cfg = self.config["output"]

        self.log("Composing final video (NVENC)...")

        args = ["-i", str(captioned_video), "-i", str(mixed_audio)]

        if logo and logo.exists():
            args.extend(["-i", str(logo)])
            filter_complex = "[0:v][2:v]overlay=W-w-10:10[vout]"
            args.extend(["-filter_complex", filter_complex, "-map", "[vout]"])
        else:
            args.extend(["-map", "0:v"])

        args.extend([
            "-map", "1:a",
            *get_video_codec_args(
                preset=out_cfg.get("preset", "fast"),
                crf=int(out_cfg.get("crf", 20)),
            ),
            "-c:a", "aac",
            "-b:a", out_cfg.get("audio_bitrate", "192k"),
            "-movflags", "+faststart",
            str(out_path),
        ])

        run_ffmpeg(args)

        self.log(f"Final video: {out_path.name}")
        return {"final_video": out_path}
