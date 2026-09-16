# Template audit: dark-composite

2026-09-15. Local-only audit of the `dark-composite` lp-compose template
(`src/landing_page_gen/compose/families.py`, `## dark-composite` in
`.claude/skills/picsart-workflows/style-families.md`) against the assets
`corpus/styles.yaml` currently tags `dark-composite`. No paid calls.

## Population

26 entries tagged `style: dark-composite` in `corpus/styles.yaml`
(3 videos skipped → 23 images across 19 pages). Corpus `variant:` values are
`None` (11), `white` (9), `light` (6) — these describe the **main card's
colour**, not the template variants `reference-thumbs`/`model-picker`/`two-up`,
which appear nowhere in styles.yaml. Sample: 10 images across 10 different
pages (all three variant tags covered) + 3 supplementary; every one viewed at
≤700 px (`/tmp/audit-dark-composite/`).

## (a) Per-asset inventory

| # | Asset | Page / slot | var tag | Ground | Panels | Boxes / chrome | Text |
|---|-------|-------------|---------|--------|--------|----------------|------|
| 1 | c1b34851 | ai-models--recraft-v4-styles S06-m1 | None | black + dot grid | 2 portrait photo panels in thin grey device-like frames, staggered diagonally (left high, right low), joined by a connector stub | bottom row: square tile with white Recraft R mark + wide near-black pill | "Generate" in the pill |
| 2 | bd014004 | ai-models--flux-3 S13-m9 (800x600) | None | black | right ~72%: three stacked wide result frames (character progression); left column: 2 photo thumbs (inputs) | left column below thumbs: 2 icon tiles (add-image glyph, model swirl mark), all near-black | none |
| 3 | bd3c5739 | compare-models--flux-2-pro-vs-midjourney S07-m1 | None | black + dot grid | 2 portrait photo panels staggered diagonally | none — no tiles, no chips | white model names ABOVE each panel ("Flux 2 Pro", "Midjourney") |
| 4 | 4fed106c | compare-models--nano-banana-2-vs-flux-2-pro S04-m1 | None | black + dot grid | 2 staggered portrait panels, each with a 4-thumb variant strip overlaid near its bottom | none besides the in-panel strips | white model names above each panel |
| 5 | 463d2cfa | variation-generator S05-m1 | None | black | 1 large photo below | top bar: white table glyph + dark spreadsheet UI (Name/Profession rows, one cell magenta-highlighted) | table copy ("Casey Morgan", …) |
| 6 | e247e30d | resize-image S08-m1 (1060x504) | None | black | 1 full-height photo right (~85% width) | left column: 4 labelled format tiles (Instagram Square, Instagram Portrait, Facebook Post — magenta outline = active, Pinterest Pin) | white tile labels |
| 7 | 87c30e6b | ai-font-generator S01-m1 (1600x1368) | white | black | large portrait design card right (blue poster) | left column: 3 light-grey thumbs (font samples) + a row of 2 near-black icon tiles (Ai, T) | design copy in the card |
| 8 | 4300f508 | bookmark-maker S06-m1 | white | black | tall bookmark strip left + large white photo card right | bottom row: bare "Aa" glyph + 4-colour palette strip card | "Aa"; design copy |
| 9 | 1fe89325 | brochure-maker S08-m1 | light | black | 1 centred landscape design card (brochure) | bottom row: outline T glyph, magenta sticker tile, palette strip card | design copy in the card |
| 10 | 8031c225 | christmas-card-maker S08-m1 | light | black | 1 large portrait design card right | left column: two-tone green swatch tile, red swatch chip, magenta T tile, outline sticker glyph | design copy; "2025" |
| 11* | d5d56eb0 | menu-maker S08-m1 | white | black | 1 large portrait design card right (menu) | left column: blank yellow swatch tile, magenta T tile, outline add-image glyph | design copy |
| 12* | f57c774f | collage-maker S10-m1 (2120x1008) | light | black | 1 large collage panel right | left column: 3 layout-glyph tiles, middle one magenta = active | none |
| 13* | 21cdafd9 | motivation-poster-maker S09-m1 | None | black | 1 large portrait design card right (50% OFF poster) | left column: magenta pattern-icon tile, gradient thumb, checkerboard cutout thumb | design copy |

\* supplementary, beyond the 10-asset sample.

