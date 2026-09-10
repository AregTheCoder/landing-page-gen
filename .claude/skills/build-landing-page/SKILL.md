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

## 1. Set up the run

1. `<run>` = the skeleton's folder. Create `<run>/sections/`, write
   `<run>/budget.json` from the skeleton frontmatter `budget.run_credits`
   plus `"dry_run": true|false`. Point `runs/current` at
   `<run>` with `ln -sfn`. The hooks read that symlink (a stale link from an
   earlier run would cap and log this run against that folder).
2. `picsart_credits` on the `b05f6314` connector; record the balance in
   `<run>/report.md` under "Start".
3. Parse the skeleton: frontmatter, each `## Sxx type` block, its `slot`
   blocks and `> annotation:`, `> style:`, `> attrs:`, `> text:` and `> device:` lines. Slots with
   role `ui-screenshot`, `icon` or `decorative` are kept from source, and so
   is any slot whose family's **Template** line says `kept-from-source`
   (link-grid thumbnails resolve there); list them in the report with the
   family name and skip. Sections with no remaining slots get no worker.
   Video slots take the family of their poster frame and are briefed as
   that family's main panel; compose is skipped for video.
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
   `model-picker` and `two-up` are `lp-compose` variants of `dark-composite`
   (`uv run lp-compose --describe dark-composite` lists their panels);
   `icon-set` and `applied-mockup` are written into the `photo` annotation
   itself (a 3x3 grid of matching icons; the mark on a sign) and use the
   plain template. The model-picker list card carries blank rows and the
   page's own model short name on the active row (`chrome: {list:
   {active_text: "Recraft V4"}}`), never a competitor's name or mark.

## 2. Write one brief per section

For each section with slots, fill `brief-template.md` into
`<run>/sections/<Sxx>/brief.md`:

- the page frontmatter's `page`, `brand`, `audience`, `defaults`, `budget`
  and `notes`; never `source:` or `snapshot:` (nothing in a brief needs the
  original's URL or path; `lp-inject` reads the snapshot from `slots.json`);
- that H2 block verbatim (text, slots, annotations, the `> device:` line)
  and nothing from other sections; strip `src:`, `local:` and `alt:` from
  its slot blocks; the `Device:` line under `## Style family` repeats the
  id and claim and says whether it is a compose variant or an annotation;
  the `## Slots to produce` table lists every panel of the variant;
- the slot's `## <style>` block from `picsart-workflows/style-families.md`,
  verbatim, under `## Style family`, followed by its **Signature** line as a
  checklist (one item per attribute) that `resemblance` walks;
- the `## Text in image` table: one row per string from the slot's
  `> text:` line with its role (headline or call-to-action), the panel that
  carries it and where; or the single word `none`;
- 2 example sections of the same type, same family first, one image each:
  `uv run lp-corpus similar --type <type> --style <true family[/ground]>
  --query "<headline and body>" --exclude <frontmatter page>
  --exclude-asset <id> [--exclude-asset <id> ...] -k 2
  --out <run>/sections/<Sxx>/examples/` (excerpt `.md` files plus one
  480 px PNG each; video examples arrive as a still frame). A worker reads
  every image it is given, so two pictures that show the look beat twelve.
  `--exclude-asset` is repeatable: pass one per generated slot of the whole
  page, the id being the first 8 hex of the uuid in the slot's `src` (what
  `attrs.asset_id` and the Examples lines use), not the hash at the end of
  `local:` (that is `sha1(url)`, and differs per CDN host). Blocks shared
  site-wide (the tutorial grid) show this page's own images on other pages
  and other section types, which is why every slot's id goes on every call;
  `--attr ground=black` narrows further;
  When `similar` prints fewer than 2 tagged same-family examples, widen the
  family first: `uv run lp-corpus widen <family>` (once per family per
  fortnight; `SERPAPI_KEY` or `GOOGLE_VISION_API_KEY` in the environment,
  no key means skip and say so in the report) and re-run `similar` with
  `--widen 2`, which adds two visual neighbours of the family's corpus
  assets as `w<n>-widened.md` + PNG. Neighbours are look references with an
  unknown licence: the brief says so, and no worker wires one into a node;
- the `## Flow board` section: the output of `uv run lp-flow templates
  --family <family> --device <device> --query "<H2>"`, verbatim — either
  "start from a blank board" or the fitting template(s). The worker decides;
  you only put the catalogue's answer in front of it;
