"""Tu nhan dien phan cung de cung mot bo code chay duoc ca Windows lan macOS.

Ly do phai co file nay: CPU KHONG ho tro float16 (chi int8, int8_float32,
int16, float32). De nguyen cau hinh cuda/float16 roi chay tren may khong co
NVIDIA la loi ngay tu buoc nhan dang giong noi.

Luu y ve faster-whisper: no chay tren CTranslate2, ma CTranslate2 KHONG ho tro
Metal/MPS cua Apple. Nen tren Mac luon la CPU, ke ca may M-series. Bu lai,
int8 tren chip ARM chay kha nhanh.
"""
import platform


def is_mac() -> bool:
    return platform.system() == "Darwin"


def is_apple_silicon() -> bool:
    return is_mac() and platform.machine() in ("arm64", "aarch64")


def has_cuda() -> bool:
    try:
        import ctranslate2
        return ctranslate2.get_cuda_device_count() > 0
    except Exception:
        return False


def has_mps() -> bool:
    """Metal cua Apple - dung duoc cho torch (demucs), khong dung duoc cho whisper."""
    try:
        import torch
        return bool(torch.backends.mps.is_available())
    except Exception:
        return False


def pick_device(configured: str = "auto") -> str:
    """Chon thiet bi cho faster-whisper.

    'auto' (khuyen dung) -> tu do. Dat cung 'cuda'/'cpu' thi ton trong,
    nhung 'cuda' tren may khong co NVIDIA se tu lui ve cpu de khoi vo.
    """
    want = (configured or "auto").strip().lower()
    if want == "auto":
        return "cuda" if has_cuda() else "cpu"
    if want == "cuda" and not has_cuda():
        return "cpu"
    return want


def pick_compute_type(device: str, configured: str = "auto") -> str:
    """Chon kieu tinh toan hop voi thiet bi.

    Dat float16 tren cpu la sai - cpu khong ho tro. Truong hop do tu doi ve int8.
    """
    want = (configured or "auto").strip().lower()
    if want == "auto":
        return "float16" if device == "cuda" else "int8"
    if device == "cpu" and want in ("float16", "int8_float16", "bfloat16"):
        return "int8"
    return want


def describe() -> str:
    """Mot dong mo ta may, dung de ghi log cho de doi chieu khi co loi."""
    bits = [platform.system(), platform.machine()]
    if has_cuda():
        bits.append("CUDA")
    elif is_apple_silicon():
        bits.append("Apple Silicon" + (" + MPS" if has_mps() else ""))
    else:
        bits.append("CPU")
    return " / ".join(bits)
