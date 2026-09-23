# Preset 06 — Multi-aspect mapping (cross-cutting)

Extend the `aspects` mechanism (today only on `panel-overlay`) so
`dark-composite`, `template-mockup` and `before-after` can render the same
family at more than one slot ratio, with the **panel rects remapped per
aspect** instead of a 1:1-only geometry that overflows a wide canvas.

This is a mechanism proposal plus per-family aspect blocks, not one card.
Read-only research on branch `layered-templates`; nothing under version control
was edited.

---

## 0. Why the current mechanism is not enough

`cli.py` scales every family rect by **width only**: `s = w / REF * SS`
(`REF = 1600` is the width). The canvas *height* changes with the slot ratio
(`ref_h = round(REF * h / w)`), but a rect authored in the 1600×1600 frame keeps
its absolute pixels — so a 1:1 panel at `y1=1450` runs off the bottom of an
800-tall (2:1) or 900-tall (16:9) canvas.

`panel-overlay` gets away with `aspects: ((4,3),(5,4))` for two reasons that do
**not** generalise:

1. Its only panel is `rect: None` → `resolve()` fills `(0,0,w*SS,h*SS)`, i.e. the
   whole slot at any ratio.
2. Its chrome (`adjust-panel` at y 300–900, `tool-pill` at y 120–620) is authored
   in a 4:3 frame (`ref_h=1200`) and happens to still fit inside the 5:4 frame
   (`ref_h=1280`). It is never *remapped* — the two ratios are close and the
   chrome clears both.

So today `aspects` means **"these near-neighbour ratios all reuse one geometry
unchanged"**. The three target families have **fixed panel rects** and a
tool-column / card topology; they need the panels re-placed, not just a taller
or shorter canvas. Two concrete breakages confirmed at the CLI:

- `before-after` already ships a `wide` variant (aspect **21:10**) for the modal
  2:1 card, but it is a *named device* you must select with `variant: wide`;
  there is no block for 16:9 and nothing auto-picks by slot size.
- A true **2:1** slot (`1600x800`) is **rejected** by that 21:10 block —
  `lp-compose: size 1600x800 is not 21:10 like before-after` — because
  `load_spec`'s ratio tolerance is `0.02` and `|2.0/2.1 − 1| = 0.048`. The band
  is too tight for one block to serve the 2:1 / 21:10 / ~2.1:1 spread that the
  corpus actually contains.

`runs/independent-1` already worked around all of this by hand: **S02**
(`compose_s02.py`, before-after **16:9**, before|after split + divider) and
**S08** (`compose_S08.py`, vs-two-up **16:9** hero) are section-local renderers
that import `compose/draw.py` and re-implement panel placement because
"no `FAMILIES` entry declares 16:9" (their own comments). Those two scripts are
the existence proof that the 16:9 need is real and that the fix belongs in the
family layer, not in per-section Python.

---

## 1. EVIDENCE

### 1a. The multi-aspect need, quantified

Aspect-class tally per family across `corpus/attributes.yaml` (2888 records),
family assigned by `taxonomy.family_of`:

| family | n | 1:1 | landscape-wide (5:4 / 16:10 / 2:1 / 16:9 / 4:3 / 3:2 / 21:9) | portrait (9:16 / 2:3 / 3:4 / 4:5) |
|---|---|---|---|---|
| **before-after** | 123 | 56 (46%) | **67 (54%)** — 5:4·27, 16:10·18, 2:1·16, 4:3·4, 3:2·1 | 4:5·1 |
| **dark-composite** | 89 | 69 (78%) | **20 (22%)** — 5:4·12, 16:10·5, 2:1·2, 16:9·1 | — |
| **template-mockup** | 422 | 179 (42%) | **109 (26%)** — 5:4·39, 16:10·31, 16:9·16, 2:1·8, 3:2·9, 4:3·3, 21:9·3 | 134 (2:3·51, 3:4·36, 9:16·23, 4:5·24) |
| panel-overlay (ref) | 28 | 13 | 4:3·5, 5:4·5, 16:10·4, 3:2·1 | — |

Reading: **fewer than half** of `before-after` and `template-mockup` assets are
square. `template-mockup` alone spans **11** aspect classes. The 1:1-only
templates are modelling the minority case for two of the three families.

Note a scope split for `template-mockup`: its **portrait** classes (134) are a
different design problem (tall poster/story cards) — out of scope here; this
preset addresses the **landscape-wide** classes and keeps 1:1 as the default.

### 1b. before-after — the wide (2:1) block (≥10 assets, HIGH)

