#!/bin/bash
# Ban cho macOS. Bam dup file nay de cai thu vien.
cd "$(dirname "$0")" || exit 1

echo
echo "  ==================================================="
echo "     CAI DAT: VIDEO DICH VIET  (macOS)"
echo "  ==================================================="
echo

echo "  [1/4] Kiem tra Python..."
if ! command -v python3 >/dev/null 2>&1; then
  echo "        [LOI] Chua co python3."
  echo "        Cai bang:  brew install python@3.11"
  echo "        Chua co brew thi xem: https://brew.sh"
  read -n 1 -s -r -p "  Nhan phim bat ky de dong..." ; exit 1
fi
echo "        OK - $(python3 --version)"

echo "  [2/4] Kiem tra FFmpeg..."
if ! command -v ffmpeg >/dev/null 2>&1; then
  echo "        [LOI] Chua co ffmpeg. Cai bang:  brew install ffmpeg"
  read -n 1 -s -r -p "  Nhan phim bat ky de dong..." ; exit 1
fi
echo "        OK"

echo "  [3/4] Tao moi truong ao .venv..."
if [ -x ".venv/bin/python" ]; then
  echo "        Da co san, bo qua."
else
  python3 -m venv .venv || { echo "        [LOI] Tao venv that bai."; read -n 1 -s -r; exit 1; }
  echo "        OK"
fi
PY=.venv/bin/python

echo "  [4/4] Cai thu vien... (vai phut)"
$PY -m pip install --quiet --upgrade pip
$PY -m pip install --quiet -r requirements-app.txt || {
  echo "        [LOI] Cai that bai."; read -n 1 -s -r; exit 1; }
echo "        OK"

echo
echo "  Mac khong co card NVIDIA nen bo qua phan GPU."
echo "  Nhan dang giong noi se chay bang CPU - cham hon nhung van chay."
echo
read -p "  Cai them phan tach nhac nen + xoa phu de cu? (c/k): " EXTRA
if [ "$EXTRA" = "c" ]; then
  echo "        Dang cai (torch ban Metal cho Apple Silicon)..."
  $PY -m pip install --quiet torch torchvision torchaudio
  $PY -m pip install --quiet demucs soundfile opencv-python easyocr
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
