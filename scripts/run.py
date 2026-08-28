"""
Douyin Video Translation Pipeline - CLI Entry Point

Usage:
    # Single video
    python scripts/run.py --url "https://www.douyin.com/video/xxx" --lang vi

    # Multiple languages
    python scripts/run.py --url "https://..." --lang vi,en,ja

    # Batch from file
    python scripts/run.py --batch workspace/urls.txt --lang vi,en

    # Schedule recurring
    python scripts/run.py --schedule "0 8 * * *" --batch workspace/urls.txt --lang vi

    # Download only
    python scripts/run.py --url "https://..." --download-only
"""
import sys
import argparse
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import load_config
from src.utils.ffmpeg import check_ffmpeg


def main():
    parser = argparse.ArgumentParser(
        description="Douyin Video Translation & Dubbing Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--url", help="Douyin video URL to process")
    parser.add_argument("--batch", help="Path to text file with URLs (1 per line)")
    parser.add_argument("--file", help="Video co san tren may (bo qua buoc tai)")
    parser.add_argument("--folder", help="Thu muc chua nhieu video, xu ly lan luot")
    parser.add_argument("--lang", default="vi",
                        help="Target language(s), comma-separated (default: vi)")
    parser.add_argument("--config", default="config/default.yaml",
                        help="Path to config file (default: config/default.yaml)")
    parser.add_argument("--download-only", action="store_true",
                        help="Only download videos, skip translation")
    parser.add_argument("--voice-clone", action="store_true",
                        help="Use F5-TTS voice cloning instead of edge-tts")
    parser.add_argument("--channel", action="store_true",
                        help="Treat --url as channel/profile URL, scrape all videos")
    parser.add_argument("--max-videos", type=int, default=0,
                        help="Max videos to scrape from channel (0 = all)")
    parser.add_argument("--schedule",
                        help="Cron expression for scheduled runs (e.g. '0 8 * * *')")
    parser.add_argument("--check", action="store_true",
                        help="Check system dependencies and exit")

    args = parser.parse_args()
    langs = [l.strip() for l in args.lang.split(",")]

    # Dependency check
    if args.check or not (args.url or args.batch or args.schedule or args.file or args.folder):
        run_checks(args.config)
        if args.check:
            return
        if not (args.url or args.batch or args.schedule or args.file or args.folder):
            parser.print_help()
            return

    from src.pipeline import Pipeline

    pipeline = Pipeline(args.config)

    # Override TTS provider if --voice-clone flag
    if args.voice_clone:
        pipeline.config["tts"]["provider"] = "voice-clone"

    # Channel scrape mode
    if args.channel and args.url:
        from src.steps.channel_scraper import ChannelScraper
        scraper = ChannelScraper(pipeline.config, pipeline.work_dir)
        result = scraper.run(profile_url=args.url, max_videos=args.max_videos)
        urls = result["video_urls"]
        print(f"Found {len(urls)} videos")
        print(f"URL list saved: {result['url_file']}")

        if args.download_only:
            from src.steps.downloader import Downloader
            dl = Downloader(pipeline.config, pipeline.work_dir)
            for i, url in enumerate(urls, 1):
                try:
                    r = dl.run(url=url)
                    print(f"  [{i}/{len(urls)}] Downloaded: {r['video_path']}")
                except Exception as e:
                    print(f"  [{i}/{len(urls)}] Failed: {e}")
            return

        results = pipeline.run_batch(urls, langs)
        success = sum(1 for r in results if r["status"] == "success")
        print(f"\nDone: {success}/{len(results)} succeeded")
        return

    if args.download_only and args.url:
        from src.steps.downloader import Downloader
        dl = Downloader(pipeline.config, pipeline.work_dir)
        result = dl.run(url=args.url)
        print(f"Downloaded: {result['video_path']}")
        return

    if args.schedule:
        if not args.batch:
            print("Error: --schedule requires --batch <url_file>")
            sys.exit(1)
        from src.scheduler.cron import PipelineScheduler
        scheduler = PipelineScheduler(pipeline)
        scheduler.schedule(args.batch, langs, args.schedule)
        scheduler.start()
        return

    if args.folder:
        results = pipeline.run_local_folder(args.folder, langs)
        success = sum(1 for r in results if r["status"] == "success")
        print("")
        print(f"Done: {success}/{len(results)} succeeded")
    elif args.file:
        for lang in langs:
            result = pipeline.run(local_video=args.file, target_lang=lang)
            print(f"Output ({lang}): {result['final_video']}")
            if result.get("script_plain"):
                print(f"Kich ban ({lang}): {result['script_plain']}")
    elif args.batch:
        results = pipeline.run_from_file(args.batch, langs)
        success = sum(1 for r in results if r["status"] == "success")
        print(f"\nDone: {success}/{len(results)} succeeded")
    elif args.url:
        for lang in langs:
            result = pipeline.run(url=args.url, target_lang=lang)
            print(f"Output ({lang}): {result['final_video']}")
    else:
        parser.print_help()


def run_checks(config_path: str):
    """Check system dependencies."""
    print("=== System Dependency Check ===\n")

    # FFmpeg
    if check_ffmpeg():
        print("[OK] FFmpeg found")
    else:
        print("[FAIL] FFmpeg not found. Install: choco install ffmpeg")

    # Config
    try:
        config = load_config(config_path)
        print(f"[OK] Config loaded: {config_path}")
    except FileNotFoundError:
        print(f"[FAIL] Config not found: {config_path}")
        return

    # CUDA
    try:
        import torch
        if torch.cuda.is_available():
            print(f"[OK] CUDA available: {torch.cuda.get_device_name(0)}")
        else:
            print("[WARN] CUDA not available. Will use CPU (slower)")
    except ImportError:
        print("[WARN] PyTorch not installed. GPU check skipped")

    # Cookies
    cookies = config.get("download", {}).get("cookies_file", "cookies.txt")
    if Path(cookies).exists():
        print(f"[OK] Cookies file found: {cookies}")
    else:
        print(f"[WARN] Cookies file not found: {cookies}")
        print("       Run: python scripts/setup_cookies.py")

    # OpenAI key
    import os
    if os.environ.get("OPENAI_API_KEY"):
        print("[OK] OPENAI_API_KEY set")
    else:
        print("[WARN] OPENAI_API_KEY not set. Translation step will fail")

    print("\n=== Check Complete ===")


if __name__ == "__main__":
    main()
