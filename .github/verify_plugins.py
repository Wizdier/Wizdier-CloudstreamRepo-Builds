#!/usr/bin/env python3
"""
CI validator for the Wizdier builds repo.

Fails the workflow if ANY of these drift out of sync (the exact failure that
made every extension uninstallable after the v215 push):
  1. plugins.json fileHash  != sha256 of the actual .cs3 bytes
  2. plugins.json fileSize  != actual .cs3 byte length
  3. plugins.json version   != manifest.json version inside the .cs3
  4. the .cs3 is not a valid zip / missing classes.dex / missing manifest.json
  5. the url basename does not resolve to a file in the repo
"""
import hashlib
import json
import os
import sys
import urllib.parse
import zipfile

os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

data = json.load(open("plugins.json", encoding="utf-8"))
failures = []

for p in data:
    name = p.get("name", "<unnamed>")
    # resolve the FULL url path (e.g. .../main/cs3/Foo.cs3 -> cs3/Foo.cs3)
    path = urllib.parse.urlparse(urllib.parse.unquote(p.get("url", ""))).path
    parts = path.split("/main/", 1)
    fname = parts[1] if len(parts) == 2 else os.path.basename(path)

    if not os.path.exists(fname):
        failures.append(f"{name}: url points to missing file {fname!r}")
        continue

    raw = open(fname, "rb").read()
    actual_sha = "sha256-" + hashlib.sha256(raw).hexdigest()
    actual_size = len(raw)

    if p.get("fileHash") != actual_sha:
        failures.append(f"{name}: fileHash stale (declared {p.get('fileHash')}, actual {actual_sha})")
    if p.get("fileSize") != actual_size:
        failures.append(f"{name}: fileSize stale (declared {p.get('fileSize')}, actual {actual_size})")

    if not zipfile.is_zipfile(fname):
        failures.append(f"{name}: not a valid zip")
        continue
    with zipfile.ZipFile(fname) as z:
        names = z.namelist()
        if z.testzip() is not None:
            failures.append(f"{name}: corrupt zip entry")
        if "classes.dex" not in names:
            failures.append(f"{name}: no classes.dex")
        if "manifest.json" not in names:
            failures.append(f"{name}: no manifest.json")
        else:
            try:
                inner = int(json.loads(z.read("manifest.json"))["version"])
                if inner != p.get("version"):
                    failures.append(f"{name}: manifest version {inner} != plugins.json version {p.get('version')}")
            except Exception as e:
                failures.append(f"{name}: unreadable manifest.json ({e})")

if failures:
    print("PLUGINS.JSON VERIFY FAILED:")
    for f in failures:
        print("  -", f)
    sys.exit(1)

print(f"OK: all {len(data)} plugins.json entries match the actual .cs3 bytes (hash, size, version, zip structure).")
