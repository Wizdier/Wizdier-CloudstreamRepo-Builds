#!/usr/bin/env python3
"""
BDIX dev relay v2  —  run this on YOUR device (the one with BDIX access).
It lets the sandbox assistant fetch BDIX-only pages through YOUR authorized
ISP connection, so providers like Circleftp / FTPBD / CineplexBD can be
debugged and updated remotely.

NEW IN v2 (2026-09-30):
  * MULTI-STREAM /par/N/<url> — parallel-range streaming proxy. Cloudstream
    can now stream BDIX files through the relay with N parallel connections
    (the AB Download Manager trick, but for playback): a player that sees
    2-2.5 MB/s on one connection gets the server's full aggregate speed.
    Full Range support (seeking works), HEAD support, automatic fallback to
    a plain single connection when the server does not honor ranges, and
    instant cleanup when the player aborts (seek/stop).
        local (same device)  : no key needed  -> http://127.0.0.1:8080/par/16/<url>
        via tunnel (outside) : X-Relay-Key header required
  * MULTIPLE KEYS — comma-separated:  --key k1,k2   (all keys are accepted)
  * "Address already in use" FIXED — a previous instance still running in
    another Termux session is detected and terminated automatically before
    the port is bound (that was the Errno 98 crash).

Zero dependencies: Python 3 standard library only (works in Termux).

USAGE
  python3 bdix_relay.py --key mykey          # key on the command line
  python3 bdix_relay.py --key k1,k2          # several keys, all valid
  python3 bdix_relay.py                       # key auto-generated, printed below
  RELAY_KEY=mysecret python3 bdix_relay.py    # env var also works
  (optional: --port 8080, --bind 127.0.0.1)

Then expose it to the outside with ONE of (both free, no account):
  A) cloudflared tunnel --url http://127.0.0.1:8080
       -> prints https://<random>.trycloudflare.com
  B) ssh -R 80:127.0.0.1:8080 nokey@localhost.run
       -> prints https://<random>.loca.lt   (A is more reliable)

Send the assistant the public URL + the key. Shut the relay down when done.

SECURITY
  - Binds 127.0.0.1 only: reachable ONLY through the tunnel you run.
  - Every request must carry a valid key -> 403 otherwise. Accepted forms:
      path mode  : ?key=KEY
      proxy mode : X-Relay-Key: KEY header  OR  proxy credentials -x http://KEY@host:port
                   (curl then sends Proxy-Authorization automatically)
      CONNECT    : same as proxy mode (--proxy-header, or -x http://KEY@host)
      /par/N/    : X-Relay-Key header when coming through the tunnel;
                   requests from the SAME DEVICE (127.0.0.1 and no
                   Cloudflare forwarding headers) are keyless so Cloudstream
                   can stream without embedding the key anywhere.
  - The tunnel URL is random and changes every run.
  - HTTPS targets use an unverified TLS context (BDIX panels often have
    self-signed or missing certs).

Env knobs: RELAY_PORT (default 8080), RELAY_KEY, RELAY_BIND (default 127.0.0.1),
RELAY_VERBOSE=1 to log every request.
"""

import base64
import http.client
import http.server
import os
import re
import secrets
import signal
import socket
import ssl
import sys
import threading
import time
import urllib.parse

PORT = int(os.environ.get("RELAY_PORT", "8080"))
BIND = os.environ.get("RELAY_BIND", "127.0.0.1")
KEYS = set()          # all accepted keys (filled in main())
VERBOSE = os.environ.get("RELAY_VERBOSE", "") not in ("", "0")
TIMEOUT = 30

# Parallel-streaming tuning
PAR_MIN_THREADS = 1
PAR_MAX_THREADS = 32
PAR_CHUNK = 2 * 1024 * 1024          # 2 MiB per worker slice
PAR_FIRST_CHUNK = 1 * 1024 * 1024    # fast-start slice
PAR_CAP = 256 * 1024 * 1024          # hard cap on the served range (256 MiB)

