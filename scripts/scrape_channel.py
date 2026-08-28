"""
Scrape all video URLs from a Douyin channel using your real Chrome browser.

Usage:
    1. CLOSE Chrome completely first
    2. Run: python scripts/scrape_channel.py "https://www.douyin.com/user/xxx"
    3. Chrome will open -> solve captcha if needed -> script auto-scrolls and collects URLs

Options:
    --max N          Max videos to scrape (default: all)
    --lang vi,en     Auto-translate after scraping
    --download-only  Only download, don't translate
"""
import sys
import io
import re
import time
import argparse
from pathlib import Path

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def scrape_with_real_chrome(profile_url: str, max_videos: int = 0) -> list[str]:
    """Open real Chrome, navigate to profile, scroll and collect video URLs."""
    from playwright.sync_api import sync_playwright

    # Chrome user data dir - uses your real login/cookies
    chrome_path = "C:/Program Files/Google/Chrome/Application/chrome.exe"
    user_data = Path.home() / "AppData" / "Local" / "Google" / "Chrome" / "User Data"

    with sync_playwright() as p:
        # Launch with real Chrome profile
        browser = p.chromium.launch_persistent_context(
            user_data_dir=str(user_data / "DouyinScraper"),  # Separate profile to avoid conflicts
            executable_path=chrome_path if Path(chrome_path).exists() else None,
            headless=False,
            args=["--disable-blink-features=AutomationControlled"],
        )

        page = browser.pages[0] if browser.pages else browser.new_page()
        print(f"Opening: {profile_url}")
        page.goto(profile_url, timeout=60000)

        # Wait for user to solve captcha if needed
        print("Waiting for page to load (solve captcha if prompted)...")
        for _ in range(30):  # Wait up to 60s
            time.sleep(2)
            try:
                title = page.title()
                if "验证" not in title and "captcha" not in title.lower():
                    break
            except Exception:
                continue  # Page navigating, retry

        print("Page loaded. Scrolling to collect videos...")
        time.sleep(3)

        video_urls = set()
        last_count = 0
        no_change_rounds = 0

        while True:
            html = page.content()

            # Collect video IDs from multiple sources
            for m in re.finditer(r'/video/(\d{15,})', html):
                video_urls.add(m.group(1))
            for m in re.finditer(r'modal_id=(\d{15,})', html):
                video_urls.add(m.group(1))
            for m in re.finditer(r'"awemeId"\s*:\s*"(\d{15,})"', html):
                video_urls.add(m.group(1))
            for m in re.finditer(r'/note/(\d{15,})', html):
                video_urls.add(m.group(1))

            current_count = len(video_urls)
            print(f"  Found {current_count} videos...", end="\r")

            if max_videos > 0 and current_count >= max_videos:
                break

            if current_count == last_count:
                no_change_rounds += 1
                if no_change_rounds >= 5:
                    break
            else:
                no_change_rounds = 0
                last_count = current_count

            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(2)

        browser.close()

    urls = [f"https://www.douyin.com/video/{vid}" for vid in sorted(video_urls)]
    if max_videos > 0:
        urls = urls[:max_videos]

    print(f"\nTotal: {len(urls)} videos found")
    return urls


def main():
    parser = argparse.ArgumentParser(description="Scrape Douyin channel videos")
    parser.add_argument("url", help="Douyin user profile URL")
    parser.add_argument("--max", type=int, default=0, help="Max videos (0=all)")
    parser.add_argument("--lang", default="vi", help="Target languages (comma-separated)")
    parser.add_argument("--download-only", action="store_true", help="Only download")
    parser.add_argument("--translate", action="store_true", help="Auto translate after scraping")
    args = parser.parse_args()

    # Scrape
    urls = scrape_with_real_chrome(args.url, args.max)

    if not urls:
        print("No videos found!")
        return

    # Save URL list
    output_file = Path("workspace/downloads/channel_urls.txt")
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, "w", encoding="utf-8") as f:
        for url in urls:
            f.write(f"{url}\n")
    print(f"Saved: {output_file}")

    # Auto-process if requested
    if args.translate or args.download_only:
        from src.pipeline import Pipeline
        pipeline = Pipeline("config/default.yaml")
        langs = [l.strip() for l in args.lang.split(",")]

        if args.download_only:
            from src.steps.downloader import Downloader
            dl = Downloader(pipeline.config, pipeline.work_dir)
            for i, url in enumerate(urls, 1):
                try:
                    r = dl.run(url=url)
                    print(f"  [{i}/{len(urls)}] OK: {r['video_path'].name}")
                except Exception as e:
                    print(f"  [{i}/{len(urls)}] FAIL: {e}")
        else:
            results = pipeline.run_batch(urls, langs)
            ok = sum(1 for r in results if r["status"] == "success")
            print(f"\nDone: {ok}/{len(results)} succeeded")
    else:
        print(f"\nTo translate: python scripts/run.py --batch {output_file} --lang {args.lang}")


if __name__ == "__main__":
    main()