Measured geometry (non-black run detection at 1600):
- 21cdafd9: outer margin 150 all round; left column x 150–533 (383 wide);
  main card x 557–1450 (893x1300, ~3:4 portrait).
- 8031c225: same shape, smaller composition centred (column 192 wide,
  card 776x1008).
- c1b34851: panels x 94–713 / x 842–1469, y 131–1119; bottom bar y 1370–1517.

## (b) Modal layouts

- **8/13 column-main**: a narrow tool column of 3–4 boxes beside ONE large
  panel; column on the **left in 8/8**. Boxes are page-specific: tool-glyph
  tiles (T/text x3, add-image x2, sticker x2, layout grids, Ai, pattern,
  model mark, labelled social-format icons), colour-swatch tiles or palette
  strips (x4), content thumbs (font samples, gradient, checkerboard cutout,
  input photos). The main panel is usually a rounded light/white **designed
  card** (the corpus `white`/`light` variant tags) or a photo.
- **8/13 carry exactly one magenta accent** (a magenta-filled tile or a
  magenta active-state outline/highlight).
- **3/13 compare/two-up**: two portrait panels staggered diagonally on black
  with a dot grid, white model-name labels above each (both compare pages;
  recraft adds a bottom mark-tile + "Generate" pill instead of labels).
- **3/13 bottom-row**: main card centred with a row of 2–3 glyphs/tiles/palette
  strips underneath (brochure, bookmark, recraft).
- **1/13 top-bar**: spreadsheet-UI bar above the photo (variation-generator).
- **Ground: black in 13/13** — including every asset tagged `white`/`light`.
- **0/13** show the current template's signature: no sparkle tile, no crop
  tile, no "4K" (or any resolution) chip, no right-side column, nowhere.

## (c) Verdict: FALSE

The base template does not match a single sampled asset. Divergences:

1. **Column side**: template puts the tile column on the right; every real
   column-main asset (8/8) has it on the left. (The variants comment in
   families.py even says "column on the left as on every Recraft card".)
2. **Tile contents**: sparkle+crop icon pair and a "4K" chip appear in 0/13.
   Real boxes are page-relevant tool glyphs, colour swatches, palette strips
   and content thumbs; resolution chips do not occur in the current
   population.
3. **No accent colour**: 8/13 assets carry one bright-magenta tile or active
   highlight; the family doc's "chrome is black and white only" is false for
   this population, and the template draws no accent/active state.
4. **Panel shape**: template's photo is 1180x1600 flush to the canvas edge;
   real column-main compositions sit inside a ~150 px margin and the main
   panel is a rounded ~3:4 card (893x1300 on 21cdafd9), most often a designed
   light card, not an edge-to-edge photo.
5. **Box count**: 3–4 boxes (often one labelled or active), not 2 tiles + 1
   chip with a 420 px gap.
6. **Compare layout uncovered**: the staggered two-panel-with-model-labels
   layout (both compare-models pages, 2/13 + recraft's cousin) matches no
   variant; `two-up` has no labels, no stagger, no dot grid.
7. **Stale evidence**: the geometry sources in families.py (86f73fc9,
   3d65a628, a3502ec3) and the doc's Examples (f746795b, 4eeca13c, 0794e437)
   are no longer tagged dark-composite in styles.yaml (86f73fc9 and 4eeca13c
   are now `full-bleed`, 0794e437 `before-after`, the rest absent). The
   template describes a population that the current styles.yaml no longer
   assigns to this family. (Viewed 86f73fc9: it is the `reference-thumbs`
   layout — column left, Recraft mark tile, an **SVG tile ~375x375**, i.e.
   full square, not the 375x140 chip the variant draws, two thumbs, output
   right.)
8. **Dot grid**: the subtle dot-grid texture on the black ground of
   ai-models/compare cards (3/13) is not drawn.

Faithful bits: black ground (13/13), rounded ~40 px corners, near-black
`#1c1c1e` tiles with white line glyphs as the non-accent tile style.

## (d) Corrected spec (1600 reference frame)

### Main template `dark-composite` (column-main, column LEFT)

Evidence: 21cdafd9, 8031c225, d5d56eb0, f57c774f, 87c30e6b, e247e30d, bd014004.

- ground: BLACK, radius 40.
- Composition inset 150 on all sides (content 150–1450) — 21cdafd9 measured.
- Left column x 150–530 (380 wide), three boxes, gutter 40:
  - `tile-1` (150, 150, 530, 530): tool-glyph tile, fill `#1c1c1e`, white
    line icon chosen per page (text-T, add-image, sticker, layout — NOT a
    fixed sparkle) [8031c225, d5d56eb0, bd014004, 87c30e6b].
  - `tile-2` (150, 570, 530, 950): ACCENT tile, magenta fill, white glyph —
    the page's active tool [21cdafd9, 8031c225, d5d56eb0, f57c774f,
    1fe89325].
  - `tile-3` (150, 990, 530, 1450): content chip — flat colour-swatch tile
    [8031c225, d5d56eb0] or a small thumb of the main panel's ingredient
    (worker-supplied `thumb` panel) [21cdafd9, 87c30e6b, bd014004].