# Headers never forwarded to the target (hop-by-hop + relay auth + framing).
HOP_BY_HOP = {
    "connection", "keep-alive", "proxy-authenticate", "proxy-authorization",
    "te", "trailers", "transfer-encoding", "upgrade", "proxy-connection",
    "content-length", "host", "x-relay-key", "range", "accept-encoding",
}
# Response headers never sent back to the client (framing handled by relay).
RESP_DROP = {
    "connection", "keep-alive", "transfer-encoding", "upgrade",
    "proxy-connection", "content-length",
}
# Cloudflare tunnel evidence — if ANY is present the request came through
# the public tunnel, not from a local app, so the key is required.
CF_EVIDENCE = ("cf-ray", "cf-connecting-ip", "cf-ipcountry", "cf-visitor",
               "x-forwarded-for", "x-real-ip", "true-client-ip")


def log(fmt, *args):
    if VERBOSE:
        sys.stderr.write("[relay] %s\n" % (fmt % args))


# --------------------------------------------------------------------------
#  stale-instance cleanup — the Errno 98 ("Address already in use") fix
# --------------------------------------------------------------------------

def _cmdline_port(parts):
    """Best-effort port of a running relay from its argv (None = default)."""
    for i, p in enumerate(parts):
        if p == "--port" and i + 1 < len(parts):
            try:
                return int(parts[i + 1])
            except ValueError:
                return None
        if p.startswith("--port="):
            try:
                return int(p.split("=", 1)[1])
            except ValueError:
                return None
    return None


def kill_stale_instances(port):
    """Find and SIGTERM every OTHER bdix_relay.py instance bound to the SAME
    port so this one can take over. Relays on other ports are left alone.
    Termux/Android + desktop Linux both expose /proc."""
    me = os.getpid()
    victims = []
    try:
        import glob
        for d in glob.glob("/proc/[0-9]*"):
            try:
                with open(d + "/cmdline", "rb") as f:
                    cmd = f.read().decode("utf-8", "replace")
            except Exception:
                continue
            if "bdix_relay" not in cmd:
                continue
            parts = [p for p in cmd.split("\0") if p]
            # only kill interpreters running THIS script
            if not any(p.endswith("bdix_relay.py") for p in parts):
                continue
            try:
                pid = int(d.rsplit("/", 1)[1])
            except ValueError:
                continue
            if pid == me:
                continue
            vport = _cmdline_port(parts)
            if vport is None:
                vport = 8080  # no --port flag -> default port
            if vport == port:
                victims.append((pid, vport))
    except Exception:
        pass
    for pid, vport in victims:
        if vport != port:
            continue
        try:
            os.kill(pid, signal.SIGTERM)
            print("  killed stale relay pid %d (was holding port %d)" % (pid, vport))
        except Exception as e:
            print("  could not kill pid %d: %s" % (pid, e))
    if victims:
        # give the kernel a moment to release the sockets
        for _ in range(30):
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                s.bind((BIND, port))
                s.close()
                return True
            except OSError:
                time.sleep(0.1)
        return False
    return True


# --------------------------------------------------------------------------
#  upstream connection helpers
# --------------------------------------------------------------------------

def connect_target(u):
    """Open a fresh http.client connection for the (already urlsplit) target."""
    if u.scheme == "https":
        ctx = ssl._create_unverified_context()
        return http.client.HTTPSConnection(
            u.hostname, u.port or 443, timeout=TIMEOUT, context=ctx)
    return http.client.HTTPConnection(u.hostname, u.port or 80, timeout=TIMEOUT)


def request_path(u):
    """Build the path+query for the upstream request line.

    The incoming target may be raw (spaces) or percent-encoded; either way
    decode once to the TRUE path, then percent-encode every character that
    is not safe on an HTTP request line. Existing valid %XX escapes come
    back as the same escape; raw spaces/brackets/unicode become escapes."""
    path = u.path or "/"
    if u.query:
        path += "?" + u.query
    raw = urllib.parse.unquote(path)
    return urllib.parse.quote(raw, safe="/&=?#+@:;,!$'()*~-._+")


