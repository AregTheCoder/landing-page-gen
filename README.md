# landing-page-gen

Agentic media production for a whole Picsart landing page. A corpus tool
scrapes existing pages into a sectioned Markdown database; a manager agent
splits a new page's skeleton into sections and hands each to a worker agent
that designs and runs a Picsart workflow (generate, refine, edit, upscale,
animate) for that section's media; a reviewer compares the result and the
workflow to similar sections in the corpus; the chosen media is injected back
into the page's HTML snapshot.

Status: Milestone 1 (corpus) done; Milestone 2 (dry run of the loop) next.
See `plan.md`.

## Setup

```
uv sync
uv run playwright install chromium
uv run pytest
```

## Build the corpus

```
uv run lp-corpus discover --seed https://picsart.com/ai-image-generator/   # -> corpus/pages.yaml
uv run lp-corpus fetch --family tool --family ai-models --sectionize        # snapshots + index
uv run lp-corpus fetch /persona/                                            # one page
uv run lp-corpus sectionize --all                                           # re-index
uv run lp-corpus skeleton ai-image-generator --out runs/demo/skeleton.md
uv run lp-corpus similar --type hero --query "AI Image Generator ..." \
    --exclude ai-image-generator -k 3 --out runs/demo/examples
```

`fetch` reads the server-rendered HTML, reassembles the React streaming
segments in Python, and opens the page once in Chromium for a full-page
screenshot and the rendered size of every image and video. `sectionize`
splits `<main>` into typed sections, stamps every text and media node with a
`data-lp*` id in `page.html`, and indexes everything in `corpus/corpus.db`
(SQLite + FTS5). `skeleton` writes the editable page description; `similar`
pulls example sections of one type from other pages, with their media as PNG.

## skeleton.md

```markdown
---
page: ai-image-generator
source: https://picsart.com/ai-image-generator/
snapshot: corpus/pages/ai-image-generator/page.html
brand: Picsart
audience: ''
defaults: {image_model: gemini-3-pro-image, video_model: seedance-2.5, video_draft: seedance-2.0-mini}
budget: {run_credits: 300, image_slot: 20, video_slot: 60}
notes: ''
---

## S04 feature-callout

- t1 h2: Access 59 AI image models on one platform
- t2 p: Every AI image model has a strength. ...
- t3 a: Try now -> https://picsart.com/ai-playground/

```slot
id: S04-m1
kind: video
role: creative          # creative | thumbnail | ui-screenshot | icon | decorative
size: 539x539           # rendered box at 1440 px; the slot to fill
aspect: '1:1'
natural: 1600x1600
duration_s: 8.4
src: https://cdn-cms-uploads.picsart.com/cms-uploads/....webm
```
> annotation: TODO what this video should show
```

Roles are guessed by `sectionize` and edited by hand; `ui-screenshot`, `icon`
and `decorative` slots are kept from the source. `slots.json` next to the
skeleton maps every `Sxx-mN` and `Sxx-tN` id to its stamp in the snapshot.

## Layout

```
src/landing_page_gen/corpus/   lp-corpus: discover, snapshot (fetch), sectionize, skeleton, similar, db
src/landing_page_gen/inject/   lp-inject: media + text re-injection into the snapshot (Milestone 2)
hooks/                         Claude Code hooks: credit guard, ledger, worker contract
tests/                         pytest; tests/fixtures/streamed.html is a saved streamed-SSR page
corpus/pages.yaml              page inventory from `discover`
corpus/pages/<slug>/           raw.html, page.html (stamped), page.png, render.json, meta.json, sections.md
corpus/corpus.db               pages, sections, texts, media, sections_fts (gitignored, rebuildable)
runs/<run>/                    skeleton.md, slots.json, sections/Sxx/, ledger.jsonl, page.md, dist/  (gitignored)
```

Only `sections.md` and `meta.json` under `corpus/pages/` are committed; the
rest is rebuilt by `lp-corpus fetch --all --sectionize` (about 12 s per page).

The agent side (skills `build-landing-page`, `picsart-workflows`; agents
`section-worker`, `section-reviewer`; hook wiring) lives in the workspace
`.claude/` folder one level up.

Output is a self-contained snapshot of the page with new media, not the
production Next.js page.
