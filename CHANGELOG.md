# Changelog

All notable changes to Arrow Browser (called Bharat Browser up to 1.5.19). Versions follow `MAJOR.MINOR.PATCH`.
Releases are signed; the in-app updater only installs a release whose signature verifies.

## [1.6.0] - 2026-10-07

### Changed
- **Bharat Browser is now Arrow Browser.** The window, menus, pages, installers and packages use the new name. The command is `arrow-browser`, the packages are `arrow-browser_…`, and the project lives at github.com/Sangam1112/arrow-browser (the old address forwards there).
- **Nothing to do if you already use it.** Installed copies update to Arrow Browser by themselves, as usual. On first start it moves into its new folders and keeps your settings, history, bookmarks, cookies and open tabs. Saved passwords are found under the old name and move to the new one the next time you save them. The `bharat-browser` command keeps working, and installing the new package replaces the old one.
- **New look:** the saffron-white-green colours and "Made in India" are replaced by the browser's indigo accent, and the icon's ring is a single violet.
- **The title bar no longer shows the version number.** It's still in Settings → About. Private windows keep "(Private)" in their title.

### License
- **Arrow Browser is now free software under the GNU General Public License v3.0 or later** (it was MIT). You may use, study, share and change it. Anything you distribute that is based on it must be released under the same license, with its source code. Versions up to 1.5.19 remain available under the MIT License. The packages now include the license text.

## [1.5.19] - 2026-10-07

### Fixed
- **On Windows the window had only a close button.** Bharat Browser draws its own title bar and shows the buttons your Linux desktop asks for. On Windows (through WSL) there is no Linux desktop to ask, so only ✕ appeared. On Windows the title bar now has minimize, maximize and close, like other Windows apps. On Linux it still follows your desktop's setting.
- **The WSL installer's launcher no longer runs code from whatever folder you start it in**, matching the other installers since 1.5.17.

## [1.5.18] - 2026-10-07

### Fixed
- **"Working on latest version" showed up even when the browser was out of date.** Every time the browser started, it showed that notice before checking anything, so an old copy said it was current. One running v1.4.5 under WSL on Windows claimed to be the latest version while v1.5.17 was out. The notice now appears only after an update check has actually run, and it says what that check found. Copies that already have the self-updater still updated themselves about 30 seconds after starting; only the notice was wrong.

## [1.5.17] - 2026-10-07

A security release, from a review of the browser against the standards other browsers follow.

### Security
- **Websites now run in a sandbox.** Each page used to run with your full rights, so a bug in the web engine that a malicious site could exploit would reach all your files (documents, SSH keys, saved cookies). Pages now run inside a bubblewrap sandbox, as in GNOME Web, Chrome and Firefox, and such an attack ends there. If the sandbox can't start on a computer, the browser works as before. `BHARAT_NO_SANDBOX=1` switches it off.
- **"Fill" can no longer put a password into the wrong site.** The fill offer stayed up for a minute and filled whatever page the tab showed by then, so a page that moved on to another site could receive the first site's password. The offer now closes when the tab goes to another page. Fill also checks the site again, and it runs where the page can't watch or tamper with it.
- **Permission prompts say what the site is asking for.** Instead of "Allow a permission?", they say "use your camera", "see and share your screen", "read what you copied to the clipboard", and so on. Requests nobody can judge from a prompt are refused without asking. Only the tab you're looking at can hide the mouse pointer, and Esc always brings it back.
- **Fullscreen names the site.** A page in fullscreen can draw a fake address bar. You now see "*site* is now full screen · Press Esc to exit" for a few seconds, as in other browsers.
- **Program files ask before saving.** Websites can save downloads without asking. For files that can run programs or install software (`.desktop`, `.sh`, `.AppImage`, `.deb`, `.exe`, …), you're now asked first. Downloads can no longer be saved as hidden files.
- **Old browsing data is really removed.** The old Chromium-based version left its cookies and site data in your profile folder, where "Clear history on exit" never reached them. The cleanup meant to remove them only removed folders and missed most names. It now removes all of it.
- **Safer install scripts.** The install and build scripts wrote files under fixed names in `/tmp`, where another user on the same computer could swap them before a system-wide install copied them as root. They now use private temporary folders. The `bharat-browser` launcher no longer falls back to running code from whatever folder you're in.
- **Less to fingerprint.** Websites could read a few markers this browser left on pages, including the made-up WebGL graphics name, and tell that you use Bharat Browser. They're gone. Private windows no longer look up or connect to links you only hover over.
- **Updates must carry a normal version number** (`1.2.3`) before anything is downloaded.