- `photo` panel (570, 150, 1450, 1450) → renders 880x1300, ~3:4 portrait
  card, radius 40 [21cdafd9 measured 893x1300; 8031c225, d5d56eb0 same
  shape]. It is the page's RESULT — a designed card or photo; on maker pages
  usually light/white (the corpus `white`/`light` tags name this card's
  colour, not the ground).
- Drop the "4K" chip as a default. A resolution/format chip is unevidenced
  in the current population (0/13); keep `chrome: {chip: ...}` only as an
  opt-in override.

### Variant `compare-labels` (new — replaces nothing, covers compare pages)

Evidence: bd3c5739, 4fed106c, c1b34851 (stagger + frames).

- ground: black with a faint dot grid (dots ~`#2a2a2c`, pitch ~85 px).
- `photo` (150, 250, 755, 1450): portrait panel, radius 30.
- `photo-b` (870, 620, 1475, 1450): second portrait panel, lower right.
- chrome: white label text above each panel — `label-a` baseline ~y 210 at
  x 150, `label-b` baseline ~y 585 at x 870; text = the two model names
  from the section copy [bd3c5739, 4fed106c].
- No tiles, no chips.

### Variant `bottom-row`

Evidence: 1fe89325, 4300f508, c1b34851's bottom bar.

- `photo` (265, 300, 1335, 1110): one centred landscape card.
- chrome row y 1155–1345: `tile-1` (330, 1180, 430, 1280) bare white glyph;
  `tile-2` (505, 1155, 710, 1345) magenta accent tile; `strip`
  (745, 1155, 1335, 1345) 3–5-colour palette strip card [1fe89325] or a
  wide dark pill with a white label ("Generate") [c1b34851].

### Existing device variants (reference-thumbs, model-picker, two-up)

Keep — the Recraft/ai-models pages they came from are real — but re-verify
their geometry: their source assets left the family in the current
styles.yaml, and on 86f73fc9 the format chip is a full 375x375 tile with
"SVG", not the 375x140 chip the `reference-thumbs` variant draws. Column
already on the left in these, which is consistent with the corrected main
template.

## (e) Open questions

1. Should the family be split? The current population is dominated by
   maker-page "editor composite" cards (design card + tool column), while
   the doc's Use line ("ai-models, compare-models and generator pages…
   resolution chips") describes the old Recraft population that styles.yaml
   has since re-tagged mostly `full-bleed`. Either the rule table moved or
   the family definition should follow the population.
2. What re-tagged the old examples (86f73fc9, 4eeca13c → full-bleed)? If the
   `styles --from-attrs` rule table changed, the doc's Examples/Signature
   lines and the families.py geometry comments are stale and need the same
   refresh.
3. Corpus `variant: white|light` vs template variants: the two vocabularies
   collide. Decide whether the compose spec's `variant:` should accept the
   card-colour tags (mapping to a main-card fill) or the corpus should tag
   layout variants instead.
4. Exact magenta: sampled accent reads bright magenta/pink (approx `#e01ee0`
   on 8031c225/d5d56eb0 tiles), noticeably brighter than families.py's
   MAGENTA (181, 23, 170). Sample the pixels before fixing a constant.
5. The `> attrs:` ground line vs the tags: all 13 grounds are black; confirm
   there is any genuinely light-grey-ground dark-composite left (doc's
   `/light` ground note may now be moot).
6. Videos (3 skipped) and the 10 unviewed images may hold more layouts
   (ai-agents, add-subtitles-to-video, video-editor, design, flow, twitter,
   quote-poster, thank-you x2, collage S08); the top-bar UI layout
   (463d2cfa) is unique in the sample — check whether it recurs there before
   templating it.
