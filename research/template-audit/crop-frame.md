# Template audit: crop-frame

2026-09-15. Local-only audit of the `crop-frame` lp-compose template
(`src/landing_page_gen/compose/families.py`) and the `## crop-frame` block in
`.claude/skills/picsart-workflows/style-families.md` against the corpus assets
tagged `style: crop-frame` in `corpus/styles.yaml`. No paid calls; every asset
below was read from `corpus/pages/<page>/media/` (converted to <=700px PNG in
/tmp/audit-crop-frame/). Geometry was measured on the original pixels
(near-black gutters, white-chrome bounding boxes).

Population: 58 tagged entries; 7 videos (skipped), 51 images. Two URL
populations: 29 on `cdn-cms-uploads.picsart.com` (the 1600x1600 composite
cards) and ~22 on `pastatic.picsart.com/cms-pastatic/` (transparent PNGs,
mostly designed-template mockups — see (e)). 16 images viewed across 15 pages.

## (a) Per-asset inventory

| # | asset | page / slot | ground | layout | brackets | label | tile / icon | notes |
|---|-------|-------------|--------|--------|----------|-------|-------------|-------|
| 01 | 25329b09 | crop-image S07-m1 | black | single 9:16 story mock, centre-left | none | dark rounded card bottom-right: "Instagram story" / "1000 x 1500 px" | none | story progress dashes at top of the mock |
| 02 | 4c0b8b9b | crop-image S01-m1 (hero) | black | overlapping cards: back = full photo top-right, front = cropped close-up bottom-left | full crop GRID on back: corner brackets + mid-edge ticks + 3x3 white lines | none | black circular badge, crop icon, left edge | the crop-image signature |
| 03 | 5f91c6aa | resize-image S07-m1 | black | two columns: left 784 = icon zone y 0-390 + source y 392-1600 (dimmed); result x 816-1600 full height | corner brackets + mid-edge ticks, measured x 235-546 (frac 0.30-0.70), y 664-1200 (frac 0.23-0.67 of the source) | "x2" white text on the photo, y 1265-1336, centred under the brackets | bare white OUTLINE enlarge icon on black (no tile fill), x 235-552, y 102-262 | the template's model; matches it almost exactly except ground and tile |
| 04 | df6f0107 | resize-image S06-m1 | black | two columns MIRRORED: left 656 = source y 0-927 (dimmed) TOP, label block BOTTOM on black; result x 680-1604 | corner brackets + ticks on the source | stacked at column bottom: Instagram outline icon + "Story" + "1080 x 1920 px" | platform icon doubles as the tile | second resize variant |
| 05 | 63e561f8 | image-enlarger S05-m1 | black | two columns: left 608 = source y 0-999 top, two tiles below; result x 632-1600 | NONE | dark rounded tile "4x" y 1032-1303 | dark rounded tile with image-sparkle icon y 1328-1600 | no brackets at all |
| 06 | fc1a07de | image-upscale S09-m1 | black | left = settings-UI mock (enlarge icon, "Upscale" heading, two input fields, x4/x2 radio rows); right = blurry small + sharp large panels stacked | none | "x4 Four times", "x2 Two times" as UI rows | outline enlarge icon | UI mock — violates the family's own "Never: UI panels" |
| 07 | 2a96c113 | ai-image-extender S01-m2 (280px) | dark checkerboard | photo with dashed white marquee, four outward arrows | dashed marquee, not brackets | none | none | EXPAND motif, not crop chrome |
| 08 | 15abe5ad | ai-background S08-m1 | black/transparent | checkerboard cutout card + photo card + full website mockup | none | none | none | misfiled; template-mockup / cutout material |
| 09 | 39c8ee3b | photo-editor S12-m1 | black | two columns: left 601 = magenta brand tile 601x601 top, source y 632-1389, label bar y 1422-1600; result x 632-1600 (video poster) | NONE | full-width dark bar "9x16" at column bottom | magenta tile with white Picsart glyph | aspect-ratio label as a bar |
| 10 | b95353fc | batch-photo-editor S11-m1 | black | three floating photo cards, collage | full crop GRID (corners + ticks + 3x3 lines) on EACH card | none | none | batch motif = grid repeated |
| 11 | c78690a2 | crop-image S05-m1 | black | overlapping cards: back photo + grid top-right, front cropped result bottom-left | full crop GRID on back | dark rounded card x~1090-1600, y~870-1290: "Pinterest" / "1000 x 1500 px" | black circular crop badge, d~258, bleeding off the left edge, y 251-509 | layout B + label card |
| 12 | d93605b1 | crop-image S06-m1 | black | overlapping: back photo + grid top-left; front = white Instagram post frame (photo + heart/comment/share/save icons) | full crop GRID on back | none (the Instagram frame IS the format) | black circular crop badge top-right | platform frame as result |
| 13 | 6c64e373 | content-creation-tools S02-m5 (800x600) | light grey/white | single photo card, frame centred on subject | solid white rounded-rect border + mid-edge tick handles | two dark pills "1080" [lock] "1080" bottom-centre under the frame | none | the only white-ground asset seen |
| 14 | 2df735f3 | social-media-ad-maker S07-m1 (pastatic) | transparent | designed 9:16 ad card + faded duplicate behind | none | two white rounded chips: "Instagram Story / 1080x1920" (magenta outline), "Facebook Ad / 1080x1080" | none | format-chip motif on a template-mockup card |
| 15 | 328f7e5d | add-shadow-to-image S07-m1 (pastatic) | transparent | before/after split, checkerboard left, sparkles | none | "Elements" chip | effects tray | misfiled |
| 16 | eadb151d | instagram-post-creator S08-m1 (pastatic) | transparent | gallery of designed posts | none | none | none | misfiled; template gallery |

