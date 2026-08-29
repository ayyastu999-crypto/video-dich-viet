#!/bin/bash
# Ban cho macOS. Bam dup file nay de cai thu vien.
cd "$(dirname "$0")" || exit 1

die() { echo; echo "  $1"; read -n 1 -s -r -p "  Nhan phim bat ky de dong..."; exit 1; }

echo
echo "  ==================================================="
echo "     CAI DAT: VIDEO DICH VIET  (macOS)"
echo "  ==================================================="
echo

# --- [1/4] Python 3.11+ ---------------------------------------------------
# macOS co san python3 nhung thuong la 3.9, qua cu cho app nay.
# Neu khong tim thay ban 3.11+, dung uv de cai rieng mot ban Python 3.12.
# uv cai vao thu muc nguoi dung, khong can mat khau admin, khong dung
# toi Python cua he thong.
echo "  [1/4] Kiem tra Python..."

py_du_moi() { "$1" -c 'import sys; sys.exit(0 if sys.version_info >= (3,11) else 1)' >/dev/null 2>&1; }

PYBIN=""
for CAND in python3.13 python3.12 python3.11 python3; do
  command -v "$CAND" >/dev/null 2>&1 || continue
  if py_du_moi "$CAND"; then PYBIN="$CAND"; break; fi
done

UV=""
if [ -n "$PYBIN" ]; then
  echo "        OK - $($PYBIN --version)"
else
  echo "        Chua co Python 3.11 tro len."
  if command -v python3 >/dev/null 2>&1; then
    echo "        (dang co $(python3 --version 2>&1), qua cu)"
  fi
  echo "        Se cai rieng Python 3.12 bang uv - khong can mat khau admin."

  if command -v uv >/dev/null 2>&1; then
    UV="$(command -v uv)"
  elif [ -x "$HOME/.local/bin/uv" ]; then
    UV="$HOME/.local/bin/uv"
  else
    echo "        Dang tai uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh >/dev/null 2>&1
    [ -x "$HOME/.local/bin/uv" ] || die "[LOI] Cai uv that bai. Kiem tra mang roi chay lai."
    UV="$HOME/.local/bin/uv"
  fi

  echo "        Dang cai Python 3.12..."
  "$UV" python install 3.12 >/dev/null 2>&1 || die "[LOI] Cai Python 3.12 that bai."
  echo "        OK - Python 3.12"
fi

# --- [2/4] FFmpeg ---------------------------------------------------------
echo "  [2/4] Kiem tra FFmpeg..."
if ! command -v ffmpeg >/dev/null 2>&1; then
  echo "        [LOI] Chua co ffmpeg."
  if command -v brew >/dev/null 2>&1; then
    echo "        Cai bang:  brew install ffmpeg"
  else
    echo "        May chua co Homebrew. Cai Homebrew truoc tai https://brew.sh"
    echo "        roi chay:  brew install ffmpeg"
  fi
  die "Cai xong ffmpeg thi chay lai file nay."
fi
echo "        OK"

# --- [3/4] Moi truong ao --------------------------------------------------
echo "  [3/4] Tao moi truong ao .venv..."
if [ -x ".venv/bin/python" ]; then
  echo "        Da co san, bo qua."
elif [ -n "$UV" ]; then
  "$UV" venv --python 3.12 .venv >/dev/null 2>&1 || die "[LOI] Tao venv that bai."
  echo "        OK"
else
  "$PYBIN" -m venv .venv || die "[LOI] Tao venv that bai."
  echo "        OK"
fi
PY=.venv/bin/python

# uv cai thu vien nhanh hon pip nhieu lan; dung khi co san.
if [ -z "$UV" ]; then
  if command -v uv >/dev/null 2>&1; then UV="$(command -v uv)"
  elif [ -x "$HOME/.local/bin/uv" ]; then UV="$HOME/.local/bin/uv"; fi
fi
cai_thu_vien() {
  if [ -n "$UV" ]; then
    "$UV" pip install --python "$PY" --quiet "$@"
  else
    $PY -m pip install --quiet "$@"
  fi
}

# --- [4/4] Thu vien -------------------------------------------------------
echo "  [4/4] Cai thu vien... (vai phut)"
[ -n "$UV" ] || $PY -m pip install --quiet --upgrade pip
cai_thu_vien -r requirements-app.txt || die "[LOI] Cai that bai."
echo "        OK"

echo
echo "  Mac khong co card NVIDIA nen bo qua phan GPU rieng."
echo "  Nhan dang giong noi chay bang CPU - cham hon nhung van chay."
echo
read -p "  Cai them phan tach nhac nen + xoa phu de cu? (~3GB) (c/k): " EXTRA
if [ "$EXTRA" = "c" ]; then
  echo "        Dang cai (torch ban Metal cho Apple Silicon)..."
  cai_thu_vien torch torchvision torchaudio || die "[LOI] Cai torch that bai."
  cai_thu_vien demucs soundfile opencv-python easyocr || die "[LOI] Cai demucs/easyocr that bai."
  $PY -c "import torch; print('        Metal (MPS):', torch.backends.mps.is_available())"
fi

chmod +x "Dich Video Viet.command" 2>/dev/null

echo
echo "  ==================================================="
echo "     XONG!"
echo
echo "     Chay app: bam dup file 'Dich Video Viet.command'"
echo "     Lan dau mo, nhap API key vao o Cai dat (banh rang)"
echo "     Lay key mien phi: https://aistudio.google.com/apikey"
echo "  ==================================================="
echo
read -n 1 -s -r -p "  Nhan phim bat ky de dong..."
