# Restructure: workflows as Picsart Flow boards, and a wider look-corpus

2026-09-10. Areg's ask: the agents' workflow process must work within
Picsart's own workflow tool (Picsart Flow), blank board first, a Picsart
template when one is most appropriate; the manager needs a method to pull a
larger corpus (e.g. Google-Lens-search the corpus images); check the
existing rules on corpus, templates and worker styles; analyse the changes.
This is the analysis. The decision row is in `plan.md`, the rules in
`prd.md`, the doctrine in `.claude/skills/picsart-workflows/flow-boards.md`.

## 1. What was found before anything was changed

**Picsart Flow is GUI-only.** Three probes, all first-party:

| Probe | Result |
|---|---|
| MCP connectors (previous session) | no flow / run-workflow / pipeline tool; the connectors expose the *engines behind Flow's nodes* (`picsart_generate` = the Image node's model, `picsart_media_*` = the Motion node's MP Scene engine) |
| Picsart API platform (`picsart.com/api-platform/docs/api-reference`, `docs.picsart.io`) | `POST /workflows/{workflow}/execute`, `/submit`, `GET .../{id}/result` exist — but `{workflow}` is a **model name** ("193 models"). One model per call. No graph, no user-defined workflow. The docs index lists no Flow product. |
| Flow's own tutorial (`picsart.com/tutorials/how-to-build-your-first-ai-workflow/`) and gallery (`picsart.com/workflows`) | editor at `picsart.com/create/workflows`, login-walled. Steps: Input (upload, prompt, blank canvas) → Processing (generate, remove background, enhance, effects; "Choose AI models" per step) → Output (format, quality); wire by dragging output to input; save, share, team templates; running spends Picsart credits. |

So "agents work within Flow" has exactly one honest form: **author every
slot in Flow's model and run it on Flow's engines**, and render the board
so a person can rebuild it on the canvas. Driving the GUI is not possible
without logging into Areg's account (declined, and 20 slots a run through a
lazy-loaded canvas would be the least reliable part of the pipeline by far).

**Google Lens has no API.** The programmatic equivalents are SerpApi's
`google_lens` engine (a Lens wrapper: `visual_matches` / `exact_matches`,
each with title, page link, source, image) and Google Cloud Vision
`WEB_DETECTION` (`visuallySimilarImages`, `fullMatchingImages`,
`pagesWithMatchingImages`, `bestGuessLabels`). Bing Visual Search is retired
(its docs are archived). Both live options need a key; neither is on this
machine yet.

**The existing rules** (full inventory taken this session; the seams it
found are in §6). The corpus is Picsart pages only (`discover.py` hard-gates
the host), tagged by measured attributes and labelled sheets, never by a
vision API; `similar` picks two same-type, same-family sections at one
480 px image each, blind to the target page by asset id; `corpus/references/`
is Pexels/Unsplash only, verified on page, URLs only, and reaches the worker
as prompt guidance plus two `(url, creator)` pairs — no file URL. "Template"
meant three things: an `lp-compose` chrome template (6 of 15 families), a
workflow *pattern* (direct, anchored, cutout, series, composite), and the
fill-in doc templates. Fifteen style families bind a worker through the
brief's verbatim block; the worker never opens the families file.

## 2. What changed: the workflow is now a Flow board

### 2.1 The object

`workflow.yaml` was an ordered list of tool steps. It is now a **board**:
START → nodes → END, each node of a Flow kind on one engine and one model,
wired by `in:`. The keys added to the existing schema, nothing removed:

| Key | Meaning | Flow equivalent |
|---|---|---|
| `board: blank \| template` | how the board began | blank canvas vs "Use this workflow" |
| `template: {title, url, category, shape, adapted}` | provenance and what was changed, when `board: template` | the gallery card |
| `start: {inputs: [{id, kind: ref, url, use}], text: [...]}` | what enters the board: the brief's strings and the one REF the brief allows | START / REF / DOCUMENT INPUT |
| step `node:` | `text \| ref \| image \| edit \| cutout \| background \| enhance \| video \| motion \| compose` | the node palette: Text, Image (generate / edit / cutout / background / enhance are the Image node's tools), Video, Motion; `compose` is ours (Picsart's card chrome has no Flow node) |
| step `in: [start \| ids]` | the nodes this one is fed from | the wire |
| step `reason:` | what the node varies, or the quoted copy that licenses a non-pro model | the step's label |
| `final:` (unchanged) | the END node | END |

