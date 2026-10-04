#!/bin/bash
# Run inside WSL by setup.ps1 (Bharat Browser's Windows Setup). Arguments are Windows paths.
#   wsl-setup.sh system <path to the .deb>    as root: update Ubuntu, install the browser
#   wsl-setup.sh user <Windows Downloads>     as the user: save downloads to Windows' Downloads
set -euo pipefail

case "${1:-}" in
system)
    export DEBIAN_FRONTEND=noninteractive
    deb="${TMPDIR:-/tmp}/bharat-browser.deb"
    cp "$(wslpath -u "$2")" "$deb"
    apt-get update
    # Brings WebKit and the graphics libraries up to date; not fatal, since an
    # interrupted upgrade on someone's existing Ubuntu shouldn't block the install.
    apt-get -y -o Dpkg::Options::=--force-confold full-upgrade ||
        echo "Warning: updating Ubuntu didn't finish; installing Bharat Browser anyway."
    # The package pulls in Python, GTK and WebKit. gnome-keyring lets it save passwords;
    # fonts-noto-core shows Hindi and other Indian scripts instead of empty boxes.
    apt-get install -y "$deb" gnome-keyring fonts-noto-core
    rm -f "$deb"
    ;;
user)
    settings="$HOME/.config/bharat-browser/settings.json"
    [ -e "$settings" ] && exit 0  # already set up: never overwrite someone's settings
    mkdir -p "$(dirname "$settings")"
    umask 077
    python3 -c 'import json, sys; json.dump({"download_dir": sys.argv[1]}, open(sys.argv[2], "w"), indent=2)' \
        "$(wslpath -u "$2")" "$settings"
    ;;
*)
    echo "usage: $0 system <deb> | user <downloads folder>" >&2
    exit 2
    ;;
esac
