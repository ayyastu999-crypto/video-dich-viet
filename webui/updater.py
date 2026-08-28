"""Kiem tra va cai ban cap nhat moi tu GitHub.

Nguyen tac: chi thay code, KHONG dung vao thu cua nguoi dung
(.env chua API key, output/ chua ket qua, workspace/, .venv, va file config
da chinh tay). Truoc khi thay deu sao luu de con duong lui.
"""
import io
import json
import shutil
import urllib.request
import zipfile
from datetime import datetime
from pathlib import Path

REPO = "ayyastu999-crypto/video-dich-viet"
BRANCH = "main"
RAW = f"https://raw.githubusercontent.com/{REPO}/{BRANCH}/version.json"
ZIP = f"https://github.com/{REPO}/archive/refs/heads/{BRANCH}.zip"

# Chi nhung thu muc/file nay bi thay khi cap nhat
CODE_DIRS = ["src", "webui", "scripts"]
CODE_FILES = ["requirements-app.txt", "requirements.txt", "requirements-core.txt",
              "Cai Dat.bat", "Dich Video Viet.bat", "HUONG DAN CAI DAT.txt",
              "README.md", "version.json", ".env.example", "install.ps1"]

# Tuyet doi khong dung toi
PROTECTED = {".env", "output", "workspace", ".venv", "models", "cookies.txt"}


def local_version(root: Path) -> dict:
    f = root / "version.json"
    if not f.exists():
        return {"version": "khong ro", "date": ""}
    try:
        return json.loads(f.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return {"version": "khong ro", "date": ""}


def check(root: Path, timeout: int = 12) -> dict:
    """So phien ban dang cai voi ban tren GitHub."""
    cur = local_version(root)
    try:
        # CDN cua raw.githubusercontent cache vai phut -> them tham so ngau nhien
        # va header no-cache, khong thi vua day ban moi len van bao "da moi nhat".
        url = RAW + "?t=" + datetime.now().strftime("%Y%m%d%H%M%S")
        req = urllib.request.Request(url, headers={"Cache-Control": "no-cache",
                                                   "Pragma": "no-cache"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            remote = json.loads(r.read().decode("utf-8"))
    except Exception as e:
        return {"ok": False, "error": f"Khong ket noi duoc GitHub: {e}",
                "current": cur}

    has_update = str(remote.get("version")) != str(cur.get("version"))
    return {"ok": True, "current": cur, "latest": remote,
            "has_update": has_update}


def apply(root: Path, timeout: int = 90) -> dict:
    """Tai ban moi ve va thay code. Tra ve tom tat viec da lam.

    Thu tu an toan: tai -> kiem tra goi hop le -> sao luu -> moi thay.
    Loi o bat ky buoc nao truoc khi thay thi khong dung gi den ban dang chay.
    """
    tmp = root / ".update-tmp"
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir()

    try:
        # 1. Tai
        zip_path = tmp / "new.zip"
        with urllib.request.urlopen(ZIP, timeout=timeout) as r:
            zip_path.write_bytes(r.read())

        # 2. Giai nen
        with zipfile.ZipFile(zip_path) as z:
            z.extractall(tmp)
        inner = next((d for d in tmp.iterdir() if d.is_dir()), None)
        if not inner:
            raise RuntimeError("Goi tai ve khong dung dinh dang")

        # 3. Kiem tra goi that su la app nay, tranh ghi de bang rac
        for must in ("src", "webui", "version.json"):
            if not (inner / must).exists():
                raise RuntimeError(f"Goi tai ve thieu '{must}', huy cap nhat")

        # 4. Sao luu truoc khi thay
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        backup = root / "backup" / stamp
        backup.mkdir(parents=True, exist_ok=True)
        for name in CODE_DIRS + CODE_FILES:
            src = root / name
            if src.exists():
                dest = backup / name
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copytree(src, dest) if src.is_dir() else shutil.copy2(src, dest)

        # 5. Thay code
        replaced = []
        for name in CODE_DIRS:
            new = inner / name
            if not new.exists():
                continue
            assert name not in PROTECTED
            old = root / name
            if old.exists():
                shutil.rmtree(old)
            shutil.copytree(new, old)
            replaced.append(name + "/")
        for name in CODE_FILES:
            new = inner / name
            if new.exists():
                shutil.copy2(new, root / name)
                replaced.append(name)

        # 6. Config: KHONG ghi de vi nguoi dung da chinh tay (crf, font, cong tac).
        #    De ban moi canh ben de ho tu doi chieu.
        config_note = None
        new_cfg = inner / "config" / "default.yaml"
        cur_cfg = root / "config" / "default.yaml"
        if new_cfg.exists():
            if cur_cfg.exists():
                shutil.copy2(new_cfg, root / "config" / "default.yaml.moi")
                config_note = ("Cau hinh cua ban duoc giu nguyen. "
                               "Ban moi luu o config/default.yaml.moi de doi chieu.")
            else:
                cur_cfg.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(new_cfg, cur_cfg)

        ver = local_version(root)
        return {"ok": True, "version": ver.get("version"), "replaced": replaced,
                "backup": str(backup).replace(chr(92), "/"),
                "config_note": config_note,
                "restart_required": True}
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
