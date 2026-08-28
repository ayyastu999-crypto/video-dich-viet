"""
Supervisor: Process manager cho Web UI.

Tự động khởi động lại Web UI nếu sập, xóa process Python cũ trên port 7860,
xoay vòng log (10MB/file, giữ 5 file), tắt mềm khi nhấn Ctrl+C.

Usage:
    python scripts/supervisor.py
    python scripts/supervisor.py --port 7860 --check-interval 30
"""
from __future__ import annotations

import argparse
import io
import os
import signal
import socket
import subprocess
import sys
import time
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path

import logging

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
LOG_DIR = ROOT / "workspace" / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
SUP_LOG = LOG_DIR / "supervisor.log"
WEB_OUT_LOG = LOG_DIR / "web_ui.log"

# Logger với rotation 10MB / 5 file
logger = logging.getLogger("supervisor")
logger.setLevel(logging.INFO)
handler = RotatingFileHandler(SUP_LOG, maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8")
handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
logger.addHandler(handler)
console = logging.StreamHandler()
console.setFormatter(logging.Formatter("[%(asctime)s] %(message)s", "%H:%M:%S"))
logger.addHandler(console)


_shutdown = False


def is_port_listening(port: int, host: str = "127.0.0.1", timeout: float = 2.0) -> bool:
    """Kiểm tra port có đang lắng nghe không."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except (OSError, ConnectionRefusedError):
        return False


def kill_port_windows(port: int) -> int:
    """Giải phóng port trên Windows. Trả về số process bị kill."""
    killed = 0
    try:
        out = subprocess.check_output(
            ["netstat", "-ano", "-p", "TCP"],
            stderr=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            errors="ignore",
        )
    except Exception as e:
        logger.warning("netstat thất bại: %s", e)
        return 0

    pids: set[str] = set()
    needle = f":{port} "
    for line in out.splitlines():
        if needle in line and "LISTENING" in line.upper():
            parts = line.split()
            if parts and parts[-1].isdigit():
                pids.add(parts[-1])

    for pid in pids:
        try:
            subprocess.run(
                ["taskkill", "/F", "/PID", pid],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            killed += 1
            logger.info("Đã kill PID %s đang giữ port %d", pid, port)
        except Exception as e:
            logger.warning("Không kill được PID %s: %s", pid, e)
    return killed


def open_log_writer() -> io.TextIOWrapper:
    """Mở log Web UI có rotation thủ công."""
    if WEB_OUT_LOG.exists() and WEB_OUT_LOG.stat().st_size > 10 * 1024 * 1024:
        # rotate: web_ui.log.5 bị xóa, dồn xuống
        for i in range(5, 0, -1):
            src = WEB_OUT_LOG.with_suffix(f".log.{i}")
            dst = WEB_OUT_LOG.with_suffix(f".log.{i + 1}")
            if i == 5 and src.exists():
                src.unlink(missing_ok=True)
            elif src.exists():
                src.replace(dst)
        WEB_OUT_LOG.replace(WEB_OUT_LOG.with_suffix(".log.1"))
    return open(WEB_OUT_LOG, "ab", buffering=0)


def start_web_ui(port: int) -> subprocess.Popen:
    """Khởi động Web UI trong subprocess."""
    log_fp = open_log_writer()
    cmd = [sys.executable, "-u", str(ROOT / "scripts" / "run_web.py"),
           "--port", str(port), "--no-browser"]
    logger.info("Khởi động Web UI: %s", " ".join(cmd))
    creationflags = 0
    if sys.platform == "win32":
        creationflags = subprocess.CREATE_NEW_PROCESS_GROUP  # type: ignore[attr-defined]
    proc = subprocess.Popen(
        cmd,
        cwd=str(ROOT),
        stdout=log_fp,
        stderr=subprocess.STDOUT,
        creationflags=creationflags,
    )
    return proc


def stop_process(proc: subprocess.Popen, timeout: float = 10.0) -> None:
    """Tắt mềm process, nếu quá hạn thì kill cứng."""
    if proc.poll() is not None:
        return
    logger.info("Đang dừng process PID=%d ...", proc.pid)
    try:
        if sys.platform == "win32":
            proc.send_signal(signal.CTRL_BREAK_EVENT)  # type: ignore[attr-defined]
        else:
            proc.terminate()
    except Exception as e:
        logger.warning("send_signal lỗi: %s", e)

    deadline = time.time() + timeout
    while time.time() < deadline and proc.poll() is None:
        time.sleep(0.5)
    if proc.poll() is None:
        logger.warning("Quá hạn — kill cứng PID=%d", proc.pid)
        proc.kill()


def handle_signal(signum, frame):
    global _shutdown
    _shutdown = True
    logger.info("Nhận tín hiệu %s — yêu cầu dừng.", signum)


def main() -> int:
    parser = argparse.ArgumentParser(description="Supervisor cho Web UI Douyin Pipeline")
    parser.add_argument("--port", type=int, default=7860)
    parser.add_argument("--check-interval", type=int, default=30, help="Giây giữa mỗi lần kiểm tra")
    parser.add_argument("--startup-grace", type=int, default=45, help="Giây chờ khởi động xong")
    parser.add_argument("--max-restarts", type=int, default=0, help="0 = không giới hạn")
    args = parser.parse_args()

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    logger.info("=== Supervisor khởi động (port=%d) ===", args.port)

    # Dọn port cũ trước
    if is_port_listening(args.port):
        logger.warning("Port %d đang bận — dọn process cũ", args.port)
        kill_port_windows(args.port)
        time.sleep(2)

    proc = start_web_ui(args.port)
    started_at = time.time()
    restart_count = 0

    try:
        while not _shutdown:
            time.sleep(args.check_interval)
            if _shutdown:
                break

            # 1) Process đã chết?
            if proc.poll() is not None:
                logger.error("Web UI dừng (returncode=%s)", proc.returncode)
                if args.max_restarts and restart_count >= args.max_restarts:
                    logger.error("Đã đạt giới hạn restart (%d) — thoát.", args.max_restarts)
                    return 1
                restart_count += 1
                logger.info("Khởi động lại lần %d ...", restart_count)
                kill_port_windows(args.port)
                time.sleep(2)
                proc = start_web_ui(args.port)
                started_at = time.time()
                continue

            # 2) Còn trong thời gian khởi động → bỏ qua kiểm tra port
            if time.time() - started_at < args.startup_grace:
                continue

            # 3) Process còn sống nhưng port không listen → restart
            if not is_port_listening(args.port):
                logger.error("Port %d không phản hồi — khởi động lại Web UI", args.port)
                stop_process(proc)
                kill_port_windows(args.port)
                time.sleep(2)
                if args.max_restarts and restart_count >= args.max_restarts:
                    logger.error("Đã đạt giới hạn restart — thoát.")
                    return 1
                restart_count += 1
                proc = start_web_ui(args.port)
                started_at = time.time()
            else:
                logger.debug("Khoẻ — port %d OK, PID=%d", args.port, proc.pid)
    finally:
        logger.info("=== Supervisor tắt — dọn dẹp ===")
        stop_process(proc)
        kill_port_windows(args.port)

    return 0


if __name__ == "__main__":
    sys.exit(main())
