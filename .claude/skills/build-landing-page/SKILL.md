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
   blocks and `> annotation:` and `> style:` lines. Slots with role
   `ui-screenshot`, `icon` or `decorative` are kept from source; list them in
   the report and skip. Sections with no remaining slots get no worker.
4. A `> style:` still reading TODO is yours to decide: pick the family whose
   **Use** line matches the section (`picsart-workflows/style-families.md`),
   write it back into `skeleton.md`, and list the choice in the report under
   "Manager decisions".

## 2. Write one brief per section

For each section with slots, fill `brief-template.md` into
`<run>/sections/<Sxx>/brief.md`:

- the page frontmatter verbatim;
- that H2 block verbatim (text, slots, annotations) and nothing from other
  sections;
- the slot's `## <style>` block from `picsart-workflows/style-families.md`,
  verbatim, under `## Style family`;
- 2 to 3 example sections of the same type, same family first:
  `uv run lp-corpus similar --type <type> --style <style>
  --query "<headline and body>" --exclude <frontmatter page> -k 3
  --out <run>/sections/<Sxx>/examples/` (excerpt `.md` files plus PNGs;
  video examples arrive as a still frame, the `src` in the excerpt is the clip);
- `<run>/shared-context.md` if it exists (see step 3);
- the budget line (advisory per-slot cap from the frontmatter) and the
  output contract.

## 3. Wave 1: the hero

Spawn one `section-worker` (Agent tool, `subagent_type: section-worker`)
with the prompt: "Section <Sxx>. Work only inside `<run>/sections/<Sxx>/`.
Read `brief.md` first." Wait for it. Review (step 5). When accepted, write
`<run>/shared-context.md`: the hero's style family, the URL of its photo
panel (never the composite), its palette and subject in two lines, and "use
as `imageUrls` reference for the anchored pattern".

## 4. Wave 2: everything else

Spawn one `section-worker` per remaining section, in the background, in
parallel, same prompt shape. Their briefs now include `shared-context.md`.

## 5. Review each finished worker

Spawn a `section-reviewer` with: the brief path, the section folder (it reads
`workflow.yaml`, `result.md`, `steps/`), and `<run>/ledger.jsonl`. It writes
`review-N.md` with `verdict: accept | rework | block` and numbered change
requests tied to workflow steps. Decide:

- accept: mark it in the report.
- rework: SendMessage the same worker: "Rework: re-run from step N. Changes:
  ..." (its context is intact). At most 2 rework rounds per section.
- after 2 rounds: accept the best candidate the reviewer names, or mark the
  slot blocked with the reason.

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
   kept-from-source and blocked slots; balance delta versus ledger sum.

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
