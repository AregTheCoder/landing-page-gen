# Scrape queue — 2026-09-17

A curated batch of **204 new Picsart landing pages** to fetch into the corpus,
prepared 2026-09-17. `queue.txt` holds the URLs, one per line.

## How the queue was found (the discovery method)

Bare `lp-corpus discover` finds **nothing new** — Picsart's hub pages are
client-rendered, so there are no links to expand. The authoritative source of
landing pages is the **sitemap**, declared in `https://picsart.com/robots.txt`:

- landing pages: `https://picsart.com/landings/landings.xml`  ← this one
- (also: miniapp-shell, blog, fonts, colors, general-library sitemaps)

`landings.xml` listed **535** landing pages. Diffed against `corpus/pages.yaml`
(272 entries): **214 already scraped, 321 new.** The 321 were curated down to
**204** by dropping non-creative genres (corporate/legal/pricing/careers, `/sizes/`,
`/events/`, `/compare/` competitor pages, `/solutions/`, `/industries/`, `/flow/`,
`/apps/`, playground/agents/earn). Kept: all new `/ai-models/` (25),
`/compare-models/` (9), genuine tools + sub-pages (110), and `/design/` template
pages (60). Areg chose "everything curated (204)".

## To run the scrape (after a /clear)

```bash
cd /Users/areg/PicsArt_Projects/landing-page-gen
uv run playwright install chromium              # if not already installed
uv run lp-corpus fetch $(cat research/scrape-2026-09-17/queue.txt) --sectionize
uv run lp-corpus media --all                    # download any media fetch left as links
uv run lp-corpus attrs                          # measure the new assets
uv run lp-corpus sheets                          # then /label-corpus for the new semantic fields
uv run lp-corpus styles --from-attrs && uv run lp-corpus taxonomy && uv run lp-corpus organise
uv run lp-corpus doctor                          # GATE: must be 0 errors before building on it
```

`fetch` without `--force` skips pages that already have a snapshot, so re-running
is safe. Expect a multi-hour fetch and a few GB of media. A page that serves only
a client-side app shell is recorded `shell: true` in its `meta.json` and gets no
snapshot — that is normal, not a failure.

Status: **queued, not yet fetched** as of 2026-09-17.
