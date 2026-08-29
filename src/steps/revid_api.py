"""RevidAPI integration - Cloud alternative for caption/video processing.

Provides cloud-based alternatives for:
- detect_caption: OCR detect subtitle position
- blur_region: Blur old captions
- add_subtitle: Burn SRT subtitles with styling
- remove_background: Remove image background
- separate_voice: Vocal/instrumental separation

Usage: Set revid.enabled=true and revid.api_key in config.
Falls back to local processing if API fails.
"""
import time
import json
import requests
from pathlib import Path

from src.steps.base import BaseStep


class RevidAPI:
    """RevidAPI client wrapper."""

    BASE_URL = "https://api.revidapi.com/paid"

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.headers = {
            "x-api-key": api_key,
            "Content-Type": "application/json",
        }

    def _post(self, endpoint: str, data: dict, timeout: int = 30) -> dict:
        url = f"{self.BASE_URL}/{endpoint}"
        resp = requests.post(url, json=data, headers=self.headers, timeout=timeout)
        resp.raise_for_status()
        return resp.json()

    def _wait_for_task(self, task_id: str, max_wait: int = 300,
                       poll_interval: int = 5) -> dict:
        """Poll task status until complete."""
        url = f"{self.BASE_URL}/get/job/status/{task_id}"
        elapsed = 0
        while elapsed < max_wait:
            resp = requests.get(url, headers=self.headers, timeout=15)
            result = resp.json()
            status = result.get("message", "")
            if status == "success" or result.get("code") == 200:
                return result
            if "error" in status or "fail" in status:
                raise RuntimeError(f"Task failed: {result}")
            time.sleep(poll_interval)
            elapsed += poll_interval
        raise TimeoutError(f"Task {task_id} timed out after {max_wait}s")

    # ─── Tai video tu link ──────────────────────────────────────────────

    # nen tang cua ta -> doan {social} trong duong dan cua RevidAPI
    SOCIAL = {
        "douyin": "douyin",
        "tiktok": "tiktok",
        "facebook": "meta",
        "instagram": "meta",
        "youtube": "youtube",
    }

    def download(self, url: str, platform: str, quality: str = "1080p",
                 timeout: int = 120) -> dict:
        """Nho RevidAPI tai ho video.

        Dung khi cac cach mien phi deu bi chan (dien hinh la Douyin). Ton 5 credit
        mot lan goi, doi lai khong phai danh nhau voi he thong chong bot.

        Tra ve: {"url": link tai truc tiep, "title", "duration", "uploader"}
        """
        social = self.SOCIAL.get(platform)
        if not social:
            raise ValueError(f"RevidAPI khong ho tro nen tang: {platform}")

        res = self._post(f"{social}/download",
                         {"url": url, "quality": quality}, timeout=timeout)
        data = res.get("response") or {}

        # download_direct la link tai thang, video_url la du phong
        link = data.get("download_direct") or data.get("video_url") or data.get("url")
        if not link:
            raise RuntimeError(f"RevidAPI khong tra ve link tai: {res}")

        return {
            "url": link,
            "title": data.get("title") or "",
            "duration": data.get("duration") or 0,
            "uploader": data.get("uploader") or "",
            "filesize": data.get("filesize") or 0,
        }

    # ─── Caption Detection ──────────────────────────────────────────────

    def detect_caption(self, video_url: str, language: str = "auto",
                       min_confidence: float = 0.5,
                       sample_rate: int = 1) -> dict:
        """Detect hardcoded captions in video.

        Returns: {detections: [{timestamp, text, confidence, bbox}], total_detections}
        """
        data = {
            "video_url": video_url,
            "language": language,
            "min_confidence": min_confidence,
            "sample_rate": sample_rate,
            "output_format": "json",
        }
        result = self._post("detect-caption", data)
        if result.get("code") == 202:
            return self._wait_for_task(result["task_id"])
        return result

    # ─── Blur Region ────────────────────────────────────────────────────

    def blur_region(self, video_url: str, regions: list[dict],
                    blur_intensity: int = 50) -> str:
        """Blur specified regions in video.

        Args:
            video_url: Video URL
            regions: [{x, y, width, height, start_time, end_time}]
            blur_intensity: 0-100

        Returns: Output video URL
        """
        for r in regions:
            r.setdefault("blur_intensity", blur_intensity)

        data = {"video_url": video_url, "regions": regions}
        result = self._post("blur-region", data)
        if result.get("code") == 202:
            result = self._wait_for_task(result["task_id"])
        return result.get("response", {}).get("video_url", "")

    # ─── Add Subtitle ───────────────────────────────────────────────────

    def add_subtitle(self, video_url: str, subtitle_url: str = None,
                     subtitle_text: str = None, auto_generate: bool = False,
                     language: str = "auto", settings: dict = None) -> str:
        """Add subtitles to video.

        Args:
            video_url: Video URL
            subtitle_url: URL to .srt file
            subtitle_text: Plain text overlay
            auto_generate: Auto-transcribe audio
            language: Language code
            settings: {position, font_family, font_size, font_color,
                       bold, italic, outline_color, outline_width, alignment}

        Returns: Output video URL
        """
        data = {"video_url": video_url}
        if subtitle_url:
            data["subtitle_url"] = subtitle_url
        if subtitle_text:
            data["subtitle_text"] = subtitle_text
        if auto_generate:
            data["auto_generate"] = True
            data["language"] = language
        if settings:
            data["settings"] = settings

        result = self._post("add-subtitle", data)
        if result.get("code") == 202:
            result = self._wait_for_task(result["task_id"])
        return result.get("response", {}).get("video_url", "")

    # ─── Remove Background ──────────────────────────────────────────────

    def remove_background(self, image_path: str,
                          model: str = "u2net") -> str:
        """Remove background from image.

        Args:
            image_path: Local image file path
            model: u2net, u2net_human_seg, isnet-general-use, etc.

        Returns: Output image URL
        """
        url = f"{self.BASE_URL}/image/remove/background"
        with open(image_path, "rb") as f:
            resp = requests.post(
                url,
                headers={"x-api-key": self.api_key},
                files={"file": f},
                data={"model": model},
                timeout=30,
            )
        result = resp.json()
        if result.get("task_id"):
            # Poll edit.revidapi.com
            task_id = result["task_id"]
            for _ in range(60):
                status_resp = requests.get(
                    f"https://edit.revidapi.com/api/get/{task_id}",
                    headers={"x-api-key": self.api_key},
                    timeout=15,
                )
                status = status_resp.json()
                if status.get("status") == "completed":
                    return status["result"]["image_url"]
                if status.get("status") == "failed":
                    raise RuntimeError(f"Remove BG failed: {status}")
                time.sleep(2)
        return result.get("result", {}).get("image_url", "")


