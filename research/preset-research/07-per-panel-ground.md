# Preset 07 — per-panel ground (each panel its own ground colour)

READ-ONLY research. No committed source touched. Everything below is a
paste-ready *proposal* for `src/landing_page_gen/compose/`; nothing is
implemented. Zero Picsart credits used (only `lp-compose`, `sips`, PIL locally).

**What it is.** A spec/preset where the two panels of a compare card do **not**
share one canvas ground: each panel sits on its own ground colour — the S08
`compose_S08.py` prototype's `ground: {left, right}`. It templates the
`vs-two-up` **hero** form that `style-families.md` already documents but marks
"not templated": *"the hero adds a white round VS badge over the seam and **one
panel black, one white**"*.

---

## 1. EVIDENCE

**Family served:** `vs-two-up` (compare-models callouts/heroes). The FAMILIES
entry today paints ONE shared ground (`{"fill": (242,242,244)}`) behind both
panels; the doc's **Ground:** line is *"light-grey (default) | white | black"* —
all three are whole-slot. Per-panel differing ground is the separate **hero**
arrangement.

**Clean exemplars — two contrasting grounds, VS badge on the seam** (viewed
full-res; both are native 1600×1600 = REF):

| id | page / slot | left panel ground | right panel ground | chrome |
|---|---|---|---|---|
| `1ccc69c2` | compare-models--gpt-image-1-5-vs-flux-2-pro **S01-m1** (the family's own listed hero example) | black canvas | light-grey `#f2f2f4` rounded card | vs-badge, model-logo, size chips |
| `e901b80b` | compare-models--ideogram-3-0-flash-vs-flux-2-pro S01-m1 | black canvas | light-grey `#f2f2f4` rounded card | vs-badge, model-logo, size chips |

Both are the *staggered two-result-card* form: the challenger sits directly on
the **black** canvas (no drawn card), the incumbent on a **light-grey rounded
mat** filling the right half. Identical geometry across both assets.

**Related differing-panel-ground forms** (viewed; confirm the *mechanism* recurs
beyond compare pages — a dark cell beside a light cell):

- `4e6bb6d9`, `c02d25a9` (ai-models--flux-2-klein…): a dark prompt card beside a light render/ad.
- `024b8aa7` (variation-generator): two product cards, orange vs magenta accents, on black.
- `5d64241c`, `c94c1d42` (scene-maker): a light product-photo card beside a coloured design/mockup card, on black.

**Counter-evidence — one shared ground** (viewed; these are the *dominant*
compare form and are NOT per-panel ground): `288da9d2`, `bd3c5739`, `6adeac96`,
`2adc1808`, `553d11df`, `a79dfb9e`, `7f9dc20b` — two photos on a single dark
(often dotted) ground with a bottom chip row.

**Modal counts (why this is a VARIANT, not a new default).** Of 53 distinct
`two-up` assets: white 30, black 8, photo-full-bleed 7, **mixed 6**, none 3,
light-grey 3, solid-colour 1. Within `compare-models` (183 assets): photo-full-
bleed 146, black 17, white 15, **mixed 5**. So a shared ground is modal (~89%);
per-panel *differing* ground (`ground=mixed` on a two-up/compare card) is the
~10% **hero** minority. Per STANDARD.md ("rarer real arrangements become named
variants, never the default") this ships as a named `split-tone` variant. The
`mixed` bag is also noisy — of the 14 two-up/split/stacked `mixed` assets, only
`1ccc69c2` and `e901b80b` are truly *two solid contrasting grounds*; the rest
are photo+card or photo+checkerboard. Hence **2 clean geometric exemplars**, one
of which is the family's canonical hero example.

Evidence images in this folder: `ev-1ccc69c2.png`, `ev-e901b80b.png` (the
canonical pair), `288da9d2.png`/`bd3c5739.png` (counter), `montage-twoup.png`
(the related forms), `full-1ccc69c2.png`/`full-e901b80b.png` (measured source).

---

## 2. MEASURED GEOMETRY (REF = 1600, from `1ccc69c2`, confirmed by `e901b80b`)

Ground read from the **opaque** pixels (these cards are flattened black/photo,
no alpha gutter to misread): the black canvas region and the light-grey
`#f2f2f4` card region were segmented and their bounding boxes measured; both
assets agree.

- **Canvas ground:** `#000000` (black). It IS the left panel's ground — no card is drawn on the left.
- **Right panel's mat card:** rounded, `#f2f2f4` (242,242,244), REF **(800, 200, 1600, 1400)** — starts exactly at the midline (measured seam x = 800 on both assets), flush to the right edge, inset ~200 top and bottom. radius ≈ 48.
- **Left photo panel:** REF **(110, 500, 690, 1240)** — square-ish, on the black canvas.
- **Right photo panel:** REF **(910, 500, 1490, 1240)** — square-ish, centred in the light mat.
- **VS round-badge:** centred on the seam, REF **(712, 712, 888, 888)** (the existing family rect works unchanged).
- **Per-panel label band** (above each photo, the model name; a `text` chrome, NOT a competitor logo): left REF (110, 300, 690, 470) white; right REF (910, 300, 1490, 470) near-black.
- **Per-panel chip row** (below each photo, size + ratio, e.g. `1024px` `1:1` / `2k` `1:1`): left ≈ REF y 1270–1380 from x 110; right ≈ REF y 1270–1380 from x 910. Dark chips (`#1c1e1e`, white text).

Measurement scripts: `q.py`-family and inline; the seam/vertical scans printed
`seam x=800`, `card vert y 200-1399` for both assets.

---

## 3. PROPOSED SPEC (do NOT implement — design only)

### 3a. families.py — add a `split-tone` variant to `vs-two-up`, and allow a per-panel `ground` on a panel entry

```python
# in FAMILIES["vs-two-up"] — keep the shipped shared-ground default as-is,
# add a `variants` block:
"variants": {
    # The documented hero form (style-families.md vs-two-up **Grid**: "one
    # panel black, one white", VS badge on the seam). Measured from 1ccc69c2
    # (the family's own hero example) and e901b80b: the challenger sits on the
    # BLACK canvas, the incumbent on a light-grey #f2f2f4 rounded MAT card
    # filling the right half (seam at x=800, card inset y 200..1400).
    "split-tone": {
        "ground": {"fill": BLACK},                          # canvas == the LEFT panel's ground
        "panels": {
            "left":  {"rect": (110, 500, 690, 1240)},        # on the black canvas, no card
            "right": {"rect": (910, 500, 1490, 1240),
                      # a panel's own ground: fill + the mat rect it fills
                      # (omit `rect` -> the panel's own rect; here the mat is larger)
                      "ground": {"fill": (242, 242, 244), "rect": (800, 200, 1600, 1400)}},
        },
        "chrome": [
            {"id": "vs", "kind": "round-badge", "rect": (712, 712, 888, 888), "text": "VS"},
            # model names are a `text` chrome the manager fills; never a competitor logo
            {"id": "label-left",  "kind": "text", "rect": (110, 300, 690, 470), "colour": [255, 255, 255], "text": ""},
            {"id": "label-right", "kind": "text", "rect": (910, 300, 1490, 470), "colour": [20, 20, 20], "text": ""},
            # size/ratio chips (dark, white text) — a later addition, per the doc
            {"id": "chip-left",  "kind": "label", "rect": (110, 1270, 300, 1370), "text": ""},
            {"id": "chip-right", "kind": "label", "rect": (910, 1270, 1075, 1370), "text": ""},
        ],
    },
},
```

The one new concept is a panel-level **`ground`**: `{"fill": (r,g,b), "rect":
(x0,y0,x1,y1)}` — the colour of the rounded card drawn *behind* that panel, and
the rect it fills (defaults to the panel's own `rect` when omitted). A panel
with no `ground` sits directly on the canvas ground, exactly as today.

### 3b. cli.py spec — the per-panel `ground:` override (what a worker writes)

Asymmetric (the measured corpus form — canvas + one card):
```yaml
family: vs-two-up
variant: split-tone
size: 1600x1600
ground:                 # keys that name panels (or `canvas`) => per-panel override
  canvas: black         # reserved key: the whole-slot ground
  right: light          # colour word (black/white/light) or {fill: [242,242,244]}
panels:
  left:  {image: a.png}
  right: {image: b.png}
```

Symmetric (the S08 `compose_S08.py` form — each half its own solid ground), on
the default template:
```yaml
family: vs-two-up
size: 1600x1600
ground: {left: white, right: black}     # no `canvas` key: each panel gets a full-cell card
panels: {left: {image: a.png}, right: {image: b.png}}
```

Back-compat: a whole-slot override (`ground: black`, or `ground: {fill: [...]}`
/ `{gradient: [...]}`) is unchanged — the mapping form is read as per-panel
**only** when its keys are not a subset of `{fill, gradient, direction}`.

### 3c. The three-line-ish plumbing this needs (proposal, not implemented)

- **`kinds.py`** — one new layer, no new kind:
  `LAYERS = {"ground": 0, "mat": 5, "card": 10, "panel": 20, ...}`. The mat draws
  below panels (20) and below explicit `card` chrome (10) like a prompt card.
- **`cli.py` `_ground`** — return `(base_ground, per_panel)`: split a mapping
  whose keys name panels/`canvas` into the `canvas` base and a
  `{panel_name: ground_spec}` map (each value run through the existing colour-
  word resolver). Subset-of-`{fill,gradient,direction}` keys keep today's
  whole-slot behaviour.
- **`cli.py` `resolve`** — merge the spec's `per_panel` onto each panel's family
  `ground`; for every panel that has a ground, synthesize a card op
  `{"id": f"mat-{name}", "kind": "card", "layer": "mat",
    "rect": ground.get("rect") or panel_rect, "fill": ground["fill"]}` and append
  it to `chrome` before scaling. Panels still draw on the panel layer, on top of
  their mat.

### New draw.py primitive / kinds.py Kind adapter needed?

**None.** The mat is a rounded solid card = the existing `draw.card` +
`kinds._card` (`Kind(_card, layer="card")`) drawn on the new `mat` layer. The VS
mark is the existing `round-badge`; labels/chips are the existing `text`/`label`
kinds. The only additions are data/plumbing (a `mat` layer value, a per-panel
`ground` key, and the `_ground`/`resolve` handling above) — no new drawing code.

---

## 4. PROTOTYPE RENDER (reuses EXISTING primitives)

Two throwaway renders in this folder, both produced with the current, unmodified
compose library:

1. **`proto-per-panel-ground.png`** — the measured `split-tone` geometry rendered
   by `proto_per_panel_ground.py` (a read-only-import section-local renderer, the
   same pattern as `runs/independent-1/sections/S08/compose_S08.py`). It calls
   only `draw.ground` / `draw.card` / `draw.panel` / `draw.round_badge` /
   `draw.box_text` with solid-colour placeholder panels (`pl-left.png`,
   `pl-right.png`). Output matches `ev-1ccc69c2.png` closely: black-canvas left
   panel, light-grey right mat, VS badge on the seam, per-panel label + chip rows.
   → `.../preset-research/proto-per-panel-ground.png`

2. **`proto-cli-desugar.png`** — proof the mechanism runs on the **live**
   `lp-compose` CLI today with zero code change, by expressing the right panel's
   ground as a `card` chrome item on the existing card layer:
   `uv run lp-compose proto_cli_desugar.yaml --out proto-cli-desugar.png`
   (`ground: black` + `chrome: [{id: mat-right, kind: card, rect: [800,0,1600,1600], fill: [242,242,244]}]`).
   It renders black-left / light-grey-right / VS-on-top correctly; the panels use
   the family's *default* rects (the CLI can't yet move panel rects or draw the
   label/chip bands), which is exactly why 3a adds the `split-tone` variant and
   3c adds the per-panel `ground` sugar.
   → `.../preset-research/proto-cli-desugar.png`

---

## 5. CONFIDENCE — **MEDIUM**

- **Mechanism: high.** Per-panel differing ground is documented as the
  `vs-two-up` hero ("one panel black, one white"), is required by the shipped
  S08 prototype, recurs across ≥7 corpus pages, and the whole-slot `ground:`
  override it generalises already exists in `cli._ground`. It reuses existing
  primitives (no new draw code).
- **Exact `split-tone` geometry: medium.** Measured from **2** clean assets
  (`1ccc69c2` — the family's own hero example — and `e901b80b`), which agree
  exactly. That is below the ≥10 STANDARD.md bar for a *default*, which is why it
  is scoped as a named variant of the documented hero form, not a new default.
  The label/chip bands are positioned from the same two assets and should be
  treated as a later, separately-verified addition (as the doc already flags:
  "Model pills and size chips arrive with a later variant").
- **Risk:** the `mixed` ground tag is noisy; a `/label-corpus` pass over the
  two-up/compare population would firm up the count and could surface more
  split-tone exemplars, which would raise this to high.
