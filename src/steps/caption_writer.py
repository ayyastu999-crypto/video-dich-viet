"""Burn subtitles into video at detected caption position.

Key feature: auto-detect where original caption was and place new
subtitle at EXACT same position (MarginV calculated from detected bbox).
"""
from pathlib import Path

from src.steps.base import BaseStep
from src.utils.ffmpeg import run_ffmpeg


# ASS alignment values (numpad layout)
POSITION_MAP = {
    "bottom-left": 1, "bottom-center": 2, "bottom-right": 3,
    "middle-left": 4, "middle-center": 5, "middle-right": 6,
    "top-left": 7, "top-center": 8, "top-right": 9,
    "bottom": 2, "center": 5, "top": 8,
}


class CaptionWriter(BaseStep):
    def run(self, video_path: Path, translated_srt: Path = None,
            caption_region: dict = None, video_height: int = None) -> dict:
        """Burn subtitles at detected caption position.

        Args:
            video_path: Input video
            translated_srt: Path to SRT file
            caption_region: {x, y, w, h} from CaptionDetector - used to
                            calculate exact vertical position
            video_height: Video height in pixels (auto-detected if None)
        """
        output_dir = self.ensure_dir("output")
        out_path = output_dir / f"{video_path.stem}_captioned.mp4"
        style = self.config["caption"]["style"]

        if not translated_srt:
            self.log("No subtitle source, passing through")
            return {"captioned_video": video_path}

        # Auto-detect video dimensions
        if video_height is None:
            w, h = self._get_video_dimensions(video_path)
            video_height = h
            self._cached_width = w

        # Calculate position from detected caption region
        margin_v, alignment, font_size = self._calc_position_from_region(
            caption_region, video_height, style
        )

        force_style = (
            f"FontName={style.get('font', 'Arial')},"
            f"FontSize={font_size},"
            f"PrimaryColour={style.get('color', '&HFFFFFF')},"
            f"OutlineColour={style.get('outline_color', '&H000000')},"
            f"Outline={style.get('outline', 2)},"
            f"Shadow={style.get('shadow', 1)},"
            f"Bold={1 if style.get('bold', False) else 0},"
            f"Italic={1 if style.get('italic', False) else 0},"
            f"MarginV={margin_v},"
            f"Alignment={alignment}"
        )

        self.log(f"Burning subtitles at MarginV={margin_v}, "
                 f"FontSize={font_size}, Alignment={alignment}")

        from src.utils.ffmpeg_fast import get_video_codec_args
        srt_safe = str(translated_srt).replace("\\", "/").replace(":", "\\:")
        run_ffmpeg([
            "-i", str(video_path),
            "-vf", f"subtitles='{srt_safe}':force_style='{force_style}'",
            "-c:a", "copy",
            # Doc crf tu config thay vi co dinh, de chinh 1 cho la ca chuoi
            # re-encode deu theo (buoc nay va Composer noi tiep nhau).
            *get_video_codec_args(
                preset=self.config.get("output", {}).get("preset", "fast"),
                crf=int(self.config.get("output", {}).get("crf", 20)),
            ),
            str(out_path),
        ])

        self.log(f"Captioned video: {out_path.name}")
        return {"captioned_video": out_path}

    def _calc_position_from_region(self, caption_region, video_height, style):
        """Calculate subtitle position.

        If style.auto_position=False, use manual config (size, margin_v, alignment).
        Otherwise, auto-calculate from detected caption region.
        """
        default_size = style.get("size", 24)
        auto_mode = style.get("auto_position", True)

        # MANUAL MODE: Use user config directly
        if not auto_mode:
            position = style.get("position", "bottom-center")
            alignment = POSITION_MAP.get(position, 2)
            margin_v = style.get("margin_v", 30)
            self.log(f"  Manual mode: FontSize={default_size}, MarginV={margin_v}, Alignment={alignment}")
            return margin_v, alignment, default_size

        # AUTO MODE: Smart detect
        if not caption_region or not video_height:
            alignment = 2
            video_width = self._get_video_width_from_height(video_height)
            if video_width:
                auto_size = max(12, min(28, int(video_width * 0.025)))
                margin_v = max(10, int(video_height * 0.02))
            else:
                auto_size = default_size
                margin_v = style.get("margin_v", 30)
            self.log(f"  Auto-sizing (no caption detected): FontSize={auto_size}, MarginV={margin_v}")
            return margin_v, alignment, auto_size

        y = caption_region["y"]
        h = caption_region["h"]
        w = caption_region["w"]

        # Caption center Y
        center_y = y + h // 2

        # Determine if caption is in top/middle/bottom third
        if center_y < video_height * 0.33:
            # Top area
            alignment = 8  # top-center
            margin_v = y
        elif center_y < video_height * 0.66:
            # Middle area
            alignment = 5  # middle-center
            margin_v = 0
        else:
            # Bottom area (most common for subtitles)
            alignment = 2  # bottom-center
            # MarginV = distance from bottom of video to bottom of caption
            margin_v = max(0, video_height - (y + h))

        # Estimate font size from detected caption height
        # ASS FontSize must be proportional to video WIDTH (not height)
        # Detected box height -> estimate original font size
        # But clamp based on video width to prevent overflow
        video_width = self._get_video_width_from_height(video_height)
        max_font = int(video_width * 0.035) if video_width else 28
        estimated_size = max(12, min(max_font, int(h * 0.4)))
        font_size = estimated_size

        self.log(f"  Detected caption: y={y}, h={h}, center={center_y}/{video_height}")
        self.log(f"  Calculated: MarginV={margin_v}, FontSize={font_size}")

        return margin_v, alignment, font_size

    def _get_video_height(self, video_path):
        """Get video height using ffprobe."""
        import subprocess
        r = subprocess.run(
            ["ffprobe", "-v", "quiet", "-select_streams", "v:0",
             "-show_entries", "stream=height",
             "-of", "default=noprint_wrappers=1:nokey=1",
             str(video_path)],
            capture_output=True, text=True,
        )
        try:
            return int(r.stdout.strip())
        except (ValueError, AttributeError):
            return 1920

    def _get_video_width_from_height(self, video_height):
        """Estimate video width from height. Cache actual value if available."""
        if hasattr(self, "_cached_width") and self._cached_width:
            return self._cached_width
        # Common Douyin ratios
        if video_height >= 1900:
            return 1080  # 1080x1920
        elif video_height >= 1200:
            return 720   # 720x1280
        elif video_height >= 1000:
            return 1920  # 1920x1080 landscape
        elif video_height >= 900:
            return 720   # 720x960
        return 720  # safe default

    def _get_video_dimensions(self, video_path):
        """Get both width and height."""
        import subprocess
        r = subprocess.run(
            ["ffprobe", "-v", "quiet", "-select_streams", "v:0",
             "-show_entries", "stream=width,height",
             "-of", "csv=s=x:p=0",
             str(video_path)],
            capture_output=True, text=True,
        )
        try:
            w, h = r.stdout.strip().split("x")
            self._cached_width = int(w)
            return int(w), int(h)
        except (ValueError, AttributeError):
            return 720, 1280
