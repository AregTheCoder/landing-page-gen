# landing-page-gen

Agentic media production for a whole Picsart landing page. A corpus tool
scrapes existing pages into a sectioned Markdown database; a manager agent
splits a new page's skeleton into sections and hands each to a worker agent
that designs and runs a Picsart workflow (generate, refine, edit, upscale,
animate) for that section's media; a reviewer compares the result and the
workflow to similar sections in the corpus; the chosen media is injected back
into the page's HTML snapshot.

Status: Milestone 0 (environment) in progress. See `plan.md`.

## Setup

```
uv sync
uv run playwright install chromium
uv run pytest
```

## Layout

```
src/landing_page_gen/corpus/   lp-corpus: fetch, sectionize, skeleton, similar
src/landing_page_gen/inject/   lp-inject: media + text re-injection into the snapshot
hooks/                         Claude Code hooks: credit guard, ledger, worker contract
tests/
corpus/                        snapshots and corpus.db (gitignored binaries)
runs/<run>/                    skeleton.md, sections/Sxx/, ledger.jsonl, page.md, dist/  (gitignored)
```

The agent side (skills `build-landing-page`, `picsart-workflows`; agents
`section-worker`, `section-reviewer`; hook wiring) lives in the workspace
`.claude/` folder one level up.

Output is a self-contained snapshot of the page with new media, not the
production Next.js page.
