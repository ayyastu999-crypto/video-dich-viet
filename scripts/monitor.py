"""
Monitor: thống kê hệ thống theo thời gian thực.

Hiển thị TUI: GPU, VRAM, CPU, RAM, ổ đĩa, độ sâu hàng đợi pipeline,
số job đang chạy, số lỗi gần đây. Có thể xuất JSON cho dashboard.

Usage:
    python scripts/monitor.py                  # TUI, refresh 2s
    python scripts/monitor.py --interval 5
    python scripts/monitor.py --json out.json  # ghi JSON 1 lần rồi thoát
    python scripts/monitor.py --json out.json --watch  # ghi JSON liên tục
"""
from __future__ import annotations

import argparse
import io
import json
import os
import shutil
import socket
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
WORKSPACE = ROOT / "workspace"
LOG_DIR = WORKSPACE / "logs"
DOWNLOADS = WORKSPACE / "downloads"
OUTPUT = WORKSPACE / "output"

try:
    import psutil  # type: ignore
except ImportError:
    psutil = None  # sẽ báo lỗi rõ trong main


# --------- Thu thập số liệu ---------

def get_gpu_stats() -> list[dict]:
    """Đọc nvidia-smi cho từng GPU."""
    try:
        out = subprocess.check_output(
            [
                "nvidia-smi",
                "--query-gpu=index,name,utilization.gpu,memory.used,memory.total,temperature.gpu",
                "--format=csv,noheader,nounits",
            ],
            text=True,
            stderr=subprocess.DEVNULL,
            timeout=5,
        )
    except (FileNotFoundError, subprocess.SubprocessError):
        return []
    gpus = []
    for line in out.strip().splitlines():
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 6:
            continue
        try:
            gpus.append({
                "index": int(parts[0]),
                "name": parts[1],
                "util_pct": float(parts[2]),
                "vram_used_mb": float(parts[3]),
                "vram_total_mb": float(parts[4]),
                "temp_c": float(parts[5]),
            })
        except ValueError:
            continue
    return gpus


def get_system_stats() -> dict:
    if psutil is None:
        return {}
    vm = psutil.virtual_memory()
    disk = psutil.disk_usage(str(WORKSPACE if WORKSPACE.exists() else ROOT))
    return {
        "cpu_pct": psutil.cpu_percent(interval=0.3),
        "ram_used_gb": round(vm.used / 1e9, 2),
        "ram_total_gb": round(vm.total / 1e9, 2),
        "ram_pct": vm.percent,
        "disk_used_gb": round(disk.used / 1e9, 2),
        "disk_total_gb": round(disk.total / 1e9, 2),
        "disk_pct": disk.percent,
    }


def count_pipeline_state() -> dict:
    """Ước lượng hàng đợi: file urls.txt, downloads chưa xử lý, output đã xong."""
    queue = 0
    urls_file = WORKSPACE / "urls.txt"
    if urls_file.exists():
        try:
            queue = sum(1 for ln in urls_file.read_text(encoding="utf-8", errors="ignore").splitlines()
                        if ln.strip() and not ln.strip().startswith("#"))
        except Exception:
            queue = 0

    downloads = 0
    if DOWNLOADS.exists():
        downloads = sum(1 for p in DOWNLOADS.glob("*.mp4"))

    finished = 0
    if OUTPUT.exists():
        finished = sum(1 for p in OUTPUT.glob("*_captioned.mp4"))

    return {"queue_urls": queue, "downloaded": downloads, "finished": finished}


def count_active_jobs() -> int:
    """Đếm process python liên quan tới pipeline (run*.py)."""
    if psutil is None:
        return 0
    count = 0
    needles = ("run.py", "run_web.py", "test_pipeline", "scrape_channel")
    for p in psutil.process_iter(["name", "cmdline"]):
        try:
            cmd = " ".join(p.info.get("cmdline") or [])
            if any(n in cmd for n in needles):
                count += 1
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return count


def count_recent_errors(window_minutes: int = 60) -> int:
    """Đếm dòng ERROR/Traceback trong logs gần đây."""
    if not LOG_DIR.exists():
        return 0
    cutoff = time.time() - window_minutes * 60
    total = 0
    for log in LOG_DIR.glob("*.log"):
        try:
            if log.stat().st_mtime < cutoff:
                continue
            with open(log, "r", encoding="utf-8", errors="ignore") as f:
                # Đọc tối đa 2MB cuối
                size = log.stat().st_size
                if size > 2 * 1024 * 1024:
                    f.seek(size - 2 * 1024 * 1024)
                    f.readline()
                for line in f:
                    if "ERROR" in line or "Traceback" in line or "CRITICAL" in line:
                        total += 1
        except Exception:
            continue
    return total