class RelayHandler(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "BDIXRelay/2.0"

    # ------------------------------------------------------------------ utils
    def log_message(self, fmt, *args):
        log(fmt, *args)

    def _send_err(self, code, title, detail):
        try:
            body = ("%s: %s\n" % (title, detail)).encode()
            self.send_response(code, title)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Connection", "close")
            self.end_headers()
            self.wfile.write(body)
        except Exception:
            pass
        self.close_connection = True

    def _authorized(self, supplied):
        """Key match via supplied value or standard proxy credentials."""
        if supplied:
            for k in supplied.split(","):
                if k.strip() in KEYS:
                    return True
        pa = self.headers.get("Proxy-Authorization", "")
        if pa.startswith("Basic "):
            try:
                dec = base64.b64decode(pa[6:].strip()).decode("utf-8", "replace")
            except Exception:
                return False
            if dec in KEYS or dec.split(":", 1)[0] in KEYS:
                return True
        return False

    def _is_local(self):
        """True when the request came from this device, not the tunnel."""
        peer = self.client_address[0]
        if peer not in ("127.0.0.1", "::1", "localhost"):
            return False
        for h in CF_EVIDENCE:
            if self.headers.get(h):
                return False
        return True

    def _resolve_target(self):
        """Return (target_url, supplied_key) or (None, None) if unmappable."""
        # Proxy mode first: curl -x sends the absolute URI as the request target.
        if self.path.startswith("http://") or self.path.startswith("https://"):
            return self.path, self.headers.get("X-Relay-Key", "")
        # Path mode: GET /?key=...&url=<encoded target>
        parsed = urllib.parse.urlsplit(self.path)
        if parsed.path in ("", "/"):
            q = urllib.parse.parse_qs(parsed.query)
            if "url" in q:
                return q["url"][0], q.get("key", [""])[0]
        return None, None

    def _parse_par(self):
        """Match /par/<N>/<target>. Returns (n, target_url) or None."""
        m = re.match(r"^/par/(\d{1,3})(?:/|$)(.*)$", self.path)
        if not m:
            return None
        n = max(PAR_MIN_THREADS, min(PAR_MAX_THREADS, int(m.group(1))))
        raw = m.group(2)
        # The extension percent-encodes the whole target URL. Accept it
        # encoded or raw: unquote once and prefer whichever is a valid URL.
        cand = urllib.parse.unquote(raw)
        for u in (cand, raw):
            if u.startswith("http://") or u.startswith("https://"):
                return n, u
        return None

    # -------------------------------------------------------------- forwarding
    def _relay(self, method):
        target, supplied = self._resolve_target()
        if target is None:
            self._send_err(400, "bad request",
                           "use /?key=KEY&url=<encoded http(s) URL>, "
                           "/par/N/<url> or forward-proxy mode")
            return
        if not self._authorized(supplied):
            self._send_err(403, "forbidden", "bad or missing relay key")
            return
        u = urllib.parse.urlsplit(target)
        if u.scheme not in ("http", "https") or not u.hostname:
            self._send_err(400, "bad target", "target must be an absolute http(s) URL")
            return

        headers = {k: v for k, v in self.headers.items()
                   if k.lower() not in HOP_BY_HOP}
        body = None
        if method in ("POST", "PUT", "PATCH"):
            try:
                n = int(self.headers.get("Content-Length") or 0)
            except ValueError:
                n = 0
            body = self.rfile.read(n) if n > 0 else None

        conn = None
        try:
            conn = connect_target(u)
            conn.request(method, request_path(u), body=body, headers=headers)
            resp = conn.getresponse()

            self.send_response_only(resp.status, resp.reason)
            for k, v in resp.getheaders():
                if k.lower() in RESP_DROP:
                    continue
                self.send_header(k, v)
            # close-delimited responses: simple + correct for probing
            self.send_header("Connection", "close")
            self.end_headers()
            if method != "HEAD":
                while True:
                    chunk = resp.read(65536)
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    self.wfile.flush()
        except Exception as e:
            self.log_message("relay error %s: %r", target, e)
            self._send_err(502, "relay error", str(e))
        finally:
            if conn is not None:
                try:
                    conn.close()
                except Exception:
                    pass
            self.close_connection = True

    # ------------------------------------------------------ parallel streaming
    def _upstream_headers(self):
        """Headers forwarded to the target on /par/ fetches."""
        h = {"Accept": "*/*"}
        ua = self.headers.get("User-Agent")
        h["User-Agent"] = ua or (
            "Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/125.0 Mobile Safari/537.36")
        ref = self.headers.get("Referer")
        if ref:
            h["Referer"] = ref
        return h

    def _probe(self, u):
        """Range-probe the target. Returns (status, total, ctype, ranges_ok)."""
        conn = connect_target(u)
        try:
            conn.request("GET", request_path(u),
                         headers=dict(self._upstream_headers(),
                                      **{"Range": "bytes=0-1"}))
            r = conn.getresponse()
            r.read(64)  # drain a bit; we only need the headers
            cr = r.getheader("Content-Range")
            total = None
            if cr:
                m = re.search(r"/(\d+)\s*$", cr)
                if m:
                    total = int(m.group(1))
            ranges_ok = (r.status == 206) and total is not None
            ctype = r.getheader("Content-Type") or "application/octet-stream"
            return r.status, total, ctype, ranges_ok
        finally:
            try:
                conn.close()
            except Exception:
                pass

    def _passthrough(self, u):
        """Single-connection fallback (no range support / tiny files)."""
        conn = None
        try:
            conn = connect_target(u)
            conn.request("GET", request_path(u),
                         headers=self._upstream_headers())
            r = conn.getresponse()
            if r.status >= 400:
                self._send_err(r.status, "upstream", "target answered %d" % r.status)
                return
            self.send_response_only(200, "OK")
            self.send_header("Content-Type",
                             r.getheader("Content-Type") or "application/octet-stream")
            cl = r.getheader("Content-Length")
            if cl:
                self.send_header("Content-Length", cl)
            self.send_header("Accept-Ranges", "none")
            self.send_header("Connection", "close")
            self.end_headers()
            if self.command != "HEAD":
                while True:
                    chunk = r.read(65536)
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    self.wfile.flush()
        except Exception as e:
            self.log_message("passthrough error %s: %r", u.geturl(), e)
            try:
                self._send_err(502, "relay error", str(e))
            except Exception:
                pass
        finally:
            if conn is not None:
                try:
                    conn.close()
                except Exception:
                    pass
            self.close_connection = True

    def _serve_par(self):
        par = self._parse_par()
        if par is None:
            self._send_err(400, "bad request",
                           "parallel mode is /par/<1-32>/<encoded target URL>")
            return
        n, target = par

        # auth: local device = keyless; tunnel = key required
        if not self._is_local():
            if not self._authorized(self.headers.get("X-Relay-Key", "")):
                self._send_err(403, "forbidden",
                               "parallel mode via the tunnel needs the X-Relay-Key header")
                return

        u = urllib.parse.urlsplit(target)
        if u.scheme not in ("http", "https") or not u.hostname:
            self._send_err(400, "bad target", "target must be an absolute http(s) URL")
            return

        # ── probe: size / range support ─────────────────────────────────
        try:
            status, total, ctype, ranges_ok = self._probe(u)
        except Exception as e:
            self._send_err(502, "relay error", "probe failed: %s" % e)
            return
        if status >= 400:
            self._send_err(status, "upstream", "target answered %d" % status)
            return
        if total is None or not ranges_ok or total < PAR_CHUNK:
            # no usable size / no ranges / tiny file -> plain relay
            self._passthrough(u)
            return

        # ── client range ────────────────────────────────────────────────
        rng = self.headers.get("Range")
        start = 0
        end = total - 1
        m = re.match(r"^bytes=(\d*)-(\d*)\s*$", rng or "")
        if m and (m.group(1) or m.group(2)):
            if m.group(1):
                start = int(m.group(1))
                if not m.group(2):
                    end = total - 1
                else:
                    end = min(int(m.group(2)), total - 1)
            else:
                # suffix form: bytes=-500 -> last 500 bytes
                suffix = int(m.group(2))
                start = max(0, total - suffix)
            if start > end or start >= total:
                self._send_err(416, "range not satisfiable",
                               "start %d beyond end %d" % (start, end))
                return
        # keep a single player request bounded; the player re-opens with a
        # fresh Range when it wants more (normal progressive behaviour)
        if end - start + 1 > PAR_CAP:
            end = start + PAR_CAP - 1
        length = end - start + 1

        # ── HEAD: answer from the probe ─────────────────────────────────
        if self.command == "HEAD":
            self.send_response_only(206, "Partial Content")
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(length))
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Content-Range",
                             "bytes %d-%d/%d" % (start, end, total))
            self.send_header("Connection", "close")
            self.end_headers()
            self.close_connection = True
            return

        # ── chunk plan: small first slice for a fast start, then equal ──
        first = min(PAR_FIRST_CHUNK, length)
        bounds = [(start, start + first - 1)]
        pos = start + first
        while pos <= end:
            hi = min(pos + PAR_CHUNK - 1, end)
            bounds.append((pos, hi))
            pos = hi + 1
        n = max(1, min(n, len(bounds)))

        # ordered chunk buffers; workers fill, the handler writes in order
        chunks = [None] * len(bounds)   # None = pending, bytes = ready, False = failed
        next_to_start = [0]
        written = [0]
        stop = threading.Event()
        lock = threading.Condition()
        t0 = time.time()

        def fetch_range(lo, hi):
            conn = connect_target(u)
            try:
                conn.request(
                    "GET", request_path(u),
                    headers=dict(self._upstream_headers(),
                                 **{"Range": "bytes=%d-%d" % (lo, hi)}))
                r = conn.getresponse()
                if r.status != 206:
                    raise IOError("upstream %d for range %d-%d" % (r.status, lo, hi))
                buf = bytearray()
                while True:
                    piece = r.read(65536)
                    if not piece:
                        break
                    buf += piece
                if len(buf) != hi - lo + 1:
                    raise IOError("range %d-%d short: %d bytes" % (lo, hi, len(buf)))
                return bytes(buf)
            finally:
                try:
                    conn.close()
                except Exception:
                    pass

        def worker():
            while not stop.is_set():
                with lock:
                    if next_to_start[0] >= len(bounds):
                        return
                    idx = next_to_start[0]
                    next_to_start[0] += 1
                    lo, hi = bounds[idx]
                data = None
                for attempt in (1, 2):  # one retry per slice
                    if stop.is_set():
                        return
                    try:
                        data = fetch_range(lo, hi)
                        break
                    except Exception as e:
                        self.log_message("par slice %d try %d failed: %r", idx, attempt, e)
                with lock:
                    chunks[idx] = data if data is not None else False
                    lock.notify_all()
                if data is None:
                    return

        # ---- headers first
        self.send_response_only(206, "Partial Content")
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(length))
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Range", "bytes %d-%d/%d" % (start, end, total))
        self.send_header("Connection", "close")
        self.end_headers()

        workers = [threading.Thread(target=worker, daemon=True) for _ in range(n)]
        for w in workers:
            w.start()

        aborted = False
        try:
            for i in range(len(bounds)):
                with lock:
                    while chunks[i] is None:
                        if chunks[i] is False:
                            raise IOError("slice %d failed upstream" % i)
                        lock.wait(timeout=1.0)
                    if chunks[i] is False:
                        raise IOError("slice %d failed upstream" % i)
                self.wfile.write(chunks[i])
                self.wfile.flush()
                written[0] += len(chunks[i])
                chunks[i] = None  # free the buffer
        except (BrokenPipeError, ConnectionResetError, socket.timeout):
            aborted = True  # player seeked/stopped: normal
        except Exception as e:
            self.log_message("par write failed at slice %d: %r", i, e)
        finally:
            stop.set()
            with lock:
                lock.notify_all()
            for w in workers:
                w.join(timeout=2.0)
            self.close_connection = True
            self.log_message(
                "par %d threads: %d bytes in %.1fs (%.1f MB/s) %s",
                n, written[0], time.time() - t0,
                written[0] / max(0.1, time.time() - t0) / 1e6,
                "ABORTED" if aborted else "done")

    # ------------------------------------------------------------ CONNECT mode
    def do_CONNECT(self):
        if not self._authorized(self.headers.get("X-Relay-Key", "")):
            self._send_err(403, "forbidden", "bad or missing relay key")
            return
        host, _, port = self.path.partition(":")
        try:
            upstream = socket.create_connection((host, int(port or 443)),
                                                timeout=TIMEOUT)
        except Exception as e:
            self._send_err(502, "connect failed", str(e))
            return
        self.log_message("CONNECT %s -> open", self.path)
        self.send_response_only(200, "Connection Established")
        self.end_headers()

        sock = self.connection

        def pump(a, b):
            try:
                while True:
                    data = a.recv(65536)
                    if not data:
                        break
                    b.sendall(data)
            except Exception:
                pass
            try:
                b.shutdown(socket.SHUT_WR)
            except Exception:
                pass

        t1 = threading.Thread(target=pump, args=(sock, upstream), daemon=True)
        t2 = threading.Thread(target=pump, args=(upstream, sock), daemon=True)
        t1.start()
        t2.start()
        t1.join()
        t2.join()
        self.close_connection = True

    # ------------------------------------------------------------- HTTP verbs
    def do_GET(self):
        if self.path.startswith("/par/"):
            self._serve_par()
        else:
            self._relay("GET")

    def do_HEAD(self):
        if self.path.startswith("/par/"):
            self._serve_par()
        else:
            self._relay("HEAD")

    def do_POST(self):
        self._relay("POST")

    def do_PUT(self):
        self._relay("PUT")

    def do_PATCH(self):
        self._relay("PATCH")

    def do_DELETE(self):
        self._relay("DELETE")


