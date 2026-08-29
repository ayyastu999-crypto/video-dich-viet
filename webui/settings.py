"""Doc/ghi API key trong file .env de nguoi dung nhap thang tren giao dien.

Khong bao gio tra key day du ve trinh duyet - chi tra 4 ky tu cuoi de nguoi dung
nhan ra minh da nhap dung chua.
"""
import io
import os
import re
from pathlib import Path

# Ten hien thi -> ten bien moi truong
KEYS = {
    "gemini": "GEMINI_API_KEY",
    "deepseek": "DEEPSEEK_API_KEY",
    "openai": "OPENAI_API_KEY",
    "revid": "REVIDAPI_KEY",
}


def env_path(root: Path) -> Path:
    return root / ".env"


def mask(value: str) -> str:
    """Che key, chi de lo 4 ky tu cuoi."""
    if not value:
        return ""
    if len(value) <= 8:
        return "*" * len(value)
    return "*" * (len(value) - 4) + value[-4:]


def read_all(root: Path) -> dict:
    """Tra ve {ten: {set: bool, masked: str}} - khong co key that."""
    out = {}
    for name, env_name in KEYS.items():
        val = os.getenv(env_name, "")
        out[name] = {"set": bool(val), "masked": mask(val), "env": env_name}
    return out


def save(root: Path, name: str, value: str) -> bool:
    """Ghi 1 key vao .env va nap luon vao tien trinh dang chay.

    value rong = xoa key do di.
    """
    if name not in KEYS:
        raise ValueError(f"Khong biet key: {name}")
    env_name = KEYS[name]
    value = (value or "").strip()

    path = env_path(root)
    lines = []
    if path.exists():
        lines = io.open(path, encoding="utf-8").read().splitlines()

    pattern = re.compile(r"^" + env_name + r"\s*=")
    lines = [l for l in lines if not pattern.match(l.strip())]
    if value:
        lines.append(f"{env_name}={value}")

    body = "\n".join(l for l in lines if l.strip() or True).strip("\n")
    io.open(path, "w", encoding="utf-8", newline="\n").write(body + "\n" if body else "")

    # Cap nhat tien trinh hien tai de khong phai khoi dong lai server
    if value:
        os.environ[env_name] = value
    else:
        os.environ.pop(env_name, None)
    return True