# ─── Step wrappers that integrate with pipeline ─────────────────────────

class RevidCaptionDetector(BaseStep):
    """Detect captions using RevidAPI (cloud) with local fallback."""

    def run(self, video_path: Path, video_url: str = None) -> dict:
        api_key = self.config.get("revid", {}).get("api_key", "")
        if not api_key or not video_url:
            # Fallback to local EasyOCR
            from src.steps.caption_detector import CaptionDetector
            return CaptionDetector(self.config, self.work_dir).run(video_path=video_path)

        self.log("Detecting captions via RevidAPI...")
        try:
            api = RevidAPI(api_key)
            result = api.detect_caption(video_url, min_confidence=0.5)
            detections = result.get("response", {}).get("detections", [])

            if not detections:
                return {"caption_region": None}

            # Aggregate bounding boxes
            all_x = [d["bbox"]["x"] for d in detections]
            all_y = [d["bbox"]["y"] for d in detections]
            all_x2 = [d["bbox"]["x"] + d["bbox"]["width"] for d in detections]
            all_y2 = [d["bbox"]["y"] + d["bbox"]["height"] for d in detections]

            region = {
                "x": min(all_x),
                "y": min(all_y),
                "w": max(all_x2) - min(all_x),
                "h": max(all_y2) - min(all_y),
            }
            self.log(f"RevidAPI detected: {len(detections)} captions, region: {region}")
            return {"caption_region": region, "detections": detections}

        except Exception as e:
            self.log(f"RevidAPI failed: {e}, falling back to local")
            from src.steps.caption_detector import CaptionDetector
            return CaptionDetector(self.config, self.work_dir).run(video_path=video_path)