### Removed
- **Reader mode.**
- **The Advanced page in Settings.** Hardware acceleration and developer tools keep whatever you had set. Developer tools can still be turned on with `"dev_tools_enabled": true` in `~/.config/bharat-browser/settings.json`.

### Fixed
- Pages opened in a new window by a link ran the browser's page scripts twice.

## [1.5.16] - 2026-10-07

### Fixed
- **Dark mode turned dark websites white.** "Dark mode for websites" works by flipping a page's colours, light to dark. It did that to every page, so a site that was already dark came out light grey or white. That includes the many sites that follow your desktop's dark theme. Before flipping, the browser now checks whether the page is already dark and leaves dark pages as they are. It checks again when a site switches to its own dark theme after loading. Turning dark mode on in Settings, or with the moon button, no longer whitens the dark page you're on.

## [1.5.15] - 2026-10-06

### Changed
- **The padlock now shows what was actually checked.** It used to turn green whenever the address started with `https://`. Now it asks the browser engine about the connection itself: green only when the site's certificate was verified, amber when part of the page (an image, a script) came over plain, unencrypted HTTP, and red for plain HTTP or a certificate with problems. It stays grey for the moment a page is still connecting.
- **See a site's certificate.** Click the padlock to see who the certificate was issued to, who issued it, the dates it's valid, and its SHA-256 fingerprint, which you can select and copy.

### Fixed
- **The certificate check now has automated tests.** Sites with an invalid certificate were already blocked with no way to click past, but nothing tested it. The tests use a local HTTPS server with an untrusted certificate and check that the page is blocked, that nothing is sent to the site, and that the padlock never shows green.

## [1.5.14] - 2026-10-06

### Fixed
- **Typing in the address bar of an open tab took you back to the same site.** Clicking into the address bar put the cursor where you clicked instead of selecting the address, so whatever you typed was inserted into the current address, and Enter just reloaded that page. The first click now selects the whole address, as in other browsers, so typing replaces it. A second click places the cursor for editing.
- **The address bar could wipe out what you were typing.** When the page in the tab finished loading while you typed, the bar was reset to the page's address. It now leaves your text alone while you're typing, as it already did for sites like YouTube that change address without reloading.

## [1.5.13] - 2026-10-06

### Fixed
- **Saved-password prompts could name the wrong site.** The browser took the site from the tab you were looking at, not from the tab where the login happened. A login form loading in a background tab was offered a fill for the site in front, and a login submitted in a background tab was offered for saving under the site in front. Each prompt now belongs to the tab its login form is in. For a login page in a background tab, the "Fill" offer appears when you switch to that tab.
- **One frozen page could stop tabs from going to sleep for the rest of the session.** When memory runs low, background tabs sleep one at a time, and each page is first asked whether you've typed something you haven't sent. A page stuck in a script never answered, so automatic sleeping stopped until you restarted the browser. A page that doesn't answer within 3 seconds is now left awake, and the browser moves on to the next tab.

## [1.5.12] - 2026-10-06

### Fixed
- **Links that open a new tab took 15 seconds, and the page you clicked on went blank.** With "Use hardware acceleration" off, WebKitGTK 2.52 stalls for 15 seconds whenever a page opens a new tab (links that open in a new tab, `window.open()` pop-ups such as sign-in windows). The new tab stayed empty and the original page stopped drawing until then. Tabs opened this way now allow hardware acceleration for themselves only; pages in them are still drawn by the CPU, the same as fullscreen video. All other tabs stay fully GPU-off. New tabs now open in under half a second. Computers using the old `radeon` driver weren't affected and are unchanged.

## [1.5.11] - 2026-10-06

### Fixed
- **Clicking a tab showed the address of the tab you just left.** The address bar, the lock icon and the window title (what your taskbar shows) all showed the previous tab's address and title, until that page changed address or finished loading. The browser asked for "the current tab" a moment before the tab bar had switched, so it got the old tab back. It now uses the tab you clicked.

## [1.5.10] - 2026-10-06

### Fixed
- **"Clear history when closing" left you signed in to sites.** The setting only emptied the browsing history and address-bar suggestions. Cookies stayed on disk, so after a restart Google and other sites still knew who you were. Closing the browser now also clears cookies, cached files and site storage, the same as "Clear history, cookies and cache", and waits for that to finish before quitting. If the browser crashes or is killed before it can clear, the leftover cookies are deleted the next time it starts. Bookmarks and saved passwords are kept. The setting is renamed "Clear history and cookies when closing" to say what it does.

