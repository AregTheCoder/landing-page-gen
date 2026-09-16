# Audit: `template-mockup` lp-compose template vs the real corpus

2026-09-15. Method: parsed `corpus/styles.yaml` (204 assets tagged
`template-mockup`; variants: none 147, black 20, mixed 20, light 8, colour 7,
gradient 2), sampled 14 assets across 13 pages, composited each over neutral
grey (most are transparent) and viewed every one at <=700px
(`/tmp/audit-template-mockup/`). Component geometry measured from the alpha
channel at native 1600px. Template under audit:
`src/landing_page_gen/compose/families.py` lines 64-79 and the
`## template-mockup` block in
`.claude/skills/picsart-workflows/style-families.md`.

Note on sampling: the page `poster-maker` has **zero** template-mockup tags in
the current styles.yaml — the doc's cited /black example `21cdafd9`
(poster-maker S09-m1) is now tagged `dark-composite` on motivation-poster-maker
(conf 0.6). It was viewed anyway as the doc's canonical /black reference.

## (a) Per-asset inventory

| # | page / slot | uuid8 | var tag | ground | tiles (count, side, content) | cards | headline | photo panel | other chrome |
|---|---|---|---|---|---|---|---|---|---|
| 1 | ai-template-generator S07 | 5d8ec016 | – | **opaque** near-white | 4 left, all black: list, checkerboard, resize, Aa | 1 flat indigo | real words in a selection frame w/ handles | lavender panel + cup photo below headline | – |
| 2 | flyer-maker S07 | def7593d | – | transparent | **0** | **4** flat cards: 3 small stacked left, 1 large pink right | real words on cards | none | magenta selection border on one card |
| 3 | birthday-card-maker S08 | ba57eaf9 | – | transparent | 3 left: swatch (white+3 stripes), magenta T, black sticker | 1 flat white, full poster design | real words + `DD/MM/YYYY` placeholder on card | none | – |
| 4 | calendar-maker S06 | 219070b9 | – | transparent | none as a column | 1 black spiral-bound calendar card | real calendar text | none | checkerboard cutout panel w/ selection frame, black `Aa Aa` type tile, wide colour swatch bar bottom |
| 5 | calendar-maker S05 | 0268ce5e | colour | opaque cream, 16:9 | 0 | plain calendar template screenshot: photo left, grid right | real words | photo half | none — arguably not this family |
| 6 | christmas-card-maker S06 | c491d842 | – | transparent | none as a column | 1 flat pink card | real words | none | light checkerboard cutout panel w/ frame, `Aa Aa` type tile, 4-colour swatch bar bottom |
| 7 | coupon-maker S06 | a591037a | – | transparent | none as a column | **2** overlapping coupon cards (zigzag edges) | real words (`50% OFF`) | none | checkerboard cutout panel w/ smiley + frame, `Aa Aa` type tile, swatch bar bottom |
| 8 | gift-certificate-maker S08 | bbc37648 | – | transparent | bottom row: black T, magenta image+, swatch strip | 1 wide olive certificate card | real words | 4-circle photo collage inside card | – |
| 9 | invitation-maker S06 | b2749949 | black | transparent | 4 left, all black: thumbnails-tile, list, sticker, T | 1 tall card, full-bleed painting + scalloped text panel | real words | card art is the photo | first tile holds 3 mini template thumbnails |
| 10 | motivation-poster-maker S07 | c3461329 | black | transparent | 4 left: **magenta** list tile, black `Aa Helvetica Text Bold`, checkerboard tile w/ sticker, swatch tile | 1 poster card (holographic photo) | `CRESCENDO` in a selection frame w/ handles | card art is the photo | purple ticket sticker repeated on tile and card |
| 11 | youtube-banner-maker S01 | 72e4d513 | gradient | transparent | 0 | 3 stacked banners (lime strip, sky strip, gradient front) | real words | banner art | selection frame around the eye graphic |
| 12 | instagram-post-creator S09 | 861c2971 | – | transparent | 3 left: swatch (black/red/white), magenta T, black image+ | 1 flat red card | real words (`FLASH SALE`, `35% OFF`, `SHOP NOW`) | **circular** photo panel centred in card | – |
| 13 | greeting-card-maker S08 | f57cb379 | – | transparent | 3 left: tall swatch (4 stripes), magenta image+, black T | 1 cream card w/ giant typography | real words | polaroid-style photo card w/ caption overlapping card centre | – |
| 14 | poster-maker S09 (doc /black ex.) | 21cdafd9 | (now dark-composite) | transparent | 3 left: magenta stripes tile, radial **gradient swatch** tile, checkerboard cutout tile w/ hand photo | 1 cream poster card | real words (`50% OFF`, `BUY NOW!`) | hand-with-product photo is the card art | matches the doc's /black description exactly |

