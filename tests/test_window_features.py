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
_HOME = tempfile.mkdtemp(prefix="bharat-test-home-")
os.environ["HOME"] = _HOME

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
spec = importlib.util.spec_from_file_location("bb_window", os.path.join(ROOT, "bharat_browser.py"))
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


class Handler(http.server.BaseHTTPRequestHandler):
    hits = {}
    requests = []  # full paths, query included

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
                        "-subj", "/O=Bharat Test Issuer/CN=bharat-test.example",
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
        bb.BharatBrowserWindow._maybe_refresh_tracker_list = lambda self: False
        bb.BharatBrowserWindow.start_auto_git_update_check = lambda self: False
        cls.win = bb.BharatBrowserWindow()
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
        try:
            wv = self.load("/darksite", "darksite")
            win.on_dark_clicked(win.btn_dark)  # switched on while a dark page is showing
            self.assertTrue(spin(lambda: js(wv, filtered) == "false", 3), "already-dark page was inverted (turns white)")
            self.load("/thin", "thin")
            self.assertTrue(spin(lambda: js(wv, filtered) == "true", 3), "light page not darkened")
            js(wv, "document.body.style.background = '#121212'")  # the site switches to its own dark theme
            self.assertTrue(spin(lambda: js(wv, filtered) == "false", 3), "page that turned dark still inverted")
            self.load("/darksite", "darksite")
            self.assertTrue(spin(lambda: js(wv, filtered) == "false", 3), "newly loaded dark page was inverted")
        finally:
            if win.dark_mode_active:
                win.on_dark_clicked(win.btn_dark)

    # ---- tabs ----------------------------------------------------------
    def test_switching_tabs_shows_that_tabs_address_and_title(self):
        win = self.win
        win.create_new_tab(self.base + "/blank")
        win.create_new_tab(self.base + "/thin")
        tabs = [win.notebook.get_nth_page(i) for i in range(win.notebook.get_n_pages())]
        self.assertTrue(spin(lambda: all(not t._bharat_webview.is_loading() and t._bharat_webview.get_title()
                                         for t in tabs[-2:]), 10))
        try:
            for tab in tabs[-2:] + tabs[-2:]:
                win.notebook.set_current_page(win.notebook.page_num(tab))
                wv = tab._bharat_webview
                self.assertEqual(win.url_entry.get_text(), wv.get_uri(), "address bar shows the tab clicked")
                self.assertTrue(win.get_title().startswith(wv.get_title() + " - "), "window title too")
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
            popup = win.notebook.get_nth_page(win.notebook.get_n_pages() - 1)._bharat_webview
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
        spin(lambda: all(not win.notebook.get_nth_page(i)._bharat_webview.is_loading() for i in range(win.notebook.get_n_pages())))
        last = win.notebook.get_nth_page(win.notebook.get_n_pages() - 1)
        win.set_tab_pinned(last, True)
        self.assertEqual(win.notebook.page_num(last), 0, "pinned tab moves to the front")
        self.assertFalse(last._bharat_close_btn.get_visible())
        self.assertTrue(last._bharat_label.get_text().startswith("📌"))
        urls, pinned = win._collect_session()
        self.assertEqual(pinned, [0])
        win._run_session_save()
        with open(bb.SESSION_FILE) as f:
            self.assertEqual(json.load(f)["pinned"], [0])

        n = win.notebook.get_n_pages()
        win.close_other_tabs(win.notebook.get_nth_page(1))
        self.assertEqual(win.notebook.get_n_pages(), 2, "close-others keeps the chosen tab and pinned tabs")
        self.assertTrue(win._closed_tabs)
        before = win.notebook.get_n_pages()
        win.reopen_closed_tab()
        self.assertEqual(win.notebook.get_n_pages(), before + 1)
        win.set_tab_pinned(last, False)
        self.assertTrue(last._bharat_close_btn.get_visible())

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
        opener = self.open_tab("/opener", "opener")._bharat_webview
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
        self.assertEqual(tab._bharat_webview.get_uri(), self.base + "/framed", "the tab still shows its own page")

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

    # ---- links from other apps ---------------------------------------------
    def test_links_passed_at_startup_open_as_tabs(self):
        win = bb.BharatBrowserWindow(private=True, startup_urls=[self.base + "/done", self.base + "/thin"])
        try:
            uris = [tb._bharat_webview.get_uri() for tb in win._tab_boxes()]
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
        new = {t._bharat_label.get_text(): i for t, i in results.items() if t in self.win._tab_boxes()[before:]}
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
        self.assertTrue(spin(lambda: tab._bharat_webview.get_title() == title and not tab._bharat_webview.is_loading(), 10))
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
            self.assertTrue(spin(lambda: not tab._bharat_webview.is_loading(), 10))
            # A renderer stuck in a script never answers the typed-text check.
            tab._bharat_webview.run_javascript_in_world = lambda *args: None
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
            del tab._bharat_webview.run_javascript_in_world
            win.close_tab(front)
            win.close_tab(tab)

    def test_sleeping_tab_ends_its_renderer_and_comes_back(self):
        self.addCleanup(self.close_new_tabs, self.win._tab_boxes())
        tab = self.open_tab("/article", "Test Article")
        wv = tab._bharat_webview
        wv.load_uri(self.base + "/done")
        self.assertTrue(spin(lambda: wv.get_title() == "done", 10))
        self.open_tab("/blank", "blank")
        pid = self.measure([tab])[tab]["pid"]
        self.assertIsNotNone(pid)
        self.assertTrue(self.win._suspend_tab(tab))
        self.assertTrue(spin(lambda: pid not in bb.web_process_pids(), 5), "the sleeping tab's renderer is gone")
        self.assertTrue(tab._bharat_label.get_text().startswith("💤"))
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
        self.assertTrue(spin(lambda: last._bharat_webview.get_title() == "blank", 10), "the tab you land on loads")
        spin(lambda: False, 1.0)
        self.assertEqual((Handler.hits.get("/r1", 0), Handler.hits.get("/r2", 0)), (0, 0), "the others wait")
        self.assertEqual(r1._bharat_label.get_text(), "💤 127.0.0.1")
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
        js(typed._bharat_webview, "const t=document.getElementById('t'); t.value='a reply in progress';"
                                  "t.dispatchEvent(new Event('input', {bubbles: true})); 1")
        self.open_tab("/blank", "blank")
        for tab in (plain, pinned, typed):
            self.win._tab_last_active[id(tab)] = time.monotonic() - 3600
        self.win._check_tab_suspension()
        self.assertTrue(spin(lambda: self.asleep(plain), 5), "an idle tab goes to sleep")
        spin(lambda: False, 1.0)
        self.assertFalse(self.asleep(pinned), "pinned tabs stay awake")
        self.assertFalse(self.asleep(typed), "so do tabs holding typed text")
        js(typed._bharat_webview, "document.getElementById('t').value=''; 1")  # the reply was sent
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
        opener = opener_tab._bharat_webview
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
        self.assertEqual(opener._bharat_related, {opener})

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
        self.assertTrue(href.startswith("bharat://allow-http?t="))

        class SchemeReq:
            def __init__(self, uri): self.uri, self.body = uri, None
            def get_uri(self): return self.uri
            def finish(self, stream, length, ctype): self.body = stream.read_bytes(length, None).get_data().decode()

        forged = SchemeReq("bharat://allow-http?t=guess")
        self.win._on_bharat_scheme(forged, None)
        self.assertNotIn("plain-only.example", self.win._http_allowed_hosts, "a guessed token does nothing")
        real = SchemeReq(href)
        self.win._on_bharat_scheme(real, None)
        self.assertIn("plain-only.example", self.win._http_allowed_hosts)
        self.assertIn("http://plain-only.example/page", real.body)
        again = SchemeReq(href)
        self.win._on_bharat_scheme(again, None)
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
            login = login_tab._bharat_webview
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
            stack = dialog._bharat_stack
            self.assertEqual([stack.child_get_property(c, "name") for c in stack.get_children()],
                             ["general", "privacy", "data", "performance", "about"])
            self.assertEqual(stack.get_visible_child_name(), "privacy")
            controls = dialog._bharat_controls
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
                self.tls, self._bharat_mixed_content, self._bharat_committed = tls, mixed, committed

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
        wv = tab._bharat_webview
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
        wv = tab._bharat_webview
        self.assertTrue(spin(lambda: not wv.is_loading() and wv.get_title() == "done", 10), wv.get_uri())
        state, cert = self.win.connection_security(wv, wv.get_uri())
        self.assertEqual(state, "bad-cert")
        self.assertEqual(bb.certificate_summary(cert)["issued_to"], "bharat-test.example")
        self.assertTrue(self.win.url_entry.get_style_context().has_class("url-insecure"))
        self.assertIn("certificate has problems", self.win.url_entry.get_icon_tooltip_text(Gtk.EntryIconPosition.PRIMARY))
        markup = self.win.site_security_markup(wv, wv.get_uri(), "127.0.0.2")
        self.assertIn("Issued by: Bharat Test Issuer", markup)

    def test_certificate_details(self):
        c = bb.certificate_summary(Gio.TlsCertificate.new_from_file(self.cert_file))
        der = ssl.PEM_cert_to_DER_cert(open(self.cert_file).read())
        import hashlib
        self.assertEqual(c["sha256"].replace(":", ""), hashlib.sha256(der).hexdigest().upper())
        self.assertEqual((c["issued_to"], c["issued_by"]), ("bharat-test.example", "Bharat Test Issuer"))
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
            while not hasattr(row, "_bharat_button"):
                row = row.get_parent()
            pages = self.win.notebook.get_n_pages()
            opened = []
            self.win.create_new_tab = lambda url=None, **kw: opened.append(url)
            try:
                row._bharat_button.clicked()
                spin(lambda: opened, 2)
            finally:
                del self.win.create_new_tab
            self.assertEqual(opened, ["https://github.com/Sangam1112/bharat-browser"])
            self.assertEqual(self.win.notebook.get_n_pages(), pages)
        finally:
            dialog.destroy()

    def test_private_window_never_writes_site_settings(self):
        private = bb.BharatBrowserWindow(private=True)
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


if __name__ == "__main__":
    unittest.main()
