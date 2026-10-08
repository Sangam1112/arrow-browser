#!/usr/bin/env python3
"""Tests for the browser's pure logic (no window needed). Run: python3 -m unittest discover -s tests -v"""
import importlib.util
import json
import os
import shutil
import sqlite3
import tempfile
import time
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
spec = importlib.util.spec_from_file_location("bb", os.path.join(ROOT, "arrow_browser.py"))
bb = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bb)


def write_text(path, text):
    with open(path, "w") as f:
        f.write(text)


def write_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f)


class TmpDirCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)


class UrlHelperTests(unittest.TestCase):
    def test_sanitize_url_strips_tracking_params(self):
        self.assertEqual(bb.sanitize_url("https://x.com/a?utm_source=t&id=5&fbclid=z"), "https://x.com/a?id=5")
        self.assertEqual(bb.sanitize_url("https://x.com/a?id=5"), "https://x.com/a?id=5")
        self.assertEqual(bb.sanitize_url("https://x.com/a"), "https://x.com/a")

    def test_secure_and_clean_url(self):
        f = bb.secure_and_clean_url
        self.assertEqual(f("http://x.com/a?utm_source=t&id=5"), ("https://x.com/a?id=5", True, True))
        self.assertEqual(f("https://x.com/a?id=5"), ("https://x.com/a?id=5", False, False))
        self.assertEqual(f("http://192.168.1.1/admin"), ("http://192.168.1.1/admin", False, False), "LAN stays http")
        self.assertEqual(f("http://router/"), ("http://router/", False, False))
        self.assertEqual(f("http://x.com/", http_allowed_hosts={"x.com"}), ("http://x.com/", False, False))
        self.assertEqual(f("http://x.com/?gclid=1", upgrade_https=False, strip_tracking=False),
                         ("http://x.com/?gclid=1", False, False), "both settings off")
        self.assertEqual(f("about:blank"), ("about:blank", False, False))

    def test_sanitize_url_keeps_everything_else_exactly(self):
        f = bb.sanitize_url
        self.assertEqual(f("https://x.com/a?utm_id=1&utm_whatever=2&q=a%20b+c&gbraid=3#top?utm_source=x"),
                         "https://x.com/a?q=a%20b+c#top?utm_source=x", "any utm_*, encoding and #fragment kept")
        self.assertEqual(f("https://x.com/a?UTM_SOURCE=t&TtClid=1"), "https://x.com/a")
        self.assertEqual(f("https://x.com/a?&flag&id=5"), "https://x.com/a?&flag&id=5", "untouched if nothing to drop")
        self.assertEqual(f("https://x.com/a?flag&srsltid=9&id=5"), "https://x.com/a?flag&id=5")
        self.assertEqual(f("https://mail.example/u/0/#inbox?utm_source=x"), "https://mail.example/u/0/#inbox?utm_source=x",
                         "a ? inside the #fragment is the page's own route, not the query")

    def test_startup_urls_from_args(self):
        self.assertEqual(bb.startup_urls_from_args(["https://x.com/", "", "--flag", "javascript:alert(1)",
                                                    "no-such-file", __file__, "http://y.org"]),
                         ["https://x.com/", bb.GLib.filename_to_uri(os.path.abspath(__file__)), "http://y.org"])

    def test_download_filename(self):
        f = bb.download_filename
        self.assertEqual(f("Report 2026.pdf", "https://x.com/dl?id=7"), "Report 2026.pdf")
        self.assertEqual(f("", "https://x.com/files/My%20File.zip"), "My File.zip", "address part is decoded")
        self.assertEqual(f("../../etc/passwd"), "_.._etc_passwd", "never a path")
        self.assertEqual(f("", "https://x.com/"), "download")
        self.assertEqual(f("..", ""), "download")
        self.assertEqual(f(".profile"), "profile", "never a hidden file")
        self.assertEqual(f("bad\nname\x07.txt"), "badname.txt", "no control characters")

    def test_old_chromium_profile_data_is_removed_and_webkit_data_kept(self):
        d = tempfile.mkdtemp()
        try:
            for name in ("Cookies", "Trust Tokens", "DIPS", "cookies.sqlite", "settings.json"):
                open(os.path.join(d, name), "w").close()
            for name in ("IndexedDB/https_x.com_0.indexeddb.leveldb", "Local Storage/leveldb", "localstorage", "storage"):
                os.makedirs(os.path.join(d, name))
            bb.ArrowBrowserWindow._cleanup_stale_chromium_artifacts(d)
            self.assertEqual(sorted(os.listdir(d)), ["cookies.sqlite", "localstorage", "settings.json", "storage"])
        finally:
            shutil.rmtree(d, ignore_errors=True)

    def test_running_under_wsl(self):
        d = tempfile.mkdtemp()
        try:
            wsl, linux = os.path.join(d, "wsl"), os.path.join(d, "linux")
            with open(wsl, "w") as f:
                f.write("Linux version 5.15.167.4-microsoft-standard-WSL2 (root@...)")
            with open(linux, "w") as f:
                f.write("Linux version 7.0.0-linuxlite (gcc ...)")
            self.assertTrue(bb.running_under_wsl({}, wsl))
            self.assertFalse(bb.running_under_wsl({}, linux))
            self.assertTrue(bb.running_under_wsl({"WSL_DISTRO_NAME": "Ubuntu"}, linux))
            self.assertFalse(bb.running_under_wsl({}, os.path.join(d, "missing")))
        finally:
            shutil.rmtree(d, ignore_errors=True)

    def test_install_from_before_the_rename_moves_to_the_new_place(self):
        d = tempfile.mkdtemp()
        try:
            legacy, new = os.path.join(d, "bharat-browser"), os.path.join(d, "arrow-browser")
            os.makedirs(legacy)
            here = os.path.join(legacy, "bharat_browser.py")
            with open(here, "w") as f:
                f.write(f'APP_VERSION = "{bb.APP_VERSION}"\n# this release\n')
            move = lambda: bb.move_off_legacy_install(here, new, legacy)
            self.assertIsNone(bb.move_off_legacy_install(os.path.join(d, "elsewhere.py"), new, legacy))
            target = move()
            self.assertEqual(target, os.path.join(new, "arrow_browser.py"))
            self.assertEqual(open(target).read(), open(here).read(), "copied to the new place")
            self.assertTrue(os.path.exists(here), "the old file stays: older launchers still start it")
            with open(target, "w") as f:
                f.write('APP_VERSION = "99.0.0"\n')  # updated since, in the new place
            self.assertEqual(move(), target)
            self.assertIn("99.0.0", open(target).read(), "a newer copy is never replaced by an older one")
            with open(target, "w") as f:
                f.write('APP_VERSION = "1.0.0"\n')
            move()
            self.assertIn("# this release", open(target).read(), "an older copy is replaced")
        finally:
            shutil.rmtree(d, ignore_errors=True)

    def test_data_from_before_the_rename_moves_once(self):
        d = tempfile.mkdtemp()
        try:
            old, new = os.path.join(d, "bharat-browser"), os.path.join(d, "arrow-browser")
            os.makedirs(old)
            open(os.path.join(old, "settings.json"), "w").close()
            bb.move_legacy_data([(old, new)])
            self.assertTrue(os.path.isfile(os.path.join(new, "settings.json")))
            self.assertEqual(os.readlink(old), new, "old name links to the new folder")
            bb.move_legacy_data([(old, new)])  # nothing left to do
            self.assertTrue(os.path.isfile(os.path.join(new, "settings.json")))
            other_old, other_new = os.path.join(d, "o1"), os.path.join(d, "o2")
            os.makedirs(other_old); os.makedirs(other_new)
            bb.move_legacy_data([(other_old, other_new)])
            self.assertTrue(os.path.isdir(other_old) and not os.path.islink(other_old), "never merged into existing data")
        finally:
            shutil.rmtree(d, ignore_errors=True)

    def test_risky_downloads(self):
        for name in ("invoice.pdf.desktop", "setup.SH", "app.AppImage", "x.deb", "run.py"):
            self.assertTrue(bb.is_risky_download(name), name)
        for name in ("report.pdf", "photo.jpg", "archive.zip", "notes.txt", "desktop"):
            self.assertFalse(bb.is_risky_download(name), name)

    def test_homepage_rejects_dangerous_schemes(self):
        for bad in ("javascript:alert(1)", "data:text/html,x", "file:///etc/passwd", ""):
            self.assertEqual(bb.sanitize_homepage_url(bad), bb.DEFAULT_HOMEPAGE)
        self.assertEqual(bb.sanitize_homepage_url("example.com"), "https://example.com")

    def test_local_network_hosts(self):
        for h in ("localhost", "192.168.1.1", "10.0.0.5", "printer"):
            self.assertTrue(bb.is_local_network_host(h), h)
        self.assertFalse(bb.is_local_network_host("example.com"))

    def test_builtin_rules_cover_domains_paths_and_streaming(self):
        rules = json.loads(bb.build_content_blocker_rules_json())
        filters = [r["trigger"]["url-filter"] for r in rules if r["action"]["type"] == "block"]
        self.assertTrue(any("doubleclick" in f for f in filters))
        paths = [r for r in rules if r["action"]["type"] == "block" and "resource-type" in r["trigger"]]
        self.assertEqual(len(paths), len(bb.BLOCKED_PATH_SEGMENTS))
        for r in paths:
            self.assertNotIn("document", r["trigger"]["resource-type"], "page navigations are never blocked by path")
            self.assertIn("*youtube.com", r["trigger"]["unless-domain"])
        kinds = [r["action"]["type"] for r in rules]
        # manifest exemptions must come after the path rules and before the domain rules
        self.assertLess(max(i for i, r in enumerate(rules) if "resource-type" in r["trigger"]), kinds.index("ignore-previous-rules"))
        for r in rules:
            self.assertNotIn("|", r["trigger"]["url-filter"], "WebKit content rules do not support alternation")

    def test_probe_picks_only_a_clear_winner(self):
        before = {10: 100, 11: 100, 12: 100}
        self.assertEqual(bb.pick_probe_pid(before, {10: 101, 11: 125, 12: 100}), 11)
        self.assertIsNone(bb.pick_probe_pid(before, {10: 101, 11: 102, 12: 100}), "too little CPU moved to trust")
        self.assertIsNone(bb.pick_probe_pid(before, {10: 122, 11: 125, 12: 100}), "two processes moved about equally")
        self.assertIsNone(bb.pick_probe_pid({}, {}), "no renderers at all")
        self.assertIsNone(bb.pick_probe_pid({10: None}, {10: 50}), "unreadable process is skipped")

    def test_memory_text(self):
        self.assertEqual(bb.format_memory_mb(None), "—")
        self.assertEqual(bb.format_memory_mb(51.4), "51 MB")
        self.assertEqual(bb.format_memory_mb(1536), "1.5 GB")

    def test_proc_readers_on_this_process(self):
        self.assertGreater(bb._proc_pss_mb(os.getpid()), 1.0)
        self.assertIsInstance(bb._proc_ticks(os.getpid()), int)
        self.assertIsNone(bb._proc_ticks(2 ** 22 + 12345))
        self.assertIsNone(bb._proc_pss_mb(2 ** 22 + 12345))
        self.assertIsInstance(bb.web_process_pids(), list)

    def test_user_agent_matches_the_engine(self):
        # Claiming Chrome from WebKit made Cloudflare's human verification fail every time.
        self.assertIn("AppleWebKit/605.1.15", bb.USER_AGENT)
        self.assertIn("Safari/605.1.15", bb.USER_AGENT)
        self.assertNotIn("Chrome/", bb.USER_AGENT)
        self.assertIn(f"Chrome/{bb.CHROME_UA_MAJOR}.0.0.0", bb.CHROME_USER_AGENT)

    def test_accessibility_bridge_guard(self):
        self.assertTrue(bb._should_disable_at_bridge({}, screen_reader_running=False))
        self.assertFalse(bb._should_disable_at_bridge({}, screen_reader_running=True), "a screen reader keeps it on")
        self.assertFalse(bb._should_disable_at_bridge({"ARROW_ACCESSIBILITY": "1"}, False), "user can opt in")
        self.assertFalse(bb._should_disable_at_bridge({"NO_AT_BRIDGE": "0"}, False), "an explicit choice is kept")
        self.assertIsInstance(bb._screen_reader_running(), bool)

    def test_fingerprint_script_skips_captcha_frames(self):
        self.assertIn(bb.FARBLING_EXEMPT_JS, bb.FARBLING_JS)
        self.assertNotIn("__ARROW_FARBLE_EXEMPT", bb.FARBLING_JS)
        for domain in ("challenges.cloudflare.com", "recaptcha.net", "hcaptcha.com"):
            self.assertIn(domain, bb.FARBLING_EXEMPT_JS)

    def test_fingerprint_script_gets_its_seed(self):
        script = bb.farbling_js(2 ** 32 + 7)
        self.assertNotIn("__ARROW_FARBLE_SEED__", script)
        self.assertIn("2166136261 ^ 7;", script)
        self.assertNotEqual(bb.farbling_js(1), bb.farbling_js(2))

    def test_site_host_of(self):
        self.assertEqual(bb.site_host_of("https://WWW.Example.com:8080/x"), "www.example.com")
        self.assertEqual(bb.site_host_of(""), "")
        self.assertEqual(bb.site_host_of("about:blank"), "")