- the `## References` section from `corpus/references/<family>.yaml`: its
  `prompt_guidance` verbatim, the `search_terms`, and two `examples`
  entries whose `matches` fit this slot's class. This is where the photo's
  look comes from; the section copy gives the subject matter and, through
  `> device:`, what the panels demonstrate together;
- `<run>/shared-context.md` if it exists (see step 3);
- the budget line (advisory per-slot cap from the frontmatter) and the
  output contract.

When every brief is written, run
`uv run python .claude/skills/build-landing-page/blindcheck.py <run>`. It
greps the briefs and example excerpts for the page's own asset ids and for
`snapshot:`/`source:` pointers. A hit names the section: re-run `similar`
with the id excluded or delete that example, and strip the line it names.
No worker is spawned while it fails. Record the clean result in the report.

## 3. Shared context, before any worker

Write `<run>/shared-context.md` from the skeleton alone: the hero's style
family, and its light, palette, finish and subject genre in words taken from
the hero annotation and the family's `prompt_guidance` ("hard even studio
flash, seamless yellow and purple, glossy editorial finish, one person").
Anchored workers quote these words; no worker waits for the hero image.

## 4. One wave: every section at once

Spawn one `section-worker` per section (Agent tool, `subagent_type:
section-worker`), all in one message, in the background, with the prompt:
"Section <Sxx>. Work only inside `<run>/sections/<Sxx>/`. Read `brief.md`
first." The hero is just one of them. When the hero worker finishes and its
record passes step 5's precheck, append its photo URL to
`shared-context.md` under `hero_url:`; a Series worker that has not yet
generated may pass it in `imageUrls`, everyone else ignores it.

Record each agent's tokens and wall time from its completion notification in
`report.md` under "Agents" (one line per spawn), so the next run can be
compared.

## 5. Precheck, then one review for the wave

1. As each worker finishes, run the paperwork check, no agent involved:
   `uv run python .claude/skills/build-landing-page/precheck.py <run> <Sxx>`.
   It names a paid node without a preflight row, `count` above 1, a gate
   without an observation, `credits.spent` off the ledger, a final file not
   on disk, a `result.md` missing its keys, or a board that does not wire
   (`lp-flow check`: a node fed by a later node, a kind on the wrong engine,
   an image node off the pro model with no quoted copy, a template board
   without its source). A problem here is a SendMessage to the worker
   ("Record fix: ...") and a re-run of the check, never a review round.
2. When every section has passed the precheck (or after the last worker,
   whichever comes first), spawn one `section-reviewer` for the whole wave
   with: the run folder, the list of section folders, and
   `<run>/ledger.jsonl`. It writes one `review-N.md` per section with
   `verdict: accept | rework | block` and numbered change requests tied to
   workflow steps. One reviewer spawn loads the rubric once for all sections.
3. Decide per section:
   - accept: mark it in the report.
   - rework: SendMessage the same worker: "Rework: re-run from node N.
     Changes: ..." (its context is intact). At most 2 rework rounds per
     section; reworked sections are reviewed together in one more spawn.
   - after 2 rounds: accept the best candidate the reviewer names, or mark
     the slot blocked with the reason.

Do not open candidate images yourself unless verdicts conflict; the reviewer
has already looked. Keep your own context for coordination.

## 6. Assemble

1. Write `<run>/page.md`: the skeleton with each filled `slot` block
   replaced by a `chosen` line (`chosen: <url or run-relative path>` and
   `workflow: sections/<Sxx>/workflow.yaml`), kept-from-source slots left
   untouched.
2. `uv run lp-inject <run>`.
3. `uv run lp-bench <run>` writes `<run>/benchmark.md`: every generated slot
   measured against the original it replaced (family, ground, coverage,
   saturation, and for composites the `pictures` count, a device proxy that
   raises `[fit]` flags) with flags keyed to the rubric. Paste its per-slot table and
   flags into `report.md` under "Against the original" **before** opening
   any original yourself; then look, and write what the numbers missed.
4. `picsart_credits` again. Finish `report.md`: per section board (blank,
   or the template title), recipe, nodes, credits quoted vs spent (from
   `ledger.jsonl`), rounds, verdict; totals, with how many boards were
   blank and how many copied a template; which families were widened and
   with how many neighbours;
   kept-from-source and blocked slots; balance delta versus ledger sum; the
   "Agents" table (spawn, model, tokens, minutes) and the wall time from the
   first spawn to the last verdict.

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
