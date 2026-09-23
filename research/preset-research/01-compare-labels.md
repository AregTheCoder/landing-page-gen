# Preset proposal: dark-composite `compare-labels`

Read-only corpus research, branch `layered-templates`, 2026-09-22. No paid
calls, no `picsart_*`, no generation. Assets were read from the corpus's own
local copies (`corpus/pages/**/media`, `corpus/frames`), converted to PNG in
this scratchpad and viewed. Geometry was measured off the pixels.

A **comparison / benchmark card**: a dark card whose ground is a subtle
**dot grid**, carrying two (or more) result panels each named by a **bare
text label on the ground** (model name / "Before"–"After" / metric caption),
with **no** pill box, VS badge or model logo. It is the layout the audit
(`research/template-audit/dark-composite.md` §(d)) already flagged deferred as
the `compare-labels` variant.

---

## (1) EVIDENCE

**Family:** a new **variant of `dark-composite`** (ground black, radius 40,
1:1). Not a new family — it is the compare form of the same editor-composite
card, and the audit specs it as a dark-composite variant.

### The population is tiered — the exact form is rare, adjacent forms are common

I viewed every asset below. Ids are the first 8 hex of the CDN UUID (the
audit's convention).

**Tier 1 — exact `compare-labels` (dot-grid ground + staggered cards + bare
text labels):**

| id | page / slot | layout | note |
|----|-------------|--------|------|
| `bd3c5739` | compare-models--flux-2-pro-vs-midjourney S07-m1 | 2 cards, staggered | textbook; 1600² |
| `4fed106c` | compare-models--nano-banana-2-vs-flux-2-pro S04-m1 | 2 cards, staggered | textbook; each card carries a 4-thumb variant strip; 1600² |

**Tier 2 — dot-grid + staggered cards, chrome elsewhere (same skeleton):**

| id | page / slot | note |
|----|-------------|------|
| `c1b34851` | ai-models--recraft-v4-styles S06-m1 | dot grid + 2 staggered cards in thin grey device frames joined by a connector, **bottom** mark-tile + "Generate" pill instead of top labels; 1600² |

**Tier 3 — comparison of two labelled results on dark, different chrome
(support the INTENT; belong to `vs-two-up`, not this template):** each names
its result, but as a **pill / logo / VS badge**, and the two panels are
**equal, side-by-side** (not staggered):

| id | page / slot | chrome |
|----|-------------|--------|
| `288da9d2` | compare-models--dall-e-3-vs-midjourney S10-m8 | VS badge + 2 model pills w/ logos |
| `2adc1808` | compare-models--imagen-4-0-ultra-vs-gpt-image-1-5 S12-m5 | VS badge + model pills |
| `6adeac96` | compare-models--luma-ray-2-vs-kling-3-0 S12-m6 | VS badge + model pills |
| `287d248c` | compare-models--recraft-v4-vs-midjourney S10-m8 | model logo + crop chips |
| `f3e723e4` | compare-models--seedance-2-vs-kling-3-0 S01-m1 | VS badge + model name chips |
| seedream S12-m1 (`Head-ba9638ef`) | ai-models--seedream-4-5 | 2 equal cards + model pills w/ logos, plain black |

**Tier 4 — column of labelled result thumbs on dark (bare text labels, one
magenta-active):** `b92f843a` persona S07-m1 (Fox Club / Kitten / Bunny /
Hedgehog\* / Duckling) — proves the "bare text names each result" idiom, in a
column layout rather than the compare pair.

Total assets tied to "labelled comparison on dark": **13** (`bd3c5739`,
`4fed106c`, `c1b34851`, `288da9d2`, `2adc1808`, `6adeac96`, `287d248c`,
`f3e723e4`, `d5292893`, `92c4d671`, `8500247f`, seedream S12-m1, `b92f843a`).

### Modal layout, with counts

Across the 9 dark two-result comparison cards viewed
(bd3c5739, 4fed106c, c1b34851, 288da9d2, 2adc1808, 6adeac96, 287d248c,
f3e723e4, seedream):

- **9/9** name each result (comparison cards always label the model).
- **3/9** render the name as **bare text on the ground** (bd3c5739, 4fed106c
  above the card; c1b34851 has no top label but is the bare-chrome cousin) —
  the rest use pills+logos or chips (→ `vs-two-up`).
- **3/9** use **staggered** cards on a **dot grid** (bd3c5739, 4fed106c,
  c1b34851); **6/9** use equal side-by-side cards on plain black.
- Within Tier 1 (the exact form), the modal is unanimous (**2/2**): black
  dot-grid ground; two **~3:4 portrait** cards; **left card high, right card
  low**; a **bare white label left-aligned to each card's left edge, ~35 px
  above its top**; **no** tile/chip/pill/VS/logo.

**Honest caveat (per STANDARD "if evidence is thin, say so"):** the exact
dot-grid + bare-label form has only **2 clean exemplars + 1 cousin**, not ≥10.
The ≥10 that share the *intent* mostly belong to `vs-two-up` (boxed pills, VS
badge, equal panels) — a different template. So this is proposed as a faithful
**variant** of a clearly-observed-but-uncommon layout, not a high-volume modal.
A dot-grid detector run over every black/mixed-ground corpus image
(`dotscan.py`) could not cleanly separate the dot-grid population — the texture
is too faint to threshold reliably at scale — which is itself evidence the
form is niche.

---

## (2) MEASURED GEOMETRY (REF = 1600, from the pixels)

**Ground — measured, not assumed.** Base is **pure black** `(0,0,0)` (RGB
read at empty cells = `(0,0,0)`; the corpus card is opaque black, not a
transparent gutter). Over it a **regular grid of faint grey dots**:

| asset | dot pitch | dot colour | ground |
|-------|-----------|-----------|--------|
| bd3c5739 | **44 px** (measured: dots at y = 3, 47, 92, 136, 180, 224 …) | `(128,128,128)` mid-grey | `(0,0,0)` |
| 4fed106c | ~44–48 px | very faint (~`(42,42,44)`, audit `#2a2a2c`) | `(0,0,0)` |
| c1b34851 | ~44 px | faint on `(14,14,14)` near-black | near-black |

→ **pitch ≈ 44–48 px, small round dots r ≈ 2–3 px, grey; brightness varies
per asset** (faint `#2a2a2c` to visible `#808080`), so it is a parameter.

**Panels** (saturation-mask bbox per half; both Tier-1 assets are exactly
1600²):

| | left card (`photo`) | right card (`photo-b`) | card size | aspect |
|--|--|--|--|--|
| bd3c5739 | (155, 252, 749, 990) | (878, 685, 1471, 1435) | ~594 × 738–750 | ~0.79 |
| 4fed106c | (129, 298, 742, 1120) | (854, 574, 1470, 1395) | ~614 × 821 | **0.75 (3:4)** |
| c1b34851 | (131, 132, 712, 910) | (887, 338, 1468, 1118) | ~581 × 779 | **0.75 (3:4)** |

- card **width ≈ 600**, **aspect ≈ 3:4** (bd3c5739 left reads 0.79 only
  because dark hair at the card bottom fell below the mask; the other 5 cards
  are 0.745–0.75).
- **outer margins** left ≈ 130–155, right ≈ 130; **h-gutter between cards**
  ≈ 112–175.
- **stagger** (right-top − left-top): 433 / 276 / 206 px across the three →
  right card sits **~300 px lower** than the left. Left high, right low in
  3/3.

**Labels** (near-white text mask, above each card, per half):

| | left label | right label |
|--|--|--|
| bd3c5739 | bbox (160,174,418,217), capH 43 | (878,602,1180,657), capH 55 |
| 4fed106c | (133,216,511,254), capH 38 | (858,498,1086,536), capH 38 |

- **left-aligned to the card's left edge** (Δx = 0–5 px in 4/4).
- **cap height ≈ 38–55 px** → font ≈ **60–70 px** at REF.
- **gap label-bottom → card-top ≈ 28–44 px** (~35 px).
- bare **white** text, weight ~700; **no box**.

---

## (3) PROPOSED SPEC

### 3a. The `text` chrome kind ALREADY EXISTS — no new text primitive needed

`kinds.py` already registers `"text": Kind(_text, text=True)`, and its adapter
comment literally reads *"a label bound to no chrome box, e.g. a prompt
sentence or a **compare-label**"*. It draws via `draw.box_text(..., fill=
(0,0,0,0), ...)` — text on a transparent fill, i.e. text on the card ground.
The task's assumed "new text-on-ground primitive" is **already present**. Only
two tiny extensions are wanted for faithfulness (both backward-compatible):

1. **`FONT_PX["compare-label"] = 64`** in `kinds.py` (measured capH 38–55 →
   ~64 px font). Without it the label falls back to `panel-label` (34 px),
   too small.
2. **left-alignment** — the corpus labels hug the card's left edge; `box_text`
   only centres. Add an `align="center"` param (default preserves every
   golden render):

```python
# draw.py — box_text: add `align="center"`, and in the `if text:` block
        if align == "left":
            d.text((x0, (y0 + y1) / 2), text, font=fnt, fill=colour, anchor="lm")
        else:
            d.text(((x0 + x1) / 2, (y0 + y1) / 2), text, font=fnt, fill=colour, anchor="mm")
