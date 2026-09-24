---
name: build-landing-page
description: Manager procedure that produces every image and video slot of a landing page from a skeleton.md by spawning section-worker and section-reviewer subagents, reviewing their Picsart workflows, and injecting the results. Invoke as /build-landing-page runs/<run>/skeleton.md [--dry-run].
disable-model-invocation: true
---

# build-landing-page

You are the manager. Arguments: `$ARGUMENTS` = path to `skeleton.md`, plus
optional `--dry-run`. Paths below are relative to the repo root. Companion files:
`brief-template.md` (what a worker receives), `output-contract.md` (what a
worker must return).

## 0. Refresh the Flow template catalogue

Workers build every slot as a Picsart Flow board (`picsart-workflows/
flow-boards.md`): blank canvas by default, a gallery template when one
fits. The catalogue they consult is `corpus/flow-templates.yaml`. Before a
run, open `https://picsart.com/workflows/` in the browser pane (the gallery
is public; never log in), walk the category tabs that match the page's
families (E-commerce & product content, Marketing & advertising, Photo
editing & enhancement, Design assets & elements), open each card whose
preview resembles a slot class we produce, and record title, url, category,
output size, description, tags, the node `shape` in words and `fits`
(families, devices). Set `refreshed:` to today. A card you did not open is
not recorded. Skip this step when the file is under two weeks old and the
page's families are covered.

## The procedure is checked

Every step below is required, in every mode (full page, `--slot`, blind,
trial). `lp-inject` runs `manager_check.py` on a live run and refuses to inject
until it is clean: `report.md` with the start balance, no generated slot the
procedure keeps from source, every family in a generation mode its context
allows, a clean precheck and an `accept` review per section. blind-1 skipped
the report, the review and the kept-from-source rule, and nothing stopped it.
A trial draws its slots with `pick.py` (§1.0), never by hand.

## 1. Set up the run

0. A trial of random slots: `uv run python .claude/skills/build-landing-page/pick.py
   --prefix <name> --n 5 --cap <credits per run> --seed <n>` draws one slot per
   page and per section type from what the procedure lets us generate and sets
   up each run folder (skeleton, slots.json, budget.json, shared-context.md) and
   `runs/<name>-plan.json`. Then do 1.1-1.2 and §2-§6 per run.

1. `<run>` = the skeleton's folder. Create `<run>/sections/`, write
   `<run>/budget.json` from the skeleton frontmatter `budget.run_credits`
   plus `"dry_run": true|false`. Point `runs/current` at
   `<run>` with `ln -sfn`. The hooks read that symlink (a stale link from an
   earlier run would cap and log this run against that folder).
2. `picsart_credits` on the `b05f6314` connector; record the balance in
   `<run>/report.md` under "Start".
3. Parse the skeleton: frontmatter, each `## Sxx type` block, its `slot`
   blocks and `> annotation:`, `> style:`, `> attrs:`, `> prior:`, `> text:`, `> device:` and `> chrome:` lines.
   `> prior:` is the page grammar (`picsart-workflows/page-grammar.md`,
   built by `lp-corpus grammar --write-doc`; `doctor` warns when it is stale):
   what slots in this context usually are — video share, the family shares,
   and for a video the motion and median length. It advises; the original's
   image-or-video and length stand. Only the length is measured to beat a
   default (see the doc's trust paragraph); the family shares are a
   shortlist, no better than the slot-class table at picking one.
   A prior ending `# unusual:` means the original breaks a well-supported
   pattern: keep it (never switch a slot between image and video) and write
   one line under "Manager decisions" saying why it holds on this page. A
   section-level `> prior: no generated media here` gets no slot. Slots with
   role `ui-screenshot`, `icon` or `decorative` are kept from source, and so
   is any slot whose family's **Template** line says `kept-from-source`
   (link-grid thumbnails resolve there); list them in the report with the
   family name and skip. Sections with no remaining slots get no worker.
   Video slots take the family of their poster frame and are briefed as
   that family's main panel; compose is skipped for video. Their
   `> duration:` line is the original clip's length: keep it (the final
   matches it, `budget.video_seconds` capping) or override it with a
   number. A TODO duration (the original's length unknown) is left for
   `brief.py`, which takes the prior's median length; `brief.py` turns it into the brief's `## Video` section and
   asks `similar` for clips (`--kind video`, excerpted as 3-frame strips).
   A video slot's `> motion:` line says how it is made: `timeline <preset>`
   (a templated callout on a static camera, rendered by `lp-compose
   --timeline` for 0 credits; `lp-compose --describe-timelines`) or
   `generative` (the Seedance recipe). A `timeline TODO ...` is yours: open
   the original's strip (`corpus/frames/<id>-strip.png`) and pick the preset
   whose states it shows, or write `generative` when the picture itself
   moves. Its `> chrome:` line carries the preset's strings (the checklist
   rows, the product name | price | button, the prompt, the title | caption),
   each from the section copy.
