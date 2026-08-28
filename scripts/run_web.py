"""
Launch the Douyin Translation Pipeline Web UI.

Usage:
    python scripts/run_web.py
    python scripts/run_web.py --port 8080
    python scripts/run_web.py --share   # Create public URL (ngrok)
"""
import sys
import io
import argparse
from pathlib import Path

# Fix Windows console encoding for Vietnamese
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.web.app import create_app


def main():
    parser = argparse.ArgumentParser(description="Launch Douyin Pipeline Web UI")
    parser.add_argument("--port", type=int, default=7860, help="Port (default: 7860)")
    parser.add_argument("--host", default="0.0.0.0", help="Host (default: 0.0.0.0)")
    parser.add_argument("--share", action="store_true", help="Create public Gradio share URL")
    parser.add_argument("--no-browser", action="store_true", help="Don't open browser")
    args = parser.parse_args()

    app = create_app()

    print(f"\n{'='*60}")
    print(f"  Douyin Dịch Video Pipeline - Web UI")
    print(f"  http://localhost:{args.port}")
    print(f"{'='*60}\n")

    app.launch(
        server_name=args.host,
        server_port=args.port,
        share=args.share,
        inbrowser=not args.no_browser,
        show_error=True,
    )


if __name__ == "__main__":
    main()