`aspect_class` 2:1, all `layout: split`, the modal composite the family
docstring already cites (`08385997`, `c5715e9b`):

`08385997` (ai-image-enhancer S09), `c5715e9b` (image-upscale S07),
`344e094b` (image-enlarger S06), `2b7a985a` (ai-models--recraft-v4-styles S08),
`41c41e72` (ai-models--recraft-v4-styles-pro S08), `5acfd40b` (ai-models--imagen-4-0 S05),
`6e1c292f` (ai-models--flux-3 S09), `768fcebb` (ai-models--hailuo-3 S06),
`85677966` (ai-models--grok-imagine S06), `bb63a74c` (ai-models--flux-2-klein-4b S05),
`dad15a71` (ai-models--google-omni S06), `e6fe5f30` (ai-models--runway-aleph-2-0 S05),
`5bb50e97` (ai-replace S08), `0af91011` (flip-video S08),
`2c990e97` (remove-object-from-video S09), `f223c881` (video-enhancer S10).
**n = 16**, modal layout = before (small, top-left) + enlarge tile under it,
result (large, right), "Before"/"After" pills. This exact geometry is already
in `families.py` as the `wide` variant, measured in
`research/template-audit/before-after.md` from `08385997`/`c5715e9b`. The 1:1
stacked card is the rare case (**1/20** composites: `69ed3f5c`).

### 1c. dark-composite — the wide (2:1 / 16:10 / 16:9) block (MEDIUM)

Same **column-main** topology as the 1:1 default, on a wider/shorter canvas:

- 2:1: `e247e30d` (resize-image S08, column-main, 4 format tiles left + full-height
  photo right), `f57c774f` (collage-maker S10, column-main, 5-thumb column left +
  collage right).
- 16:10: `3062ad35` (video-tools S02, column-main), `464e0bea` (design S03,
  column-main), `7050565e` (ai-design-tools S06), `a80f238f` (ai-design-tools S07),
  `b54783a7` (ai-design-tools S06).
- 16:9: `b476daea` (flow S11, column-main, 8-panel board).

**n = 8 landscape-wide** (2 clean 2:1 + 5 at 16:10 + 1 at 16:9). Fewer than the
10-asset bar for a template default — hence MEDIUM and proposed as a *block*, not
a re-tag of the family default. The 1:1 column-main default (corrected spec in
`research/template-audit/dark-composite.md`, evidence `21cdafd9`, `8031c225`,
`d5d56eb0`, `f57c774f`, `87c30e6b`, `e247e30d`, `bd014004`) stays the default.

### 1d. template-mockup — wide is single-card, not tile-column (LOW for column)

Of the landscape-wide `template-mockup` assets, the ones with a real tile column
are only `9e0a38de` (ai-models S02, 16:10), `a68edf30` (design S05, 16:10),
`abb45bdc` (ai-design-tools S05, 16:10), `d9aa2404` (design S04, 16:10, pc=6) —
**n ≈ 4**. The large majority of wide template-mockup assets are `layout: single`
(the finished card fills the frame): e.g. 16:9 `86b946c1`, `b607f718`,
`f076e3f7`, `715e6d64`, `3f5c7dfe`; 2:1 `a710062f`, `e6f7b7a0`. So the honest
wide template-mockup block is **card-fills-frame** (photo panel ≈ whole frame,
tile column dropped), which is a trivial remap; a wide block *with* the tile
column is thin evidence → deferred.

---

## 2. MEASURED GEOMETRY (REF = 1600 wide × `ref_h` tall)

`ref_h = round(1600 · h / w)`: **1:1 → 1600**, **16:9 → 900**, **2:1 → 800**,
**21:10 → 762**. Ground is measured from the audits (alpha where transparent,
pixels where painted): before-after = **transparent** (`fill: None`, alpha-0
gutters on all 20 composites); dark-composite = **black** (13/13, opaque
measured); template-mockup = **transparent** (12/14).

### 2a. before-after · 2:1 block (from `08385997`/`c5715e9b`, native 1060×504 ×1.509→REF, ref_h≈762)