class OfflineAndPagesTests(unittest.TestCase):
    def test_offline_detection_is_conservative(self):
        self.assertTrue(bb.looks_offline("Error resolving 'x.com': Temporary failure in name resolution"))
        self.assertTrue(bb.looks_offline("Network is unreachable"))
        # per-site problems must not be blamed on the user's internet
        if bb.Gio.NetworkMonitor.get_default().get_network_available():
            self.assertFalse(bb.looks_offline("Connection refused"))
            self.assertFalse(bb.looks_offline("Error resolving 'typo.invalid': Name or service not known"))

    def test_error_page_escapes_hostile_input(self):
        evil = 'https://x.com/"><script>alert(1)</script>'
        for offline in (True, False):
            html = bb.build_error_page('ev"il<h>', evil, "err <b>&@HEADING@", offline)
            self.assertNotIn("<script>alert", html)
            self.assertNotIn('ev"il<h>', html)
            self.assertIn("&lt;b&gt;&amp;@HEADING@", html, "error text must not be re-substituted")

    def test_notice_page(self):
        html = bb.build_notice_page("⚠️", "Heading", "<p>body</p>", '<a class="btn" href="#">Go</a>', tech="a<b")
        self.assertIn("Heading", html)
        self.assertIn("a&lt;b", html)
        self.assertNotIn("@ACTIONS@", html)


