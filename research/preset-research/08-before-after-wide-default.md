# Preset proposal 08 — before-after: wide-as-default inversion

**Preset:** invert `FAMILIES["before-after"]` so the modal **wide ~2.1:1** card is
the default and the rare **1:1 stacked pair** becomes a named variant. Today
`families.py` has this backwards: the default is the 1:1 stack (measured off one
asset, 69ed3f5c) and the wide card is the `wide` variant.

Read-only research, branch `layered-templates`. Zero credits (no `picsart_*`
calls; `lp-compose` and corpus reads only). Fresh corpus data (post the
2026-09-22 labelling campaign), which extends the 2026-09-15 audit in
`research/template-audit/before-after.md`.

---

## (1) EVIDENCE

**Family:** `before-after` (style-families.md `## before-after`). Population:
**123** assets tagged `style: before-after` in `corpus/styles.yaml` — 112 images
+ 11 video. The compose template exists for the multi-panel **composite card**
(before panel + result panel + an icon `tile` + Before/After pills), not for the
single-panel pair-halves or the interactive wipe-slider stills that also carry
the tag.

### Aspect ratio, measured from the pixels (112 images)

| aspect (measured w/h) | n | with `tile` chrome | VS/model-logo pair | prompt-panel |
|---|---|---|---|---|
| **WIDE ~2.10:1** | 16 | **11** | 4 | 6 |
| SQUARE 1:1 | 52 | 8 | 17 | 1 |
| ~1.6:1 | 7 | 0 | 0 | 0 |
| ~1.33:1 | 37 | 4 | 0 | 0 |

