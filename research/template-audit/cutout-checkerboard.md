# Template audit: cutout-checkerboard

2026-09-15. Local-only audit of the `cutout-checkerboard` lp-compose template
(`src/landing_page_gen/compose/families.py`) and its
`.claude/skills/picsart-workflows/style-families.md` block against the corpus
assets tagged `style: cutout-checkerboard` in `corpus/styles.yaml`.

Corpus tally: 32 tagged assets (31 images + 1 webm). 13 images viewed across
9 pages, PNG proofs in `/tmp/audit-cutout-checkerboard/`. All measurements at
the 1600px asset scale.

## (a) Per-asset inventory

| asset | page / slot | conf | what the pixels show |
|---|---|---|---|
| 4604e99a | batch-photo-editor S06-m1 | .65 | **Canonical.** TRANSPARENT ground (gutter alpha=0). Left column 513 wide: two panels 513x784 stacked, gutter 32. Each panel is a *partial cutout*: the original photo background remains on part of the panel and a DARK checker (cells ~78px, #232021/#414143) fills only the removed region; cutout cap spans both. Magenta rounded badge 76x76 with white check at top-RIGHT of each (bbox 407..483 x 31..107, inset ~30; #D700C8). Right: light-grey studio `result` panel 545..1600 x 0..~1360. Dark button (#1c1c1c) full column width, ~y1361..1600, white caps "ADD TO BAG". |
| f1a23ccd | batch-photo-editor S12-m1 | .75 | Same skeleton: transparent ground, two stacked left panels (photo + dark-checker strip where bg removed), magenta badges top-right, big light result (shirt) right. **Button differs:** black caption "Whimsy Cut / $85" bottom-LEFT on the ground + a rounded PURPLE "Buy" pill bottom-right — not a full-width dark button. |
| a49dfb87 | batch-photo-editor S04-m1 | .70 | Transparent ground, 2x2 grid of equal panels; each = dark checker left half / photo right half, cutout ring spanning; recoloured per panel. NO badges, NO button, NO result panel. |
| 7a980105 | background-remover S08-m1 | .75 | Transparent ground. Left: one tall photo panel. Right: BLACK card with a profile UI (round avatar, BLUE check disc, name, role, follower stats). Bottom-left: black tile with a white checker-photo icon. No checkerboard panels, no magenta. |
| ec67a479 | background-remover S10-m1 | .70 | Transparent ground. Top-left: before/after panel — photo left, LIGHT grey-on-white checker right, cutout cup spanning; magenta badge top-LEFT. Below: two BLACK tiles ("50 photos" text; checker-photo icon). Right: tall light result card, then caption "Cappuccino / $3" + WHITE pill "ORDER" under it. |
| 68b8f004 | background-remover S17-m6 | .70 | BLACK ground (the one black ground seen). Two panels side by side: before/after wipe (photo | light checker, slider handle) and result-on-white. Magenta CIRCLES numbered "1","2" top-LEFT. |
| 50393c49 | background-changer S09-m1 | .70 | 2:1 strip, light/transparent ground. Left: two black icon tiles stacked. Then four photo→cutout pairs; cutout halves on LIGHT checker with magenta check badge top-right. No result, no button. |
| b7497932 | sticker-maker S09-m1 | .60 | One full-bleed rounded DARK-checker panel (near-black cells), five die-cut stickers scattered on it. No badges, buttons, result. Stickers carry their own art text. |
| 2f5015e2 | sticker-maker S09-m2 | .60 | Same as b7497932 (near-duplicate sibling). |
| 8e3c73fe | flip-image S04-m1 | .45 | Light ground: cutout bottle on LIGHT checker panel left, phone story mockup right, white round icon chip. Marginal fit. |
| edff67df | image-upscale S08-m1 | .50 | No checker anywhere: 3 small photo panels w/ magenta badges left, two big Before/After panels with translucent pills right. This is before-after with selection badges — mistagged. |
| 024b8aa7 | variation-generator S06-m1 | .60 | Black URL-bar card + two product-listing cards with price pills. Not this family — mistag. |
| 644754eb | persona S05-m1 | .50 | Dark persona-style card carousel (Y2K card, HOT pill). Not this family — mistag. |
| e12dcda2 | thank-you-card-maker S04-m4 | .75 | A greeting-card design ("Giving Thanks"). Not this family — mistag (variant "checker" is wrong). |

Not viewed: remaining 18, mostly conf <= 0.55 and on non-cutout pages
(video-tools, slideshow-maker, ai-models--seedance-1-pro x2, ai-design-generator,
product-ad-maker, video-ad-maker, photo-editor, remove-object, image-tools,
background-tools x2, persona webm, instagram-video-maker, plus 3 more
batch/bg-changer siblings). Page names suggest roughly a third of the 32 tags
are noise from the rules pass.

## (b) Modal layouts (of the 10 on-family images viewed)

1. **Cutout-to-product card** (4 of 10: 4604e99a, f1a23ccd, ec67a479, ~68b8f004):
   left checker-cutout panel(s) with magenta badge + large light result panel
   right + a commerce action (dark full-width button, or caption+small pill).
   The template's shape. Only batch-photo-editor stacks TWO left panels; the
   background-remover ones use ONE cutout panel plus black info tiles.
2. **Cutout pair/grid, no result** (2: a49dfb87, 50393c49): 2x2 or 1x4 of
   photo|checker split panels; badges optional; no button, no result.
3. **Sticker sheet** (2: b7497932, 2f5015e2): one full-bleed dark checker
   panel, several die-cut stickers, no chrome at all.
4. One-offs: profile-card composite (7a980105), cutout+phone mockup (8e3c73fe).

Constants across on-family assets: rounded panels (~40px radius), magenta
#D700C8 check badges wherever a "selected" cutout is shown, checker only
*behind removed background* (a photo remnant stays in the panel), and a
transparent page ground (9 of 10; black once).

## (c) VERDICT

The template's skeleton (two stacked left checker panels + magenta badge
top-right + big result right + dark button under it) is REAL — it is the
batch-photo-editor callout, pixel-close on 4604e99a. But four claims diverge
from consensus:

