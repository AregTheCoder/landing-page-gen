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
set. One generate with `count` 4–6, one prompt template with a slot-specific
subject phrase, hero as reference. Gate: reject any member that breaks the
set (different finish, text, wrong framing, a different family or ground
variant from the brief); regenerate members singly.

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
- Text and the default model: `gemini-3-pro-image` renders short strings
  reliably; `gemini-3.1-flash-image` is acceptable for one string of one
  or two words. Do not switch to a text-specialist model unless the brief
  says so.
- Resolution: 1K by default (1200 px covers every card and tile); 2K when the
  slot's natural width is over 1000 px; 4K only over 2500 px. `count: 1`
  always on `gemini-3-pro-image` (a second candidate is a second call).
- Faces and hands are the artefact hotspots. Prefer compositions that do not
  depend on them unless the examples do.

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
