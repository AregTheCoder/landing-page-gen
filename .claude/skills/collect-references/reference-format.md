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