Not viewed: remaining cms-uploads siblings (crop-image bef623e5; ai-models--*
S04/S07 callouts a16bd5ba, a6439ac4, b0a87ed7, dbddedcf, edb74178, ee36e3a1,
f57cf19d, 7f72e491, 0636dbd7; fa2a98b6, 38d2100f, 7baf8638, b618ca32,
738d1d58) and 7 videos.

## (b) Modal layouts

Of the 13 assets that belong to the family at all (excluding misfiles 08, 15,
16):

- **Layout A — two columns, source left / result right** (4: 03, 04, 05, 09).
  Black ground. Left column 600-784 wide holding the dimmed source photo plus
  an icon/tile and a size label; result panel full height on the right, 780
  (03) to 924-968 (04, 05, 09) wide. Brackets on the source in 2 of 4.
- **Layout B — overlapping crop cards** (3: 02, 11, 12). Black ground. Back
  card = photo with a full crop grid (corner brackets + mid-edge ticks + 3x3
  rule-of-thirds lines); front card overlaps it showing the cropped result (or
  a platform post frame); a black circular crop-icon badge; optionally a dark
  rounded label card "Platform / 1000 x 1500 px". This is the signature of the
  canonical crop-image page.
- **Singles / collages** (3: 01, 10, 13): one framed photo or a batch collage,
  label card or pills, no second panel.
- **Off-family drift** (3: 06 UI mock, 07 expand marquee, 14 format chips on a
  designed card).

No single layout is a majority; A and B together cover 7 of 13.

## (c) Verdict

The current template is a faithful re-creation of exactly ONE asset —
5f91c6aa (resize-image S07): left column 784 with icon on top and source
below, brackets measured at frac (0.30, 0.23, 0.70, 0.67) vs the template's
(0.3, 0.22, 0.7, 0.66), "x2" centred ~65px under the brackets, result 784
wide at x 816. Geometry: excellent match. But as a family representative it
diverges:

1. **Ground is wrong in both template and doc.** `families.py` has
   `"fill": None` (transparent) and style-families.md line 175 says
   "white (default) | transparent". Evidence: 10 of the 13 in-family assets
   are BLACK ground (01-05, 09-12; also 06); white/light appears once (13).
   Black must be the default.
2. **The tile is a stylisation.** In 5f91c6aa there is no filled tile — a bare
   white outline enlarge icon sits directly on the black ground (icon strokes
   x 235-552, y 102-262). Filled tiles do exist in the family but elsewhere:
   05 has two dark rounded tiles at the column BOTTOM ("4x" + icon), 09 a
   magenta brand tile at the top.
3. **The crop-grid variant is unrepresented.** Every crop-image-page asset
   (02, 11, 12) and the batch collage (10) draws corner brackets + mid-edge
   ticks PLUS 3x3 grid lines, on an overlapping-cards layout with a circular
   crop badge. The named family is "crop-frame" yet the template cannot
   produce the crop pages' own chrome.
4. **The label-card treatment is missing.** The most distinctive recurring
   chrome is a dark rounded card "Platform" / "W x H px" (01, 11; chips in 13
   and 14; stacked icon+format+size in 04; "9x16" bar in 09). The template
   only knows a text label under the brackets ("x2"), which occurs once (03).
5. **Result width is split.** 780 (03) vs 924-968 (04, 05, 09). The 600-wide
   left column / ~970 result (matching the before-after grid) is as common as
   the 780/780 split the template hard-codes.
