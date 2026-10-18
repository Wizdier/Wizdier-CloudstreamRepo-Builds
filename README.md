# Wizdier CloudStream Repository

> **Movies, Series & Anime for CloudStream — built for Bangladesh.**

[![CloudStream](https://img.shields.io/badge/CloudStream-extension-blueviolet?logo=android)](https://github.com/recloudstream/cloudstream)
[![Extensions](https://img.shields.io/badge/extensions-8-success)](#-whats-inside)
[![License](https://img.shields.io/badge/license-GPL--3.0-blue)](LICENSE)

---

## Installation

1. Install [**CloudStream**](https://github.com/recloudstream/cloudstream/releases) on your Android phone, TV or box.
2. Open **Settings → Extensions → Add repository** and paste:

   ```
   https://raw.githubusercontent.com/Wizdier/Wizdier-CloudstreamRepo-Builds/main/repo.json
   ```
   Or, Use **ShortCode**   
   ```
   wizrepo
   ``` 
3. Buy the subscription packs and enjoy streaming.
---

## What you get
| Category | Available services |
| :--- | :--- |
| **BDIX** | **CircleFTP**, **CineplexBD**, **CTGMovies**, **FTPBD**, **FMFTP**, **Mediaserver**, **FlixHub** |
| **Web Servers** | **Bingr**, **PirateXPlay**, **PirateXPlay Max**, **Movy**, **MultiMovies**, **Cinejoy**|
| **Anime Servers** | **AnimeX**, **AniZone**, **AniHQ** |
| **Subtitles** | **Wyzie Subs** integration adds subtitles |
| **Ratings** | **MDBList** integration shows **IMDb**, **Rotten Tomatoes**, **Metacritic**, and **MAL** scores together on the page. |

---

## FAQ

**Do I need a BDIX connection?**
No, but it's the point of this repo. Without BDIX the Bangladeshi servers
won't reach and you'll fall back to the web sources.

**Nothing plays / no links found.**
Check you're on your BDIX ISP, then open Settings and confirm the sources
aren't switched off. If one server is down, another usually has the title.

**Can I stop fetching languages I don't want?**
Yes — Settings → Playback → "Fetch only these languages". Uncheck anything
you never watch (e.g. keep only English + Bengali) and every language-row
source (Bingr, Movy-Austin, Rareanimes) skips those rows before fetching
them — zero wasted requests. Unlabeled/Original tracks are always kept.

**Can I use only some of a source's servers?**
Yes — Settings → the source's section → expand "Servers" (Bingr: Orion,
Polaris, Bastion…; Movy: the city providers; SceneLumen: the five routes).
Unwanted servers are never contacted again. Applies live at the next link
load — no restart needed.

**Why do some AbyssPlayer rows say “(no-seek)”?**
Those 720p/1080p files sit behind a CDN that cannot serve range requests —
they play fine from the start, but skipping may fail. Rows without the tag
seek normally. (The site's own player has the same limitation.)

**Why do I need my own API keys?**
Wyzie and MDBList issue free per-user keys (1,000 requests/day each) and
their terms don't allow shipping a shared key inside an app. Both features
are entirely optional.

**Is this legal?**
These extensions only *index* publicly reachable servers — no content is
hosted, uploaded or owned here. You are responsible for what you access.

---

## For developers

Kotlin, built with the [recloudstream](https://github.com/recloudstream) Gradle plugin (AGP 8.7.3 / Kotlin 2.3.0, `compileSdk 35`).

```bash
./gradlew make makePluginsJson   # builds all 8 .cs3 packages + plugins.json
./gradlew :Wizstream:make        # builds just Wizstream/build/Wizstream.cs3
```

`WizstreamSources.kt` holds the shared link-resolving engine (one
`SourceResolver` per site, fanned out in parallel per episode request);
`WizstreamAnimeSources.kt` the anime-web resolvers. Version history lives
compactly in [CHANGELOG.md](CHANGELOG.md); full detail in the git log.

---

## License

Released under the [GNU GPL v3](LICENSE), the same license as the
[CloudStream](https://github.com/recloudstream/cloudstream) app and its
extension ecosystem. Each plugin links against the CloudStream API, so the
corresponding source (and this notice) must travel with any redistribution.

---

<sub>Not affiliated with CloudStream, TMDB, AniList, MDBList or any listed
site.</sub>