3b. **Generation mode.** Picsart uses a bare standalone generation only where
   it showcases many options side by side (a scrolling gallery of different
   characters, styles or subjects) and on tutorial thumbnails; everywhere else
   its images are layered templates, or finished designs on maker pages
   (`style-families.md` § Vocabulary → Generation modes, measured by `corpus/genmode.py`).
   `brief.py` states the allowed modes in every brief and refuses a family of
   another mode; to leave them, write `> mode: <mode> because <the copy that
   demands it>` under the slot and list it under "Manager decisions".
4. A `> style:` is yours to decide when it reads TODO, and also when its
   `> attrs:` line says `chrome=unanswered` and the slot's row in the
   `## Slot classes` table lists any chrome family (dark-composite,
   before-after, crop-frame, cutout-checkerboard, template-mockup,
   prompt-card, vs-two-up, mockup-card, model-card, panel-overlay): a
   pre-filled tag whose chrome was never labelled is a measurement, not a
   label (the measurer reads a black card with a picture panel as
   `photo-full-bleed`, and sibling pages of one CMS block share the same
   unanswered measurement, so their agreement proves nothing). Rows whose
   families are all chrome-free (gallery-9:16, tutorial-3:2) keep the tag.
   Resolve from the table in `picsart-workflows/style-families.md`:
   1. the slot's class is `<type>-<aspect class>[-video]` (`callout-1:1`,
      `gallery-9:16`, `thumb-5:4`; `aspect_class` in the slot block when it
      differs from `aspect`);
   2. take that row's families; apply the page-family rule the row names
      (ai-models callouts are `dark-composite/light`, compare-models callouts
      are `vs-two-up`; on an adjustment-tool page, where the H1 or the tool
      name says hue, saturation, HSL, colour, colorize, curves, filter or
      adjust, 4:3 and 5:4 heroes and use-case cards are `panel-overlay`);
   3. only if more than one candidate remains, read their **Use** lines for
      the headline cue; otherwise the row's first family;
   4. write `> style: <family>[/<ground>]` back into `skeleton.md`. When the
      family's **Template** says `none; brief as X`, the skeleton keeps the
      true family and the brief carries X's block with a `Stands in for:`
      line; a `TBD` row is briefed as `full-bleed`.
   List every choice in the report under "Manager decisions"; an overridden
   tag as `tag overridden: <old> -> <new> (chrome unanswered)`.
5. A `> text:` still reading TODO is yours to decide, after the family. Read
   the family's **Text** line: if it says chrome text only, write
   `> text: none`. Otherwise derive the picture text from this section's
   copy and nothing else:
   - a headline of 1 to 3 words: a marketing fragment the section implies
     (a promotion, an event, a season, a product name the copy names), not
     the H2 itself and never the HTML copy that will sit next to the image;
   - at most one call-to-action of 1 to 2 words, taken from the section's
     link text when it has one;
   - the page's language; ordinary words only; no brand names, model names,
     trademarks, prices with a currency, or people's names;
   - at most 2 strings per slot, written exactly as they must render:
     `> text: "50% OFF" | "Buy now"`.
   Write the line back into `skeleton.md` and list every string under
   "Manager decisions". A slot whose family allows text but whose section
   gives nothing to say gets `none`, not an invented phrase.
6. A `> annotation:` still reading TODO: one sentence of subject and
   composition from this section's copy, one finish; when step 7 gives the
   slot a device that is a compose variant, one clause per panel of that
   variant (thumbnails included, each with its own ground). For `gallery-*`
   classes the subject fills the frame (80 to 100 % of the tile height,
   edge to edge) on the ground the family's **Grid** line names; margin and
   centring language belongs to callout panels only (live-2's gallery came
   out pale and under-filled from "centred, generous margin, off-white").