Everything the old record had stays: `tool`, `model`, `params`, `gate`,
`quoted_credits`, `status`, `outputs`, `passed`, `note`, `credits`,
`rounds`, `<step N passed>` placeholders. The hooks (`check_result.py` keys
`slot:`/`steps:`/`final:`), the ledger and `precheck.py`'s prompt-matching
are untouched. Records from live-1 to live-4 read as boards through
inference (`flow/board.py: infer_node`, `infer_in`), so nothing old is
orphaned.

### 2.2 The tooling: `lp-flow`

`src/landing_page_gen/flow/board.py` + `cli.py`, console script `lp-flow`.

- `lp-flow check <workflow.yaml>...` — the board wires: `board` value known;
  a template board carries title/url/adapted; every `in:` is `start` or an
  earlier node; a node's `tool` is an engine of its `node` kind; an `image`
  node off `gemini-3-pro-image` has a `reason`; an END exists.
  `precheck.py` calls the same check, so the manager's paperwork pass now
  refuses an unwirable board before any reviewer is spawned.
- `lp-flow sheet <workflow.yaml> [--out flow.md]` — the canvas sheet: a
  Mermaid `flowchart LR` of START → nodes → END plus one row per node (Flow
  type, engine, model, in, prompt, gate, credits, status). This is the
  artefact that closes the GUI gap: a person rebuilds the board in the Flow
  editor node by node from it, and the reviewer reads it before the yaml.
  `flow.md` is now part of the output contract and `precheck.py` requires
  it.
- `lp-flow templates --family --device --query` — searches
  `corpus/flow-templates.yaml`, prints fitting templates or "start from a
  blank board".

### 2.3 Blank board first; a template when it fits

The rule (`flow-boards.md`): every board starts blank. A gallery template
is copied only when **all three** hold — its `fits` names the family (and
the device when the slot has one); its `shape` covers every panel in the
brief's `## Slots to produce`; copying it moves no invariant (the pro-model
rule, the text rule, the family's Panels/Never lines, the ratio map). Then
`board: template` with provenance and `adapted`. A template is a **node
shape and an order of operations, not a look**: its pictures are not
references, its prompts are not ours, its models are replaced where they
differ. The reviewer scores this under a new `board` rubric key; a blank
board where a template would have fitted is a 4 with a note, never a
rework — blank stays the safe default.

`corpus/flow-templates.yaml` is the catalogue: categories, and per template
title, url, category, output size, description, tags, shape in words,
`fits: {families, devices}`. It is seeded with the two templates read
first-hand from the gallery last session ("Ethereal Studio Motion": packshot
→ studio-scene composite → 2K still + 4 s video, which is the layered-photo
Route 2 as a shipped Flow; "Create Animated Videos from Photos with Relight":
photo → motion → fan-out into three relit variants, which is our variation
pass). The manager refreshes it as step 0 of `/build-landing-page` from the
public gallery, recording only cards it opened. The gallery is client-
rendered and lazy-loaded, so the pass needs the browser pane visible.

### 2.4 The recipes, re-expressed

`image-workflows.md`'s patterns are now **board recipes** with their node
shape written out (direct: START → image → (edit) → (enhance) → END; series:
START → text envelope → one image node per member → END; composite: one
image node per panel → compose fed by all of them → END; cutout: image →
cutout → (background)). One recipe is new and promoted from the pilot:
**layered** — Route 1 (one model-native image node, REF in `imageUrls` when
a subject must stay identical) and Route 2 (plate → subject → cutout →
harmonise node fed by both → enhance), with the seven-item harmonisation
gate from `research/layered-photos/design.md`, and the pilot's finding that
`remove_bg` does not preflight-quote so Route 2 harmonises the subject's
own render when the cut is not quotable. The "longer workflows" doctrine
(critique → i2i refine → variation) is now literally more nodes fed by the
pass.

### 2.5 The agents

- **section-worker**: procedure is decide the board (read the brief's
  `## Flow board`, apply the three tests) → lay the nodes (`lp-flow check`)
  → preflight every paid node → run in wiring order, re-runs as new nodes
  with the same `in:` → `lp-flow sheet` → `result.md` with `board:` and
  `nodes:` per slot. The stale sentence "thumbnails go to
  `gemini-3.1-flash-image`, 3 credits" — the live seam the inventory found
  in the one file a worker reads first — is gone; every panel is
  `gemini-3-pro-image`. New rule: examples, stock and widened images are
  read, never wired.
- **section-reviewer**: reads `flow.md` first; scores `board`; change
  requests name nodes and may name wiring.
