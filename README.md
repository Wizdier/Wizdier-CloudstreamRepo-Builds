# Wizdier-CloudstreamRepo-Builds

Compiled CloudStream extensions — the **builds** distribution point.

* Source code: **private** (not published here or anywhere).
* The extensions are **locked to their owner** — installing them from this
  repository works, but content only loads after activation on the device.
* Supported app: [CloudStream](https://github.com/recloudstream/cloudstream)

## Add to CloudStream

1. CloudStream → Settings → Extensions → **Add repository**
2. Paste:

```
https://raw.githubusercontent.com/Wizdier/Wizdier-CloudstreamRepo-Builds/main/repo.json
```

## Contents

| Plugin | What it is |
|---|---|
| Wizstream | TMDB + AniList multi-source (movies, series, anime) |
| CTGMovies | ctgmovies.com |
| Cineplex BD | cineplexbd.net |
| Circle FTP | new.circleftp.net |
| FM FTP | fmftp.net |
| FlixHub | flixhub.net |
| Mediaserver | BDIX media server |

Each release is published in `plugins.json` with a SHA-256 `fileHash`; the
app verifies every download against it.
