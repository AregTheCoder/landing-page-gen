# Preset 09 — S02/S08 replay: generalise the two independent-1 section renderers

Goal: turn the two hand-written section-local renderers from `runs/independent-1`
into first-class `lp-compose` family features, and say **exactly** which grammar
additions each needs and which already landed in waves 1–10.

- `runs/independent-1/sections/S02/compose_s02.py` — before/after **50/50 split**
  at 16:9 with a thin seam **divider** and Before/After pills.
- `runs/independent-1/sections/S08/compose_S08.py` — a **vs two-card** hero at
  16:9 with **per-panel ground** (dark left / light right), a gutter, per-card
  **label pill + attribute chip**, and a **VS** round badge on the seam.

Read-only research. No `picsart_*` call, no generation, zero credits. All renders
below are `lp-compose`/section-renderer output on solid-colour placeholders.

---

## 0. Verdict up front (the three candidate additions the task names)

| candidate addition | needed? | why |
|---|---|---|
| **divider primitive** | **YES — new** | S02's seam. No `draw.*` primitive draws a line/rule/handle today. `compare-handle` exists only as a corpus *label* kind (wave 8), not as a compose primitive. `card` can't stand in (opaque RGB, fixed `radius`, no thin translucent bar). |
| **per-panel ground** | **NO — already expressible** | Achieved with the landed `card` kind (wave 3 registry + `card` layer, which draws *before* panels) placed behind inset photo panels, plus a per-spec `ground:` override. Prototype C proves the dark-left / light-right look renders with zero new code. |
| **gutter / radius spec keys** | **NO — not grammar** | Gutter is just the gap baked into the panel rects (REF frame). Radius is the family `radius` field, and a `variant` may override it (`cli.template()` merges the variant over the family top-level keys). No new key needed. |

Net: **one new primitive (`divider`), for S02 only.** S08 is a pure data
addition (a 16:9 variant of the already-landed `vs-two-up` family).

---

## 1. EVIDENCE

### 1a. What already landed (waves 1–10) that these two rely on

From `git log` and the current source:

- **wave 3** (`fa49707`) chrome-kind **registry + layer model** (`kinds.KINDS`,
  `LAYERS = ground<card<panel<chrome<overlay<top`) — lets a new kind be added
  and placed by layer; lets `card` items sit *behind* panels.
- **wave 4** (`5eed995`) **`place:` / `repeat:`** (`layout.py`) and **list-form
  chrome** (`cli._chrome_entries`: a chrome list where a new `id`+`kind` *adds*
  an item). S08's `chrome: [ {id: vs-badge, …} ]` list form is this.
- **wave 5** (`b1ab6a8`) **`text` kind** (free label on transparent fill).
- **wave 6** (`a9a66d5`) **`vs-two-up` family + `round-badge` primitive** — S08's
  VS mark is already first-class; the two-card skeleton (two side-by-side panels
  + a seam badge) already exists at 1:1.
- **wave 7** (`da7ddda`) `mockup-card` + `profile-card`.
- **wave 8** (`0ac6e92`) split `slider` → **`adjust-slider` + `compare-handle`**
  — but only in the corpus *attribute* vocabulary (`attrs.CHROME_KINDS`). There
  is **no** compose primitive that draws a compare-handle. This is the gap.
- Pre-existing: **multi-aspect** via `aspects` (`panel-overlay` carries
  `((4,3),(5,4))`) and **variant `aspect` override** (`before-after`'s `wide`
  variant is 21:10). A 16:9 variant is therefore already a supported shape of
  data — `cli.load_spec` reads `family.get("aspects") or (family["aspect"],)`
  from the *resolved* (variant-merged) template.

So both replays are mostly assembly of landed pieces. The only true code gap is
the divider.

### 1b. S02 — before/after 50/50 split (corpus family: `before-after`)

