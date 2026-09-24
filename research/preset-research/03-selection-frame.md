# Preset 03 — `selection-frame` chrome primitive

A dashed/solid selection box with handles: the Picsart editor's transform box.
Editor furniture for the **template-mockup** and **cutout-checkerboard**
families (and the wider `editor-canvas` look). New `draw.py` primitive +
`kinds.py` adapter; distinct from a plain `card`/`headline` outline and from the
model-rendered `face-box` (which is reserved in `kinds.MODEL_KINDS` precisely
because "a plain box is selection-frame").

Scope note: the primitive itself is HIGH confidence (63 living assets carry the
chrome, 8 viewed at pixels, geometry measured at REF=1600). Where it plugs into
each *family* (exact rect inside a generated card) is context-dependent and is
called out as opt-in / composition-plan-driven, not a baked default, to honour
"do not invent geometry."

---

## (1) EVIDENCE

**Family/pattern served:** the `selection-handles` chrome kind
(`attrs.CHROME_KINDS`) and the `ui_mockup: editor-canvas` look
("an image on a canvas with handles, grid or cursor"). It recurs across the two
target composite families plus the editor-canvas link-grid/callout look.

**Population (labelled `corpus/attributes.yaml`, read-only):**
- `chrome` bag contains `selection-handles`: **63 assets**.
- `ui_mockup == editor-canvas`: **117 assets** (52 of which also carry
  `selection-handles`).
- Family breakdown of the 63 selection-handles assets: `editor-canvas` 38,
  **template-mockup 9**, `crop-frame` 5, **cutout-checkerboard 4**,
  panel-overlay 1, mockup-card 2, before-after 1, graphic-collage 1, other 2.

**>=10 corpus asset ids (uuid8), living and currently tagged:**

