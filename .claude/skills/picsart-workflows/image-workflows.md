# Image workflows

Pick the pattern that matches the slot, write every step into
`workflow.yaml`, preflight, then run with a gate after each step.

## Patterns

**direct**: for the hero or any slot with no shared context yet.
1. generate `gemini-3-pro-image`, `count: 1`, 1K, nearest ratio → gate: pass,
   or fix the prompt and regenerate (once). The prompt names the stock genre
   from the brief's `## References` (subject, light, backdrop, colour,
   framing) and keeps clear the area a chrome item will cover.
2. targeted edit (`picsart-qwen-image-edit`) only if the gate named a
   concrete flaw (extra hand, stray object, wrong colour).
3. enhance ×2 if the slot is wider than 2000 px or the pick is soft.

**anchored** (default after the hero): same as direct, but the prompt carries
the hero's light, palette and finish in words from `shared-context.md`
("hard even studio flash, seamless yellow and purple, glossy editorial
finish"). Pass the hero URL in `imageUrls` only when `shared-context.md`
already has one when you start and the slot is a Series member; then the
prompt also says what of the hero must not appear ("no rose, no vase").
Words keep the page reading as one campaign without waiting for the hero.

**product cutout**: for slots whose source media is a subject on a flat or
transparent background.
1. generate the product alone on a plain mid-grey backdrop.
2. `picsart_remove_bg` (free) → gate: clean edges, no halo.
3. either stop (transparent PNG) or `picsart_change_bg` with the scene the
   brief describes → gate: subject scale and shadow are plausible.
4. enhance if needed.

**series**: galleries and tutorial-card thumbnails that must look like a
set. `gemini-3-pro-image` like every other finished slot — a gallery of
finished cards is finished work, not drafts. One generate with `count` 4–6,
one prompt template with a slot-specific subject phrase, hero as reference.
Gate: reject any member that breaks the set (different finish, text, wrong
framing, a different family or ground variant from the brief); regenerate
members singly. Members are the place to spend the per-slot headroom: after
the set passes as a set, revisit the weakest one or two with an i2i refine
and a controlled variation rather than shipping the first pass.

**composite**: when the brief's `## Style family` block's **Template** line
names an `lp-compose` template (`style-families.md`). A block whose
**Template** says `none; brief as X` never reaches you unchanged (the
manager briefs X's block, with a `Stands in for:` line); `kept-from-source`
slots never reach a worker. Pattern per family: composite for
dark-composite, before-after, crop-frame, cutout-checkerboard and
template-mockup; direct or anchored for full-bleed; series for
cinematic-still, graphic-collage, outcome-tile and any slot the brief marks
as a Series; fallback families take the pattern of the family they are
briefed as. The worker generates the photographic panels only;
`lp-compose` draws ground, panels and chrome. `uv run lp-compose --describe
<family>` prints the panels and the `aspectRatio` to generate each at.
1. one `picsart_generate` per distinct panel that `uv run lp-compose
   --describe <family>` lists for the brief's `Device:` variant (the plain
   template when the device is `none` or annotation-carried), `count: 1`, at
   its ratio, hero in `imageUrls` when anchored; thumbnails (`thumb-a`,
   `thumb-b`) on `gemini-3.1-flash-image`; the prompt describes the
   photograph only → gate: photo content only, subject inside the panel's
   crop, nothing from the family's **Never** list, thumbnails in the same
   finish and palette as the main panel.
2. before/after pairs are one photo: the after is `picsart_enhance`,
   `picsart_change_bg` or `picsart_remove_bg` (free; placed `fit: contain`)
   on step 1's URL, never a second generate; the result panel reuses the
   after URL with its own anchor.
3. write `compose-<slot>.yaml` (family, `variant:` exactly as the brief's
   `Device:` names it when the family draws that device, `size` = the
   slot's natural size, one image per panel with an anchor; `omit:` any
   chrome item whose text the model rendered instead, e.g. `omit:
   [headline]` for `template-mockup`), run `uv run lp-compose
   compose-<slot>.yaml --out steps/<slot>-<step>-1.png`, `Read` it → gate:
   panels unstretched, each subject inside its panel, the device's panels
   and chrome present (thumbnails, list card, second panel), chrome legible
   at 480 px, chrome text only the family's labels, no string appearing
   twice (once in the panel, once as chrome). Costs nothing, no preflight.

## Prompt rules

- Subject, setting, light, finish, camera, in that order. One sentence each.
- Name the finish the examples show (editorial photo, soft 3D render, flat
  illustration). Look at the example media before writing the prompt.
- Describe one panel from the family's **Panels** line; put its **Never**
  list in the prompt as negatives. No composites, tiles, pills or grounds
  in a prompt.
- Text: only the strings in the brief's `## Text in image` table, and only
  in the panel the table names. Quote each string verbatim in double
  quotes, then give its typographic role, position and one typeface, e.g.
  `the headline "50% OFF" in bold condensed white capitals across the top
  third; below the subject the smaller label "Buy now"`. Never paraphrase,
  translate or add words; the model's spelling is checked at the gate.
  Slots whose table is `none` get no text at all.
- End with ", no other text, no logos or watermarks". Never ask a model for
  UI, buttons, screens, pills or frames; when the family has chrome,
  `lp-compose` draws it.
- The generation model is `gemini-3-pro-image` for **every finished panel
  and tile**, with or without text. It is the default and it is not
  negotiable to save credits. `gemini-3.1-flash-image` is banned in a
  landing-page run unless the context strictly requires it, and the only
  contexts that qualify are (a) a composite's throwaway thumbnails
  (`thumb-a`, `thumb-b`), which are never a slot on their own, or (b) a
  brief that names flash explicitly for a stated reason. A short string, a
  gallery tile, or a cheaper-per-call price is **not** such a context — a
  gallery of finished cards is finished work and runs on the pro model.
  Whenever you use flash, record the qualifying context in the step's
  `reason`; a step on flash without one fails its own gate. Do not switch to
  a text-specialist model unless the brief says so.
- Resolution: 1K by default (1200 px covers every card and tile); 2K when the
  slot's natural width is over 1000 px; 4K only over 2500 px. `count: 1`
  always on `gemini-3-pro-image` (a second candidate is a second call).
- Faces and hands are the artefact hotspots. Prefer compositions that do not
  depend on them unless the examples do.

## Anchor to the corpus, then vary

The corpus examples in `examples/` and the `## References` genre are the
**spine, not a stencil**. Read them first and pull out the invariants — the
things that must hold for the asset to belong on this page: the finish
(editorial photo / soft 3D / flat illustration), the palette and light from
`shared-context.md`, the family's **Panels** and **Never** lines, the crop
class, and any string from `## Text in image`. Those are fixed; copying them
is the floor.

Everything the invariants do not pin is yours to move, and you should move
it. Give each slot its own subject treatment — a different angle, prop,
camera distance, secondary accent inside the palette, time-of-day within the
same light key, or compositional balance — so the set reads as one campaign
by a designer, not one prompt run N times. A gallery whose tiles differ only
by their headline string has under-used its freedom; vary the scene beneath
the string too. The test is: same family and finish across the set, no two
slots interchangeable. Never vary an invariant to be "creative" (a stray
extra word, a finish the family forbids, a palette off shared context) —
that is a gate failure, not variation. State the one thing you varied for a
slot in its step `reason`.

## Longer workflows: spend the per-slot headroom

The per-slot cap affords more than generate-and-stop. Once a panel passes
its gate, the default next move is to make it better, not to ship it:

1. **generate** `gemini-3-pro-image`, `count: 1` → gate.
2. **critique** the pass against the brief and examples in the step note —
   name the weakest concrete thing (soft subject, flat light, crop, a prop
   that fights the palette). If nothing is weak, stop; do not spend to spend.
3. **i2i refine**: `picsart_generate` with the pass in `imageUrls` and a
   prompt describing only that change → gate. Keeps the composition, fixes
   the flaw.
4. **variation pass** (series slots, or a hero the reviewer may choose
   among): one alternate take that holds every invariant and moves one
   varied axis, so there is a real choice, not a re-roll.

Every step is still preflighted, gated and recorded. Preflight the whole
planned chain before step 1 and stop if the quoted total exceeds the
section cap — depth is for quality, never a licence to overrun the budget.

## Gate checklist per step

fit to brief and annotation, and the composite carries the brief's
`Device:` (its panels and chrome, not a single panel where the device names
more); matches the family's **Panels** line and the
example finish; nothing from the family's **Never** list; every string
from `## Text in image` present, spelt and cased exactly, readable at the
slot size, and no other text; no logo or watermark; no artefacts; subject
placed for the slot's crop; palette consistent with shared context. A
wrong or extra word fails the gate: re-run the same step once with the
string repeated in the prompt; on a second failure drop that string, say
so in the note, and let the reviewer decide. Record pass/fail and the
chosen URL in the step.
