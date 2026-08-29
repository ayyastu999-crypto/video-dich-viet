"""Detect hardcoded captions/subtitles in video.

Smart detection: distinguishes subtitles from UI text by analyzing:
- Position consistency across frames (subtitles appear at same Y)
- Horizontal centering (subtitles are usually centered)
- Text length (subtitles are short phrases, not long paragraphs)
- Y position clustering (find the most common text region)
"""
from pathlib import Path
from collections import Counter

from src.steps.base import BaseStep


class CaptionDetector(BaseStep):
    def run(self, video_path: Path) -> dict:
        from src.utils.model_cache import model_cache
        import cv2

        from src.utils.device import has_cuda
        # easyocr chi tang toc duoc bang CUDA; Mac phai chay CPU
        reader = model_cache.get_easyocr(["ch_sim", "en"], gpu=has_cuda())
        cap = cv2.VideoCapture(str(video_path))
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = cap.get(cv2.CAP_PROP_FPS) or 25
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        n_samples = self.config["caption"].get("detect_samples", 10)
        min_confidence = self.config["caption"].get("min_confidence", 0.5)
        padding = self.config["caption"].get("padding", 20)

        self.log(f"Detecting captions in {n_samples} frames ({width}x{height})")

        # Collect ALL text detections across frames
        raw_detections = []

        for i in range(n_samples):
            frame_idx = total_frames * (i + 1) // (n_samples + 1)
            timestamp = frame_idx / fps
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
            ret, frame = cap.read()
            if not ret:
                continue

            try:
                results = reader.readtext(frame)
            except Exception as e:
                self.log(f"  OCR error at {timestamp:.1f}s: {e}")
                continue

            for (box, text, conf) in results:
                if conf < min_confidence:
                    continue
                if len(text.strip()) < 2:
                    continue

                xs = [int(p[0]) for p in box]
                ys = [int(p[1]) for p in box]
                raw_detections.append({
                    "timestamp": round(timestamp, 2),
                    "text": text,
                    "confidence": round(conf, 3),
                    "x_min": min(xs),
                    "y_min": min(ys),
                    "x_max": max(xs),
                    "y_max": max(ys),
                    "y_center": (min(ys) + max(ys)) / 2,
                    "x_center": (min(xs) + max(xs)) / 2,
                    "box_width": max(xs) - min(xs),
                    "box_height": max(ys) - min(ys),
                })

        cap.release()

        if not raw_detections:
            self.log("No text detected")
            return {"caption_region": None, "detections": []}

        # Smart filtering: find the SUBTITLE region
        caption_detections = self._find_subtitle_region(
            raw_detections, width, height
        )

        if not caption_detections:
            self.log("No subtitle region found (only UI text detected)")
            return {"caption_region": None, "detections": []}

        # Build final region
        x1 = max(0, min(d["x_min"] for d in caption_detections) - padding)
        y1 = max(0, min(d["y_min"] for d in caption_detections) - padding)
        x2 = min(width, max(d["x_max"] for d in caption_detections) + padding)
        y2 = min(height, max(d["y_max"] for d in caption_detections) + padding)

        region = {"x": x1, "y": y1, "w": x2 - x1, "h": y2 - y1}

        detections = [{
            "timestamp": d["timestamp"],
            "text": d["text"],
            "confidence": d["confidence"],
            "bbox": {"x": d["x_min"], "y": d["y_min"],
                     "width": d["box_width"], "height": d["box_height"]},
        } for d in caption_detections]

        self.log(f"Caption region: {region} ({len(detections)} subtitle detections)")
        return {
            "caption_region": region,
            "detections": detections,
            "total_detections": len(detections),
        }

    def _find_subtitle_region(self, detections, width, height):
        """Identify which detections are subtitles vs UI text.

        Subtitles have these characteristics:
        1. Appear in bottom 50% of video (y > 50%)
        2. Horizontally centered (x_center near width/2)
        3. Appear at CONSISTENT Y position across frames
        4. Text is short-medium length (5-50 chars)
        5. Box width is 30-90% of video width (not tiny buttons or full-width bars)
        """
        candidates = []

        for d in detections:
            y_ratio = d["y_center"] / height
            x_center_ratio = d["x_center"] / width
            width_ratio = d["box_width"] / width
            text_len = len(d["text"].strip())

            # Score each detection on subtitle-likeness
            score = 0

            # Bottom of video (subtitles are almost always in bottom 30%)
            if y_ratio > 0.8:
                score += 4
            elif y_ratio > 0.7:
                score += 2
            elif y_ratio > 0.5:
                score += 0  # Middle area - neutral

            # Horizontally centered
            if 0.2 < x_center_ratio < 0.8:
                score += 2
            if 0.35 < x_center_ratio < 0.65:
                score += 1

            # Reasonable text width (not tiny button or full-width banner)
            if 0.2 < width_ratio < 0.9:
                score += 2

            # Reasonable text length for subtitle
            if 4 <= text_len <= 40:
                score += 2
            elif text_len > 40:
                score -= 1  # Too long, probably paragraph

            # Reasonable height (subtitle-sized, not huge heading)
            height_ratio = d["box_height"] / height
            if 0.02 < height_ratio < 0.08:
                score += 1

            d["_score"] = score
            if score >= 6:
                candidates.append(d)

        if not candidates:
            # Fallback: just take detections in bottom 40%
            candidates = [d for d in detections if d["y_center"] / height > 0.6]

        if not candidates:
            return []

        # Cluster by Y position: find the most common Y band
        # Subtitles appear at consistent Y across frames
        y_bands = []
        for d in candidates:
            band = round(d["y_center"] / height, 1)  # Round to 10% bands
            y_bands.append(band)

        band_counts = Counter(y_bands)
        best_band = band_counts.most_common(1)[0][0]

        # Keep only detections in the best Y band (±10%)
        filtered = [
            d for d in candidates
            if abs(round(d["y_center"] / height, 1) - best_band) <= 0.1
        ]

        self.log(f"  Subtitle scoring: {len(detections)} total -> "
                 f"{len(candidates)} candidates -> {len(filtered)} in band {best_band:.0%}")

        return filtered if filtered else candidates