class ThreadingRelay(http.server.ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def main():
    import argparse
    ap = argparse.ArgumentParser(
        description="BDIX dev relay v2 (probe + parallel-range streaming)")
    ap.add_argument("--key", dest="cli_key",
                    help="relay key, comma-separated for several (else "
                         "RELAY_KEY env var, else auto-generated)")
    ap.add_argument("--port", type=int, dest="cli_port",
                    help="listen port (default 8080)")
    ap.add_argument("--bind", dest="cli_bind",
                    help="bind address (default 127.0.0.1)")
    args = ap.parse_args()
    global KEYS, PORT, BIND
    if args.cli_key:
        raw = args.cli_key
    elif os.environ.get("RELAY_KEY"):
        raw = os.environ["RELAY_KEY"]
    else:
        raw = secrets.token_urlsafe(12)
    KEYS = {k.strip() for k in raw.split(",") if k.strip()}
    if args.cli_port:
        PORT = args.cli_port
    if args.cli_bind:
        BIND = args.cli_bind

    print("=" * 62)
    print(" BDIX dev relay v2")
    print(" listening : http://%s:%d" % (BIND, PORT))
    print(" key(s)    : %s" % ", ".join(sorted(KEYS)))
    print(" local test: curl \"http://%s:%d/?key=%s&url=http://example.com/\"" % (BIND, PORT, sorted(KEYS)[0]))
    print(" proxy cred : curl -x http://%s@%s:%d https://example.com/" % (sorted(KEYS)[0], BIND, PORT))
    print(" streaming : curl \"http://%s:%d/par/16/<encoded target url>\"  (local: keyless)" % (BIND, PORT))
    print(" next      : cloudflared tunnel --url http://%s:%d" % (BIND, PORT))
    print("             (or:  ssh -R 80:%s:%d nokey@localhost.run)" % (BIND, PORT))
    print(" send the assistant: public tunnel URL + the key above")
    print(" Ctrl+C to stop")
    print("=" * 62)

    # v2: an older instance in another Termux session used to crash this
    # start with "OSError: [Errno 98] Address already in use". Kill it.
    if not kill_stale_instances(PORT):
        print("\nPort %d is still busy after cleanup. Fix it with:\n"
              "  pkill -f bdix_relay.py   (then run this again)\n"
              "or pick another port:      --port 8081" % PORT)
        raise SystemExit(1)

    try:
        ThreadingRelay((BIND, PORT), RelayHandler).serve_forever()
    except KeyboardInterrupt:
        print("\nbye")


if __name__ == "__main__":
    main()
