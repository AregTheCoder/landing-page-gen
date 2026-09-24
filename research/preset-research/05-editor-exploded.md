# Preset proposal: `template-mockup` **/editor** exploded view

The designed card shown on an editor canvas with its component layers pulled
apart: a **checkerboard cutout panel** (with a selection frame + drag handles)
and an **"Aa Aa" type tile** in a left column, the finished **design card** on
the right, and a full-width **colour-swatch bar** across the bottom. This is
"Layout B" in `research/template-audit/template-mockup.md`, which specified it
as deferred pending new primitives. This proposal re-measures it on the current
corpus (re-scraped since the 2026-09-15 audit) and gives a paste-ready variant.

Family: **template-mockup** (a named `variant`, like `dark-composite`'s
`two-up`). Preset id: `editor`.

---

## (1) EVIDENCE

### Two different "editor" things — this preset is the template-mockup one
The corpus also has a distinct **`editor-canvas` style family** (117 assets with
`ui_mockup=editor-canvas`; link-grid tool-page thumbnails of the real Picsart
editor). That family is **kept-from-source and never generated** (style-families.md
line 345: "Template: kept-from-source"; "Panels (worker): none produced"). It is
**not** a compose target and is out of scope. This preset is the **template-mockup
family's** own editor-styled callout: a *designed template* exploded into its
parts, which the worker *does* generate. Keep them separate.

### The Layout-B population (viewed, every asset)
`template-mockup` now carries **422** tags in `corpus/styles.yaml` (was 204 at the
audit). I enumerated every `template-mockup` asset at the `S05-m1/S06-m1/S06-m2`
slots (38 pages) plus everything tagged with `swatch`/`selection-handles`/`cursor`
chrome (39), built contact sheets, and viewed them. Clean Layout-B (checkerboard
cutout panel **+** "Aa Aa" type tile **+** design card **+** bottom swatch bar):

| # | page | slot | uuid8 | selection frame? | bottom bar | checker tone |
|---|------|------|-------|------------------|-----------|--------------|
| 1 | calendar-maker | S06-m1 | `219070b9` | yes (white, 8 handles) | 4-colour swatch | dark |
| 2 | christmas-card-maker | S06-m1 | `c491d842` | yes (black, 8 handles) | 4-colour swatch | light |
| 3 | coupon-maker | S06-m1 | `a591037a` | yes (black, 8 handles) | 3-colour swatch | light |
| 4 | birthday-card-maker | S06-m1 | `d4507d92` | yes | multi-colour swatch | light |
| 5 | facebook-post-maker | S06-m1 | `6aac8086` | yes | 4-colour swatch | light |
| 6 | quote-poster-maker | S06-m1 | `cf38e144` | yes | 2-colour swatch | light |
| 7 | menu-maker | S06-m1 | `fc4bbe40` | yes (tagged `selection-handles`) | 4-colour swatch | dark |
| 8 | gift-certificate-maker | S06-m1 | `0a059f15` | no | wide info-card | dark |

Two **reduced /black relatives** (Aa type tile + swatch bar + card on a black
ground, **no** cutout panel): `e47b7b3d` (ai-replace S10-m10 / design S04-m6, var
`black`). Useful as evidence for a `/black` fill override, not as full Layout-B.

**Modal facts (out of the 8):**
- **Ground: transparent 8/8** (alpha min 0, fully-transparent gutters between
  every element; the page section supplies white/black — same as the family
  default). Measured from the alpha channel, not a flattened RGB read.
- **Slot: `S06-m1` 8/8, aspect 1:1 (1600²) 8/8.** This preset is a *callout-1:1 /
  gallery-1:1* tile, one per template/card/poster/menu *maker* page.
- **Left column = cutout panel (top) + type tile (bottom): 8/8.**
- **Checkerboard cutout panel: 8/8**, holding one cut-out design element on
  transparency (a star, tree, smiley, apple, chrome blob…). Checker tone dark
  3/8, light 5/8.
- **Selection frame with 8 round handles: 7/8** (4 corners + 4 edge midpoints;
  white on a dark checker, near-black on a light checker). This is the one
  recurring editor-furniture chrome the audit flagged as worth drawing.
