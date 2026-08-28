"""Scrape all video URLs from a Douyin user/channel profile."""
import re
import time
import json
from pathlib import Path

from src.steps.base import BaseStep


class ChannelScraper(BaseStep):
    def run(self, profile_url: str, max_videos: int = 0) -> dict:
        """Scrape video URLs from a Douyin profile page.

        Args:
            profile_url: Douyin user profile URL
            max_videos: Max videos to scrape (0 = all)

        Returns:
            dict with 'video_urls' list and 'channel_info' dict
        """
        self.log(f"Scraping channel: {profile_url}")

        if self._is_profile_url(profile_url):
            return self._scrape_playwright(profile_url, max_videos)
        else:
            # Single video URL, just return it
            return {"video_urls": [profile_url], "channel_info": {}}

    def _is_profile_url(self, url: str) -> bool:
        return bool(re.search(r'/user/', url)) and not re.search(r'modal_id=', url)

    def _scrape_playwright(self, profile_url: str, max_videos: int) -> dict:
        from playwright.sync_api import sync_playwright

        # Use REAL Chrome with persistent profile to bypass Douyin captcha
        chrome_path = "C:/Program Files/Google/Chrome/Application/chrome.exe"
        user_data = Path.home() / "AppData" / "Local" / "Google" / "Chrome" / "User Data"

        with sync_playwright() as p:
            ctx = p.chromium.launch_persistent_context(
                user_data_dir=str(user_data / "DouyinScraper"),
                executable_path=chrome_path if Path(chrome_path).exists() else None,
                headless=False,
                args=["--disable-blink-features=AutomationControlled"],
            )

            page = ctx.pages[0] if ctx.pages else ctx.new_page()
            self.log(f"Opening browser for: {profile_url[:80]}...")
            page.goto(profile_url, timeout=60000)

            # Wait for captcha resolution if needed
            for _ in range(30):
                time.sleep(2)
                try:
                    title = page.title()
                    if "验证" not in title and "captcha" not in title.lower():
                        break
                except Exception:
                    continue  # Page navigating
            time.sleep(5)

            # Get channel info
            channel_info = {}
            try:
                name_el = page.query_selector('[data-e2e="user-info"] .j5WZzJdp')
                if name_el:
                    channel_info["name"] = name_el.inner_text()
            except:
                pass

            # Scroll to load all videos
            video_urls = set()
            last_count = 0
            no_change_rounds = 0

            while True:
                # Find video links - multiple selectors for Douyin DOM variants
                video_ids_found = set()

                # Method 1: href links
                links = page.query_selector_all('a[href*="/video/"]')
                for link in links:
                    href = link.get_attribute("href") or ""
                    m = re.search(r'/video/(\d+)', href)
                    if m:
                        video_ids_found.add(m.group(1))

                # Method 2: extract from page HTML (catches dynamically loaded)
                html = page.content()
                for m in re.finditer(r'/video/(\d{15,})', html):
                    video_ids_found.add(m.group(1))

                # Method 3: modal_id links
                for m in re.finditer(r'modal_id=(\d{15,})', html):
                    video_ids_found.add(m.group(1))

                for vid in video_ids_found:
                    video_urls.add(f"https://www.douyin.com/video/{vid}")

                current_count = len(video_urls)
                self.log(f"  Found {current_count} videos...")

                # Check stop conditions
                if max_videos > 0 and current_count >= max_videos:
                    break

                if current_count == last_count:
                    no_change_rounds += 1
                    if no_change_rounds >= 5:
                        break
                else:
                    no_change_rounds = 0
                    last_count = current_count

                # Scroll down more aggressively
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                time.sleep(3)

            ctx.close()

        urls = sorted(video_urls)
        if max_videos > 0:
            urls = urls[:max_videos]

        self.log(f"Scraped {len(urls)} videos from channel")

        # Save URL list
        output_dir = self.ensure_dir("downloads")
        list_file = output_dir / "channel_urls.txt"
        with open(list_file, "w", encoding="utf-8") as f:
            for url in urls:
                f.write(f"{url}\n")

        return {
            "video_urls": urls,
            "channel_info": channel_info,
            "url_file": list_file,
        }

    def _load_cookies(self, context, cookies_file: str):
        """Load Netscape cookie file into Playwright browser context."""
        cookies = []
        with open(cookies_file, encoding="utf-8") as f:
            for line in f:
                if line.startswith("#") or not line.strip():
                    continue
                parts = line.strip().split("\t")
                if len(parts) >= 7:
                    domain = parts[0]
                    if not domain.startswith("."):
                        domain = "." + domain
                    cookies.append({
                        "name": parts[5],
                        "value": parts[6],
                        "domain": domain,
                        "path": parts[2],
                        "secure": parts[3] == "TRUE",
                        "httpOnly": False,
                    })
        if cookies:
            context.add_cookies(cookies)
            self.log(f"  Loaded {len(cookies)} cookies")
