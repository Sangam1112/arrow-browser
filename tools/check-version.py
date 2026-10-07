#!/usr/bin/env python3
"""Fail if the version differs between package.json (the single source of truth),
arrow_browser.py, the README install commands, CHANGELOG.md and the RPM changelog."""
import json
import os
import re
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))


def read(name):
    with open(os.path.join(ROOT, name), encoding="utf-8") as f:
        return f.read()


version = json.loads(read("package.json"))["version"]
checks = {
    "arrow_browser.py APP_VERSION": re.search(r'^APP_VERSION = "([^"]+)"', read("arrow_browser.py"), re.M),
    "arrow_browser.py header": re.search(r"^Arrow Browser v(\S+) - ", read("arrow_browser.py"), re.M),
    "CHANGELOG.md top entry": re.search(r"^## \[?v?([\d.]+)", read("CHANGELOG.md"), re.M),
    "build-rpm.sh top changelog": re.search(r"^%changelog\n\* .*? - ([\d.]+)-1", read("build-rpm.sh"), re.M),
}
readme_versions = set(re.findall(r"^VERSION=([\d.]+)$", read("README.md"), re.M))
if readme_versions != {version}:
    checks["README install commands (VERSION=...)"] = re.search(r"(.+)", ", ".join(sorted(readme_versions)) or "none found")
bad = [f"  {name}: {m.group(1) if m else 'NOT FOUND'}" for name, m in checks.items() if not m or m.group(1) != version]
# Installs from before the rename update from bharat_browser.py; it must be the very same file.
if not os.path.exists(os.path.join(ROOT, "bharat_browser.py")) or read("bharat_browser.py") != read("arrow_browser.py"):
    bad.append("  bharat_browser.py: not identical to arrow_browser.py (run tools/update-checksum.sh)")
if bad:
    sys.exit(f"Version mismatch (package.json says {version}):\n" + "\n".join(bad) + "\nRun tools/bump-version.py to change versions.")
print(f"Version {version} is consistent everywhere.")