## [1.5.9] - 2026-10-06

### Fixed
- **A crashed tab stayed broken.** When a tab's page crashed, Bharat Browser is meant to reload it automatically, or show a "This tab ran out of memory" or "This page keeps crashing" page. Since version 1.4.0 the crash handler itself failed on a misspelt WebKit name, so none of that happened and the tab just stayed blank until you reloaded it yourself. Crashed tabs reload again, and the two notice pages appear when they should.

## [1.5.8] - 2026-10-06

### Fixed
- **Fullscreen video was a black screen with GPU acceleration off.** Only the play/pause controls showed. With the GPU off, the browser told WebKit never to use hardware acceleration, and WebKitGTK 2.52 can't show a fullscreen video that way. Acceleration is now switched on just while something is fullscreen and off again when you leave; pages are still drawn on the CPU and the setting stays off. On computers using the old `radeon` driver this doesn't help, and nothing changes there.
- **Video froze after leaving fullscreen.** After Esc or the exit button, a playing video stopped on its current frame while still showing as playing, with GPU acceleration on or off. This is a WebKitGTK 2.52 bug; the browser now restarts a playing video when a page leaves fullscreen, including players embedded in other sites (iframes).

## [1.5.7] - 2026-10-06

### Fixed
- **"I'm not a robot" checks now see real canvas and audio readings.** Fingerprint protection makes tiny changes to canvas and audio readings, and captcha checks look for exactly that kind of change. Only Cloudflare's check was left alone, so Google reCAPTCHA, hCaptcha and Arkose (used at Microsoft, GitHub and Roblox sign-up) could see the changes and count them against you. These checks now get the real readings. For reCAPTCHA only the check itself, under `google.com/recaptcha/`, is left alone; Google Search and the rest of Google stay protected.
- **Look-alike sites could switch off fingerprint protection.** Streaming sites are left alone, but the check matched any address *containing* "youtube.com", so a site named, say, `notyoutube.com` received your real canvas and audio readings. Only the real domains and their subdomains match now.

## [1.5.6] - 2026-10-06

### Changed
- **Starts about a quarter of a second faster.** Python was recompiling the whole browser (about 6,700 lines) on every launch, because the launcher ran the file directly, and Python never caches a file run that way. The launcher, the install scripts and the browser's own restart after an update now start it through an import, so the compiled code is saved and reused. For system-wide `.deb`/`.rpm` installs, which users can't write to, the package compiles the browser once at install time and removes that copy on uninstall. The faster start comes with the new launcher, so install the 1.5.6 package (or run the install script again): the in-app updater replaces only the browser itself, not the launcher.
- **Uses about 10 MB less memory.** Every launch read all ~94,000 ad and tracker domains into memory just to work out which compiled block list to load, and the weekly "are the lists out of date?" check read them a second time, although WebKit already had the list compiled and saved. A small summary file now answers both. The full list is only read when it really has to be compiled again. Blocking is unchanged.

## [1.5.5] - 2026-10-05

### Added
- **Real ad blocking.** The weekly list download now includes EasyList, the main ad list, alongside EasyPrivacy (trackers): about 94,000 ad and tracker domains instead of 47,000. Before, ads were only caught by a short built-in list. As before, listed domains are blocked only when another site loads them, never when you visit them yourself, and sign-in and captcha services are never blocked. Compiling the bigger list takes about 20 seconds once a week, in the background; the built-in protection stays on meanwhile. If you already had the old list, the new one is downloaded on the next launch.
- **Much better link cleaning.** "Remove tracking tags from links" now also uses the ClearURLs rules, downloaded once a week from clearurls.xyz (not shipped in the package): hundreds of site-specific tags on Amazon, Flipkart, Google, YouTube, Reddit, LinkedIn, Instagram and about 200 other sites, on top of `utm_*`, `fbclid`, `gclid` and the like. Tracking redirects such as `google.com/url?q=…` are skipped and the real page opens directly (upgraded to HTTPS too). Affiliate and referral tags are left alone, because `?ref=` also picks the branch on GitHub. Addresses that use `#…?` for their own navigation, like Gmail, are never changed after the `#`.
- **Stronger fingerprint protection.** Sites could still recognise your computer from how it draws a canvas image (`toDataURL`/`toBlob`), from WebGL pixels or from how it processes sound. Those readings now get tiny changes that you can't see or hear. A site gets the same changes all session, so pages keep working, but different sites and new sessions get different ones. Private windows get their own, so a site can't match a private visit to a normal one. Very small reads, as used by colour pickers, stay exact.
- **The lock in the address bar is green on secure (HTTPS) pages and red on insecure (HTTP) ones.**
- **Settings → About links to the project page on GitHub** (source code, release notes, downloads and bug reports).

