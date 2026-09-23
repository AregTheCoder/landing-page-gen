# Preset proposal: `crop-grid` (a variant of the `crop-frame` family)

A 3x3 rule-of-thirds crop grid over a source photo, plus a circular crop badge
and a ratio/size label. It extends the family's existing `brackets` chrome
(corner L's + mid-edge ticks) with the interior thirds lines, and adds the
circular badge that the crop-image page uses as its signature. It fills the
`crop-frame crop-grid` slot the audit left deferred
(`research/template-audit/crop-frame.md` §(d), STANDARD.md "Deferred").

Read-only research. Nothing in the repo was edited. Corpus assets were read
from `corpus/pages/<page>/media/` (decoded with Pillow, zero network, zero
credits). Geometry was measured on the 1600px originals; ground was measured
from the alpha channel per the STANDARD rule.

---

## (1) EVIDENCE

**Family:** `crop-frame` (namesake page `crop-image`). The preset is a new
`variant` of it, not a new family.

**How the grid was found.** The `crop-grid` chrome kind exists in the enum
(`attrs.FIELDS["chrome"]`) but is applied to **0** assets — the labelling pass
captured the grid under `brackets`/`selection-handles`. So the population was
found by description text ("rule of thirds", "crop grid", "crop frame") over
`corpus/attributes.yaml`, then every candidate was viewed.

**≥10 corpus assets that show the thirds grid** (13 distinct ids):

| id | page / slot | ground (alpha) | layout | what it shows |
|----|-------------|----------------|--------|---------------|
| `4c0b8b9b` | crop-image S01-m1 (hero) | transparent (0.23) | overlapping cards | back food photo + grid, front clean photo, black crop badge left |
| `c78690a2` | crop-image S05-m1 | transparent (0.31) | overlapping cards | back portrait + grid, front clean, crop badge left, "Pinterest / 1000 x 1500 px" label card |
| `d93605b1` | crop-image S06-m1 | transparent (0.31) | overlapping cards | back surfer + grid, front = IG-post mockup, crop badge right |
| `24e4540f` | crop-image S09-m1 | transparent (0.41) | overlapping cards | large clean result + small gridded inset, round "AI" badge |
| `6082f48b` | crop-image S10-m1 | transparent (0.32) | overlay | grid over a face in a lips collage |
| `9e4e068f` | ai-models--flux-2-max S01-m1 | **black (painted)** | overlapping cards | back gridded + front clean, vertical round tool rail (crop is one) |
| `639e11c1` | background-tools S12-m4 | photo-full-bleed | single | one photo, thick handle brackets + full thirds grid centred |
| `54f94706` | ai-design-generator S11-m9 / image-tools S04-m3 | photo-full-bleed | single | photo on editor canvas, thirds grid + handles |
| `d009e3c0` | ai-image-extender S15-m7 | photo-full-bleed | single | crop brackets + grid + "1080" size label |
| `35fd07a1` | batch-photo-editor S05-m1 | transparent (0.28) | grid (3 tiles) | three photos each under a thirds grid + corner handles |
| `b95353fc` | batch-photo-editor S11-m1 | transparent | split (2) | batch of vase photos each under a crop grid |
| `fa2a98b6` | batch-photo-editor S09-m1 | transparent | overlay (3) | several photos + crop grid + "+50 photos" pill |
| `3266d99b` | book-cover-maker S10-m1 | black | column-main | poster with a crop frame — **likely misfiled** (template-mockup), listed for completeness |

**Modal layout (counts over the 12 in-family assets, excluding the `3266d99b` misfile):**

- **Overlapping two cards** — back photo under the grid, front the clean result,
  a circular crop badge on the seam: **5/12** (`4c0b8b9b`, `c78690a2`,
  `d93605b1`, `24e4540f`, `9e4e068f`). This is the crop-image namesake signature
  and the plurality layout.
- Single full-bleed photo + grid overlay: 2/12 (`639e11c1`, `54f94706`) — plus
  each batch tile is this form repeated.
- Batch of gridded tiles: 3/12 (`35fd07a1`, `b95353fc`, `fa2a98b6`).
- **The 3x3 grid itself appears in 12/12** — it is the defining chrome.
- **Circular crop badge present in 4/4** of the crop-image cms overlapping cards
  (`4c0b8b9b`, `c78690a2`, `d93605b1`, `24e4540f`); `9e4e068f` swaps it for a
  round tool rail.
- **A ratio/size label present in** `c78690a2` (two-line card), `d009e3c0`
  ("1080"), `5f91c6aa` ("x2" on the brackets), plus format chips on resize pages.

The preset therefore templates the **overlapping-cards layout**: back gridded
source, front clean result, circular crop badge, ratio/size label.

---

## (2) MEASURED GEOMETRY (REF = 1600)

**Ground — measured from alpha, not a flattened RGB read.** The four crop-image
cms cards are **transparent** (fully-transparent gutter fraction 0.23 / 0.31 /
0.31 / 0.41; all four corners alpha 0). The current `crop-frame` default
(`ground: BLACK`) and the audit's "10/13 black" are the exact RGBA→RGB illusion
STANDARD.md failure #2 warns about — even the current template model `5f91c6aa`
has alpha-0 corners, and the "white" batch tile `35fd07a1` is transparent too.
The one genuinely painted-black asset is `9e4e068f` (an ai-models dark card;
corners `(0,0,0,255)`). **The variant ground is transparent (`fill: None`).**

**Grid = rule-of-thirds, confirmed by interior line positions:**
- `639e11c1` (clean single): interior lines at fraction **0.34 and 0.66** in
  both axes, plus the frame edge — i.e. 1/3 and 2/3.
- `c78690a2` (back card): grid frame bbox `(613, 233, 1463, 1075)` (850x842,
  ~square); interior horizontals at y-fraction **0.335 and 0.662**.

**Circular crop badge — a black disc + white crop glyph:**
- `4c0b8b9b`: disc `(92, 368, 368, 648)`, d ≈ **278**, centre (230, 508) — fully
  on-canvas, left of the front card.
- `c78690a2`: disc `(0, 252, 256, 508)`, d ≈ **256**, on the left edge (bleeds off).
- `d93605b1`: disc `(1336, 384, 1596, 648)`, d ≈ **262**, right edge (bleeds off).
- So: diameter ≈ **256–278** (~0.16–0.17 of the canvas), sits on a card seam,
  may bleed off the nearest edge.

**Ratio/size label card** (`c78690a2`): dark rounded card `(1100, 884, 1596,
1288)` = **496x404**, bottom-right, two centred lines (format name + "W x H px").

**Panel cards:** two overlapping rounded photo cards (~55–65% of the canvas
each), one top-right (gridded), one bottom-left (clean), overlapping ~1/3
diagonally. Exact rects vary per asset; the proposal uses representative rects
generalised from `c78690a2`/`4c0b8b9b`.

---

## (3) PROPOSED SPEC

### 3a. `FAMILIES["crop-frame"]["variants"]` entry (paste-ready)

Add this `variants` block to the existing `"crop-frame"` family dict in
`src/landing_page_gen/compose/families.py` (the family currently has no
variants):

```python
        "variants": {
            # The crop-image namesake signature (4c0b8b9b S01 hero, c78690a2 S05,
            # d93605b1 S06, 24e4540f S09): two overlapping rounded photo cards on a
            # TRANSPARENT ground (measured from alpha: 0.23-0.41 alpha-0 gutters, not
            # black), the back card under a rule-of-thirds crop grid, the front card
            # the clean result, a black circular crop badge on the seam, and a dark
            # rounded ratio/size label. Fills STANDARD.md's deferred `crop-grid`.
            "crop-grid": {
                "ground": {"fill": None},
                "panels": {
                    "source": {"rect": (600, 110, 1510, 1120)},   # back, gridded
                    "result": {"rect": (90, 560, 850, 1470)},     # front, clean, overlaps the corner
                },
                "chrome": [
                    # the existing brackets PLUS interior thirds lines (grid: True); inset
                    # to the back card's outer ~65% so the front card does not cross it
                    # (639e11c1 interior lines at 1/3, 2/3; c78690a2 frame 613-1463 x 233-1075)
                    {"id": "grid", "kind": "brackets", "at": "source",
                     "frac": (0.30, 0.09, 0.95, 0.90), "grid": True},
                    # black disc + white crop glyph, d~260 on the seam
                    # (4c0b8b9b d278 @ (230,508); c78690a2 d256 left edge)
                    {"id": "crop-badge", "kind": "crop-badge",
                     "rect": (470, 430, 730, 690), "icon": "crop"},
                    # dark rounded ratio/size label bottom-right (c78690a2 card 496x404 @ (1100,884))
                    {"id": "ratio", "kind": "label", "rect": (1090, 900, 1560, 1300), "text": "1:1"},
                ],
            },
        },
```

`template()` merges a variant by replacing whole keys, so the variant's
`ground`, `panels` and `chrome` cleanly override the family defaults; `aspect`
and `radius` are inherited. A spec uses it with `variant: crop-grid` (or the
brief's `> device:`), `size: 1600x1600`, and one image per panel
(`source`, `result`).

### 3b. NEW primitive — extend `draw.brackets` (draw.py)

The task's "extends the existing brackets" is literal: add one optional arg to
the existing primitive.

```python
def brackets(canvas, rect, text, fnt, stroke, colour=WHITE, grid=False):
    ...                                   # unchanged: 4 corner L's + 4 mid-edge ticks + label
    if grid:                              # NEW: interior rule-of-thirds lines
        x0, y0, x1, y1 = rect
        thin = max(1, round(stroke * 0.6))
        for f in (1/3, 2/3):
            gx, gy = x0 + (x1 - x0) * f, y0 + (y1 - y0) * f
            d.line([(gx, y0), (gx, y1)], fill=colour, width=thin)
            d.line([(x0, gy), (x1, gy)], fill=colour, width=thin)
    return rect
```

One-line behaviour: when `grid`, draws two interior verticals and two
horizontals at 1/3 and 2/3 across the bracket rect (the rule-of-thirds grid).

And the `_brackets` adapter in `kinds.py` passes it through (one changed line):

```python
def _brackets(canvas, it, ctx):
    x0, y0, x1, y1 = ctx.panels[it["at"]]["rect"]
    fx0, fy0, fx1, fy1 = it["frac"]
    w, h = x1 - x0, y1 - y0
    return draw.brackets(canvas, (x0 + w*fx0, y0 + h*fy0, x0 + w*fx1, y0 + h*fy1),
                         it.get("label", ""), ctx.font("brackets"),
                         max(1, round(10 * ctx.s)), grid=it.get("grid", False))  # NEW: grid
```

### 3c. NEW primitive — `draw.disc_icon` + a `crop-badge` Kind

The crop badge is a filled circle carrying a white line icon — `draw.badge`
(rounded square + check) and `draw.round_badge` (circle + *text*) both exist,
but neither is a circle + arbitrary icon, so add the small primitive:

```python
# draw.py
def disc_icon(canvas, rect, name, fill=(0, 0, 0)):
    """A filled circle carrying a white line icon (the crop-tool badge)."""
    x0, y0, x1, y1 = (round(v) for v in rect)
    layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    ImageDraw.Draw(layer).ellipse((x0, y0, x1, y1), fill=tuple(fill) + (255,))
    inset = (x1 - x0) * 0.30
    icon(layer, (x0 + inset, y0 + inset, x1 - inset, y1 - inset), name)
    canvas.alpha_composite(layer)
    return (x0, y0, x1, y1)
```

```python
# kinds.py
def _crop_badge(canvas, it, ctx):
    return draw.disc_icon(canvas, it["rect"], it.get("icon", "crop"),
                          tuple(it.get("fill") or (0, 0, 0)))
# register in KINDS:
"crop-badge": Kind(_crop_badge),
```

One-line behaviour: black (or given) disc with a white 24-grid line icon
inset 30% — the crop glyph already exists in `draw.ICONS["crop"]`.

### 3d. Ratio label — REUSES the existing `label` kind

No new code. `label` already draws a dark rounded box (`fill (28,28,28,255)`)
with centred white text — exactly the ratio pill. Use `text: "1:1"`,
`"1080 x 1080 px"`, etc. (the manager's string, per the plan's label rule).

*Optional enrichment (not required by this preset):* the two-line
"Pinterest / 1000 x 1500 px" card of `c78690a2` needs multi-line text — stack a
`label` (format) + a `text` item (size) at the same rect, or add a future
`label-card` primitive. Left out of the minimal preset.

### 3e. One caveat to flag — layer order / occlusion

Chrome always draws above panels (`LAYERS`: panel=20 < chrome=30), so a grid
placed as chrome paints over the *front* card wherever they overlap. The
default `frac` above insets the grid clear of the overlap corner, which reads
correctly (see the prototype). For arrangements where the front card should
genuinely occlude the grid (as in `c78690a2`), the robust fix is a per-panel
`grid` option handled in `cli._draw_panel` so the source panel draws its grid
immediately after its image and before the `result` panel — a small, contained
change. The minimal preset avoids it by insetting the grid.

---

## (4) PROTOTYPE RENDER

A throwaway renderer (read-only import of `landing_page_gen.compose.draw`, the
same pattern as `runs/independent-1/sections/S02,S08`) inlines the two new draw
bits (§3b, §3c) and renders the proposed geometry with solid-colour placeholder
panels — nothing in the repo is touched:

- script: `proto_crop_grid.py`
- placeholders: `ph-source.png`, `ph-result.png`
- output (transparent RGBA): `proto-crop-grid.png`
- flattened on a page-white surround for viewing: `proto-on-white.png`

(all in this folder:
`<2026-09-22 session scratchpad, not kept>/`)

The render reproduces the modal `c78690a2` arrangement: back card top-right
under corner brackets + mid-edge ticks + interior 1/3–2/3 grid lines; front
clean card overlapping bottom-left; black circular crop badge with the white
crop glyph on the seam; dark "1:1" ratio label bottom-right; transparent
ground. A pure `lp-compose` CLI render is not possible yet because a spec cannot
move panel rects (rects are fixed by the family), so the overlapping layout only
exists once the variant is added to `families.py`; the scratch script stands in
for that.

---

## (5) CONFIDENCE

**High** on the pattern and the two primitives; **medium** on the exact panel
rects.

- ≥10 assets (13 distinct), the 3x3 grid in 12/12, the overlapping-cards layout
  the plurality (5/12) and the crop-image namesake signature → **high** that the
  preset templates a real modal, not an exemplar.
- Ground (transparent), rule-of-thirds fractions (1/3, 2/3), badge diameter
  (~256–278) and label-card size (496x404) are pixel/alpha measurements →
  **high**.
- The exact overlapping panel rects vary per asset (the audit itself gave "~"
  rects); mine are representative, generalised from `c78690a2`/`4c0b8b9b` →
  **medium**. Worth a designer eyeball on a real render before shipping.
- The layer-order/occlusion caveat (§3e) is a real limitation the default frac
  sidesteps; heavy-overlap fidelity needs the small `cli._draw_panel` change.