class ImportTests(TmpDirCase):
    def test_chromium_bookmarks_and_history(self):
        prof = os.path.join(self.tmp, "Default")
        os.makedirs(prof)
        write_json(os.path.join(prof, "Bookmarks"), {"roots": {"bookmark_bar": {"type": "folder", "children": [
            {"type": "url", "name": "Example", "url": "https://example.com/", "date_added": "13350000000000000"},
            {"type": "folder", "children": [{"type": "url", "name": "Deep", "url": "http://deep.test/"}]},
            {"type": "url", "name": "JS", "url": "javascript:alert(1)"}]}}})
        conn = sqlite3.connect(os.path.join(prof, "History"))
        conn.execute("CREATE TABLE urls (url TEXT, title TEXT, visit_count INT, last_visit_time INT)")
        conn.execute("INSERT INTO urls VALUES ('https://a.test/', 'A', 3, 13350000000000000)")
        conn.execute("INSERT INTO urls VALUES ('chrome://settings', 'S', 1, 13350000000000001)")
        conn.commit(); conn.close()
        marks = bb.read_chromium_bookmarks(prof)
        self.assertEqual({m["url"] for m in marks}, {"https://example.com/", "http://deep.test/"})
        self.assertTrue(1.6e9 < marks[0]["added"] < 1.8e9, "1601-epoch conversion")
        hist = bb.read_chromium_history(prof)
        self.assertEqual([h["url"] for h in hist], ["https://a.test/"])
        self.assertEqual(hist[0]["visits"], 3)

    def test_firefox_bookmarks_and_history(self):
        prof = os.path.join(self.tmp, "x.default")
        os.makedirs(prof)
        conn = sqlite3.connect(os.path.join(prof, "places.sqlite"))
        conn.execute("CREATE TABLE moz_places (id INTEGER PRIMARY KEY, url TEXT, title TEXT, visit_count INT, last_visit_date INT)")
        conn.execute("CREATE TABLE moz_bookmarks (id INTEGER PRIMARY KEY, type INT, fk INT, title TEXT, dateAdded INT)")
        conn.execute("INSERT INTO moz_places VALUES (1,'https://ff.test/','FF',2,1700000000000000)")
        conn.execute("INSERT INTO moz_places VALUES (2,'place:sort=1','Q',0,NULL)")
        conn.execute("INSERT INTO moz_bookmarks VALUES (1,1,1,'Bm',1700000000000000)")
        conn.execute("INSERT INTO moz_bookmarks VALUES (2,2,NULL,'folder',1)")
        conn.commit(); conn.close()
        self.assertEqual([b["url"] for b in bb.read_firefox_bookmarks(prof)], ["https://ff.test/"])
        self.assertEqual(bb.read_firefox_bookmarks(prof)[0]["added"], 1700000000)
        self.assertEqual([h["url"] for h in bb.read_firefox_history(prof)], ["https://ff.test/"])

    def test_find_profiles_and_read_profile_survives_bad_files(self):
        base = os.path.join(self.tmp, ".config", "google-chrome", "Default")
        os.makedirs(base)
        write_text(os.path.join(base, "Bookmarks"), "{not json")
        profiles = bb.find_importable_profiles(home=self.tmp)
        self.assertEqual([(p["browser"], p["profile"], p["kind"]) for p in profiles], [("Google Chrome", "Default", "chromium")])
        marks, hist, errors = bb.read_profile(profiles[0])
        self.assertEqual((marks, hist), ([], []))
        self.assertEqual(len(errors), 2, "both parts report their failure instead of crashing")

    def test_netscape_bookmarks_html(self):
        html = """<!DOCTYPE NETSCAPE-Bookmark-file-1><DL><p>
        <DT><H3>Folder</H3><DL><p>
        <DT><A HREF="https://a.test/?x=1&amp;y=2" ADD_DATE="1700000000" ICON="data:image/png;base64,AAAA">A &amp; B</A>
        <DT><a add_date="1600000000" href="http://b.test/">  <b>Bee</b> </a>
        <DT><A HREF="javascript:alert(1)">bad</A><DT><A HREF="">empty</A><DT><A>nohref</A></DL><p></DL><p>"""
        marks = bb.parse_netscape_bookmarks(html)
        self.assertEqual([(m["url"], m["title"], m["added"]) for m in marks],
                         [("https://a.test/?x=1&y=2", "A & B", 1700000000), ("http://b.test/", "Bee", 1600000000)])

    def test_merge_dedupes_and_respects_limits(self):
        existing = [{"url": "https://a/", "title": "A", "added": 1}]
        merged, added = bb.merge_bookmarks(existing, [{"url": "https://a/", "title": "dup", "added": 2},
                                                     {"url": "https://b/", "title": "B", "added": 3}])
        self.assertEqual((len(merged), added, merged[0]["title"]), (2, 1, "A"))
        _, added = bb.merge_bookmarks(existing, [{"url": f"https://n{i}/", "title": "", "added": 0} for i in range(10)], limit=3)
        self.assertEqual(added, 2)
        hist_old = [{"url": "https://a/", "last_visited": 100}]
        hist_new = [{"url": "https://a/", "last_visited": 999}, {"url": "https://b/", "last_visited": 500}]
        merged, added = bb.merge_history(hist_old, hist_new)
        self.assertEqual([e["url"] for e in merged], ["https://b/", "https://a/"])
        self.assertEqual(merged[1]["last_visited"], 100, "existing entry wins")
        self.assertEqual(added, 1)


