"""Mo trinh duyet de dang nhap mot lan, app se nho phien do ma dung lai.

Vi sao can: Douyin khong tra noi dung video cho trinh duyet vua mo len chua co
phien nao. Cach hop le la ban tu dang nhap bang tai khoan cua minh, app giu lai
ho so trinh duyet do de lan sau khoi phai lam lai.

Chay:  .venv/Scripts/python.exe scripts/dang_nhap.py
       .venv/Scripts/python.exe scripts/dang_nhap.py --trang instagram
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

# Ho so trinh duyet rieng cua app, khong dung chung voi Chrome cua ban
HO_SO = Path("workspace") / "ho-so-trinh-duyet"

TRANG = {
    "douyin": "https://www.douyin.com/",
    "instagram": "https://www.instagram.com/",
    "facebook": "https://www.facebook.com/",
    "xiaohongshu": "https://www.xiaohongshu.com/",
}


def main():
    ap = argparse.ArgumentParser(description="Dang nhap mot lan de app nho phien")
    ap.add_argument("--trang", default="douyin", choices=sorted(TRANG),
                    help="Trang can dang nhap (mac dinh: douyin)")
    args = ap.parse_args()

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("[LOI] Chua cai playwright. Chay:")
        print("      .venv/Scripts/python.exe -m pip install playwright")
        print("      .venv/Scripts/python.exe -m playwright install chromium")
        return 1

    # Trinh duyet chua tai thi tai luon, khoi bat nguoi dung go lenh
    import subprocess
    try:
        with sync_playwright() as _p:
            _b = _p.chromium.launch(headless=True); _b.close()
    except Exception:
        print("  Lan dau chay - dang tai trinh duyet (khoang 150MB)...")
        subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"])
        print("  Xong.")
        print()

    HO_SO.mkdir(parents=True, exist_ok=True)
    url = TRANG[args.trang]

    print()
    print("  ===============================================")
    print(f"     DANG NHAP: {args.trang}")
    print()
    print("     1. Cua so trinh duyet sap mo ra")
    print("     2. Dang nhap tai khoan cua ban nhu binh thuong")
    print("     3. Dang nhap xong thi quay lai day bam Enter")
    print()
    print(f"     Phien duoc luu tai: {HO_SO}")
    print("  ===============================================")
    print()

    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            user_data_dir=str(HO_SO.resolve()),
            headless=False,                      # phai thay de con dang nhap
            viewport={"width": 1280, "height": 860},
            args=["--disable-blink-features=AutomationControlled"],
        )
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto(url)
        input("  >> Dang nhap xong roi thi bam Enter... ")
        ctx.close()

    print()
    print("  Da luu phien. Gio thu dan lai link vao app.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
