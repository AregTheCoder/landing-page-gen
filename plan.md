# Plan: landing-page-gen

## Milestones

| # | Milestone | Exit criterion | Status |
|---|---|---|---|
| 0 | Environment: repo, CLIs, hooks, skills, agents, docs | `uv run pytest` passes; `lp-corpus --help`, `lp-inject --help` print; skill and agents load; hook smoke test passes | done 2026-09-04; deferred: live hook check needs a fresh session (hooks load at start), `.env.example` blocked by the workspace deny rule |
| 1 | Corpus: discover pages, fetch, sectionize, DB, `similar`, `skeleton` | pytest on a saved HTML fixture; `similar --type hero` returns hero sections from other pages with media; unquoted step costs measured | done 2026-09-04: 19 tests on `tests/fixtures/streamed.html`; `similar` returns one hero per page with PNG media; extend/edit/reframe quoted in `tool-map.md`; corpus = 199 pages: the 205 non-hub paths in `pages.yaml` minus 6 that serve the client-side app shell (`/ai-agent/`, `/ai-avatar/`, `/ai-enhance/`, `/ai-models/midjourney/`, `/ai-storyline/`, `/batch/`; recorded as `shell` in meta.json), built by `lp-corpus fetch --family ... --sectionize` and `lp-corpus media --all` |
| 2 | Dry run of the loop | `--dry-run` produces priced `workflow.yaml` per slot, reviewer critiques, `lp-inject` fills placeholders, ledger has zero paid rows | done 2026-09-04 on `runs/dry-1` (resize-image, 6 sections, 14 slots): every slot has a preflighted `workflow.yaml`, each section reviewed (5 of 6 needed one rework round), `dist/index.html` renders with 14 labelled placeholders, ledger has 0 paid rows; the manager procedure was run by the main session step by step, not via `/build-landing-page` |
| 3 | Live run, images only, ≤ 200 credits | every creative/thumbnail slot accepted or blocked with a reason; `dist/index.html` renders; spend matches ledger and `picsart_credits` delta | todo |
| 4 | Video and tuning | hero video via still-to-motion; rework loop tuned; rules in `prd.md` | todo |

