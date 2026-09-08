# live-1 style gap: what hsl-color's images really are, and how the generator now follows them

2026-09-08. Follows `runs/live-1` (five slots of `picsart.com/hsl-color/` generated blind,
all accepted, 50 credits) and its "against the original" note. Files here: `originals/`
(the five originals plus four sibling-page cards), `generated/` (the five accepted
renders), `refs/` (stock sources and competitor images, indexed in `refs.yaml`),
`trial/` (three `runs/trial-4` renders composed with the new template), `board.png`
(one row per slot: original, generated, web reference, trial composite),
`measurements.json` (panel geometry measured from the originals).

## 1. What the originals are

Every one of the five is a stock photograph with Picsart product chrome laid over it.
Measured on the 524x393 corpus copies (`measurements.json`; fractions of the card):

| slot | photo | source | chrome | ground | panel box (x, y, w, h) | tilt |
|---|---|---|---|---|---|---|
| S01-m1 hero | smiling man in glasses, magenta and cyan gel light, white sweatshirt, lilac backdrop | Pexels 2180474 "Smiling Man" by R. Fera (exact frame) | white round badge with the three-ring HSL mark (0.17 w at x 0.73, y 0.11); white "HSL" label pill with a pointer (0.27 x 0.15 at x 0.68, y 0.37); no panel | rounded card, transparent corners | none | 0 |
| S03-m1 | woman in a red top and white trousers dancing by a striped studio wall | same shoot as Pexels 850391 / 850393 by Godisable Jacob (exact frame not found) | dark panel: header (mark, "HSL", teal badge, chevron), 8 hue chips (27 px, one ringed), Hue 28 / Saturation -26 / Lightness 30 sliders with value chips | full bleed, rounded | 0.42, 0.25, 0.51, 0.50 | 0 |
| S03-m2 | woman in a white shirt and a multicolour striped skirt, blue sky | not found (Pexels, Unsplash keyword search) | dark panel with 8 chips and one Hue slider | two tilted rounded cards on the page's white | panel over the lower left | 9.8 deg |
| S03-m3 | woman in a purple satin blouse, orange-red eyeshadow, seamless yellow | same look as Pexels 12928824 by weezy-mie (not the frame) | dark panel with one Saturation slider (43) | full bleed, rounded | 0.39, 0.64, 0.55, 0.19 | 0 |
| S03-m4 | woman with short hair in an iridescent fringe jacket, pastel | not found | dark panel with one Lightness slider (30) | two tilted rounded cards on white | 0.19, 0.59, 0.50, 0.19 | 9.7 deg |

Panel colour is `rgb(33, 31, 33)` with the photo faintly showing through (about 93 %
alpha). The corpus tags all five `full-bleed` because `measure.py` reads a dark panel on
a photo as `photo-full-bleed / single` and nobody had answered the chrome field: the
labelling sheets held 1 answered sheet of 182, and the hsl-color assets were not on any
sheet (they were indexed the day after the sheets were built).

The same chrome recurs on sibling pages: hair-color-changer S02-m2 and S02-m4 are the
tilted stacked cards (m4 with a round "before" inset), ai-filters S04-m1 and S08-m1 carry
the same white round badge and label pill ("AI Filters") over a picture. So the look is
Picsart's tool call-out, not a one-page quirk.

## 2. The Picsart look for adjustment tools, as a spec

**Photography.** Stock fashion and beauty photography of the kind Pexels lists under
"colourful fashion": one person, one or two saturated garment colours (red top, purple
blouse, striped skirt) against a flat or graphic backdrop (striped studio wall, seamless
yellow, lilac with gel light), hard even studio or street light, face visible, subject
in the left two thirds. Nothing in the photo is "edited"; the panel says what the tool
does. Creators whose work fits: Godisable Jacob (Pexels, striped and coloured studio
walls), R. Fera (gel-lit portraits), weezy-mie (pastel-on-yellow beauty), plus the
Pexels search pages `woman colorful striped wall` and `woman yellow background purple`
(Isi Parente, Westley Ferguson, MART Production, Victoria Strelka). These are the
"content creators who make similar images": stock lifestyle photographers, not AI-art
accounts.