7. A `> device:` still reading TODO is decided after step 2's `similar` has
   written the examples and before the brief. It names what the picture
   demonstrates, the family names how it looks. Read the H2 and body for the
   cue: reference, style reference, lock, feed it -> `reference-thumbs`;
   icon, set, system, kit, matching -> `icon-set`; how it works, examples,
   every format -> `two-up`; preferred, compared, vs, leading models, "% of
   the time" -> `model-picker`; logo, brand mark, sign, packaging, app icon
   -> `applied-mockup`; nothing -> `none`. Then open each example image once
   and name the device it carries; when the copy allows it, the examples'
   device wins (live-3's hero examples showed two reference thumbnails and
   nobody was asked to look). Write `> device: <id>: <claim>` back into
   `skeleton.md` (the claim in one clause, e.g. "references in, style-locked
   output out") and list it under "Manager decisions". `reference-thumbs`,
   `model-picker`, `two-up` and `bento` are `lp-compose` variants of
   `dark-composite` (`uv run lp-compose --describe dark-composite` lists their
   panels and slots; `--skeleton dark-composite --preset bento --out x.png`
   draws one). A layout is a skeleton: choose the one whose slots this page
   can fill with blocks that belong (`picsart-workflows/blocks.md`). When
   the TODO names `m-<code>` it is this slot's own measured layout (induced
   from the original's reading by `lp-compose --induce`: its panels, cards and
   pills where the original has them, each with its measured fill, radius and
   type); prefer it when the section's copy can fill its slots, since it is
   the structure the page already had, and set `> style:` to the family it
   names. A
   dark-composite section on a page with no image tool whose copy carries a
   formula or key line, the channels the output runs on, or the page's own
   calculator -> `bento` (three cards around the picture), never the tile
   column with a borrowed tool;
   `icon-set` and `applied-mockup` are written into the `photo` annotation
   itself (a 3x3 grid of matching icons; the mark on a sign) and use the
   plain template. Four devices are compose variants of one family each and are
   named only when the slot is that family: on a `crop-frame` slot, rule of
   thirds, grid, straighten, compose the shot, or examples showing a 3x3 grid
   -> `crop-grid`; on a `template-mockup` slot, palette, colours, brand kit,
   colour scheme -> `palette-card` (the page's colours go on the `> chrome:`
   line, step 8); on a `template-mockup` or
   `cutout-checkerboard` slot, select, move, resize, drag, arrange, transform an
   element -> `selection-frame` (move `select.rect` in the plan onto the
   element when its default spot misses it); on a `template-mockup` slot whose
   copy invites customising every part of a template (its elements, fonts,
   colours, photos), or whose examples show the design pulled apart into a
   cut-out motif, a type tile and a swatch bar -> `editor` (the swatch colours
   go on `> chrome:`; the worker adds the motif as a `cutout` panel). On a
   before-after section whose two 1:1 slots are one picture before and after
   (the enhancer heroes) -> `pill`, with `> chrome: "Before" | "After"` (one
   state per slot, in slot order); the Before slot is then made from the
   After, never generated. Never name `stacked-square` or `compare-slider`:
   a 1:1 before-after slot gets the first and a 16:10 gallery card the second from its size. A
   model-picker ticks the model that generates the picture (the page's own on
   a model page); name another only on `> chrome:` when the copy presents it.
