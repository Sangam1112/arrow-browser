#!/bin/bash
# Build script to produce a .deb package for Ubuntu/Debian.
#
# Built by hand with ar/tar (the .deb format itself — see man 5 deb)
# instead of dpkg-deb, so it works on machines that don't have the dpkg
# tools installed (e.g. this repo's own Fedora dev machine). The output
# is a standard binary .deb either way; nothing about the resulting file
# format depends on which tool built it.
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Refresh the updater checksum in package.json before packaging
bash tools/update-checksum.sh
python3 tools/check-version.py

VERSION="$(python3 -c 'import json; print(json.load(open("package.json"))["version"])')"
PKG_NAME="arrow-browser"
OUTPUT_DIR="${OUTPUT_DIR:-$HOME/Downloads}"
# A fresh private folder (not a fixed /tmp name another local user could create or swap first), made
# world-readable like the package tree it holds.
BUILD_ROOT="$(mktemp -d)"
DEB_ROOT="$(mktemp -d)"
chmod 755 "$BUILD_ROOT"
trap 'rm -rf "$BUILD_ROOT" "$DEB_ROOT"' EXIT

echo "Building .deb package for ${PKG_NAME} v${VERSION}..."

mkdir -p "${BUILD_ROOT}/usr/share/arrow-browser/assets"
mkdir -p "${BUILD_ROOT}/usr/bin"
mkdir -p "${BUILD_ROOT}/usr/share/applications"
mkdir -p "${BUILD_ROOT}/usr/share/icons/hicolor/256x256/apps"
mkdir -p "${BUILD_ROOT}/DEBIAN"

cp arrow_browser.py "${BUILD_ROOT}/usr/share/arrow-browser/"
cp -r assets/* "${BUILD_ROOT}/usr/share/arrow-browser/assets/"
cp arrow-browser "${BUILD_ROOT}/usr/bin/arrow-browser"
cp arrow-browser.desktop "${BUILD_ROOT}/usr/share/applications/"
cp assets/arrow_icon.png "${BUILD_ROOT}/usr/share/icons/hicolor/256x256/apps/arrow-browser.png"
mkdir -p "${BUILD_ROOT}/usr/share/doc/arrow-browser"
cp LICENSE "${BUILD_ROOT}/usr/share/doc/arrow-browser/copyright"  # the GPL goes with every copy

chmod +x "${BUILD_ROOT}/usr/bin/arrow-browser" "${BUILD_ROOT}/usr/share/arrow-browser/arrow_browser.py"
# The command before the rename keeps working (menu entries, scripts, wrappers that call it).
ln -s arrow-browser "${BUILD_ROOT}/usr/bin/bharat-browser"

# Installed size in KiB, as the control file's Installed-Size field expects.
INSTALLED_SIZE_KB=$(du -sk "$BUILD_ROOT" --exclude="$BUILD_ROOT/DEBIAN" | cut -f1)

cat <<EOF > "${BUILD_ROOT}/DEBIAN/control"
Package: arrow-browser
Version: ${VERSION}
Section: web
Priority: optional
Architecture: all
Installed-Size: ${INSTALLED_SIZE_KB}
Depends: python3, python3-gi, python3-gi-cairo, gir1.2-gtk-3.0, gir1.2-webkit2-4.1 | gir1.2-webkit2-4.0
Suggests: gnome-keyring | keepassxc | kwalletmanager, hunspell-en-us | hunspell-en-gb
Provides: bharat-browser
Replaces: bharat-browser
Conflicts: bharat-browser
Maintainer: Arrow Browser Developer <Sangam1112@users.noreply.github.com>
Homepage: https://github.com/Sangam1112/arrow-browser
Description: Modern, Ultra-Fast, and Privacy-First Web Browser
 Arrow Browser is a modern, high-performance web browser designed with
 strict security, privacy protection, and site compatibility at its core.
 GTK3 + WebKit2GTK desktop application with a custom ad/tracker blocklist,
 tracking-parameter stripping, HTTPS upgrading, and a DarkReader-style
 dark mode, all built in-house.
EOF

# Precompile on install so launches don't recompile arrow_browser.py each time (~0.25 s): users can't write
# a __pycache__ into /usr/share themselves. A failure here must never fail the install.
cat <<'EOF' > "${BUILD_ROOT}/DEBIAN/postinst"
#!/bin/sh
python3 -m py_compile /usr/share/arrow-browser/arrow_browser.py >/dev/null 2>&1 || true
exit 0
EOF
cat <<'EOF' > "${BUILD_ROOT}/DEBIAN/prerm"
#!/bin/sh
rm -rf /usr/share/arrow-browser/__pycache__
exit 0
EOF
chmod 755 "${BUILD_ROOT}/DEBIAN/postinst" "${BUILD_ROOT}/DEBIAN/prerm"


echo "2.0" > "${DEB_ROOT}/debian-binary"

# --numeric-owner + --owner=0 --group=0: fake root:root ownership in the
# archive metadata without actually needing to be root to build this.
tar --numeric-owner --owner=0 --group=0 -czf "${DEB_ROOT}/control.tar.gz" -C "${BUILD_ROOT}/DEBIAN" .
tar --numeric-owner --owner=0 --group=0 -czf "${DEB_ROOT}/data.tar.gz" \
    -C "$BUILD_ROOT" --exclude="./DEBIAN" .

mkdir -p "$OUTPUT_DIR"
DEB_FILE="${OUTPUT_DIR}/arrow-browser_${VERSION}-1_all.deb"
rm -f "$DEB_FILE"

# Debian binary package format: an ar archive of exactly these three
# members, in this order (see `man 5 deb`).
(cd "$DEB_ROOT" && ar rc "$DEB_FILE" debian-binary control.tar.gz data.tar.gz)

echo "Built: ${DEB_FILE}"

# Copy into the repo root too, matching how build-rpm.sh's tarball lands
# next to the source when run with OUTPUT_DIR set to the repo itself.
if [ "$OUTPUT_DIR" != "$SCRIPT_DIR" ]; then
    cp "$DEB_FILE" "$SCRIPT_DIR/"
fi

rm -rf "$BUILD_ROOT" "$DEB_ROOT"
echo "Done."
