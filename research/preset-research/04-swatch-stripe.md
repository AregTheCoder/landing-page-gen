# Preset proposal: `swatch-stripe` (a `palette-card` variant of `template-mockup`)

Read-only research, branch `layered-templates`, 2026-09-22. No committed source
touched. Prototype + views live beside this file.

**Recommendation in one line:** do NOT make a new family. Add one new draw
primitive (`swatch_stripe`) + its Kind adapter (`swatch`), and register a
`palette-card` **variant of `template-mockup`** that encodes the measured
"swatch stripe beside a finished card" modal. The audit already lists this exact
chrome as deferred template-mockup work (`research/template-audit/STANDARD.md`
line 73: "template-mockup **selection-frame**, **swatch-stripe tile** …";
`template-mockup.md` §(d) even sketches a `swatch-tile` kind). This closes it.

---

## (1) EVIDENCE

**Family served:** `template-mockup` (81 / 96 swatch-bearing corpus assets are
tagged it). The preset targets its **`column-main` sub-population**: a left
column of small tiles + one finished design card. Of 96 assets whose `chrome`
bag carries `swatch`, layout splits `single` 37 (palette *inside* a card) /
`column-main` 35 (swatch stripe *beside* a card) / `stacked` 14 / other 10. Every
one of the 9 assets carrying a detailed `swatch` `chrome_item` records
`placement: beside` (9/9). The task's wording — "a column/row of colour swatch
tiles **beside** a recoloured image" — is the `column-main / beside` cluster.

**≥10 corpus asset ids exemplifying the modal** (all `column-main`, `1:1`,
`family_hint: template-mockup`, ground transparent; every one viewed):

| id | page / slot | swatch stripe cells (viewed) |
|----|-------------|------------------------------|
| `861c2971` | instagram-post-creator S09-m1 | 3 — black / red / white |
| `8031c225` | christmas-card-maker S08-m1 | 4 — green / dk-green / black / red |
| `f57cb379` | greeting-card-maker S08-m1 | 4 — coral / orange / olive / tan |
| `56f038cf` | thank-you-card-maker S08-m1 | stripe present |
| `517b85da` | quote-poster-maker S08-m1 | stripe present |
| `80694dc4` | t-shirt-maker S08-m1 | stripe present |
| `d5d56eb0` | menu-maker S08-m1 | stripe present |
| `ba57eaf9` | birthday-card-maker S08-m1 | stripe present |
| `c3461329` | motivation-poster-maker S07-m1 | large-tile mode (see variants) |
| `d7577fb9` | bookmark-maker S08-m1 | swatch column, 3 cards |
| `3266d99b` | book-cover-maker S10-m1 | color swatches |
| `4c10cce3` | calendar-maker S08-m1 | swatch column |
| `dfd22ac3` | twitter-post-maker S08-m1 | swatch strip |

Broader corpus support (same swatch-stripe chrome, other framings, ids logged
for the citation trail): brand-kit boards `3df432c6 0e470b88 0f03db11 4cc460c2
f69463de 10abe8ee` (`single`, palette row inside the card); recolour/cutout
cards `54efb397 ad9d863b a82f6eef 48191133` (`cutout-checkerboard`, palette
stripe beside a product cutout). These confirm the primitive is reused widely;
they are *not* the modal geometry below.

**Modal layout, with counts (the 8 `S08`-style cards above):**
- 8/8 put the tile column **on the LEFT**, the finished card on the right.
- 8/8 order the column **swatch stripe (top) → magenta accent tile → black tool
  tile**. The swatch is the tall element; the two glyph tiles are equal squares.
- 6/8 share **byte-identical geometry** (`56f038cf 8031c225 80694dc4 861c2971
  d5d56eb0 517b85da`): column `x 290–481`, card `x 532–1307 / y 300–1299`.
  `ba57eaf9` and `f57cb379` are the same layout shifted ≤35 px.