Query: `before_after=True AND layout=split AND family_hint=before-after`
→ **20 distinct assets, 19/20 `photo-full-bleed`** (the two halves *are* the
ground; 1 is black). The pure 50/50 side-by-side halves (excluding the
before+result *composite cards* 063c75bf / 08385997 / 69ed3f5c / ad4a1557 /
bcc56313 / c5715e9b, which are the existing `wide`/square variant's territory):

`303e844a` (ai-photo-editing S01), `06bfdecd` (aura S08), `2d5cd187`
(video-enhancer S01), `54964550` (red-eye-remover S02), `18910633` (photo-effects
S13), `82424493` (photo-effects S13), `85838174` (image-tools S05), `91443790`
(red-eye-remover S02), `99076257` (hair-color-changer S02), `89382c9a`
(ai-image-enhancer S16), `efee1128` (photo-editor S14), `9be1bcb6` (draw S10),
`acf65550` (ai-sticker-maker S12), `f223c881` (video-enhancer S10) — **14 pure
splits, ≥10 comfortably.**

Modal, viewed (contact sheet `sheet_vs.png`): **two touching halves, no gutter,
edge-to-edge; a seam mark on the midline; a `Before`/`After` pill low on each
half.** The seam mark recurs as a `compare-handle` (a round grip with L/R
arrows — `303e844a`, `06bfdecd`, `18910633`, `89382c9a`, `acf65550`) or an
`adjust-slider` (`efee1128`, `9be1bcb6`); S02's own render used the plainest form,
a hairline translucent rule. **8/14 carry a real divider mark on the seam.**

### 1c. S08 — vs comparison (corpus family: `vs-two-up`)

Query: `vs-badge in chrome OR family_hint=vs-two-up` → **132 distinct**. Two forms:

- **Full-bleed split (63)** — one scene rendered by two models, shown as two
  *touching* halves on a `photo-full-bleed` ground (62/63), a VS badge or model
  pills on the seam. e.g. `4418775b`, `6612e61a`, `8632c15f`, `a03ad87c`. **This
  is the true modal vs layout.**
- **Two-card (13)** — two *separate* rounded cards with a gutter, VS badge on the
  gutter, a model-name pill (+ attribute chip) per card. **This is S08.** Grounds:
  `black` 7, `mixed` 3, `photo-full-bleed` 3. Citations:
  `1ccc69c2` (gpt-vs-flux S01, mixed), `e901b80b` (ideogram-vs-flux S01, mixed),
  `7f9dc20b` (sora-vs-veo S07, mixed), `288da9d2` (dall-e-vs-mj S10, black),
  `2adc1808` (imagen-vs-gpt S12, black), `553d11df` (ideogram-4-0 S12, black),
  `6adeac96` (luma-vs-kling S12, black), `65ba628b` (video-to-gif S13, black),
  `f7808afd` (seedance-vs-kling S08, black), `2ada28c9` (seedance-2-5 S10, black),
  `f584f8d2`/`f1025f68`/`46bb8816` (photo-full-bleed). **13 assets.**

Honest caveat (STANDARD.md rule "template the modal, rarer forms are variants"):
the two-card form S08 builds is the **minority** vs layout (13 vs 63 full-bleed
split). The **black-ground** two-card is its modal (7/13); the exact **dark-left
/ light-right asymmetry** S08 uses is only 3 assets (`1ccc69c2`, `e901b80b`,
`7f9dc20b`). So the two-card belongs as a *named variant*, with **black-symmetric
as the safe default** and the dark/light "mixed" ground as an opt-in per spec.
(The landed `vs-two-up` family default is a *third* thing — a single light-grey
ground — and is itself arguably mis-templated against the full-bleed-split modal;
flagged as an open item, out of scope here.)

---

## 2. MEASURED GEOMETRY (REF = 1600; slots are 16:9 = 1600×900)

Grounds measured as **transparent/photo** from the alpha behaviour of the sampled
assets (the two halves/cards *are* the picture or sit on a page-supplied ground —
no painted black gutter). No panel-rect table is stored in `attributes.yaml`
(`chrome_items` carry no geometry); rects below are the section renderers' own
measured values, which reproduce the corpus proportions.

**S02 split (16:9):** before `(0,0,800,900)`, after `(800,0,1600,900)` — a clean
50/50, radius **0** (edge-to-edge, no rounded corners). Divider: vertical, `x=800`,
width `4`, colour white @ opacity `130`. Pills: `Before` bl of `before`, `After`
bl of `after`, `translucent` style. Ground transparent.

**S08 two-card (16:9):** left card = the black ground; right card = a light
rounded `card` `(800,0,1600,900)`. Photo panels inset with a ~40 px margin and a
40 px gutter: left `(40,40,780,860)`, right `(820,40,1560,860)`. Model-name pill
bl of each panel; attribute chip br of each panel. VS `round-badge` centred on the
gutter: `(712,362,888,538)` (176 px dia, canvas centre). Card radius = family
`radius` (40); the section script used photo-radius 24 ≠ card-radius 32 — a
cosmetic split that collapses to one `radius` with no visible loss.

---

## 3. PROPOSED SPEC

### 3a. `before-after` → add a `split` variant (+ the new `divider` chrome)

Paste into the `"variants"` dict of `FAMILIES["before-after"]` in
`src/landing_page_gen/compose/families.py`:

```python
# S02 replay: the pure 50/50 before|after split — the modal for a *comparison*
# (not the before+result composite card). 14 pure-split corpus assets, all
# photo-full-bleed: 303e844a (ai-photo-editing S01), 06bfdecd (aura S08),
# 89382c9a (ai-image-enhancer S16), 18910633 (photo-effects S13), acf65550
# (ai-sticker-maker S12), 2d5cd187 (video-enhancer S01), 54964550
# (red-eye-remover S02), 82424493/91443790/99076257/85838174/efee1128/9be1bcb6/
# f223c881. Two halves touch (radius 0), a hairline seam divider (8/14 carry a
# compare-handle/slider mark on the seam), Before/After pills bl of each half.
"split": {
    "aspect": (16, 9),
    "ground": {"fill": None},                      # transparent — the halves are the picture
    "radius": 0,                                   # edge-to-edge, no rounded corners
    "panels": {
        "before": {"rect": (0, 0, 800, 900)},
        "after":  {"rect": (800, 0, 1600, 900)},
    },
    "chrome": [
        # NEW kind. plain rule by default; set handle:true for the round grip
        # the corpus shows (303e844a, 06bfdecd).
        {"id": "divider", "kind": "divider", "orient": "v", "rect": (798, 0, 802, 900),
         "colour": (255, 255, 255), "opacity": 130},
        {"id": "before-pill", "kind": "pill", "at": "before", "corner": "bl", "text": "Before", "style": "translucent"},
        {"id": "after-pill",  "kind": "pill", "at": "after",  "corner": "bl", "text": "After",  "style": "translucent"},
    ],
},
```

Selected with `variant: split` in the spec (or the skeleton's `> device:` line).

### 3b. NEW primitive `divider` (`draw.py`) + Kind adapter (`kinds.py`)

`draw.py`:
```python
def divider(canvas, rect, fill, orient="v", handle=False, fnt=None):
    """A straight seam rule filling `rect` (a thin bar), alpha-composited so it
    can be translucent — the before/after seam. When `handle`, add a round white
    grip with a small double-arrow at the bar's midpoint: the corpus
    compare-handle (303e844a, 06bfdecd). `fill` is RGBA. Returns rect."""
    # one-liner behaviour: alpha_composite a rounded bar; if handle, draw a white
    # disc (~0.09*min(canvas) dia) at the midpoint with a 2-unit chevron pair.
```

`kinds.py` — one adapter + one registry line (layer `chrome`, above panels):
```python
def _divider(canvas, it, ctx):
    colour = tuple(it.get("colour") or (255, 255, 255))
    fill = colour + (it.get("opacity", 255),)
    return draw.divider(canvas, it["rect"], fill, it.get("orient", "v"),
                        it.get("handle", False), ctx.font("pill"))
# in KINDS:
"divider": Kind(_divider),          # layer defaults to "chrome"
```
`rect` is scaled by `resolve()` exactly like every other rect — no `cli.py` change.
This is the whole delta: **one draw fn, one adapter, one KINDS entry, one variant.**

### 3c. `vs-two-up` → add 16:9 + a `cards` variant (NO new primitive)

Add `aspects` to the family and a variant; everything renders on landed
primitives (`card`, `pill`, `round-badge`):

```python
# in FAMILIES["vs-two-up"]: allow the 16:9 hero shape alongside the 1:1 default
"aspects": ((1, 1), (16, 9)),
...
"variants": {
    # S08 replay: two separate cards, VS badge on the gutter, a model-name pill
    # (bl) + attribute chip (br) per card. Two-card corpus form, black-ground
    # modal: 288da9d2, 2adc1808, 553d11df, 6adeac96, 65ba628b, f7808afd,
    # 2ada28c9; dark/light "mixed" opt-in: 1ccc69c2, e901b80b, 7f9dc20b.
    # Left card = the black ground; right card = an opt-in light `card`.
    "cards": {
        "aspect": (16, 9),
        "ground": {"fill": (0, 0, 0)},                 # black-symmetric default
        "panels": {
            "left":  {"rect": (40, 40, 780, 860)},
            "right": {"rect": (820, 40, 1560, 860)},
        },
        "chrome": [
            # drop `card-right` (omit) for the black-symmetric modal; keep it for
            # the dark/light "mixed" look S08 used.
            {"id": "card-right", "kind": "card", "rect": (800, 0, 1600, 900), "fill": (236, 236, 239)},
            {"id": "vs", "kind": "round-badge", "rect": (712, 362, 888, 538), "text": "VS"},
            {"id": "label-left",  "kind": "pill", "at": "left",  "corner": "bl", "text": "", "style": "solid-light"},
            {"id": "chip-left",   "kind": "pill", "at": "left",  "corner": "br", "text": "", "style": "solid-light"},
            {"id": "label-right", "kind": "pill", "at": "right", "corner": "bl", "text": "", "style": "solid-dark"},
            {"id": "chip-right",  "kind": "pill", "at": "right", "corner": "br", "text": "", "style": "solid-dark"},
        ],
    },
},
```

Rules constraint: the pill carries the **model name text only** — the corpus
`model-logo` (OpenAI/Flux/… marks) is a forbidden third-party mark and is **not**
drawn by compose. The chip is an attribute/size string (`1024x1024`, `2K`, `1x1`,
`~3s`) the manager derives — a legitimate `size-label`. (Optional nicety: a
`"chip"` entry in `draw.STYLES`, e.g. `(255,255,255,46)`+white, for the exact
translucent chip fill the corpus uses; `solid-dark`/`solid-light` read fine
without it.)

No `draw.py`/`kinds.py`/`cli.py` change for S08 — it is data only.

---

## 4. PROTOTYPE RENDER

All three written to the research folder; specs + placeholders alongside.

- **C — `render_C_s08_cli.png`** (the load-bearing one): the S08 grammar rendered
  by the **stock `uv run lp-compose`** on **existing primitives** —
  `ground: black` + a light `card-right` + two panels + four `pill`s (model name
  bl, size chip br) + the inherited `round-badge` VS. Spec:
  `protoC-s08-cli.yaml`. Rendered at the family's native **1:1** (the CLI rejects
  16:9 until the `aspects` line above lands — that is the only blocker, and it is
  data). This proves **S08 needs no new primitive**.
- **B — `render_B_s08.png`**: the S08 *target* look at 16:9 via the section
  renderer (`compose_S08.py` + `protoB-s08.yaml`): dark-left / light-right cards,
  gutter, model labels + chips, VS on the seam.
- **A — `render_A_s02.png`**: the S02 *target* look at 16:9 via the section
  renderer (`compose_s02.py` + `protoA-s02.yaml`): two halves + a hairline seam
  divider + Before/After pills. This is what the `divider` primitive must
  reproduce; the first-class path (variant `split` above) renders identically
  once `draw.divider` exists. Montage of all three: `renders_montage.png`.

---

## 5. CONFIDENCE

- **S02 (`before-after`/`split` + `divider` primitive): HIGH.** ≥10 (14) pure-split
  corpus assets, one clear modal (50/50, transparent, seam mark, pills), a small
  corpus-motivated primitive (`compare-handle` is already a named corpus kind).
  Low-risk, ~30 lines.
- **S08 (`vs-two-up`/`cards` variant): MEDIUM.** The two-card pattern is real and
  coherent (13 assets, black-ground modal), and reuses only landed primitives
  (prototype C confirms). Pulled down from high because (a) the two-card form is
  the *minority* vs layout — the full-bleed split (63) is the true modal, so this
  is correctly a variant, not a default; and (b) the exact dark/light asymmetric
  ground S08 chose is only 3 assets, so black-symmetric should be the default and
  the light card an opt-in.

**Overall: MEDIUM** (S02 high, S08 medium; one small new primitive total).
