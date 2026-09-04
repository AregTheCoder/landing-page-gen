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
   `skeleton.md` for a page, `similar` excerpts for briefs.
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
uv run lp-corpus sectionize --all                        # re-index after sectionize.py changes
uv run lp-corpus skeleton ai-image-generator --out runs/<run>/skeleton.md   # + slots.json
uv run lp-corpus similar --type hero --query "<headline and body>" \
    --exclude ai-image-generator -k 3 --out runs/<run>/sections/S01/examples
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
- Paid calls only on the `b05f6314` connector, only inside an active run
  (`runs/current`), only after a preflight. The `hooks/` scripts enforce this
  and log every URL to `ledger.jsonl`.
- Roles `ui-screenshot`, `icon`, `decorative` are never generated.
- Images carry no text; page copy is HTML.
- Video: draft on `seedance-2.0-mini`, final on `seedance-2.5`, audio off.
- A rule learned goes into `prd.md`; the decision behind it into `plan.md`.