class ClearOnExitCrashTests(TmpDirCase):
    def setUp(self):
        super().setUp()
        for name, value in (("CLEAR_ON_EXIT_MARKER", os.path.join(self.tmp, "clear-on-exit.pending")),
                            ("COOKIE_DB_FILE", os.path.join(self.tmp, "cookies.sqlite"))):
            self.addCleanup(setattr, bb, name, getattr(bb, name))
            setattr(bb, name, value)
        write_text(bb.COOKIE_DB_FILE, "x")
        write_text(bb.COOKIE_DB_FILE + "-journal", "x")

    def test_crashed_session_loses_its_cookies(self):
        dead = 2 ** 22 + 12345  # above pid_max's usual default, so never running
        write_text(bb.CLEAR_ON_EXIT_MARKER, str(dead))
        self.assertTrue(bb.clear_cookies_left_by_crash())
        self.assertFalse(os.path.exists(bb.COOKIE_DB_FILE))
        self.assertFalse(os.path.exists(bb.COOKIE_DB_FILE + "-journal"))
        self.assertFalse(os.path.exists(bb.CLEAR_ON_EXIT_MARKER))

    def test_running_browser_keeps_its_cookies(self):
        write_text(bb.CLEAR_ON_EXIT_MARKER, str(os.getppid()))
        self.assertFalse(bb.clear_cookies_left_by_crash())
        self.assertTrue(os.path.exists(bb.COOKIE_DB_FILE))

    def test_clean_exit_keeps_cookies(self):
        self.assertFalse(bb.clear_cookies_left_by_crash())
        self.assertTrue(os.path.exists(bb.COOKIE_DB_FILE))

    def test_marker_round_trip(self):
        bb.mark_clear_on_exit_pending()
        with open(bb.CLEAR_ON_EXIT_MARKER) as f:
            self.assertEqual(f.read(), str(os.getpid()))
        bb.unmark_clear_on_exit_pending()
        self.assertFalse(os.path.exists(bb.CLEAR_ON_EXIT_MARKER))
        bb.unmark_clear_on_exit_pending()  # already gone: no error


class SiteSettingsTests(TmpDirCase):
    def test_set_get_and_cleanup(self):
        s = {}
        bb.set_site_value(s, "a.com", "permissions", "allow", sub="media")
        bb.set_site_value(s, "a.com", "zoom", 1.5)
        self.assertEqual(bb.get_site_permission(s, "a.com", "media"), "allow")
        self.assertIsNone(bb.get_site_permission(s, "a.com", "location"))
        self.assertIsNone(bb.get_site_permission(s, "b.com", "media"))
        bb.set_site_value(s, "a.com", "permissions", None, sub="media")
        bb.set_site_value(s, "a.com", "zoom", None)
        self.assertEqual(s, {}, "empty entries are removed")
        bb.set_site_value(s, "", "zoom", 2)
        self.assertEqual(s, {}, "no host, no entry")

    def test_roundtrip_and_corrupt_file(self):
        old = bb.SITE_SETTINGS_FILE
        bb.SITE_SETTINGS_FILE = os.path.join(self.tmp, "site.json")
        self.addCleanup(setattr, bb, "SITE_SETTINGS_FILE", old)
        self.assertEqual(bb.load_site_settings(), {})
        bb.save_site_settings({"a.com": {"zoom": 1.2}})
        self.assertEqual(bb.load_site_settings(), {"a.com": {"zoom": 1.2}})
        self.assertEqual(oct(os.stat(bb.SITE_SETTINGS_FILE).st_mode & 0o777), "0o600")
        write_text(bb.SITE_SETTINGS_FILE, "garbage")
        self.assertEqual(bb.load_site_settings(), {})


class TrackerListTests(unittest.TestCase):
    LIST = "\n".join([
        "[Adblock Plus 2.0]", "! comment", "||tracker.example^", "||ads.example.net^$third-party",
        "||script.example^$script,third-party", "||only-on-site.example^$domain=news.com", "||neg.example^$~third-party",
        "@@||allowed.example^", "||path.example/ads^", "||wild*.example^", "example.com##.banner",
        "||google.com^", "||x.google.com^", "||recaptcha.net^", "||popup.example^$popup", "||UPPER.Example^",
    ])

    def test_parse_keeps_only_safe_whole_domain_rules(self):
        self.assertEqual(bb.parse_abp_domain_rules(self.LIST),
                         {"tracker.example", "ads.example.net", "script.example", "upper.example"})

    def test_rules_json_is_third_party_only_and_valid(self):
        rules = json.loads(bb.build_content_blocker_rules_json({"tracker.example"}))
        extra = [r for r in rules if "tracker\\.example" in r["trigger"]["url-filter"]]
        self.assertEqual(len(extra), 1)
        for r in extra:
            self.assertEqual(r["trigger"]["load-type"], ["third-party"])
            self.assertEqual(r["action"], {"type": "block"})
        base = json.loads(bb.build_content_blocker_rules_json())
        self.assertEqual(len(rules) - len(base), 1)

    def test_cache_roundtrip(self):
        tmp = tempfile.mkdtemp(); self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        old = bb.TRACKER_LIST_CACHE
        bb.TRACKER_LIST_CACHE = os.path.join(tmp, "t.json")
        self.addCleanup(setattr, bb, "TRACKER_LIST_CACHE", old)
        self.assertEqual(bb.load_tracker_list_cache(), (set(), 0.0))
        write_json(bb.TRACKER_LIST_CACHE, {"fetched": 5, "domains": ["a.example", 7]})
        self.assertEqual(bb.load_tracker_list_cache(), ({"a.example"}, 5.0))


