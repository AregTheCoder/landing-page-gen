# Image workflows

Pick the board recipe that matches the slot, lay its nodes into
`workflow.yaml` from START to END (`workflow-format.md`), preflight, `lp-flow
check`, then run with a gate after each node. A recipe is a node shape on a
blank board; when `lp-flow templates` returns a gallery template that passes
the three tests in `flow-boards.md`, its shape replaces the recipe's and the
rules below still bind every node.

## Board recipes

**direct**: for the hero or any slot with no shared context yet.
Board: START → `image` → (`edit`) → (`enhance`) → END.
1. generate `gemini-3-pro-image`, `count: 1`, 1K, nearest ratio → gate: pass,
   or fix the prompt and regenerate (once, as a new node). The prompt names
   the stock genre from the brief's `## References` (subject, light,
   backdrop, colour, framing) and keeps clear the area a chrome item will
   cover.
2. `edit` node (`picsart-qwen-image-edit`) only if the gate named a
   concrete flaw (extra hand, stray object, wrong colour).
3. `enhance` ×2 if the slot is wider than 2000 px or the pick is soft.

**anchored** (default after the hero): same board as direct, but the prompt carries
the hero's light, palette and finish in words from `shared-context.md`
("hard even studio flash, seamless yellow and purple, glossy editorial
finish"). Pass the hero URL in `imageUrls` only when `shared-context.md`
already has one when you start and the slot is a Series member; then the
prompt also says what of the hero must not appear ("no rose, no vase").
Words keep the page reading as one campaign without waiting for the hero.

**product cutout**: for slots whose source media is a subject on a flat or
transparent background.
Board: START → `image` → `cutout` → (`background`) → (`enhance`) → END.
1. generate the product alone on a plain mid-grey backdrop.
2. `cutout` (`picsart_remove_bg`, free) → gate: clean edges, no halo.
3. either stop (transparent PNG) or `background` (`picsart_change_bg`) with
   the scene the brief describes → gate: subject scale and shadow are
   plausible.
4. enhance if needed.

**series**: galleries and tutorial-card thumbnails that must look like a
set. Board: START → `text` (the envelope) → one `image` node per member,
each `in: [envelope]` → END; the cross-slot gate is written on the envelope
node before the first call and scored after the last. `gemini-3-pro-image`
like every other finished slot — a gallery of finished cards is finished
work, not drafts. One prompt template on the text node with a slot-specific
subject phrase per member, hero as reference, `count: 1` per member (render
two, gate the envelope, then the rest). Gate: reject any member that breaks
the set (different finish, text, wrong framing, a different family or
ground variant from the brief); regenerate members singly as new nodes.
Members are the place to spend the per-slot headroom: after the set passes
as a set, revisit the weakest one or two with an i2i refine node and a
controlled variation rather than shipping the first pass.

**layered**: for a panel that must read as one photograph built from more
than one photographic element — a subject seated in a generated scene with
matched light, a contact shadow, right scale, no matte line (the pilot in
`runs/pilot-layered`, design in `research/layered-photos/design.md`). Two
boards; Route 1 is the default, Route 2 when a specific subject must land in
a specific plate.
- Route 1, model-native: START → `image` (one pass composing the whole
  scene; a subject that must stay identical enters as a REF in `imageUrls`)
  → (`image` i2i refine) → END. Best light coherence, least placement control.
- Route 2, cut and place: START → `image` plate (negative space where the
  subject sits, the key-light direction named) → `image` subject (plain
  backdrop, lit from the same named direction) → `cutout` → `image`
  harmonise (`in:` the plate and the cutout, both in `imageUrls`, a prompt
  that only seats the subject: contact shadow to the named side, match the
  warm light and the plate's grain, keep the subject identical) → (`enhance`)
  → END. `picsart_remove_bg` does not preflight-quote (the guard denies it
  in a run), so a Route 2 board without a quotable cutout harmonises the
  subject's own render instead of a cut.
- Harmonisation gate, every item: one key-light side across the elements;
  one colour temperature; a contact shadow whose direction and softness
  match the plate's own; no matte line or halo; scale, horizon and
  vanishing plausible; occlusion right; focus, grain and depth of field
  shared. A failure re-runs its own node (plate, subject or harmonise) as a
  new node, never the board. The `photo` panel of `template-mockup` and
  `dark-composite` may be built this way when the brief's annotation asks
  for a subject in a scene.

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
Board: START → one `image` node per panel (an `enhance`/`background`/
`cutout` node for a derived panel) → `compose` with `in:` every panel node
→ END.
1. one `picsart_generate` per distinct panel that `uv run lp-compose
   --describe <family>` lists for the brief's `Device:` variant (the plain
   template when the device is `none` or annotation-carried), `count: 1`, at
   its ratio, hero in `imageUrls` when anchored; thumbnails (`thumb-a`,
   `thumb-b`) on `gemini-3-pro-image` like every panel; the prompt describes
   the photograph only → gate: photo content only, subject inside the panel's
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
- The generation model is `gemini-3-pro-image` for **every image** — finished
  slot or composite thumbnail, with or without text. It is not negotiable to
  save credits: a cheaper per-call price, a short string, or a gallery of many
  tiles is never a reason to leave it. The one and only exception is
  truthfulness. When the section copy tied to the image explicitly states the
  image was generated by a specific named model — a model-showcase or
  compare-models page whose text says the picture was made with `<model>` —
  generate that one image with the model the copy names, so the demonstration
  is honest. Absent such copy, use the pro model; `gemini-3.1-flash-image`
  (and any other non-pro model) is otherwise banned in the run. When you match
  a named model, quote the exact copy that names it in the step's `reason`; a
  non-pro model without that quoted copy fails its own gate. Do not switch to
  a text-specialist model unless the brief says so.
- Resolution: 1K by default (1200 px covers every card and tile); 2K when the
  slot's natural width is over 1000 px; 4K only over 2500 px. `count: 1`
  always on `gemini-3-pro-image` (a second candidate is a second call).
- Faces and hands are the artefact hotspots. Prefer compositions that do not
  depend on them unless the examples do.

## Anchor to the corpus, then vary

The corpus examples in `examples/`, the widened neighbours beside them
(`w<n>-widened.md`, `origin: widened`: the same look found elsewhere on the
web by reverse image search, read for finish, light and framing, never
wired into a node) and the `## References` genre are the **spine, not a
stencil**. Read them first and pull out the invariants — the
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
its gate, the default next move is to add nodes that make it better, not to
ship it:

1. **generate** `image` node, `gemini-3-pro-image`, `count: 1` → gate.
2. **critique** the pass against the brief and examples in the node note —
   name the weakest concrete thing (soft subject, flat light, crop, a prop
   that fights the palette). If nothing is weak, stop; do not spend to spend.
3. **i2i refine**: an `image` node `in:` the pass, the pass in `imageUrls`
   and a prompt describing only that change → gate. Keeps the composition,
   fixes the flaw.
4. **variation pass** (series slots, or a hero the reviewer may choose
   among): one alternate `image` node that holds every invariant and moves
   one varied axis, so there is a real choice, not a re-roll.

Every node is still preflighted, gated and recorded. Preflight the whole
planned board before node 1 and stop if the quoted total exceeds the
section cap — depth is for quality, never a licence to overrun the budget.

## Gate checklist per node

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