- **"Aa Aa" type-specimen tile: 8/8** — a black rounded tile with two "Aa", a
  serif/script one and a bold sans one (the template's type pairing).
- **Design card, flat, 1 card: 7/8** (coupon has 2 overlapping tickets). The card
  **is** the finished design (headline typography included) — never blank bars.
- **Full-width bottom bar: 8/8** — a colour-swatch bar (7/8) or a wide info-card
  (1/8, gift-cert). Swatch bars have **3–4 unequal stripes** drawn from the card
  palette, not equal thirds.

Not Layout-B (for the record, so the counts are honest): the *modal*
template-mockup arrangement is still **Layout A** — a left column of icon/swatch
*tiles* beside one card, with **no** checkerboard cutout panel and **no** bottom
swatch bar (e.g. motivation-poster-maker S07 `c3461329`, instagram-post-creator
S09 `861c2971`, flyer-maker S08 `9923ffa5`, invitation-maker S06). Layout-B is a
distinct minority arrangement clustered on the *card/poster/menu maker* pages.

---

## (2) MEASURED GEOMETRY

Alpha bounding boxes at native 1600² (`np` on the RGBA alpha channel):

```
region        calendar(219070b9)   christmas(c491d842)  coupon(a591037a)
cutout-panel  (260,264,691,857)    (282,314,673,853)    (282,504,673,863)
type-tile     (260,888,693,1079)   (281,882,675,1055)   (274,894,667,1067)
card          (722,265,1341,1076)  (703,314,1335,1054)  (708,504,1323,1061)
swatch-bar    (260,1109,1341,1335) (264,1086,1333,1291) (264,1092,1333,1297)
```

Consistent structure (the whole composition floats vertically — coupon sits ~240
px lower — but margins, the column split and the element proportions are stable):
- Outer margin ≈ **260** left/right (symmetric). Vertical gutter between left
  column and card ≈ **28–34 px** (x≈690→720). Inter-element gutter ≈ **28–32 px**.
- Left column width ≈ **424**; card width ≈ **616**.
- Card top aligns with the cutout-panel top; card bottom aligns with the
  type-tile bottom; the swatch bar spans **both** columns' full width below.

**Selection frame** (measured on `219070b9`, white pixels inside the panel):
spans x[0.04, 0.95] and y[0.05, 0.65] of the panel — i.e. ~full width, top ~65 %
of the height (the subject region), abs `(279,292,669,649)` in panel
`(264,264,691,857)`.

**Swatch-bar stripes** (mid-row colour runs): unequal widths, palette colours.
`219070b9` ≈ [black 52 %, blue, yellow, orange]; `a591037a` ≈ [navy 40 %, pink 40 %,
green 20 %]. Count 3–4, worker/palette-driven.

**Canonical rects, REF=1600** (top-aligned, margins/gutters cleaned):
```
cutout-panel : (264, 264, 688,  856)   # 424 x 592
type-tile    : (264, 888, 688, 1072)   # 424 x 184
card         : (720, 264, 1336, 1072)  # 616 x 808
swatch-bar   : (264,1100, 1336, 1336)  # 1072 x 236 (full width)
selection-frame (in cutout panel): (280, 294, 668, 649)  ≈ inset 4% x / 5% top, 65% down
radius: 40 (family default)
```

---

## (3) PROPOSED SPEC

### `families.py` — add under `template-mockup`'s `variants`
Paste-ready (the variant inherits `aspect`, `ground`, `radius` from the family):

```python
# /editor exploded view (Layout B, 8 corpus assets: 219070b9 calendar-maker S06,
# c491d842 christmas-card-maker S06, a591037a coupon-maker S06, d4507d92
# birthday-card-maker S06, 6aac8086 facebook-post-maker S06, cf38e144
# quote-poster-maker S06, fc4bbe40 menu-maker S06, 0a059f15 gift-certificate S06).
# The design is the `photo`/card; the pulled-out element is the `cutout` panel on
# a checkerboard; a selection frame marks it; an Aa type tile + a bottom swatch
# bar complete the editor canvas. Ground stays transparent (8/8).
"editor": {
    "panels": {
        "photo":  {"rect": (720, 264, 1336, 1072)},           # the finished design card
        "cutout": {"rect": (264, 264, 688, 856),              # one design element, on checker
                   "under": "checkerboard", "fit": "contain"},
    },
    "chrome": [
        {"id": "card", "kind": "card", "rect": (720, 264, 1336, 1072), "fill": (43, 20, 90)},
        {"id": "select", "kind": "selection-frame", "at": "cutout",
         "frac": (0.04, 0.05, 0.95, 0.65), "colour": [255, 255, 255]},  # near-black on light checker
        {"id": "type", "kind": "type-tile", "rect": (264, 888, 688, 1072), "fill": [0, 0, 0]},
        {"id": "swatch", "kind": "swatch-bar", "rect": (264, 1100, 1336, 1336),
         "colours": [[0, 0, 0], [17, 138, 178], [255, 210, 0], [255, 88, 36]]},
    ],
},
```

Notes / decisions the manager makes per slot:
- **`checker_tone`**: dark default; set light on card/greeting pages. Needs
  `draw.checkerboard` (and `draw.panel`) to accept a light cell pair — a 2-line
  extension, or a `CHECKER_LIGHT` constant chosen by a `cutout.checker` key.
- **`/black`**: a fill override (page ground dark, tile fills black) — same as the
  family's existing `/black` story; the reduced `e47b7b3d` proves it.
- The **`cutout` panel is a second worker input** (a transparent PNG of one design
  element). The worker's Flow board already produces a cutout for
  `cutout-checkerboard`; here it feeds the panel. Brief it as "one motif from the
  design, background removed, centred".

### NEW `draw.py` primitives (three)

```python
def selection_frame(canvas, rect, colour, stroke, handle_r):
    """A thin rectangle outline with 8 round drag handles (4 corners + 4 edge
    midpoints): the editor selection mark. white on dark checker, near-black on
    light. Returns rect."""

def type_tile(canvas, rect, radius, fill, fnt_a, fnt_b, colour):
    """A rounded tile with two 'Aa' specimens side by side (a serif/script face
    and a bold sans). Returns rect."""   # needs a serif face bundled; see caveat

def swatch_bar(canvas, rect, colours, radius, widths=None):
    """A single rounded bar split into vertical colour stripes (outer corners
    rounded only); widths are fractions summing to 1, equal if omitted. Returns
    rect."""
```

### NEW `kinds.py` adapters + registry entries
```python
def _selection_frame(canvas, it, ctx):
    if "at" in it:
        x0, y0, x1, y1 = ctx.panels[it["at"]]["rect"]; w, h = x1 - x0, y1 - y0
        fx0, fy0, fx1, fy1 = it["frac"]
        r = (x0 + w * fx0, y0 + h * fy0, x0 + w * fx1, y0 + h * fy1)
    else:
        r = it["rect"]
    return draw.selection_frame(canvas, r, tuple(it.get("colour") or (255, 255, 255)),
                                max(1, round(4 * ctx.s)), round(11 * ctx.s))

def _type_tile(canvas, it, ctx):
    return draw.type_tile(canvas, it["rect"], ctx.r, tuple(it.get("fill") or (0, 0, 0)),
                          ctx.font("type-specimen", 300), ctx.font("type-specimen", 800),
                          tuple(it.get("colour") or (255, 255, 255)))

def _swatch_bar(canvas, it, ctx):
    return draw.swatch_bar(canvas, it["rect"], [tuple(c) for c in it["colours"]],
                           ctx.r, it.get("widths"))

# KINDS += {"selection-frame": Kind(_selection_frame), "type-tile": Kind(_type_tile),
#           "swatch-bar": Kind(_swatch_bar)}
# FONT_PX += {"type-specimen": 150}
```

All three are **reusable beyond this preset**: `selection-frame` is also the
default template-mockup's real headline chrome and the brighten-images editor
look; `swatch-bar` is the same primitive as Layout-A's vertical swatch *tile*
(rotate → could unify as one `swatch` kind with an `orientation`); `type-tile`
recurs across Layout-A columns too. Building them pays off family-wide, which is
the main argument for doing this preset now.

---

## (4) PROTOTYPE RENDER

It needs new primitives, so I prototyped all three **inline** in a throwaway
section-local renderer (the `runs/independent-1/S08` pattern: imports
`compose.draw` read-only, writes only to scratchpad) and rendered the full
canonical layout with solid-colour placeholder panels:

- script: `scratchpad/preset-research/proto_editor.py`
- render: `scratchpad/preset-research/editor_proto.png` (1600², produced by
  `uv run python proto_editor.py`)
- placeholders: `ph_cutout.png` (magenta star on alpha), `ph_card.png` (indigo)

The render reproduces the modal Layout-B and closely matches `219070b9`
(calendar-maker): dark checker cutout panel with the star and a white selection
frame + 8 handles; black "Aa Aa" tile; indigo design card; full-width 4-stripe
swatch bar (black/blue/yellow/orange, unequal). The checkerboard cutout and the
card reuse the **existing** `draw.panel`/`draw.card`; only the frame, type tile
and swatch bar are the new code. Caveat: only `Manrope.ttf` ships, so the type
tile contrasts weights (light vs heavy) rather than a true serif+sans pairing —
a faithful build should bundle a serif face; the two "Aa" also want more gap than
the prototype's 0.30/0.68 spacing.

---

## (5) CONFIDENCE: **medium**

- **For:** the modal layout is unambiguous and stable across **8** viewed assets
  (element positions, margins, the left-column split, the bottom bar), ground is
  cleanly measured transparent 8/8, every chrome element cites a living asset id,
  and the geometry is corroborated by three independently-measured examples. The
  audit independently identified the same layout.
- **Against high:** 8 clean assets, just under the ≥10 bar; Layout-B is a
  *minority* arrangement within template-mockup (the family's modal is still
  Layout A), so it must ship as a named `variant`, never the default. It needs
  **3 new draw primitives + a 2nd worker panel (`cutout`) + a light/dark checker
  tone**, so no zero-new-code prototype is possible; the swatch-bar stripe
  count/widths and the type pairing are worker/palette-driven, not fixed. The
  `selection-handles`/`swatch` tags are inconsistently applied by the labeller
  (only `fc4bbe40` carries `selection-handles`), so tag-count queries undercount
  this population — I relied on viewing, not tags.
- **Recommendation:** build it as `template-mockup` `variant: editor`, and build
  `selection-frame` + `swatch-bar` first since both are reused by the default
  template-mockup and Layout-A; treat `type-tile` (serif face) as a follow-up.