class TrackerListFetchTests(TmpDirCase):
    def setUp(self):
        super().setUp()
        for name in ("TRACKER_LIST_CACHE", "CACHE_DIR"):
            self.addCleanup(setattr, bb, name, getattr(bb, name))
        bb.CACHE_DIR = self.tmp
        bb.TRACKER_LIST_CACHE = os.path.join(self.tmp, "t.json")

    def list_url(self, name, domains):
        path = os.path.join(self.tmp, name)
        write_text(path, "\n".join(f"||{d}^" for d in domains))
        return "file://" + path

    def test_lists_are_merged_in_priority_order(self):
        trackers = self.list_url("easyprivacy.txt", [f"t{i}.example" for i in range(150)] + ["shared.example"])
        ads = self.list_url("easylist.txt", [f"a{i}.example" for i in range(150)]
                            + ["shared.example", "sub.shared.example", "x.ad.example", "ad.example"])
        old_max = bb.TRACKER_LIST_MAX_DOMAINS
        self.addCleanup(setattr, bb, "TRACKER_LIST_MAX_DOMAINS", old_max)
        bb.TRACKER_LIST_MAX_DOMAINS = 200
        domains = bb.fetch_tracker_list((trackers, ads))
        self.assertEqual(len(domains), 200, "capped")
        self.assertTrue({f"t{i}.example" for i in range(150)} <= domains, "the first list is kept whole")
        self.assertNotIn("sub.shared.example", domains, "covered by shared.example")
        bb.TRACKER_LIST_MAX_DOMAINS = old_max
        domains = bb.fetch_tracker_list((trackers, ads))
        self.assertIn("ad.example", domains)
        self.assertNotIn("x.ad.example", domains, "covered by ad.example")
        with open(bb.TRACKER_LIST_CACHE) as f:
            self.assertEqual(json.load(f)["sources"], [trackers, ads])
        self.assertEqual(bb.load_tracker_list_cache()[0], domains)

    def test_one_bad_list_keeps_the_old_cache(self):
        write_json(bb.TRACKER_LIST_CACHE, {"fetched": 5, "domains": ["old.example"]})
        good = self.list_url("easyprivacy.txt", [f"t{i}.example" for i in range(150)])
        with self.assertRaises(ValueError):
            bb.fetch_tracker_list((good, self.list_url("easylist.txt", ["only.example"])))
        self.assertEqual(bb.load_tracker_list_cache(), ({"old.example"}, 5.0))

    def test_summary_spares_reading_the_whole_list(self):
        self.assertIsNone(bb.tracker_list_summary())
        write_json(bb.TRACKER_LIST_CACHE, {"fetched": 7, "domains": ["a.example", "b.example", 3]})
        summary = bb.tracker_list_summary()
        self.assertEqual((summary["fetched"], summary["count"], summary["sources"]), (7.0, 2, [bb.TRACKER_LIST_URLS[0]]))
        summary_path = os.path.join(self.tmp, "t-summary.json")
        self.assertTrue(os.path.exists(summary_path))
        with open(bb.TRACKER_LIST_CACHE, "r+") as f:  # same size and time: the list itself must not be read again
            st = os.stat(f.name)
            text = f.read().replace("a.example", "x.example")
            f.seek(0)
            f.write(text)
        os.utime(bb.TRACKER_LIST_CACHE, ns=(st.st_atime_ns, st.st_mtime_ns))
        os.chmod(bb.TRACKER_LIST_CACHE, 0)
        try:
            self.assertEqual(bb.tracker_list_summary()["count"], 2, "answered from the summary file")
        finally:
            os.chmod(bb.TRACKER_LIST_CACHE, 0o600)
        write_json(bb.TRACKER_LIST_CACHE, {"fetched": 9, "sources": ["s"], "domains": ["only.example"]})
        self.assertEqual(bb.tracker_list_summary()["count"], 1, "a changed list is summarised again")
        write_json(summary_path, "garbage")
        self.assertEqual(bb.tracker_list_summary()["fetched"], 9.0)

    def test_staleness(self):
        now = time.time()
        self.assertTrue(bb.tracker_list_is_stale(now), "nothing downloaded yet")
        write_json(bb.TRACKER_LIST_CACHE, {"fetched": now, "domains": ["a.example"]})
        self.assertTrue(bb.tracker_list_is_stale(now), "a cache from before EasyList was added")
        write_json(bb.TRACKER_LIST_CACHE, {"fetched": now, "sources": list(bb.TRACKER_LIST_URLS), "domains": []})
        self.assertFalse(bb.tracker_list_is_stale(now))
        self.assertTrue(bb.tracker_list_is_stale(now + bb.TRACKER_LIST_MAX_AGE + 1), "a week old")


