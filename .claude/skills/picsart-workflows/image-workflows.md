# Image workflows

Pick the board recipe that matches the slot, lay its nodes into
`workflow.yaml` from START to END (`workflow-format.md`), preflight, `lp-flow
check`, then run with a gate after each node. A recipe is a node shape on a
blank board; when `lp-flow templates` returns a gallery template that passes
the three tests in `flow-boards.md`, its shape replaces the recipe's and the
rules below still bind every node.

## Workflow philosophy: plan the whole board up front

A worker's board is not one call that ships whatever it returns, and it is not
a generate that grows a refine only when a gate happens to find a flaw. It is a
**multi-step recipe planned in full before the first call**: you look up the
slot's family recipe in `recipes.md`, lay every planned node into
`workflow.yaml` (the base generate, the i2i refine, the family's edit/compose
steps, the finishing upscale), preflight the whole board against the cap, `lp-
flow check` it, then run each node with its gate. Every planned node runs — the
refine and the finish are part of the plan, not a reaction to a bad pass. A gate
that fails re-runs *its own* node; it never decides whether a planned node
exists. `lp-flow check` enforces the recipe from the board's `family:` line, so
a shallow board does not wire. State what each planned node changed in its
`reason`.

"Layered", in the Picsart house style, is about the **finished picture**, not
about stacking many photos: a photographic base layer with a clean graphic
overlay laid over it — the panel-overlay / HSL family, where `lp-compose`
draws the control panel over a generated stock photo (`style-families.md`).
The worker iterates the photo layer toward final; the overlay layer is the
deterministic compose step. (Distinct from the `layered` recipe below, which
is the different job of seating one subject inside a generated scene.) Keep
both clean: depth of iteration, not a pile of elements.

## Board recipes

**direct**: for the hero or any slot with no shared context yet.
Board (planned whole): START → `image` generate → `image` i2i refine →
`enhance` → END; add a `vectorize` node when the subject is a logo/mark
(`recipes.md`).
1. generate `gpt-image-2.5-sunburst`, `count: 1`, `quality: high`, nearest ratio → gate. The
   prompt names the stock genre from the brief's `## References` (subject,
   light, backdrop, colour, framing) and keeps clear the area a chrome item
   will cover.
2. `image` i2i refine (planned, always): the base in `imageUrls`, a prompt
   describing only the improvement (tighter or fuller subject, cleaner light,
   fixed crop) → gate. A separate `edit` node (`picsart-qwen-image-edit`) is
   added on top when the gate names a surgical flaw (extra hand, stray object).
3. `enhance` (planned finishing upscale; ×2 when the slot is wider than 2000 px
   or the pick is soft).

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
node before the first call and scored after the last. `gpt-image-2.5-sunburst`
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
  → END. The flat-rate edit nodes carry no preflight quote; the guard prices
  them from a fixed table (`cutout`/remove_bg 0, `background`/change_bg 2,
  `enhance` 2, topaz 3) and allows them without a preflight, so a Route 2
  board runs a true cut. (i2i-harmonise on the subject's own render is still
  a valid cheaper variant when exact placement is not needed.)
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
briefed as. The worker generates the photographic panels only; `lp-compose` draws ground,
panels and chrome from the manager's composition plan. Do not run `--describe`:
the brief's `## Panels and keep-clear` table already lists every panel, the
ratio to generate it at, and the region each carries an overlay in, and the
manager has written `composition-<slot>.yaml` with the chrome items.
Board: START → one `image` node per panel (an `enhance`/`background`/
`cutout` node for a derived panel) → `compose` with `in:` every panel node
→ END.
1. one `picsart_generate` per row of the brief's `## Panels and keep-clear`
   table, `count: 1`, at the row's ratio, hero in `imageUrls` when anchored;
   thumbnails (`thumb-a`, `thumb-b`) on `gpt-image-2.5-sunburst` like every panel;
   the prompt describes the photograph only and keeps the subject clear of the
   row's keep-clear region (an overlay sits there) → gate: photo content only,
   subject inside the panel's crop and out of its keep-clear region, nothing
   from the family's **Never** list, thumbnails in the same finish and palette
   as the main panel.
2. before/after pairs are one photo: the after is `picsart_enhance`,
   `picsart_change_bg` or `picsart_remove_bg` (free; placed `fit: contain`)
   on step 1's URL, never a second generate; the result panel reuses the
   after URL with its own anchor.
