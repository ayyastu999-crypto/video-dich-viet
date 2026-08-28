"""Search Douyin videos by keyword, sorted by popularity."""
import re
import time
import json
from pathlib import Path
from urllib.parse import quote

from src.steps.base import BaseStep


class KeywordSearch(BaseStep):
    def run(self, keyword: str, max_results: int = 20,
            sort: str = "popular") -> dict:
        """Search Douyin videos by keyword.

        Args:
            keyword: Search term
            max_results: Max videos to return
            sort: "popular" (most liked), "new" (newest), "default" (relevance)

        Returns:
            dict with 'videos' list of {url, title, likes, comments, shares, author}
        """
        self.log(f"Searching: '{keyword}' (sort={sort}, max={max_results})")
        videos = self._search_playwright(keyword, max_results, sort)

        # Save results
        output_dir = self.ensure_dir("downloads")
        results_file = output_dir / f"search_{keyword[:30].replace(' ', '_')}.json"
        with open(results_file, "w", encoding="utf-8") as f:
            json.dump({"keyword": keyword, "sort": sort, "videos": videos}, f,
                      ensure_ascii=False, indent=2)

        # Save URL list for batch processing
        url_file = output_dir / f"search_{keyword[:30].replace(' ', '_')}_urls.txt"
        with open(url_file, "w", encoding="utf-8") as f:
            for v in videos:
                f.write(f"{v['url']}\t{v.get('title', '')[:50]}\t"
                        f"likes={v.get('likes', 0)}\n")

        self.log(f"Found {len(videos)} videos -> {url_file.name}")
        return {
            "videos": videos,
            "url_file": url_file,
            "results_file": results_file,
        }

    def _search_playwright(self, keyword: str, max_results: int,
                           sort: str) -> list[dict]:
        from playwright.sync_api import sync_playwright

        sort_map = {"popular": 1, "new": 2, "default": 0}
        sort_type = sort_map.get(sort, 0)

        search_url = (
            f"https://www.douyin.com/search/{quote(keyword)}"
            f"?type=video&sort_type={sort_type}"
        )

        chrome_path = "C:/Program Files/Google/Chrome/Application/chrome.exe"
        user_data = Path.home() / "AppData" / "Local" / "Google" / "Chrome" / "User Data"

        with sync_playwright() as p:
            browser = p.chromium.launch_persistent_context(
                user_data_dir=str(user_data / "DouyinScraper"),
                executable_path=chrome_path if Path(chrome_path).exists() else None,
                headless=False,
                args=["--disable-blink-features=AutomationControlled"],
            )

            page = browser.pages[0] if browser.pages else browser.new_page()
            page.goto(search_url, timeout=30000)

            # Wait for captcha
            for _ in range(15):
                time.sleep(2)
                if "验证" not in page.title():
                    break

            time.sleep(3)

            videos = []
            last_count = 0
            no_change = 0

            while len(videos) < max_results:
                # Extract video data from page
                new_videos = self._extract_videos_from_page(page)
                for v in new_videos:
                    if v["url"] not in {x["url"] for x in videos}:
                        videos.append(v)

                if len(videos) == last_count:
                    no_change += 1
                    if no_change >= 3:
                        break
                else:
                    no_change = 0
                    last_count = len(videos)

                self.log(f"  Collected {len(videos)}/{max_results}...")

                if len(videos) >= max_results:
                    break

                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                time.sleep(2)

            browser.close()

        return videos[:max_results]

    def _extract_videos_from_page(self, page) -> list[dict]:
        """Extract video info from search results page."""
        videos = []
        html = page.content()

        # Find video IDs
        video_ids = set()
        for m in re.finditer(r'/video/(\d{15,})', html):
            video_ids.add(m.group(1))
        for m in re.finditer(r'modal_id=(\d{15,})', html):
            video_ids.add(m.group(1))

        # Try to extract metadata from page elements
        cards = page.query_selector_all(
            '[data-e2e="scroll-list"] > div, '
            '.search-result-card, '
            '[class*="VideoList"] > div, '
            'ul[class*="list"] > li'
        )

        for card in cards:
            try:
                # Find video link
                link = card.query_selector('a[href*="/video/"]')
                if not link:
                    continue
                href = link.get_attribute("href") or ""
                m = re.search(r'/video/(\d+)', href)
                if not m:
                    continue

                vid = m.group(1)
                url = f"https://www.douyin.com/video/{vid}"

                # Extract metadata
                title = ""
                title_el = card.query_selector(
                    '[class*="title"], [class*="desc"], p, span'
                )
                if title_el:
                    title = title_el.inner_text().strip()[:100]

                # Extract stats (likes, etc)
                stats = self._extract_stats(card)

                videos.append({
                    "url": url,
                    "video_id": vid,
                    "title": title,
                    **stats,
                })
            except Exception:
                continue

        # Fallback: if no cards found, just use video IDs from HTML
        if not videos and video_ids:
            for vid in video_ids:
                videos.append({
                    "url": f"https://www.douyin.com/video/{vid}",
                    "video_id": vid,
                    "title": "",
                    "likes": 0,
                    "comments": 0,
                    "shares": 0,
                    "author": "",
                })

        return videos

    def _extract_stats(self, card) -> dict:
        """Try to extract like/comment/share counts from a card element."""
        stats = {"likes": 0, "comments": 0, "shares": 0, "author": ""}

        try:
            text = card.inner_text()
            # Parse numbers like "1.2w" (万=10k), "3456"
            numbers = re.findall(r'([\d.]+[wW万kK]?)', text)
            parsed = [self._parse_count(n) for n in numbers[:3]]
            if len(parsed) >= 1:
                stats["likes"] = parsed[0]
            if len(parsed) >= 2:
                stats["comments"] = parsed[1]

            # Author
            author_el = card.query_selector('[class*="author"], [class*="nickname"]')
            if author_el:
                stats["author"] = author_el.inner_text().strip()[:30]
        except Exception:
            pass

        return stats

    def _parse_count(self, text: str) -> int:
        """Parse '1.2w' -> 12000, '3.4k' -> 3400, '5678' -> 5678."""
        text = text.strip().lower()
        try:
            if text.endswith(("w", "万")):
                return int(float(text[:-1]) * 10000)
            elif text.endswith("k"):
                return int(float(text[:-1]) * 1000)
            else:
                return int(float(text))
        except (ValueError, IndexError):
            return 0
