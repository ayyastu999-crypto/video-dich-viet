"""Blur caption regions in video.

Inspired by RevidAPI blur-region:
- Supports time-based blur (only blur when captions appear)
- Configurable blur intensity (0-100)
- Multiple region support
"""
from pathlib import Path

from src.steps.base import BaseStep
from src.utils.ffmpeg import run_ffmpeg


class CaptionBlur(BaseStep):
    def run(self, video_path: Path, caption_region: dict | None,
            detections: list[dict] = None) -> dict:
        """Blur caption region in video.

        Args:
            video_path: Input video
            caption_region: {x, y, w, h} aggregate region
            detections: Optional list of per-timestamp detections for time-based blur
        """
        if caption_region is None:
            self.log("No caption region to blur, passing through")
            return {"blurred_video": video_path}

        # Validate + clamp region to video bounds
        r = self._validate_region(caption_region, video_path)
        if r is None:
            self.log("Invalid region, skipping blur")
            return {"blurred_video": video_path}

        blur_strength = self.config["caption"].get("blur_strength", 51)
        # blur_strength must be odd for boxblur, and not too large
        blur_strength = min(blur_strength, min(r["w"], r["h"]) // 4)
        blur_strength = max(blur_strength, 5)

        output_dir = self.ensure_dir("output")
        out_path = output_dir / f"{video_path.stem}_blurred.mp4"

        self.log(f"Blurring region: x={r['x']}, y={r['y']}, "
                 f"w={r['w']}, h={r['h']} (intensity={blur_strength})")

        try:
            if detections and len(detections) > 2:
                self._blur_timed(video_path, r, detections, blur_strength, out_path)
            else:
                self._blur_full(video_path, r, blur_strength, out_path)
        except Exception as e:
            self.log(f"Blur failed ({e}), trying simpler method...")
            try:
                # Fallback: simpler drawbox blur
                self._blur_simple(video_path, r, out_path)
            except Exception as e2:
                self.log(f"Blur fallback also failed ({e2}), skipping blur")
                return {"blurred_video": video_path}

        self.log(f"Blurred video saved: {out_path.name}")
        return {"blurred_video": out_path}

    def _validate_region(self, region, video_path):
        """Clamp region to video bounds, return None if invalid."""
        import subprocess
        r_info = subprocess.run(
            ["ffprobe", "-v", "quiet", "-select_streams", "v:0",
             "-show_entries", "stream=width,height",
             "-of", "csv=s=x:p=0", str(video_path)],
            capture_output=True, text=True,
        )
        try:
            vw, vh = map(int, r_info.stdout.strip().split("x"))
        except (ValueError, AttributeError):
            return region  # Can't validate, pass through

        x = max(0, int(region.get("x", 0)))
        y = max(0, int(region.get("y", 0)))
        w = int(region.get("w", 0))
        h = int(region.get("h", 0))

        # Clamp to video bounds
        if x >= vw or y >= vh:
            return None
        w = min(w, vw - x)
        h = min(h, vh - y)

        # Must be even for video encoding
        w = (w // 2) * 2
        h = (h // 2) * 2

        if w < 10 or h < 10:
            return None

        return {"x": x, "y": y, "w": w, "h": h}

    def _blur_simple(self, video_path, r, out_path):
        """Simplest blur using avgblur (less memory, more compatible)."""
        vf = (
            f"split=2[main][blur];"
            f"[blur]crop={r['w']}:{r['h']}:{r['x']}:{r['y']},"
            f"avgblur=10[blurred];"
            f"[main][blurred]overlay={r['x']}:{r['y']}"
        )
        run_ffmpeg([
            "-i", str(video_path),
            "-filter_complex", vf,
            "-c:a", "copy", "-c:v", "libx264",
            "-preset", "veryfast", "-crf", "23",
            "-pix_fmt", "yuv420p",
            str(out_path),
        ])

    def _blur_full(self, video_path, r, blur_strength, out_path):
        """Blur region for entire video duration (uses NVENC if available)."""
        from src.utils.ffmpeg_fast import get_video_codec_args
        vf = (
            f"split=2[main][blur];"
            f"[blur]crop={r['w']}:{r['h']}:{r['x']}:{r['y']},"
            f"boxblur={blur_strength}[blurred];"
            f"[main][blurred]overlay={r['x']}:{r['y']}"
        )
        run_ffmpeg([
            "-i", str(video_path),
            "-filter_complex", vf,
            "-c:a", "copy",
            *get_video_codec_args(preset="fast", crf=22),
            str(out_path),
        ])

    def _blur_timed(self, video_path, r, detections, blur_strength, out_path):
        """Time-based blur - only blur when captions are visible.

        Groups detections into time ranges, applies blur with enable/disable.
        """
        # Group detections into time ranges (merge close timestamps)
        ranges = self._merge_time_ranges(detections, gap_threshold=0.5)

        if not ranges:
            self._blur_full(video_path, r, blur_strength, out_path)
            return

        # Build enable condition: blur only during detected ranges
        enable_parts = []
        for start, end in ranges:
            enable_parts.append(f"between(t,{start:.2f},{end:.2f})")
        enable_expr = "+".join(enable_parts)

        # Use drawbox with blur or crop+overlay with enable
        vf = (
            f"split[main][blur];"
            f"[blur]crop={r['w']}:{r['h']}:{r['x']}:{r['y']},"
            f"boxblur={blur_strength}[blurred];"
            f"[main][blurred]overlay={r['x']}:{r['y']}:enable='{enable_expr}'"
        )
        run_ffmpeg([
            "-i", str(video_path),
            "-filter_complex", vf,
            "-c:a", "copy", "-preset", "fast",
            str(out_path),
        ])

    def _merge_time_ranges(self, detections, gap_threshold=0.5):
        """Merge close timestamp detections into continuous ranges."""
        if not detections:
            return []

        timestamps = sorted(set(d["timestamp"] for d in detections))
        ranges = []
        start = timestamps[0]
        end = timestamps[0] + 1.0  # Assume caption visible for ~1s per detection

        for ts in timestamps[1:]:
            if ts - end <= gap_threshold:
                end = ts + 1.0
            else:
                ranges.append((max(0, start - 0.2), end + 0.2))
                start = ts
                end = ts + 1.0

        ranges.append((max(0, start - 0.2), end + 0.2))
        return ranges