class UrlRulesTests(TmpDirCase):
    PROVIDERS = {
        "globalRules": {"urlPattern": ".*", "rules": ["(?:%3F)?utm(?:_[a-z_]*)?", "(?:%3F)?[a-z]?mc"],
                        "referralMarketing": ["(?:%3F)?ref_?"],
                        "exceptions": ["^https?:\\/\\/(?:[a-z0-9-]+\\.)*?gitlab\\.com"]},
        "shop": {"urlPattern": "^https?:\\/\\/(?:[a-z0-9-]+\\.)*?shop\\.example", "rules": ["tag", "pf_rd_[a-z]*"],
                 "rawRules": ["\\/ref=[^/?]*"], "completeProvider": False},
        "search": {"urlPattern": "^https?:\\/\\/search\\.example", "rules": ["ved"],
                   "redirections": ["^https?:\\/\\/search\\.example\\/url\\?.*?(?:url|q)=([^&]+)"]},
        "blocked": {"urlPattern": "^https?:\\/\\/ads\\.example", "completeProvider": True},
        "broken": {"urlPattern": "^https?:\\/\\/broken\\.example", "rules": ["(?<bad", "id2"]},
        "notadict": "x",
    }

    def setUp(self):
        super().setUp()
        self.rules = bb.compile_url_rules(self.PROVIDERS)

    def clean(self, url):
        return bb.sanitize_url(url, self.rules)

    def test_site_rules(self):
        self.assertEqual(len(self.rules), 5, "the provider that isn't a dict is skipped")
        self.assertEqual(self.clean("https://www.shop.example/item/ref=sr_1?tag=aff&PF_RD_P=1&id=5&mc=1&amc=2"),
                         "https://www.shop.example/item?id=5")
        self.assertEqual(self.clean("https://other.example/?tag=aff&utm_x=1&ref=main"), "https://other.example/?tag=aff&ref=main",
                         "site rules stay on their site; referral tags (GitHub's ?ref=) are kept")
        self.assertEqual(self.clean("https://gitlab.com/a?mc=1&utm_source=x"), "https://gitlab.com/a?mc=1",
                         "an exception turns the downloaded rules off, built-in ones still apply")
        self.assertEqual(self.clean("https://ads.example/x?utm_source=1"), "https://ads.example/x", "pages are never blocked")
        self.assertEqual(self.clean("https://broken.example/?id2=1&k=2"), "https://broken.example/?k=2",
                         "a pattern Python can't compile is skipped, the rest still work")

    def test_background_compile_never_blocks(self):
        for name in ("URL_RULES_CACHE",):
            self.addCleanup(setattr, bb, name, getattr(bb, name))
        bb.URL_RULES_CACHE = os.path.join(self.tmp, "rules.json")
        write_json(bb.URL_RULES_CACHE, {"fetched": 9, "providers": self.PROVIDERS})
        self.assertEqual(bb.load_url_rules_cache(block=False), ([], 0.0), "not compiled yet: built-in cleaning only")
        deadline = time.time() + 5
        while not bb.load_url_rules_cache(block=False)[0] and time.time() < deadline:
            time.sleep(0.01)
        self.assertEqual(len(bb.load_url_rules_cache(block=False)[0]), 5)

    def test_tracking_redirect_is_skipped(self):
        self.assertEqual(self.clean("https://search.example/url?ved=1&q=https%3A%2F%2Fshop.example%2Fp%3Ftag%3Da%26id%3D5&usg=2"),
                         "https://shop.example/p?id=5", "the destination is cleaned too")
        self.assertEqual(self.clean("https://search.example/url?q=javascript%3Aalert(1)&ved=1"),
                         "https://search.example/url?q=javascript%3Aalert(1)", "only http(s) destinations")
        self.assertEqual(bb.secure_and_clean_url("https://search.example/url?q=http%3A%2F%2Fnews.example%2F",
                                                 url_rules=self.rules), ("https://news.example/", True, True),
                         "a destination reached by skipping a redirect is upgraded to HTTPS too")

    def test_fetch_falls_back_and_caches(self):
        for name in ("URL_RULES_CACHE", "CACHE_DIR"):
            self.addCleanup(setattr, bb, name, getattr(bb, name))
        bb.CACHE_DIR = self.tmp
        bb.URL_RULES_CACHE = os.path.join(self.tmp, "rules.json")
        self.assertEqual(bb.load_url_rules_cache(), ([], 0.0))
        providers = {f"site{i}": {"urlPattern": f"^https?:\\/\\/site{i}\\.example", "rules": ["sid"]} for i in range(60)}
        good = os.path.join(self.tmp, "data.json")
        write_json(good, {"providers": providers})
        small = os.path.join(self.tmp, "small.json")
        write_json(small, {"providers": self.PROVIDERS})
        with self.assertRaises(ValueError):
            bb.fetch_url_rules(("file://" + small,))
        self.assertEqual(bb.fetch_url_rules(("file://" + os.path.join(self.tmp, "missing.json"), "file://" + good)), 60)
        rules, fetched = bb.load_url_rules_cache()
        self.assertEqual(len(rules), 60)
        self.assertGreater(fetched, 0)
        self.assertIs(bb.load_url_rules_cache()[0], rules, "compiled once, not on every navigation")
        self.assertIs(bb.load_url_rules_cache(block=False)[0], rules)
        self.assertEqual(bb.sanitize_url("https://site7.example/?sid=1&a=2", rules), "https://site7.example/?a=2")


class LaunchTests(TmpDirCase):
    """Every way of starting the browser goes through the same import-based start, so the compiled code
    in __pycache__ is reused instead of recompiling arrow_browser.py on each launch."""
    LAUNCHERS = ("arrow-browser", "install-ubuntu.sh", "install-fedora.sh", "install-wsl.sh")

    def fake_app(self, directory):
        os.makedirs(directory, exist_ok=True)
        write_text(os.path.join(directory, "arrow_browser.py"),
                   "import sys, json\nif __name__ == '__main__':\n    print(json.dumps([__name__, __file__, sys.argv]))\n")

    def test_launchers_share_one_start_command(self):
        for name in self.LAUNCHERS:
            with open(os.path.join(ROOT, name)) as f:
                text = f.read()
            self.assertIn("python3 -c '" + bb.LAUNCH_SNIPPET + "'", text, name)
            self.assertNotIn("exec python3 \"", text.replace("exec python3 -c", ""), name + " still runs the file directly")

    def test_start_command_runs_the_file_as_main_and_caches_it(self):
        import subprocess
        app = os.path.join(self.tmp, "app")
        self.fake_app(app)
        argv = bb.launch_argv(os.path.join(app, "arrow_browser.py"), ["--x", "https://a.example"])
        out = json.loads(subprocess.run(argv, capture_output=True, text=True, check=True).stdout)
        self.assertEqual(out, ["__main__", os.path.join(app, "arrow_browser.py"),
                               [os.path.join(app, "arrow_browser.py"), "--x", "https://a.example"]])
        self.assertTrue(any(n.startswith("arrow_browser.") for n in os.listdir(os.path.join(app, "__pycache__"))))

    def test_launcher_prefers_the_per_user_copy(self):
        import subprocess
        user_app = os.path.join(self.tmp, ".local", "share", "arrow-browser")
        self.fake_app(user_app)
        out = subprocess.run(["bash", os.path.join(ROOT, "arrow-browser"), "https://b.example"],
                             capture_output=True, text=True, check=True, env=dict(os.environ, HOME=self.tmp)).stdout
        self.assertEqual(json.loads(out)[2], [os.path.join(user_app, "arrow_browser.py"), "https://b.example"])


class StatsTests(TmpDirCase):
    def test_roundtrip_and_defaults(self):
        old = bb.STATS_FILE
        bb.STATS_FILE = os.path.join(self.tmp, "s.json")
        self.addCleanup(setattr, bb, "STATS_FILE", old)
        fresh = bb.load_privacy_stats()
        self.assertEqual((fresh["blocked"], fresh["params"], fresh["https"]), (0, 0, 0))
        bb.save_privacy_stats({"since": 1.0, "blocked": 4, "params": 2, "https": 9})
        self.assertEqual(bb.load_privacy_stats(), {"since": 1.0, "blocked": 4, "params": 2, "https": 9})


