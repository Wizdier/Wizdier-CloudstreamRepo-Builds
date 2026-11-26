# AGENTS.md — the Builds lane's agent protocol

> Signed and maintained by **Agent One** (2026-11-26, the v336 session).
> This is the RELEASE LANE — the artifacts here are what every user's app
> downloads. Treat every commit as a deployment.

## What lives here
- `<Name>.cs3` — the compiled extensions (Wizstream is the main carrier)
- `plugins.json` — the index the app reads (url / version / fileSize / fileHash)
- `repo.json` + `icons/` — the repository identity
- `.nojekyll` — keep it

## The laws
1. **Nothing is hand-edited here.** Artifacts arrive through
   `tools/stage.py` (from a verified local build) or the source repo's CI
   (`Publish build <sha>`). A hand-edited .cs3 is a deployment incident.
2. **Stage only what changed.** Every other module ships byte-identical
   at its shipped version (the dex_audit byte-identity gate enforces it).
3. **The anti-regression guard**: CI refuses to publish a Wizstream
   version older than the one already served — never bypass it.
4. **plugins.json is derived** — stage.py regenerates the entry
   (version/fileSize/fileHash) from the staged bytes; never hand-edit it.
5. The full working protocol (fetch first, the handoff, the ship
   discipline, the cluster memory, signing) lives in the SOURCE repo's
   AGENTS.md — it governs this lane too. Sign as your seat
   (Agent One / Two / Three / ...).

## The Firebase
`wizstream-activation` (telemetry/activation) and `wizdier-ai-cluster`
(the agents' memory store — agents/<AgentSeat>/projects/...; the database
id is the NAMED `default`). The security rules for both live in the
source repo's tools/ and release through the Firebase console.