def is_web_up(port: int = 7860) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=1):
            return True
    except OSError:
        return False


def collect_all() -> dict:
    return {
        "ts": datetime.now().isoformat(timespec="seconds"),
        "web_ui_up": is_web_up(),
        "system": get_system_stats(),
        "gpus": get_gpu_stats(),
        "pipeline": count_pipeline_state(),
        "active_jobs": count_active_jobs(),
        "errors_last_60min": count_recent_errors(60),
    }


# --------- Trình bày TUI ---------

def bar(pct: float, width: int = 20) -> str:
    pct = max(0.0, min(100.0, pct))
    filled = int(width * pct / 100)
    return "[" + "#" * filled + "-" * (width - filled) + f"] {pct:5.1f}%"


def clear_screen() -> None:
    os.system("cls" if sys.platform == "win32" else "clear")


def render_tui(snap: dict) -> None:
    clear_screen()
    cols = shutil.get_terminal_size((80, 24)).columns
    line = "=" * min(cols, 70)
    print(line)
    print(f"  Douyin Pipeline Monitor — {snap['ts']}")
    print(line)

    web = "ONLINE" if snap["web_ui_up"] else "OFFLINE"
    print(f"  Web UI (port 7860):  {web}")
    print(f"  Job đang chạy:       {snap['active_jobs']}")
    print(f"  Lỗi 60 phút qua:     {snap['errors_last_60min']}")
    print()

    sys_ = snap["system"]
    if sys_:
        print("  --- Hệ thống ---")
        print(f"  CPU   {bar(sys_.get('cpu_pct', 0))}")
        print(f"  RAM   {bar(sys_.get('ram_pct', 0))}  "
              f"{sys_.get('ram_used_gb', 0):.1f}/{sys_.get('ram_total_gb', 0):.1f} GB")
        print(f"  Disk  {bar(sys_.get('disk_pct', 0))}  "
              f"{sys_.get('disk_used_gb', 0):.1f}/{sys_.get('disk_total_gb', 0):.1f} GB")
    print()

    gpus = snap["gpus"]
    if gpus:
        print("  --- GPU ---")
        for g in gpus:
            vram_pct = g["vram_used_mb"] / g["vram_total_mb"] * 100 if g["vram_total_mb"] else 0
            print(f"  GPU{g['index']} {g['name'][:30]}")
            print(f"        Util  {bar(g['util_pct'])}")
            print(f"        VRAM  {bar(vram_pct)}  "
                  f"{g['vram_used_mb']:.0f}/{g['vram_total_mb']:.0f} MB  "
                  f"({g['temp_c']:.0f}°C)")
    else:
        print("  --- GPU ---  (không phát hiện nvidia-smi)")
    print()

    pl = snap["pipeline"]
    print("  --- Pipeline ---")
    print(f"  URL chờ xử lý:       {pl['queue_urls']}")
    print(f"  Video đã tải:        {pl['downloaded']}")
    print(f"  Video hoàn tất:      {pl['finished']}")
    print(line)
    print("  Ctrl+C để thoát")


def main() -> int:
    parser = argparse.ArgumentParser(description="Theo dõi hệ thống Douyin Pipeline")
    parser.add_argument("--interval", type=float, default=2.0, help="Giây giữa các lần refresh")
    parser.add_argument("--json", type=str, help="Ghi snapshot ra file JSON")
    parser.add_argument("--watch", action="store_true", help="Khi dùng --json: ghi liên tục")
    parser.add_argument("--once", action="store_true", help="Chỉ in TUI 1 lần rồi thoát")
    args = parser.parse_args()

    if psutil is None:
        print("Cần cài: pip install psutil", file=sys.stderr)
        return 2

    try:
        while True:
            snap = collect_all()
            if args.json:
                Path(args.json).write_text(json.dumps(snap, ensure_ascii=False, indent=2),
                                           encoding="utf-8")
                if not args.watch:
                    print(f"Đã ghi {args.json}")
                    return 0
            else:
                render_tui(snap)
                if args.once:
                    return 0
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print("\nĐã thoát monitor.")
        return 0


if __name__ == "__main__":
    sys.exit(main())
