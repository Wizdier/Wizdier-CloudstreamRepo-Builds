#!/usr/bin/env python3
"""
bdix_probe.py — sandbox-side harness for probing BDIX hosts through the
user's relay (bdix_relay.py running on their device).

Usage:
  # single probe via relay
  python3 bdix_probe.py --relay https://abc-xyz.trycloudflare.com --key KEY \
      probe http://103.x.y.z:8080/

  # batch from file (one URL per line, # comments allowed)
  python3 bdix_probe.py --relay ... --key KEY batch --file servers.txt

  # media/Range check (does the server honor Range? is it a real playlist?)
  python3 bdix_probe.py --relay ... --key KEY range http://host/file.mp4

  # save fetched page for offline parser work (note: --save goes after 'probe')
  python3 bdix_probe.py --relay ... --key KEY probe http://host/movies \
      --save /home/z/my-project/scripts/circleftp_movies.html

  # direct mode (no relay) for publicly reachable hosts
  python3 bdix_probe.py probe https://example.com

Relay request shape: GET {relay}/?key=K&url=<urlencoded target>
Headers forwarded: User-Agent, Accept, Range, Referer, Origin, Cookie, custom.
Redirects are NOT followed by default (30x + Location reported); use --follow.
"""

import argparse
import re
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

UA = ("Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Mobile Safari/537.36")
MAX_BODY = 512 * 1024  # first 512 KB is plenty for sniffing/HTML


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def relay_url(relay, key, target):
    return (relay.rstrip("/") + "/?key=" + urllib.parse.quote(key, safe="")
            + "&url=" + urllib.parse.quote(target, safe=""))


def fetch(url, headers=None, timeout=30, method="GET", follow=False):
    ctx = ssl._create_unverified_context()
    handlers = [urllib.request.HTTPSHandler(context=ctx)]
    if not follow:
        handlers.append(NoRedirect())
    opener = urllib.request.build_opener(*handlers)
    req = urllib.request.Request(
        url, method=method,
        headers={"User-Agent": UA, "Accept": "*/*", **(headers or {})})
    t0 = time.time()
    out = {"ms": 0, "status": 0, "headers": {}, "body": b"", "url": url, "err": ""}
    try:
        r = opener.open(req, timeout=timeout)
        out["status"] = r.status
        out["headers"] = dict(r.headers)
        out["body"] = r.read(MAX_BODY)
        out["url"] = r.url
    except urllib.error.HTTPError as e:
        out["status"] = e.code
        out["headers"] = dict(e.headers)
        try:
            out["body"] = e.read(MAX_BODY)
        except Exception:
            pass
        out["err"] = "%s %s" % (e.code, e.reason)
    except Exception as e:
        out["err"] = repr(e)
    out["ms"] = int((time.time() - t0) * 1000)
    return out


def sniff(res):
    ctype = res["headers"].get("Content-Type", "")
    head = res["body"][:1200].decode("utf-8", "replace")
    if "#EXTM3U" in head:
        return "HLS manifest"
    low = head.lower()
    if "<html" in low:
        if "index of /" in low:
            return "Apache dir index"
        return "HTML page"
    if "json" in ctype.lower():
        return "JSON"
    if not res["body"]:
        return "EMPTY body"
    return "binary/other (%s)" % (ctype or "?")


def title_of(res):
    m = re.search(rb"<title[^>]*>(.*?)</title>", res["body"][:2048], re.S | re.I)
    if m:
        return m.group(1).decode("utf-8", "replace").strip()[:70]
    line = res["body"][:80].decode("utf-8", "replace").strip().replace("\n", " ")
    return line[:70] if line else "-"


def print_result(url, res, extra=""):
    loc = res["headers"].get("Location", "")
    print("%-58s %s %6dms  %-24s srv=%-18s %s%s" % (
        url[:58], res["status"] or "ERR", res["ms"],
        sniff(res)[:24], res["headers"].get("Server", "-")[:18],
        title_of(res)[:40],
        ("  -> " + loc[:60]) if loc else ""))
    if res["err"]:
        print("    err: %s" % res["err"][:160])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--relay", help="public relay URL, e.g. https://x.trycloudflare.com")
    ap.add_argument("--key", help="relay key")
    ap.add_argument("--timeout", type=int, default=30)
    ap.add_argument("--follow", action="store_true", help="follow redirects")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p1 = sub.add_parser("probe")
    p1.add_argument("urls", nargs="+")
    p1.add_argument("--save", help="save fetched body to this file (put AFTER 'probe')")

    p2 = sub.add_parser("batch")
    p2.add_argument("--file", required=True)

    p3 = sub.add_parser("range")
    p3.add_argument("url")

    a = ap.parse_args()

    if a.cmd in ("probe", "batch") and a.relay and not a.key:
        sys.exit("--key is required with --relay")

    def map_url(u):
        if a.relay:
            return relay_url(a.relay, a.key, u), u
        return u, u

    if a.cmd == "probe":
        for u in a.urls:
            ru, orig = map_url(u)
            res = fetch(ru, timeout=a.timeout, follow=a.follow)
            print_result(orig, res)
            if a.save:
                with open(a.save, "wb") as f:
                    f.write(res["body"])
                print("    saved %d bytes -> %s" % (len(res["body"]), a.save))
    elif a.cmd == "batch":
        urls = [ln.strip() for ln in open(a.file, encoding="utf-8", errors="replace")
                if ln.strip() and not ln.strip().startswith("#")]
        print("probing %d URLs%s\n" % (len(urls), " via relay" if a.relay else " direct"))
        for u in urls:
            ru, orig = map_url(u)
            res = fetch(ru, timeout=a.timeout, follow=a.follow)
            print_result(orig, res)
    elif a.cmd == "range":
        ru, orig = map_url(a.url)
        res = fetch(ru, headers={"Range": "bytes=0-1023"},
                    timeout=a.timeout, follow=a.follow)
        cr = res["headers"].get("Content-Range", "")
        clen = res["headers"].get("Content-Length", "-")
        print("target  : %s" % orig)
        print("status  : %s %s (206 = Range honored, 200 = full body)" %
              (res["status"], res["err"]))
        print("type    : %s" % res["headers"].get("Content-Type", "-"))
        print("range   : %s (len=%s)" % (cr or "-", clen))
        head = res["body"][:64]
        print("first64 : %s" % head[:64])
        print("isM3U8  : %s" % ("yes" if res["body"].lstrip().startswith(b"#EXTM3U") else "no"))


if __name__ == "__main__":
    main()