```
before  (24,  24, 610, 519)       # 388×328 native
result  (622, 24, 1576, 737)      # 632×472 native
tile    (24, 531, 610, 737)       # 388×136 native, enlarge glyph
before-pill  bl of `before`, solid-dark
after-pill   bl of `result`, solid-dark      # "After" rides the RESULT
```
(Identical to today's `wide` variant — reused verbatim.)

### 2b. before-after · 16:9 block (from `runs/independent-1/S02`, before|after split)

```
before  (0,   0, 800, 900)        # ref_h=900
after   (800, 0, 1600, 900)
before-pill  bl of `before`, translucent
after-pill   bl of `after`,  translucent
divider  x=800, 4 px, white @ ~50% (a thin seam, not a panel)
```
This is `compose_s02.py`'s exact geometry, promoted into the family. (A hairline
divider is the one new chrome item — see §3d.)

### 2c. dark-composite · 2:1 block (fitted to `e247e30d`/`f57c774f`, measured below)

Alpha/luma content measured on the two clean 2:1 assets, scaled to REF:

| asset | native | content x (REF) | content y (REF) | column│main gap (REF x) |
|---|---|---|---|---|
| `e247e30d` | 1060×504 | 24–1532 | 24–735 | 166–181 |
| `f57c774f` | 2120×1008 | 24–1575 | 24–736 | 254–266 |

Both: outer margin ≈ **24**, a left tool column, main panel filling to x≈1576 and
down to y≈736. The **column-width invariant** (fixed-width left column, main panel
fills the rest) is the remapping principle. Proposed block, `ref_h=800`:

```
tile-1  (24,  24, 300, 300)       # tool-glyph tile, #1c1c1e
tile-2  (24, 324, 300, 500)       # magenta accent = the active tool
tile-3  (24, 524, 300, 776)       # colour-swatch / content-thumb tile
photo   (340, 24, 1576, 776)      # the result card, fills the remainder
```
Column 276 wide (narrower than the 1:1 block's 380, because vertical room is
compressed); margins 24 (vs 150 at 1:1 — wide cards are tight, both measured
assets confirm). Same three-box column, same one main panel, same black ground.

### 2d. dark-composite · 1:1 default (unchanged, for reference)

```
tile-1 (150,150,530,530); tile-2 (150,570,530,950); tile-3 (150,990,530,1450)
photo  (570,150,1450,1450)        # inset 150, column left, per the audit's corrected spec
```

### 2e. template-mockup · wide (16:9 / 2:1) block — card-fills-frame

```
photo  (24, 24, 1576, ref_h-24)   # the finished card fills the frame, inset 24
                                   # tile column dropped (wide singles carry none)
```
Chrome: none by default at wide (the card is one design). Ground transparent.

---

## 3. PROPOSED SPEC

### 3a. Mechanism — `aspects` gains a mapping form (paste-ready)

`aspects` today is a tuple of `(w,h)` pairs used **only** for size validation
(`cli.load_spec`). Extend it to accept **either**:

- **tuple form** (unchanged): `((4,3),(5,4))` — every listed ratio reuses the base
  geometry. `panel-overlay` keeps working byte-for-byte.
- **mapping form** (new): `{"1:1": {...}, "2:1": {...}, "16:9": {...}}` — each key
  is an aspect label, each value an override block merged onto the family exactly
  like a `variant` (a key the block omits is inherited). The family's top-level
  `aspect` names the default block.

`cli.py` changes (minimal — reuse the variant merge and the rect scaler already
there):

```python
# families.py — helper next to nearest_ratio()
def aspect_blocks(fam):
    """{'w:h': override} when the family uses the mapping form, else {}."""
    a = fam.get("aspects")
    return a if isinstance(a, dict) else {}

# cli.py — template(): layer the aspect block UNDER any named variant
def template(fam, variant=None, aspect=None):
    f = FAMILIES[fam]
    base = {k: v for k, v in f.items() if k not in ("variants", "aspects")}
    blocks = f["aspects"] if isinstance(f.get("aspects"), dict) else {}
    if aspect and aspect in blocks:
        base = {**base, **blocks[aspect]}
    if not variant:
        return base
    variants = f.get("variants") or {}
    if variant not in variants:
        sys.exit(f"lp-compose: {fam} has no variant {variant!r}; "
                 f"one of {', '.join(variants) or 'none'}")
    return {**base, **variants[variant]}

# cli.py — pick the block by the spec's size (auto-select), nearest ratio wins
def _aspect_for(fam, w, h):
    blocks = aspect_blocks(FAMILIES[fam])
    if not blocks:
        return None
    t = math.log(w / h)
    return min(blocks, key=lambda lbl: abs(math.log(ratio_value(lbl)) - t))
```

`load_spec` / `resolve` then call `template(fam, _preset(spec), _aspect_for(fam, w, h))`
and drop the hard `0.02` reject for mapping-form families (nearest-block wins;
keep the reject only for the tuple form, whose ratios are exact by construction).
`describe()` gains one line per aspect block, same as it already does per variant.

