# Free corpus expansion: scraping plan

Status: plan, 2026-09-16. Nothing here is built yet.

## Goal

Grow the two *reference* tiers — `corpus/pool/` (licensed look-refs) and
`corpus/widened/` (licence-unknown look-refs) — with images and videos that
look like the 2740 corpus assets (2454 images, 286 videos), at $0 API spend.
The generatable corpus itself only grows via `lp-corpus fetch` on Picsart
pages; nothing scraped is ever wired into a node or injected. The isolation
guard already enforces the wire half; tier routing (below) is procedure.

Two separate problems, and only one of them is source-specific:

1. **Acquire candidates** — per source. Options 1–4 below.
2. **Match candidates to the corpus** — identical for every source. Build once.

The thing that used to cost money (`widen`'s per-image reverse search) is
problem 2. Every free option here replaces it with *local* similarity over a
big candidate pool, so the ranker is the load-bearing piece, not the scraper.

## Shared foundation (build first; every option depends on it)

- **F1 Thumbnails only.** Never download full-res. Every API below returns a
  thumbnail URL; store `url`, `licence`, `source`, `thumb_hash` and embed from
  a ≤256 px copy — the size `measure.py` already works at. 100k candidates ≈
  3 GB of thumbs, not 300 GB of originals.
- **F2 Ranker, two tiers.**
  - *Tier 0 (exists, zero new deps):* `pool.score` — dhash dedupe against
    corpus (`CORPUS_DUP=10`) and pool (`POOL_DUP=6`), 64-bin RGB histogram
    (`W_HIST=0.7`) + measured fields (`W_FIELDS=0.3`). Fine for Option 1
    volumes where the source is already on-style.
  - *Tier 1 (one new dependency, justified):* CLIP ViT-B/32 via `open_clip`
    on MPS. Embed the 2740 corpus assets once and every candidate; cosine
    nearest-neighbour in numpy (FAISS is unnecessary under ~1M). This gives
    **per-corpus-asset neighbours = a free `widen`**. Justification for the
    dependency: a histogram cannot express "same look, different subject";
    CLIP can, and Options 2–3 drown without it (1–5 % on-style at 100k+).
    ~50 img/s on M-series → 100k candidates in ~35 min. One `.npy` per source.
- **F3 Video = mid-frame.** `attrs.grab_frames` already produces one frame per
  corpus video (`corpus/frames/`, 286). Run the same hash/embedding on a
  candidate clip's poster frame. No new machinery.
- **F4 Tier routing.** Stock and CC sources → `pool/` (licensed). SERP and
  web discovery → `widened/` (look-only, never promoted). Same rule as today.

## Option 1 — Max out the free stock APIs  *(do first)*

**Sources:** Pexels photos + **Pexels videos**, Unsplash, **Pixabay photos +
videos**.

**Why first:** cleanest licences, highest style hit-rate (polished marketing
look), closes the video gap, and `stock.py`/`pool.py` are already ~60 % of
it — `stock.SEARCH` is the plug-in point.

**Free limits:** Pexels 200 req/hr, 20k/mo, `per_page` 80, same key for
`/videos/search`. Unsplash 50/hr demo → 5k/hr after production approval,
`per_page` 30, download-tracking required (`unsplash_track_download` exists).
Pixabay ~100 req/min, `per_page` 200, images + videos, ToS requires caching
results 24 h (store them; don't re-query).

**Yield:** the 15 families carry **99 `photography.search_terms`** in
`corpus/references/`. 99 terms × 5 pages × 80 ≈ **40k image candidates from
Pexels for ~500 requests** — 2.5 % of the 20k/mo free quota, so paginate
deeper if the dedupe still leaves room. Pixabay (`per_page` 200) roughly
doubles it; the two video endpoints give thousands of clips. Tier-0 ranker is
enough here.

**Work (~1 day):** `pixabay_search`, `pexels_video_search`,
`pixabay_video_search` in `stock.py` returning the existing normalised shape;
a `media=video` path in `pool.search` that hashes the poster frame via F3.

## Option 2 — Open-licence commons at volume  *(biggest raw yield)*

**Sources:** Flickr API (`license=` CC filter), Openverse API, Wikimedia
Commons API.

**Why:** effectively unlimited, per-item CC metadata, and Flickr holds a lot
of polished photography. Commons has video (webm). Openverse is one client
over ~800M items from many upstreams — best code-to-yield ratio of anything
here.

**Free limits:** Flickr 3600 req/hr, `per_page` 500. Openverse: anonymous is
tiny; a free registered key raises it to roughly 10k req/day, `page_size` up
to 500 *(verify)*. Commons: no key, ~1 req/s is polite, `generator=search`
with `filetype`.

**Yield:** 100k–1M candidates. Style hit-rate is low (Commons skews
documentary) so **this option needs the Tier-1 CLIP ranker** or the sheets
become unreviewable.

**Work (~1 day):** three thin clients in `stock.py`. Start with Openverse.

## Option 3 — Scraping Robot free tier → widened tier  *(web-wide look-refs)*

**Source:** Scraping Robot's Google Images SERP module, **5,000 scrapes/mo
free**, then $0.0018/scrape pay-as-you-go, credits don't expire (verified
2026-09-16). Keyword = the family's search terms.

**Why:** the only free way to discover neighbours *beyond* stock sites. It
produces exactly what `widen` produces today — licence-unknown look-refs —
so it slots into the existing `corpus/widened/<family>.yaml` format.

**What it is not:** reverse-image. Scraping Robot has no Lens/search-by-image
module (its Google module is keyword SERP). This is keyword discovery plus
local CLIP ranking. Don't bodge Lens through its generic JS module — the
rendered HTML is unstructured and fragile; Option 4 is the clean version.

**Yield:** 5k SERPs × ~50 image URLs ≈ 250k URLs/mo → thumb + CLIP → keep
top-N per family.

**Work (~½ day):** a `scrapingrobot` backend in `widen.py`.

**Rules:** widened tier only. Never pool, never wired. Google-ToS-gray, but
that risk sits with the vendor; the results carry no licence so they can't be
promoted regardless.

## Option 4 — Rationed true reverse-image  *(precision drip, zero code)*

**Sources:** Google Vision web-detection, **1,000 free/mo** — already built
as `widen --backend vision-web`, just needs `GOOGLE_VISION_API_KEY`. Plus
Apify's Lens actors on its **$5/mo free platform credit** *(verify per-result
cost)*.