Geometry (native 1600x1600, alpha bounding boxes):

- b2749949: frame margin 152 all round; tiles x152-632 (**480 wide**, first
  480x376, rest 480x276, gutter 28); card x660-1444, y152-1444 (**784x1292**).
- c3461329: tiles ~376-380 sq (two), then 376x228 (two), x148-528; card
  x556-1444 (**888x1292**).
- 861c2971 / f57cb379: small-tile mode — swatch tile ~190x545 (tall stripe
  stack), two ~190x190 tiles; card **772x996** / **704x984**, larger margins.
- c491d842: cutout panel 328x320 + frame, type tile 392x168, card 628x736,
  swatch bar 1064x200 across the bottom.

## (b) Modal layouts (counts out of 14 viewed)

- **Ground:** transparent 12/14; opaque 2 (the 800px template source and the
  16:9 colour screenshot). The white or black comes from the **page section**,
  not the asset. /black assets are transparent too.
- **Aspect:** 1:1 (1600x1600) 12/14.
- **Layout A — side tile column + one card (8/14, modal):** a left column of
  **3-4 tiles** and one flat rounded card right. Tile fills are **mixed**:
  typically one magenta/pink tile, one or two black tiles, and one **swatch
  tile** (stacked colour stripes) — the all-black 4-tile column exists in only
  2/14 (5d8ec016, b2749949). Tile icons seen: T, image+, Aa type specimen,
  list/form, sticker, checkerboard, template thumbnails.
- **Layout B — editor exploded view (3/14):** checkerboard cutout panel with a
  selection frame + `Aa Aa` type tile on the left, card right, wide colour
  swatch bar across the bottom (219070b9, c491d842, a591037a).
- **Layout C — cards only (2/14):** several overlapping/stacked template cards,
  no tiles (def7593d, 72e4d513); one card may carry a selection highlight.
- **Card count:** exactly 1 in 10/14; 2-4 in 3; flat in 14/14 (no tilt, no
  perspective, no paper texture — "Never" rules confirmed).
- **Headline:** real words in 14/14, **never blank bars**; part of the card's
  poster typography. In 3/14 a **selection frame with drag handles** surrounds
  the headline or a card graphic — that frame is the one recurring
  "headline-box"-like chrome, and it also appears around cutout subjects.
- **Photo panel:** a distinct photo region inside the card in only 4/14, and
  its shape varies (rect panel, circle, polaroid, 4-circle collage); in the
  rest the card is one full design.

## (c) VERDICT

The current template reproduces **one specific asset** (ai-template-generator
5d8ec016 — the only opaque-white sample) rather than the family. Divergences:

1. **Ground:** template bakes white; 12/14 real assets are transparent and take
   the page ground. White is a fair proxy for light pages but /black is not a
   different artwork — it is the same transparent asset on a dark section.
2. **Tile count/fill:** template draws 4 uniform black tiles; the modal column
   is **3 mixed tiles** (one magenta, one black, one swatch). All-black x4 is
   the minority (2/14).
3. **Tile size:** template 260x260 at x240; measured columns are either
   ~480-wide (large mode, margin 152) or ~190 (small mode). 260 matches
   neither.
4. **Headline box:** template reserves a bar-zone in the card's top third;
   reality is real words rendered as card typography anywhere on the card,
   optionally wrapped in a **selection frame with handles** (the actual chrome
   worth drawing). Blank bars never occur, so the current
   `omit: [headline]` practice is correct and the "keep with blank bars when
   text is none" fallback contradicts the corpus.
5. **Photo panel:** template hard-codes a 740x660 rect below the headline;
   only 4/14 have any discrete photo region and none at that geometry. The
   card-as-one-design is the norm — the `photo` panel should be the **whole
   card interior**, not a sub-rectangle.
