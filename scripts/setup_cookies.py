"""
Cookie Setup Helper for Douyin

Extracts cookies from your browser for use with yt-dlp.

Usage:
    python scripts/setup_cookies.py                  # Auto-detect Chrome
    python scripts/setup_cookies.py --browser firefox
    python scripts/setup_cookies.py --manual          # Manual cookie.txt paste
"""
import sys
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def extract_from_browser(browser: str, output: str):
    """Extract cookies from browser using yt-dlp."""
    import subprocess
    result = subprocess.run(
        ["yt-dlp", "--cookies-from-browser", browser,
         "--cookies", output,
         "--skip-download", "https://www.douyin.com/"],
        capture_output=True, text=True,
    )
    if result.returncode == 0:
        print(f"[OK] Cookies extracted to {output}")
        print("     Make sure you're logged into Douyin in your browser.")
    else:
        print(f"[FAIL] Could not extract cookies: {result.stderr[:300]}")
        print("\nTry:")
        print("  1. Make sure you're logged into douyin.com in your browser")
        print("  2. Close the browser completely")
        print("  3. Run this script again")
        print(f"\n  Or use: python scripts/setup_cookies.py --manual")


def manual_setup(output: str):
    """Guide user through manual cookie setup."""
    print("=== Manual Cookie Setup ===\n")
    print("1. Open douyin.com in your browser and log in")
    print("2. Install 'Get cookies.txt LOCALLY' browser extension")
    print("3. Export cookies for douyin.com")
    print(f"4. Save the file as: {output}")
    print(f"\nOr paste cookie content below (Ctrl+Z to finish on Windows, Ctrl+D on Linux):")

    try:
        content = sys.stdin.read()
        if content.strip():
            Path(output).write_text(content, encoding="utf-8")
            print(f"\n[OK] Cookies saved to {output}")
        else:
            print("\n[SKIP] No content provided")
    except KeyboardInterrupt:
        print("\n[SKIP] Cancelled")


def main():
    parser = argparse.ArgumentParser(description="Setup cookies for Douyin download")
    parser.add_argument("--browser", default="chrome",
                        help="Browser to extract from (default: chrome)")
    parser.add_argument("--output", default="cookies.txt",
                        help="Output cookie file path (default: cookies.txt)")
    parser.add_argument("--manual", action="store_true",
                        help="Manual cookie paste mode")
    args = parser.parse_args()

    if args.manual:
        manual_setup(args.output)
    else:
        extract_from_browser(args.browser, args.output)


if __name__ == "__main__":
    main()