8. A `> chrome:` still reading TODO is decided after step 7, for a slot whose
   family `lp-compose` draws. The layout's slots are empty until the worker
   fills them from the bank, and the worker takes every string from the page
   copy; this line lists only what the chrome may say beyond the copy: the
   Before | After of a `pill` pair (in slot order), a model a picker may tick
   that the page presents, the page's colours as hex for a palette. Most slots
   need none, so `> chrome: none` is the common answer. Never a competitor's
   name, never a string on the `> text:` line (brief.py refuses a string on
   both lines). To change it, edit the line and re-run `brief.py --replan`;
   never a slot in `composition-<slot>.yaml`, which must match the line it was
   built from (moving a slot's `rect` off the subject is the one hand edit).
   `brief.py` refuses a layout whose required slot no bank block can honestly
   fill on this page and names the layouts of the family that can. List the
   strings under "Manager decisions".

## 2. Write one brief per section

The four `>` lines (annotation, style, text, device) are the manager's
judgement (§1.4–1.7). Once a section's are resolved in `skeleton.md`, assemble
its brief deterministically — do not read `style-families.md`, `slots.json`, the
example excerpts or the references yourself:

```
uv run python .claude/skills/build-landing-page/brief.py <run> <Sxx> \
    [--pool N --seed <run>] [--widen N] [--replan] [--slot Sxx-mN]   # --slot: one slot of the section, its own lines
```

**Blind mode (`--blind`).** No line read off the original reaches the worker:
not its measured `> attrs:`, not its labelled `> style:`, not the manager's
`> annotation:`/`> device:`/`> text:`/`> chrome:`. Phase 1 writes a proposal
brief (page and section copy, slot geometry, the page grammar, the families'
**Use** lines, examples from other pages, shared context); the worker writes
`proposal-<slot>.yaml` (style, device, annotation, text, chrome, because) and
stops. Re-run `brief.py --blind` for the full brief built from the proposal
(no layout check: it reads the original), then the worker builds as usual.
The manager only reads the proposal for rule faults (a never-generated family,
a string the family's Text line forbids), never against the original. A
proposal `brief.py --blind` refuses (a family outside the allowed generation
modes) goes back to the same worker: "Re-propose <slot>: <brief.py's message>".
The proposal brief also lists, per slot, the families with a layout at its
size and those layouts by their panels and slots (`## Layouts for <slot>`); the
proposal names its layout first on the device line, so the plan is built on
the layout that shows the device (blind-2: three plans fell back to a default
that could not show a set, a stack or a prompt box). It carries the text rules
and the enforced cap (`budget.json`). Both blind briefs carry `## Where each image sits` (the card heading and card
text each image belongs to, from the page snapshot) and `## Generation mode`.

**The manager adds nothing to a brief by message.** The spawn and the
phase-2 message are fixed: "Section <Sxx>. Work only inside
`<absolute run path>/sections/<Sxx>/`. Read `brief.md` first." The absolute
path is what the hooks read: each worker's calls are capped and logged in the
run its first message names (`hooks/_ledger.active_run`), so the runs of a
trial build in parallel; `runs/current` only covers calls made outside a worker. (blind phase 2: "Your full
brief is written. Build from `brief.md`."). No description, recipe, model,
cap or panel instruction goes in a message: when the brief is wrong, fix its
source (a skeleton line, the plan, `brief.py`) and re-run `brief.py`. blind-1's
build messages restated a plan the brief contradicted and overrode its cap.

**Layout check (before any worker starts).** `brief.py` measures each slot's
layout against the slot's own original (`compose/fitcheck.py`: panel count,
boxes, the share of the canvas the pictures fill, aspect), prints a
`brief.py: Sxx Sxx-mN (<layout>): ...` line per warning, puts them in the
brief's `## Layout check` and draws `layout-check-<slot>.png` (original |
skeleton). Open the sheet and resolve every warning before spawning: change
the `> style:`/`> device:` line (a warning names the slot's own measured layout
when one exists), split a section whose slots are different devices, or note
in the report why the warning stands. Both layout faults the live runs paid
for would have been caught here.

`brief.py` fills `brief-template.md` from the skeleton and the corpus: the
section block (verbatim, minus `src:/local:/alt:`), the family's
`style-families.md` block and its **Signature** checklist (a
`Template: none; brief as X` becomes X's block with a `Stands in for:` line;
a video slot is briefed as its poster family's main panel), the recipe row
rendered from `flow/board.py` RECIPES (never a hand-typed table that could
drift from `lp-flow check`), `lp-flow templates`, `similar -k 2` with the
page's own asset ids excluded (from `slots.json`, so no `exclude_ids.txt`),
the references genre and terms, `shared-context.md`, the budget and the output
contract. It runs `blindcheck.py` for that section and refuses to write on a
hit — fix the hit (exclude the id, or delete the example) and re-run. A
slot's composition plan is written once: a re-run keeps it, with your hand
edits (a moved `select.rect`, a checker tone, panel state), and refuses one
whose skeleton lines or slot size changed since it was built; `--replan`
rebuilds it, dropping those edits. It also
refuses a composition plan `lp-compose` could not render, such as a slot size
no layout of the family fits: set `> device:` to the layout the message says
fits (`none` for the default), or restyle the slot, then re-run.

Pass `--pool 2 --seed <run>` when the family has kept pool entries
(`corpus/pool/<family>.yaml`); pass `--widen 2` (after `uv run lp-corpus widen
<family>`, once per family per fortnight) when `similar` yields fewer than two
same-family examples and the pool is empty. Both add look-only references the
worker never wires into a node.

Write `<run>/shared-context.md` (§3) first — every brief carries it, so it must
exist before the first section. Spawn each section the moment its brief is
written (§4); when every brief is written, run the whole-run backstop once
(`uv run python .claude/skills/build-landing-page/blindcheck.py <run>`, no
section) and record its clean result in the report.

## 3. Shared context, before any worker

Write `<run>/shared-context.md` from the skeleton alone: the hero's style
family, and its light, palette, finish and subject genre in words taken from
the hero annotation and the family's `prompt_guidance` ("hard even studio
flash, seamless yellow and purple, glossy editorial finish, one person").
Anchored workers quote these words; no worker waits for the hero image.

## 4. The wave: spawn each section as its brief clears

Spawn one `section-worker` per section (Agent tool, `subagent_type:
section-worker`), in the background, the moment that section's per-section
blind check passes (§2) — do not wait for the last brief, so the earliest
sections generate while the later briefs are still being assembled. Batch
into one message whatever briefs are ready at the same time. The prompt:
"Section <Sxx>. Work only inside `<run>/sections/<Sxx>/`. Read `brief.md`
first." The hero is just one of them (spawned as soon as its brief clears, so
usually among the first). When the hero worker finishes and its record passes
step 5's precheck, append its photo URL to `shared-context.md` under
`hero_url:`; a Series worker that has not yet generated may pass it in
`imageUrls`, everyone else ignores it. Nothing waits on the hero image — §3's
shared context is written from the skeleton.

Do not hand-log tokens per spawn: after the run, `uv run lp-tokens <run>`
reads the session transcript and emits the per-agent token/cost `## Agents`
table (turns, average context, output, cache-read, cost, and the polls,
sleeps and ledger reads that drive them). Paste it into `report.md` at §6.

## 5. Precheck and review, per section as workers finish

1. As each worker finishes, run the paperwork check, no agent involved:
   `uv run python .claude/skills/build-landing-page/precheck.py <run> <Sxx>`.
   It names a paid node without a preflight row, `count` above 1, a gate
   without an observation, `credits.spent` off the ledger, a final file not
   on disk, a `result.md` missing its keys, or a board that does not wire
   (`lp-flow check`: a node fed by a later node, a kind on the wrong engine,
   an image node off the pro model with no quoted copy, a template board
   without its source). A problem here is a SendMessage to the worker
   ("Record fix: ...") and a re-run of the check, never a review round.
2. The moment a section passes its precheck, spawn a `section-reviewer` for
   that section — the run folder and that one section folder (batch up to 3
   that clear precheck close together). The precheck (§5.1) has already
   reconciled `credits.spent` against the ledger, so the prompt says
   `precheck: clean record` instead of passing `<run>/ledger.jsonl`; the
   reviewer never greps the ledger. Review overlaps
   the still-running wave instead of following it, and each spawn stays well
   inside its turn budget. It writes one `review-N.md` per section named, with
   `verdict: accept | rework | block` and numbered change requests tied to
   workflow steps.
3. Decide per section as each verdict arrives:
   - accept: mark it in the report.
   - rework: SendMessage the same worker: "Rework: re-run from node N.
     Changes: ..." (its context is intact). At most 2 rework rounds per
     section; a reworked section is re-reviewed in its own spawn.
   - after 2 rounds: accept the best candidate the reviewer names, or mark
     the slot blocked with the reason.

Do not open candidate images yourself unless verdicts conflict; the reviewer
has already looked. Keep your own context for coordination.

## 6. Assemble

0. `uv run python .claude/skills/build-landing-page/manager_check.py <run>`
   must print `procedure followed`; `lp-inject` runs it too and refuses
   otherwise. Fix what it names (write the report, spawn the missing review,
   restyle or block the slot); never inject around it.
1. `uv run lp-inject <run>` — it reads the skeleton and each
   `sections/<Sxx>/result.md` frontmatter (the worker's `chosen` asset and
   `workflow` per slot) and assembles `<run>/page.md` itself, kept-from-source
   slots untouched, then injects the media and changed text. Do not hand-write
   page.md.
2. `uv run lp-bench <run>` writes `<run>/benchmark.md`: every generated slot
   measured against the original it replaced (family, ground, coverage,
   saturation, and for composites the `pictures` count, a device proxy that
   raises `[fit]` flags) with flags keyed to the rubric. Paste its per-slot table and
   flags into `report.md` under "Against the original" **before** opening
   any original yourself; then look, and write what the numbers missed.
3. `picsart_credits` again. Finish `report.md`: per section board (blank,
   or the template title), recipe, nodes, credits quoted vs spent (from
   `ledger.jsonl`), rounds, verdict; totals, with how many boards were
   blank and how many copied a template; which families were widened and
   with how many neighbours; which families drew pool references, how many
   each, and the `--seed` used;
   kept-from-source and blocked slots; balance delta versus ledger sum; the
   `## Agents` table from `uv run lp-tokens <run>` (§4) and the wall time from
   the first spawn to the last verdict.

## Dry run

With `--dry-run`, `budget.json` has `dry_run: true`; the credit guard denies
every paid step and tells the worker to record it as quoted. Workers still
preflight (free). The result is a fully priced `workflow.yaml` per slot and a
page total in `report.md`. Present the total and stop.

## Rules

- Never call paid Picsart tools yourself. Only workers generate.
- Never pass another section's text to a worker unless you write it into
  `shared-context.md` on purpose, with a one-line reason.
- Every rule a review teaches goes to `prd.md`; the decision to `plan.md`.