3. fill the skeleton and build the compose spec — never hand-author the item
   list: pick one bank block per slot in `blocks-<slot>.yaml` (`blocks.md`;
   before any paid call) and `uv run lp-compose --check-blocks
   composition-<slot>.yaml blocks-<slot>.yaml`, then `uv run lp-compose
   --spec-from-plan composition-<slot>.yaml --blocks blocks-<slot>.yaml
   --image <panel>=steps/<slot>-<node>-1.png ... --out compose-<slot>.yaml`.
   You add only the panel image paths; the family, preset, ground and every
   chrome item come from the plan and your picks (never add, drop or edit an
   item in the spec — precheck diffs it against the picks). Then render and
   read it: `uv run lp-compose compose-<slot>.yaml --out
   steps/<slot>-<step>-1.png`, `Read` it → gate: every picked block present,
   in its slot, saying what the pick gave it; panels unstretched; each subject
   inside its panel; chrome legible at 480 px; no string appearing twice (once
   in the panel, once as chrome). Costs nothing, no preflight.

**Every block has a meaning, and a place only where it belongs.** A template
is a skeleton: its background (ground and fixed surfaces, never generated),
its panels (the only place a model's pixels go) and its slots, each taking
one block of the categories it accepts in its shape. The blocks live in the
bank (`compose/assets/blocks.yaml`), each with its category (state-label,
tool, attribution, comparison, spec, action, statement, derived, context,
editor), what it means and *when* it belongs. The brief lists each slot's
candidates — the blocks whose category, shape and hard context (the page's
own tool, the generating model's mark, two states for a Before/After, copy
strings) pass here — and you choose by the soft context: a candidate goes in
only when its *When* is true of this section, with a `because:`. An optional
slot nothing belongs in stays empty. `blocks.md` has the rules.

**Hybrid item (rare).** When the plan marks a chrome item `rendered_by: model`
— a `brush-mask`, `applied-mockup` or `face-box`, chrome too organic or bespoke
for `lp-compose` — render it inside one generate/edit node carrying
`chrome_item: <id>` and a `reason:`; the prompt names that item and nothing
else UI (the compose node then draws every other item, skipping this one). This
is the only case a model touches chrome; you never mark an item hybrid yourself
(the manager does, in the plan), and a model item never carries text. Gate:
the item is painted, matches its reason, no text, nothing else changed.

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
- The generation model is `gpt-image-2.5-sunburst` for **every image** — finished
  slot or composite thumbnail, with or without text. It is not negotiable to
  save credits: a cheaper per-call price, a short string, or a gallery of many
  tiles is never a reason to leave it. The one and only exception is
  truthfulness: a picture the page presents as a named model's output is made
  on that model. The brief's `## Model attribution` table (`made-by.yaml`)
  names it per panel — every picture on an `ai-models--<x>` page is x's; the
  two sides of a `compare-models--<a>-vs-<b>` vs-two-up are a's and b's; a
  model picker's panels are its ticked model's. Mark each such panel's final
  node `panel: <name>`; `lp-flow check` refuses any generate, edit or
  background node upstream of it on another model (a Nano Banana refine pass
  over a Recraft render makes it not Recraft's). A video model's page is
  illustrated by frames of its clips. When the section copy itself says a
  picture was made with `<model>` and no table covers it, generate it on that
  model and quote the copy in the step's `reason`. Otherwise use the pro
  model; any other model (Nano Banana included) is banned. Do not switch to
  a text-specialist model unless the brief says so.
- Quality: `high` by default (2 cr); `max` (7 cr) only where the copy claims
  detail or fidelity. Both return 1024 px on the short side (1024x1536 at 2:3,
  1536x1024 at 3:2), so `max` buys detail, never pixels. `count: 1` always on `gpt-image-2.5-sunburst` (a second candidate is a second call).
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

## The planned pipeline: every node authored before node 1

The recipe (`recipes.md`) is laid down whole before the first call, not grown
as gates fire. The standard pipeline for an image slot:

1. **generate** `image` node, `gpt-image-2.5-sunburst`, `count: 1` → gate.
2. **i2i refine** (planned, always present): an `image` node `in:` the pass,
   the pass in `imageUrls`, a prompt describing only the improvement (tighter
   or fuller subject, cleaner light, fixed crop) → gate. Name in its `reason`
   the one thing it improved; the refine still earns its gate, but its
   existence is fixed by the plan, not by whether the base looked acceptable.
3. **family edit / compose** as `recipes.md` names it (cutout, background,
   the after-edit for before-after, the `compose` chrome step).
4. **finishing enhance** (planned on full-bleed and cinematic-still, and any
   slot over 1000 px); **vectorize** last when the subject is a logo/mark.
5. **variation pass** (series slots, or a hero the reviewer may choose among):
   one alternate `image` node that holds every invariant and moves one varied
   axis, so there is a real choice, not a re-roll.

Preflight the **whole** planned board before node 1; if the quoted total
exceeds the section cap, drop the optional extras (a second refine, the
variation) in that order until it fits, but never the recipe's own planned
nodes — if the recipe floor alone exceeds the cap, stop and report. Every node
is preflighted, gated and recorded. `lp-flow check` (which the manager re-runs
in `precheck.py`) reads the board's `family:` and fails a board that skips a
planned step.

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
