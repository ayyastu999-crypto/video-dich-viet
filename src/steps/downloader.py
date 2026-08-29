import re
import time
from pathlib import Path

from src.steps.base import BaseStep


class Downloader(BaseStep):
    def run(self, url: str) -> dict:
        output_dir = self.ensure_dir("downloads")
        retry_count = self.config["download"].get("retry_count", 3)

        # Extract video ID from URL
        video_id = self._extract_video_id(url)
        if not video_id:
            raise ValueError(f"Cannot extract video ID from: {url}")

        video_path = output_dir / f"{video_id}.mp4"

        # Skip re-download if already exists
        if video_path.exists() and video_path.stat().st_size > 10000:
            self.log(f"Already downloaded: {video_path.name}")
            return {
                "video_path": video_path,
                "video_id": video_id,
                "metadata": {"title": "", "description": "", "tags": [],
                              "uploader": "", "duration": 0},
            }

        # Playwright first (yt-dlp Douyin extractor often broken)
        # Python xoa ten bien cua "except ... as e" khi thoat khoi khoi except,
        # nen phai giu loi ra bien khac de con dung o duoi.
        pw_error = "khong ro"
        try:
            return self._download_playwright(video_id, output_dir)
        except Exception as e:
            pw_error = f"{type(e).__name__}: {e}"
            self.log(f"Playwright failed: {pw_error}, trying yt-dlp...")

        # Fallback to yt-dlp
        for attempt in range(1, retry_count + 1):
            try:
                return self._download_ytdlp(url, video_id, output_dir)
            except Exception as e:
                if attempt == retry_count:
                    raise RuntimeError(
                        f"All download methods failed. Playwright: {pw_error}, yt-dlp: {e}"
                    )

    def _extract_video_id(self, url: str) -> str | None:
        # Match /video/ID or modal_id=ID
        match = re.search(r'(?:video/|modal_id=)(\d+)', url)
        if match:
            return match.group(1)
        # Match share URL /v.douyin.com/xxx
        match = re.search(r'(\d{15,})', url)
        return match.group(1) if match else None

    def _download_ytdlp(self, url: str, video_id: str, output_dir: Path) -> dict:
        import yt_dlp

        cookies_file = self.config["download"]["cookies_file"]
        opts = {
            "outtmpl": str(output_dir / "%(id)s.%(ext)s"),
            "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
            "merge_output_format": "mp4",
            "socket_timeout": self.config["download"].get("timeout", 60),
        }

        if Path(cookies_file).exists():
            opts["cookiefile"] = cookies_file

        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            video_path = output_dir / f"{info['id']}.mp4"
            return {
                "video_path": video_path,
                "video_id": info["id"],
                "metadata": {
                    "title": info.get("title", ""),
                    "description": info.get("description", ""),
                    "tags": info.get("tags", []),
                    "uploader": info.get("uploader", ""),
                    "duration": info.get("duration", 0),
                },
            }

    def _download_playwright(self, video_id: str, output_dir: Path) -> dict:
        from playwright.sync_api import sync_playwright

        url = f"https://www.douyin.com/video/{video_id}"
        video_path = output_dir / f"{video_id}.mp4"

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            ctx = browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/130.0.0.0 Safari/537.36"
                )
            )
            page = ctx.new_page()
            # "load" cho toan bo tai nguyen tai xong - Douyin la SPA nang nen
            # su kien do co the khong bao gio xay ra. "domcontentloaded" du dung,
            # vi ngay sau day ta doi the <video> xuat hien.
            cho = int(self.config["download"].get("timeout", 60)) * 1000
            page.goto(url, wait_until="domcontentloaded", timeout=cho)
            try:
                page.wait_for_selector("video", timeout=cho)
            except Exception:
                pass          # khong thay the video thi van thu boc tu HTML ben duoi
            time.sleep(3)

            # Find video source URL
            video_url = None
            for el in page.query_selector_all("video source, video"):
                src = el.get_attribute("src")
                if src and "http" in src:
                    video_url = src
                    break

            if not video_url:
                content = page.content()
                matches = re.findall(
                    r'(https?://v[0-9a-z-]+\.(?:zjcdn|douyinvod)\.com/[^"]+)',
                    content,
                )
                if matches:
                    video_url = matches[0]

            if not video_url:
                browser.close()
                raise RuntimeError("No video URL found on page")

            resp = page.request.get(video_url)
            with open(video_path, "wb") as f:
                f.write(resp.body())

            # Try to get title from page
            title = ""
            title_el = page.query_selector('[data-e2e="video-desc"]')
            if title_el:
                title = title_el.inner_text()

            browser.close()

        size_mb = video_path.stat().st_size / 1024 / 1024
        self.log(f"Downloaded via Playwright: {video_path.name} ({size_mb:.1f} MB)")

        return {
            "video_path": video_path,
            "video_id": video_id,
            "metadata": {
                "title": title,
                "description": "",
                "tags": [],
                "uploader": "",
                "duration": 0,
            },
        }
