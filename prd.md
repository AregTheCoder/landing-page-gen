# PRD: landing-page-gen

## Problem

A landing page needs a dozen or more visuals that read as one campaign and
match how Picsart already presents itself. Producing them by hand, one
generation at a time, does not scale and loses the reasoning behind each
asset.

## Input

`runs/<run>/skeleton.md`: page frontmatter (brand, audience, defaults,
budget, notes), one H2 per section with all text and a `slot` block per
media node, annotations as blockquotes. Produced by `lp-corpus skeleton`,
edited by hand.

## Output

`runs/<run>/dist/index.html` with every `creative` and `thumbnail` slot
filled by a worker's accepted workflow result; `report.md` listing per slot
the workflow, credits quoted vs spent, review rounds and verdict; a complete
`workflow.yaml` and `result.md` per section.

## What "satisfactory" means

The rubric lives in the `picsart-workflows` skill (`evaluation.md`). Rules
below are lessons that reviews teach; each adds one line with the run that
taught it.

- Still-to-motion whose motion reshapes or reframes the picture needs a still
  with visible edges and margin (a print on a plain backdrop), not a
  full-bleed scene; a full-bleed still gives the video model nothing to move.
  (runs/dry-1 S01, review 1)
- Every video step states `generateAudio: false`, `async: true` and ends its
  prompt with ", no text or logos"; the reviewer checks the yaml, not the
  intent. (runs/dry-1 S01, review 1)
- A worker's "examples share finish X" claim must hold for every example it
  names; say which examples differ. (runs/dry-1 S01, review 1)
- Anything the call must carry (`async: true`, `generateAudio: false`) lives
  in the step's `params`, never only in its `note`; `params` is what is sent.
  (runs/dry-1 S01, review 2)
- Anchored takes light and palette from the hero; subject and composition
  come from the section's annotation and its examples. A detail callout is an
  edge-to-edge macro; the floating print is the hero's composition, not the
  page's. (runs/dry-1 S07, review 1)
- One finish instruction per prompt. When the annotation names a finish (flat
  3D render), the shared context contributes light and palette only; two
  finishes in one prompt is a rework. (runs/dry-1 S08, review 1)
- A set of card thumbnails shares one prompt envelope (container, backdrop,
  shadow, light) with the slot subject as the only variable, and a cross-slot
  gate that rejects any member that breaks the set. (runs/dry-1 S11, review 1)
- A gate with `count` > 1 says how the pick is made, has a failure branch, and
  when lp-inject will crop the output it checks that the subject sits inside
  the slot's safe band. (runs/dry-1 S06 and S08, review 1)
- Thumbnails under about 400 px go to `gemini-3.1-flash-image` at a native
  ratio (5:4 exists there, 3 credits) rather than the pro model cropped; pro
  fidelity is invisible at that size. (runs/dry-1 S11, round 2)
- `gemini-3-pro-image` with `count: 2` returned one image and charged for two
  (10 credits, twice). Use `count: 1` and re-run for a second candidate; the
  ledger, not the response, says what was paid. (runs/trial-1 S07)
- The look of a tool-page image is its style family
  (`picsart-workflows/style-families.md`), not its copy or alt. The skeleton
  names the family per slot (`> style:`), the brief carries the family
  block, `similar --style` picks same-family examples. A physical still
  life where the family is a flat composite is a `resemblance` 1.
  (runs/trial-1 S07)
- Composite slots: the worker generates the photographic panels only;
  ground, panels and chrome come from `lp-compose` with the family template,
  so `clean` is scored on the panels and chrome text is limited to the
  family's labels (Before, After, x2, 4K, a size). (runs/trial-1 S07)

## Non-goals

- Writing or rewriting page copy.
- Generating product UI screenshots, icons or decorative brand assets.
- Drawing panel chrome (tiles, pills, brackets, checkerboards) with a
  generative model; `lp-compose` draws it.
- Producing the production Next.js page; the output is a snapshot.

## Budget

Default run cap 300 credits, enforced by hook. Per-slot caps are advisory
(image 20, video 60) and reviewed against the ledger.
