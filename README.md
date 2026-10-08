<div align="center">

<img src="assets/arrow_icon.png" width="112" alt="Arrow Browser logo">

<h1>Arrow Browser</h1>

<p><b>A tiny, fast, privacy-first web browser for Linux.<br>Built on WebKitGTK.</b></p>

<p><i>Formerly Bharat Browser (up to v1.5.19). Installed copies update to Arrow Browser by themselves and keep their settings, history and saved passwords. <a href="#coming-from-bharat-browser">More</a></i></p>

[![Latest release](https://img.shields.io/github/v/release/Sangam1112/arrow-browser?label=release&color=blue)](https://github.com/Sangam1112/arrow-browser/releases/latest)
[![License](https://img.shields.io/badge/license-GPL--3.0--or--later-blue.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/platform-Ubuntu%20%7C%20Debian%20%7C%20Fedora%20%7C%20RHEL%20family%20%7C%20WSL2-orange.svg)](#-install)
[![Installer](https://img.shields.io/badge/installer-~120%20KB-brightgreen.svg)](#-small-by-design)
[![Updates](https://img.shields.io/badge/updates-signed%20(Ed25519)-6366f1.svg)](#-keeping-it-up-to-date)

[**Highlights**](#-highlights) · [**Benchmarks**](#-benchmarks) · [**Install**](#-install) · [**Update**](#-keeping-it-up-to-date) · [**Shortcuts**](#-keyboard-shortcuts) · [**Privacy**](#-privacy--what-it-connects-to)

</div>

---

## 🌟 Why Arrow Browser?

<table>
  <tr>
    <td width="25%" valign="top"><h3>🪶 Tiny</h3>A ~120 KB installer. It uses the WebKitGTK already on your system instead of shipping its own 150 MB engine.</td>
    <td width="25%" valign="top"><h3>🛡️ Private</h3>Tracker blocking, HTTPS upgrades, cookie protection and a sandbox for every page work from the very first launch.</td>
    <td width="25%" valign="top"><h3>⚡ Light</h3>Built to stay comfortable on older PCs: it sleeps unused tabs and trims its own memory.</td>
    <td width="25%" valign="top"><h3>🔐 Trustworthy</h3>Signed updates, passwords in your system keyring, and no telemetry at all.</td>
  </tr>
</table>

It is a native GTK3 desktop app, not a repackaged Chromium or Electron. The ad blocker, dark mode and tracker protection are built in-house rather than bundled copies of uBlock Origin, DarkReader or ClearURLs; only their public rule lists are downloaded.

---

## ✨ Highlights

**🛡️ Privacy you don't have to configure**
- **Blocks trackers and ads out of the box**, refreshed weekly from EasyList and EasyPrivacy, with a safety list so sign-in pages and captchas keep working.
- **Cleans links**: removes `utm_*`, `fbclid` and hundreds of site-specific tracking tags (ClearURLs rules) and skips tracking redirects such as `google.com/url?q=`.
- **HTTPS-only warning**: if a site can't be reached securely, *you* decide whether to continue over HTTP. There is no silent downgrade.
- **Per-site controls** from the 🔒 icon: ads, JavaScript, zoom and camera/location/notification permissions, remembered site by site. Permission prompts say exactly what a site is asking for.
- **Passwords stay in your system keyring** (GNOME Keyring, KWallet or KeePassXC), never in the browser's own files, and only fill when you click.
- **Leak and fingerprint protection**: third-party cookies blocked, WebRTC off by default (so it can't expose your IP), your real GPU details hidden from websites, and canvas and audio fingerprints given tiny per-site changes so they can't be used to recognise your computer.
- **Privacy report** to see what was stopped, and **private windows** that write nothing to disk.

**🔐 Secure by default**
- **Every page runs in a sandbox** (bubblewrap): a site that exploits a bug in the web engine still can't reach your files.
- **No click-through for bad certificates**, and the padlock is green only when the site's certificate was actually verified. Click it to see who issued the certificate.
- **Downloads that can run programs** (`.desktop`, `.sh`, `.AppImage`, `.deb`, `.exe`, …) **ask first**. Nothing is saved as a hidden file.
- **Fullscreen always says which site it is** and how to leave, so a page can't pass off a fake address bar.

**🧭 Everyday touches**
- **Pinned tabs** that survive restarts, plus a one-key way to reopen a closed tab.
- **Tab Memory** (main menu): see which tab is using the most memory, then suspend or close it from the list.
- **Switch in a minute**: import bookmarks and history from Firefox, Chrome, Brave, Edge, Vivaldi, Opera and more.
- **Dark mode for websites** (Settings → General) that darkens bright pages and leaves sites that are already dark alone.
- **Digital Wellbeing** (Settings → Digital Wellbeing, off until you turn it on): screen time per site, daily limits that close a site once its time is used up, break reminders, and a bedtime wind-down that turns pages greyscale. It all stays on your computer.
- **A friendly offline page** that reloads itself when you're back online, with a kite game while you wait 🪁.

**🪶 Light on your computer**
- **Sleeps tabs you aren't using** and has a Low Memory Mode, so older PCs stay responsive.
- **Signed self-updates** (Ed25519): a release that isn't signed by the project key is never installed.

---

## 📊 Benchmarks

Arrow Browser 1.6.0 against Firefox 157, Brave 1.96 and Ungoogled Chromium 150, tested in October 2026 on a low-power laptop (AMD E2-7110, 4 cores at 1.8 GHz, 6.7 GB RAM, Linux Lite / XFCE). **Bold** marks the best result in each row.

| Test | Arrow | Firefox | Brave | Ungoogled Chromium |
| :--- | :---: | :---: | :---: | :---: |
| **Speedometer 3.1** (responsiveness, higher is better) | 1.57 | 1.83 | **3.27** | 2.27 |
| **Startup time** (lower is better) | 2.91 s | 8.11 s | **2.32 s** | 2.65 s |
| **Memory, one simple page** | **234 MB** | 642 MB | 385 MB | 405 MB |
| **Memory, one heavy page** (4 web apps) | 485 MB | 717 MB | **458 MB** | 483 MB |
| **Memory, 6 tabs** | 688 MB | 764 MB | **498 MB** | 520 MB |
| **Engine tests** (JS, WebAssembly, DOM, canvas; average % of the fastest) | 66% | 61% | **85%** | 69% |
| **Web features supported** (of 38 checked) | 25 | 34 | **35** | **35** |

**Where Arrow does well**
- **Lightest with one page open:** 234 MB, against 385–642 MB for the others.
- **Quick, steady startup:** 2.9 s on every launch, close to the Chromium-based browsers and almost 3× faster than Firefox.
- **Smallest by far:** a ~120 KB installer (see [Small by design](#-small-by-design)).

**Where it falls behind**
- **Responsiveness in heavy web apps:** last on Speedometer; Brave is about twice as fast. This comes mostly from the WebKitGTK engine Arrow is built on, so it improves as WebKitGTK does.
- **Many tabs:** WebKitGTK gives every tab its own processes, so memory grows faster than in Brave or Chromium, which share a process between tabs from the same site. Unused tabs are put to sleep to keep this in check.
- **Missing web features:** no DRM (Netflix, Spotify and similar sites won't play), no passkeys, no picture-in-picture, no AV1 video and no AVIF images. WebRTC (video calls) is off by default for privacy and can be turned on in Settings.

<details>
<summary><b>How it was measured</b></summary>

- Every browser ran the same tests one at a time from a fresh, throwaway profile, with all test pages served from a local server, so network speed played no part.
- Arrow ran with ad blocking and GPU acceleration on and WebRTC off; the other browsers used their default settings (so Brave's ad blocker was on).
- Speedometer 3.1 is the official `release/3.1` suite, averaged over 10 iterations; the scores were repeated in a second run and agreed within 3%. Startup is the median of 5 launches. Memory is the PSS total of every process the browser started, measured after the pages settled.
- This is a slow machine, so the absolute numbers are far below what a modern PC scores. The ranking between browsers is what carries over.
</details>

---

## 📦 Install

**Requirements:** Linux with Python 3, GTK 3, PyGObject and **WebKit2GTK 4.1** (4.0 also works). The installers below fetch these for you. Optional: a keyring service (GNOME Keyring / KWallet / KeePassXC) for saved passwords, and a hunspell dictionary for spell check.

### Quick install

Packages are on the [**Releases page**](https://github.com/Sangam1112/arrow-browser/releases/latest). Replace the version if a newer one is out.

<table>
<tr><th>Ubuntu / Debian / Mint</th><th>Fedora / RHEL family</th></tr>
<tr valign="top"><td>

```bash
VERSION=1.6.2
wget https://github.com/Sangam1112/arrow-browser/releases/download/v$VERSION/arrow-browser_${VERSION}-1_all.deb
sudo apt install ./arrow-browser_${VERSION}-1_all.deb
```

</td><td>

```bash
VERSION=1.6.2
wget https://github.com/Sangam1112/arrow-browser/releases/download/v$VERSION/arrow-browser-${VERSION}-1.noarch.rpm
sudo dnf install ./arrow-browser-${VERSION}-1.noarch.rpm
```

</td></tr>
</table>

Use `apt install ./file.deb` (not `dpkg -i`) so the GTK and WebKit dependencies are resolved automatically. Then start it from your application menu, or run `arrow-browser`.

> **Red Hat family (RHEL, Rocky Linux, AlmaLinux, CentOS Stream):** supported since 1.4.2. Fedora calls the WebKit package `webkit2gtk4.1` and these systems call it `webkit2gtk3`; the RPM and `install-fedora.sh` accept either, and the app itself works with WebKit2GTK 4.1 or 4.0. The install logic is covered by automated tests, but it hasn't been run on a real RHEL-family machine yet. If you try it, please tell us how it went in [issues](https://github.com/Sangam1112/arrow-browser/issues).

### Install from source (no root needed)

This installs for your user only (`~/.local`) and gives you the self-updater:

```bash
git clone https://github.com/Sangam1112/arrow-browser.git
cd arrow-browser
./install-ubuntu.sh        # Ubuntu / Debian / Mint
./install-fedora.sh        # Fedora, RHEL, Rocky, AlmaLinux, CentOS Stream
```

Add `--system` to install for all users instead (it asks for `sudo`). If `arrow-browser` isn't found in a new terminal, add this to `~/.bashrc`:

```bash
export PATH="$HOME/.local/bin:$PATH"
```

<details>
<summary><b>Fedora without git</b>: use the release archive</summary>

```bash
VERSION=1.6.2
wget https://github.com/Sangam1112/arrow-browser/releases/download/v$VERSION/arrow-browser_${VERSION}_fedora.tar.gz
mkdir -p /tmp/arrow_fedora
tar -xzf arrow-browser_${VERSION}_fedora.tar.gz -C /tmp/arrow_fedora
cd /tmp/arrow_fedora && ./install-fedora.sh
```
</details>

<details>
<summary><b>Windows 10/11</b> (via WSL2 + WSLg)</summary>

There is no native Windows build. Arrow Browser runs inside **WSL2** and opens as its own window on the Windows desktop through **WSLg** (Windows 11, or Windows 10 build 19044+).

**1. Prepare Windows**

- **Check your Windows version:** press <kbd>Win</kbd>+<kbd>R</kbd>, type `winver`. You need Windows 11, or Windows 10 version 21H2 (build 19044) or later.
- **Install Windows updates:** Settings → Windows Update → *Check for updates*, install everything, and restart.
- **Check virtualization is on:** Task Manager → Performance → CPU should say *Virtualization: Enabled*. If it says Disabled, turn on Intel VT-x / AMD-V (sometimes called SVM) in your PC's BIOS/UEFI settings.

**2. Update WSL (PowerShell as Administrator)**

Right-click the Start button → *Terminal (Admin)* or *Windows PowerShell (Admin)*, then:

```powershell
wsl --update                   # get the latest WSL from Microsoft (it includes WSLg, which shows Linux windows on your desktop)
wsl --version                  # should list a "WSL version" and a "WSLg version"
wsl --set-default-version 2    # new Linux installs use WSL 2
wsl --shutdown                 # restart WSL so the update takes effect
```

If `wsl --update` or `wsl --version` says WSL isn't installed or doesn't recognize the option, you have the old built-in WSL: run `wsl --install`, restart the PC, then run the commands above again.

**3. Set up Ubuntu (PowerShell)**

```powershell
wsl --install -d Ubuntu     # skip if Ubuntu is already installed; reboot if asked
wsl -l -v                   # Ubuntu should show VERSION 2
```

Open **Ubuntu** from the Start menu once to create your Linux username and password. If `wsl -l -v` shows VERSION 1, run `wsl --set-version Ubuntu 2`.

**4. Update Ubuntu (Ubuntu terminal)**

```bash
sudo apt update && sudo apt full-upgrade -y
```

This brings Ubuntu's graphics and WebKit libraries up to date before the browser is installed. If it upgraded a lot, close Ubuntu, run `wsl --shutdown` in PowerShell, and open Ubuntu again.

**5. Install (Ubuntu terminal)**

```bash
git clone https://github.com/Sangam1112/arrow-browser.git
cd arrow-browser
./install-wsl.sh
```

The script uses `sudo apt` (it will ask for your Linux password) to install Python, GTK3, WebKit2GTK and git, then installs the browser to `~/.local/share/arrow-browser` and a launcher at `~/.local/bin/arrow-browser`.

**6. Run it**

```bash
arrow-browser
```

If the command isn't found, add `export PATH="$HOME/.local/bin:$PATH"` to `~/.bashrc` and open a new terminal. Later, use **Settings → About → Check for updates** to stay current.

**7. Add a desktop shortcut (optional)**

So you can start the browser by double-clicking an icon instead of opening Ubuntu first. In the **Ubuntu terminal**, copy the browser's icon to Windows (Windows shortcuts need an `.ico` file):

```bash
WIN_APPDATA="$(wslpath "$(cmd.exe /c 'echo %LOCALAPPDATA%' 2>/dev/null | tr -d '\r')")"
mkdir -p "$WIN_APPDATA/ArrowBrowser"
python3 -c 'import struct,sys; p=open(sys.argv[1],"rb").read(); open(sys.argv[2],"wb").write(struct.pack("<3H4B2H2I",0,1,1,0,0,0,0,1,32,len(p),22)+p)' \
  ~/.local/share/arrow-browser/assets/arrow_icon.png "$WIN_APPDATA/ArrowBrowser/arrow-browser.ico"
```

Then in **PowerShell** (a normal one, not Administrator), create the shortcut:

```powershell
$s = (New-Object -ComObject WScript.Shell).CreateShortcut("$([Environment]::GetFolderPath('Desktop'))\Arrow Browser.lnk")
$s.TargetPath = "C:\Program Files\WSL\wslg.exe"
$s.Arguments = "-d Ubuntu --cd ~ -- bash -lc arrow-browser"
$s.IconLocation = "$env:LOCALAPPDATA\ArrowBrowser\arrow-browser.ico"
$s.Save()
```

A **Arrow Browser** icon appears on your desktop. `wslg.exe` starts the browser without leaving a terminal window open. To pin it, right-click the icon (on Windows 11, then *Show more options*) → **Pin to taskbar** or **Pin to Start**.

- If your Ubuntu has a different name in `wsl -l -v` (for example `Ubuntu-24.04`), put that name after `-d` instead.
- If Windows says it can't find `wslg.exe`, your WSL is out of date: go back to step 2.
- The first launch after starting Windows can take a few seconds while WSL starts up.

**Troubleshooting**

- *No window appears:* check that WSLg works with `sudo apt install -y x11-apps && xeyes`. If that doesn't open either, run `wsl --update` and `wsl --shutdown` in PowerShell, then reopen Ubuntu.
- *Blank or white window:* try `WEBKIT_DISABLE_DMABUF_RENDERER=1 arrow-browser`, a common workaround for WebKitGTK under WSLg.
- *Saving passwords doesn't work:* the password manager needs a system keyring. Run `sudo apt install -y gnome-keyring`. Everything else works without it.

> Arrow Browser runs on Windows 11 through WSLg; the title bar has the usual minimize, maximize and close buttons there. The WSL installer itself has less testing than the Linux ones, so if something goes wrong, please tell us in [issues](https://github.com/Sangam1112/arrow-browser/issues).
</details>

---

## 🔄 Keeping it up to date

- **Source or user install:** open **Settings → About → Check for updates**. If a newer release exists it is downloaded, its signature is verified, and you just click **Restart now**. The browser also checks quietly about 30 seconds after launch.
- **`.deb` / `.rpm` installs:** the same button works (updates go to `~/.local/share/arrow-browser`, which the launcher prefers), or install the newer package from the [Releases page](https://github.com/Sangam1112/arrow-browser/releases/latest).
- A release that is **not signed by the project key is never installed**, even if the download itself were tampered with.

### Coming from Bharat Browser

Arrow Browser was called Bharat Browser up to v1.5.19. Nothing needs doing:

- **It updates itself** to Arrow Browser, as usual. On its first start it moves to its new folders (`~/.config/arrow-browser`, `~/.cache/arrow-browser`, `~/.local/share/arrow-browser`) and keeps your settings, history, bookmarks, cookies and open tabs. A link is left at each old folder name.
- **Saved passwords** are still found under the old name and move to the new one the next time you save them.
- **The `bharat-browser` command keeps working.** Installing the new `.deb` or `.rpm` replaces the old `bharat-browser` package and brings the new icon and menu entry.
- The old GitHub address forwards to this one.

## 🗑️ Uninstall

```bash
sudo apt remove arrow-browser          # Debian / Ubuntu package
sudo dnf remove arrow-browser          # Fedora package

# user install / self-updated copy
rm -rf ~/.local/share/arrow-browser ~/.local/bin/arrow-browser \
       ~/.local/share/applications/arrow-browser.desktop \
       ~/.local/share/icons/hicolor/256x256/apps/arrow-browser.png

# your data (history, bookmarks, settings, cookies) and cache
rm -rf ~/.config/arrow-browser ~/.cache/arrow-browser

# left behind by Bharat Browser (before 1.6.0), if you used it
rm -rf ~/.config/bharat-browser ~/.cache/bharat-browser ~/.local/share/bharat-browser ~/.local/bin/bharat-browser
```

Saved passwords are in your system keyring, not in those folders: remove them first from **Settings → Privacy & Security → Saved passwords**.

---

## 🧭 Keyboard shortcuts

| Action | Shortcut | Action | Shortcut |
|---|---|---|---|
| New tab | `Ctrl+T` | Find in page | `Ctrl+F` |
| Close tab | `Ctrl+W` | Bookmark page | `Ctrl+D` |
| Reopen closed tab | `Ctrl+Shift+T` | Bookmark manager | `Ctrl+Shift+O` |
| Next / previous tab | `Ctrl+Tab` / `Ctrl+Shift+Tab` | History dashboard | `Ctrl+H` |
| New private window | `Ctrl+Shift+N` | Close find bar | `Esc` |
| Focus address bar | `Ctrl+L` | Print / save as PDF | `Ctrl+P` |
| Back / forward | `Alt+←` / `Alt+→` | Zoom in / out / reset | `Ctrl++` / `Ctrl+-` / `Ctrl+0` |
| Reload | `F5` or `Ctrl+R` | Developer inspector* | `F12` or `Ctrl+Shift+I` |

\* Off by default. To turn it on, set `"dev_tools_enabled": true` in `~/.config/arrow-browser/settings.json` and restart. Touchpad swipe also goes back/forward.

---

## 🔒 Privacy & what it connects to

Arrow Browser has **no telemetry, analytics or accounts**. Besides the sites you visit, it makes only these connections itself:

| What | To | When | Turn off |
|---|---|---|---|
| Update check | `api.github.com`, `raw.githubusercontent.com` | ~30 s after launch, and when you click *Check for updates* | n/a (it only reads a small version file) |
| Ad and tracker lists | `easylist.to` | About once a week | Settings → Privacy & Security → *Keep the block lists up to date* |
| Link-cleaning rules | `rules2.clearurls.xyz` (or `gitlab.com` if that's down) | About once a week | Same switch |
| Link / DNS prefetch | the pages you hover over | While browsing (never in private windows) | n/a |

**Where your data lives:** settings, history, bookmarks, session, per-site settings, cookies and statistics are in `~/.config/arrow-browser` (readable only by you); cache in `~/.cache/arrow-browser`; passwords only in your system keyring. Private windows write none of it to disk.

Spotted a security problem? Please open a [GitHub issue](https://github.com/Sangam1112/arrow-browser/issues), or contact the maintainer privately if it's sensitive.

---

## 🪶 Small by design

| Browser | Installer size | Installed size (approx.) |
|---|---|---|
| **Arrow Browser** | **~129 KB** (RPM) / **~117 KB** (.deb) | **~390 KB** |
| Google Chrome | ~90–100 MB | ~250–350 MB |
| Mozilla Firefox | ~55–75 MB | ~200–300 MB |
| Chromium | ~100–150 MB | ~300–400 MB |
| Brave | ~90–110 MB | ~300+ MB |
| Microsoft Edge (Linux) | ~90–100 MB | ~250–350 MB |

That's roughly **500–1000× smaller**. Chrome, Firefox, Chromium, Brave and Edge each bundle a complete rendering engine (Blink + V8, or Gecko + SpiderMonkey), typically 150–250 MB on its own. Arrow Browser ships none of that: it's a ~340 KB Python/GTK3 program that calls into **WebKitGTK**, a system library most Linux desktops already have for other GTK apps, from the same engine family as Safari.

> Arrow Browser's sizes were measured from the v1.6.0 release packages. The other browsers' figures are well-known public approximations that vary by version and platform.

---

## 🙏 Credits

Built on [WebKitGTK](https://webkitgtk.org/) and [PyGObject](https://pygobject.gnome.org/). The optional weekly block lists are [EasyList and EasyPrivacy](https://easylist.to/) by the EasyList authors, and the link-cleaning rules are [ClearURLs](https://gitlab.com/ClearURLs/rules) by Kevin Röbert and contributors. Both are downloaded at runtime, not shipped in the package.

## 📄 License

© 2026 Sangam1112. Arrow Browser is free software under the [GNU General Public License v3.0 or later](LICENSE): you may use, study, share and change it, but anything you distribute that is based on it must be released under the same license, with its source code. Versions up to 1.5.19 were released under the MIT License.
