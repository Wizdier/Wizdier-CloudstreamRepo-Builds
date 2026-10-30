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
3. Buy the subscription packs from the discord server and enjoy streaming.
[![Discord](https://invidget.switchblade.xyz/xcYWfbhTuV)](https://discord.gg/xcYWfbhTuV)

---

## What you get
| Category | Available services |
| :--- | :--- |
| **BDIX** | **CircleFTP**, **CineplexBD**, **CTGMovies**, **FTPBD**, **FMFTP**, **Mediaserver**, **FlixHub** |
| **Web Servers** | **Bingr**, **PirateXPlay**, **PirateXPlay Max**, **Movy**, **MultiMovies**, **Cinejoy**|
| **Anime Servers** | **AnimeX**, **AniZone**, **AniHQ** |
| **Subtitles** | **Wyzie Subs** integration adds subtitles |
| **Ratings** | **MDBList** integration shows **IMDb**, **Rotten Tomatoes**, **Metacritic**, and **MAL** scores together on the page. |
| **Skip Times** | **IntroDB** / **TheIntroDB** integration fetches community skip stamps for intros, recaps and outros on supported shows and movies. |

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

<sub>Not affiliated with CloudStream, TMDB, AniList, MDBList or any listed
site.</sub>
