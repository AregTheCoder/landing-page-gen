# landing-page-gen

Generates every image and video slot of a Picsart landing page. Workers
author and run multi-step **Picsart workflows** per slot; a manager reviews
them against a corpus of existing Picsart pages; the chosen media is injected
back into the page's HTML snapshot. Workspace rules live in `../CLAUDE.md`.

Read `plan.md` first: milestones, status, decisions log. `prd.md` holds the
quality rules, one line per lesson learned. Skills, agents and hook wiring
are in `.claude/` here; start Claude Code in this folder.

## Three parts

1. `lp-corpus` (deterministic, outside the agent loop): Playwright snapshot →
   typed sections as Markdown → `corpus/corpus.db` (SQLite + FTS5) →
   `skeleton.md` for a page, `similar` excerpts for briefs. Asset attributes
   are measured from the pixels and completed from labelling contact sheets
   (`/label-corpus`); no vision API is involved.
2. `/build-landing-page runs/<run>/skeleton.md [--dry-run]`: the manager
   skill. Spawns `section-worker` agents (hero first, then the rest in
   parallel), reviews each with `section-reviewer`, sends rework via
   SendMessage, writes `page.md` and `report.md`.
3. `lp-inject runs/<run>`: writes chosen media and changed text into the
   snapshot → `runs/<run>/dist/index.html`.

`/collect-references`: one `reference-collector` agent per style family
finds Pexels/Unsplash photos and creators that match the family's
photography → `corpus/references/<family>.yaml` and a **References** line in
`style-families.md`; `--pages` does the same per page. No paid calls.

`/review-pool [family]`: one subagent per contact sheet keeps or drops the
stock pool's ranked candidates (`corpus/pool/<family>.yaml`), moving a good
photo to a better family with `best_family`, then `pool calibrate` turns the
answers into the auto-drop threshold the next search obeys. Free-tier APIs
only, metered in code; no paid calls.

## Run

```
uv run lp-corpus discover --seed <url>                   # -> corpus/pages.yaml
uv run lp-corpus fetch --family tool --sectionize        # or: fetch /ai-image-generator/ ...
uv run lp-corpus media --all                             # download media for snapshots fetched --no-media
uv run lp-corpus sectionize --all                        # re-index after sectionize.py changes; re-applies corpus/styles.yaml
uv run lp-corpus attrs [--dry-run|--limit N]             # measure every distinct asset (pixels only) -> corpus/attributes.yaml, media.attrs/style
uv run lp-corpus sheets [--skip-resolved]                 # assets still missing a semantic field -> corpus/labels/*.png + manifests + README
uv run lp-corpus labels                                   # merge every corpus/labels/*.answers.yaml (validated) into the attributes
uv run lp-corpus taxonomy --out corpus/taxonomy           # cross-tab + contact sheets from attributes.yaml -> report.md
uv run lp-corpus styles --from-attrs                      # derive corpus/styles.yaml from the attributes through the rule table
uv run lp-corpus organise [--dry-run]                     # rebuild library/: a browsable hardlink tree (page dossiers; assets by model -> art_style -> structure) + a Markdown sidecar per asset
uv run lp-corpus doctor                                   # verify the corpus conforms to metastructure.md (snapshots indexed, assets measured, styles synced + mirrored, labels in-enum, pool well-formed); exits non-zero on an ERROR. Run before and after a scrape.
uv run lp-corpus skeleton ai-image-generator --out runs/<run>/skeleton.md   # + slots.json
uv run lp-corpus similar --type hero --style full-bleed --query "<headline and body>" \
    --exclude ai-image-generator --exclude-asset <8hex> -k 3 --out runs/<run>/sections/S01/examples
uv run lp-corpus widen template-mockup [--exact] [--limit 5]  # reverse-image neighbours of the family's assets -> corpus/widened/<family>.yaml (SERPAPI_KEY or GOOGLE_VISION_API_KEY)
uv run lp-corpus similar ... --style template-mockup --widen 2  # + two neighbours in examples/ as w<n>-widened.md, look only
uv run lp-corpus pool search full-bleed [--pages 2] [--dry-run]  # Pexels/Unsplash/Pixabay by the family's search_terms, metered and cached, pHash-deduped vs corpus+pool, ranked -> corpus/pool/<family>.yaml (PEXELS_API_KEY, UNSPLASH_ACCESS_KEY, PIXABAY_API_KEY; a missing key skips that platform)
uv run lp-corpus pool quota                                # how many candidates each family is owed, inversely to the corpus it already has
uv run lp-corpus pool embed [--describe] [--refresh]       # build the CLIP cache the clip ranker reads (needs `uv sync --extra embed`)
uv run lp-corpus pool sheets full-bleed && uv run lp-corpus pool labels  # keep/drop from contact sheets (/review-pool), like the label sheets
uv run lp-corpus pool calibrate full-bleed --write [--family-check]  # answers -> auto-drop threshold at 95% recall + per-term keep rates
uv run lp-corpus similar ... --style full-bleed --pool 2 --seed <run>  # + two kept licensed images as p<n>-pool.md, rotated per run
uv run lp-compose --describe before-after                # panels of a style family and their generate ratios
uv run lp-compose runs/<run>/sections/S07/compose-S07-m1.yaml --out runs/<run>/sections/S07/steps/S07-m1-3-1.png
uv run lp-flow templates --family template-mockup --device applied-mockup   # gallery templates that fit, from corpus/flow-templates.yaml
uv run lp-flow check runs/<run>/sections/S07/workflow.yaml                  # does the board wire START -> nodes -> END
uv run lp-flow sheet runs/<run>/sections/S07/workflow.yaml                  # -> flow.md, the node sheet for the Flow canvas
uv run lp-inject runs/<run>
```