1. **Ground is transparent, not BLACK.** Gutter alpha = 0 on every 1:1 asset
   probed; the page's own background shows through. Only 68b8f004 (a small
   inline step figure, 738x608) sits on black. `families.py` says
   `"ground": {"fill": BLACK}` — wrong; style-families.md "Ground: black
   (default)" — wrong.
2. **The checker panel is a before/after split, not a plain checker slab.**
   Real panels keep part of the original photo background and show checker
   only where the background was removed, the subject spanning the seam. The
   template's `under: checkerboard` + `fit: contain` (a transparent PNG
   floated on a full checker) reads flatter than every corpus example.
3. **Checker tone varies by page:** dark (#232021/#414143, ~78px cells) on
   batch-photo-editor and sticker-maker; light grey-on-white on
   background-remover / background-changer / flip-image. Template hard-codes
   dark-grey only.
4. **The button is one variant of a commerce footer.** Corpus shows: full-width
   dark "ADD TO BAG" (once), caption+price on the ground with a small "Buy" /
   "ORDER" pill (twice). Black info tiles (icon or "50 photos") appear in three
   assets and are absent from the template.

Also: geometry is near-exact where it matches (left panels 513x784 vs spec
510x780; badge 76x76 inset ~30; button y1361..1600 vs spec 1370..1560 —
actual is ~240 tall, slightly taller than spec's 190), and the styles.yaml
tag set is noisy — at least 4 of 13 viewed are other families entirely.

## (d) CORRECTED SPEC (1600px frame, 1:1)

```
ground: none (transparent; page ground shows through gutters)   # 4604e99a, f1a23ccd, ec67a479
radius: 40
panels:
  cutout-a: rect (0, 0, 513, 784)        # 4604e99a measured
  cutout-b: rect (0, 816, 513, 1600)     # gutter 32, not 40
  result:   rect (545, 0, 1600, 1360)    # light studio ground
chrome:
  badge-a / badge-b: magenta #D700C8 rounded square 76x76, white check,
                     top-right, inset 30                        # 4604e99a bbox 407..483 x 31..107
  button: solid near-black #1c1c1c, rect (545, 1390, 1600, 1600 - r),
          white caps label                                       # 4604e99a y1361..1600; keep a 30px gap
checker (per cutout panel): drawn only over the REMOVED region — keep the
  panel's own photo backdrop on ~40-60% of the width and checker the rest,
  subject spanning the seam; cells ~78px; dark cells #232021 / #414143
  (batch/sticker pages) or light #ffffff / #e5e5e8 (remover/changer pages)
variants (observed, for future work):
  footer=caption: "Name / $price" text bottom-left + small pill bottom-right
                  (f1a23ccd Buy purple, ec67a479 ORDER white)
  grid: 2x2 equal split panels, no result/button (a49dfb87, 50393c49)
  sticker-sheet: one full-bleed dark checker panel, n die-cut subjects
                 (b7497932) — no badges or buttons
```

Minimal code change: `ground.fill BLACK -> None`; panel rects/gutter as above;
add a `checker_tone: dark|light` knob; render the checker as a partial fill
behind the cutout rather than a full `under` slab (needs the pre-removal photo
as a second input, or at least a photo-strip fake).

## (e) Open questions

- The partial-fill checker needs the *original* (pre-remove_bg) frame per
  cutout. The worker recipe only keeps the transparent PNG; either keep the
  step-1 generate too and composite photo|checker halves, or accept the flat
  full-checker look and note the divergence.
- Which checker tone should the default be? Dark matches batch-photo-editor
  (the template's namesake page); light matches background-remover, the more
  on-topic tool. Possibly keyed on page ground.
- styles.yaml noise: ~1/3 of `cutout-checkerboard` tags (thank-you-card,
  persona, variation-generator, image-upscale, seedance, video pages) are
  other families; the rules pass over-fires on any transparency/checker hint.
  Worth a labelling-sheet pass before trusting the n counts.
- The `variant:` values (checker/white/colour/null) in styles.yaml do not map
  to what the pixels show (e12dcda2 "checker" has no checker); re-derive.
- Black info tiles ("50 photos", checker-photo icon) recur on
  background-remover; template a tile row as an optional chrome variant?
