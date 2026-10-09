#!/usr/bin/env python3
"""Integration tests that drive the real browser window (needs a display).
They use a throw-away HOME and local HTTP servers, never the network or your profile.
Run: python3 -m unittest discover -s tests -v"""
import http.server
import importlib.util
import json
import os
import shutil
import ssl
import subprocess
import tempfile
import threading
import time
import unittest
import warnings

warnings.filterwarnings("ignore", category=DeprecationWarning)

# Must be set before the browser module computes its config paths at import time.
_HOME = tempfile.mkdtemp(prefix="arrow-test-home-")
os.environ["HOME"] = _HOME

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
spec = importlib.util.spec_from_file_location("bb_window", os.path.join(ROOT, "arrow_browser.py"))
bb = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bb)
from gi.repository import Gdk, Gio, GLib, Gtk, WebKit2  # noqa: E402

HAVE_DISPLAY = Gtk.init_check()[0] if isinstance(Gtk.init_check(), tuple) else bool(Gtk.init_check())

ARTICLE = ("<html><head><title>Test Article</title><meta name='author' content='A. Writer'></head><body>"
           "<nav><a href='/'>Home</a> <a href='/menu'>Menu</a></nav><div class='content'><h1>The Great Test</h1>"
           + "".join(f"<p>Paragraph {i}: the quick brown fox jumps over the lazy dog while the test "
                     f"checks that a long article page loads and keeps its text.</p>" for i in range(6))
           + "<div class='share'><a href='/s'>Share this</a></div></div><footer>Copyright</footer></body></html>")
PAGES = {
    "/blank": "<html><title>blank</title></html>",
    "/article": ARTICLE,
    "/thin": "<html><title>thin</title><body><p>short</p></body></html>",
    "/login": ("<html><title>login</title><body><form action='/done' method='get'>"
               "<input id='u' type='text' name='user'><input id='p' type='password' name='pw'>"
               "<button id='go' type='submit'>Sign in</button></form></body></html>"),
    "/done": "<html><title>done</title><body>ok</body></html>",
    "/js": "<html><head><title>js-off</title></head><body><script>document.title='js-ran'</script></body></html>",
    "/pathrules": ("<html><title>pathrules</title><body><img src='/pagead/p.png'><img src='/sub/ads/p.png'>"
                   "<img src='/telemetry.png'><img src='/pagead/stream.m3u8'><img src='/roads/ok.png'><img src='/adsense.png'>"
                   "<img src='/fine/ok.png'></body></html>"),
    "/ads/landing": "<html><title>landing</title><body>an ordinary page whose address contains /ads/</body></html>",
    "/mem-heavy": ("<html><title>mem-heavy</title><body><script>window.keep=[];for(let i=0;i<20;i++){"
                   "let a=new Float64Array(1000000);a.fill(i+1);window.keep.push(a)}</script>heavy</body></html>"),
    "/form": "<html><title>form</title><body><textarea id='t'></textarea></body></html>",
    "/third": "<html><title>third</title><body><img src='http://localhost:%PORT%/pixel'></body></html>",
    # a single-page site (like YouTube): moves to another address without loading a new page
    "/spa": ("<html><title>spa</title><body><script>window.go=n=>history.pushState({},'','/spa/watch?v='+n)"
             "</script></body></html>"),
    "/framed": "<html><title>framed</title><body><iframe src='/thin?utm_source=frame'></iframe></body></html>",
    "/darksite": ("<html><head><title>darksite</title><style>.dk{background:#121212;color:#eee}</style></head>"
                  "<body class='dk'>already dark</body></html>"),
    "/opener": "<html><title>opener</title><body><a id='p' target='_blank' href='/done?utm_source=mail&k=1'>open</a></body></html>",
}


BIG_FILE = bytes(range(256)) * 4096  # 1 MiB with a pattern, so a misplaced byte shows

class Handler(http.server.BaseHTTPRequestHandler):
    hits = {}
    requests = []  # full paths, query included
    download_requests = []  # (path, Range header, Cookie header) for /big.dat and /norange.dat
    download_delay = 0.01

    def do_GET(self):
        path = self.path.split("?")[0]
        Handler.hits[path] = Handler.hits.get(path, 0) + 1
        Handler.requests.append(self.path)
        if path == "/dl":  # the real name only comes in Content-Disposition
            body = b"%PDF-1.4 test"
            self.send_response(200)
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("Content-Disposition", 'attachment; filename="Report 2026.pdf"')
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if path in ("/big.dat", "/norange.dat"):  # a slow download; /big.dat can send just a part (Range)
            Handler.download_requests.append((path, self.headers.get("Range"), self.headers.get("Cookie")))
            body, start = BIG_FILE, 0
            wanted = self.headers.get("Range") if path == "/big.dat" else None
            if wanted and wanted.startswith("bytes=") and wanted.endswith("-"):
                start = int(wanted[6:-1])
                if start >= len(body):
                    self.send_response(416)
                    self.send_header("Content-Range", f"bytes */{len(body)}")
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                    return
                self.send_response(206)
                self.send_header("Content-Range", f"bytes {start}-{len(body) - 1}/{len(body)}")
            else:
                self.send_response(200)
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("Content-Disposition", f'attachment; filename="{path[1:]}"')
            self.send_header("Accept-Ranges", "bytes" if path == "/big.dat" else "none")
            self.send_header("ETag", '"v1"')
            self.send_header("Content-Length", str(len(body) - start))
            self.end_headers()
            try:
                for i in range(start, len(body), 8192):
                    self.wfile.write(body[i:i + 8192])
                    self.wfile.flush()
                    time.sleep(Handler.download_delay)
            except (BrokenPipeError, ConnectionResetError):
                pass  # the browser stopped (paused or cancelled)
            return
        if path == "/broken.zip":  # promises more than it sends, then hangs up
            self.send_response(200)
            self.send_header("Content-Type", "application/zip")
            self.send_header("Content-Length", "100000")
            self.end_headers()
            self.wfile.write(b"PK" * 5)
            self.wfile.flush()
            self.close_connection = True
            return
        if path.endswith(".desktop"):
            body = b"[Desktop Entry]\nType=Application\nExec=true\n"
            self.send_response(200)
            self.send_header("Content-Type", "application/x-desktop")
            self.send_header("Content-Disposition", "attachment")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if path == "/pixel" or path.endswith(".png"):
            body, ctype = b"\x89PNG", "image/png"
        else:
            body = PAGES.get(path, "<html><title>404</title></html>").replace("%PORT%", str(self.server.server_port)).encode()
            ctype = "text/html"
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


class TLSServer(http.server.ThreadingHTTPServer):
    """HTTPS test server. The TLS handshake runs in each connection's own thread: done in the accept loop,
    one connection that never finishes its handshake would stall every other one."""
    tls = None

    def finish_request(self, request, client_address):
        try:
            request = self.tls.wrap_socket(request, server_side=True)
        except (ssl.SSLError, OSError):
            return  # the browser rejected the certificate
        super().finish_request(request, client_address)


def spin(condition, timeout=10.0):
    end = time.time() + timeout
    while time.time() < end:
        while Gtk.events_pending():
            Gtk.main_iteration_do(False)
        if condition():
            return True
        time.sleep(0.02)
    return condition()


def js(webview, script, timeout=5.0):
    box = {}

    def done(wv, result, _):
        try:
            box["v"] = wv.run_javascript_finish(result).get_js_value().to_string()
        except Exception as e:
            box["v"] = f"ERR {e}"

    webview.run_javascript(script, None, done, None)
    spin(lambda: "v" in box, timeout)
    return box.get("v")


class FakeSecrets:
    def __init__(self):
        self.items = {}
        self.error = ""

    def available(self):
        return True

    def store(self, host, user, password):
        self.items[(host, user)] = password
        return True

    def find(self, host=None):
        return [{"item": f"{h}|{u}", "host": h, "username": u} for (h, u) in sorted(self.items) if host in (None, h)]

    def get_password(self, item):
        h, u = item.split("|")
        return self.items.get((h, u))

    def delete(self, item):
        h, u = item.split("|")
        return self.items.pop((h, u), None) is not None