**Chrome.** A dark rounded panel (`#1c1c1e` at ~93 % alpha) with a header row (tool
mark, tool name, small teal badge, collapse chevron), a row of eight hue chips (red,
orange, yellow, green, turquoise, blue, purple, pink; the active one ringed), and one
row per slider (grey label, thin track, white knob, dark value chip). One card carries
all three sliders; the others carry the one the section names. Heroes carry a white
round badge with the tool mark and a white label pill with a pointer instead.

**Ground.** Either the photo fills the rounded card, or the card sits tilted about
10 degrees over a plain card on the page's white ground (two of five cards here, two of
the hair-color cards).

**Competitors.** Fotor's hue-changer page: two offset rounded photo cards labelled
Before / After (red sequin jacket turned magenta) with an arrow, on a flat blue ground,
both in the hero and in the feature image (`refs/competitors/fotor-*`; its alt text
claims a UI overlay, the picture shows none). VSCO's HSL page: a before/after hero and
feature images of photos with the HSL sliders overlaid (`refs/competitors/vsco-*`).
The category convention is a stock portrait plus a device that shows the tool at work:
either a control overlay (Picsart, VSCO) or a labelled before/after pair (Fotor); a
plain photo is the exception.

## 3. Gap: live-1 generated vs original

Scored in the rubric's words (`picsart-workflows/evaluation.md`); 5 is the original.

| axis | original | live-1 generated | score |
|---|---|---|---|
| subject | one person, fashion or beauty stock | still life (cyan rose), a torso in a parka, a bundled-up person, a fruit table, a woman on a street | resemblance 2 |
| what shows the edit | the panel; the photo is untouched stock | the photo itself is asked to "read as hue-shifted" (cyan rose, intensified orange and green) | resemblance 2 |
| saturation and light | high, flat, even studio or street light, graphic backdrops | editorial, soft window light, shallow depth, natural greens and greys | consistency 3 |
| backdrop | striped wall, seamless yellow, lilac, blue sky | foliage, concrete, garden table, city street | resemblance 2 |
| chrome | panel, chips, sliders, value chips; badge and pill on the hero | none | resemblance 1 |
| ground | rounded card; two of five tilted stacks on white | full bleed, square | resemblance 3 |
| text | chrome text only (HSL, Hue, Saturation, Lightness, values) | none | text 5 (nothing wrong, nothing there) |
| finish | photo, clean, stock | photo, clean, editorial | clean 5, artefacts 5 |

The generated set is a good answer to the brief it was given. The brief was wrong about
the family.

## 4. Why the pipeline produced this

1. **Missing labels, not a finding.** `usecase-4:3` and the pooled `hero-4:3` resolved
   to `full-bleed` from measured fields alone; chrome was unanswered on 5686 of 5691
   media rows. The slot-class table then said "lifestyle photo, no chrome".
2. **No family described "photo with a floating editor panel".** The taxonomy had
   `prompt-ui` and `slider` in its vocabulary but no rule and no compose template, so
   even a labelled asset would have fallen to `full-bleed`.
3. **Annotations written from the copy.** "Orange and green elements", "a red jacket",
   "a still life": the section copy's example objects, which the originals ignore.
   The manager could not know that blind, but the family block should have said it.
4. **Anchoring on a still-life hero** pulled the series towards editorial restraint
   (soft light, muted grounds) and once leaked the rose itself.

## 5. What changed (implemented in this branch)

- **`panel-overlay` family** in `picsart-workflows/style-families.md` (fifteenth block,
  nine keys): Use, Slots, Signature, Ground (`none` | `white` = tilted stack), Grid
  (4:3 and 5:4; panel 810x600 at (680,300); tool pill 440x500 at (1080,120)), Template,
  Chrome, Panels (the stock look, subject left two thirds, panel area clear), Palette,
  Text (chrome text only: tool name, slider labels, values), Never (no panel or sliders
  painted by the model; no "hue-shifted" subject prompted in), Examples (85708ef3,
  da31e929, 0c9be8c4; tilted 9caa06ad, e9c17dd8). Slot-class row `usecase-4:3` names
  `panel-overlay` for adjustment-tool pages; the pooled-classes paragraph does the same
  for `hero-4:3` and `usecase-5:4`. Vocabulary: chrome gains `adjust-panel`; the
  `panel` constant describes the adjust panel.
