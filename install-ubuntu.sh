#!/bin/bash
# Installation script for Arrow Browser on native Ubuntu/Debian Linux
# (System or User mode). For running inside WSL2 on Windows, use
# install-wsl.sh instead — the dependency install is the same, but that
# script skips desktop-shortcut/icon registration since WSLg launches it
# straight from the command it installs.
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=========================================="
echo "Installing Arrow Browser on Ubuntu/Debian Linux"
echo "=========================================="
echo "(Installs to ~/.local by default. Pass --system for a system-wide"
echo " /usr install; you'll be prompted for sudo.)"

USE_SUDO=false
if [ "$EUID" -ne 0 ]; then
    if [ "$1" = "--system" ]; then
        if sudo -v; then
            USE_SUDO=true
        else
            echo "System-wide install requested but sudo authentication failed." >&2
            exit 1
        fi
    fi
    # No silent escalation: passwordless sudo being configured for unrelated
    # reasons shouldn't change this script's behavior from a user-local
    # install to a system-wide one without the user asking for it.
else
    USE_SUDO=true
fi

# apt always needs root regardless of whether the app itself is being
# installed system-wide or to ~/.local; but if we're already root (e.g. a
# minimal container image), "sudo" may not even be installed, so don't
# invoke it unnecessarily in that case (unlike CMD_PREFIX below, this
# doesn't depend on the --system choice).
APT_PREFIX="sudo"
if [ "$EUID" -eq 0 ]; then
    APT_PREFIX=""
fi

echo "[1/4] Installing dependencies via apt..."
$APT_PREFIX apt-get update
$APT_PREFIX apt-get install -y python3 python3-gi python3-gi-cairo gir1.2-gtk-3.0 git

# gir1.2-webkit2-4.1 is the current package on 24.04, and was also
# confirmed present via point-release updates on 22.04 (tested in a real
# Ubuntu 22.04 container); fall back to the older gir1.2-webkit2-4.0 name
# only if 4.1 genuinely isn't available.
if apt-cache show gir1.2-webkit2-4.1 >/dev/null 2>&1; then
    $APT_PREFIX apt-get install -y gir1.2-webkit2-4.1
else
    $APT_PREFIX apt-get install -y gir1.2-webkit2-4.0
fi

if [ "$USE_SUDO" = true ]; then
    INSTALL_DIR="/usr/share/arrow-browser"
    BIN_DIR="/usr/bin"
    DESKTOP_DIR="/usr/share/applications"
    ICON_DIR="/usr/share/icons/hicolor/256x256/apps"
    CMD_PREFIX="sudo"
else
    echo "Installing in user local directory (~/.local)..."
    INSTALL_DIR="${HOME}/.local/share/arrow-browser"
    BIN_DIR="${HOME}/.local/bin"
    DESKTOP_DIR="${HOME}/.local/share/applications"
    ICON_DIR="${HOME}/.local/share/icons/hicolor/256x256/apps"
    CMD_PREFIX=""
fi

echo "[2/4] Copying application files..."
$CMD_PREFIX mkdir -p "$INSTALL_DIR" "$INSTALL_DIR/assets" "$BIN_DIR" "$DESKTOP_DIR" "$ICON_DIR"

$CMD_PREFIX cp arrow_browser.py "$INSTALL_DIR/"
if [ -d "assets" ]; then
    $CMD_PREFIX cp -r assets/* "$INSTALL_DIR/assets/"
fi

# Create launcher script wrapper. Staged in a private temp folder: a fixed /tmp name could be swapped by
# another local user before the copy below, which runs as root for a system-wide install.
STAGE_DIR="$(mktemp -d)"
trap 'rm -rf "$STAGE_DIR"' EXIT
cat << 'EOF' > "$STAGE_DIR/arrow-browser-launcher"
#!/bin/bash
SCRIPT_PATH="$(readlink -f "$0")"
BIN_DIR="$(dirname "$SCRIPT_PATH")"
# Start through an import so Python reuses the compiled code it keeps in __pycache__: running
# arrow_browser.py directly would recompile all of it on every launch (~0.25 s).
run() { exec python3 -c 'import runpy, sys; sys.path.insert(0, sys.argv.pop(1)); runpy.run_module("arrow_browser", run_name="__main__", alter_sys=True)' "$@"; }

# User-writable install checked first: it's the only copy the browser's
# self-updater can actually rewrite in place. A root-owned /usr/share install
# is left as a fallback for systems that only have a system-wide install.
if [ -f "${HOME}/.local/share/arrow-browser/arrow_browser.py" ]; then
    run "${HOME}/.local/share/arrow-browser" "$@"
elif [ -f "/usr/share/arrow-browser/arrow_browser.py" ]; then
    run /usr/share/arrow-browser "$@"
else
    echo "arrow-browser: no installed copy found in ~/.local/share/arrow-browser or /usr/share/arrow-browser." >&2
    echo "Reinstall Arrow Browser from https://github.com/Sangam1112/arrow-browser/releases" >&2
    exit 1
fi
EOF
chmod +x "$STAGE_DIR/arrow-browser-launcher"
$CMD_PREFIX cp "$STAGE_DIR/arrow-browser-launcher" "$BIN_DIR/arrow-browser"
$CMD_PREFIX chmod +x "$BIN_DIR/arrow-browser" "$INSTALL_DIR/arrow_browser.py"

echo "[3/4] Registering desktop shortcut..."
sed "s|Exec=arrow-browser|Exec=${BIN_DIR}/arrow-browser|g" arrow-browser.desktop > "$STAGE_DIR/arrow-browser.desktop"
$CMD_PREFIX cp "$STAGE_DIR/arrow-browser.desktop" "$DESKTOP_DIR/arrow-browser.desktop"

if [ -f "assets/arrow_icon.png" ]; then
    $CMD_PREFIX cp assets/arrow_icon.png "$ICON_DIR/arrow-browser.png"
fi

# Up to 1.5.19 this was Bharat Browser: drop its menu entry and icon, so the menu shows one browser, and
# point its command at this one.
$CMD_PREFIX rm -f "$DESKTOP_DIR/bharat-browser.desktop" "$ICON_DIR/bharat-browser.png"
if [ -e "$BIN_DIR/bharat-browser" ] || [ -L "$BIN_DIR/bharat-browser" ]; then
    $CMD_PREFIX ln -sf arrow-browser "$BIN_DIR/bharat-browser"
fi

echo "[4/4] Updating desktop environment databases..."
if command -v update-desktop-database &> /dev/null; then
    update-desktop-database "$DESKTOP_DIR" 2>/dev/null || true
fi

echo "=========================================="
echo "Arrow Browser successfully installed!"
echo "Binary location: ${BIN_DIR}/arrow-browser"
echo "Launch by typing '${BIN_DIR}/arrow-browser' in terminal or via Application Menu."
if [ "$USE_SUDO" = false ]; then
    echo "(add \"export PATH=\\\"\$HOME/.local/bin:\$PATH\\\"\" to ~/.bashrc if the"
    echo " \"arrow-browser\" command isn't found in new terminals)"
fi
echo "=========================================="