### Changed
- The "Keep the tracker list up to date" switch is now "Keep the block lists up to date" and covers all three downloads. Turning it off also stops the browser from using the downloaded link-cleaning rules; the built-in ones still apply.

## [1.5.4] - 2026-10-05

### Fixed
- **"Always use secure connections (HTTPS)" did nothing.** Pages stayed on `http://` while the Privacy Report counted them as upgraded. The browser changed the address after WebKit had already decided what to load, and WebKit ignores that. Addresses are now upgraded before the page starts loading: ones you type, new tabs, bookmarks, restored tabs, links opened from other apps, and the first page of a tab a site opens. If a site has no secure version, the "Secure connection unavailable" page now really appears and you choose whether to continue over HTTP. Local-network addresses (routers, printers) still stay on `http://`.
- **"Remove tracking tags from links" did nothing either**, for the same reason: sites still received `utm_…`, `fbclid`, `gclid` and similar tags. They are now removed from the same addresses before loading. Links you click inside a page are still sent as they are: WebKit reports a click inside an embedded frame the same way as a click on the page, so changing those could replace the whole page with the frame. The Privacy Report now counts only addresses that really changed.
- **Downloads got the wrong name, and failed downloads showed as completed.** A file the site calls "Report.pdf" but serves from an address like `…/download?id=7` was saved as `download`, without its extension. Downloads now use the name the site gives. An address with spaces or `#` in it could also lose the file while still saying "Completed ✅". A download that fails, or whose connection drops part-way, now shows "Failed ❌".
- **Links opened from other apps opened the browser without the link.** Clicking a link in an email or chat app, with Bharat Browser as the default browser, only restored your last session. The link now opens in a new tab after your restored tabs.
- The address bar now says "Search DuckDuckGo…" (or whichever engine you chose) instead of always "Search Google…".

## [1.5.3] - 2026-10-05

### Fixed
- **The address bar could show the wrong site**, for example google.com on a YouTube tab. It only updated when you switched tabs or a page finished loading. Sites like YouTube and Gmail change their address without loading a new page, and a slow page kept showing the previous site's address until it finished. The address bar now follows the page's real address as it changes, but never overwrites what you're typing in it.

### Changed
- Pressing Enter in the address bar now moves the focus to the page, as other browsers do.

## [1.5.2] - 2026-10-05

### Fixed
- **The whole computer could freeze on older AMD laptops** (Radeon R2/R3 "Mullins" and similar) that use the legacy `radeon` driver: WebKit's GPU drawing hit a GPU lockup that only a hard power-off cleared. On the `radeon` driver, GPU acceleration is now off by default. The "Use hardware acceleration" switch in Settings → Performance also really turns the GPU off now; before, a setting it couldn't override kept the GPU on. The change applies after a restart.
- **The browser crashed when a site opened a popup with GPU acceleration off.** Turning the GPU off also turned off WebGL, and with WebGL off any page opening a new window crashed WebKit. WebGL now stays on, so with the GPU off, 3D content (maps, games) still uses the graphics card; everything else is drawn on the CPU.
- **The browser could crash at random with GPU acceleration off.** It switched off a WebKit drawing component that pages sometimes still use. Pages are now drawn on the CPU while that component stays available. The old behaviour is kept only on the `radeon` driver, where a GPU lockup freezes the whole desktop.

## [1.5.1] - 2026-10-04

### Changed
- **Sleeping tabs now free all their memory.** A tab put to sleep used to load a blank page, which left its renderer process running and holding most of its memory (about 480 of 680 MB in a test). Its process is now ended, so all of that memory comes back. Clicking the tab reloads it where it was, with its Back history; that takes about 0.4 s longer than before. A popup and the tab that opened it share one process, so for those only the page is unloaded, as before.
- **Restoring your last session no longer loads every tab at once.** Only the tab you land on loads; the others show as 💤 and load the first time you open them. With 6 restored tabs, memory 30 s after starting dropped from 959 MB (6 renderers) to 204 MB (1).
- **Tabs go to sleep sooner when the computer is low on memory** (under 10% of RAM, or under 400 MB, available): the least recently used background tab sleeps first, one every 10 seconds while memory stays low. The browser checks this itself: the system's low-memory signal it relied on before only exists where the low-memory-monitor service is installed (Fedora has it; Ubuntu and Linux Lite don't). Controlled by the same "Sleep inactive tabs" switch.

