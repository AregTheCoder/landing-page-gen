# Evaluation

Used three times: at every node's gate (worker), on the final asset (worker
self-eval, then reviewer), and on the board itself (reviewer).

## Asset rubric, score 1–5 each

| Key | Question |
|---|---|
| fit | Does the composition plan — its Device and its panels — demonstrate the section's `> device:` claim (references in, one style across a set, two outputs, chosen among models, the output applied), so a reader of the H2 sees it proved and not a generic version of the copy? `fit` judges the **plan**, not the drawing: a plan that shows the wrong device or the wrong panels for the copy is a fit defect (a manager gap); a right plan rendered wrong is a `composition` defect, not a fit one. A `none` composite where the line names a device is a 2. |
| composition | For a composite (a slot with a `composition-<slot>.yaml` plan): is every chrome item the plan lists present in the render, in the place the plan puts it, carrying exactly the plan's label text and no other — nothing drawn twice, nothing the plan omits, nothing the plan does not list? One item missing or mis-placed is a 3; a label the plan does not carry is a 1. `5` when the slot has no composition plan (not a composite). The worker adds only panel image paths to the spec (`spec-from-plan`), so a composition defect is a render or wiring fault, not an invented item — precheck diffs the spec against the plan. |
| resemblance | Do the panels match the brief's Style family and its ground variant (panel count, ground, chrome, subject, framing, safe area, nothing from its Never list), and does the composite sit beside the family's examples for this slot class? A still life or perspective render for a flat composite family, or a black composite briefed as `/light`, is a 1. |
| consistency | Same palette, light and finish as the hero / shared context, and across every member when the brief names a Series? |
| clean | No logos, watermarks or UI, and no text beyond the brief's `## Text in image` strings? Chrome drawn by `lp-compose` is clean only when its labels are the composition plan's (Before, After, x2, 4K, a size string — the manager's strings, drawn by compose) and none duplicates a model-rendered string. (a failure here is a hard reject) |
| text | Every string in `## Text in image` present, spelt and cased exactly, in the panel and position the brief names, readable at the slot size, in a typeface that suits the family? `5` when the table is `none` and the image carries no text. (a wrong or extra word is a hard reject) |
| artefacts | Faces, hands, products, edges: nothing wrong at 100 % zoom? |
| geometry | Right aspect for the slot; enough resolution; subject survives the slot's crop? Composites at the slot's natural size with unstretched panels? |
| legibility | If HTML text overlays this slot, is the area behind it quiet enough? |

Accept: no score below 3, `fit` >= 4, `clean` = 5 and `text` = 5, and (on a
composite) `composition` >= 4. Otherwise rework with the lowest key named
first. `fit` and `composition` name different fixes: a low `fit` sends the
slot back to the manager (wrong plan for the copy); a low `composition` is the
worker's to re-render.

### Video keys (a video slot adds these three; scored on the strip, never on the URL)

The worker writes `steps/<slot>-<node>-strip.png` (first, middle, last frame,
`uv run lp-corpus frames <clip> --out <strip>`) at every video gate; the
reviewer reads the same file and regenerates it with that command when it is
missing. `picsart_media_probe_media` gives the length and fps.

| Key | Question |
|---|---|
| first_frame | Is the strip's first frame the accepted still (same subject, framing, palette, no re-render)? A clip that opens on a different picture is a 1. (below 4 is a hard reject: the poster and the clip would disagree) |
| motion | Does what changes across the strip match the node's prompt and the family's **Motion:** line (kind, camera, pace), with no morphing, no added or lost elements, no animated typography? (below 3 is a rework) |
| loop | Does the last frame return to the first (a seam a muted autoplay loop hides), and is the measured length within 1 s of the brief's target duration? A 5 s clip in a 10 s slot is a 2 regardless of seam. (below 3 is a rework) |

## Workflow rubric, score 1–5 each

| Key | Question |
|---|---|
| justified | Is every node needed and the recipe right for the slot and its source media? For composites: family matches the brief, one generate per distinct panel, before/after pairs from one photo? |
| gated | Was each node gated with a note that says what was seen, not just "ok"? |
| quote_respected | Preflight before every paid node; `credits.spent` equals the ledger; within the slot cap? |
| board | Does `flow.md` read as a Flow a person could rebuild: every node one creative step on one model, `in:` wiring true to the placeholders, START carrying only allowed REFs? A template board: does `fits` cover the family and device, does `adapted` say what changed, and did the template move nothing an invariant pins? A blank board where a fitting template existed is a 4 with a note, never a rework. |

## Reviewer output: review-N.md

For a composite slot, read `composition-<slot>.yaml` (the plan) before the
pixels: it lists the panels and every chrome item, so the `composition` score
is the render against that plan, not a guess at what the family draws.

```markdown
---
section: S03
class: callout-1:1
style: before-after
verdict: accept | rework | block
round: 1
scores: {fit: 4, composition: 5, resemblance: 3, consistency: 5, clean: 5, text: 5, artefacts: 4, geometry: 5, legibility: 4}
# a non-composite slot has no plan: composition is 5
# a video slot: ..., legibility: 4, first_frame: 5, motion: 4, loop: 4}
workflow_score: {justified: 4, gated: 5, quote_respected: 5, board: 5}
best_candidate: https://...
---

## Changes requested (tied to nodes)
1. node 1: prompt lacks the product; add "..." and drop "...".
2. node 3: enhance blurred the face; use topaz-upscale-image.

## Composition (composite slots)
Per plan item: present, placed, labelled as the plan says — or what is off.

## Notes
What the examples do that this asset does not.
```

`block` is for slots that cannot be produced within the rules (needs UI,
needs a real person, brief contradiction). Say what a human must decide.
