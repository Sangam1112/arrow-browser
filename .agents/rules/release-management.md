---
trigger: always_on
description: Bharat Browser release management and version synchronization standards for RPM and DEB packages.
---

# Bharat Browser Release & Packaging Standards

## 1. Releasing
- Change the version with `python3 tools/bump-version.py X.Y.Z "one-line summary"`. It updates `package.json` (the single source of truth), `bharat_browser.py`, the README, `CHANGELOG.md` and the RPM changelog. `build-deb.sh` and `build-rpm.sh` read the version from `package.json` and refuse to build if anything disagrees (`tools/check-version.py`). Expand the notes in `CHANGELOG.md` by hand.
- Run `tools/run-tests.sh` before every release.
- Run both `./build-deb.sh` and `./build-rpm.sh`: they refresh the `sha256` in `package.json` and sign the release (Ed25519, key at `~/.config/bharat-browser-signing/release-ed25519.pem`, which must never be committed). If a build prints "release NOT signed", do not publish it. Changing `UPDATE_PUBLIC_KEY_HEX` locks every installed version out of auto-updating.
- `tools/check-packages.py` confirms the built `.deb`, `.rpm` and Fedora archive all carry the `package.json` version and contain the exact signed `bharat_browser.py`; `tools/release.sh` runs it before publishing.
- Clean up old package artifacts (`bharat-browser*<old-version>*`) in the repo root and `~/Downloads`.
- Commit, then run `tools/release.sh`: it pushes `master`, creates and pushes the `vX.Y.Z` tag, verifies the published release exactly as the in-app updater will (`tools/verify-published.py`) and creates the GitHub Release with the packages attached. The tag is essential: the updater downloads `bharat_browser.py` from it, and without it every installed browser fails to self-update.

## 2. Settings & Dialog UI Architecture
- Settings is a `Gtk.StackSidebar` + `Gtk.Stack` (`build_settings_dialog`): one page per category, not one long scroll view. Pack the stack with `pack_start(stack, True, True, 0)` so it fills the dialog.
- Build pages from the shared helpers: `_settings_section` (heading + `.settings-card`), `_settings_switch_row`, `_settings_button_row` and `_settings_row`. Every row has a title and a plain-language hint that says what the setting really does.
- Register each new switch in `dialog._bharat_controls` (the `switch()` helper does this) so the settings test checks it.
