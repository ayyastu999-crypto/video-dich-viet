"""
Search Douyin videos by keyword and optionally translate the best ones.

Usage:
    # Search top 10 popular videos about "design"
    python scripts/search_douyin.py "设计教程" --max 10

    # Search newest videos
    python scripts/search_douyin.py "美食" --max 5 --sort new

    # Search + auto translate
    python scripts/search_douyin.py "动漫海报" --max 5 --translate --lang vi

    # Search + download only
    python scripts/search_douyin.py "穿搭" --max 10 --download-only
"""
import sys
import io
import argparse
from pathlib import Path

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def main():
    parser = argparse.ArgumentParser(
        description="Search Douyin videos by keyword",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("keyword", help="Search keyword (Chinese or English)")
    parser.add_argument("--max", type=int, default=10,
                        help="Max results (default: 10)")
    parser.add_argument("--sort", choices=["popular", "new", "default"],
                        default="popular",
                        help="Sort: popular (most liked), new, default (relevance)")
    parser.add_argument("--translate", action="store_true",
                        help="Auto translate found videos")
    parser.add_argument("--download-only", action="store_true",
                        help="Only download, don't translate")
    parser.add_argument("--lang", default="vi",
                        help="Target language(s), comma-separated (default: vi)")
    args = parser.parse_args()

    from src.config import load_config
    from src.steps.keyword_search import KeywordSearch

    config = load_config("config/default.yaml")
    searcher = KeywordSearch(config, Path("workspace"))
    result = searcher.run(
        keyword=args.keyword,
        max_results=args.max,
        sort=args.sort,
    )

    videos = result["videos"]
    if not videos:
        print("No videos found!")
        return

    # Display results
    print(f"\n{'='*70}")
    print(f"  Search: '{args.keyword}' | Sort: {args.sort} | Found: {len(videos)}")
    print(f"{'='*70}\n")

    for i, v in enumerate(videos, 1):
        likes = f"{v['likes']:,}" if v['likes'] else "?"
        title = v['title'][:50] or "(no title)"
        author = v.get('author', '')
        print(f"  {i:2d}. [{likes} likes] {title}")
        if author:
            print(f"      by @{author}")
        print(f"      {v['url']}")
        print()

    print(f"URL list: {result['url_file']}")
    print(f"Full data: {result['results_file']}")

    # Auto-process if requested
    if args.translate or args.download_only:
        from src.pipeline import Pipeline
        pipeline = Pipeline("config/default.yaml")
        langs = [l.strip() for l in args.lang.split(",")]
        urls = [v["url"] for v in videos]

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
            print(f"\nDone: {ok}/{len(results)} translated")
    else:
        print(f"\nTo translate: python scripts/run.py --batch {result['url_file']} --lang vi")


if __name__ == "__main__":
    main()