```
```python
# kinds.py — _text: pass the align through (default center = unchanged)
    return draw.box_text(canvas, it["rect"], it.get("text", ""), (0, 0, 0, 0),
                         colour, 0, ctx.font(it.get("font", "panel-label")),
                         align=it.get("align", "center"))
```

### 3b. NEW primitive: a dot-grid ground option

The only genuinely new drawing code. `draw.ground` today handles solid /
transparent / gradient; add a `dots` overlay branch. Dots are authored at REF
and scaled to the (supersampled) canvas so the texture is size-independent.

```python
# draw.py — new helper
from .families import CHECKER, MAGENTA, REF   # add REF to the existing import

def dot_grid(canvas, spec):
    """A regular grid of faint dots over the ground — the compare card's
    texture (bd3c5739 pitch 44 px grey; 4fed106c/audit ~#2a2a2c). `spec`
    keys (all at REF, scaled by canvas width): colour, pitch, radius, offset.
    Measured default: subtle #2a2a2c dots on ~48 px centres."""
    scale = canvas.size[0] / REF
    colour = tuple(spec.get("colour", (42, 42, 44)))
    if len(colour) == 3:
        colour += (255,)
    pitch = max(2, round(spec.get("pitch", 48) * scale))
    rad = max(1, round(spec.get("radius", 3) * scale))
    ox = round(spec["offset"] * scale) if "offset" in spec else pitch // 2  # half a pitch
    d = ImageDraw.Draw(canvas)
    for y in range(ox, canvas.size[1], pitch):
        for x in range(ox, canvas.size[0], pitch):
            d.ellipse((x - rad, y - rad, x + rad, y + rad), fill=colour)
    return canvas
