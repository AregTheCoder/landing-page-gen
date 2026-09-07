# Evaluation

Used three times: at every step gate (worker), on the final asset (worker
self-eval, then reviewer), and on the workflow itself (reviewer).

## Asset rubric, score 1–5 each

| Key | Question |
|---|---|
| fit | Does it illustrate this section's text and annotation, not a generic version of it? |
| resemblance | Do the panels match the brief's Style family (panel count, subject, framing, safe area, nothing from its Never list), and does the composite sit beside the family's examples? A still life or perspective render for a flat composite family is a 1. |
| consistency | Same palette, light and finish as the hero / shared context? |
| clean | No model-generated text, logos, watermarks or UI? Chrome drawn by `lp-compose` is clean only when its labels are the family's (Before, After, x2, 4K, a size string). (a failure here is a hard reject) |
| artefacts | Faces, hands, products, edges: nothing wrong at 100 % zoom? |
| geometry | Right aspect for the slot; enough resolution; subject survives the slot's crop? Composites at the slot's natural size with unstretched panels? |
| legibility | If HTML text overlays this slot, is the area behind it quiet enough? |

Accept: no score below 3 and `clean` = 5. Otherwise rework with the lowest
key named first.

## Workflow rubric, score 1–5 each

| Key | Question |
|---|---|
| justified | Is every step needed and the pattern right for the slot and its source media? For composites: family matches the brief, one generate per distinct panel, before/after pairs from one photo? |
| gated | Was each step gated with a note that says what was seen, not just "ok"? |
| quote_respected | Preflight before every paid step; `credits.spent` equals the ledger; within the slot cap? |

## Reviewer output: review-N.md

```markdown
---
section: S03
style: before-after
verdict: accept | rework | block
round: 1
scores: {fit: 4, resemblance: 3, consistency: 5, clean: 5, artefacts: 4, geometry: 5, legibility: 4}
workflow_score: {justified: 4, gated: 5, quote_respected: 5}
best_candidate: https://...
---

## Changes requested (tied to steps)
1. step 1: prompt lacks the product; add "..." and drop "...".
2. step 3: enhance blurred the face; use topaz-upscale-image.

## Notes
What the examples do that this asset does not.
```

`block` is for slots that cannot be produced within the rules (needs UI,
needs a real person, brief contradiction). Say what a human must decide.