- Swatch cell count: modal **4** (range 3–5), equal-height horizontal bands.
- Ground: transparent in all (the grey in the view PNGs is my preview backing;
  the page section supplies white/black — STANDARD.md rule 2).

Measured with alpha-channel column/row coverage (`measure.py` beside this file);
grounds read from alpha, never a flattened RGB read.

---

## (2) MEASURED GEOMETRY (REF = 1600, from the 6 byte-identical exemplars)

Ground: **transparent** (`ground.fill = None`).

| element | rect (x0,y0,x1,y1) | w × h | notes |
|---------|--------------------|-------|-------|
| card | `(532, 300, 1307, 1299)` | 775 × 999 | the finished design fills it |
| swatch stripe | `(290, 292, 481, 843)` | 191 × 551 | N cells, equal-height, outer corners round |
| magenta tile | `(290, 884, 481, 1075)` | 191 × 191 | accent glyph (image+), fill (251,81,238) |
| black tile | `(290, 1114, 481, 1305)` | 191 × 191 | tool glyph (T/type), fill (16,16,16) |

Gutters: column→card = 51; swatch→magenta = 41; magenta→black = 39 (≈40 px
vertical rhythm). Corner radius 40 (family default). Swatch cell colours come
from the section copy (see §3 spec), not measured.

Large-tile mode (`c3461329`, `b2749949`) is the SAME layout at column `x 152–532`
(w380) / card `x 556–1444` — this is what the **current default** template-mockup
already encodes. The small-tile modal above is the more common one across
`*-card/-poster/-post-maker` S08 slots, so it becomes the named variant; the
default is left untouched (surgical).

---

## (3) PROPOSED SPEC

### 3a. New `draw.py` primitive

```python
def swatch_stripe(canvas, rect, colours, radius, direction="column", gap=0):
    """A rounded tile split into len(colours) equal cells of solid colour; only
    the OUTER corners are rounded, interior edges butt flush. `direction`
    stacks the cells down a column (modal) or along a row; `gap` (px) inserts
    transparent gutters, else cells touch. Generalises tile(name=None), the
    single flat swatch, to N palette cells. Colours are the section palette the
    manager passes; a card_swatch_bar (Layout B, deferred) reuses direction=row."""
    x0, y0, x1, y1 = (round(v) for v in rect)
    n = max(1, len(colours))
    layer = Image.new("RGBA", (x1 - x0, y1 - y0), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    W, H = x1 - x0, y1 - y0
    horizontal = direction == "row"
    span = W if horizontal else H
    step = (span - gap * (n - 1)) / n
    for i, c in enumerate(colours):
        off = i * (step + gap)
        cell = ((off, 0, off + step, H) if horizontal else (0, off, W, off + step))
        d.rectangle([round(v) for v in cell], fill=tuple(c) + (255,))
    layer.putalpha(ImageChops.multiply(layer.getchannel("A"), rounded_mask((W, H), radius)))
    canvas.alpha_composite(layer, (x0, y0))
    return (x0, y0, x1, y1)
```

`ImageChops` and `rounded_mask` are already imported/defined in `draw.py`; no new
imports. Verified working in the prototype (`proto_swatch_stripe.py`).

### 3b. New `kinds.py` Kind adapter

```python
def _swatch(canvas, it, ctx):
    cols = it.get("colours") or [(90, 90, 96)]           # flat grey if the copy gives none
    return draw.swatch_stripe(canvas, it["rect"], cols, ctx.r,
                              it.get("direction", "column"), round(it.get("gap", 0) * ctx.s))
```
Register in `KINDS`: `"swatch": Kind(_swatch),` (default `layer="chrome"`).
`resolve()` scales `rect` and passes `colours`/`direction`/`gap` through
untouched, so `repeat:`/`place:` keep working. `text=False`, so `--describe`
lists it plainly.

### 3c. New `template-mockup` variant (paste-ready FAMILIES addition)