```
```python
# draw.py — ground(): after building the solid/transparent base, before return
    fill = spec.get("fill")
    base = Image.new("RGBA", size, tuple(fill) + (255,) if fill else (0, 0, 0, 0))
    if "dots" in spec:
        dot_grid(base, spec["dots"] if isinstance(spec["dots"], dict) else {})
    return base
```

No `kinds.py` adapter is needed for the ground — `cli.compose` builds it
straight from `layout["ground"]` via `draw.ground`, and a family ground dict
with a `dots` key flows through `cli._ground` untouched (no spec override →
`_ground` returns the family dict as-is). The final
`out.convert("RGB")` guard already fires because `fill` is non-None.

### 3c. FAMILIES entry — paste-ready variant under `dark-composite`

Add inside `FAMILIES["dark-composite"]["variants"]` (alongside
`reference-thumbs` / `model-picker` / `two-up`):

```python
            # two results compared on a dot-grid black ground, each named by a
            # bare white text label above its top-left corner (no pill, no VS,
            # no logo). Cards ~3:4 portrait, LEFT high / RIGHT low. Ground dots
            # measured on bd3c5739 (pitch 44 grey) and 4fed106c (faint #2a2a2c);
            # labels left-aligned to each card, capH ~48, ~35px above the card.
            # Evidence: bd3c5739 (compare-models--flux-2-pro-vs-midjourney S07),
            # 4fed106c (compare-models--nano-banana-2-vs-flux-2-pro S04),
            # c1b34851 (ai-models--recraft-v4-styles S06, dot-grid+stagger).
            "compare-labels": {
                "ground": {"fill": BLACK, "dots": {"colour": (42, 42, 44), "pitch": 48, "radius": 3}},
                "panels": {
                    "photo":   {"rect": (140, 250, 740, 1050)},   # left, high, 600x800 = 3:4
                    "photo-b": {"rect": (870, 560, 1470, 1360)},  # right, low (~+310 stagger)
                },
                "chrome": [
                    {"id": "label-a", "kind": "text", "rect": (140, 175, 740, 235),
                     "font": "compare-label", "align": "left", "text": ""},
                    {"id": "label-b", "kind": "text", "rect": (870, 485, 1470, 545),
                     "font": "compare-label", "align": "left", "text": ""},
                ],
            },
