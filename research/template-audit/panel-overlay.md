# Template audit: panel-overlay

2026-09-15. Compared `FAMILIES["panel-overlay"]` (src/landing_page_gen/compose/families.py:140-153)
and the `## panel-overlay` block (`.claude/skills/picsart-workflows/style-families.md:351`)
against the corpus assets tagged `style: panel-overlay` in `corpus/styles.yaml`
(28 entries, 26 distinct assets, 2 videos). 14 image assets across 11 pages were
viewed at ≤700px (`/tmp/audit-panel-overlay/`); the five hsl-color assets were
also measured pixel-wise (dark-neutral mask, scaled to the 1600x1200 REF frame).

Naming note: styles.yaml keys carry the CDN uuid (`48531286…`), local files pair
it with the corpus hash (`48531286…-85708ef3.png`). The doc's example ids
(85708ef3, da31e929, 0c9be8c4, 9caa06ad, e9c17dd8) are the hash halves of the
same five files — not stale.

## (a) Per-asset inventory

Canonical core — hsl-color, confidence 0.85-0.9, all 524x393 native (4:3):

| asset | slot | what is actually there |
|---|---|---|
| 48531286 / 85708ef3 | S01-m1 hero | Man, round glasses, magenta/cyan gel light on lavender ground, subject centre-left. Upper right: white circular badge (black tri-circle HSL mark) with a white label pill "HSL" directly below, pointer on the pill's top centre pointing up at the badge. No adjust panel. Measured (REF frame): badge dia ~260 at y 137-397, pill ~440x143 at y 443-586; whole block ≈ (1100,137)-(1540,586) — template rect (1080,120,1520,620) fits. |
| 48790089 / da31e929 | S03-m1 lead card | Woman in red/white stripes dancing before a rainbow-striped wall, subject in left third. Dark panel lower right, measured ≈ 810x640 at (675,305) (template: 810x600 at (680,300) — match within ~7% height). Header: tri-circle mark, "HSL", small TEAL CIRCLE badge with a white glyph inside, chevron-up far right, hairline separator under the header. 8 hue chips — ROUNDED SQUARES, not circles — red orange yellow green turquoise blue purple pink; active = 2nd (orange), ringed WHITE. Three sliders: Hue 28, Saturation -26, Lightness 30; grey label left, white track + white knob, dark (#303034-ish) value chip right. |
| 12481028 / 9caa06ad | S03-m2 tilted | White page ground; blue-grey plain card rotated one way, photo card (woman, white knotted shirt, multicolour striped skirt, sky/concrete) rotated the other. Panel sits LEVEL (unrotated) at the photo card's LEFT edge, overhanging onto the white ground, ≈ (211,388), width ~810: header + 8 chips (orange active, white ring) + ONE slider: Hue 28. |
| 27148736 / 0c9be8c4 | S03-m3 | Woman, red eyeshadow, purple blouse, flat yellow ground, subject fills left/centre. Compact panel lower right ≈ 840x280 at (690,760): header + ONE slider: Saturation 43. NO chips row. |
| 61572740 / e9c17dd8 | S03-m4 tilted | White ground, tilted stack (back card light grey), woman with iridescent fringe, soft high-key light. Level panel lower left ≈ (305,711): header + ONE slider: Lightness 30. No chips. |

Other pages tagged panel-overlay (confidence 0.3-0.6) — heterogeneous, mostly
NOT the HSL panel:

| asset | page/slot | conf | what is actually there |
|---|---|---|---|
| 9a29fc3f | brighten-images S05-m1 | 0.45 | White ground, before/after coffee cards; WHITE panel, 4 sliders (Brightness 80, Contrast 85, Highlights 20, Shadows 50), black knobs, light-grey value chips. Still life, no person. |
| 0e6fd8bb | ai-filters S12-m1 | 0.4 | Blue gradient ground, 4 tilted filter cards (NOISE, PLRD, HDR text in-image); small WHITE 3-slider panel (Saturation, Brightness, Contrast), no values. |
| c249a42e | image-style-transfer S01-m1 | 0.55 | Black ground, pink-gel portrait card, style-ref thumbnails with "+" badge; DARK panel, 3 sliders on GRADIENT tracks (Brightness, Temperature, Saturation), no header, no chips, no value chips. |
| 548e38c0 | face-editor S05-m1 | 0.5 | Black ground, portrait on mustard with face-landmark dots; two WHITE list pills (Face, Nose) with icons + chevrons. |
| 2a6c2e04 | design-localization S01-m1 | 0.6 | Black ground, stacked localized poster cards; DARK CHECKBOX panel (English…French, magenta checks). |
| bc5e359e | image-tools S04-m7 | 0.5 | Black ground, pizza photo cards with magenta check badges; WHITE MENU panel, 5 icon+label rows, "Crop" highlighted. |
| 1d8867c2 | watermark-photos S05-m1 | 0.5 | White ground, tilted photo stack, "glimmr photography" watermark w/ selection frame; WHITE "Position" toggle panel + WHITE Opacity 100% / Size 17% slider panel. |
| 3f1d367d | add-shadow-to-image S04-m1 | 0.5 | Black ground, mint still-life card, red sticker shapes w/ selection handles; DARK COLOR-PICKER panel (gradient square, rainbow hue bar, HEX #e03138, RGB values). |
| 245b27b0 | background-remover S17-m3 | 0.6 | Before/after checkerboard cutout + Instagram post mockup. No adjust panel at all — mis-tag. |

Not viewed: 2 videos (266573a7, 4152c4fc), plus 9 more low-confidence images
(background-tools, brand-identity-generator, content-creation-tools, design,
quote-maker=design dup 6bca3aad, face-editor 4e30ac1a, image-style-transfer
d1da1aae, image-tools 68ac744f, social-media-ad-maker, watermark-maker,
video-background-remover).

## (b) Modal layouts

Of the 14 viewed:

1. **HSL dark adjust-panel** — 5/14, all hsl-color, conf ≥0.85. The template's
   true referent. Sub-modes: hero = tool-pill only (1); lead card = header +
   8 chips + 3 sliders (1); Hue tilted card = header + chips + 1 slider (1);
   Saturation/Lightness cards = header + 1 slider, NO chips (2).
2. **White slider panel** — 3 (brighten-images, ai-filters, watermark-photos):
   white card, black knobs, values as plain chips/percent or absent.
3. **List / menu / checkbox panel** — 3 (image-tools, face-editor,
   design-localization); `list-panel` chrome already exists for part of this.
4. **Other chrome** — 2 (color picker; gradient-track dark panel).
5. **No panel (mis-tag)** — 1 (background-remover).

## (c) Verdict

The template is a faithful model of the five hsl-color assets — geometry,
palette, slider labels/values, chip colours and the tool-pill block all check
out within ~5-10% — but it encodes only the LEAD card as the default, and 21 of
the 28 styles.yaml tags (all conf ≤0.6) point at panel designs the template
does not draw at all. Divergences, canonical core first:

1. **Chips are rounded squares, ringed white.** draw.py `adjust_panel` draws
   `d.ellipse` chips and a yellow `(250,215,40)` active ring; every real chip
   row shows squircles with a WHITE ring on the active (orange) chip
   (zoom `/tmp/audit-panel-overlay/zoom_lead_header_chips.png`).
2. **Header details.** Real teal badge is a circle with a small white glyph
   (code: plain teal rounded rect); a faint hairline separator runs under the
   header row (code: none). Chevron-up matches.
3. **Default chrome = lead card only.** Real siblings are header + ONE slider
   (Saturation 43 / Lightness 30) with chips only on the Hue card. The spec
   mechanism covers this (`chrome: {panel: {chips: 0, sliders: [[Saturation, 43]]}}`
   merges by id, cli.py `resolve`), and style-families.md says "three on the
   lead card, one on the others" — but neither names the no-chips rule nor the
   43 value; a worker copying the template default puts chips + 3 sliders on
   every card.
4. **Tilted variant rotates the panel.** `compose()` draws all chrome, then
   `tilted_stack` rotates the finished card — so the panel tilts with the
   photo. In both real tilted assets (9caa06ad, e9c17dd8) the panel stays
   LEVEL over the rotated photo card and overhangs the card edge onto the
   white ground. Back card is light grey in one (matches `back=(236,236,238)`)
   but blue-grey in the other.
5. **Tool-pill proportions.** Real badge dia ≈ 0.59 of the block width with a
   ~46px gap to the pill; code uses `dia = w*0.42` and anchors the pill to the
   rect bottom, leaving a ~175px gap. Rendered block reads smaller-badge,
   floaty-pill vs the original.
6. **Compact single-slider panel geometry.** Real S03-m3 panel is ~840x280 at
   (690,760) — the code's auto-grow (`need = …`) shrinks correctly when
   sliders=1/chips=0, but the template rect keeps y0=300, leaving the panel
   high; real singles sit low (y0 ≈ 710-780).
7. **Tag noise.** 245b27b0 and likely f71cbbc1 (background-remover) carry no
   panel; brighten-images breaks the "subject=person" signature (coffee still
   life). The white-panel and list-panel designs are a different family (or
   `panel` variants), not instances of this template.

## (d) Corrected spec (evidence-cited)

`families.py` "panel-overlay":

```python
"panel-overlay": {
    "aspect": (4, 3),
    "aspects": ((4, 3), (5, 4)),
    "ground": {"fill": None},
    "radius": 40,
    "panels": {"photo": {"rect": None}},
    "chrome": [
        # lead card (da31e929): header + 8 chips + 3 sliders, lower right
        {"id": "panel", "kind": "adjust-panel", "rect": (680, 300, 1490, 900),
         "title": "HSL", "chips": 8, "active": 1,
         "sliders": [["Hue", 28], ["Saturation", -26], ["Lightness", 30]]},
        # hero (85708ef3): badge+pill block upper right
        {"id": "tool-pill", "kind": "tool-pill", "rect": (1080, 120, 1520, 620),
         "text": "HSL", "icon": "wheel"},
    ],
},
```

keeps its rects (measured: panel 810x640 at (675,305); pill block
(1100,137)-(1540,586)) — no geometry change needed. Renderer fixes:

- `adjust_panel`: chips as `rounded_rectangle` (radius ≈ dia*0.3), active ring
  white `(255,255,255)` [zoom_lead_header_chips]; hairline separator under the
  header (1px, ~(60,60,64)); teal badge as a circle with a small white inner
  mark [same zoom].
- `tool_pill`: `dia = w*0.59`, pill top at badge bottom + ~0.09*h
  [85708ef3 measurements above].
- `tilted_stack` (or compose order): draw the adjust-panel AFTER the tilt —
  rotate photo card + ground stack first, composite the level panel last, at
  the card's lower/left edge so it overhangs [9caa06ad, e9c17dd8].

Doc/spec guidance (style-families.md **Grid**): "eight hue chips" → "eight hue
chips on the lead and Hue cards only; Saturation/Lightness cards carry the
header and their one slider (Saturation 43, Lightness 30 in the originals) and
sit lower (panel ≈ 840x280 at (690,760))" [0c9be8c4, e9c17dd8]. Workers reach
this with `chrome: {panel: {chips: 0, sliders: [["Saturation", 43]], rect: …}}`.

## (e) Open questions

- Should the white slider panel (brighten-images, ai-filters, watermark-photos)
  become a `variant` of panel-overlay or its own family? 3+ corpus assets, a
  distinct light palette, and one is a no-person still life — the current
  **Never**/"subject=person" lines contradict it.
- Retag or accept the ≤0.6 tags? background-remover 245b27b0/f71cbbc1 have no
  panel; design-localization/image-tools/face-editor are list-panel designs
  (a `list-panel` chrome kind already exists). The rules tagger appears to fire
  on "photo + any floating UI card".
- Tilted back-card colour: light grey (e9c17dd8) vs blue-grey (9caa06ad) —
  parametrize `back=` or keep grey?
- What does the teal badge glyph actually depict (looks like a small white
  rectangle/replay mark at native res — too small to resolve at 524px; the
  1600px original wasn't in the snapshot)?
- Videos 266573a7 / 4152c4fc unviewed; unclear whether any video genuinely
  carries the panel.
