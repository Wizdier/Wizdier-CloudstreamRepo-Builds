# BDIX Relay Setup — give the sandbox live access to your BDIX

**Problem:** BDIX panels (Circleftp, CineplexBD, etc.) are only reachable from
inside Bangladesh. The sandbox sits in Hong Kong and cannot see them, so when a
BDIX site changes its layout, the provider code can't be debugged remotely.

**Fix:** Your phone/PC is already authorized on your ISP's BDIX routes. Run a
tiny relay on it and expose it through a free tunnel. The sandbox then fetches
BDIX pages through *your* connection — same loop used for the Movy/Bingr
updates. No paid service involved, nothing cracked.

---

## Android (Termux) — 5 minutes

1. Install **Termux** (from F-Droid: f-droid.org, the Play Store build is outdated)
2. In Termux:

```bash
pkg update -y && pkg install python cloudflared
# copy bdix_relay.py into Termux storage, then:
python bdix_relay.py
```

3. It prints a **key** (write it down). Leave this session running.
4. Open a **second Termux session** (swipe from left → New Session):

```bash
cloudflared tunnel --url http://127.0.0.1:8080
```

5. It prints a public URL like `https://random-words.trycloudflare.com`
6. **Send the sandbox assistant: that URL + the key.** Done.

## PC (Windows/Mac/Linux)

- Install Python 3 + cloudflared (one exe from developers.cloudflare.com/cloudflare-one/connections/connect-apps)
- Same two steps: `python bdix_relay.py`, then `cloudflared tunnel --url http://127.0.0.1:8080`

## Alternative tunnel (no extra install, Termux only)

```bash
ssh -R 80:127.0.0.1:8080 nokey@localhost.run
```

Prints a `*.loca.lt` URL. cloudflared is more reliable; loca.lt sometimes shows
an interstitial page.

---

## Safety

- Relay binds to `127.0.0.1` only — reachable only through your tunnel
- Every request needs the key — anything else gets 403
- The tunnel URL is random and changes each run
- **Shut both sessions down (Ctrl+C) when debugging is done** — while it runs,
  key holders use your bandwidth

## What the assistant does with it

- Fetches live pages from the BDIX panel (list pages, player pages, search)
- Diffs against what the current provider parser expects
- Updates the provider, bumps the extension version, rebuilds
- You re-test on your device — no relay needed at runtime; Cloudstream fetches
  directly from your device as always
