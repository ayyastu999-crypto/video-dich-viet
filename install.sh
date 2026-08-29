#!/bin/bash
# Cai dat Video Dich Viet tren macOS bang 1 lenh:
#   curl -fsSL https://raw.githubusercontent.com/ayyastu999-crypto/video-dich-viet/main/install.sh | bash

set -e
REPO="ayyastu999-crypto/video-dich-viet"
DEST="$HOME/video-dich-viet"

echo
echo "  ==================================================="
echo "     CAI DAT: VIDEO DICH VIET  (macOS)"
echo "  ==================================================="
echo
echo "  Se cai vao: $DEST"

if [ -d "$DEST" ]; then
  read -p "  Thu muc da ton tai. Ghi de? (c/k): " OW < /dev/tty
  [ "$OW" = "c" ] || { echo "  Da huy."; exit 0; }
  rm -rf "$DEST"
fi

echo "  [1/3] Dang tai ma nguon..."
TMP=$(mktemp -d)
curl -fsSL "https://github.com/$REPO/archive/refs/heads/main.zip" -o "$TMP/app.zip"

echo "  [2/3] Dang giai nen..."
unzip -q "$TMP/app.zip" -d "$TMP"
mv "$TMP"/*-main "$DEST"
rm -rf "$TMP"
chmod +x "$DEST"/*.command 2>/dev/null || true

echo "  [3/3] Xong phan tai ve."
echo
echo "  ==================================================="
echo "     Da tai ve: $DEST"
echo
echo "     Tiep theo:"
echo "       1. Mo thu muc do trong Finder"
echo "       2. Bam dup 'Cai Dat.command'  (cai thu vien)"
echo "       3. Bam dup 'Dich Video Viet.command'  (chay app)"
echo
echo "     Neu macOS chan file, bam chuot phai > Open > Open."
echo "  ==================================================="
echo
open "$DEST" 2>/dev/null || true