### Fixed
- Automatic tab sleeping no longer puts tabs to sleep that you'd lose something in: **pinned tabs**, tabs using the **camera, microphone or screen sharing**, and tabs holding **text you typed but haven't sent** (any text in a text box or rich-text editor, a single field with more than 50 characters, or two or more filled-in fields). Tabs playing sound or still loading were already kept awake. "Suspend" in Tab Memory still works on any tab.

## [1.5.0] - 2026-10-04

### Changed
- **Redesigned Settings.** A sidebar now replaces the tab bar and the large banner, and settings are split across six pages: **General**, **Privacy & Security**, **History & Data**, **Performance**, **Advanced** and **About**. Each setting is a row with a plain-language note on what it really does. Several settings moved to the page where you'd expect them: dark mode is under General (it used to be under Privacy), developer tools under Advanced (it used to be under Performance), and update checks under About (they used to be under "Data & Actions").
- Settings closes with the × in the title bar or Esc. "Open New Private Window" is no longer repeated in Settings; it stays in the main menu and on Ctrl+Shift+N.

### Added
- **Download folder** in Settings → General (previously only in the Downloads window).
- **Tab Memory** can be opened from Settings → Performance.

### Fixed
- "Clear history, cookies and cache" used to clear everything on a single click. It now asks first and says what is kept (bookmarks and saved passwords).

## [1.4.5] - 2026-10-04

### Fixed
- **Cloudflare "Verify you are human" now works.** The browser claimed to be Chrome while running the WebKit engine; Cloudflare saw the mismatch and never let it through (0 of 6 test runs). It now identifies as what it is (Safari on Linux, the same form GNOME Web uses), and Cloudflare's checks pass (6 of 9 test runs without clicking; the checkbox challenge now shows normally for you to click). A site that refuses this browser can be switched back per site: lock icon -> "Identify as Chrome".
- **Crash on google.com (the default homepage) on some systems.** WebKitGTK 2.52 with GTK3's accessibility bridge segfaults the browser on some pages while the accessibility service runs, even with no screen reader. The bridge is now turned off unless a screen reader (Orca) is running; set `BHARAT_ACCESSIBILITY=1` to keep it on.
- The anti-fingerprinting script no longer runs inside Cloudflare's verification frame.

## [1.4.4] - 2026-10-04

### Added
- **Tab Memory** (main menu): see how much memory each tab uses, heaviest first, and go to, suspend or close a tab right from the list. Right-clicking a tab also shows its memory. WebKit does not say which renderer process belongs to which tab, so each tab is matched by a short CPU probe (about 0.2 s per tab, cached afterwards); a tab that can't be matched, for example one with JavaScript turned off, shows "—". Memory is the process's proportional set size, so shared libraries are not counted once per tab.

## [1.4.3] - 2026-10-03

### Fixed
- **Path-based ad/tracker blocking now actually blocks.** Requests matching `/ads/`, `/adserver/`, `/pagead/`, `/pixel.gif`, `/tracker.js`, `/telemetry`, `/analytics.js`, `/gtm.js`, `/collect?` and `/log_event` were only counted by the old Python check; WebKit still sent them. They are now rules in the native content blocker. They apply to images, scripts, styles, fonts, media and fetch/XHR only, never to a page you navigate to, and streaming hosts (YouTube, Vimeo, Twitch) and `.m3u8`/`.mpd` manifests are exempt. The per-site "Block ads" switch turns them off too.
- The diagnose tool reported "Main process memory is growing" when a second browser instance started during a run, because it summed all main processes into one series. It now fits each process on its own.

### Changed
- The per-request Python ad matcher (and the optional `adblockparser` engine) is removed: the native blocker handles all blocking inside the web process.
- The shield button no longer shows a count, and the Privacy Report no longer shows "Trackers & ads blocked": WebKit does not tell the browser about requests its content blocker drops, so those numbers were misleading. Tracking-parameter and HTTPS-upgrade counts are unchanged.

## [1.4.2] - 2026-10-03

