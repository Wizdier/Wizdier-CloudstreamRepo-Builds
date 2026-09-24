#!/usr/bin/env python3
"""
BDIX dev relay  —  run this on YOUR device (the one with BDIX access).
It lets the sandbox assistant fetch BDIX-only pages through YOUR authorized
ISP connection, so providers like Circleftp / CineplexBD can be debugged
and updated remotely.

Zero dependencies: Python 3 standard library only (works in Termux).

USAGE
  python3 bdix_relay.py --key mykey          # RECOMMENDED: key on the command line
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
  - Every request must carry the key -> 403 otherwise. Accepted forms:
      path mode  : ?key=KEY
      proxy mode : X-Relay-Key: KEY header  OR  proxy credentials -x http://KEY@host:port
                   (curl then sends Proxy-Authorization automatically)
      CONNECT    : same as proxy mode (--proxy-header, or -x http://KEY@host)
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
import secrets
import socket
import ssl
import sys
import threading
import urllib.parse

PORT = int(os.environ.get("RELAY_PORT", "8080"))
BIND = os.environ.get("RELAY_BIND", "127.0.0.1")
KEY = os.environ.get("RELAY_KEY") or secrets.token_urlsafe(12)
VERBOSE = os.environ.get("RELAY_VERBOSE", "") not in ("", "0")
TIMEOUT = 30

# Headers never forwarded to the target (hop-by-hop + relay auth + framing).
HOP_BY_HOP = {
    "connection", "keep-alive", "proxy-authenticate", "proxy-authorization",
    "te", "trailers", "transfer-encoding", "upgrade", "proxy-connection",
    "content-length", "host", "x-relay-key",
}
# Response headers never sent back to the client (framing handled by relay).
RESP_DROP = {
    "connection", "keep-alive", "transfer-encoding", "upgrade",
    "proxy-connection", "content-length",
}


class RelayHandler(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "BDIXRelay/1.0"

    # ------------------------------------------------------------------ utils
    def log_message(self, fmt, *args):
        if VERBOSE:
            sys.stderr.write("[relay] %s\n" % (fmt % args))

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
        if supplied == KEY:
            return True
        pa = self.headers.get("Proxy-Authorization", "")
        if pa.startswith("Basic "):
            try:
                dec = base64.b64decode(pa[6:].strip()).decode("utf-8", "replace")
            except Exception:
                return False
            if dec == KEY or dec.split(":", 1)[0] == KEY:
                return True
        return False

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

    # -------------------------------------------------------------- forwarding
    def _relay(self, method):
        target, supplied = self._resolve_target()
        if target is None:
            self._send_err(400, "bad request",
                           "use /?key=KEY&url=<encoded http(s) URL> or forward-proxy mode")
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
            if u.scheme == "https":
                ctx = ssl._create_unverified_context()
                conn = http.client.HTTPSConnection(
                    u.hostname, u.port or 443, timeout=TIMEOUT, context=ctx)
            else:
                conn = http.client.HTTPConnection(
                    u.hostname, u.port or 80, timeout=TIMEOUT)
            path = (u.path or "/") + (("?" + u.query) if u.query else "")
            conn.request(method, path, body=body, headers=headers)
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
        self._relay("GET")

    def do_HEAD(self):
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
        description="BDIX dev relay",
        epilog="example: python bdix_relay.py --key wizdierfix")
    ap.add_argument("--key", dest="cli_key",
                    help="relay key (else RELAY_KEY env var, else auto-generated)")
    ap.add_argument("--port", type=int, dest="cli_port",
                    help="listen port (default 8080)")
    ap.add_argument("--bind", dest="cli_bind",
                    help="bind address (default 127.0.0.1)")
    args = ap.parse_args()
    global KEY, PORT, BIND
    if args.cli_key:
        KEY = args.cli_key
    if args.cli_port:
        PORT = args.cli_port
    if args.cli_bind:
        BIND = args.cli_bind

    print("=" * 62)
    print(" BDIX dev relay")
    print(" listening : http://%s:%d" % (BIND, PORT))
    print(" key       : %s" % KEY)
    print(" local test: curl \"http://%s:%d/?key=%s&url=http://example.com/\"" % (BIND, PORT, KEY))
    print(" proxy cred : curl -x http://%s@%s:%d https://example.com/" % (KEY, BIND, PORT))
    print(" next      : cloudflared tunnel --url http://%s:%d" % (BIND, PORT))
    print("             (or:  ssh -R 80:%s:%d nokey@localhost.run)" % (BIND, PORT))
    print(" send the assistant: public tunnel URL + the key above")
    print(" Ctrl+C to stop")
    print("=" * 62)
    try:
        ThreadingRelay((BIND, PORT), RelayHandler).serve_forever()
    except KeyboardInterrupt:
        print("\nbye")


if __name__ == "__main__":
    main()
