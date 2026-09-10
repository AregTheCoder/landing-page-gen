# Layered photographs — method design (for review)

Status: **design only, no paid calls yet.** Areg's plan: get one small set of
layered photographs to a quality bar, then feed the method into the assembled
composite families (`template-mockup`, `dark-composite`) so their photo panels
gain the same depth. This file is the method to review before we pilot.

## What "layered photograph" means here

One believable photograph built from **more than one photographic element**,
harmonised so it reads as a single exposure: a foreground subject sitting in a
generated environment with matched light, a cast contact shadow, correct scale
and occlusion, and no cut-out matte line. The difficulty is not making the
elements — it is making them agree.

This is new. What already exists is deliberately shallower and must not be
confused with it:

| Existing | What it does | Why it is not this |
|---|---|---|
| `product cutout` pattern | generate → `remove_bg` → `change_bg` | swaps a backdrop; no light/shadow matching, so the subject reads as pasted |
| `graphic-collage` family | cutout over a flat saturated ground + shapes | poster look on purpose; "no photographic backgrounds" is in its Never list |
| `template-mockup` `photo` panel | one flat photo | single layer; depth comes later from lp-compose chrome, not from the photo |
| `outcome-tile` | `change_bg` states | a backdrop swap per tile, not a composed scene |

## Two construction routes

The worker picks one per slot from the brief's annotation.

**Route 1 — model-native composition (preferred; fewest seams).**
One `gemini-3-pro-image` call composes the whole scene in a single pass; if a
specific subject/product must stay identical, pass its reference in `imageUrls`
(the tool takes up to 14). The model relights and grounds everything itself, so
light coherence is best and there is no matte line — at the cost of exact
placement control. Use when the elements can be described together and no pixel-
exact real subject is required.

- Cost: 5 cr (1 call), +5 per refine.
- Failure mode: the model merges elements or ignores one; fix by naming each
  element, its position, and the light in one sentence each, then i2i-refine.

**Route 2 — cut-and-place chain (most control; more seams to harmonise).**
Build the plate and the subject separately, cut the subject, place it, then
**harmonise as an explicit step**. Use when a specific subject must land in a
specific plate, or when reflections/occlusion need per-element control.

1. **Plate** — `gemini-3-pro-image`, slot aspect: the background scene, with
   negative space where the subject will sit and the **key-light direction
   named in the prompt** (e.g. "soft key from camera-left, warm 3pm light").
   Gate: empty landing zone present, light direction legible, no stray subject.
2. **Subject** — `gemini-3-pro-image`, on a plain backdrop, **lit from the same
   named direction** as the plate. Gate: subject only, that light direction,
   full margin.
3. **Cut** — `picsart_remove_bg` (free). Gate: clean alpha, no halo, hair and
   thin edges intact.
4. **Harmonise (the hard step)** — pass **plate + cut subject** as `imageUrls`
   to `gemini-3-pro-image` with a prompt that only asks to seat the subject:
   "place the subject on the surface, cast a soft contact shadow to camera-
   right, match the warm light and the plate's grain, keep the subject
   identical." This is where a paste becomes a photograph. (Fallback if i2i
   drifts the subject: `picsart_change_bg` for placement, accept a weaker
   shadow, and note it.)
5. **Finish** — `picsart_enhance` only if the pick is soft or over ~2000 px.

Both routes end at the same gate. Route 1 is the default; Route 2 is for
control.

## The harmonisation gate (the hard-case checklist)

Beyond the normal gate (text strings exact, nothing from the family Never list,
no artefacts, subject in crop), a layered photograph must pass **all** of:

- [ ] **Light direction agrees** — one key-light side across every element; no
      element lit from a contradicting angle.
- [ ] **Colour temperature agrees** — no element visibly warmer/cooler than the
      plate.
- [ ] **Contact shadow present and correct** — the subject casts a grounding
      shadow; its direction and softness match the plate's own shadows. A
      floating subject fails.
- [ ] **No matte line / halo** — edges read as photographed, not cut.
- [ ] **Scale and perspective plausible** — subject size, horizon and vanishing
      consistent with the plate.
- [ ] **Occlusion correct** — overlaps read right; nothing clips or floats.
- [ ] **Focus / grain / depth-of-field match** — the inserted element shares the
      plate's sharpness and noise; a suspiciously crisp subject fails.

A failure re-runs its **own** step (plate, subject, or harmonise), never the
whole chain, and the fix is recorded as a new step in `workflow.yaml`.

## Anchor to the corpus, then vary — for a layered set

Invariants (the fixed spine, from the brief's examples and shared context):
key-light direction, colour temperature, plate genre, finish, and any text
string. Vary per slot: subject, prop, secondary element, camera distance,
compositional balance. A set of layered photos that differ only by subject on an
identical plate has under-used the freedom; move the camera and the accent too,
holding the light.

## Budget

A layered photo is 2–5 paid calls. Typical Route 2: plate 5 + subject 5 +
harmonise 5 (+ enhance 5) = 15–20 cr, with one rework round ~25–30. The per-slot
cap of 40 covers it. Preflight the whole planned chain before step 1 and stop if
the quote exceeds the section cap — depth is for the harmonisation step, not a
licence to overrun.

## How this feeds the assembled composites (A)

Once the harmonise step reliably passes, the `photo` panel of `template-mockup`
and `dark-composite` is generated by **this layered method instead of a single
flat generate**. The callout's photo then has real depth before `lp-compose`
draws the card and tiles, and each panel of a future multi-panel `template-
mockup` (the live-4 `[fit]` gap) is a proper layered plate. Nothing in
`lp-compose` changes; only the panel-generation step upgrades.

## Scaling ladder

1. **Pilot 1 (B):** 2–3 layered-photo slots on one page, both routes exercised,
   iterate to the checklist bar. Deliverable: the routes that held, the prompts
   that worked, the gate items that actually caught failures.
2. **Pilot 2 (A):** feed the winning method into one `template-mockup` section's
   `photo` panels; confirm the composite reads richer with no `lp-compose`
   change.
3. **Scale:** promote `layered` to a first-class pattern in `image-workflows.md`
   with this gate block, decide whether it is its own family or a modifier on
   existing ones, then run a full page.

## Open questions for Areg

1. **Where does `layered` live** — a new *pattern* (like `direct`/`series`) usable
   by any family, a new *style family*, or a *modifier* on `photo` panels? My
   lean: a pattern, because it is a way of building a panel, not a look.
2. **Pilot page** — pick a real Picsart page whose hero/callouts want a layered
   product-in-scene look (e.g. a background/scene/product page), or synthesise
   3 slots for the pilot outside a full run?
3. **Route 1 vs Route 2 default** — I lean Route 1 first (cheaper, best light),
   Route 2 only when the brief needs exact placement. Agree?
4. **Harmonise fallback** — is a weaker `change_bg` shadow acceptable when i2i
   drifts the subject, or should the slot fail and escalate instead?

## After approval (not done yet)

Codify the approved method as a `layered` pattern block in
`.claude/skills/picsart-workflows/image-workflows.md` with the harmonisation
gate, add the routes to the worker's contract, add a `prd.md` rule and a
`plan.md` decision row, then run Pilot 1.
