# Compose-template standard — audit verdicts and the standing rules

A per-family audit (2026-09-15) checked every `lp-compose` template in
`src/landing_page_gen/compose/families.py` against the real corpus assets it
claims to represent (sampled from `corpus/styles.yaml`, every sample viewed).
Per-family evidence and corrected specs are in the sibling files
(`dark-composite.md`, `before-after.md`, …). This file is the index, the
cross-cutting findings, and the rules that keep the templates honest.

## Verdicts

| family | verdict | matched the real modal? | grounds correct? | built from |
|---|---|---|---|---|
| dark-composite | **FALSE** | 0 / 13 | no (black ok, but column on wrong side, wrong boxes) | 1 exemplar, since re-tagged away |
| template-mockup | **FALSE** | 1 / 14 | no — real is transparent, not white | 1 exemplar |
| before-after | half-faithful | 1 / 20 (the rarest layout) | no — real is transparent | 1 exemplar |
| crop-frame | half-faithful | 1 / 13 (geometry ok there) | no — real is black, doc says white | 1 exemplar |
| cutout-checkerboard | half-faithful | skeleton real (4604e99a) | no — real is transparent, not black | 1 exemplar |
| panel-overlay | faithful geometry | 5 / 5 (hsl-color) | ok (transparent) | the 5 real assets |

## The five cross-cutting failures (why the templates drifted)

1. **Single-exemplar templates.** Every template was measured off ONE hand-picked
   asset and generalised to a whole family. The modal real layout was never
   consulted, so 4 of 6 encode a rare or unique arrangement (before-after's
   square is 1/20; crop-frame's is 1/13).
2. **Grounds misread as opaque.** 4 of 6 real families are **transparent**
   artwork (the page section supplies white/black); one is **black**. Our
   templates paint an opaque ground. The likely cause is an RGBA→RGB read that
   makes a transparent gutter look black (the before-after auditor reproduced
   this illusion).
3. **Invented chrome.** dark-composite's "4K" resolution chip and sparkle/crop
   icons appear in **0** sampled assets; template-mockup's blank headline bars
   appear in **0**. Real recurring chrome (a magenta accent tile, a selection
   frame with handles, colour-swatch tiles, a 3×3 crop grid) is **undrawn**.
4. **Evidence rot.** The assets several templates and the `style-families.md`
   **Examples** lines were built on have since been **re-tagged to other
   families** (e.g. dark-composite's `4eeca13c`/`86f73fc9` → `full-bleed`,
   template-mockup's `21cdafd9` → `dark-composite`). Nothing re-checked the
   template when its evidence moved.
5. **Noisy tag populations.** `taxonomy.family_of` over-fires on crop-frame
   (~half the 58 tags are `pastatic` designed-template mockups), before-after
   (17 VS cards, mistagged), cutout-checkerboard (4/13 off-family), and
   panel-overlay (21/28 are other panel designs). Counts can't be trusted until
   a labelling pass cleans these.

## The standing rules (institute these)

- **A template must match its family's MODAL layout, not one exemplar.** Before
  writing or changing a template, sample ≥10 currently-tagged assets across
  pages, view them, and template the most common arrangement; rarer real
  arrangements become named `variants`, never the default.
- **Ground is measured from the alpha channel, never from a flattened RGB read.**
  Corpus callout artwork is transparent unless the pixels prove a painted
  ground; `families.py` `ground.fill` is `None` (transparent) by default.
- **Every chrome element cites a living asset.** No element ships that isn't in
  the current sample; the citation (asset id) lives in a comment next to it.
  When an asset that a template cites is re-tagged, the template is re-audited.
- **`style-families.md` Examples lines must be re-derived from `styles.yaml`,
  not hand-kept** — a test (or `styles` step) should fail when a cited id is no
  longer tagged that family.
- **Clean the tag population before trusting counts** — a `/label-corpus` pass
  over the flagged families precedes any recount.

## Implementation status

Corrected default templates + ground fixes land in `families.py`
(see the commit); each is re-rendered and eyeballed against a cited real asset.

Deferred (need a new worker panel input or a new draw primitive, each with its
own verification): cutout-checkerboard **partial-fill checker** (needs the
pre-removal frame as a second input); template-mockup **selection-frame**,
**swatch-stripe tile** and **/editor** exploded view; crop-frame **crop-grid**
overlapping-cards and **label-card** variants; dark-composite **compare-labels**
and **bottom-row** variants. These are specified in the per-family files.

Data follow-ups (separate from the templates): re-tag the noisy populations,
and add the Examples-line consistency check.