Slugs are the URL path with `/` as `--` (`ai-models--flux-3`). `fetch` needs
Chromium (`uv run playwright install chromium`); `--no-render` skips it and
loses screenshot and slot sizes. Snapshots carry their media in `media/`;
the served URL is kept on each element as `data-lp-src`.

## Test

`uv run pytest`. Hooks are tested as subprocesses on the system python3.

## Rules

- A worker's `workflow.yaml` is a Picsart Flow board: START, nodes (one
  Flow kind, one engine, one model, `in:` wiring, a gate each), END. Blank
  board by default; a gallery template from `corpus/flow-templates.yaml`
  only when it fits the family and device, covers every panel and moves no
  invariant. Written whole and `lp-flow check`ed before anything runs, every
  paid node preflighted, `flow.md` rendered after. `result.md` follows the
  output contract in the `build-landing-page` skill.
- Pool traffic is free-tier only and metered in code (`apiclient`/`ledger`):
  the `hooks/` guards match `picsart_*` MCP names and cannot see an
  `lp-corpus` HTTP call. `--dry-run` costs a sweep before it runs; a re-run
  inside the cache TTL costs zero requests. Zero credits, zero spend.
- Corpus assets, stock references and widened neighbours **are** read for the
  look and curated into a worker's `examples/` exactly as the workflow rules
  say; they are never wired into a node (`imageUrls`, `startFrame`, `image`).
- **Previously generated media never impacts a new image.** No earlier run's
  outputs (`runs/*/steps`, `runs/*/dist`) and nothing from Picsart Drive is
  read as a reference *or* wired into a node — a new generation is seeded only
  by the corpus/stock look and the run's own in-run nodes. The read half is
  procedure: never point curation, `similar`, or a brief at `runs/*` or Drive.
  The wire half is enforced by `hooks/isolation_guard.py` — a paid call that
  references any URL not in the current run's `ledger.jsonl` is denied (corpus,
  Drive, prior-run, or a `media_upload`-laundered URL); corpus is read-only so
  it is never wired regardless.
- Paid calls only on the `b05f6314` connector and only after a preflight.
  Inside an active run (`runs/current` exists) the `hooks/` scripts enforce
  this, deny dry-run, over-cap and cross-run calls, and log every URL to
  `ledger.jsonl`; outside a run the guard allows everything.
- Roles `ui-screenshot`, `icon`, `decorative` are never generated.
- Text inside an image is generated, but only the exact strings the
  skeleton's `> text:` line names for that slot (the manager derives them
  from the section copy and the family's **Text** line); page copy stays
  HTML. Non-text chrome (tiles, brackets, checkerboard) and geometry-bound
  labels (Before/After pills, size labels, chips) come from `lp-compose`,
  never from a model. Every generated slot has a style family
  (`picsart-workflows/style-families.md`).
- Video: draft on `seedance-2.0-mini`, final on `seedance-2.5`, audio off.
- Attributes are measured, then labelled from the sheets: `attrs` writes only
  what the pixels settle, `sheets` asks for the rest, `labels` validates
  against the enums and drops anything outside them. Never hand-edit
  `corpus/attributes.yaml`. The enums in `attrs.FIELDS`,
  `picsart-workflows/style-families.md` and `tests/test_styles.py` are pinned
  to each other and change together.
- A rule learned goes into `prd.md`; the decision behind it into `plan.md`.
