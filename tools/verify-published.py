#!/usr/bin/env python3
"""Check a published release exactly as the in-app updater will: download
arrow_browser.py and package.json from the vX.Y.Z tag on GitHub, then verify the
SHA-256 and the Ed25519 signature with the verifier built into the app.

  tools/verify-published.py [version]     (default: the version in package.json)
"""
import hashlib
import json
import os
import re
import sys
import time
import urllib.request

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
REPO = "Sangam1112/arrow-browser"
# Installs from before the rename (Bharat Browser) still ask the old address, which GitHub redirects.
LEGACY_REPO = "Sangam1112/bharat-browser"


def fetch(url, tries=8):
    for attempt in range(tries):
        try:
            req = urllib.request.Request(f"{url}?cb={time.time()}", headers={"User-Agent": "arrow-verify"})
            return urllib.request.urlopen(req, timeout=20).read()
        except Exception as e:
            if attempt == tries - 1:
                sys.exit(f"Could not download {url}: {e}")
            time.sleep(15)  # raw.githubusercontent.com takes a moment to serve a new tag


def main():
    with open(os.path.join(ROOT, "package.json")) as f:
        version = sys.argv[1] if len(sys.argv) > 1 else json.load(f)["version"]
    base = f"https://raw.githubusercontent.com/{REPO}/v{version}/"
    source, pkg = fetch(base + "arrow_browser.py"), json.loads(fetch(base + "package.json"))
    text = source.decode()
    ns = {"hashlib": hashlib,
          "UPDATE_PUBLIC_KEY_HEX": re.search(r'^UPDATE_PUBLIC_KEY_HEX = "(\w+)"', text, re.M).group(1),
          "_UPDATE_SIGNATURE_PREFIX": b"bharat-browser-update\n"}
    exec(re.search(r"# ed25519 verify begin\n(.*?)# ed25519 verify end", text, re.S).group(1), ns)
    exec(re.search(r"(def verify_update_signature.*?)\n\n\n", text, re.S).group(1), ns)
    sha_ok = hashlib.sha256(source).hexdigest() == pkg.get("sha256")
    sig_ok = ns["verify_update_signature"](pkg["version"], source, pkg.get("signature", ""))
    legacy_ok = fetch(f"https://raw.githubusercontent.com/{LEGACY_REPO}/v{version}/bharat_browser.py") == source
    print(f"v{version}: version in package.json = {pkg['version']}, sha256 ok = {sha_ok}, signature valid = {sig_ok}, "
          f"old installs get the same file = {legacy_ok}")
    if not (sha_ok and sig_ok and legacy_ok and pkg["version"] == version):
        sys.exit(1)


main()
