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

## 1. Set up the run

1. `<run>` = the skeleton's folder. Create `<run>/sections/`, write
   `<run>/budget.json` from the skeleton frontmatter `budget.run_credits`
   plus `"dry_run": true|false`. Point `runs/current` at
   `<run>` with `ln -sfn`. The hooks read that symlink.
2. `picsart_credits` on the `b05f6314` connector; record the balance in
   `<run>/report.md` under "Start".
3. Parse the skeleton: frontmatter, each `## Sxx type` block, its `slot`
   blocks and `> annotation:`, `> style:` and `> text:` lines. Slots with
   role `ui-screenshot`, `icon` or `decorative` are kept from source, and so
   is any slot whose family's **Template** line says `kept-from-source`
   (link-grid thumbnails resolve there); list them in the report with the
   family name and skip. Sections with no remaining slots get no worker.
   Video slots take the family of their poster frame and are briefed as
   that family's main panel; compose is skipped for video.
4. A `> style:` still reading TODO is yours to decide, from the
   `## Slot classes` table in `picsart-workflows/style-families.md`:
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
   List every choice in the report under "Manager decisions".
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

## 2. Write one brief per section

For each section with slots, fill `brief-template.md` into
`<run>/sections/<Sxx>/brief.md`:

- the page frontmatter verbatim;
- that H2 block verbatim (text, slots, annotations) and nothing from other
  sections;
- the slot's `## <style>` block from `picsart-workflows/style-families.md`,
  verbatim, under `## Style family`;
- the `## Text in image` table: one row per string from the slot's
  `> text:` line with its role (headline or call-to-action), the panel that
  carries it and where; or the single word `none`;
- 2 example sections of the same type, same family first, one image each:
  `uv run lp-corpus similar --type <type> --style <true family[/ground]>
  --query "<headline and body>" --exclude <frontmatter page>
  --exclude-asset <8-hex id of the slot's source src> -k 2
  --out <run>/sections/<Sxx>/examples/` (excerpt `.md` files plus one
  480 px PNG each; video examples arrive as a still frame). A worker reads
  every image it is given, so two pictures that show the look beat twelve.
  `--exclude-asset` keeps sibling pages that reuse the very same image out
  of the examples; `--attr ground=black` narrows further;
- the `## References` section from `corpus/references/<family>.yaml`: its
  `prompt_guidance` verbatim, the `search_terms`, and two `examples`
  entries whose `matches` fit this slot's class. This is where the photo's
  look comes from; the section copy only gives the subject matter;
- `<run>/shared-context.md` if it exists (see step 3);
- the budget line (advisory per-slot cap from the frontmatter) and the
  output contract.

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
   It names a paid step without a preflight row, `count` above 1, a gate
   without an observation, `credits.spent` off the ledger, a final file not
   on disk, or a `result.md` missing its keys. A problem here is a
   SendMessage to the worker ("Record fix: ...") and a re-run of the check,
   never a review round.
2. When every section has passed the precheck (or after the last worker,
   whichever comes first), spawn one `section-reviewer` for the whole wave
   with: the run folder, the list of section folders, and
   `<run>/ledger.jsonl`. It writes one `review-N.md` per section with
   `verdict: accept | rework | block` and numbered change requests tied to
   workflow steps. One reviewer spawn loads the rubric once for all sections.
3. Decide per section:
   - accept: mark it in the report.
   - rework: SendMessage the same worker: "Rework: re-run from step N.
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
3. `picsart_credits` again. Finish `report.md`: per section pattern, steps,
   credits quoted vs spent (from `ledger.jsonl`), rounds, verdict; totals;
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
