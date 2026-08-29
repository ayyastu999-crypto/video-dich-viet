#!/bin/bash
# Ban cho macOS. Bam dup file nay trong Finder de chay app.
# Neu Finder bao "khong co quyen", mo Terminal go:  chmod +x "Dich Video Viet.command"

cd "$(dirname "$0")" || exit 1

if [ ! -x ".venv/bin/python" ]; then
  echo
  echo "  [LOI] Chua co .venv trong thu muc nay."
  echo "  Chay truoc file 'Cai Dat.command'."
  echo
  read -n 1 -s -r -p "  Nhan phim bat ky de dong..."
  exit 1
fi

echo
echo "  ==================================================="
echo "     VIDEO DICH VIET"
echo
echo "     Dia chi:  http://localhost:5177"
echo "     Trinh duyet se tu mo sau vai giay."
echo
echo "     DONG CUA SO NAY = TAT SERVER"
echo "  ==================================================="
echo

# Mo trinh duyet sau 5 giay, chay nen de khong chan server
( sleep 5 && open "http://localhost:5177" ) &

.venv/bin/python -m uvicorn webui.server:app --port 5177

echo
read -n 1 -s -r -p "  Server da dung. Nhan phim bat ky de dong..."
