"""Tai video tu link web (RedNote, Douyin, Facebook, Instagram, TikTok...).

Tra ve dung contract nhu LocalSource va Downloader nen cac buoc sau khong phai sua.

Thu tu thu (phuong an C):
  Douyin  -> Playwright truoc (khong can cookie), hong thi yt-dlp + cookie
  Con lai -> yt-dlp thang, hong vi bi chan thi thu lai kem cookie
"""
import subprocess
from pathlib import Path

from src.steps.base import BaseStep
from src.steps.local_source import slugify
from src.utils.video_url import describe, platform_of


class WebSource(BaseStep):
    def run(self, url: str) -> dict:
        info = describe(url)
        plat, real_url = info["platform"], info["url"]

        if info["changed"]:
            self.log(f"Da nan link ({plat}): {real_url}")
        else:
            self.log(f"Nguon: {plat}")

        out_dir = self.ensure_dir("downloads")

        if plat == "douyin":
            try:
                # Phai dua URL DA NAN: Downloader cu chi hieu dang /video/<id>,
                # dua dang feed vao no bóc id ra None roi vo.
                return self._qua_playwright(real_url, out_dir)
            except Exception as e:
                self.log(f"Playwright hong ({type(e).__name__}), chuyen sang yt-dlp...")

        return self._qua_ytdlp(real_url, out_dir, plat)

    # ---------- Douyin: dung lai bo tai san co ----------

    def _qua_playwright(self, url: str, out_dir: Path) -> dict:
        from src.steps.downloader import Downloader

        res = Downloader(self.config, self.work_dir).run(url=url)
        res.setdefault("duration", self._do_thoi_luong(Path(res["video_path"])))
        res.setdefault("video_id", Path(res["video_path"]).stem)
        return res

    # ---------- Con lai: yt-dlp ----------

    def _qua_ytdlp(self, url: str, out_dir: Path, plat: str) -> dict:
        import yt_dlp

        # Thu lan luot: khong cookie -> file cookie -> cookie song trong trinh duyet.
        # Cookie doc thang tu trinh duyet luon moi, khong phai chay script lay tay.
        cach = [("khong", None)]
        f = self._tim_cookie()
        if f:
            cach.append(("file cookie", {"cookiefile": str(f)}))
        for tb in self._trinh_duyet():
            cach.append((f"cookie tu {tb}", {"cookiesfrombrowser": (tb, None, None, None)}))

        loi_cuoi = None
        for ten, opt in cach:
            if opt:
                self.log(f"Thu lai voi {ten}...")
            try:
                return self._tai(yt_dlp, url, out_dir, opt)
            except Exception as e:
                loi_cuoi = e
                if not self._co_the_do_cookie(e):
                    break

        raise RuntimeError(self._giai_thich(loi_cuoi, plat, len(cach) > 1))

    def _tai(self, yt_dlp, url: str, out_dir: Path, them: dict | None) -> dict:
        opts = {
            "outtmpl": str(out_dir / "%(id)s.%(ext)s"),
            "format": "bv*+ba/best",
            "merge_output_format": "mp4",
            "quiet": True,
            "no_warnings": True,
            "noprogress": True,
        }
        if them:
            opts.update(them)

        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            path = Path(ydl.prepare_filename(info))

        # yt-dlp co the doi duoi khi gop luong (vd .webm -> .mp4)
        if not path.exists():
            cung_ten = list(out_dir.glob(path.stem + ".*"))
            if not cung_ten:
                raise FileNotFoundError(f"Tai xong nhung khong thay file: {path}")
            path = cung_ten[0]

        video_id = slugify(info.get("id") or path.stem)
        size_mb = path.stat().st_size / 1024 / 1024
        # Vai trang (vd Instagram Reels) khong tra thoi luong -> tu do tu file
        duration = float(info.get("duration") or 0) or self._do_thoi_luong(path)
        self.log(f"Da tai: {path.name} ({size_mb:.1f} MB, {duration:.0f}s)")

        return {
            "video_path": path,
            "video_id": video_id,
            "duration": duration,
            "metadata": {
                "id": video_id,
                "title": info.get("title") or video_id,
                "description": (info.get("description") or "")[:500],
                "source": info.get("extractor") or "web",
                "original_path": url,
                "uploader": info.get("uploader") or "",
            },
        }

    # ---------- ho tro ----------

    def _tim_cookie(self) -> Path | None:
        name = self.config.get("download", {}).get("cookies_file", "cookies.txt")
        p = Path(name)
        return p if p.exists() and p.stat().st_size > 0 else None

    def _trinh_duyet(self) -> list:
        """Cac trinh duyet co tren may, de yt-dlp doc cookie truc tiep.

        Cach nay luon lay duoc cookie moi nhat, khong phai chay script xuat file
        roi vai thang sau lai het han.
        """
        import os
        import sys

        if sys.platform == "win32":
            la = os.environ.get("LOCALAPPDATA", "")
            ro = os.environ.get("APPDATA", "")
            co = [("chrome", la + r"/Google/Chrome/User Data"),
                  ("edge",   la + r"/Microsoft/Edge/User Data"),
                  ("firefox", ro + r"/Mozilla/Firefox")]
        elif sys.platform == "darwin":
            h = os.path.expanduser("~/Library/Application Support")
            co = [("chrome", h + "/Google/Chrome"),
                  ("edge",   h + "/Microsoft Edge"),
                  ("firefox", h + "/Firefox")]
        else:
            h = os.path.expanduser("~")
            co = [("chrome", h + "/.config/google-chrome"),
                  ("firefox", h + "/.mozilla/firefox")]

        return [ten for ten, duong in co if duong and Path(duong).exists()]

    @staticmethod
    def _co_the_do_cookie(err) -> bool:
        s = str(err).lower()
        return any(t in s for t in ("cookie", "login", "sign in", "private",
                                    "rate-limit", "429", "403", "forbidden"))

    @staticmethod
    def _giai_thich(err, plat: str, co_cookie: bool) -> str:
        """Doi loi kho hieu cua yt-dlp thanh cau nguoi dung lam duoc gi."""
        s = str(err)
        if WebSource._co_the_do_cookie(err):
            if co_cookie:
                return (f"{plat}: cookie hien tai khong dung duoc (co the da het han). "
                        f"Hay nap lai cookie moi tu trinh duyet. Chi tiet: {s[:160]}")
            return (f"{plat}: trang nay doi cookie moi tai duoc, va cookie tren may "
                    f"deu khong dung duoc. Hay mo trang do bang trinh duyet mot lan "
                    f"(dang nhap neu can) roi thu lai. Chi tiet: {s[:150]}")
        if "unsupported url" in s.lower():
            return (f"Khong nhan ra dang link nay. Hay mo video roi copy link tren "
                    f"thanh dia chi, dung copy tu nut chia se. Chi tiet: {s[:160]}")
        return f"Tai that bai ({plat}): {s[:200]}"

    def _do_thoi_luong(self, path: Path) -> float:
        try:
            r = subprocess.run(
                ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
                 "-of", "csv=p=0", str(path)],
                capture_output=True, text=True, timeout=20)
            return float(r.stdout.strip() or 0)
        except (ValueError, subprocess.TimeoutExpired, FileNotFoundError):
            return 0.0