**Why:** the only per-image neighbours of your *actual* assets. Highest
precision, lowest volume.

**Yield:** ~1,000 corpus assets/mo on Vision → the full 2740 in three
months at $0. Apify adds a few hundred to a couple thousand Lens lookups/mo.

**Use it for two things:** the widened tier, and as **ground truth to tune
the CLIP ranker's threshold** — Vision's neighbours tell you where to cut
Options 2–3.

**Work:** none for Vision (set the key, put it on a monthly cron). Apify is a
small backend if the credit maths works out.

## Where Scrapy fits

Only for scrape-friendly targets that have *no* API: CC0 stock sites with
sitemaps (Burst, StockSnap, Kaboompics, Reshot). Moderate yield, high style
fit. Do **not** point it at Google or at Pexels/Unsplash HTML — strictly worse
than their free APIs (no licence metadata, fragile, against ToS). Add it after
Options 1–2 only if breadth is still short.

## Recommended sequence

| When | Do | Why |
|---|---|---|
| Week 1 | F1–F3 + **Option 1** | immediate, clean, closes the video gap, mostly built |
| Week 2 | **Option 4** Vision on a monthly cron | free, zero code; its neighbours tune the CLIP cut |
| Week 3 | **Option 2** Openverse → Flickr | volume, once the ranker is trusted |
| Later | **Option 3** | web-wide look-refs if stock+CC still look narrow |

## Verify before relying on these numbers

- Openverse registered daily quota and max `page_size`
- Apify Lens actor per-result cost against the $5 credit
- Pixabay current per-key rate and the 24 h cache rule
- Unsplash production-tier approval requirements

## Budget

$0 in API spend across all four. Real costs: ~3 days of code (Options 1–3),
one new dependency (`open_clip` + torch) if Tier-1 is built, ~3 GB of thumbs
per 100k candidates, and a one-off ~35 min embedding pass per 100k.
