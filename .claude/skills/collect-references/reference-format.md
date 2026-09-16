# Reference file format

One file per family, `corpus/references/<family>.yaml`. Every key below is
required unless marked optional. Values are plain strings unless shown as a
list; keep each string under 40 words.

```yaml
family: dark-composite            # the family id, exactly as in style-families.md
collected: 2026-09-08             # date of this pass
by: reference-collector           # agent name
photography:
  genre: >                        # 2 to 4 sentences: subject, light, backdrop, colour, framing of the
    ...                           # photographs inside this family's panels (not the chrome, not the ground)
  search_terms:                   # 3 to 8 Pexels/Unsplash queries that return this genre
    - studio product photo dark background
examples:                         # 5 to 10, each verified on its own photo page
  - url: https://www.pexels.com/photo/...-1234567/      # the photo page
    image: https://images.pexels.com/photos/1234567/pexels-photo-1234567.jpeg   # direct file, from the page
    creator: Name as shown on the page
    platform: Pexels              # Pexels | Unsplash
    licence: Pexels               # Pexels | Unsplash
    matches: >                    # which corpus example (asset id) it resembles and in what
      f746795b: one product, centred, black seamless, hard rim light
    differs: >                    # what Picsart would change: crop, ground, colour, chrome
      Picsart crops to 3:4 and puts the tool tiles beside it
creators:                         # 3 to 6 photographers whose body of work fits the genre
  - name: ...
    platform: Pexels
    profile_url: https://www.pexels.com/@...
    why: >
      ...
picsart_specific:                 # what is Picsart's own, not the genre: chrome, ground, tilt, pills
  - black ground with two tool tiles and a resolution chip
category_convention: >            # optional: what competitor tool pages do for the same slot, if known
  ...
prompt_guidance: >                # 2 to 4 sentences a worker can paste into a photo prompt; must agree
  ...                             # with the family's Panels (worker) and Never lines
open:                             # what could not be found or verified; empty list when nothing
  - ...
```

## The `layout` block (optional, written by `--layout`)

The block above describes the photograph that goes *inside* the family's
chrome. This one describes a picture that already carries the **arrangement** —
a split, a grid, a collage, a diptych, a device mockup scene. The pool's
`--composition layout` intake reads it, and its bare intake scores every
pre-arranged image zero by design, so without this block no such reference can
ever enter the pool.

```yaml
layout:                           # optional; absent for families that have no arrangement to match
  arrangement: >                  # 2 to 4 sentences: how many panels, how they divide the frame,
    ...                           # what repeats across them, what sits in the gutter
  repetition: >                   # optional: the serial motif, when the family tiles one subject
    ...                           # (five mugs in five colours; one framing across six faces)
  search_terms:                   # 3 to 8 queries that return pictures already laid out this way
    - before after split screen skincare
  examples:                       # 3 to 8, each verified on its own photo page, same shape as above
    - url: ...
      image: ...
      creator: ...
      platform: Pexels
      licence: Pexels
      matches: >                  # which corpus example's ARRANGEMENT it resembles
        f746795b: two equal panels, hard vertical divide, same subject either side
      differs: >
        Picsart's divider carries a drag handle and the panels are 5:4
```

### Rules for the layout block

- Judge the **arrangement**, not the photograph. A mediocre photo in exactly
  the right two-panel split is a better layout reference than a beautiful
  single frame.
- A laid-out stock picture is a marketing artifact far more often than a bare
  photo is, so it usually carries text, a logo or a watermark. Record that in
  `differs` rather than rejecting it: the pool keeps these as compositional
  references only, and a reviewer needs to know what Picsart would strip.
- Never collect a layout that is itself another product's UI — a competitor's
  editor screenshot is not an arrangement Picsart can reuse.
- Write no `layout` block at all for a family whose slot is one uninterrupted
  picture (`full-bleed`, `cinematic-still`). An empty block is worse than none:
  it makes a sweep look collected when it is not.
- `repetition` is the point for the tiling families (`outcome-tile`,
  `graphic-collage`, `cutout-checkerboard`): name the motif that repeats, since
  a set of near-identical frames from one shoot is the asset there, not a
  duplicate to be capped away.

## Rules

- Pexels and Unsplash only. Both licences allow free use; both photo pages
  name the creator. No other stock site, no social media, no AI galleries.
- Verify every example by fetching its photo page: the `creator` and
  `image` fields come from that page, never from memory or a search snippet.
- A match is about the photograph: subject type, number of subjects, light,
  backdrop, colour, framing. Ignore the family's chrome and ground when
  searching; record them under `picsart_specific`.
- Aim for variety across the examples (different creators, subjects) so a
  worker sees the genre, not one photo.
- For `editor-canvas` and `model-card` (kept-from-source UI mockups) the
  photography is the picture inside the tile; collect for that.
- For `before-after` collect the plain "before" genre: ordinary, slightly
  flawed photos (soft, dull, cluttered) as a tool's input would be.
- Write `open` honestly: a genre with no good Pexels match is a finding.
- Never download files in this pass. Never call a Picsart tool.