### Changed
- **Red Hat family:** the RPM now requires `(webkit2gtk4.1 or webkit2gtk3)` and `install-fedora.sh` accepts either, trying Fedora's `webkit2gtk4.1` first and falling back to `webkit2gtk3` (RHEL, Rocky Linux, AlmaLinux, CentOS Stream). The app itself already ran on WebKit2GTK 4.1 or 4.0. Not yet tested on a real RHEL-family system; the installer paths are covered by automated tests with stubbed `rpm`/`dnf`.
- Clearer manual-install instructions when dependencies can't be installed automatically.

## [1.4.1] - 2026-10-03

### Fixed
- "Check for updates" could report the old version for a few minutes after a release, because GitHub caches the raw file address. It now asks GitHub's API first and falls back to the raw address. Updates are still only installed if the release signature verifies.
- When an update can't be installed automatically, the message now says where to download it instead of mentioning `git pull`.

## [1.4.0] - 2026-10-03

### Added
- **Tabs:** pin tabs (they survive restarts), right-click tab menu (reload, duplicate, pin, close others/to the right), middle-click to close, Ctrl+Shift+T to reopen the last closed tab.
- **Reader mode** (Ctrl+Alt+R): clean, distraction-free article view with text size and theme controls.
- **Per-site controls** from the lock icon: block ads, allow JavaScript, remembered zoom, and remembered camera/microphone, location and notification choices, with a manager in Settings.
- **Password saving** through the system keyring (GNOME Keyring, KWallet, KeePassXC) with a "Save?" / "Fill?" bar and a password manager. Never stored in the browser's own files, never filled without a click, never in private windows.
- **Import** bookmarks and history from Firefox, Chrome, Chromium, Brave, Edge, Vivaldi and Opera, or from an exported bookmarks `.html`.
- **Tracker list updates:** weekly EasyPrivacy download (whole-domain, third-party rules only, with a never-block list for sign-in and captcha services). Compiled once and cached, so launches stay instant.
- **Privacy report** (click the shield): trackers blocked, tracking parameters removed and connections upgraded to HTTPS.
- **HTTPS-only warning:** when a site can't be reached securely you get a clear page and a deliberate "continue over HTTP" choice (single-use token, so a website can't switch HTTPS upgrading off).
- Spell check toggle; a menu on the ☰ button; friendly "this tab ran out of memory" and "keeps crashing" pages.
- Tooling: `tools/bump-version.py`, `tools/check-version.py`, `tools/release.sh`, `tools/verify-published.py`, `tools/run-tests.sh`, and an automated test suite (`tests/`).

### Fixed
- Tab titles were squeezed to "…"; tabs now have a proper minimum width.
- The 🇮🇳 emoji showed as "IN" on systems without a flag font.

## [1.3.7] - 2026-10-03

- Friendly offline page (clear message, auto-reload when back online, kite mini-game); update check no longer claims "latest version" when offline.
- Redesigned Settings: banner, icon badges, toggle switches, version/signing chips.
- README screenshots.

## [1.3.6] - 2026-10-03

- Auto-updater now requires a valid Ed25519 signature on every release, verified against a public key built into the app.

## [1.3.5] - 2026-10-03

- User agent updated from Chrome 126 to Chrome 154 and moved to a single constant (`CHROME_UA_MAJOR`).

## [1.3.4] - 2026-10-03

- Persistent SQLite cookies (logins survive restarts), third-party cookie blocking and ITP.
- Fullscreen video hides the browser chrome; touchpad swipe back/forward.
- F12 / Ctrl+Shift+I inspector, Ctrl+P print, Ctrl+L, F5, Alt+Left/Right, Ctrl+Tab.

## [1.3.3] - 2026-10-03

- Self-updater works for system-wide package installs by installing to `~/.local/share/bharat-browser`.
- Fixed a stale checksum in `package.json` that made updates fail the integrity check.

## [1.3.2] - 2026-10-03

- Performance and memory fixes: signal disconnection on tab close, throttled shield badge updates, O(1) ad-block pre-lookup, stale cache cleanup.

## [1.3.1] - 2026-09-30

- GPU detection moved off the startup path; history/session writes debounced and compacted; autocomplete model updated in place.

## [1.3.0] - 2026-09-30

- Downloads Manager: choose the download folder.
- Bookmarks: address-bar star, Ctrl+D, Bookmark Manager (Ctrl+Shift+O).
- Dark mode is now a WebKit user stylesheet applied by the engine: no white flash, survives navigation and restarts.

## Earlier

Versions 1.2.x and before: see the git history and the `%changelog` in `build-rpm.sh`.