Page inventory: `corpus/pages.yaml` (families: ai-models 82, tool 64, other 28,
compare-models 18, ai-tool 13, hub 13). Regenerate with
`uv run lp-corpus discover --seed <url>`. The corpus holds every family but
`hub` (catalog pages, no campaign media); add them with `fetch --family hub`.
Snapshots live in `corpus/pages/<slug>/` (raw.html, page.html with `data-lp*`
stamps and local `media/` links, media/, page.png, render.json, meta.json,
sections.md); only sections.md and meta.json are committed. The 199
snapshots take 4 GB on disk (media, full-page screenshots, raw HTML); 9 of
4551 media nodes point at assets the CDN no longer serves (404) and keep
their absolute URL.

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
| 2026-09-04 | Dry run findings: workers plan well but copy the hero's composition into every section unless told that anchored means light and palette only; every first-round review asked for prompt changes, none for pattern changes; the rework loop via SendMessage worked (worker context intact, one round each); small thumbnails go to `gemini-3.1-flash-image` at a native ratio (3 credits) instead of the pro model cropped. | Lessons are in `prd.md`; the brief template should carry the anchored rule so reviewers stop repeating it. |
| 2026-09-04 | `check_result.py` takes the section from the first `sections/Sxx` path in the worker transcript (its assignment), not the last. | In the dry run a worker that listed the run folder was blocked on stop for another worker's section (S06 asked to finish S11). |
| 2026-09-04 | Skills, agents and hook wiring moved from the workspace `.claude/` into this repo's `.claude/`; hook commands are cwd-relative (`python3 hooks/...`) and `_ledger.current_run()` resolves `runs/current` from the hook file's own location. | Claude Code loaded this repo's `.claude/settings.json` (hooks fired live), but `$CLAUDE_PROJECT_DIR` resolves to the workspace folder, so anything path-dependent must not use it. The workspace copies had no version control. |
| 2026-09-04 | `fetch` gets the HTML by plain HTTP and reassembles the React streaming segments in Python (`<template id="P:x">` and Suspense `B:x` boundaries swapped for the hidden `<div id="S:x">` chunks, as the inline `$RC` scripts would). Playwright still runs once per page, for the full-page screenshot and the rendered box of every image and video. | The reassembled `<main>` was checked identical to the rendered DOM (31 images, 5 videos on `/ai-image-generator/`); slot sizes only exist after layout, so geometry comes from the browser. |
| 2026-09-04 | Before the full-page screenshot, inject `*{content-visibility:visible!important}`. | Section wrappers use `content-visibility:auto`; without the override everything below the fold is captured blank. `networkidle` never fires on these pages (analytics), so `load` + a scroll pass is used. |
| 2026-09-04 | A section is one non-empty direct child of `<main>`, plus the body-level `<aside>` (link chips) and `<footer>`. Type comes from the CMS component labels (`data-testid`, `data-pulse-section-group`: banner-block, promotional-component, how-it-works-section, use-cases, tutorials-section, faq-section, pricing-cards, ...) and falls back to structural heuristics (headings, media count, tabs, card links). | Labels are stable across pages and free; heuristics alone confused captioned galleries with link grids. |
| 2026-09-04 | Media roles are guessed: footer/header or ≤120 px → `icon`; card sections → `thumbnail`; alt words decoration/badge/logo → `decorative`; videos in how-it-works or "inside Picsart"/"built-in tools" callouts → `ui-screenshot`; else `creative`. Media with a 0×0 rendered box is dropped. | A wrong `creative` would spend credits on a UI shot; a wrong `ui-screenshot` only loses a slot. The skeleton is hand-edited before a run. |
| 2026-09-04 | `sectionize` stamps the snapshot: `data-lp-section="S03"`, `data-lp="S03-m1"`, `data-lp-t="S03-t2"`; the DB stores those selectors and `skeleton` emits `slots.json` with them. | `lp-inject` then needs no DOM-path selectors; the stamps survive any re-serialisation of `page.html`. |
| 2026-09-04 | Media `src` is stored as the CDN asset URL (Next.js `/_next/image?url=` proxy unwrapped). `similar` writes examples as PNG: AVIF/WebP converted with Pillow, videos as a still grabbed with Chromium at t=1 s. | Agents view files with `Read`, which cannot open AVIF or WebM; Playwright's bundled ffmpeg has no VP9 decoder. |
| 2026-09-04 | `skeleton.md` format: YAML frontmatter (`page, source, snapshot, brand, audience, defaults, budget, notes`), `## Sxx type`, `- tN tag: text -> href`, one fenced ```slot YAML block per media node (`id, kind, role, size, aspect, natural, duration_s, src, alt`), `> annotation:` per generated-role slot. `aspect` is quoted because bare `9:16` is a sexagesimal integer to YAML 1.1 parsers. | One file the manager parses and a human edits; ids map back to the stamps. |
| 2026-09-04 | Snapshots hold their media: `fetch` (and `lp-corpus media` for older snapshots) downloads every `img src`, `video src` and `poster` into `corpus/pages/<slug>/media/<stem>-<8 hex of the URL><ext>`, points the attribute at the copy, keeps the served attribute in `data-lp-src` / `data-lp-poster`, drops `srcset`, `sizes`, image preloads and `<picture>` sources, and removes `<base>` after absolutising the remaining relative links. `media.local_path`, `slots.json` `local`, the `skeleton.md` slot block `local:` and the `sections.md` media link (CDN URL as link title) all name the copy; `similar` copies from it. Stylesheets, fonts and CSS backgrounds stay remote. | Areg's call: a snapshot must not lose its images when the CDN drops an asset, and `lp-inject` can ship `media/` with `dist/`. Relative `media/` paths cannot coexist with `<base href="https://picsart.com/">`. |
| 2026-09-04 | `similar`: BM25 over section Markdown filtered by type, one section per page, source page excluded with `--exclude`, only sections with a `creative`/`thumbnail` slot, type-only fallback when the query matches nothing; at most 4 media files per example. | Briefs need media to look at, not the page's own section; 10 hero carousel images per example bloated a brief to 15 MB. |
| 2026-09-04 | Package uses a `src/` layout with one package and two console scripts. | Zero build-backend configuration with `uv_build`. |
| 2026-09-04 | Trial `runs/trial-1`: one random creative slot (ai-template-generator S07, 480x480) produced from the section text alone, source image, alt and paths withheld from the worker; 20 credits, one gate failure (a real brand mark inside a generated inset photo), balance delta matched the ledger. | Checks whether the brief carries enough for a worker without the original; the result is on-brief but generic (nature-photo cards) where the original is a bold branded template with tool icons, so the annotation, not the copy, decides the look. |
| 2026-09-04 | Repo declares an empty `[tool.uv.workspace]`. | `~/pyproject.toml` is a uv workspace; without this, uv adopts the project as a member and puts `.venv` and `uv.lock` in the home directory. |

## Branch

`main` is fast-forwarded to `milestone-1-corpus` after each milestone (last:
2026-09-04, Milestone 2). New work branches off `main`. No remote is
configured; the repo lives on this Mac only.

## Open questions

- Live check of the hooks and agents from `.claude/` needs a fresh session
  started in this folder (they load at start).
- The deny rule `Read(./**/.env.*)` also blocks writing `.env.example`; narrow it (e.g. `.env.local`) or create the file by hand.
- Worker model: `sonnet` (default now) or `opus`; decide on Milestone 3 reject rates.
- `page.png` (1440 px wide, full page) is stored but nothing reads it yet; the reviewer could compare against it.
- Offline, a snapshot shows its images and videos but not its styling: CSS chunks, fonts and the few `background-image:url(...)` assets are still remote. Localise those too if a fully offline `dist/` is ever needed.
- Six inventory paths serve the client-side app shell (no server-rendered text). `fetch` now records them as `shell: true` in meta.json without a snapshot, so they never enter the DB; `discover` could drop them from `pages.yaml` by fetching each candidate once.
- Role guesses to watch in Milestone 2: every `feature-callout` video is `creative` unless the headline says "inside Picsart" or "built-in tools"; product-demo videos will slip through as creative.