- **manager** (`build-landing-page`): step 0 catalogue refresh; brief gains
  `## Flow board` (the catalogue's answer, verbatim — the worker decides);
  widening when `similar` is thin (§3); precheck includes the board check;
  report counts blank vs template boards and widened families.

## 3. What changed: the manager can pull a wider corpus

### 3.1 Three tiers, three uses

| Tier | Source | Found by | Reaches the worker as | May be wired into a node? |
|---|---|---|---|---|
| Corpus | Picsart's own pages (`corpus/corpus.db`) | `similar`: BM25 over section copy, same type and family, blind by asset id | 2 excerpts + 1 image each | no |
| References | Pexels / Unsplash stock (`corpus/references/<family>.yaml`) | a collector searching **words** | `prompt_guidance` + 2 `(url, creator)` | no |
| **Widened** (new) | the web's visual neighbours of the corpus images (`corpus/widened/<family>.yaml`) | `lp-corpus widen`: reverse image search on the **pictures themselves** | `w<n>-widened.md` + PNG, `origin: widened` | no |

The first two were searched by words about the look; the third is searched
by the look. It is what "Google Lens the corpus" means in the pipeline.

### 3.2 `lp-corpus widen <family> [--exact] [--backend] [--limit]`

`src/landing_page_gen/corpus/widen.py`, stdlib `urllib` only (no new
dependency). For every asset `corpus/styles.yaml` tags with the family
(the CDN src is public), one search per asset, results merged into
`corpus/widened/<family>.yaml` keyed by the 8-hex asset id, an asset already
searched is not re-searched. Two sections per asset: `visual` (neighbours)
and `exact` (the photo's own pages elsewhere — provenance; a Pexels/Unsplash
hit is a candidate for the family's reference file, feeding the
`/collect-references` wave 2 that was defined but never run). Filters:
matches on our own hosts are dropped (that is the corpus, not a widening);
duplicate image URLs are dropped.

Backends: `serpapi-lens` (default; the literal Google Lens result set) and
`vision-web` (Cloud Vision web detection). Keys from `SERPAPI_KEY` /
`GOOGLE_VISION_API_KEY`; the module raises a clear error without one.

`similar --widen N` then serves N neighbours into a brief's `examples/`,
round-robin across the family's source assets so one asset does not fill
the set, honouring every `--exclude-asset` id (a neighbour whose page or
image names one is the target page's own picture on another site). Each
lands as `w<n>-widened.md` (origin, source asset, source site, page) plus a
480 px PNG.

### 3.3 The licence line, drawn once

Widened images have an **unknown licence**. They are therefore look
references only: read for finish, light, subject genre and framing; never
uploaded, never passed as `imageUrls`/`startFrame`/`image`, never injected.
This is now a rule in the skill's non-negotiables, the worker definition,
`prd.md` and `CLAUDE.md` — and it closed a gap the inventory found: nothing
previously forbade a worker from wiring a Pexels file URL into `imageUrls`;
the only defence was that the brief never carried one.

### 3.4 What widening does *not* do

It does not grow `corpus.db`: neighbours have no Picsart section, copy,
slot class or measured attributes, so they cannot enter `similar`'s ranking,
`attrs`, `taxonomy` or `styles`. They widen what a worker *sees* of a
family's look, not what the taxonomy is derived from. Making them corpus
members would need attributes measured on them — possible later with
`measure.py` (pixels only), but that is a taxonomy decision, not this one.

## 4. Validation

- `uv run pytest`: **91 passed** (78 before this work; +`tests/test_flow.py`
  7 tests, +`tests/test_widen.py` 6 tests, `test_precheck` updated for
  `flow.md`).
- `lp-flow check` on every live-3 and live-4 record: **50 problems, all the
  same kind** — `image node on gemini-3.1-flash-image without a reason`
  across live-4 S05 (15 gallery tiles), live-3 S03 (8 tiles) and S09 (4
  tutorial thumbs). Those are exactly the finished slots that ran on flash
  under the clause since removed; every other node in both runs wires with
  no finding. The check would have refused those boards before the first
  call.
- `precheck.py runs/live-4 S06`: clean record (the board check adds no
  false positive to a good composite record).
- `lp-flow sheet` on live-4 S06 renders START → image → image → compose →
  END with the compose fed by the second image, as the placeholders say.
- `lp-flow templates --family template-mockup --device applied-mockup`
  returns "Ethereal Studio Motion"; `--family before-after` returns "start
  from a blank board".

Not validated live: `lp-corpus widen` against a real key (none on this
machine; the parsers are tested on the documented payload shapes), and a
worker running the new procedure end to end (needs a run).

## 5. Cost and risk

- **Credits**: none of this spends generation credits. Boards add zero
  paid nodes by themselves; depth was already budgeted (40/slot, 600/run).
- **Money outside credits**: SerpApi and Cloud Vision bill per request;
  `--limit` bounds a first pass. A family has 3–370 tagged assets
  (`callout-1:1` is the big one), so a full pass on the corpus is a few
  thousand searches — run per family, on demand, cached in the yaml.
- **Template catalogue is thin** (2 entries) until a visible-pane gallery
  pass; until then most `## Flow board` lines will read "start from a blank
  board", which is the intended default anyway.
- **Inference on old records** can mis-wire a re-run: live-4 S06's second
  image node was a re-run of the first (fed from START), but with no `in:`
  it infers as fed by node 1. New records write `in:` explicitly; the
  worker rule says a re-run keeps its parent's `in:`.
- **Fidelity to Flow** is by model, not by execution: the same node kinds,
  one model per node, typed output, templates as node shapes — but our
  gates, quotes, ledger and blindness are ours, and `compose` is a node Flow
  does not have. `flow-boards.md` states the differences rather than hiding
  them.
- **The stale symlink**: `runs/current` still points at `pilot-layered`;
  step 1.1 now warns that a stale link would cap and log a new run against
  the old folder. Left in place (it is the last run's state); the next
  `/build-landing-page` re-points it.

## 6. The rule audit: what the inventory found, what was fixed, what stands

Fixed in this pass:

1. `section-worker.md` still sent thumbnails to `gemini-3.1-flash-image`
   (the worker's first-read file; the live seam). Fixed.
2. `prd.md` Budget still said 300 / 20 while `skeleton.py` said 600 / 40.
   Fixed.
3. No rule barred an external file URL from `imageUrls`. Now four places
   say never.
4. `plan.md`'s claim that `tool-map.md` says "composite thumbnails only"
   was stale (the doc already said "only when the page copy names this
   model"); superseded by the new row.

Standing, listed so they are not lost (none blocks the new procedure):

5. `similar -k` defaults to 3 where the manager procedure mandates 2; a
   forgotten flag yields 3 examples.
6. `similar --exclude` takes one slug while `--exclude-asset` repeats.
7. `> attrs:` is emitted by `skeleton` and used by the manager, but the
   brief template does not say whether the worker sees it.
8. `cinematic-still` lists `hero-1:1` in its Slots, but `taxonomy.family_of`
   requires 9:16, so that tag can only be manual.
9. `precheck.device_problems` reads the **first** `> device:` in a brief; a
   two-slot section with two devices false-flags the second spec.
10. `/collect-references --pages` (wave 2) is specified, never run; `widen
    --exact` now gives it a cheap first step.
11. 6 of 15 families have an `lp-compose` template; `prompt-card`,
    `vs-two-up`, `mockup-card`, `outcome-tile` are briefed as fallbacks and
    `template-mockup` draws one photo panel where the live-4 originals show
    2–3 (the `[fit]` gap).
12. `.env.example` cannot be written under the workspace `Read(./**/.env.*)`
    deny rule; the key names are in `CLAUDE.md` instead.

## 7. Files touched

Code: `src/landing_page_gen/flow/{__init__,board,cli}.py` (new),
`src/landing_page_gen/corpus/widen.py` (new), `corpus/cli.py` (`widen`
subcommand, `similar --widen`), `.claude/skills/build-landing-page/precheck.py`
(board check, `flow.md`), `pyproject.toml` (`lp-flow`), `.gitignore`
(widened PNGs), `corpus/flow-templates.yaml` (new), `tests/test_flow.py`,
`tests/test_widen.py` (new), `tests/test_precheck.py`.

Doctrine: `picsart-workflows/{SKILL,flow-boards (new),workflow-format,
image-workflows,video-workflows,tool-map,evaluation}.md`;
`build-landing-page/{SKILL,brief-template,output-contract}.md`;
`collect-references/SKILL.md`; `.claude/agents/{section-worker,
section-reviewer}.md`; `CLAUDE.md`, `prd.md`, `plan.md`;
`research/picsart-flow/analysis.md` (addendum).

## 8. What to run next

1. A live run on a small page with the new format — the measure is how
   many boards copy a template, what `lp-flow check` catches that
   `precheck` did not, and whether `flow.md` shortens the review.
2. A gallery pass for `corpus/flow-templates.yaml` with the browser pane
   visible, the four product/marketing/editing categories first.
3. `lp-corpus widen template-mockup --limit 5` with a key, read the yaml,
   then one brief with `--widen 2` to see whether the neighbours change
   what a worker prompts.
4. Items 5–9 of §6 are each a one-line code fix; 11 is the next real build.