class UpdateInfoTests(unittest.TestCase):
    """fetch_release_info must prefer the API, fall back to the cached raw address, and fail loudly."""

    def _run(self, responses):
        calls = []

        class Resp:
            def __init__(self, status, body): self.status, self.body = status, body
            def read(self, n): return self.body
            def __enter__(self): return self
            def __exit__(self, *a): return False

        def fake_urlopen(req, timeout=0):
            calls.append((req.full_url, req.get_header("Accept")))
            outcome = responses[len(calls) - 1]
            if isinstance(outcome, Exception):
                raise outcome
            return Resp(*outcome)

        original = bb.urllib.request.urlopen
        bb.urllib.request.urlopen = fake_urlopen
        try:
            return bb.fetch_release_info("test", sources=bb.UPDATE_INFO_SOURCES), calls
        finally:
            bb.urllib.request.urlopen = original

    def test_api_answer_wins(self):
        data, calls = self._run([(200, b'{"version": "9.9.9", "sha256": "x"}')])
        self.assertEqual(data["version"], "9.9.9")
        self.assertEqual(len(calls), 1)
        self.assertIn("api.github.com", calls[0][0])
        self.assertEqual(calls[0][1], "application/vnd.github.raw+json")

    def test_falls_back_when_api_is_rate_limited_or_odd(self):
        for first in (OSError("HTTP Error 403: rate limit exceeded"), (200, b"not json"), (200, b'{"nope": 1}'), (500, b"")):
            data, calls = self._run([first, (200, b'{"version": "1.2.3"}')])
            self.assertEqual(data["version"], "1.2.3")
            self.assertIn("raw.githubusercontent.com", calls[1][0])

    def test_version_must_be_plain_numbers(self):
        # it goes into the download address and on-screen markup
        for bad in (b'{"version": "../main"}', b'{"version": "1.2.3<b>"}', b'{"version": "1.2"}'):
            with self.assertRaises(ValueError):
                self._run([(200, bad), (200, bad)])

    def test_raises_when_every_source_fails(self):
        with self.assertRaises(OSError):
            self._run([OSError("boom1"), OSError("boom2")])


@unittest.skipUnless(os.environ.get("ARROW_TEST_KEYRING", "1") == "1", "keyring tests disabled")
class SecretServiceTests(unittest.TestCase):
    def test_logins_saved_before_the_rename_are_found_and_moved(self):
        old = bb.SecretServiceClient(application="arrow-browser-test-old", legacy_applications=())
        if not old.available():
            self.skipTest(f"no Secret Service on this machine: {old.error}")
        new = bb.SecretServiceClient(application="arrow-browser-test", legacy_applications=("arrow-browser-test-old",))
        host = f"rename-{int(time.time())}.example"
        try:
            self.assertTrue(old.store(host, "alice", "before"))
            found = new.find(host)
            self.assertEqual([(f["host"], f["username"]) for f in found], [(host, "alice")], "old login still found")
            self.assertEqual(new.get_password(found[0]["item"]), "before")
            self.assertTrue(new.store(host, "alice", "after"))
            self.assertEqual(old.find(host), [], "saved again under the new name, old entry removed")
            found = new.find(host)
            self.assertEqual(len(found), 1)
            self.assertEqual(new.get_password(found[0]["item"]), "after")
        finally:
            for client in (old, new):
                for f in client.find(host):
                    client.delete(f["item"])

    def test_roundtrip_against_real_keyring(self):
        client = bb.SecretServiceClient(application="arrow-browser-test")
        if not client.available():
            self.skipTest(f"no Secret Service on this machine: {client.error}")
        host = f"unittest-{int(time.time())}.example"
        try:
            self.assertTrue(client.store(host, "alice", "s3cret é中"))
            self.assertTrue(client.store(host, "alice", "changed"), "same user replaces, not duplicates")
            found = client.find(host)
            self.assertEqual([(f["host"], f["username"]) for f in found], [(host, "alice")])
            self.assertEqual(client.get_password(found[0]["item"]), "changed")
            self.assertEqual(client.find("other-" + host), [])
        finally:
            for f in client.find(host):
                client.delete(f["item"])
        self.assertEqual(client.find(host), [])


class GpuDriverTests(TmpDirCase):
    def add_card(self, card, driver):
        os.makedirs(os.path.join(self.tmp, "drivers", driver), exist_ok=True)
        os.makedirs(os.path.join(self.tmp, "drm", card, "device"))
        os.symlink(os.path.join(self.tmp, "drivers", driver), os.path.join(self.tmp, "drm", card, "device", "driver"))

    def test_legacy_radeon_driver_is_unstable(self):
        self.add_card("card0", "radeon")
        self.assertTrue(bb._gpu_driver_is_unstable(os.path.join(self.tmp, "drm")))

    def test_other_drivers_are_fine(self):
        self.add_card("card0", "amdgpu")
        self.add_card("card1", "i915")
        self.assertFalse(bb._gpu_driver_is_unstable(os.path.join(self.tmp, "drm")))
        self.assertFalse(bb._gpu_driver_is_unstable(os.path.join(self.tmp, "missing")))

    def test_gpu_on_forces_compositing(self):
        env = {"WEBKIT_SKIA_ENABLE_CPU_RENDERING": "1"}
        bb._apply_gpu_environment(env, gpu_enabled=True, driver_unstable=False)
        self.assertEqual(env["WEBKIT_FORCE_COMPOSITING_MODE"], "1")
        self.assertNotIn("WEBKIT_DISABLE_COMPOSITING_MODE", env)

    def test_gpu_off_keeps_compositing_available(self):
        # Disabling compositing leaves WebKit without a backing store and crashes the UI process.
        env = {"WEBKIT_FORCE_COMPOSITING_MODE": "1"}
        bb._apply_gpu_environment(env, gpu_enabled=False, driver_unstable=False)
        self.assertEqual(env, {"WEBKIT_SKIA_ENABLE_CPU_RENDERING": "1"})

    def test_gpu_off_on_radeon_still_disables_compositing(self):
        env = {}
        bb._apply_gpu_environment(env, gpu_enabled=False, driver_unstable=True)
        self.assertEqual(env["WEBKIT_DISABLE_COMPOSITING_MODE"], "1")
        self.assertEqual(env["WEBKIT_SKIA_ENABLE_CPU_RENDERING"], "1")

    def test_gpu_off_lifts_acceleration_policy_only_while_fullscreen(self):
        # Policy NEVER turns fullscreen video black on WebKitGTK 2.52.
        self.assertTrue(bb._wants_accelerated_policy(gpu_enabled=True, fullscreen=False, driver_unstable=False))
        self.assertFalse(bb._wants_accelerated_policy(gpu_enabled=False, fullscreen=False, driver_unstable=False))
        self.assertTrue(bb._wants_accelerated_policy(gpu_enabled=False, fullscreen=True, driver_unstable=False))
        self.assertFalse(bb._wants_accelerated_policy(gpu_enabled=False, fullscreen=True, driver_unstable=True))


class MemoryPressureTests(unittest.TestCase):
    def test_low_means_under_ten_percent_or_400_mb_available(self):
        self.assertTrue(bb.is_memory_low(600, 8000), "under 10% of 8 GB")
        self.assertFalse(bb.is_memory_low(900, 8000))
        self.assertTrue(bb.is_memory_low(350, 2000), "under the 400 MB floor on a small machine")
        self.assertFalse(bb.is_memory_low(450, 2000))

    def test_reads_proc_meminfo(self):
        available, total = bb.system_memory_mb()
        self.assertGreater(total, 0)
        self.assertTrue(0 < available <= total)