Add to the `template-mockup` entry a `"variants"` key (it has none today):

```python
"variants": {
    # measured small-tile modal (8 S08 cards; 6 byte-identical): swatch stripe
    # on top, magenta accent + black tool tile below, beside the finished card.
    # Evidence: 861c2971, 8031c225, f57cb379, 56f038cf, 517b85da, 80694dc4,
    # d5d56eb0, ba57eaf9. Colours come from the section copy (spec override).
    "palette-card": {
        "panels": {
            "photo": {"rect": (532, 300, 1307, 1299)},   # the card interior
        },
        "chrome": [
            {"id": "card", "kind": "card", "rect": (532, 300, 1307, 1299), "fill": (43, 20, 90)},
            {"id": "swatch", "kind": "swatch", "rect": (290, 292, 481, 843),
             "colours": [[0, 0, 0], [228, 40, 40], [245, 245, 245]]},  # placeholder; manager overrides
            {"id": "tile-accent", "kind": "tile", "rect": (290, 884, 481, 1075), "icon": "sparkle", "fill": MAGENTA},
            {"id": "tile-tool", "kind": "tile", "rect": (290, 1114, 481, 1305), "icon": "crop", "fill": (16, 16, 16)},
        ],
    },
},
```

Spec (`compose-<slot>.yaml`) the worker writes — colours from the section
palette, panel = the finished-card render:

```yaml
family: template-mockup
variant: palette-card
size: 1600x1600
panels:
  photo: { image: card.png }
chrome:
  swatch: { colours: [[12,12,14],[228,40,40],[245,245,245],[120,120,126]] }
```

**Scope note (kept out, per "surgical"):** the icons `sparkle`/`crop` stand in
for the real *image+* and *T/type* glyphs. Adding those two glyphs to
`draw.ICONS` is a trivial, separate change; the swatch stripe is the load-bearing
new element and needs no glyph. The existing flat-grey `swatch` tile in the
default template-mockup and dark-composite `tile-3` can later switch to
`kind: swatch` with `colours:`, but I leave them as `kind: tile` so
`tests/test_compose_golden.py` stays green — the new kind is purely additive.

---

## (4) PROTOTYPE RENDER

Reuses existing primitives (`draw.card`, `draw.panel`, `draw.tile`) + the one new
`swatch_stripe`, rendered by the throwaway `proto_swatch_stripe.py` (scratchpad
only). Output:

`…/scratchpad/preset-research/prototype.png` (1600×1600, previewed over white).

It reconstructs `861c2971`: black/red/white swatch stripe with rounded outer
corners and flush inner cells, magenta accent tile, black tool tile, and a
solid-colour placeholder card (`placeholder-card.png`) standing in for the
finished design. Side-by-side reference views of the real assets:
`view-861c2971.png`, `view-8031c225.png`, `view-f57cb379.png`; isolated swatch
crops `swatch-*.png`.

---

## (5) CONFIDENCE: **HIGH**

- 96 corpus assets carry the swatch chrome; 35 in the `column-main / beside`
  target layout; 13 ids listed, 8 measured, **6 byte-identical** — a clear modal,
  not one exemplar (satisfies STANDARD.md rule 1).
- Ground measured from alpha = transparent (rule 2).
- Every chrome element cites living asset ids in the variant comment (rule 3).
- Geometry is real (rule 4 — nothing invented); the only un-measured input is the
  swatch cell colours, which are copy-derived by design.
- Reuses an existing family + existing primitives + one small new primitive that
  is already prototyped and rendered.

**One judgement call flagged:** small-tile mode is the modal for S08 template
cards, but the *current default* template-mockup is large-tile mode. I propose
the new modal as a **variant** rather than flipping the default, to stay surgical
and keep goldens green; if the team would rather the measured modal BE the
default, that is a one-line swap (promote `palette-card` geometry to the family,
demote today's large-tile block to a `poster-card` variant).