**No change to `draw.py` and no change to `kinds.py`** — every panel/chrome kind
in these blocks (`tile`, `card`, `pill`, `photo` panels) already exists. The
remap is pure geometry.

### 3b. before-after — fold `wide` into `aspects`, add 16:9

```python
"before-after": {
    "aspect": (1, 1),                       # default block = the 1:1 stacked card
    "aspects": {
        "1:1": {},                          # inherit the base panels+chrome (below)
        "2:1": {                            # modal wide card, 16 assets (08385997, c5715e9b, …)
            "panels": {
                "before": {"rect": (24, 24, 610, 519)},
                "result": {"rect": (622, 24, 1576, 737)},
            },
            "chrome": [
                {"id": "before-pill", "kind": "pill", "at": "before", "corner": "bl", "text": "Before", "style": "solid-dark"},
                {"id": "after-pill",  "kind": "pill", "at": "result", "corner": "bl", "text": "After",  "style": "solid-dark"},
                {"id": "tile", "kind": "tile", "rect": (24, 531, 610, 737), "icon": "enlarge"},
            ],
        },
        "16:9": {                           # before|after split, from runs/independent-1/S02
            "panels": {
                "before": {"rect": (0, 0, 800, 900)},
                "after":  {"rect": (800, 0, 1600, 900)},
            },
            "chrome": [
                {"id": "before-pill", "kind": "pill", "at": "before", "corner": "bl", "text": "Before", "style": "translucent"},
                {"id": "after-pill",  "kind": "pill", "at": "after",  "corner": "bl", "text": "After",  "style": "translucent"},
                {"id": "divider", "kind": "divider", "at_x": 800, "width": 4, "colour": [255, 255, 255, 130]},
            ],
        },
    },
    "ground": {"fill": None}, "radius": 40,
    "panels": {                             # the 1:1 default (69ed3f5c)
        "before": {"rect": (0, 0, 604, 632)},
        "after":  {"rect": (0, 664, 604, 1296)},
        "result": {"rect": (636, 0, 1600, 1600)},
    },
    "chrome": [
        {"id": "before-pill", "kind": "pill", "at": "before", "corner": "bl", "text": "Before", "style": "translucent"},
        {"id": "after-pill",  "kind": "pill", "at": "after",  "corner": "bl", "text": "After",  "style": "translucent"},
        {"id": "tile", "kind": "tile", "rect": (0, 1328, 604, 1600), "icon": "enlarge"},
    ],
},
```

The old named `variants: {wide: …}` can stay as an alias for one release, but the
`aspects["2:1"]` block makes it redundant — a worker just gives the slot's 2:1
size and gets the wide card.

### 3c. dark-composite — add `aspects` (1:1 default + 2:1)

```python
"dark-composite": {
    "aspect": (1, 1),
    "aspects": {
        "1:1": {},                          # inherit the column-left default below
        "2:1": {                            # wide column-main (e247e30d, f57c774f)
            "panels": {"photo": {"rect": (340, 24, 1576, 776)}},
            "chrome": [
                {"id": "tile-1", "kind": "tile", "rect": (24,  24, 300, 300), "icon": "sparkle", "fill": (28, 28, 30)},
                {"id": "tile-2", "kind": "tile", "rect": (24, 324, 300, 500), "icon": "crop", "fill": MAGENTA},
                {"id": "tile-3", "kind": "tile", "rect": (24, 524, 300, 776), "fill": (90, 90, 96)},
            ],
        },
    },
    "ground": {"fill": BLACK}, "radius": 40,
    "panels": {"photo": {"rect": (570, 150, 1450, 1450)}},   # 1:1 default (per audit)
    "chrome": [
        {"id": "tile-1", "kind": "tile", "rect": (150, 150, 530, 530), "icon": "sparkle", "fill": (28, 28, 30)},
        {"id": "tile-2", "kind": "tile", "rect": (150, 570, 530, 950), "icon": "crop", "fill": MAGENTA},
        {"id": "tile-3", "kind": "tile", "rect": (150, 990, 530, 1450), "fill": (90, 90, 96)},
    ],
    "variants": { ... existing reference-thumbs / model-picker / two-up ... },
},
```
Device `variants` compose *on top of* the selected aspect block via the layered
`template()` above, so `reference-thumbs` at 2:1 is expressible later without a
new mechanism.

### 3d. template-mockup — add a wide card-fills-frame block