class WebProcessCrashTests(unittest.TestCase):
    """on_web_process_terminated named a reason WebKit doesn't have (EXCEEDED_MEMORY), so every crash raised
    AttributeError: crashed tabs were never reloaded and no notice page appeared."""

    def terminate(self, reason):
        from types import SimpleNamespace
        from unittest import mock
        browser = SimpleNamespace(_crash_counts={}, homepage="about:blank", context_id=0,
                                  statusbar=mock.Mock(), MAX_AUTO_RELOAD_CRASHES=3)
        webview = mock.Mock()
        webview.get_uri.return_value = "https://example.com/"
        with mock.patch.object(bb.GLib, "idle_add", lambda fn: fn()):
            bb.ArrowBrowserWindow.on_web_process_terminated(browser, webview, reason)
        return webview

    def test_crashed_tab_reloads(self):
        webview = self.terminate(bb.WebKit2.WebProcessTerminationReason.CRASHED)
        webview.load_uri.assert_called_once_with("https://example.com/")

    def test_out_of_memory_tab_shows_notice(self):
        webview = self.terminate(bb.WebKit2.WebProcessTerminationReason.EXCEEDED_MEMORY_LIMIT)
        webview.load_uri.assert_not_called()
        self.assertIn("ran out of memory", webview.load_html.call_args[0][0])



class WellbeingTests(TmpDirCase):
    def tracker(self):
        return bb.WellbeingTracker(os.path.join(self.tmp, "wellbeing.json"))

    def test_site_groups_subdomains_and_ignores_non_web_pages(self):
        self.assertEqual(bb.wellbeing_site("https://m.youtube.com/watch?v=1"), "youtube.com")
        self.assertEqual(bb.wellbeing_site("https://www.bbc.co.uk/news"), "bbc.co.uk")
        self.assertEqual(bb.wellbeing_site("http://127.0.0.1:8080/x"), "127.0.0.1")
        self.assertEqual(bb.wellbeing_site("http://localhost:3000/"), "localhost")
        for uri in ("about:blank", "arrow://times-up?t=x", "file:///home/a.html", "", None):
            self.assertEqual(bb.wellbeing_site(uri), "", uri)
        self.assertEqual(bb.wellbeing_site_from_input(" https://www.YouTube.com/feed "), "youtube.com")
        self.assertEqual(bb.wellbeing_site_from_input("reddit.com"), "reddit.com")
        self.assertEqual(bb.wellbeing_site_from_input("not a site"), "")

    def test_bedtime_runs_past_midnight(self):
        start, end = bb.parse_clock("23:00", "0:0"), bb.parse_clock("07:00", "0:0")
        self.assertEqual((start, end), (23 * 60, 7 * 60))
        self.assertTrue(bb.in_bedtime(23 * 60 + 30, start, end))
        self.assertTrue(bb.in_bedtime(3 * 60, start, end))
        self.assertFalse(bb.in_bedtime(7 * 60, start, end))
        self.assertFalse(bb.in_bedtime(12 * 60, start, end))
        self.assertTrue(bb.in_bedtime(21 * 60, 20 * 60, 22 * 60))
        self.assertFalse(bb.in_bedtime(5, 60, 60), "same start and end means no bedtime")
        self.assertEqual(bb.parse_clock("25:99", "23:00"), 23 * 60, "bad times fall back to the default")
        evening = time.mktime((2026, 10, 8, 23, 30, 0, 0, 0, -1))
        night = time.mktime((2026, 10, 9, 1, 0, 0, 0, 0, -1))
        self.assertEqual(bb.bedtime_night(evening, start, end), bb.bedtime_night(night, start, end),
                         "1 am belongs to the night that began at 11 pm")

    def test_limits_extra_time_and_saving(self):
        t, now = self.tracker(), time.time()
        t.set_limit("youtube.com", 1)
        t.add("youtube.com", 55, now)
        self.assertFalse(t.over_limit("youtube.com", now))
        t.add("youtube.com", 5, now)
        self.assertTrue(t.over_limit("youtube.com", now))
        self.assertFalse(t.over_limit("github.com", now), "sites without a limit are never over")
        t.grant_extra("youtube.com", bb.WELLBEING_EXTRA_SECONDS, now)
        self.assertFalse(t.over_limit("youtube.com", now))
        self.assertTrue(t.over_limit("youtube.com", now + 86400) is False and t.used("youtube.com", now + 86400) == 0,
                        "a new day starts from zero")
        t.add("github.com", 30, now)
        t.save()
        again = self.tracker()
        self.assertEqual(again.limits, {"youtube.com": 1})
        self.assertEqual(again.used("youtube.com", now), 60)
        self.assertEqual(again.totals(1, now), [("youtube.com", 60), ("github.com", 30)])
        again.clear()
        self.assertEqual(self.tracker().totals(7, now), [])
        self.assertEqual(self.tracker().limits, {"youtube.com": 1}, "clearing screen time keeps the limits")

    def test_old_days_are_dropped(self):
        t, now = self.tracker(), time.time()
        for back in range(20):
            t.add("a.com", 10, now - back * 86400)
        self.assertEqual(len(t.days), bb.WELLBEING_KEEP_DAYS)
        self.assertEqual(t.totals(7, now), [("a.com", 70)])

    def test_damaged_file_is_ignored(self):
        path = os.path.join(self.tmp, "wellbeing.json")
        write_text(path, "{not json")
        self.assertEqual(self.tracker().limits, {})
        write_json(path, {"days": {"2026-10-08": {"a.com": "x", "b.com": 5}}, "limits": {"a.com": True, "b.com": 20}})
        t = self.tracker()
        self.assertEqual(t.days, {"2026-10-08": {"b.com": 5.0}})
        self.assertEqual(t.limits, {"b.com": 20})

    def test_break_reminder_after_continuous_browsing(self):
        t = self.tracker()

        def browse(start, stop):  # one call every 5 seconds, like the window's tick
            return [now for now in range(start, stop, 5) if t.break_due(now, 600)]

        self.assertEqual(browse(0, 1300), [600, 1200], "every 10 minutes of browsing")
        pause = bb.WELLBEING_BREAK_RESET_SECONDS + 5
        self.assertEqual(browse(1300 + pause, 1300 + pause + 595), [], "a 5-minute pause starts the count again")
        self.assertEqual(browse(1300 + pause + 595, 1300 + pause + 700), [1300 + pause + 600])

if __name__ == "__main__":
    unittest.main()