```

The two `text` items carry the manager-supplied model names (the skeleton's
`> text:` strings). `radius` (40) and `aspect` (1:1) inherit from the family.

**Usage:** `variant: compare-labels`, `size: 1600x1600`, panel images `photo`
(generate at **3:4**) and `photo-b` (generate at **3:4**), `chrome.label-a.text`
/ `chrome.label-b.text` = the two names. Generalises to "Before"/"After" or a
metric caption by changing only the two strings.

**Deferred (needs its own input/primitive):** 4fed106c overlays a 4-thumbnail
variant strip on each card's lower edge — that needs a thumbnail-strip
primitive + a worker `thumbs` input; leave it out of the default (as the audit
does).

---

## (4) PROTOTYPE RENDER

`proto-compare-labels.png` (1600×1600), rendered by the throwaway
`proto_compare_labels.py` in this folder. It follows the
`runs/independent-1/sections/S02/compose_s02.py` precedent: a standalone script
that **read-only-imports `landing_page_gen.compose.draw`**, prototypes the new
dot-grid ground inline, and reuses `draw.panel` + a left-anchored text draw
(the `text` kind's mechanism) for the cards and labels. Nothing in the repo is
written. Placeholder panels are solid-colour `ph-A.png` / `ph-B.png` (3:4).

The render reproduces bd3c5739's structure: subtle dot-grid black ground, two
staggered 3:4 cards (left high, right low), bare white left-aligned labels
above each. This validates both the layout geometry and the proposed
dot-grid primitive (the only new drawing code) before any change lands in
`families.py` / `draw.py`.

Path:
`<2026-09-22 session scratchpad, not kept>/proto-compare-labels.png`

Full `lp-compose <spec>.yaml` cannot render this yet because the variant does
not exist in committed `FAMILIES` and the dot-grid branch is not in
`draw.ground` — both are read-only for this task. The throwaway script is the
faithful stand-in and exercises the exact primitives the spec names.

---

## (5) CONFIDENCE: **MEDIUM**

- **For (geometry & fidelity of the exact form):** two REF-frame exemplars
  measured to the pixel, internally unanimous, plus a third confirming the
  dot-grid + stagger skeleton. The layout, ground and label placement are not
  guessed.
- **Against (volume):** only 2 clean + 1 cousin exemplars, short of the
  STANDARD's ≥10 for a *modal*. The broader "labelled comparison on dark"
  population (≥13) mostly wears pills/VS/logos and belongs to `vs-two-up`, a
  different template. The generalisation to Before/After and metric captions
  is inferred from the primitive's flexibility, not separately evidenced.
- **Net:** ship it as a faithful, evidence-cited **variant** (not a default),
  which is exactly how the dark-composite audit scoped it. The implementation
  cost is small and low-risk: one new `draw.ground` branch, a 1-line font
  entry, a backward-compatible `align` param, and a FAMILIES variant — the
  text kind it needs already exists.
```