Template-mockup (9):
`972da313` card-maker S01-m1 ("lemon quote card on an editor canvas with colour
swatches and selection handles", conf 0.5) · `87194d0d` timeline-maker S07-m1
("document taped to a grid with selection handles", 0.4) · `168e63a1`
menu-maker S06-m1 ("apple cutout with handles beside a menu card", 0.8) ·
`87d58fb8` book-cover-maker S10-m3 (0.8) · `5176f435` collage-maker S05-m1 ·
`6dd441a0` ai-content-generator S05-m3 · `a0e1874c` timeline-maker S09-m3 ·
`d71c0f5c` brochure-maker S06-m1 · `33f184e2` text-editor S01-m1.

Cutout-checkerboard (4):
`361c2368` ai-image-extender S05-m1 ("pasta … on a checkerboard ground with a
dashed selection outline", chrome_item `selection-handles/overlay`) · `16410f3b`
whatsapp-sticker-maker S05-m1 ("die-cut sticker … edit handles") · `bc439e86`
ai-sticker-maker S05-m1 · `2e7d83cc` background-tools S10-m1.

editor-canvas transform-box exemplars (used to fix geometry):
`17a18112` meme-generator S10-m9 ("fried egg cutout on checkerboard with a
transform selection frame", item `selection-handles/overlay`) · `45692262`
video-ad-maker S11-m1 (conf 0.85, "selection box and Animate button") ·
`1fa729f4` background-tools S13-m1 ("flower cutout with selection handles") ·
`a83409b2` image-tools S04-m3 ("rule of thirds grid and handles") · `539d5c3b`
batch-photo-editor S11-m1 ("crop grid with corner selection handles") ·
`2554308c` photo-editor S17-m1 · `f08ac76c` ai-logo-generator S11-m1 ·
`38ef3b78` add-shadow-to-image S11-m3 · `ab6af56e` content-creation-tools S02-m5
("selection handles and 1080 size labels") · `947668c7` photo-editor S11-m1.

**Modal layout (8 assets viewed at native pixels):**
`972da313`, `17a18112`, `45692262`, `361c2368`, `1fa729f4`, `a83409b2` viewed in
full; `16410f3b`, `2554308c` cross-checked. The recurring form:

- **Thin, square-cornered rectangle** over the subject. Corners are sharp 90°
  (this is what separates it from `card`/`headline`, which are rounded). 6/6
  clearly-viewed.
- **Filled disc handles at the four edge midpoints** (N/S/E/W): 5/6 (the
  rule-of-thirds crop case `a83409b2` uses short rounded *bar* handles instead).
- **Colour is contrast-driven:** white over dark/photographic grounds
  (`17a18112`, `45692262`), dark/near-black over light grounds (`972da313`,
  `1fa729f4`). 3 white / 3 dark among viewed.
- **Corner tool discs outside the frame** (X top-left, rotate top-right,
  resize/diagonal bottom-right), each an icon in a filled disc of the *opposite*
  tone: 2/6 viewed (`17a18112`, `1fa729f4`). Optional.
- **Interior 3×3 rule-of-thirds grid:** 1/6 (`a83409b2`; also `539d5c3b`,
  `bbd49100`). Optional (overlaps `crop-grid`).
- **Dashed border:** 1/6 (`361c2368`, the "extend" guide with up/down arrows).
  Solid is modal (5/6).
- The frame **wraps a single element** — a cutout on a checkerboard panel, or
  one card graphic — not the whole card (panel_count is 1 in 44/63).

---

## (2) MEASURED GEOMETRY (REF = 1600)

Measured off `972da313` (card-maker), which is a native 1600×1600 asset (== REF),
dark frame on a light card:

- **Frame rect** (around one card graphic): x 963–1354, y 246–637 →
  **391 × 391 px**, i.e. a square ~24% of REF on a side, placed over the card's
  focal element (here the upper-right).
- **Border stroke:** ~**6 px** (measured left border run at y=300).
- **Edge-midpoint disc handles:** diameter **~40 px** (measured 37–42 across
  top-mid and left-mid), i.e. radius ~20 px, ~10% of the frame side.
- **Corner tool discs** (from `17a18112`/`1fa729f4`, proportion): ~**4×** the
  handle radius in diameter (~80–90 px at REF), centred ~0.75·(their diameter)
  outside the corner. Glyph inset ~0.28 of the disc.

Ground: the primitive is chrome drawn **over** a panel, so it has no ground of
its own; it inherits the family's ground (template-mockup transparent,
cutout-checkerboard transparent + a checkerboard panel). No alpha ground
measurement applies to the frame itself.

---

## (3) PROPOSED SPEC

### New primitive — `draw.py`

```python
def selection_frame(canvas, rect, colour=WHITE, stroke=6, handle=20, dashed=False,
                    grid=False, handles=("top", "bottom", "left", "right"), tools=()):
    """The editor transform/selection box: a thin, square-cornered rectangle over
    a subject with filled disc handles at the named positions (edge midpoints
    top/bottom/left/right and/or corners tl/tr/bl/br), an optional 3x3
    rule-of-thirds grid inside, and optional round tool discs (an icon in a disc
    of the opposite tone) floating just outside named corners. Solid by default;
    `dashed` gives the extend/crop guide. `colour` is white over dark or
    photographic grounds, dark over light ones. Editor furniture: it marks a
    selection and carries no text."""
```

Behaviour: alpha-composited layer; draw the four sides with `ImageDraw.line`
(dashed = split each side into segments when `dashed`); optional two vertical +
two horizontal interior lines at 1/3, 2/3 (`grid`, width ~0.6·stroke); a filled
`ellipse` of `colour` (radius `handle`) at each named position; for each
`tools` entry `(corner, icon)` a filled disc (diameter `4·handle`) of `colour`
with the icon in the opposite tone centred, offset outside the corner. Verified
by the prototype below — the code is in `proto_selection_frame.py`.

**Two new `draw.ICONS` entries** the tool discs need (24-unit grid; `resize`
reuses the existing `enlarge` glyph, so only two are new):

```python
"close":  {"lines": [[(7, 7), (17, 17)], [(17, 7), (7, 17)]]},
"rotate": {"arc": (5, 5, 19, 19, 40, 320), "lines": [[(19, 7), (19, 12), (14, 12)]]},
```

`draw.icon` needs a tiny `"arc"` clause (`d.arc(bbox, start, end, ...)`) to draw
the rotate glyph; everything else uses the existing lines/polygon machinery.
(If tool discs are dropped as out-of-scope, no new icons are needed at all — the
box + disc handles reuse only `ImageDraw.line`/`ellipse`.)

### New adapter — `kinds.py`

```python
def _selection_frame(canvas, it, ctx):
    if "at" in it:
        x0, y0, x1, y1 = ctx.panels[it["at"]]["rect"]
        fx0, fy0, fx1, fy1 = it.get("frac", (0.0, 0.0, 1.0, 1.0))
        w, h = x1 - x0, y1 - y0
        rect = (x0 + w * fx0, y0 + h * fy0, x0 + w * fx1, y0 + h * fy1)
    else:
        rect = it["rect"]
    colour = tuple(it.get("colour") or (255, 255, 255))
    if len(colour) == 3:
        colour += (255,)
    return draw.selection_frame(canvas, rect, colour,
        stroke=max(1, round(6 * ctx.s)), handle=round(20 * ctx.s),
        dashed=it.get("dashed", False), grid=it.get("grid", False),
        handles=tuple(it.get("handles", ("top", "bottom", "left", "right"))),
        tools=tuple(tuple(t) for t in it.get("tools", ())))

# register (drawn above the panels/chrome, like an overlay):
KINDS["selection-frame"] = Kind(_selection_frame, layer="overlay")
```

`at`+`frac` mirror the existing `_brackets` anchoring so the frame is grounded
to a resolved panel rect; `rect` is the explicit fallback. `text=False` (it
carries no string — consistent with prd's "a model item never carries a string"
and the fact that this is a drawn, not model, kind).

### Family placements (paste-ready chrome items)

**cutout-checkerboard** — strongest fit; add an opt-in item anchored to a
cutout panel (evidence `17a18112`, `361c2368`, `16410f3b`, `1fa729f4`):

```python
# in FAMILIES["cutout-checkerboard"]["chrome"], opt-in via the composition plan
{"id": "select", "kind": "selection-frame", "at": "cutout-a",
 "frac": (0.16, 0.16, 0.84, 0.84), "colour": [255, 255, 255],
 "tools": [["tl", "close"], ["tr", "rotate"], ["br", "enlarge"]]},
```

**template-mockup** — matches the audit's proposed `select` item, but as a
**square over a card graphic** (measured 391² on `972da313`), not a wide blank
headline bar. Because the focal element's position varies per generated card,
place it through the composition plan rather than baking a rect:

```python
# opt-in; rect set per slot by composition-<slot>.yaml over the card's focal graphic
{"id": "select", "kind": "selection-frame", "rect": (980, 250, 1370, 640),
 "colour": [255, 255, 255], "handles": ["top", "bottom", "left", "right"]},
```

`grid: true` turns either into the rule-of-thirds crop variant (`a83409b2`);
`dashed: true` gives the extend guide (`361c2368`).

---

## (4) PROTOTYPE RENDER

`proto-selection-frame.png` (3260×1600), rendered by
`proto_selection_frame.py` — a throwaway script that imports the shared
`landing_page_gen.compose.draw` (read-only, like runs/independent-1 S02/S08) and
implements the *proposed* `selection_frame` inline over solid-colour placeholder
panels, so the PNG is faithful to the code being proposed. Nothing in `src/` was
touched; `uv run python proto_selection_frame.py --out proto.png`.

- **Left (cutout-checkerboard):** `draw.checkerboard` panel + a solid-blue
  placeholder cutout + white frame, edge-midpoint disc handles, and corner tool
  discs (X / rotate / resize). Reproduces `17a18112` and `1fa729f4`.
- **Right (template-mockup):** `draw.card` (dark purple, the family default
  fill) + a solid-yellow placeholder graphic + white frame with the 3×3
  rule-of-thirds grid and midpoint discs. Reproduces `972da313` / `a83409b2`.

Both read as the Picsart transform box on first glance. Path:
`<2026-09-22 session scratchpad, not kept>/proto-selection-frame.png`

(The prototype is a standalone script, not `lp-compose`, because the kind does
not yet exist in `KINDS`; it exercises the exact draw algorithm proposed for
`draw.selection_frame`.)

---

## (5) CONFIDENCE

**HIGH** for the primitive. 63 living corpus assets carry `selection-handles`
and 117 carry `editor-canvas`; 8 viewed at pixels agree on the modal form; frame
stroke, handle diameter and frame size are measured at REF=1600 on a native-1600
asset; the kind is already reserved in `kinds.MODEL_KINDS`'s wording and named in
the template-mockup deferral list; the prototype renders convincingly from the
proposed code.

**MEDIUM** for the exact in-family rect. The frame wraps a per-generation focal
element whose position varies, so both family placements are proposed as opt-in
/ composition-plan-driven items (with grounded default geometry) rather than
baked defaults — consistent with prd's 2026-09-22 composition-plan model and the
"do not invent geometry" rule.

New primitive needed: **yes** — `draw.selection_frame` + a `kinds.selection-frame`
adapter, plus two small `draw.ICONS` entries (`close`, `rotate`) and an `arc`
clause in `draw.icon`, only if the optional corner tool discs are kept.
