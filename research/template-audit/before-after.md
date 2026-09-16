# Template audit: before-after

2026-09-15. Does the `before-after` entry in `src/landing_page_gen/compose/families.py`
(and the `## before-after` block in `.claude/skills/picsart-workflows/style-families.md`)
match the real corpus assets tagged `style: before-after`?

Method: parsed `corpus/styles.yaml` (73 entries, 72 images + 1 webm), located every
image in `corpus/pages/<page>/media/`, machine-classified all 72 by alpha structure
(transparent gutters = composite card), viewed 15 of them (10 sampled across pages +
5 follow-ups), and measured panel rects of 6 composites by connected components on
the alpha channel. No paid calls.

## (a) Per-asset inventory (viewed sample)

| # | asset | page / slot | size | ground | panels | pills / labels | tile / icons | arrows-sliders | text in panels |
|---|-------|-------------|------|--------|--------|----------------|--------------|----------------|----------------|
| 1 | 69ed3f5c | image-enlarger S08-m1 | 1600² | **transparent** (32 px gutters) | before 604x632 TL, after 604x632 below, result 964x1600 R (bus-stop poster mockup of the after) | translucent dark "Before"/"After" pills bl of the two small panels | black tile 604x272 bottom-left, enlarge icon | none | poster copy inside the result mockup |
| 2 | 15c37bff | ai-image-enhancer S01-m1 | 1600² | none (full-bleed) | 1 (blurred before photo) | solid-dark "Before" pill bl | none | none | none |
| 3 | f1fec5c1 | background-changer S07-m1 | 1600² | none | 1 (before photo) | light translucent "Before" pill bl | none | none | none |
| 4 | 4418775b | compare-models--imagen-4-0-ultra… S02-m1 | 1600² | transparent | two tall panels side by side | none | white circular **VS badge** centre; two black label bars bottom with model logo + name | none | model names in chrome |
| 5 | 3866877e | compare-models--nano-banana-2… S06-m1 | 1600² | transparent | two tall panels side by side | none | VS-card chrome variant: two black model label bars bottom | none | model names |
| 6 | 9ab0394d | ai-replace S07-m1 | 1600² | none | 1 (before photo) | solid-dark "Before" pill bl | none | none | none |
| 7 | ad4a1557 | image-upscale S10-m1 | 1600² | transparent | **6 panels**: before 520x788 TL + x4 label tile 232x376 + enlarge icon + scribble panel 784x656 TR + after 784x784 BL + result 784x912 BR | solid black "Before"/"After" pills bl of before and after | "x4" text + enlarge icon on the ground between panels | red scribble markup in one panel | "x4" |
| 8 | bcc56313 | photo-effects S10-m1 | 1600² | transparent | before 656x1052 TL, result 912x1600 R (no separate after panel) | **light** translucent "Before" pill bl of before, "After" pill bl of the **result** | black tile 656x516 bottom-left, "fx" glyph | none | none |
| 9 | 54964550 | red-eye-remover S02-m1 | 600x450 | none | side-by-side halves, thin gutter | yellow parallelogram "BEFORE"/"AFTER" labels (off-brand, legacy) | none | none | labels only |
| 10 | 06bfdecd | aura S08-m1 | 400x400 | none | one photo split by a vertical **wipe divider** | none | slider handle on the divider; dark prompt caption bottom ("Teleport them to…") | slider | prompt text |
| 11 | 0b0a14f9 | hd-photo-converter S01-m1 | 1600² | none | 1 (before photo) | translucent dark "Before" pill bl | none | none | none |
| 12 | 08385997 | ai-image-enhancer S09-m1 | 1060x504 | transparent, 16 px outer margin | before 388x328 TL, result 632x472 R | solid black "Before" pill bl of before, "After" pill bl of the **result** | black tile 388x136 below the before, image-sparkle icon | none | none |
| 13 | c5715e9b | image-upscale S07-m1 | 1060x504 | transparent, 16 px margin | before 388x328 TL, after 288x472 M, result 336x472 R (framed poster mockup) | black "Before"/"After" pills | black tile 388x136, image-sparkle icon | none | poster copy in the result mockup |
| 14 | 063c75bf | image-upscale S06-m1 | 1600² | transparent | before 784x1188 TL, result 784x1600 R (poster mockup) | **no pills** | **two** tiles bottom-left 376x380 each: "x2" label tile + enlarge icon tile | none | "x2"; poster copy in result |
| 15 | dae3bcef | ai-design-generator S08-m6 | 1600² | transparent | prompt card + palette strip + website mockup | none | Generate button | none | prompt + mockup copy — **misclassified**, not before-after |