```python
"template-mockup": {
    "aspect": (1, 1),
    "aspects": {
        "1:1": {},
        "16:9": {"panels": {"photo": {"rect": (24, 24, 1576, 876)}}, "chrome": []},
        "2:1":  {"panels": {"photo": {"rect": (24, 24, 1576, 776)}}, "chrome": []},
    },
    "ground": {"fill": None}, "radius": 40,
    "panels": {"photo": {"rect": (600, 200, 1400, 1400)}},   # 1:1 default (card + tile column)
    "chrome": [ ... existing card + tile-1/tile-2/swatch ... ],
},
```
`ref_h-24` written out: 16:9 → 876, 2:1 → 776. A wide block *with* the tile column
is left for later (evidence n≈4).

### 3e. New primitive / kind needed?

- **draw.py**: none for dark-composite (2c) and template-mockup (2e) — existing
  `tile`/`card`/`photo` only.
- **draw.py + kinds.py**: **one** small kind for the before-after 16:9 divider —
  a `divider` kind. `runs/independent-1/S02` draws it inline as a 4 px
  `ImageDraw.rectangle`; promoting it is ~6 lines:
  ```python
  # draw.py
  def divider(canvas, x, top, bottom, width, colour):
      ImageDraw.Draw(canvas).rectangle((x - width/2, top, x + width/2, bottom), fill=tuple(colour))
      return (x - width/2, top, x + width/2, bottom)
  # kinds.py — adapter: reads at_x (REF x), width, colour; spans the canvas height
  def _divider(canvas, it, ctx):
      _, H = canvas.size
      return draw.divider(canvas, it["at_x"] * ctx.s, 0, H, it["width"] * ctx.s, it.get("colour", [255,255,255,130]))
  KINDS["divider"] = Kind(_divider)
  ```
  If you would rather not add a kind now, the 16:9 before-after block can ship
  without the divider (the gutter between the two panels already reads as a seam);
  the divider is cosmetic.

---

## 4. PROTOTYPE RENDER

All reuse **existing** primitives; all free/offline.

- `proto_before_after_wide.png` — **real `lp-compose` CLI run** of the shipped
  `before-after` `wide` block (aspect 21:10, `size: 1600x762`) with solid
  placeholder panels. Confirms the 2:1 panel-remap renders today with no code
  change: before + enlarge tile top-left, result right, Before/After pills in the
  right places. Spec: `proto_before_after_wide.yaml`.
- `proto_before_after_square.png` — the 1:1 default, for side-by-side contrast.
- `proto_dark_composite_wide.png` — the **proposed** dark-composite 2:1 block
  (2c), rendered by a throwaway section-local script
  (`proto_dark_composite_wide.py`, read-only import of `compose/draw.py`, nothing
  added to `FAMILIES`). Black ground, fixed-width 3-tile column left (dark glyph /
  magenta accent / grey swatch), main photo filling the rest — matches
  `e247e30d`/`f57c774f`. Proves the remap needs no new draw primitive.
- Tolerance check: `proto_tol.yaml` at `size: 1600x800` (true 2:1) against the
  21:10 `wide` block is **rejected** by the CLI — the finding behind the
  "nearest-block, drop the 0.02 reject" part of §3a.

All under
`<2026-09-22 session scratchpad, not kept>/`.

---

## 5. CONFIDENCE

- **Mechanism (aspects-as-mapping + nearest-block auto-select): HIGH.** It reuses
  the existing variant-merge and width-based rect scaler; the CLI, S02/S08 and the
  shipped `wide` variant all corroborate the shape of the need, and the prototype
  renders with no `draw.py`/`kinds.py` change (bar the optional 6-line divider).
- **before-after 2:1 block: HIGH** — 16 corpus assets, geometry already measured
  and shipping.
- **before-after 16:9 block: MEDIUM-HIGH** — one direct precedent
  (`runs/independent-1/S02`) rather than ≥10 corpus assets at that exact ratio;
  geometry copied from a working renderer.
- **dark-composite 2:1 block: MEDIUM** — 2 clean 2:1 + 6 more landscape-wide
  (n=8, under the 10-asset bar); measured column-width-invariant is principled but
  fitted to 2 assets, so it ships as a *block*, not a re-tag of the default.
- **template-mockup wide (card-fills-frame): MEDIUM**; **wide-with-tile-column:
  LOW** (n≈4) → deferred.

Thin-evidence items are flagged, not smoothed over: the dark-composite column
proportions (n=2 at true 2:1) and any wide template-mockup tile column want a
`/label-corpus` pass before they become defaults.
