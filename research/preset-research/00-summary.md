# Compose audit-backlog presets — synthesis + completeness

Read-only synthesis of the nine per-preset proposals in this folder
(`01`–`09`). No paid calls, no source touched. Purpose: decide **authoring
order** (what is ready for Areg's eye now vs later), flag what is **under-
evidenced**, isolate the **MAGENTA** fix, and name the **conflicts** that stop
two presets being authored in parallel.

---

## (1) Ranking by evidence strength × primitive cost

Ordered best-first. "Ready" = high confidence AND either no new primitive or a
single small self-contained one; those are the ones to author with Areg now.

| # | preset | family | conf. | evidence (exact form) | new primitive? | modal clear? | tier |
|---|--------|--------|-------|-----------------------|----------------|--------------|------|
| 08 | before-after-wide-default | before-after | **high** | 16 wide / 5 sq of 123 tagged (76% wide) | **none** (reuses pill/tile/panel; `variant: wide` already ships) | yes, strong | **A — author first** |
| 02 | crop-grid | crop-frame | **high** | 13 assets; 3×3 grid 12/12; overlap-cards 5/12 | yes — small (brackets `grid=` + `disc_icon`/`crop-badge` Kind) | yes | **B — ready** |
| 04 | swatch-stripe | template-mockup | **high** | 13; 8/8 sampled, 6/8 byte-identical geom | yes — one (`swatch_stripe` + `_swatch` Kind) | yes | **B — ready** |
| 03 | selection-frame | template-mockup + cutout-checkerboard | **high** | 63 selection-handles assets; 8 viewed | yes — one (`selection_frame` + Kind); +2 optional icons | yes (contrast-driven) | **B — ready (author before 05)** |
| 06 | multi-aspect | before-after / dark-composite / template-mockup | med | 18; population-backed per family | mostly cli/families; one **optional** divider | yes (mechanism) | **C — mechanism, do deliberately** |
| 09 | s02-s08-replay | before-after + vs-two-up | med | S02 14 pure-split (high); S08 13 two-card (minority vs 63) | S02 needs `divider`; **S08 reuse-only** | S02 yes; S08 ok (black default) | **C/D — split the two halves** |
| 05 | editor-exploded | template-mockup | med | 9 assets (8 viewed); **minority** within family | yes — **three** (2 of them = 03 + 04) | yes but minority | **D — author last, depends on 03+04** |
| 07 | per-panel-ground (split-tone) | vs-two-up | med | **only 2 clean** exemplars (1ccc69c2, e901b80b); ~10% form | none (reuses card + LAYERS `mat`) | weak | **re-scope / defer** |
| 01 | compare-labels | dark-composite | med | **2 clean + 1 cousin** for the exact form (<10) | yes — `dot_grid` ground branch | weak (exact form) | **re-scope / defer** |

---

## (2) New primitive vs reuse (this sets authoring order)

**Reuse-only (fastest — no `draw.py`/`kinds.py` risk):**
- **08 before-after-wide-default** — pure `FAMILIES` restructure. (Has a test/
  doc ripple; see conflicts.)
- **06 multi-aspect** — `cli.py` + `families.py` only (aspects-as-mapping +
  nearest-block select); divider is optional.
- **09 S08 half** — ground + card + pills + existing round-badge; blocked only
  on the `aspects` line, no new draw code.
- **07 per-panel-ground** — reuses `card` on a new `mat` layer; plumbing only.
  (But under-evidenced — see §3.)

**One small self-contained new primitive (author next):**
- **02 crop-grid** — `brackets(grid=…)` one-liner + `disc_icon`/`crop-badge`.
- **04 swatch-stripe** — `swatch_stripe` + `_swatch` Kind.
- **03 selection-frame** — `selection_frame` + Kind (+2 optional ICONS).

**Needs a primitive that another preset also owns (author after that one):**
- **09 S02 half** — `divider` (also proposed by 06 — author once).
- **05 editor-exploded** — three primitives, but two are **03's
  selection-frame and 04's swatch-bar**; only `type-tile` is genuinely new
  (and it wants a serif face the repo does not bundle — only Manrope ships).
  So 05 is mostly assembly once 03 + 04 land.

**Suggested order:** 08 → (02, 04, 03 in parallel) → 06 (reconciled with 08) →
09 → 05.

---

## (3) Completeness pass — under-evidenced, drop or re-scope

The STANDARD bar is ≥10 assets with a clear modal before templating. Two
presets miss it on the **exact** form they propose, even though an adjacent
population is large:

- **01 compare-labels — re-scope, do not author on the modal claim.** The exact
  dot-grid + bare-label form has **2 clean exemplars + 1 cousin**. The ≥10 that
  share the *intent* wear pills/VS/logos and belong to **vs-two-up**, a
  different template. Author's own dot-grid detector could not separate the
  population — the form is niche. Keep it as a cited low-priority *variant* of
  dark-composite (as the audit already scoped it) or shelve it; do not present
  it to Areg as a ready modal. The `dot_grid` ground branch is cheap and reusable
  if you do land it.

- **07 per-panel-ground — re-scope / defer.** Only **1ccc69c2 and e901b80b** are
  clean two-solid-contrasting-ground exemplars; the rest of the ~10% "mixed"
  bag is photo+card, not the proposed form. This is the minority hero form
  style-families.md already marks "not templated." Ship only as an opt-in
  variant if at all; the LAYERS `mat` plumbing is the real (small) deliverable.

- **05 editor-exploded — keep but sequence last, not drop.** 9 assets and a
  genuinely reproduced modal, but it is a **minority** arrangement inside
  template-mockup (family modal is the icon/swatch-tile card) and it leans on
  three primitives, two of which belong to 03/04. Correctly a variant; author
  after 03 + 04 so it is assembly, not new drawing.

Everything else clears the bar: **02** (13, grid 12/12), **03** (63
selection-handles assets), **04** (8/8 byte-identical), **08** (123-asset
population, 76% wide), **06** (per-family populations), **09 S02** (14
pure-split).

---

## (4) MAGENTA fix — ships on its own, not a preset

`families.py` defines `MAGENTA = (181, 23, 170)`; the real Picsart accent is
≈ **`#e01ee0` = (225, 30, 224)`**. This is a **one-line constant change**, not a
preset — land it independently. Note it is **load-bearing for 04
swatch-stripe and 05 editor-exploded** (both render a magenta accent tile), so
it should land **before or with** those two so their goldens are generated
against the correct accent, not the wrong one. It will also shift any existing
golden that renders MAGENTA — regenerate those shas in the same commit.

---

## (5) Conflicts — do NOT author these in parallel

- **before-after is touched by three proposals (06, 08, 09).** 08 swaps
  default↔variant so wide 21:10 becomes the default; 06 rewrites `aspects` into
  a mapping with its own before-after 1:1/2:1/16:9 blocks; 09 adds a `split`
  16:9 variant. 06 and 09 even define the **same** 16:9 geometry
  (`before 0,0,800,900` / `after 800,0,1600,900`) and **both add `draw.divider`**.
  → Reconcile all three into **one** before-after authoring pass: land 08's
  default flip first, express 06's other aspects as variants on top of it, add
  the divider **once**, and fold 09's split into that. Never three parallel edits
  to `FAMILIES["before-after"]` / the aspects mechanism.
- **`draw.divider` is proposed twice (06 and 09).** Author one primitive; both
  consumers reference it.
- **vs-two-up is touched by 07 and 09.** 07 adds per-panel `ground` on a `mat`
  layer; 09 adds a `cards` variant + `aspects` line + VS round-badge. Different
  mechanisms, same family dict — sequence them, don't parallelise.
- **05 depends on 03 + 04.** 05's `selection-frame` and `swatch-bar` ARE 03 and
  04. Author 03 + 04 first; do not let 05 re-define them.
- **`cli._ground` / `draw.ground` is edited by 01 (dot-grid branch) and 07
  (per-panel return shape).** Minor, but land them aware of each other.

---

## Return summary

**Ready to author now:** `08 before-after-wide-default` (high, zero new
primitives — do first, with the test/doc ripple it flags), then
`02 crop-grid`, `04 swatch-stripe`, and `03 selection-frame` (all high, each
one small self-contained primitive). **Sequence after those:** `06 multi-aspect`
and `09 s02-s08` (reconciled with 08 into a single before-after pass, sharing
one `divider`), then `05 editor-exploded` last since it is assembly on top of
03 + 04. **Drop or re-scope:** `01 compare-labels` and `07 per-panel-ground` are
under-evidenced (2–3 clean exemplars, the ≥10 belong to a different template)
and should ship, if at all, only as cited niche variants — not presented as
modals. Land the one-line **MAGENTA** constant fix (`(181,23,170)` →
`(225,30,224)`) on its own, before/with 04 and 05, and regenerate the goldens
it shifts.
