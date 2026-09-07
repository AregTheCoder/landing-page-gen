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
uv run lp-corpus skeleton ai-image-generator --out runs/<run>/skeleton.md   # + slots.json
uv run lp-corpus similar --type hero --style full-bleed --query "<headline and body>" \
    --exclude ai-image-generator --exclude-asset <8hex> -k 3 --out runs/<run>/sections/S01/examples
uv run lp-compose --describe before-after                # panels of a style family and their generate ratios
uv run lp-compose runs/<run>/sections/S07/compose-S07-m1.yaml --out runs/<run>/sections/S07/steps/S07-m1-3-1.png
uv run lp-inject runs/<run>
```

Slugs are the URL path with `/` as `--` (`ai-models--flux-3`). `fetch` needs
Chromium (`uv run playwright install chromium`); `--no-render` skips it and
loses screenshot and slot sizes. Snapshots carry their media in `media/`;
the served URL is kept on each element as `data-lp-src`.

## Test

`uv run pytest`. Hooks are tested as subprocesses on the system python3.

## Rules

- A worker writes `workflow.yaml` (every step, model, params, gate) before
  running anything, and preflights every paid step. `result.md` follows the
  output contract in the `build-landing-page` skill.
- Paid calls only on the `b05f6314` connector and only after a preflight.
  Inside an active run (`runs/current` exists) the `hooks/` scripts enforce
  this, deny dry-run and over-cap calls, and log every URL to
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