6. **The source panel is dimmed** in the bracketed column assets (03, 04) —
   a dark scrim that makes the white brackets read; the template composites
   the source at full brightness.
7. **Tag noise.** ~22 `pastatic` entries (14-16 sampled) are mostly designed
   template mockups keyed, presumably, on "Instagram Story / 1080x1920"-style
   alt text; plus 06 (settings-UI mock), 07 (expand marquee), 08 (website
   mockup) inside the cms population. The family's effective n is roughly
   half of the tagged 58.

## (d) Corrected spec (1600px frame, evidence-cited)

Default (layout A, the templated one — keeps 5f91c6aa as the model but fixes
ground, dim and tile):

```python
"crop-frame": {
    "aspect": (1, 1),
    "ground": {"fill": BLACK},        # 5f91c6aa, df6f0107, 63e561f8, 39c8ee3b, all crop-image assets
    "radius": 40,
    "panels": {
        # 5f91c6aa: source x 0-784, y 392-1600 (h 1208), dimmed under white brackets
        "source": {"rect": (0, 392, 784, 1600), "dim": 0.35},
        # 5f91c6aa: gutter 784-815, result 816-1600 full height
        "result": {"rect": (816, 0, 1600, 1600)},
    },
    "chrome": [
        # bare white outline icon on the black ground, no tile fill
        # (5f91c6aa icon strokes x 235-552, y 102-262)
        {"id": "icon", "kind": "icon", "rect": (232, 100, 552, 264), "icon": "enlarge"},
        # measured frac (0.30, 0.23, 0.70, 0.67); label ~65px below the bracket bottom
        {"id": "brackets", "kind": "brackets", "at": "source", "frac": (0.30, 0.22, 0.70, 0.66), "label": "x2"},
    ],
},
```

Variants worth templating (in priority order):

- `crop-grid` (02, 11, 12; 10): overlapping cards on black. Back panel
  ~(300, 0, 1450, 960) carrying corner brackets + mid-edge ticks + 3x3 white
  grid lines over its middle ~70%; front result panel ~(0, 480, 1100, 1550)
  overlapping bottom-left; black circular badge d~260 with the crop icon at a
  card corner (11: left edge y 251-509); optional dark rounded label card
  ~510x420 overlapping bottom-right (11: x 1090-1600, y 870-1290) with two
  centred lines: format name ("Pinterest", "Instagram story"), size
  ("1000 x 1500 px").
- `label-bottom` (04, 09): source TOP of the left column (600-656 wide),
  label block at the bottom of the column on black — platform outline icon +
  format name + "1080 x 1920 px" stacked (04), or a full-width dark bar
  "9x16" (09); result 924-968 wide right.
- `tiles-bottom` (05): no brackets; left column 608 = source top, dark
  rounded tile "4x" (y 1032-1303) and icon tile (y 1328-1600) below; result
  968 wide.

Doc fixes for style-families.md `## crop-frame`:
- **Ground:** black (default) | white (6c64e373 content-creation-tools only).
- **Chrome:** add the 3x3 crop grid, the circular crop badge and the dark
  rounded label card; note the source dim.
- **Grid:** correct "left column 780 ... result 780" to note the 600/970
  split is equally attested, and add the overlapping-cards layout.
- The "Never: ... UI panels" rule is contradicted by fc1a07de (image-upscale
  S09) — the corpus itself ships one; keep the rule for generation but expect
  the tag to catch such assets.

## (e) Open questions

1. Should the ~22 `pastatic.picsart.com` entries be re-tagged? Sampled ones
   (2df735f3, 328f7e5d, eadb151d) are designed-template mockups or
   before/after cards, not crop-frame chrome. The rules in
   `corpus/styles.yaml` (`source: rules`) likely key on format/size words.
2. 15abe5ad (ai-background S08) and 2a96c113 (ai-image-extender S01, the
   expand marquee) sit in other motifs — is "expand/extend" its own family or
   a crop-frame variant? The dashed-marquee + outward-arrows chrome recurs on
   extender pages.
3. Which layout should `> style: crop-frame` produce by default for
   crop/resize tools — column A (resize pages) or overlapping-cards B (the
   crop-image page itself)? B is the signature of the family's namesake page
   and is currently unbuildable.
4. The 9 unviewed ai-models S04/S07 callouts tagged crop-frame (a16bd5ba,
   a6439ac4, ...) may be another sub-population; worth a follow-up sheet
   before trusting family n counts.
5. fc1a07de-style UI mocks: exclude from the family or add a `ui-mock`
   no-generate note?
