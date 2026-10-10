# BDIX Relay Setup — give the sandbox live access to your BDIX

**Problem:** BDIX panels (Circleftp, CineplexBD, FTPBD, etc.) are only reachable
from inside Bangladesh. The sandbox sits in Hong Kong and cannot see them, so
when a BDIX site changes its layout, the provider code can't be debugged
remotely.

**Fix:** Your phone/PC is already authorized on your ISP's BDIX routes. Run a
tiny relay on it and expose it through a free tunnel. The sandbox then fetches
BDIX pages through *your* connection — same loop used for the Movy/Bingr
updates. No paid service involved, nothing cracked.

**v2 (2026-09-30)** adds the parallel-range streaming lane for Cloudstream
playback (see "Stream threads" below) and fixes the
`OSError: [Errno 98] Address already in use` crash.

---

## Android (Termux) — 5 minutes

1. Install **Termux** (from F-Droid: f-droid.org, the Play Store build is outdated)
2. In Termux:

```bash
pkg update -y && pkg install python cloudflared
# copy bdix_relay.py into Termux storage, then:
python bdix_relay.py --key YOURKEY1,YOURKEY2
```

   (several keys are fine — comma-separated, all accepted. No `--key` prints
   an auto-generated one.)

3. It prints the key(s) you gave it. Leave this session running.
4. Open a **second Termux session** (swipe from left → New Session):

```bash
cloudflared tunnel --url http://127.0.0.1:8080
```

5. It prints a public URL like `https://random-words.trycloudflare.com`
6. **Send the sandbox assistant: that URL + the key(s).** Done.

If you started the relay before and it is still running in another Termux
session, v2 now **finds and stops the old instance automatically** (it used to
crash with `OSError: [Errno 98] Address already in use`). Relays on *other*
ports are left alone. If the port is still busy, v2 tells you the exact fix:

```bash
pkill -f bdix_relay.py   # then start it again
# or use another port:    python bdix_relay.py --port 8081
```

## PC (Windows/Mac/Linux)

- Install Python 3 + cloudflared (one exe from developers.cloudflare.com/cloudflare-one/connections/connect-apps)
- Same two steps: `python bdix_relay.py --key YOURKEY`, then `cloudflared tunnel --url http://127.0.0.1:8080`

## Alternative tunnel (no extra install, Termux only)

```bash
ssh -R 80:127.0.0.1:8080 nokey@localhost.run
```

Prints a `*.loca.lt` URL. cloudflared is more reliable; loca.lt sometimes shows
an interstitial page.

---

## Stream threads — AB Download Manager speeds while streaming

One BDIX connection caps at ~2-2.5 MB/s, but N parallel range connections
aggregate to the server's real ceiling (that's why AB Download Manager with 32
threads pulls 14 MB/s while Cloudstream's single connection gets 2-2.5). The
relay's `/par/N/<url>` lane gives playback the same effect:

- Cloudstream plays `http://127.0.0.1:8080/par/16/<encoded file url>`
- The relay range-probes the file, then serves the player `206 + Content-Range`
  (so seeking works) while 16 workers fetch 2 MiB slices in parallel and feed
  them in order — measured **8.1x** on a throttled link
- Local playback (same device) is **keyless**; only tunnel traffic needs the key

In Cloudstream (Wizstream v194 / Circle FTP v17): **Settings → Stream
threads** — flip the switch for the sources you want (e.g. Circle FTP on),
leave the others off, pick the thread count (16 is plenty for a 14 MB/s line)
and the relay address if not the default. Only direct files (.mp4/.mkv/…) are
threaded; HLS playlists pass through untouched. Takes effect on the next
episode load — no restart. Public installs without the relay see zero change
(default is OFF everywhere).

## Safety

- Relay binds to `127.0.0.1` only — reachable only through your tunnel
- Tunnel requests need the key (`?key=` / `X-Relay-Key` / proxy credentials) —
  anything else gets 403; same-device requests are keyless on purpose
- The tunnel URL is random and changes each run
- **Shut both sessions down (Ctrl+C) when debugging is done** — while it runs,
  key holders use your bandwidth

## What the assistant does with it

- Fetches live pages from the BDIX panel (list pages, player pages, search)
- Diffs against what the current provider parser expects
- Updates the provider, bumps the extension version, rebuilds
- You re-test on your device — no relay needed at runtime; Cloudstream fetches
  directly from your device as always (the relay is only for the sandbox
  debugging loop — and now, optionally, for parallel streaming)
