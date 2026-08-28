"""
Tiện ích dùng chung cho lớp remediation: ANSI màu, logger, đường dẫn workspace.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# ANSI colour helpers (no external deps)
# ---------------------------------------------------------------------------
class C:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"

    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"
    GREY = "\033[90m"


def colour(text: str, code: str) -> str:
    return f"{code}{text}{C.RESET}"


def ok(text: str) -> str:
    return colour(f"[OK]    {text}", C.GREEN)


def warn(text: str) -> str:
    return colour(f"[WARN]  {text}", C.YELLOW)


def err(text: str) -> str:
    return colour(f"[ERROR] {text}", C.RED)


def info(text: str) -> str:
    return colour(f"[INFO]  {text}", C.CYAN)


def head(text: str) -> str:
    return colour(text, C.BOLD + C.MAGENTA)


# ---------------------------------------------------------------------------
# Workspace paths
# ---------------------------------------------------------------------------
def workspace_root(work_dir: Path | str | None = None) -> Path:
    """Return absolute path to workspace root."""
    if work_dir is None:
        return Path.cwd() / "workspace"
    return Path(work_dir)


def logs_dir(work_dir: Path | str | None = None) -> Path:
    p = workspace_root(work_dir) / "logs"
    p.mkdir(parents=True, exist_ok=True)
    return p


def quarantine_dir(work_dir: Path | str | None = None) -> Path:
    p = workspace_root(work_dir) / "quarantine"
    p.mkdir(parents=True, exist_ok=True)
    return p


# ---------------------------------------------------------------------------
# Structured audit logger
# ---------------------------------------------------------------------------
_LOGGERS: dict[str, logging.Logger] = {}


def get_logger(name: str = "healer", work_dir: Path | str | None = None) -> logging.Logger:
    """Return a singleton logger that writes to workspace/logs/<name>.log."""
    if name in _LOGGERS:
        return _LOGGERS[name]

    log_path = logs_dir(work_dir) / f"{name}.log"
    logger = logging.getLogger(f"remediation.{name}")
    logger.setLevel(logging.INFO)
    logger.propagate = False

    if not logger.handlers:
        fh = logging.FileHandler(log_path, encoding="utf-8")
        fh.setFormatter(logging.Formatter(
            "%(asctime)s [%(levelname)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        ))
        logger.addHandler(fh)

    _LOGGERS[name] = logger
    return logger


def audit(action: str, payload: dict[str, Any], work_dir: Path | str | None = None) -> None:
    """Append a tamper-evident JSON line to the audit log."""
    record = {
        "ts": datetime.utcnow().isoformat() + "Z",
        "action": action,
        **payload,
    }
    audit_path = logs_dir(work_dir) / "audit.jsonl"
    with audit_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def safe_size(path: Path) -> int:
    try:
        return path.stat().st_size
    except OSError:
        return 0


def utc_now_iso() -> str:
    return datetime.utcnow().isoformat() + "Z"
