"""Nhan dien nen tang va nan link ve dung dang ma yt-dlp hieu.

Ly do can file nay: link nguoi dung copy tu trinh duyet thuong KHONG phai dang
ma extractor nhan. Hai vi du that:

  rednote.com/discovery/item/<id>?xsec_token=...
      -> extractor chi khop xiaohongshu.com, cung nen tang khac ten mien
  douyin.com/jingxuan?modal_id=<id>
      -> extractor can dang /video/<id>, day la dang feed

Ca hai deu bao "Unsupported URL" du video tai duoc binh thuong.
"""
import re
from urllib.parse import urlparse, parse_qs, urlencode

# ten mien -> ten nen tang
DOMAINS = [
    (("rednote.com", "xiaohongshu.com", "xhslink.com"), "xiaohongshu"),
    (("douyin.com", "iesdouyin.com"), "douyin"),
    (("tiktok.com",), "tiktok"),
    (("facebook.com", "fb.watch", "fb.com"), "facebook"),
    (("instagram.com", "instagr.am"), "instagram"),
    (("bilibili.com", "b23.tv"), "bilibili"),
    (("youtube.com", "youtu.be"), "youtube"),
]

# Nen tang thuong chan neu khong co cookie
CAN_COOKIE = {"douyin", "facebook", "instagram"}


def is_url(text: str) -> bool:
    return bool(re.match(r"https?://", (text or "").strip(), re.I))


def platform_of(url: str) -> str:
    host = (urlparse(url).hostname or "").lower().lstrip("www.")
    for domains, name in DOMAINS:
        if any(host == d or host.endswith("." + d) for d in domains):
            return name
    return "khac"


def normalize(url: str) -> str:
    """Nan link ve dang extractor hieu. Khong nhan ra dang nao thi tra nguyen."""
    url = (url or "").strip()
    plat = platform_of(url)
    if plat == "xiaohongshu":
        return _xiaohongshu(url)
    if plat == "douyin":
        return _douyin(url)
    return url


def _xiaohongshu(url: str) -> str:
    """rednote.com -> xiaohongshu.com, GIU NGUYEN xsec_token.

    Bo token la trang tra ve loi khong xem duoc, nen phai giu ca query.
    """
    p = urlparse(url)
    host = (p.hostname or "").lower()
    if "rednote.com" in host:
        p = p._replace(netloc="www.xiaohongshu.com")
    return p.geturl()


def _douyin(url: str) -> str:
    """Cac dang feed cua Douyin deu giau id trong query -> doi ve /video/<id>."""
    p = urlparse(url)
    q = parse_qs(p.query)
    # /jingxuan?modal_id=<id>, /discover?modal_id=<id>, /?modal_id=<id>
    for key in ("modal_id", "vid", "aweme_id"):
        if q.get(key):
            return "https://www.douyin.com/video/" + q[key][0]
    # /video/<id> san roi thi bo query cho gon
    m = re.search(r"/video/(\d+)", p.path)
    if m:
        return "https://www.douyin.com/video/" + m.group(1)
    return url


def describe(url: str) -> dict:
    """Tom tat de ghi log va hien tren giao dien."""
    plat = platform_of(url)
    fixed = normalize(url)
    return {
        "platform": plat,
        "url": fixed,
        "changed": fixed != url.strip(),
        "may_need_cookie": plat in CAN_COOKIE,
    }
