# Image workflows

Pick the pattern that matches the slot, write every step into
`workflow.yaml`, preflight, then run with a gate after each step.

## Patterns

**direct**: for the hero or any slot with no shared context yet.
1. generate `gemini-3-pro-image`, `count: 2`, 2K, nearest ratio → gate: pick
   one or fix the prompt and regenerate (once).
2. targeted edit (`picsart-qwen-image-edit`) only if the gate named a
   concrete flaw (extra hand, stray object, wrong colour).
3. enhance ×2 if the slot is wider than 2000 px or the pick is soft.

**anchored** (default after the hero): same as direct, but step 1 passes the
accepted hero URL in `imageUrls` and the prompt says "same lighting, palette
and finish as the reference; new subject: ...". Keeps the page reading as one
campaign.

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
set (different finish, text, wrong framing); regenerate members singly.

**composite**: when the brief's `## Style family` block lists chrome
(`style-families.md`). The worker generates the photographic panels only;
`lp-compose` draws ground, panels and chrome. `uv run lp-compose --describe
<family>` prints the panels and the `aspectRatio` to generate each at.
1. one `picsart_generate` per distinct panel named under **Panels**,
   `count: 1`, at its ratio, hero in `imageUrls` when anchored; the prompt
   describes the photograph only → gate: photo content only, subject inside
   the panel's crop, nothing from the family's **Never** list.
2. before/after pairs are one photo: the after is `picsart_enhance`,
   `picsart_change_bg` or `picsart_remove_bg` (free; placed `fit: contain`)
   on step 1's URL, never a second generate; the result panel reuses the
   after URL with its own anchor.
3. write `compose-<slot>.yaml` (family, `size` = the slot's natural size,
   one image per panel with an anchor; `omit:` any chrome item whose text
   the model rendered instead, e.g. `omit: [headline]` for
   `template-mockup`), run `uv run lp-compose compose-<slot>.yaml --out
   steps/<slot>-<step>-1.png`, `Read` it → gate: panels unstretched, each
   subject inside its panel, chrome legible at 480 px, chrome text only
   the family's labels, no string appearing twice (once in the panel, once
   as chrome). Costs nothing, no preflight.

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
- Resolution: 2K by default; 4K only when the slot is over 2500 px wide.
- Faces and hands are the artefact hotspots. Prefer compositions that do not
  depend on them unless the examples do.

## Gate checklist per step

fit to brief and annotation; matches the family's **Panels** line and the
example finish; nothing from the family's **Never** list; every string
from `## Text in image` present, spelt and cased exactly, readable at the
slot size, and no other text; no logo or watermark; no artefacts; subject
placed for the slot's crop; palette consistent with shared context. A
wrong or extra word fails the gate: re-run the same step once with the
string repeated in the prompt; on a second failure drop that string, say
so in the note, and let the reviewer decide. Record pass/fail and the
chosen URL in the step.
