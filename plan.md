# Plan: landing-page-gen

## Milestones

| # | Milestone | Exit criterion | Status |
|---|---|---|---|
| 0 | Environment: repo, CLIs, hooks, skills, agents, docs | `uv run pytest` passes; `lp-corpus --help`, `lp-inject --help` print; skill and agents load; hook smoke test passes | done 2026-09-04; deferred: live hook check needs a fresh session (hooks load at start), `.env.example` blocked by the workspace deny rule |
| 1 | Corpus: discover pages, fetch, sectionize, DB, `similar`, `skeleton` | pytest on a saved HTML fixture; `similar --type hero` returns hero sections from other pages with media; unquoted step costs measured | in progress: `discover` done 2026-09-04, 218 pages in `corpus/pages.yaml` |
| 2 | Dry run of the loop | `--dry-run` produces priced `workflow.yaml` per slot, reviewer critiques, `lp-inject` fills placeholders, ledger has zero paid rows | todo |
| 3 | Live run, images only, ≤ 200 credits | every creative/thumbnail slot accepted or blocked with a reason; `dist/index.html` renders; spend matches ledger and `picsart_credits` delta | todo |
| 4 | Video and tuning | hero video via still-to-motion; rework loop tuned; rules in `prd.md` | todo |

Page inventory: `corpus/pages.yaml` (families: ai-models 82, tool 64, other 28,
compare-models 18, ai-tool 13, hub 13). Regenerate with
`uv run lp-corpus discover --seed <url>`. Which families to fetch is Areg's call.

## Decisions log

| Date | Decision | Why |
|---|---|---|
| 2026-09-04 | Corpus comes from scraping live picsart.com pages with Playwright. | Pages are CMS-driven and client-rendered; no internal export is assumed. |
| 2026-09-04 | Output is re-injection into the scraped HTML snapshot, not a template render. | Highest fidelity; every new page starts from a snapshot of an existing one. |
| 2026-09-04 | Manager is the main session; workers and reviewers are subagents. | Subagents cannot spawn subagents; SendMessage keeps a worker's context across rework rounds. |
| 2026-09-04 | Workers author `workflow.yaml` before executing; reviewers critique steps, and rework re-runs from step N. | Reuses upstream URLs; makes prompts and model choices reviewable, not just the final pixel. |
| 2026-09-04 | Defaults: `gemini-3-pro-image` (Nano Banana Pro) for images, `seedance-2.5` for video, `seedance-2.0-mini` as video draft tier. | Areg's brief; quoted costs in the `picsart-workflows` skill tool map. |
| 2026-09-04 | Paid calls only via connector `b05f6314`, only after a preflight, only inside an active run; enforced by `hooks/credit_guard.py`. | Wrong-connector and unquoted spend are the two mistakes worth making impossible. |
| 2026-09-04 | Roles `ui-screenshot`, `icon`, `decorative` are kept from source. | AI cannot faithfully render product UI; icons are brand assets. |
| 2026-09-04 | Page discovery is a plain-HTTP link crawl from hub pages (`discover.py`); no sitemap exists (`/sitemap.xml` returns the SPA shell). Pages are server-rendered (1.4 MB HTML with links), so Playwright is a fallback for `fetch`, not the default. | Faster, no browser; verify per page that sections are in the static HTML. |
| 2026-09-04 | Hooks run on system `python3`, stdlib only. | Fast start, no dependency on the project venv. |
| 2026-09-04 | Package uses a `src/` layout with one package and two console scripts. | Zero build-backend configuration with `uv_build`. |
| 2026-09-04 | Repo declares an empty `[tool.uv.workspace]`. | `~/pyproject.toml` is a uv workspace; without this, uv adopts the project as a member and puts `.venv` and `uv.lock` in the home directory. |

## Open questions

- The deny rule `Read(./**/.env.*)` also blocks writing `.env.example`; narrow it (e.g. `.env.local`) or create the file by hand.
- Which families from `corpus/pages.yaml` go into the corpus (all 218, or ai-models + compare-models + tool)?
- Worker model: `sonnet` (default now) or `opus`; decide on Milestone 3 reject rates.
- Video extend, edit and reframe costs are unquoted until Milestone 1.