Local files: first-8-hex prefix under `corpus/pages/<page>/media/`; converted copies
in `/tmp/audit-before-after/`.

## (b) Population and modal layouts (all 72 images, machine-classified)

| class | n | what it is |
|-------|---|------------|
| single square panel (no alpha) | 29 | one photo, full-bleed, usually one "Before" or "After" pill bl — a **pair half**; its sibling (`S0x-m2`) is tagged `full-bleed` (checked on ai-image-enhancer S01, ai-replace S07, hd-photo-converter S01) |
| single rounded panel | 6 | small legacy images (red-eye-remover, image-tools, draw…), off-brand labels |
| vs-card (all on compare-models pages) | 17 | two tall panels side by side, white round VS badge, black model-name label bars — **model comparison, not before/after**; belongs with dark-composite/compare, not this template |
| composite card | 20 | transparent ground, multiple panels, 32 px (square) or 8 px (wide) gutters |

Composite breakdown (the population the template exists for):

- **Wide card 1060x504 (or 2120x1008 retina): 14 of 20 — the modal composite.**
  16 px transparent outer margin, 8 px gutters; before 388x328 top-left with a
  solid black "Before" pill bl; black icon tile 388x136 under it; result 632x472
  right with the "After" pill bl **on the result**. One 3-column variant
  (c5715e9b: before | after | framed mockup). Found on tool pages *and* ai-models
  pages (flux-3, hailuo-3, grok-imagine, recraft…, imagen-4-0) and video pages.
- Square card 1600x1600: 5 (plus 1 misclassified). Every one different:
  - 69ed3f5c: stacked pair + tile left, result right — **the layout the current
    template encodes, n=1**.
  - bcc56313: before + big tile left, result right (no after panel; After pill on result).
  - 063c75bf: before + two tiles (x2 label, enlarge) left, poster-mockup result right, no pills.
  - ad4a1557: six-panel editing story (before, x4 tile, scribble markup, after, result).
  - dae3bcef: prompt-generate card, misclassified.

## (c) Verdict

**Half-faithful.** The template's geometry is a near-exact measurement of one real
asset — but only that one — and its ground colour is wrong for all of them.

Faithful:
- Panel rects match 69ed3f5c within 6 px: measured before (0,0,604,632), after
  (0,664,604,1296), tile (0,1328,604,1600), result (636,0,1600,1600) vs template
  (0,0,600,630) / (0,660,600,1290) / (0,1320,600,1600) / (630,0,1600,1600). Gutter 32 px, radius ≈ 36–40 (template 40 ok).
- Pill style: measured pill is semi-transparent dark with white text; renderer's
  `translucent` = (30,30,30,150) + white matches. Positions bl of the two small
  panels match 69ed3f5c.
