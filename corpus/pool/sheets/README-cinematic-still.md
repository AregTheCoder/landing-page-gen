# Pool sheets: cinematic-still (36)

429 pending entr(ies); 0/36 answered.

## Prompt

Review one contact sheet of licensed stock candidates for the `cinematic-still` style family.

**Row 1 is 3 Picsart originals of this family, captioned `ref <id>`.** They are the
target, not candidates: do not judge them. Numbered cells (#1, #2, ...) start on row 2 and
read left to right, top to bottom, best-ranked first; the manifest yaml beside the sheet
names each cell's source.

The photography this family needs:

> Single-subject vertical frames that read like film stills: one person, dish or prop, centred or on a third, shallow depth. Light is deliberate and coloured (teal-orange or red-blue split, warm golden hour, fairy-light bedroom glow) or bold complementary studio colour (yellow food on blue seamless). The grade is unified and saturated, the finish glossy, no chrome or text.

Write <sheet>.answers.yaml beside the sheet, one line per cell:

```yaml
1: keep
2: drop
3: {keep: true, subject: person}
4: {keep: false, best_family: cinematic-still}
5: {keep: true, note: slight text overlay}
```

keep = the photograph a worker could build this family's slot from; drop = off-style,
watermarked, text-heavy, or a near-duplicate of another cell. Judge the photograph only:
the tiles, pills, panels and badges of the family are drawn by lp-compose afterwards, so a
bare photo is what you should be seeing.

`subject` (optional): one of person, product, scene, food, animal, abstract, typography, illustration, object, multiple.
`best_family` (optional): a better-fitting family from dark-composite, before-after, crop-frame, cutout-checkerboard, template-mockup, prompt-card, full-bleed, vs-two-up, mockup-card, cinematic-still, graphic-collage, outcome-tile, editor-canvas, model-card, panel-overlay — a good photo
in the wrong place moves there instead of being lost.
`note` (optional): up to 120 characters, for why a borderline call went the way it did.
Leave a cell out if you cannot judge it; an unanswered cell stays pending.