@unittest.skipUnless(HAVE_DISPLAY and os.environ.get("DISPLAY"), "needs a display")
class WindowFeatureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        cls.port = cls.server.server_port
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        cls.base = f"http://127.0.0.1:{cls.port}"
        # HTTPS with a self-signed certificate, which no system trusts
        cls.cert_file, key_file = os.path.join(_HOME, "test-cert.pem"), os.path.join(_HOME, "test-key.pem")
        subprocess.run(["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "30",
                        "-keyout", key_file, "-out", cls.cert_file,
                        "-subj", "/O=Arrow Test Issuer/CN=arrow-test.example",
                        "-addext", "subjectAltName=IP:127.0.0.1,IP:127.0.0.2"], check=True, capture_output=True)
        TLSServer.tls = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        TLSServer.tls.load_cert_chain(cls.cert_file, key_file)
        cls.tls_servers = {}
        for address in ("127.0.0.1", "127.0.0.2"):
            server = TLSServer((address, 0), Handler)
            threading.Thread(target=server.serve_forever, daemon=True).start()
            cls.tls_servers[address] = server
        os.makedirs(bb.CONFIG_DIR, exist_ok=True)
        with open(bb.CONFIG_FILE, "w") as f:
            json.dump({"homepage": cls.base + "/blank", "open_homepage_on_startup": True,
                       "first_run_greeted": True, "tracker_lists_enabled": True}, f)
        # a tracker "list" that blocks third-party loads from the name `localhost`
        os.makedirs(bb.CACHE_DIR, exist_ok=True)
        with open(bb.TRACKER_LIST_CACHE, "w") as f:
            json.dump({"fetched": time.time(), "domains": ["localhost"]}, f)
        bb.ArrowBrowserWindow._maybe_refresh_tracker_list = lambda self: False
        bb.ArrowBrowserWindow.start_auto_git_update_check = lambda self: False
        cls.win = bb.ArrowBrowserWindow()
        cls.win.show_all()
        cls.win.secrets = FakeSecrets()
        assert spin(lambda: cls.win.content_filter is not None, 20), "content filter never compiled"

    @classmethod
    def tearDownClass(cls):
        cls.win.destroy()
        cls.server.shutdown()
        for server in cls.tls_servers.values():
            server.shutdown()
        shutil.rmtree(_HOME, ignore_errors=True)

    def setUp(self):
        self.win.site_settings.clear()
        self.win._clear_infobar()
        Handler.hits.clear()
        Handler.requests.clear()

    def load(self, path, wait_title=None):
        wv = self.win.get_active_webview()
        wv.load_uri(self.base + path)
        self.assertTrue(spin(lambda: not wv.is_loading() and (wv.get_uri() or "").endswith(path.split("?")[0])
                             and (wait_title is None or wv.get_title() == wait_title), 10), f"{path} did not load")
        return wv

    # ---- dark mode -----------------------------------------------------
    def test_dark_mode_darkens_light_pages_and_leaves_dark_ones_alone(self):
        win = self.win
        filtered = "getComputedStyle(document.documentElement).filter !== 'none'"
        self.assertFalse(win.dark_mode_active)
        self.assertFalse(hasattr(win, "btn_dark"), "dark mode lives in Settings, not on the toolbar")
        try:
            wv = self.load("/darksite", "darksite")
            win.set_dark_mode(True)  # switched on while a dark page is showing
            self.assertTrue(spin(lambda: js(wv, filtered) == "false", 3), "already-dark page was inverted (turns white)")
            self.load("/thin", "thin")
            self.assertTrue(spin(lambda: js(wv, filtered) == "true", 3), "light page not darkened")
            js(wv, "document.body.style.background = '#121212'")  # the site switches to its own dark theme
            self.assertTrue(spin(lambda: js(wv, filtered) == "false", 3), "page that turned dark still inverted")
            self.load("/darksite", "darksite")
            self.assertTrue(spin(lambda: js(wv, filtered) == "false", 3), "newly loaded dark page was inverted")
        finally:
            win.set_dark_mode(False)

    # ---- digital wellbeing ---------------------------------------------
    def wellbeing_on(self):
        win, tracker = self.win, bb.wellbeing_tracker()
        win.wellbeing_enabled = True
        win._clear_infobar()

        def reset():
            win.wellbeing_enabled = win.bedtime_enabled = False
            win._update_bedtime(time.time())
            win.set_dark_mode(False)
            win._clear_infobar()
            tracker.limits.clear()
            tracker.clear()
            tracker.tokens.clear()
            tracker.bedtime_snoozed = tracker.bedtime_greeted = ""
            tracker.last_active = tracker.next_break = None
        self.addCleanup(reset)
        return win, tracker

    def infobar_text(self):
        bar = self.win._infobar
        return bar.get_content_area().get_children()[0].get_text() if bar else ""

    def test_screen_time_counts_only_the_site_in_front_and_limits_close_it(self):
        win, tracker = self.wellbeing_on()
        wv, site = self.load("/thin", "thin"), "127.0.0.1"
        now = time.time()
        win._wellbeing_step(now, time.monotonic(), False)
        self.assertEqual(tracker.used(site, now), 0, "not counted while another window is in front")
        win._wellbeing_step(now, time.monotonic(), True)
        self.assertEqual(tracker.used(site, now), win.WELLBEING_TICK_SECONDS)

        tracker.set_limit(site, 1)
        tracker.add(site, 60, now)
        win._wellbeing_step(now, time.monotonic(), False)  # limits apply even when not in front
        self.assertTrue(spin(lambda: (wv.get_uri() or "").startswith("arrow://times-up"), 5), wv.get_uri())
        self.assertTrue(spin(lambda: js(wv, "document.querySelector('h1').innerText") == "Time's up for 127.0.0.1", 5))

        wv.load_uri(self.base + "/done")  # the site stays closed for the rest of the day
        self.assertTrue(spin(lambda: (wv.get_uri() or "").startswith("arrow://times-up"), 5), wv.get_uri())
        allowed = tracker.allowed(site)
        wv.load_uri("arrow://wellbeing-more?t=made-up")  # a page can't hand itself more time
        self.assertTrue(spin(lambda: not wv.is_loading(), 5))
        self.assertEqual(tracker.allowed(site), allowed)

        wv.load_uri(self.base + "/done")
        self.assertTrue(spin(lambda: (wv.get_uri() or "").startswith("arrow://times-up"), 5))
        self.assertTrue(spin(lambda: js(wv, "document.querySelector('a.btn') !== null") == "true", 5))
        more = js(wv, "document.querySelector('a.btn').href")
        js(wv, "document.querySelector('a.btn').click()")
        self.assertTrue(spin(lambda: wv.get_uri() == self.base + "/done" and wv.get_title() == "done", 10),
                        "5 more minutes goes back to the page")
        self.assertEqual(tracker.allowed(site), allowed + bb.WELLBEING_EXTRA_SECONDS)
        wv.load_uri(more)
        self.assertTrue(spin(lambda: wv.get_uri() == more and not wv.is_loading(), 5))
        self.assertEqual(tracker.allowed(site), allowed + bb.WELLBEING_EXTRA_SECONDS, "each button works once")

    def test_break_reminder_and_snooze(self):
        win, tracker = self.wellbeing_on()
        self.load("/thin", "thin")
        now = time.monotonic()
        win._wellbeing_step(time.time(), now, True)
        win._wellbeing_step(time.time(), now + 5, True)
        self.assertIsNone(win._infobar)
        tracker.next_break = now + 6
        win._wellbeing_step(time.time(), now + 10, True)
        self.assertIn(f"browsing for {win.break_interval_minutes} minutes", self.infobar_text())
        win._infobar.response(1)  # Snooze 10 min
        self.assertIsNone(win._infobar)
        self.assertGreater(tracker.next_break, time.monotonic() + win.BREAK_SNOOZE_SECONDS - 5)

    def test_bedtime_turns_pages_grey_also_with_dark_mode(self):
        win, tracker = self.wellbeing_on()
        filt = "getComputedStyle(document.documentElement).filter"
        wv = self.load("/thin", "thin")
        win.bedtime_enabled = True
        win.bedtime_start = time.strftime("%H:%M", time.localtime(time.time() - 3600))
        win.bedtime_end = time.strftime("%H:%M", time.localtime(time.time() + 3600))
        win._update_bedtime(time.time())
        self.assertTrue(spin(lambda: "grayscale" in js(wv, filt), 3), js(wv, filt))
        self.assertIn("bedtime", self.infobar_text())

        win.set_dark_mode(True)
        self.assertTrue(spin(lambda: "invert" in js(wv, filt) and "grayscale" in js(wv, filt), 3), js(wv, filt))
        win.set_dark_mode(False)
        self.assertTrue(spin(lambda: "grayscale" in js(wv, filt) and "invert" not in js(wv, filt), 3), js(wv, filt))

        before = len(win._tab_boxes())
        self.addCleanup(lambda: [win.close_tab(t) for t in win._tab_boxes()[before:]])
        win.create_new_tab(self.base + "/blank")
        new = win.get_active_webview()
        self.assertTrue(spin(lambda: not new.is_loading() and "grayscale" in js(new, filt), 5), "new tabs are grey too")

        win._infobar.response(1)  # Not tonight
        self.assertTrue(spin(lambda: js(new, filt) == "none", 3), js(new, filt))
        win._update_bedtime(time.time())
        self.assertFalse(win._bedtime_active, "stays off for the rest of the night")

    def test_settings_adds_and_removes_a_site_limit(self):
        win, tracker = self.wellbeing_on()
        dialog = win.build_settings_dialog("wellbeing")
        self.addCleanup(dialog.destroy)
        controls = dialog._arrow_controls
        controls["wellbeing_limit_site"].set_text("not a site")
        controls["wellbeing_limit_add"].clicked()
        self.assertEqual(tracker.limits, {})
        controls["wellbeing_limit_site"].set_text("https://www.Example.co.uk/page")
        controls["wellbeing_limit_minutes"].set_value(45)
        controls["wellbeing_limit_add"].clicked()
        self.assertEqual(tracker.limits, {"example.co.uk": 45})
        with open(bb.WELLBEING_FILE) as f:
            self.assertEqual(json.load(f)["limits"], {"example.co.uk": 45}, "saved to disk")

        def buttons(widget):
            if isinstance(widget, Gtk.Button):
                yield widget
            if isinstance(widget, Gtk.Container):
                for child in widget.get_children():
                    yield from buttons(child)
        remove = [b for b in buttons(controls["wellbeing_limits_box"]) if b.get_label() == "Remove"]
        self.assertEqual(len(remove), 1)
        remove[0].clicked()
        self.assertEqual(tracker.limits, {})

        controls["wellbeing_enabled"].set_active(False)
        self.assertFalse(win.wellbeing_enabled)

    # ---- tabs ----------------------------------------------------------
    def test_switching_tabs_shows_that_tabs_address_and_title(self):
        win = self.win
        win.create_new_tab(self.base + "/blank")
        win.create_new_tab(self.base + "/thin")
        tabs = [win.notebook.get_nth_page(i) for i in range(win.notebook.get_n_pages())]
        self.assertTrue(spin(lambda: all(not t._arrow_webview.is_loading() and t._arrow_webview.get_title()
                                         for t in tabs[-2:]), 10))
        try:
            for tab in tabs[-2:] + tabs[-2:]:
                win.notebook.set_current_page(win.notebook.page_num(tab))
                wv = tab._arrow_webview
                self.assertEqual(win.url_entry.get_text(), wv.get_uri(), "address bar shows the tab clicked")
                self.assertTrue(win.get_title().startswith(wv.get_title() + " - "), "window title too")
                self.assertEqual(win.get_title(), wv.get_title() + " - Arrow Browser", "no version number in the title bar")
        finally:
            for tab in tabs[-2:]:
                win.close_tab(tab)

    def test_link_opens_new_tab_quickly_with_gpu_off(self):
        # WebKitGTK 2.52 stalls a new tab opened by a page for 15 s under HardwareAccelerationPolicy.NEVER,
        # and the opener stops painting meanwhile.
        win = self.win
        saved = win.gpu_acceleration_enabled
        win.gpu_acceleration_enabled = False
        win._apply_hardware_acceleration_policy()
        before = win.notebook.get_n_pages()
        win.create_new_tab(self.base + "/blank")
        try:
            opener = win.get_active_webview()
            opener.load_uri(self.base + "/opener")
            self.assertTrue(spin(lambda: opener.get_title() == "opener" and not opener.is_loading(), 10))
            opener.run_javascript("document.getElementById('p').click()", None, None, None)
            self.assertTrue(spin(lambda: win.notebook.get_n_pages() == before + 2, 3), "no new tab")
            popup = win.notebook.get_nth_page(win.notebook.get_n_pages() - 1)._arrow_webview
            started = time.time()
            self.assertTrue(spin(lambda: popup.get_title() == "done", 10), "new tab never loaded")
            self.assertLess(time.time() - started, 5, "new tab stalled")
            answered = []
            for wv in (opener, popup):
                wv.run_javascript("1+1", None, lambda v, r, _d: answered.append(v), None)
            self.assertTrue(spin(lambda: len(answered) == 2, 3), "a tab stopped responding")
            if not bb._DRIVER_UNSTABLE:
                self.assertEqual(popup.get_settings().get_hardware_acceleration_policy(),
                                 WebKit2.HardwareAccelerationPolicy.ALWAYS)
                self.assertEqual(opener.get_settings().get_hardware_acceleration_policy(),
                                 WebKit2.HardwareAccelerationPolicy.NEVER, "only the new tab is lifted")
        finally:
            for i in reversed(range(before, win.notebook.get_n_pages())):
                win.close_tab(win.notebook.get_nth_page(i))
            win.gpu_acceleration_enabled = saved
            win._apply_hardware_acceleration_policy()

    def test_pin_reorder_close_reopen_and_session(self):
        win = self.win
        win.create_new_tab(self.base + "/blank")
        win.create_new_tab(self.base + "/done")
        spin(lambda: all(not win.notebook.get_nth_page(i)._arrow_webview.is_loading() for i in range(win.notebook.get_n_pages())))
        last = win.notebook.get_nth_page(win.notebook.get_n_pages() - 1)
        win.set_tab_pinned(last, True)
        self.assertEqual(win.notebook.page_num(last), 0, "pinned tab moves to the front")
        self.assertFalse(last._arrow_close_btn.get_visible())
        self.assertTrue(last._arrow_label.get_text().startswith("📌"))
        urls, pinned = win._collect_session()
        self.assertEqual(pinned, [0])
        win._run_session_save()
        with open(bb.SESSION_FILE) as f:
            self.assertEqual(json.load(f)["pinned"], [0])

        win.close_other_tabs(win.notebook.get_nth_page(1))
        self.assertEqual(win.notebook.get_n_pages(), 2, "close-others keeps the chosen tab and pinned tabs")
        self.assertTrue(win._closed_tabs)
        before = win.notebook.get_n_pages()
        win.reopen_closed_tab()
        self.assertEqual(win.notebook.get_n_pages(), before + 1)
        win.set_tab_pinned(last, False)
        self.assertTrue(last._arrow_close_btn.get_visible())

        ev = Gdk.EventButton()  # what the "button-press-event" signal really passes to handlers
        ev.type = Gdk.EventType.BUTTON_PRESS
        ev.button = 2
        count = win.notebook.get_n_pages()
        win._on_tab_header_click(win.get_active_tab_box(), ev)
        self.assertEqual(win.notebook.get_n_pages(), count - 1, "middle-click closes the tab")

    # ---- address bar ----------------------------------------------------
    def test_address_bar_follows_single_page_navigation(self):
        win = self.win
        wv = self.load("/spa")
        win.get_active_webview().grab_focus()
        js(wv, "go(1)")
        self.assertTrue(spin(lambda: win.url_entry.get_text().endswith("/spa/watch?v=1"), 5),
                        "address bar shows the page's new address: " + win.url_entry.get_text())

    def test_address_bar_keeps_what_you_type(self):
        win = self.win
        wv = self.load("/spa")
        win.url_entry.grab_focus()
        win.url_entry.set_text("half-typed")
        js(wv, "go(2)")
        spin(lambda: (wv.get_uri() or "").endswith("v=2"), 5)
        self.assertEqual(win.url_entry.get_text(), "half-typed")
        wv.grab_focus()

    def test_address_bar_keeps_what_you_type_when_the_page_finishes_loading(self):
        win = self.win
        wv = self.load("/blank")
        win.url_entry.grab_focus()
        win.url_entry.set_text("half-typed")
        finished = []
        handler = wv.connect("load-changed", lambda v, e: e == WebKit2.LoadEvent.FINISHED and finished.append(1))
        self.addCleanup(wv.disconnect, handler)
        wv.reload()
        self.assertTrue(spin(lambda: finished, 5))
        self.assertEqual(win.url_entry.get_text(), "half-typed")
        wv.grab_focus()

    def test_first_click_in_address_bar_selects_the_address(self):
        win = self.win
        self.load("/blank")
        win.get_active_webview().grab_focus()
        ev = Gdk.EventButton()
        ev.type = Gdk.EventType.BUTTON_PRESS
        ev.button = 1
        self.assertTrue(win.on_url_entry_button_press(win.url_entry, ev), "GTK doesn't move the cursor to the click")
        text = win.url_entry.get_text()
        self.assertTrue(text)
        self.assertEqual(win.url_entry.get_selection_bounds(), (0, len(text)), "typing replaces the whole address")
        win.get_active_webview().grab_focus()

    def test_enter_in_address_bar_hands_focus_to_the_page(self):
        win = self.win
        win.url_entry.grab_focus()
        win.url_entry.set_text(self.base + "/blank")
        win.on_url_activate(win.url_entry)
        spin(lambda: False, 0.2)
        self.assertFalse(win.url_entry.has_focus())

    # ---- HTTPS upgrade + tracking parameters ------------------------------
    def test_typed_address_loses_its_tracking_parameters(self):
        win = self.win
        before = win.stats["params"]
        win.url_entry.set_text(self.base + "/done?utm_source=mail&k=1")
        win.on_url_activate(win.url_entry)
        self.assertTrue(spin(lambda: "/done?k=1" in Handler.requests, 8), Handler.requests)
        self.assertNotIn("/done?utm_source=mail&k=1", Handler.requests, "the site never sees the tracking tag")
        self.assertEqual(win.stats["params"], before + 1)

    def test_tab_opened_by_a_link_loses_its_tracking_parameters(self):
        self.addCleanup(self.close_new_tabs, self.win._tab_boxes())
        opener = self.open_tab("/opener", "opener")._arrow_webview
        count = self.win.notebook.get_n_pages()
        js(opener, "document.getElementById('p').click()")
        self.assertTrue(spin(lambda: "/done?k=1" in Handler.requests, 8), Handler.requests)
        self.assertEqual(self.win.notebook.get_n_pages(), count + 1, "opened in a new tab")
        self.assertNotIn("/done?utm_source=mail&k=1", Handler.requests)

    def test_iframe_in_a_new_tab_is_never_loaded_as_the_page(self):
        self.addCleanup(self.close_new_tabs, self.win._tab_boxes())
        tab = self.open_tab("/framed", "framed")
        self.assertTrue(spin(lambda: Handler.hits.get("/thin", 0) > 0, 5))
        spin(lambda: False, 0.5)
        self.assertEqual(tab._arrow_webview.get_uri(), self.base + "/framed", "the tab still shows its own page")

    def test_http_is_really_upgraded_and_warns_when_https_fails(self):
        # 127.0.0.1 is never upgraded (local network); pretend it's a public site. The test server only
        # speaks plain HTTP, so the upgraded load must fail and show the HTTPS warning.
        self.addCleanup(self.close_new_tabs, self.win._tab_boxes())
        real = bb.is_local_network_host
        bb.is_local_network_host = lambda host: False
        self.addCleanup(setattr, bb, "is_local_network_host", real)
        before = self.win.stats["https"]
        wv = self.win.create_new_tab(self.base + "/blank")
        self.assertTrue((wv.get_uri() or "").startswith("https://"), wv.get_uri())
        self.assertTrue(spin(lambda: "Secure connection unavailable" in (js(wv, "document.body.innerText") or ""), 15))
        self.assertEqual(self.win.stats["https"], before + 1)
        self.assertNotIn("/blank", Handler.requests, "nothing was sent over plain HTTP")

    # ---- downloads ------------------------------------------------------
    def start_download(self, path):
        count = len(self.win.downloads_history)
        self.win.context.download_uri(self.base + path)
        self.assertTrue(spin(lambda: len(self.win.downloads_history) > count, 5), "download never started")
        return self.win.downloads_history[-1]

    def test_download_uses_the_servers_file_name(self):
        folder = tempfile.mkdtemp(dir=_HOME)
        self.win.download_dir = folder
        self.addCleanup(setattr, self.win, "download_dir", "")
        entry = self.start_download("/dl?id=7")
        self.assertTrue(spin(lambda: entry["status"] != "Downloading...", 10), entry)
        self.assertEqual(entry["status"], "Completed ✅")
        self.assertIn(entry["filename"], ("Report 2026.pdf", "Report_2026.pdf"))  # WebKit may swap spaces for _
        with open(os.path.join(folder, entry["filename"]), "rb") as f:
            self.assertEqual(f.read(), b"%PDF-1.4 test")
        second = self.start_download("/dl?id=7")
        self.assertTrue(spin(lambda: second["status"] != "Downloading...", 10))
        self.assertNotEqual(second["path"], entry["path"], "an existing file is never overwritten")

    def test_risky_download_is_confirmed_first(self):
        folder = tempfile.mkdtemp(dir=_HOME)
        self.win.download_dir = folder
        self.addCleanup(setattr, self.win, "download_dir", "")
        original = self.win._confirm_risky_download
        self.addCleanup(setattr, self.win, "_confirm_risky_download", original)
        asked = []
        self.win._confirm_risky_download = lambda name, source: asked.append(name) or False
        entry = self.start_download("/invoice.pdf.desktop")
        self.assertTrue(spin(lambda: entry["status"] != "Downloading...", 10), entry)
        self.assertEqual(entry["status"], "Cancelled")
        self.assertEqual(asked, ["invoice.pdf.desktop"])
        self.assertEqual(os.listdir(folder), [], "nothing saved when the user says no")
        self.win._confirm_risky_download = lambda name, source: True
        entry = self.start_download("/invoice.pdf.desktop")
        self.assertTrue(spin(lambda: entry["status"] != "Downloading...", 10), entry)
        self.assertEqual(entry["status"], "Completed ✅")

    def test_failed_download_stays_failed(self):
        self.win.download_dir = tempfile.mkdtemp(dir=_HOME)
        self.addCleanup(setattr, self.win, "download_dir", "")
        entry = self.start_download("/broken.zip")
        self.assertTrue(spin(lambda: entry["status"] != "Downloading...", 10), entry)
        spin(lambda: False, 0.5)
        self.assertEqual(entry["status"], "Failed ❌", "a cut-off download is not reported as completed")
        cancelled = {"filename": "x", "path": "", "status": "Downloading..."}
        self.win.on_download_failed(cancelled, "cancelled")
        self.win.on_download_finished(cancelled)  # WebKit emits "finished" after "failed"
        self.assertEqual(cancelled["status"], "Failed ❌")

    def slow_download(self, path):
        folder = tempfile.mkdtemp(dir=_HOME)
        self.win.download_dir = folder
        self.addCleanup(setattr, self.win, "download_dir", "")
        Handler.download_delay = 0.03
        self.addCleanup(setattr, Handler, "download_delay", 0.01)
        Handler.download_requests.clear()
        entry = self.start_download(path)
        self.assertTrue(spin(lambda: entry["received"] > 100_000, 10), entry)
        return entry, folder

    def test_download_pauses_and_resumes_where_it_stopped(self):
        wv = self.load("/blank", "blank")
        js(wv, "document.cookie = 'sid=abc123; path=/'")
        entry, folder = self.slow_download("/big.dat")
        self.assertTrue(entry["resumable"])
        self.assertTrue(self.win.pause_download(entry))
        self.assertEqual(entry["status"], "Paused")
        part = entry["path"] + bb.DOWNLOAD_PART_SUFFIX
        spin(lambda: False, 0.5)
        kept = os.path.getsize(part)
        self.assertGreater(kept, 100_000)
        self.assertLess(kept, len(BIG_FILE))
        self.assertEqual(sorted(os.listdir(folder)), ["big.dat.part"], "WebKit's own copy is gone; ours stays")
        spin(lambda: False, 0.5)
        self.assertEqual(entry["status"], "Paused", "a pause isn't reported as a failure")

        Handler.download_delay = 0.003
        self.assertTrue(self.win.resume_download(entry))
        self.assertTrue(spin(lambda: entry["status"] != "Downloading...", 15), entry)
        self.assertEqual(entry["status"], "Completed ✅", entry)
        with open(entry["path"], "rb") as f:
            self.assertTrue(f.read() == BIG_FILE, "the resumed file is exactly the original")
        self.assertFalse(os.path.exists(part))
        path, wanted, cookie = Handler.download_requests[-1]
        self.assertEqual(wanted, f"bytes={kept}-", "only the missing part was asked for")
        self.assertIn("sid=abc123", cookie or "", "the site's cookies go with the resumed request")

    def test_download_restarts_when_the_server_cant_resume(self):
        entry, folder = self.slow_download("/norange.dat")
        self.assertTrue(self.win.pause_download(entry))
        Handler.download_delay = 0.003
        self.assertTrue(self.win.resume_download(entry))
        self.assertTrue(spin(lambda: entry["status"] != "Downloading...", 15), entry)
        self.assertEqual(entry["status"], "Completed ✅", entry)
        self.assertIn("started again", entry["note"])
        with open(entry["path"], "rb") as f:
            self.assertTrue(f.read() == BIG_FILE)
        self.assertEqual(os.listdir(folder), ["norange.dat"])

    def test_paused_download_can_be_cancelled(self):
        entry, folder = self.slow_download("/big.dat")
        self.assertTrue(self.win.pause_download(entry))
        self.assertTrue(self.win.cancel_download(entry))
        self.assertEqual(entry["status"], "Cancelled")
        spin(lambda: False, 0.3)
        self.assertEqual(os.listdir(folder), [], "nothing left behind")
        self.assertFalse(self.win.resume_download(entry))

    def test_cut_off_download_is_kept_aside_for_resume(self):
        self.win.download_dir = folder = tempfile.mkdtemp(dir=_HOME)
        self.addCleanup(setattr, self.win, "download_dir", "")
        entry = self.start_download("/broken.zip")
        self.assertTrue(spin(lambda: entry["status"] != "Downloading...", 10), entry)
        self.assertEqual(entry["status"], "Failed ❌")
        self.assertEqual(os.listdir(folder), ["broken.zip.part"], "the cut-off file doesn't pass for the whole one")

    def test_downloads_window_is_live(self):
        entry, folder = self.slow_download("/big.dat")
        self.addCleanup(lambda: self.win.cancel_download(entry))
        dialog = self.win.on_downloads_clicked(None)
        try:
            self.assertFalse(dialog.get_modal(), "browsing goes on while it's open")
            self.assertIs(self.win.on_downloads_clicked(None), dialog, "opening it again brings it forward")

            def texts():
                found = []
                def walk(w):
                    if isinstance(w, (Gtk.Label, Gtk.Button)) and not isinstance(w, Gtk.Container) or isinstance(w, Gtk.Label):
                        found.append(w.get_text())
                    elif isinstance(w, Gtk.Button):
                        found.append(w.get_label())
                    for c in (w.get_children() if isinstance(w, Gtk.Container) else ()):
                        walk(c)
                walk(dialog)
                return found
            self.assertIn("⏸ Pause", texts())
            first = entry["received"]
            self.assertTrue(spin(lambda: any(" of 1.0 MB" in t and "/s" in t for t in texts()), 5), texts())
            self.assertGreater(entry["received"], first)
            self.win.pause_download(entry)
            self.assertTrue(spin(lambda: "▶ Resume" in texts(), 2), texts())
        finally:
            dialog.destroy()
        self.assertIsNone(self.win._downloads_window)

    # ---- links from other apps ---------------------------------------------
    def test_links_passed_at_startup_open_as_tabs(self):
        win = bb.ArrowBrowserWindow(private=True, startup_urls=[self.base + "/done", self.base + "/thin"])
        try:
            uris = [tb._arrow_webview.get_uri() for tb in win._tab_boxes()]
            self.assertEqual(uris, [self.base + "/done", self.base + "/thin"], "no extra homepage tab")
            self.assertEqual(win.get_active_webview().get_uri(), self.base + "/thin")
        finally:
            win.destroy()

    # ---- per-site policy ------------------------------------------------
    def test_per_site_javascript(self):
        wv = self.load("/js", wait_title="js-ran")
        self.assertEqual(wv.get_title(), "js-ran")
        bb.set_site_value(self.win.site_settings, "127.0.0.1", "javascript", False)
        wv = self.load("/js", wait_title="js-off")
        self.assertEqual(wv.get_title(), "js-off", "JavaScript is off for this site")
        self.win.site_settings.clear()
        wv = self.load("/js", wait_title="js-ran")
        self.assertEqual(wv.get_title(), "js-ran", "and back on again")

    def test_canvas_and_audio_reads_are_farbled_consistently(self):
        wv = self.load("/blank")
        result = js(wv, """(function(){
          function draw(){ var c=document.createElement('canvas'); c.width=200; c.height=50;
            var x=c.getContext('2d'); x.fillStyle='#336699'; x.fillRect(0,0,200,50); return c; }
          var a=draw(), b=draw(), d=a.getContext('2d').getImageData(0,0,200,50).data, changed=0;
          for (var i=0;i<d.length;i+=4) if (d[i]!==0x33||d[i+1]!==0x66||d[i+2]!==0x99) changed++;
          var own=a.getContext('2d'), tiny=own.getImageData(0,0,4,4).data, exact=true;
          for (var i=0;i<tiny.length;i+=4) exact = exact && tiny[i]===0x33 && tiny[i+2]===0x99;
          var ctx=new OfflineAudioContext(1,1000,44100), buf=ctx.createBuffer(1,1000,44100);
          buf.copyToChannel(new Float32Array(1000).fill(0.5),0);
          var s1=Array.from(buf.getChannelData(0)), s2=Array.from(buf.getChannelData(0));
          return JSON.stringify({changed:changed, sameURL:a.toDataURL()===b.toDataURL(),
            tinyExact:exact, audioChanged:s1.filter(v=>v!==0.5).length, audioStable:JSON.stringify(s1)===JSON.stringify(s2)});
        })()""")
        self.assertTrue(result.startswith("{"), result)
        r = json.loads(result)
        self.assertTrue(1 <= r["changed"] <= 64, r)
        self.assertTrue(r["sameURL"], "the same drawing gives the same result all session")
        self.assertTrue(r["tinyExact"], "colour-picker sized reads stay exact")
        self.assertTrue(r["audioChanged"] > 0 and r["audioStable"], r)
        # the page's own canvas isn't changed by toDataURL
        self.assertEqual(js(wv, """(function(){var c=document.createElement('canvas');c.width=20;c.height=20;
          var x=c.getContext('2d');x.fillStyle='#ff0000';x.fillRect(0,0,20,20);c.toDataURL();
          x.globalCompositeOperation='copy';var d=x.getImageData(0,0,2,2).data;return d[0]+','+d[1];})()"""), "255,0")

    def test_farbling_exemptions_match_whole_domains(self):
        wv = self.load("/blank")
        cases = {
            ("challenges.cloudflare.com", "/cdn-cgi/challenge-platform/h/b/turnstile/if/ov2/av0/rcv0/0/x"): True,
            ("www.google.com", "/recaptcha/api2/anchor"): True,
            ("www.google.com", "/recaptcha/enterprise/anchor"): True,
            ("www.recaptcha.net", "/recaptcha/api2/bframe"): True,
            ("newassets.hcaptcha.com", "/captcha/v1/abc/static/hcaptcha.html"): True,
            ("client-api.arkoselabs.com", "/fc/gc/"): True,
            ("WWW.YouTube.com", "/watch"): True,
            ("www.google.com", "/search"): False,      # the rest of Google stays farbled
            ("cloudflare.com", "/"): False,
            ("notyoutube.com", "/"): False,            # look-alike names don't get the exemption
            ("hcaptcha.com.evil.example", "/"): False,
            ("example.com", "/recaptcha/"): False,
        }
        got = json.loads(js(wv, "JSON.stringify(%s.map(([h, p]) => %s(h, p)))"
                            % (json.dumps([list(k) for k in cases]), bb.FARBLING_EXEMPT_JS)))
        self.assertEqual(dict(zip(cases, got)), cases)

    def test_per_site_ad_blocking(self):
        self.load("/third")
        spin(lambda: False, 1.0)
        self.assertEqual(Handler.hits.get("/pixel", 0), 0, "tracker-list rule blocks the third-party load")
        bb.set_site_value(self.win.site_settings, "127.0.0.1", "adblock", False)
        self.load("/third")
        self.assertTrue(spin(lambda: Handler.hits.get("/pixel", 0) > 0, 5), "ad blocking off for this site lets it load")

    def test_path_rules_block_subresources_natively(self):
        self.load("/pathrules")
        spin(lambda: Handler.hits.get("/fine/ok.png", 0) > 0 and Handler.hits.get("/roads/ok.png", 0) > 0, 5)
        spin(lambda: False, 1.0)
        for blocked in ("/pagead/p.png", "/sub/ads/p.png", "/telemetry.png"):
            self.assertEqual(Handler.hits.get(blocked, 0), 0, f"{blocked} is blocked by the native path rules")
        for allowed in ("/roads/ok.png", "/adsense.png", "/fine/ok.png"):
            self.assertGreater(Handler.hits.get(allowed, 0), 0, f"{allowed} must not be caught by '/ads/' or '/adserver/'")
        self.assertGreater(Handler.hits.get("/pagead/stream.m3u8", 0), 0, "streaming manifests are exempt")
        # navigating to a page whose address contains /ads/ is never blocked
        self.assertEqual(self.load("/ads/landing", wait_title="landing").get_title(), "landing")
        # and the per-site ad-block switch turns the path rules off too
        bb.set_site_value(self.win.site_settings, "127.0.0.1", "adblock", False)
        self.addCleanup(self.win.site_settings.clear)
        self.load("/pathrules")
        self.assertTrue(spin(lambda: Handler.hits.get("/pagead/p.png", 0) > 0, 5), "ad blocking off lets /pagead/ load")

    def measure(self, tabs=None):
        box = {}
        self.win.measure_tab_memory(lambda r: box.setdefault("r", r), tabs)
        self.assertTrue(spin(lambda: "r" in box, 30), "memory measurement never finished")
        return box["r"]

    def test_tab_memory_finds_the_heavy_tab(self):
        before = len(self.win._tab_boxes())
        self.win.create_new_tab(self.base + "/blank")
        spin(lambda: False, 1.5)
        self.win.create_new_tab(self.base + "/mem-heavy")
        spin(lambda: False, 2.5)
        self.addCleanup(lambda: [self.win.close_tab(t) for t in self.win._tab_boxes()[before:]])
        results = self.measure()
        new = {t._arrow_label.get_text(): i for t, i in results.items() if t in self.win._tab_boxes()[before:]}
        self.assertEqual(set(new), {"blank", "mem-heavy"})
        for info in new.values():
            self.assertEqual(info["state"], "ok")
        self.assertNotEqual(new["blank"]["pid"], new["mem-heavy"]["pid"], "each tab has its own renderer")
        self.assertGreater(new["mem-heavy"]["mb"], new["blank"]["mb"] + 60, "the tab holding ~160 MB is the heavy one")
        # a repeat measurement reuses the match instead of probing again
        again = self.measure()
        self.assertEqual({t: i["pid"] for t, i in results.items() if t in again},
                         {t: i["pid"] for t, i in again.items() if t in results})

    def test_tab_memory_reports_suspended_tabs_and_dialog_opens(self):
        self.win.create_new_tab(self.base + "/blank")
        spin(lambda: False, 1.0)
        victim = self.win._tab_boxes()[-1]
        self.win.create_new_tab(self.base + "/blank")  # becomes the active tab
        spin(lambda: False, 1.0)
        self.addCleanup(lambda: [self.win.close_tab(t) for t in (victim, self.win._tab_boxes()[-1]) if t.get_parent()])
        self.win._suspend_tab(victim)
        spin(lambda: False, 1.0)
        self.assertEqual(self.measure([victim])[victim]["state"], "suspended")
        seen = {}

        def close_dialog():
            for w in Gtk.Window.list_toplevels():
                if isinstance(w, Gtk.Dialog) and w.get_title() == "Tab Memory":
                    seen["title"] = w.get_title()
                    w.response(Gtk.ResponseType.CLOSE)
            return False

        GLib.timeout_add(2500, close_dialog)
        self.win.open_tab_memory()  # modal: returns once close_dialog() has dismissed it
        self.assertEqual(seen.get("title"), "Tab Memory")

    # ---- sleeping tabs ---------------------------------------------------
    def open_tab(self, path, title):
        self.win.create_new_tab(self.base + path)
        tab = self.win._tab_boxes()[-1]
        self.assertTrue(spin(lambda: tab._arrow_webview.get_title() == title and not tab._arrow_webview.is_loading(), 10))
        return tab

    def close_new_tabs(self, before):
        for tab in self.win._tab_boxes():
            if tab not in before:
                self.win.close_tab(tab)

    def asleep(self, tab):
        return id(tab) in self.win._suspended_session_states

    def test_unresponsive_page_does_not_stop_memory_relief(self):
        win = self.win
        win.create_new_tab(self.base + "/blank")
        tab = win.notebook.get_nth_page(win.notebook.get_n_pages() - 1)
        win.create_new_tab(self.base + "/thin")
        front = win.notebook.get_nth_page(win.notebook.get_n_pages() - 1)
        try:
            self.assertTrue(spin(lambda: not tab._arrow_webview.is_loading(), 10))
            # A renderer stuck in a script never answers the typed-text check.
            tab._arrow_webview.run_javascript_in_world = lambda *args: None
            win.TYPED_TEXT_CHECK_TIMEOUT_MS = 200
            results = []
            win._sleep_unless_typed(tab, results.append)
            self.assertTrue(spin(lambda: results, 3), "never decided")
            self.assertEqual(results, [False], "a page that doesn't answer stays awake")
            self.assertFalse(self.asleep(tab))
            spin(lambda: False, 0.3)
            self.assertEqual(results, [False], "decided once")

            win._relieving_memory_pressure = False
            win._relieve_memory_pressure()
            self.assertTrue(spin(lambda: not win._relieving_memory_pressure, 3), "memory relief stays locked out")
        finally:
            del win.TYPED_TEXT_CHECK_TIMEOUT_MS
            del tab._arrow_webview.run_javascript_in_world
            win.close_tab(front)
            win.close_tab(tab)

    def test_sleeping_tab_ends_its_renderer_and_comes_back(self):
        self.addCleanup(self.close_new_tabs, self.win._tab_boxes())
        tab = self.open_tab("/article", "Test Article")
        wv = tab._arrow_webview
        wv.load_uri(self.base + "/done")
        self.assertTrue(spin(lambda: wv.get_title() == "done", 10))
        self.open_tab("/blank", "blank")
        pid = self.measure([tab])[tab]["pid"]
        self.assertIsNotNone(pid)
        self.assertTrue(self.win._suspend_tab(tab))
        self.assertTrue(spin(lambda: pid not in bb.web_process_pids(), 5), "the sleeping tab's renderer is gone")
        self.assertTrue(tab._arrow_label.get_text().startswith("💤"))
        self.assertIn(self.base + "/done", self.win._collect_session()[0], "still saved in the session")
        self.win.notebook.set_current_page(self.win.notebook.page_num(tab))
        self.assertTrue(spin(lambda: wv.get_title() == "done" and not wv.is_loading(), 10), "reloads where it was")
        self.assertTrue(wv.can_go_back(), "with its history")
        self.assertFalse(self.asleep(tab))

    def test_restored_session_loads_only_the_tab_you_open(self):
        self.addCleanup(self.close_new_tabs, self.win._tab_boxes())
        before = len(self.win._tab_boxes())
        urls = [self.base + "/r1", self.base + "/r2", self.base + "/blank"]
        self.win.restore_tabs(urls)
        r1, r2, last = self.win._tab_boxes()[before:]
        self.assertIs(self.win.get_active_tab_box(), last)
        self.assertTrue(spin(lambda: last._arrow_webview.get_title() == "blank", 10), "the tab you land on loads")
        spin(lambda: False, 1.0)
        self.assertEqual((Handler.hits.get("/r1", 0), Handler.hits.get("/r2", 0)), (0, 0), "the others wait")
        self.assertEqual(r1._arrow_label.get_text(), "💤 127.0.0.1")
        self.assertEqual(self.win._collect_session()[0][-3:], urls, "all of them stay in the session")
        self.win.notebook.set_current_page(self.win.notebook.page_num(r1))
        self.assertTrue(spin(lambda: Handler.hits.get("/r1", 0) > 0, 5), "opening a tab loads it")
        self.assertEqual(Handler.hits.get("/r2", 0), 0)

    def test_automatic_sleep_keeps_pinned_and_typed_in_tabs(self):
        self.addCleanup(self.close_new_tabs, self.win._tab_boxes())
        plain = self.open_tab("/blank", "blank")
        pinned = self.open_tab("/thin", "thin")
        self.win.set_tab_pinned(pinned, True)
        typed = self.open_tab("/form", "form")
        js(typed._arrow_webview, "const t=document.getElementById('t'); t.value='a reply in progress';"
                                  "t.dispatchEvent(new Event('input', {bubbles: true})); 1")
        self.open_tab("/blank", "blank")
        for tab in (plain, pinned, typed):
            self.win._tab_last_active[id(tab)] = time.monotonic() - 3600
        self.win._check_tab_suspension()
        self.assertTrue(spin(lambda: self.asleep(plain), 5), "an idle tab goes to sleep")
        spin(lambda: False, 1.0)
        self.assertFalse(self.asleep(pinned), "pinned tabs stay awake")
        self.assertFalse(self.asleep(typed), "so do tabs holding typed text")
        js(typed._arrow_webview, "document.getElementById('t').value=''; 1")  # the reply was sent
        self.win._check_tab_suspension()
        self.assertTrue(spin(lambda: self.asleep(typed), 5))

    def test_low_memory_puts_the_oldest_background_tab_to_sleep(self):
        self.addCleanup(self.close_new_tabs, self.win._tab_boxes())
        oldest = self.open_tab("/blank", "blank")
        older = self.open_tab("/thin", "thin")
        self.open_tab("/blank", "blank")
        now = time.monotonic()
        self.win._tab_last_active[id(oldest)] = now - 100000
        self.win._tab_last_active[id(older)] = now - 50000
        real = bb.system_memory_mb
        self.addCleanup(setattr, bb, "system_memory_mb", real)
        bb.system_memory_mb = lambda: (4000.0, 8000.0)
        self.win._check_memory_pressure()
        spin(lambda: False, 1.0)
        self.assertFalse(self.asleep(oldest), "nothing sleeps while memory is fine")
        bb.system_memory_mb = lambda: (300.0, 8000.0)
        self.win._check_memory_pressure()
        self.assertTrue(spin(lambda: self.asleep(oldest), 5), "least recently used goes first")
        self.assertFalse(self.asleep(older), "one tab per check")
        self.win._check_memory_pressure()
        self.assertTrue(spin(lambda: self.asleep(older), 5))

    def test_popup_sleeps_without_killing_the_opener_it_shares_a_renderer_with(self):
        self.addCleanup(self.close_new_tabs, self.win._tab_boxes())
        opener_tab = self.open_tab("/done", "done")
        opener = opener_tab._arrow_webview
        popup = self.win.on_create_webview(opener, None)
        popup_tab = self.win._tab_boxes()[-1]
        popup.load_uri(self.base + "/thin")
        self.assertTrue(spin(lambda: popup.get_title() == "thin", 10))
        self.win.notebook.set_current_page(self.win.notebook.page_num(opener_tab))
        Handler.hits.clear()
        self.assertTrue(self.win._suspend_tab(popup_tab))
        spin(lambda: False, 1.5)
        self.assertEqual(js(opener, "document.title"), "done", "the opener's renderer is still running")
        self.assertEqual(Handler.hits.get("/done", 0), 0, "and it was not reloaded")
        self.win.close_tab(popup_tab)
        self.assertEqual(opener._arrow_related, {opener})

    def test_tab_on_screen_reloads_if_its_renderer_is_ended(self):
        wv = self.load("/done", wait_title="done")
        Handler.hits.clear()
        wv.terminate_web_process()  # as if it shared a process with a tab put to sleep
        self.assertTrue(spin(lambda: Handler.hits.get("/done", 0) > 0 and wv.get_title() == "done", 10))
        self.assertFalse(self.asleep(self.win.get_active_tab_box()))

    def test_identify_as_chrome_per_site(self):
        wv = self.load("/blank")
        self.assertNotIn("Chrome/", js(wv, "navigator.userAgent"), "default: the engine's own (Safari) user agent")
        bb.set_site_value(self.win.site_settings, "127.0.0.1", "chrome_ua", True)
        self.addCleanup(self.win.site_settings.clear)
        wv = self.load("/blank")
        self.assertIn(f"Chrome/{bb.CHROME_UA_MAJOR}", js(wv, "navigator.userAgent"))
        self.assertIn("identifies as Chrome", self.win._describe_site_entry(self.win.site_settings["127.0.0.1"]))
        # combined with JavaScript off: both apply
        bb.set_site_value(self.win.site_settings, "127.0.0.1", "javascript", False)
        wv = self.load("/js", wait_title="js-off")
        self.assertEqual(wv.get_title(), "js-off")
        self.assertIn("Chrome/", wv.get_settings().get_user_agent())
        self.win.site_settings.clear()
        wv = self.load("/js", wait_title="js-ran")
        self.assertNotIn("Chrome/", js(wv, "navigator.userAgent"), "switched back off")

    def test_zoom_is_remembered_per_site(self):
        wv = self.load("/blank")
        self.win.adjust_zoom(0.3)
        self.assertAlmostEqual(self.win.site_settings["127.0.0.1"]["zoom"], 1.3, places=2)
        wv.set_zoom_level(1.0)
        wv = self.load("/done")
        self.assertTrue(spin(lambda: abs(wv.get_zoom_level() - 1.3) < 0.01, 5), "saved zoom re-applied on load")
        self.win.adjust_zoom(reset=True)
        self.assertNotIn("zoom", self.win.site_settings.get("127.0.0.1", {}))

    # ---- permissions ----------------------------------------------------
    def test_remembered_permissions_skip_the_prompt(self):
        wv = self.load("/blank")
        calls = []

        class Req:
            def allow(self): calls.append("allow")
            def deny(self): calls.append("deny")

        original = self.win._describe_permission
        self.win._describe_permission = lambda r: ("media", "use your camera")
        try:
            bb.set_site_value(self.win.site_settings, "127.0.0.1", "permissions", "allow", sub="media")
            self.assertTrue(self.win.on_permission_request(wv, Req()))
            bb.set_site_value(self.win.site_settings, "127.0.0.1", "permissions", "deny", sub="media")
            self.win.on_permission_request(wv, Req())
        finally:
            self.win._describe_permission = original
            self.win.site_settings.clear()
        self.assertEqual(calls, ["allow", "deny"])

    def test_permissions_nobody_can_judge_are_refused_without_asking(self):
        wv = self.load("/blank")
        calls = []

        class Unknown:  # e.g. a WebXR session or a request type added in a later WebKit
            def allow(self): calls.append("allow")
            def deny(self): calls.append("deny")

        self.assertEqual(self.win._describe_permission(Unknown()), (None, None))
        self.assertTrue(self.win.on_permission_request(wv, Unknown()))  # a prompt here would block the test
        self.assertEqual(calls, ["deny"])

    # ---- update notice -------------------------------------------------
    def test_update_notice_only_appears_after_a_check(self):
        win = self.win
        win.update_dialog_box.hide()
        win.show_all()  # what starting the browser does: it used to reveal the notice, unchecked
        self.assertFalse(win.update_dialog_box.get_visible(), "claimed 'latest version' without checking")
        win.show_latest_version_notification()
        self.assertTrue(win.update_dialog_box.get_visible())
        self.assertTrue(win.update_dialog_label.get_visible())
        self.assertIn("latest version", win.update_dialog_label.get_text())
        self.assertFalse(win.btn_restart_update.get_visible())
        win.show_update_notification_dialog("99.0.0", installed=True)
        self.assertTrue(win.btn_restart_update.get_visible(), "restart button shown for a downloaded update")
        win.update_dialog_box.hide()

    # ---- sandbox, fullscreen ----------------------------------------------
    def test_web_pages_run_in_the_sandbox(self):
        self.assertTrue(bb.webkit_sandbox_usable(), "bubblewrap can't start a sandbox on this machine")
        self.assertTrue(self.win.context.get_sandbox_enabled())

    def test_fullscreen_names_the_site_and_how_to_leave(self):
        win = self.win
        wv = self.load("/blank")
        original = win._apply_hardware_acceleration_policy
        win._apply_hardware_acceleration_policy = lambda: None  # a GPU policy flip isn't what's tested here
        try:
            win.on_webview_enter_fullscreen(wv)
            self.assertTrue(win.fullscreen_notice.get_visible())
            self.assertIn("127.0.0.1", win.fullscreen_notice.get_text())
            self.assertIn("Esc", win.fullscreen_notice.get_text())
            win.on_webview_leave_fullscreen(wv)
            self.assertFalse(win.fullscreen_notice.get_visible())
            self.assertIsNone(win._fullscreen_notice_source)
        finally:
            win._apply_hardware_acceleration_policy = original
            if win._fullscreen:
                win.on_webview_leave_fullscreen(wv)

    # ---- https warning --------------------------------------------------
    def test_https_warning_and_one_time_token(self):
        wv = self.load("/blank")
        self.win._show_https_warning(wv, "https://plain-only.example/page", "connection refused")
        self.assertTrue(spin(lambda: "Secure connection unavailable" in (js(wv, "document.body.innerText") or ""), 8))
        href = js(wv, "document.querySelector('a.alt').href")
        self.assertTrue(href.startswith("arrow://allow-http?t="))

        class SchemeReq:
            def __init__(self, uri): self.uri, self.body = uri, None
            def get_uri(self): return self.uri
            def finish(self, stream, length, ctype): self.body = stream.read_bytes(length, None).get_data().decode()

        forged = SchemeReq("arrow://allow-http?t=guess")
        self.win._on_arrow_scheme(forged, None)
        self.assertNotIn("plain-only.example", self.win._http_allowed_hosts, "a guessed token does nothing")
        real = SchemeReq(href)
        self.win._on_arrow_scheme(real, None)
        self.assertIn("plain-only.example", self.win._http_allowed_hosts)
        self.assertIn("http://plain-only.example/page", real.body)
        again = SchemeReq(href)
        self.win._on_arrow_scheme(again, None)
        self.assertNotIn("refresh", again.body, "the token is single-use")
        self.win._http_allowed_hosts.discard("plain-only.example")

    # ---- passwords ------------------------------------------------------
    def test_password_save_then_fill(self):
        wv = self.load("/login")
        js(wv, "document.getElementById('u').value='alice';document.getElementById('p').value='hunter2';"
               "document.getElementById('go').click();'x'")
        self.assertTrue(spin(lambda: self.win._infobar is not None, 6), "save prompt appears after submit")
        self.win._infobar.response(1)  # "Save"
        self.assertEqual(self.win.secrets.items, {("127.0.0.1", "alice"): "hunter2"})

        wv = self.load("/login")
        self.assertTrue(spin(lambda: self.win._infobar is not None, 6), "fill offer appears on a login page")
        self.win._infobar.response(1)  # "Fill"
        self.assertTrue(spin(lambda: js(wv, "document.getElementById('p').value") == "hunter2", 5))
        self.assertEqual(js(wv, "document.getElementById('u').value"), "alice")
        self.win.secrets.items.clear()

    def test_fill_offer_never_fills_another_site(self):
        win = self.win
        win.secrets.items[("127.0.0.1", "alice")] = "hunter2"
        self.addCleanup(win.secrets.items.clear)
        wv = self.load("/login")
        self.assertTrue(spin(lambda: win._infobar is not None, 6), "fill offer appears on a login page")
        bar = win._infobar
        other = f"http://localhost:{self.port}/login"  # another site, same login form
        wv.load_uri(other)
        self.assertTrue(spin(lambda: not wv.is_loading() and wv.get_uri() == other, 10))
        self.assertIsNone(win._infobar, "the fill offer closes when the tab goes to another page")
        bar.response(1)  # "Fill" clicked anyway (e.g. the click landed just as the page changed)
        spin(lambda: False, 0.5)
        self.assertEqual(js(wv, "document.getElementById('p').value"), "", "password went to another site")

    def test_password_prompts_belong_to_the_tab_that_sent_them(self):
        # The visible tab is on another site ("localhost") than the background login page ("127.0.0.1").
        win = self.win
        win.secrets.items[("127.0.0.1", "alice")] = "hunter2"
        before = win.notebook.get_n_pages()
        try:
            win.create_new_tab(self.base + "/login")
            login_tab = win.notebook.get_nth_page(win.notebook.get_n_pages() - 1)
            login = login_tab._arrow_webview
            win.create_new_tab(f"http://localhost:{self.port}/blank")
            front = win.get_active_webview()
            self.assertTrue(spin(lambda: not login.is_loading() and not front.is_loading()
                                 and front.get_title() == "blank", 10))
            spin(lambda: False, 1.0)  # the form message comes 300 ms after load
            self.assertIsNone(win._infobar, "no fill offer over another site's tab")

            win.notebook.set_current_page(win.notebook.page_num(login_tab))
            self.assertTrue(spin(lambda: win._infobar is not None, 3), "offered once the login tab is shown")
            win._infobar.response(1)  # "Fill"
            self.assertTrue(spin(lambda: js(login, "document.getElementById('p').value") == "hunter2", 5))

            win.secrets.items.clear()
            win._fill_offered.clear()
            win.notebook.set_current_page(win.notebook.get_n_pages() - 1)  # back to localhost
            js(login, "document.getElementById('u').value='carol';document.getElementById('p').value='s3cret';"
                      "document.getElementById('go').click();'x'")
            self.assertTrue(spin(lambda: win._infobar is not None, 6), "save prompt for a background submit")
            win._infobar.response(1)  # "Save"
            self.assertEqual(win.secrets.items, {("127.0.0.1", "carol"): "s3cret"}, "saved for the tab's own site")
        finally:
            win.secrets.items.clear()
            win._clear_infobar()
            for i in reversed(range(before, win.notebook.get_n_pages())):
                win.close_tab(win.notebook.get_nth_page(i))

    def test_password_prompt_respects_never_and_private(self):
        self.win.site_settings["127.0.0.1"] = {"passwords": False}
        wv = self.load("/login")
        js(wv, "document.getElementById('u').value='bob';document.getElementById('p').value='pw';document.getElementById('go').click();'x'")
        spin(lambda: False, 1.5)
        self.assertIsNone(self.win._infobar, "'never for this site' suppresses the prompt")

    # ---- stats / report / import ---------------------------------------
    def test_privacy_report_and_stats(self):
        before = self.win.stats["params"]
        self.win._count_event("params")
        self.assertEqual(self.win.stats["params"], before + 1)
        html = self.win.build_privacy_report_html()
        self.assertIn("Privacy Report", html)
        self.assertIn("Tracking parameters removed", html)
        self.assertNotIn("Trackers &amp; ads blocked", html, "native blocks are not reported to us, so no fake zero")
        self.win._run_session_save()
        self.assertGreaterEqual(bb.load_privacy_stats()["params"], before + 1, "stats are persisted")

    def test_import_merges_into_live_lists(self):
        marks = [{"url": "https://imp.example/", "title": "Imp", "added": 1}]
        hist = [{"url": "https://imp.example/h", "title": "H", "visits": 2, "total_seconds": 0.0, "last_visited": 5}]
        added_b, added_h = self.win._apply_import(marks, hist)
        self.assertEqual((added_b, added_h), (1, 1))
        self.assertEqual(self.win._apply_import(marks, hist), (0, 0), "importing twice adds nothing")
        with open(bb.BOOKMARKS_FILE) as f:
            self.assertIn("https://imp.example/", [b["url"] for b in json.load(f)])
        self.assertIn("https://imp.example/h", [row[0] for row in self.win.url_completion_store])

    def test_clear_on_exit_removes_cookies(self):
        wv = self.load("/blank", "blank")
        uri = self.base + "/blank"
        wv.run_javascript("document.cookie = 'sid=signed-in; max-age=3600'", None, None, None)
        cookie_mgr = self.win.context.get_cookie_manager()

        def cookie_names():
            out = []
            cookie_mgr.get_cookies(uri, None, lambda m, r, _d: out.append(
                [c.get_name() for c in m.get_cookies_finish(r)]), None)
            spin(lambda: out, 5)
            return out[0] if out else None

        self.assertTrue(spin(lambda: "sid" in (cookie_names() or []), 5), "test cookie was never set")
        bb.mark_clear_on_exit_pending()
        done = []
        self.win._clear_website_data(lambda: done.append(True))
        self.assertTrue(spin(lambda: done, 10), "clear never finished")
        self.assertEqual(cookie_names(), [], "cookies survive the exit clear")
        self.assertFalse(os.path.exists(bb.CLEAR_ON_EXIT_MARKER), "marker kept after a successful clear")
        spin(lambda: False, 0.3)
        self.assertEqual(done, [True], "on_done ran more than once")

    def test_settings_dialog_pages_and_switches(self):
        dialog = self.win.build_settings_dialog("privacy")
        try:
            stack = dialog._arrow_stack
            self.assertEqual([stack.child_get_property(c, "name") for c in stack.get_children()],
                             ["general", "privacy", "data", "performance", "wellbeing", "about"])
            self.assertEqual(stack.get_visible_child_name(), "privacy")
            controls = dialog._arrow_controls
            for key, sw in controls.items():
                if isinstance(sw, Gtk.Switch):
                    self.assertEqual(sw.get_active(), bool(getattr(self.win, key)), key)

            sw = controls["clear_history_on_exit"]
            sw.set_active(not sw.get_active())
            self.assertEqual(self.win.clear_history_on_exit, sw.get_active())
            with open(bb.CONFIG_FILE) as f:
                self.assertEqual(json.load(f)["clear_history_on_exit"], sw.get_active(), "saved to disk")
            self.assertEqual(os.path.exists(bb.CLEAR_ON_EXIT_MARKER), sw.get_active(), "crash marker follows the switch")
            sw.set_active(not sw.get_active())
            self.assertEqual(os.path.exists(bb.CLEAR_ON_EXIT_MARKER), sw.get_active())

            dark = controls["dark_mode_active"]
            dark.set_active(not dark.get_active())
            self.assertEqual(self.win.dark_mode_active, dark.get_active())
            dark.set_active(not dark.get_active())
            self.assertEqual(self.win.dark_mode_active, dark.get_active())
        finally:
            dialog.destroy()

    def test_lock_colour_follows_the_connection(self):
        win, style = self.win, self.win.url_entry.get_style_context()
        cert = Gio.TlsCertificate.new_from_file(self.cert_file)

        class Page:
            def __init__(self, tls, mixed=False, committed=True):
                self.tls, self._arrow_mixed_content, self._arrow_committed = tls, mixed, committed

            def get_tls_info(self):
                return self.tls

        verified, bad = (True, cert, Gio.TlsCertificateFlags(0)), (True, cert, Gio.TlsCertificateFlags.UNKNOWN_CA)
        for uri, page, expected in (
                ("https://x.example/", Page(verified), "url-secure"),
                ("https://x.example/", Page(verified, mixed=True), "url-mixed"),
                ("https://x.example/", Page(bad), "url-insecure"),
                ("https://x.example/", Page(verified, committed=False), None),  # still connecting
                ("https://x.example/", None, None),  # the address alone proves nothing
                ("http://x.example/", Page((False, None, 0)), "url-insecure"),
                ("about:blank", Page((False, None, 0)), None)):
            win.update_security_icon(uri, page)
            shown = [c for c in ("url-secure", "url-mixed", "url-insecure") if style.has_class(c)]
            self.assertEqual(shown, [expected] if expected else [], (uri, page and page.__dict__))

    def test_invalid_certificate_is_blocked_without_a_bypass(self):
        # In its own tab: a tab left showing a browser-made page freezes when later tests switch GPU modes
        # (a WebKitGTK problem with any load_html() page, not specific to this one).
        self.addCleanup(self.close_new_tabs, self.win._tab_boxes())
        url = f"https://127.0.0.1:{self.tls_servers['127.0.0.1'].server_port}/done"
        self.win.create_new_tab(url)
        tab = self.win._tab_boxes()[-1]
        self.win.notebook.set_current_page(self.win.notebook.page_num(tab))
        wv = tab._arrow_webview
        self.assertTrue(spin(lambda: "not private" in (js(wv, "document.body ? document.body.innerText : ''") or ""), 10))
        self.assertNotIn("/done", Handler.requests, "the request never reached the site")
        self.assertEqual(wv.get_uri(), url)
        self.assertIn("bypass", js(wv, "document.body.innerText"))
        self.assertFalse(self.win.url_entry.get_style_context().has_class("url-secure"))

    def test_lock_reads_the_real_connection(self):
        # Trusting the test certificate for 127.0.0.2 only (127.0.0.1 stays blocked for the test above):
        # WebKit then loads the page but still reports the certificate's errors, and the lock must show them.
        self.win.context.allow_tls_certificate_for_host(Gio.TlsCertificate.new_from_file(self.cert_file), "127.0.0.2")
        self.addCleanup(self.close_new_tabs, self.win._tab_boxes())
        self.win.create_new_tab(f"https://127.0.0.2:{self.tls_servers['127.0.0.2'].server_port}/done")
        tab = self.win._tab_boxes()[-1]
        self.win.notebook.set_current_page(self.win.notebook.page_num(tab))
        wv = tab._arrow_webview
        self.assertTrue(spin(lambda: not wv.is_loading() and wv.get_title() == "done", 10), wv.get_uri())
        state, cert = self.win.connection_security(wv, wv.get_uri())
        self.assertEqual(state, "bad-cert")
        self.assertEqual(bb.certificate_summary(cert)["issued_to"], "arrow-test.example")
        self.assertTrue(self.win.url_entry.get_style_context().has_class("url-insecure"))
        self.assertIn("certificate has problems", self.win.url_entry.get_icon_tooltip_text(Gtk.EntryIconPosition.PRIMARY))
        markup = self.win.site_security_markup(wv, wv.get_uri(), "127.0.0.2")
        self.assertIn("Issued by: Arrow Test Issuer", markup)

    def test_certificate_details(self):
        c = bb.certificate_summary(Gio.TlsCertificate.new_from_file(self.cert_file))
        der = ssl.PEM_cert_to_DER_cert(open(self.cert_file).read())
        import hashlib
        self.assertEqual(c["sha256"].replace(":", ""), hashlib.sha256(der).hexdigest().upper())
        self.assertEqual((c["issued_to"], c["issued_by"]), ("arrow-test.example", "Arrow Test Issuer"))
        self.assertRegex(c["valid_until"], r"^\d{1,2} [A-Z][a-z]{2} \d{4}$")
        self.assertEqual(bb.dn_field(r"C=US,O=Acme\, Inc.,CN=R3", "O"), "Acme, Inc.")

    def test_about_page_links_to_the_project_page(self):
        dialog = self.win.build_settings_dialog("about")
        try:
            def find(widget):
                if isinstance(widget, Gtk.Label) and widget.get_text() == "Project page on GitHub":
                    return widget
                for child in (widget.get_children() if isinstance(widget, Gtk.Container) else ()):
                    found = find(child)
                    if found:
                        return found
            row = find(dialog).get_parent()
            while not hasattr(row, "_arrow_button"):
                row = row.get_parent()
            pages = self.win.notebook.get_n_pages()
            opened = []
            self.win.create_new_tab = lambda url=None, **kw: opened.append(url)
            try:
                row._arrow_button.clicked()
                spin(lambda: opened, 2)
            finally:
                del self.win.create_new_tab
            self.assertEqual(opened, ["https://github.com/Sangam1112/arrow-browser"])
            self.assertEqual(self.win.notebook.get_n_pages(), pages)
        finally:
            dialog.destroy()

    def test_about_page_shows_the_web_engine_version(self):
        def engine_row(dialog):
            def find(widget):
                if hasattr(widget, "_arrow_outdated"):
                    return widget
                for child in (widget.get_children() if isinstance(widget, Gtk.Container) else ()):
                    found = find(child)
                    if found:
                        return found
            return find(dialog)

        def labels(widget):
            if isinstance(widget, Gtk.Label):
                return [widget.get_text()]
            kids = widget.get_children() if isinstance(widget, Gtk.Container) else ()
            return [t for child in kids for t in labels(child)]

        version = ".".join(map(str, bb.webkit_version()))
        dialog = self.win.build_settings_dialog("about")
        try:
            row = engine_row(dialog)
            self.assertIn("Web engine: WebKitGTK " + version, labels(row))
            self.assertEqual(row._arrow_outdated, bb.webkit_version() < bb.MIN_WEBKIT_VERSION)
        finally:
            dialog.destroy()

        real_minimum = bb.MIN_WEBKIT_VERSION
        bb.MIN_WEBKIT_VERSION = (99, 0, 0)
        try:
            dialog = self.win.build_settings_dialog("about")
            try:
                row = engine_row(dialog)
                self.assertTrue(row._arrow_outdated)
                self.assertIn("⚠️ Outdated", labels(row))
            finally:
                dialog.destroy()
        finally:
            bb.MIN_WEBKIT_VERSION = real_minimum

    # ---- browser theme -------------------------------------------------------
    def test_browser_theme_switches_live_and_is_saved(self):
        win = self.win
        self.addCleanup(win.set_ui_theme, "dark")
        self.assertEqual(win.ui_theme, "dark", "dark stays the default")
        top_bar_colour = lambda: win.top_bar.get_style_context().get_property(
            "background-color", Gtk.StateFlags.NORMAL).to_string()
        dark = top_bar_colour()
        dialog = win.build_settings_dialog("general")
        try:
            buttons = dialog._arrow_controls["ui_theme"]
            self.assertTrue(buttons["dark"].get_active())
            buttons["light"].set_active(True)  # what a click does
            self.assertEqual(win.ui_theme, "light")
            self.assertEqual(top_bar_colour(), "rgb(255,255,255)", "light theme applies without a restart")
            with open(bb.CONFIG_FILE) as f:
                self.assertEqual(json.load(f)["ui_theme"], "light")
            buttons["dark"].set_active(True)
            self.assertEqual(top_bar_colour(), dark)
        finally:
            dialog.destroy()
        win.set_ui_theme("neon")
        self.assertEqual(win.ui_theme, "dark", "unknown themes are ignored")

    # ---- search ----------------------------------------------------------
    def test_search_shortcuts_and_own_search_engines(self):
        win = self.win
        saved_engine, saved_custom = win.search_engine, list(win.custom_search_engines)

        def restore():
            win.custom_search_engines = saved_custom
            win.set_search_engine(saved_engine)
        self.addCleanup(restore)
        self.assertIsNone(win.add_custom_search_engine("Local", "LT", self.base + "/done?q=%s"))
        self.assertIn("already", win.add_custom_search_engine("local", "zz", self.base + "/done?q=%s"))
        self.assertIn("already used", win.add_custom_search_engine("Other", "w", self.base + "/done?q=%s"))
        self.assertIn("%s", win.add_custom_search_engine("Other", "o", self.base + "/done"))
        with open(bb.CONFIG_FILE) as f:
            self.assertEqual(json.load(f)["custom_search_engines"],
                             [{"name": "Local", "keyword": "lt", "url": self.base + "/done?q={query}"}])

        win.url_entry.set_text("lt hello world")
        win.on_url_activate(win.url_entry)
        self.assertTrue(spin(lambda: "/done?q=hello%20world" in Handler.requests, 8), Handler.requests)

        win.set_search_engine("Local")
        dialog = win.build_settings_dialog("general")
        try:
            combo = dialog._arrow_controls["search_engine"]
            self.assertEqual(combo.get_active_text(), "Local")
            self.assertIn("Local", [row[0] for row in combo.get_model()])
        finally:
            dialog.destroy()
        win.url_entry.set_text("plain words")
        win.on_url_activate(win.url_entry)
        self.assertTrue(spin(lambda: "/done?q=plain%20words" in Handler.requests, 8), Handler.requests)
        self.assertIn("Local", win.url_entry.get_placeholder_text())

        win.remove_custom_search_engine("Local")
        self.assertEqual(win.search_engine, bb.DEFAULT_SEARCH_ENGINE, "removing the default engine falls back")
        self.assertEqual(win.custom_search_engines, [])

    # ---- tab audio ---------------------------------------------------------
    def test_tab_mute_button_follows_the_page(self):
        win = self.win
        tab_box = win.get_active_tab_box()
        wv, button = tab_box._arrow_webview, tab_box._arrow_audio_btn
        self.addCleanup(wv.set_is_muted, False)
        self.assertFalse(button.get_visible(), "silent tabs show no speaker")
        wv.set_is_muted(True)  # the notify::is-muted signal updates the tab
        self.assertTrue(spin(lambda: button.get_visible() and button.get_label() == "🔇", 2))
        win.toggle_tab_muted(tab_box)
        self.assertFalse(wv.get_is_muted())
        self.assertFalse(button.get_visible())

        # A tab playing sound (pages can't autoplay sound in a test, so a stand-in webview)
        state = {"playing": True, "muted": False}
        stand_in = type("StandIn", (), {"is_playing_audio": lambda self: state["playing"],
                                        "get_is_muted": lambda self: state["muted"]})()
        fake_tab = type("Tab", (), {})()
        fake_tab._arrow_webview, fake_tab._arrow_audio_btn = stand_in, Gtk.Button(label="?")
        win._update_tab_audio(fake_tab)
        self.assertTrue(fake_tab._arrow_audio_btn.get_visible())
        self.assertEqual(fake_tab._arrow_audio_btn.get_label(), "🔊")
        self.assertEqual(fake_tab._arrow_audio_btn.get_tooltip_text(), "Mute tab")
        state["playing"] = False
        win._update_tab_audio(fake_tab)
        self.assertFalse(fake_tab._arrow_audio_btn.get_visible(), "hidden again once the sound stops")

    # ---- export and backup ---------------------------------------------------
    def test_export_bookmarks_and_restore_a_backup(self):
        win = self.win
        saved = (list(win.bookmarks), win.adblock_enabled, win.download_dir, win.homepage)

        def restore():
            win.bookmarks, win.adblock_enabled, win.download_dir, win.homepage = saved
            bb.save_bookmarks(win.bookmarks)
            win.save_settings()
        self.addCleanup(restore)
        folder = tempfile.mkdtemp(dir=_HOME)
        win.bookmarks = [{"url": "https://kept.example/", "title": "Kept", "added": 1700000000}]
        self.assertEqual(win.export_bookmarks_to(os.path.join(folder, "marks.html")), 1)
        with open(os.path.join(folder, "marks.html")) as f:
            self.assertEqual([b["url"] for b in bb.parse_netscape_bookmarks(f.read())], ["https://kept.example/"])
        self.assertEqual(os.stat(os.path.join(folder, "marks.html")).st_mode & 0o077, 0)

        win.site_settings["zoomed.example"] = {"zoom": 1.5}
        win.homepage = "https://home.example"
        backup_path = os.path.join(folder, "backup.json")
        win.write_backup_to(backup_path)
        self.assertEqual(os.stat(backup_path).st_mode & 0o077, 0, "the backup is private to the user")

        # things change after the backup ...
        win.bookmarks = []
        win.site_settings.clear()
        win.homepage = "https://other.example"
        win.download_dir = folder  # this computer's own; a restore keeps it
        restored, added_b, sites = win.apply_backup(win.read_backup_file(backup_path))
        self.assertGreater(restored, 10)
        self.assertEqual((added_b, sites), (1, 1))
        self.assertEqual(win.homepage, "https://home.example")
        self.assertEqual(win.download_dir, folder)
        self.assertEqual(win.site_settings["zoomed.example"], {"zoom": 1.5})
        self.assertEqual([b["url"] for b in win.bookmarks], ["https://kept.example/"])
        with open(bb.CONFIG_FILE) as f:
            self.assertEqual(json.load(f)["homepage"], "https://home.example")

        with open(os.path.join(folder, "not-a-backup.json"), "w") as f:
            f.write("{}")
        with self.assertRaises(ValueError):
            win.read_backup_file(os.path.join(folder, "not-a-backup.json"))

    def test_private_window_never_writes_site_settings(self):
        private = bb.ArrowBrowserWindow(private=True)
        try:
            self.assertEqual(private.site_settings, {})
            bb.set_site_value(private.site_settings, "x.test", "zoom", 2.0)
            before = os.path.exists(bb.SITE_SETTINGS_FILE) and open(bb.SITE_SETTINGS_FILE).read()
            private._save_site_settings()
            after = os.path.exists(bb.SITE_SETTINGS_FILE) and open(bb.SITE_SETTINGS_FILE).read()
            self.assertEqual(before, after)
            self.assertIsNone(private.password_script, "no password detection in private windows")
        finally:
            private.destroy()


    def test_windows_get_minimize_and_maximize_buttons_under_wsl(self):
        original = bb.running_under_wsl
        bb.running_under_wsl = lambda: True
        try:
            wsl = bb.ArrowBrowserWindow(private=True)
        finally:
            bb.running_under_wsl = original
        try:
            self.assertEqual(wsl._titlebar.get_decoration_layout(), ":minimize,maximize,close")
        finally:
            wsl.destroy()
        self.assertIsNone(self.win._titlebar.get_decoration_layout(), "on Linux the desktop's own layout is kept")


if __name__ == "__main__":
    unittest.main()
