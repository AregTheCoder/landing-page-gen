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
   one image per panel with an anchor), run `uv run lp-compose
   compose-<slot>.yaml --out steps/<slot>-<step>-1.png`, `Read` it → gate:
   panels unstretched, each subject inside its panel, chrome legible at
   480 px, chrome text only the family's labels. Costs nothing, no preflight.

## Prompt rules

- Subject, setting, light, finish, camera, in that order. One sentence each.
- Name the finish the examples show (editorial photo, soft 3D render, flat
  illustration). Look at the example media before writing the prompt.
- Describe one panel from the family's **Panels** line; put its **Never**
  list in the prompt as negatives. No composites, tiles, pills or grounds
  in a prompt.
- End with ", no text or logos". Never ask a model for UI, buttons, screens,
  pills or frames; when the family has chrome, `lp-compose` draws it.
- Resolution: 2K by default; 4K only when the slot is over 2500 px wide.
- Faces and hands are the artefact hotspots. Prefer compositions that do not
  depend on them unless the examples do.

## Gate checklist per step

fit to brief and annotation; matches the family's **Panels** line and the
example finish; nothing from the family's **Never** list; no text/logo; no
artefacts; subject placed for the slot's crop; palette consistent with
shared context. Record pass/fail and the chosen URL in the step.