- **Manager cue** in `build-landing-page/SKILL.md` step 4: an H1 or tool name saying
  hue, saturation, HSL, colour, colorize, curves, filter or adjust makes 4:3 and 5:4
  heroes and cards `panel-overlay`.
- **`lp-compose`**: template `panel-overlay` with `aspects` (4:3, 5:4) and a photo panel
  that fills whatever size the spec gives; chrome kinds `adjust-panel` (title, chips,
  active, sliders as [label, value]) and `tool-pill` (text, icon); `wheel` and `chevron`
  icons; `ground: tilted` (or `tilt: <deg>`) stacks the card over a plain one; the
  spec omits `tool-pill` on cards and `panel` on the hero; `--describe panel-overlay`
  prints all of it.
- **Taxonomy**: `adjust-panel` in the chrome enum (and `slider` redefined as a labelled
  track with a knob, or a before/after handle); `family_of` rule after `before_after`:
  `adjust-panel` in chrome, or `slider` with layout `overlay`, or a hero with both
  `pill` and `badge` on a single full-bleed photo, gives `panel-overlay`; white ground
  gives the `/white` variant.
- **Labels**: sheets rebuilt without `--skip-resolved` (299 sheets; the earlier 182
  kept their names) so assets the measurer had "resolved" get a sheet too. Three sheets
  answered for the hsl-color cells (and the rest of `use-case-grid_unknown_unknown-1b50b1`).
  After `lp-corpus labels` and `styles --from-attrs`, all five hsl-color creatives read
  `panel-overlay` (m2 and m4 `panel-overlay/white`) and `lp-corpus skeleton hsl-color`
  emits `> style: panel-overlay` for them.
- **Trial** (`runs/trial-4`, 15 credits): three `gemini-3-pro-image` renders prompted for
  the stock look (striped wall, purple on yellow, gel-lit portrait), each leaving the
  panel area clear, composed with the template as a three-slider card, a one-slider
  card, a tilted one-slider card and a hero with the tool pill. See `board.png`, last
  column: they sit beside the originals without a change of register.
- `prd.md` gains five lessons; `plan.md` a decision row and a Milestone 3 note.

## 6. Still open

- Two source photos (S03-m2 skirt, S03-m4 fringe jacket) not identified; a visual
  search with the file would settle it.
- Sibling adjustment pages (`/photo-effects/colorize-images/`,
  `/photo-effects/change-color-of-image/`) are not in the corpus; their alt texts read
  as effect results. Fetch them before the next adjustment-tool run to see whether they
  carry the panel.
- The measurer still cannot see a panel; a detector for a large dark rounded rectangle
  inside a photo-full-bleed asset would tag these without a labeller (< 40 lines,
  deferred).
- The composite check in a worker-driven run (Milestone 3 criterion) remains: re-run
  hsl-color S03 through `/build-landing-page` and compare with `board.png`.
- Canva, Adobe Express and Pixlr pages could not be fetched (403 / 404).

## Sources

- https://www.pexels.com/photo/smiling-man-2180474/ (R. Fera)
- https://www.pexels.com/photo/850391/ and https://www.pexels.com/photo/850393/ (Godisable Jacob)
- https://www.pexels.com/photo/12928824/ (weezy-mie)
- https://www.pexels.com/search/woman%20colorful%20striped%20wall/ and https://www.pexels.com/search/woman%20yellow%20background%20purple/
- https://www.fotor.com/features/hue-changer/
- https://www.vsco.co/features/hsl
- https://picsart.com/hsl-color/, https://picsart.com/photo-effects/colorize-images/, https://picsart.com/photo-effects/change-color-of-image/