The `tile` (a black rounded square with a white line glyph, below the before
panel) is the compose template's signature chrome. Filtering to genuine
`before + result + tile` composite cards — dropping the `compare-handle`
wipe-sliders (interactive stills, on the family's **Never** list) and the
`model-logo`+`pill` compare-models VS cards (a different pattern, the tagging
noise the audit flagged) — the modal is unambiguous:

- **WIDE ~2.1:1 composite cards with a tile: 11**
- **SQUARE 1:1 composite cards with a tile: 4** (the other 8 square-with-tile are
  `compare-handle` wipe-sliders: 120e92ec, 303e844a, a7d64fef, b572f707)
- **~1.33:1 with a tile: 4** (all `compare-handle` wipe-sliders, not this card)

**Modal = wide, 11 vs 4 (≈73%) among genuine composites; 16 vs 5 (≈76%) by
aspect alone.** This reproduces the 2026-09-15 audit (14/20 wide then) on a
larger, freshly-labelled population.

### The ≥10 corpus asset ids for the modal (WIDE ~2.1:1)

Genuine `before + result + tile` wide cards (11):

| id | page / slot | native px | chrome |
|---|---|---|---|
| `08385997` | ai-image-enhancer S09-m1 | 1060×504 | pill, tile — **canonical** |
| `c5715e9b` | image-upscale S07-m1 | 1060×504 | pill, tile — 3-column sub-form |
| `f223c881` | video-enhancer S10-m1 | 1060×504 | pill, play-button, tile |
| `6e1c292f` | ai-models--flux-3 S09-m1 | 1060×504 | prompt-panel, tile |
| `dad15a71` | ai-models--google-omni S06-m1 | 2120×1008 | pill, prompt-panel, tile |
| `85677966` | ai-models--grok-imagine S06-m1 | 1060×504 | prompt-panel, tile |
| `768fcebb` | ai-models--hailuo-3 S06-m1 | 2120×1008 | model-logo, tile |
| `5acfd40b` | ai-models--imagen-4-0 S05-m1 | 1060×504 | prompt-panel, tile |
| `5bb50e97` | ai-replace S08-m1 | 1060×504 | button, prompt-panel, tile |
| `0af91011` | flip-video S08-m1 | 1060×504 | play-button, tile |
| `2c990e97` | remove-object-from-video S09-m1 | 1060×504 | button, prompt-panel, tile |

(5 further wide-aspect before-after composites carry no tile — 344e094b,
e6fe5f30, bb63a74c, 2b7a985a, 41c41e72 — for 16 wide total.)

The **1:1 stacked** form the current default encodes is real but rare — genuine
square composites (before+result+tile): `69ed3f5c` (image-enlarger S08, the
current default's sole exemplar), `063c75bf` (image-upscale S06), `ad4a1557`
(image-upscale S10), `bcc56313` (photo-effects S10), + `2e9d292c`
(ai-image-enhancer S12, stacked, pill only). The other ~26 "square" tags are 17
compare-models VS cards + 6 wipe-slider stills + 1 misclassified prompt card.

Viewed to confirm layout (converted to PNG on a checkerboard, read as images):
`08385997`, `c5715e9b` (wide), `69ed3f5c` (square). 08385997 is before panel +
enhance tile top-left, big result right, solid-dark pills with **"After" on the
result**. 69ed3f5c is before/after stacked + tile left, result-as-billboard-mockup
right.

---

## (2) MEASURED GEOMETRY

### Ground — measured from the alpha channel (standing rule)

All **15/15** sampled wide RGBA assets have ≈11% fully-transparent pixels and
**all four corners at alpha 0** (transparent gutters and margin). The card is
**transparent artwork; the page section supplies the surround.**

```
08385997  trans=0.11  corners=[0,0,0,0]   stored ground field = "photo-full-bleed"
2c990e97  trans=0.12  corners=[0,0,0,0]   stored ground field = "black"
5acfd40b  trans=0.11  corners=[0,0,0,0]   stored ground field = "black"   ...
```

The `ground` field stored in `attributes.yaml` (black / mixed / photo-full-bleed)
is the RGBA→RGB misread the audit's cross-cutting failure #2 warns about — the
alpha proves transparent. **`ground: {"fill": None}`** (already correct in both
the current default and the `wide` variant; the inversion does not touch it).

### Panel rects at REF=1600 (from 08385997 alpha, native 1060×504 scaled ×1.5094)

aspect `(21, 10)` → the card is **1600×762** at REF (h = 1600·504/1060 = 761).

| element | measured @REF | proposed rect | native px |
|---|---|---|---|
| outer margin | 24 | — | 16 |
| `before` panel | (24, 24, 607, 518) | **(24, 24, 610, 519)** | 388×328 TL |
| `result` panel | (620, 24, 1574, 735) | **(622, 24, 1576, 737)** | 632×472 R |
| `tile` (under before) | (24, 531, 607, 735) | **(24, 531, 610, 737)** | 388×136 |
| gutter | ≈12–13 | — | 8 |

Cross-checked on `c5715e9b` and `f223c881`: identical 24px margin and left
column, same before-left / tile-below / result-right schema (c5715e9b splits the
right side into after + framed-poster = a 3-column sub-form; f223c881 makes the
before wider). The proposed rects are the current `wide` variant's values
verbatim, now confirmed within **3px** of the alpha measurement — **no
re-measurement, no new geometry invented.**

### Chrome (each cites a living asset)

- `before-pill` — `pill` at `before` bl, "Before", **solid-dark** (08385997,
  c5715e9b, dad15a71: black pill on the wide cards, not translucent).
- `after-pill` — `pill` at **`result`** bl, "After", solid-dark. The After label
  sits on the large result panel, not on a separate after panel (08385997,
  bcc56313, f223c881).
- `tile` — `tile` at (24, 531, 610, 737), `icon: "enlarge"`. Glyph note:
  upscale/enlarge cards (c5715e9b, 063c75bf, ad4a1557, 69ed3f5c) use the enlarge
  (expand-arrows) glyph — a fair family default; the enhancer card 08385997 uses
  an image+sparkle "enhance" mark (closest existing ICON is `"sparkle"`), a
  per-spec override, not a new primitive.

---

## (3) PROPOSED SPEC

Paste-ready replacement for `FAMILIES["before-after"]` in
`src/landing_page_gen/compose/families.py`. It **swaps default ↔ variant**: the
wide card's geometry (already present and shipping as `variant: wide`) becomes
the top-level default; the current default becomes `variant: stacked-square`.
Both keep the transparent ground.

```python
    "before-after": {
        # Ground is transparent on every corpus composite (alpha-0 gutters and
        # margin, measured 15/15; the page section supplies the surround). The
        # MODAL card is the WIDE ~2.1:1 layout — 11 of 15 genuine before+result+
        # tile composites, 16 of 21 by aspect (e.g. 08385997 ai-image-enhancer
        # S09, c5715e9b image-upscale S07, f223c881 video-enhancer S10). Native
        # 1060x504 scaled x1.5094 to REF width: margin 16->24, gutter 8->12.
        # before + icon tile left, result right, solid-dark pills, "After" on the
        # RESULT. The rare 1:1 stacked pair (1/21 for this exact geometry;
        # 69ed3f5c image-enlarger S08) is `variant: stacked-square`.
        "aspect": (21, 10),                         # 1060x504 = 2.103:1
        "ground": {"fill": None},                   # transparent — all composites
        "radius": 40,
        "panels": {
            "before": {"rect": (24, 24, 610, 519)},   # 388x328 native
            "result": {"rect": (622, 24, 1576, 737)}, # 632x472 native
        },
        "chrome": [
            {"id": "before-pill", "kind": "pill", "at": "before", "corner": "bl", "text": "Before", "style": "solid-dark"},
            {"id": "after-pill", "kind": "pill", "at": "result", "corner": "bl", "text": "After", "style": "solid-dark"},
            {"id": "tile", "kind": "tile", "rect": (24, 531, 610, 737), "icon": "enlarge"},
        ],
        "variants": {
            # the 1:1 stacked pair, measured from 69ed3f5c (image-enlarger S08):
            # before + after stacked left with a tile below, result (often an
            # applied mockup of the after image) right. The former default; for
            # callout-1:1 slots. Translucent pills (69ed3f5c, bcc56313).
            "stacked-square": {
                "aspect": (1, 1),
                "panels": {
                    "before": {"rect": (0, 0, 604, 632)},
                    "after": {"rect": (0, 664, 604, 1296)},
                    "result": {"rect": (636, 0, 1600, 1600)},
                },
                "chrome": [
                    {"id": "before-pill", "kind": "pill", "at": "before", "corner": "bl", "text": "Before", "style": "translucent"},
                    {"id": "after-pill", "kind": "pill", "at": "after", "corner": "bl", "text": "After", "style": "translucent"},
                    {"id": "tile", "kind": "tile", "rect": (0, 1328, 604, 1600), "icon": "enlarge"},
                ],
            },
        },
    },
```

**New draw.py primitive needed: NONE.** **New kinds.py Kind adapter needed:
NONE.** The layout reuses `pill` (`draw.pill_at`), `tile` (`draw.tile`) and
`panel` (`draw.panel`) exactly as the shipping `wide` variant already does. The
inversion is a pure restructure of the dict.

### Downstream ripple (outside the FAMILIES entry — flag, do not silently break)

Changing the default aspect from 1:1 to 21:10 touches four call sites:

1. `tests/golden_compose.py` — the `before-after+omit` case uses `variant: None`
   + `_size(1, 1)`; after the inversion the default is 21:10, so `load_spec`'s
   aspect check rejects a 1:1 size. Change it to `_size(21, 10)` and regenerate
   that golden sha (and the auto-enumerated default-aspect case).
2. `tests/test_compose.py` — `write_spec(... size="720x720")` defaults to 1:1 for
   before-after; change to a 21:10 size (e.g. `"1600x762"`) or pass
   `variant="stacked-square"` in the affected tests.
3. `.claude/skills/picsart-workflows/style-families.md` — the **Ground** line
   (172) already says the modal is wide, but **Template** still reads
   "lp-compose: before-after (1:1)" and **Slots**/the slot-class table (line 119)
   list before-after under callout-1:1. Update: default = wide/callout-2:1, the
   1:1 stack is `variant: stacked-square` for callout-1:1; lead **Grid** with the
   wide card.
4. No change to `plan.py` / `layout.py` / `cli.py` — `--describe` and
   `--keepclear` read the family dict directly and pick up the new default and
   variant name automatically.

Naming: keeping the wide layout keyed by no name (it is the default) and renaming
the old default to `stacked-square` means any existing spec that said
`variant: wide` must drop the line; grep found none in `runs/`.

---

## (4) PROTOTYPE RENDER

Reuses existing primitives, so it renders **today** with the shipping code via
`variant: wide` (identical geometry to the proposed default). Throwaway spec +
solid-colour placeholder panels in this folder:

- spec: `proto_wide.yaml`
- panels: `p_before.png` (776×656, blue), `p_result.png` (1264×944, rose)
- render: **`proto_wide.png`** (1060×504, transparent ground)
- viewable (composited on checkerboard): **`proto_wide_checker.png`**

Command:
```
uv run lp-compose proto_wide.yaml --out proto_wide.png
```

The render is a byte-faithful reproduction of 08385997's structure: transparent
ground (checkerboard shows through the corners and both gutters), Before panel +
black enlarge tile in the left column, result panel on the right, solid-dark
"Before" pill on the before panel and "After" pill on the **result**. It matches
the viewed corpus asset.

---

## (5) CONFIDENCE

**HIGH.**

- ≥10 assets: 16 wide-aspect before-after composites, 11 carrying the exact
  before+result+tile schema; clear modal (11 vs 4 among genuine composites, 16
  vs 5 by aspect), reproducing the 2026-09-15 audit on a larger population.
- Ground measured from alpha (15/15 transparent, all corners alpha 0), not from
  the mis-stored RGB `ground` field.
- Geometry is not newly invented — it is the current `wide` variant's rects,
  cross-checked within 3px against the alpha of 08385997 / c5715e9b / f223c881,
  and it renders correctly with existing primitives (prototype above).
- No new draw/kind primitive; the only risk is the flagged test/doc ripple, which
  is mechanical.

Minor open point (does not lower confidence): the tile glyph — `enlarge` fits the
upscale/enlarge cluster; enhancer pages want a sparkle-ish "enhance" mark, handled
by a per-spec `icon` override, no new ICON entry required.