- Tile: black rounded square with a white line icon, correct (measured fill
  #1c1c1c vs renderer default #000000 — a nuance, cf. the dark-composite tile note).

False / divergent:
1. **Ground: template fills BLACK; every real composite is TRANSPARENT** (alpha-0
   gutters, the page shows through — same treatment as crop-frame's `fill: None`).
   Rendered on a white page, the current template paints black bars where Picsart
   shows white. Biggest single error.
2. **The encoded arrangement is the rarest real one.** Stacked-pair-plus-result
   square = 1 asset of 72. The modal composite (14) is the wide ~2.1:1 card with
   ONE small before panel + tile on the left and the result right; there is no
   after panel and the After pill sits on the result.
3. Sample-wide, the "After" pill lives on the LARGE panel except in 69ed3f5c and
   ad4a1557; pill fills vary (solid black on the wide cards, light translucent on
   photo-effects) — translucent dark is a fair default but not universal.
4. The `result` panel is frequently an applied MOCKUP of the after image (bus-stop
   poster, framed print with its own headline copy), not the after image plain —
   the families-doc line "`result` reuses B with an anchor on the subject"
   under-describes what the corpus actually shows (5 of the 8 composites viewed).
5. 17 of the 72 tagged assets are compare-models VS cards and 1 is a
   prompt-generate card — tagging noise that inflates this family and would poison
   `similar` retrieval for it.
6. Half the tagged population (35) isn't a composite at all but a single pair-half;
   style-families.md already knows this ("hero pair … briefed as full-bleed"), so
   no template change needed, but the numbers show it is the majority case.

## (d) Corrected spec (evidence-cited)

Keep 1600 REF. Fix the ground and re-centre the family on the wide card; keep the
measured square as a variant since it is real (69ed3f5c).

```python
"before-after": {
    # modal layout: the wide card, 14/20 corpus composites, e.g. 08385997
    # (ai-image-enhancer S09-m1), c5715e9b (image-upscale S07-m1). Measured at
    # 1060x504 and scaled x1.5094 to REF width: margin 16->24, gutter 8->12.
    "aspect": (21, 10),                      # 1060x504 = 2.103:1
    "ground": {"fill": None},                # transparent — all 20 composites; alpha-0 gutters measured
    "radius": 40,
    "panels": {
        "before": {"rect": (24, 24, 610, 519)},     # 388x328 at native
        "result": {"rect": (622, 24, 1576, 737)},   # 632x472 at native
    },
    "chrome": [
        {"id": "before-pill", "kind": "pill", "at": "before", "corner": "bl", "text": "Before", "style": "solid-dark"},   # solid black on the wide cards (08385997)
        {"id": "after-pill", "kind": "pill", "at": "result", "corner": "bl", "text": "After", "style": "solid-dark"},     # After sits on the RESULT (08385997, bcc56313)
        {"id": "tile", "kind": "tile", "rect": (24, 531, 610, 737), "icon": "enhance"},   # 388x136 native, image-sparkle glyph
    ],
    "variants": {
        # the 1:1 stacked pair, measured from 69ed3f5c (image-enlarger S08-m1) — the current template, corrected
        "stacked-square": {
            "aspect": (1, 1),
            "panels": {
                "before": {"rect": (0, 0, 604, 632)},
                "after":  {"rect": (0, 664, 604, 1296)},
                "result": {"rect": (636, 0, 1600, 1600)},
            },
            "chrome": [
                {"id": "before-pill", "kind": "pill", "at": "before", "corner": "bl", "text": "Before", "style": "translucent"},
                {"id": "after-pill", "kind": "pill", "at": "after", "corner": "bl", "text": "After", "style": "translucent"},
                {"id": "tile", "kind": "tile", "rect": (0, 1328, 604, 1600), "icon": "enlarge"},
            ],
        },
    },
},
```

Also update style-families.md `## before-after`: Ground line "black (default)" ->
"transparent (all composites; the pair halves are full-bleed with no ground)";
Grid line gains the wide card as the default; note that `result` may be an applied
mockup of the after image on upscale/enlarge pages.

## (e) Open questions

1. Which slot ratio do the wide 1060x504 cards actually fill in the HTML
   (callout-2:1?), and should the skeleton's `> style:` line carry the ratio so
   the manager picks wide vs square? The template today only claims 1:1 (480).
2. Should the 17 compare-models VS cards get their own style (or a dark-composite
   variant with VS badge + model label bars) and be re-tagged out of before-after?
   They dominate the family's high-confidence tail (0.9–0.95) and will surface in
   `similar --style before-after` for tool pages.
3. Is a mockup-style `result` (poster/frame of the after image) in scope for a
   worker, or does "result reuses B" stay the rule? 5 of 8 viewed composites use a
   mockup; producing one needs an extra generate or a template-mockup-style step.
4. The wipe/slider look (aura, 2 assets) is on the family's Never list yet exists
   in corpus — keep forbidding (it's an interactive-UI still), or split off?
5. dae3bcef (ai-design-generator S08-m6) is a prompt-generate card mis-tagged
   before-after; worth a rules fix or a label-sheet answer.
6. Renderer tile default is pure black (0,0,0); the measured tiles are #1c1c1c.
   Align with the dark-composite lesson ("a step lighter so the edges read")?
