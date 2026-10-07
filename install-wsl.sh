#!/bin/bash
# Installation script for Arrow Browser inside WSL2 (Ubuntu/Debian) on Windows 11.
# For native Ubuntu/Debian Linux (not WSL), use install-ubuntu.sh instead —
# same dependencies, but with desktop-shortcut/icon registration, which WSLg
# doesn't need since it launches straight from the command this script installs.
#
# Windows 11 ships WSLg, which runs Linux GUI apps side-by-side with Windows
# apps (its own taskbar entry, no separate VM window). Arrow Browser is a
# GTK3 + WebKit2GTK app with no native Windows build of its rendering engine,
# so this runs the real, unmodified app inside WSL2 instead of a native port.
#
# One-time setup on the Windows 11 side (run in PowerShell, not in here):
#   wsl --install -d Ubuntu
# then reboot if prompted, open "Ubuntu" from the Start menu once to finish
# first-run setup (pick a username/password), and run this script inside it.
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=========================================="
echo "Installing Arrow Browser (WSL2 / Windows 11)"
echo "=========================================="

if ! grep -qi microsoft /proc/version 2>/dev/null; then
    echo "Note: this doesn't look like a WSL environment, continuing anyway."
fi

echo "[1/3] Installing dependencies via apt..."
sudo apt-get update
sudo apt-get install -y python3 python3-gi python3-gi-cairo gir1.2-gtk-3.0 git

# gir1.2-webkit2-4.1 is the current package on 24.04, and was also
# confirmed present via point-release updates on 22.04 (tested in a real
# Ubuntu 22.04 container); fall back to the older gir1.2-webkit2-4.0 name
# only if 4.1 genuinely isn't available.
if apt-cache show gir1.2-webkit2-4.1 >/dev/null 2>&1; then
    sudo apt-get install -y gir1.2-webkit2-4.1
else
    sudo apt-get install -y gir1.2-webkit2-4.0
fi

INSTALL_DIR="${HOME}/.local/share/arrow-browser"
BIN_DIR="${HOME}/.local/bin"

echo "[2/3] Installing to ${INSTALL_DIR}..."
mkdir -p "$INSTALL_DIR/assets" "$BIN_DIR"
cp arrow_browser.py "$INSTALL_DIR/"
if [ -d "assets" ]; then
    cp -r assets/* "$INSTALL_DIR/assets/"
fi
chmod +x "$INSTALL_DIR/arrow_browser.py"

cat << 'EOF' > "$BIN_DIR/arrow-browser"
#!/bin/bash
# Start through an import so Python reuses the compiled code it keeps in __pycache__: running
# arrow_browser.py directly would recompile all of it on every launch (~0.25 s).
run() { exec python3 -c 'import runpy, sys; sys.path.insert(0, sys.argv.pop(1)); runpy.run_module("arrow_browser", run_name="__main__", alter_sys=True)' "$@"; }
if [ -f "${HOME}/.local/share/arrow-browser/arrow_browser.py" ]; then
    run "${HOME}/.local/share/arrow-browser" "$@"
else
    echo "arrow-browser: no installed copy found in ~/.local/share/arrow-browser." >&2
    echo "Reinstall Arrow Browser from https://github.com/Sangam1112/arrow-browser/releases" >&2
    exit 1
fi
EOF
chmod +x "$BIN_DIR/arrow-browser"
# Called Bharat Browser up to 1.5.19: the old command keeps working.
if [ -e "$BIN_DIR/bharat-browser" ] || [ -L "$BIN_DIR/bharat-browser" ]; then
    ln -sf arrow-browser "$BIN_DIR/bharat-browser"
fi

echo "[3/3] Done."
echo "=========================================="
echo "Arrow Browser installed for WSLg."
echo "Run it with:  ${BIN_DIR}/arrow-browser"
echo "(add \"export PATH=\\\"\$HOME/.local/bin:\$PATH\\\"\" to ~/.bashrc if the"
echo " \"arrow-browser\" command isn't found in new terminals)"
echo "It will open as its own window on the Windows 11 desktop via WSLg."
echo "=========================================="