6. **Missing chrome confirmed:** swatch tile / swatch bar, checkerboard cutout
   panel with selection frame, `Aa` type-specimen tile, magenta accent tile —
   exactly the items style-families.md lists as "not yet drawn"; they appear
   in 8/14 samples, so they are core, not optional.
7. **Doc example drift:** 21cdafd9 is cited as the /black exemplar but is now
   tagged dark-composite on a different page; the /black cluster is real
   (b2749949, c3461329 confirm the doc's description) but its ground is still
   transparent + dark page.

## (d) CORRECTED SPEC (1600x1600 frame)

Default variant (Layout A, large-tile mode; evidence: b2749949, c3461329,
5d8ec016):

```python
"template-mockup": {
    "aspect": (1, 1),
    # page supplies the ground; export with alpha. WHITE fallback for previews.
    "ground": {"fill": None},          # transparent (12/14 corpus assets)
    "radius": 40,
    "panels": {
        # the photo IS the card interior (10/14 cards are one full design)
        "photo": {"rect": (600, 200, 1400, 1400)},   # inset 44 inside card
    },
    "chrome": [
        # card measured 784-888 x 1292 at x556-660, y152-1444 (b2749949, c3461329)
        {"id": "card", "kind": "card", "rect": (556, 152, 1444, 1448), "fill": (43, 20, 90)},
        # 3 mixed tiles, 380 wide, x152-532, gutter 28 (c3461329 geometry)
        {"id": "tile-1", "kind": "tile", "rect": (152, 152, 532, 532), "icon": "list", "fill": (255, 0, 200)},   # magenta
        {"id": "tile-2", "kind": "tile", "rect": (152, 560, 532, 940), "icon": "type-specimen", "fill": (0, 0, 0)},  # "Aa"
        {"id": "swatch", "kind": "swatch-tile", "rect": (152, 968, 532, 1448),
         "stripes": 4},  # stacked colour stripes from the card palette
        # selection frame with handles around the headline zone; replaces the
        # blank-bar headline box (real assets never show bars)
        {"id": "select", "kind": "selection-frame", "rect": (640, 240, 1360, 520)},
    ],
},
```

Variants worth templating:

- **/black** (20 tagged): same layout, all-black tile fills except the magenta
  accent; export stays transparent, page ground is dark. Not a separate
  drawing — a fill override (evidence: b2749949, c3461329, 21cdafd9).
- **/editor** (new; Layout B, 3/14): checkerboard cutout panel
  (152, 240, 680, 1000) with a selection frame, `Aa Aa` type tile
  (152, 1040, 680, 1240), card (720, 152, 1448, 1240), swatch bar
  (152, 1300, 1448, 1500) — geometry from c491d842 scaled 700->1600.
- **/gradient** (2 tagged): stacked-cards layout with no tiles; too rare and
  too free-form to template — keep briefing as the default with a note, as
  today.

Worker brief change: the `photo` panel prompt should ask for **a finished
poster/card design filling the card**, headline typography included, not a
product photo with 25% margin; the discrete product-photo-in-panel reading
fits only 4/14 assets.

## (e) Open questions

1. Should `ground: None` (alpha export) be supported by lp-compose at all, or
   keep baked white/black per target section? lp-inject would need to know the
   section ground either way.
2. The swatch tile needs palette input (stripe colours). Derive from
   `card.fill` + photo palette, or let the worker pass them?
3. calendar-maker 0268ce5e (`colour`, 16:9 plain template screenshot) reads as
   full-bleed, not template-mockup — is the `colour` variant (7 assets) a
   mis-tag cluster worth re-running rules on?
4. 21cdafd9's retag to dark-composite: update the Examples line in
   style-families.md, or fix the tag? The image itself is unmistakably
   template-mockup chrome (magenta tile, gradient swatch, checkerboard cutout).
5. Selection-frame-with-handles appears both around headlines and around
   cutout subjects — one chrome kind with a `target` param, or two kinds?
6. Small-tile mode (~190px tiles, card ~700x990: 861c2971, f57cb379) vs
   large-tile mode (~380-480 tiles): template one and accept the other, or add
   a size variant?
