#!/bin/bash
# Build the Windows installer, bharat-browser-X.Y.Z-windows-setup.exe, with NSIS.
# It wraps the .deb package (installed into Ubuntu on WSL 2), so run ./build-deb.sh and
# ./build-rpm.sh first (tools/check-packages.py checks all the packages before this builds).
# Needs makensis: `sudo apt install nsis`, or set MAKENSIS to its path.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

VERSION="$(python3 -c 'import json; print(json.load(open("package.json"))["version"])')"
DEB="bharat-browser_${VERSION}-1_all.deb"
OUT="bharat-browser-${VERSION}-windows-setup.exe"
MAKENSIS="${MAKENSIS:-makensis}"

[ -f "$DEB" ] || { echo "Missing $DEB: run ./build-deb.sh first."; exit 1; }
command -v "$MAKENSIS" >/dev/null || { echo "makensis not found: sudo apt install nsis (or set MAKENSIS)."; exit 1; }
python3 tools/check-version.py
python3 tools/check-packages.py   # the .deb inside must carry the signed bharat_browser.py

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

# Windows shortcuts need an .ico. Several sizes look sharp in Explorer, the taskbar and the
# Start menu; without Pillow, a single 256 px PNG entry still works (Windows Vista and later).
python3 - assets/bharat_icon.png "$WORK/bharat-browser.ico" <<'PY'
import struct, sys
src, dst = sys.argv[1], sys.argv[2]
try:
    from PIL import Image
    Image.open(src).save(dst, sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
except ImportError:
    png = open(src, "rb").read()
    with open(dst, "wb") as f:
        f.write(struct.pack("<3H4B2H2I", 0, 1, 1, 0, 0, 0, 0, 1, 32, len(png), 22) + png)
PY
sed 's/$/\r/' LICENSE > "$WORK/LICENSE.txt"   # the license page wants Windows line endings

"$MAKENSIS" -V2 -DVERSION="$VERSION" -DDEB="$PWD/$DEB" -DICON="$WORK/bharat-browser.ico" \
    -DLICENSE="$WORK/LICENSE.txt" -DOUTFILE="$PWD/$OUT" windows/bharat-browser-setup.nsi
echo "Built: $OUT ($(du -k "$OUT" | cut -f1) KB)"
