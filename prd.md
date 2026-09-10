# PRD: landing-page-gen

## Problem

A landing page needs a dozen or more visuals that read as one campaign and
match how Picsart already presents itself. Producing them by hand, one
generation at a time, does not scale and loses the reasoning behind each
asset.

## Input

`runs/<run>/skeleton.md`: page frontmatter (brand, audience, defaults,
budget, notes), one H2 per section with all text and a `slot` block per
media node, annotations as blockquotes. Produced by `lp-corpus skeleton`,
edited by hand.

## Output

`runs/<run>/dist/index.html` with every `creative` and `thumbnail` slot
filled by a worker's accepted workflow result; `report.md` listing per slot
the workflow, credits quoted vs spent, review rounds and verdict; a complete
`workflow.yaml` and `result.md` per section.

## What "satisfactory" means

The rubric lives in the `picsart-workflows` skill (`evaluation.md`). Rules
below are lessons that reviews teach; each adds one line with the run that
taught it.

- Still-to-motion whose motion reshapes or reframes the picture needs a still
  with visible edges and margin (a print on a plain backdrop), not a
  full-bleed scene; a full-bleed still gives the video model nothing to move.
  (runs/dry-1 S01, review 1)
- Every video step states `generateAudio: false`, `async: true` and ends its
  prompt with ", no other text, no logos or watermarks"; the reviewer checks
  the yaml, not the intent. (runs/dry-1 S01, review 1)
- `resemblance` is scored against the family and its ground variant for the
  slot's class; a black composite where the corpus shows light grey is a 1.
  Examples for a blind trial are drawn with `--exclude-asset <source id>`,
  never by page slug alone. (2026-09-07, taxonomy round)
- Text in an image is generated only from the slot's `> text:` strings,
  which the manager derives from the section copy and the family's **Text**
  line; the worker quotes them verbatim and the gate reads every word. A
  string that fails twice is dropped and reported, not paraphrased.
  (2026-09-07, Areg's decision after runs/trial-3)
- Attribute labels are never guessed. `measure` writes only the fields the
  pixels settle; a sheet answer outside an enum is reported and dropped, and
  a cell a labeller cannot read is left out. A missing field costs a family
  tag; a wrong one corrupts every `similar --style` after it.
  (2026-09-07, no-API labelling round)
- A worker's "examples share finish X" claim must hold for every example it
  names; say which examples differ. (runs/dry-1 S01, review 1)
- Anything the call must carry (`async: true`, `generateAudio: false`) lives
  in the step's `params`, never only in its `note`; `params` is what is sent.
  (runs/dry-1 S01, review 2)
- Anchored takes light and palette from the hero; subject and composition
  come from the section's annotation and its examples. A detail callout is an
  edge-to-edge macro; the floating print is the hero's composition, not the
  page's. (runs/dry-1 S07, review 1)
- One finish instruction per prompt. When the annotation names a finish (flat
  3D render), the shared context contributes light and palette only; two
  finishes in one prompt is a rework. (runs/dry-1 S08, review 1)
- A set of card thumbnails shares one prompt envelope (container, backdrop,
  shadow, light) with the slot subject as the only variable, and a cross-slot
  gate that rejects any member that breaks the set. (runs/dry-1 S11, review 1)
- A gate with `count` > 1 says how the pick is made, has a failure branch, and
  when lp-inject will crop the output it checks that the subject sits inside
  the slot's safe band. (runs/dry-1 S06 and S08, review 1)
- Thumbnails under about 400 px go to `gemini-3.1-flash-image` at a native
  ratio (5:4 exists there, 3 credits) rather than the pro model cropped; pro
  fidelity is invisible at that size. (runs/dry-1 S11, round 2)
- `gemini-3-pro-image` with `count: 2` returned one image and charged for two
  (10 credits, twice). Use `count: 1` and re-run for a second candidate; the
  ledger, not the response, says what was paid. (runs/trial-1 S07)
- The look of a tool-page image is its style family
  (`picsart-workflows/style-families.md`), not its copy or alt. The skeleton
  names the family per slot (`> style:`), the brief carries the family
  block, `similar --style` picks same-family examples. A physical still
  life where the family is a flat composite is a `resemblance` 1.
  (runs/trial-1 S07)
- Composite slots: the worker generates the photographic panels only;
  ground, panels and chrome come from `lp-compose` with the family template,
  so `clean` is scored on the panels and chrome text is limited to the
  family's labels (Before, After, x2, 4K, a size). (runs/trial-1 S07)
- `similar --exclude <page>` is not enough for a blind trial: sibling pages of one
  CMS block share the source image. Grep the brief for the source asset id and
  swap those examples out by hand. (runs/trial-3 S09)
- "Omni" in the Picsart catalog is video-only (Gemini Omni, Kling V3 Omni). An
  image from it is one frame of a 3 s static-camera clip (9 credits at 720p)
  grabbed with `FrameGrabber`; a 9:16 frame in a near-square panel needs an
  explicit compose `anchor`. (runs/trial-3 S09)
- A video frame is a finish tier below a native image generate for a panel:
  720p into a 740 px panel leaves no headroom, and the 9:16 to near-square
  cover crop discards half the height, so a 25 % margin in the frame is ~7 %
  in the panel. A frame-grab gate measures margin after the crop and detail
  at 100 %, not just "no motion blur". (runs/trial-3 S09, review 1)
- A re-run to fix one flaw changes one variable. Fighting margin with
  "photographed small, from a distance" shrank and de-centred the subject;
  "one single fern, nothing else in the pot" would have fixed the species
  mix and left the framing alone. (runs/trial-3 S09, review 1)
- A gallery whose copy is "Featured In" and whose alts are publication names
  is a press-logo strip: its tiles are `decorative` and kept from source, never
  generated. (runs/live-1 S05, manager relabel)
- The `count: 1` rule for `gemini-3-pro-image` must reach the worker through
  the skill or the agent definition, not prd.md; the S01 worker read the skill
  only and paid 20 for two candidates. (runs/live-1 S01, review 1)
- An `imageUrls` anchor carries the hero's subject as well as its light. An
  anchored prompt says what of the hero must not appear ("no flowers, no rose,
  no vase"). (runs/live-1 S03-m3, worker gate)
- A Series writes its cross-slot gate in `workflow.yaml` before the first
  call and scores it after the last; per-slot gates let a dark member ship
  beside three daylight siblings. (runs/live-1 S03-m4, review 1)
- A `full-bleed` tag on a class whose sheets are unanswered is a missing
  label, not a finding: the measurer reads a photo with a dark panel over it
  as `photo-full-bleed / single`. Before briefing a class from the corpus tag,
  check that its assets have `chrome` answered. (research/live-1-style-gap)
- Adjustment-tool pages (hue, saturation, colour, curves, filter) show a stock
  fashion photo with the tool's panel laid over it, never a plain photo whose
  subject "looks edited": brief `panel-overlay`, describe the stock look (one
  person, one bold garment colour or a flat coloured backdrop, hard even
  light), and leave the edit to the chrome. (research/live-1-style-gap)
- Picsart's creatives are stock photographs (the hsl-color hero is Pexels
  2180474 by R. Fera) plus compose chrome; a photo prompt should name the
  stock genre ("Pexels colourful fashion") rather than the section copy's
  example objects, which the originals ignore. (runs/trial-4)
- A generate whose result cannot be saved to Picsart Drive fails after the
  render with `failure_space_limit_reached` and is not charged; pass
  `saveToDrive: false` when Drive is full. (runs/trial-4)
- Hooks are cwd-relative: a `cd` in a Bash call moves the shell for every
  later call, and the next preflight is not logged, so the credit guard has
  no quote. Use absolute paths, never `cd`. (runs/trial-4)
- A family's chrome does not travel with its photography. hair-color-changer
  shares panel-overlay's stock portraits and tilted-card ground but carries no
  panel, and its hero is a sticker collage; brief the ground and the photo
  from the family, and the chrome only when the page's own cards show it.
  (runs/trial-5)
- The paid calls are a tenth of a run's clock; the rest is briefing, review
  rounds and rework. A worker or reviewer that loads the whole skill reads
  40 KB of families it does not need; a brief with twelve example images
  costs more than the render it asks for. Load the companions the role
  needs, one image per example at 480 px, one render read per gate.
  (runs/live-1, timing from ledger.jsonl)
- Paperwork is not a review. A missing preflight row, `count: 2` or an empty
  gate is caught by `precheck.py` and fixed by one message to the worker;
  the reviewer looks at pixels, once per wave, for every section at once.
  (runs/live-1 S01, round 2 was record-only)
- Anchoring is words first. The hero's light, palette and finish written into
  `shared-context.md` from the skeleton let every section start together;
  the hero URL is an optional `imageUrls` for a Series that has not yet
  rendered. (runs/live-1: 7 idle minutes between waves; runs/trial-4 and
  trial-5 landed the look without an image anchor)

## Non-goals

- Writing or rewriting page copy.
- Generating product UI screenshots, icons or decorative brand assets.
- Drawing panel chrome (tiles, pills, brackets, checkerboards) and the
  labels bound to it with a generative model; `lp-compose` draws them.
- Inventing copy for an image: picture text comes from the section's own
  copy via `> text:`, or the slot carries none.
- Producing the production Next.js page; the output is a snapshot.

## Budget

Default run cap 300 credits, enforced by hook. Per-slot caps are advisory
(image 20, video 60) and reviewed against the ledger.
- A corpus `full-bleed` tag on an ai-models callout or hero is trusted only
  when that asset's `chrome` attribute is answered; unanswered, the slot-class
  row default (`dark-composite`) stands. Sibling pages of one CMS block share
  the same unanswered measurement, so their agreement proves nothing. The
  four Recraft callouts and hero are black composites with a mark tile and an
  SVG chip, briefed as full-bleed. (runs/live-2 S01/S04/S05/S07, manager)
- Gallery 9:16 tiles fill the frame: the subject at 80 to 100 % of the tile
  height on a saturated solid ground that changes per tile, one illustration
  style across the set. "Centred with generous margin" is a callout-panel rule
  and yields an under-filled, pale gallery. (runs/live-2 S03, against the original)
- A gate names the visual test, not a ratio the model cannot target: "row gap
  smaller than the outer margins" decided S05 where "row gap under 1.5x the
  column gap" failed a better render. (runs/live-2 S05, review 2)
- A Series worker that gates every member serially is the run's long pole;
  render two members, gate the envelope, then the rest in parallel calls.
  (runs/live-2 S03: 18 min of a 34 min run)
- A corpus tag is only as good as its inputs: the skeleton's `> attrs:` line
  says `chrome=unanswered` when the family came from the pixels alone, and a
  pre-filled `> style:` on a slot class that lists chrome families is then the
  manager's to decide from the slot-class row. (runs/live-2 S01/S04/S05/S07,
  post-run audit)
- Blindness is checked, not assumed: `--exclude-asset` takes one id per slot
  of the whole page (the uuid prefix of `src`), briefs carry no `source:` or
  `snapshot:`, and `blindcheck.py` must pass before a worker is spawned. In
  live-1 and live-2 the exclusions were no-ops (single-scalar flag, wrong id)
  and S09's examples were the page's own thumbnails. (runs/live-2, audit)
- Card-sized images in hero, feature-callout and use-case-grid sections are
  creatives whatever their alt says; "logo" and "how ... works" in an alt
  demote only small images and videos. Two live-2 creatives were kept from
  source as `decorative` and `ui-screenshot`. (runs/live-2 S06/S08)
- Every run ends with `lp-bench`: generated vs original per slot (family,
  ground, coverage, saturation) with rubric-keyed flags, written before anyone
  opens an original. (runs/live-2, 38 flags on 16 slots)
- A composite's chrome must be visible on its ground: `dark-composite` tiles
  are `#1c1c1e` on the black card, never the card's own black, or only the
  glyphs show. Check a composite at 100 % for chrome edges, not just the
  panel. (runs/live-3 S01/S04/S05, review 1)
- Grounds are assigned per slot, for composites as for gallery tiles: a shared
  context that lists eight colours and assigns none yields four cards on one
  cobalt. (runs/live-3 S01/S05/S06/S07, review 1)
- After two crop-wording retries the lever is the pose or the subject, not
  more wording: the third S03-m4 call gained 0.6 points of fill and added
  three artefacts. (runs/live-3 S03, review 2)
- A brand mark on a prop is fixed with the targeted-edit pattern
  (`picsart-qwen-image-edit`, 4 credits, "remove every printed letter ...
  change nothing else"), not with another generate that gambles on a new
  spot; name every prop class in the edit prompt (pencils, brushes, loose
  pencils). (runs/live-3 S09-m3, rounds 2-3)
- A reviewer spawn gets about four sections in 30 turns only when told to
  budget one Read per asset and skip examples already scored; without that it
  can spend all 30 turns reading and write nothing. (runs/live-3 review 1 B)
- The bench's coverage metric counts width as well as height: originals that
  cut the figure at the frame edge score higher than whole figures at full
  height; brief galleries "cropped by the frame" when the originals are.
  (runs/live-3 S03, benchmark)
- A composite demonstrates the section's claim, not only its family: the
  family gives the look, the `> device:` line gives the narrative (references
  beside the output, a set, two outputs, a chosen row, the output applied),
  and `fit` is scored against that claim and gated at 4. live-3's composites
  scored `fit` 5 while every original showed a device ours lacked.
  (runs/trial-6 against runs/live-3, 2026-09-09)
- The manager reads the example images for the device before writing the
  brief: live-3's hero examples showed two reference thumbnails and the
  reviewer wrote them off as "the template as briefed". (runs/live-3 S01,
  trial-6 step 1.7)
- Two steps that share one prompt (a Drive-full failure and its re-run) hold
  one set of ledger rows; a paperwork check sums the ledger over distinct
  prompts, not over steps. (runs/trial-6 S04, precheck)
- The SubagentStop hook may be handed a transcript holding every worker's
  assignment; with more than one assignment it cannot tell whose stop it is
  and must not block, or every worker is judged as the first one spawned.
  (runs/trial-6, all five workers blocked once as S01)
- A `saveToDrive: false` re-run is a new preflight as well as a new step: the
  params differ by that flag, and a re-run that reuses its parent's quote has
  no row of its own. (runs/trial-6 S01, review 1 record note)
- On a template/card-maker page (birthday-card, greeting-card, invitation), the
  gallery originals are designed card thumbnails and the callouts show finished
  cards, not photographs: brief the gallery as `full-bleed` with a per-tile
  headline and the callouts as `template-mockup`. Pin "flat 2D illustration,
  fills the frame edge to edge, no surface, no table, no drop shadow, no
  card-object" in the annotation — without it the model photographs the card as
  an object on a surface (8 of 15 tiles, runs/live-4 S05 first round; all three
  callout first attempts read as printed-card/book-cover mockups).
- Every image is `gemini-3-pro-image` — finished slot, gallery tile, and
  composite thumbnail alike. The only exception is truthfulness: when the
  section copy tied to the image explicitly says the picture was generated by
  a specific named model (a model-showcase or compare page), generate that one
  image with the model the copy names and quote that copy in the step; absent
  such copy, pro model always. A cheaper price, a short string, or many tiles
  is never a reason — live-4 ran 15 finished gallery tiles on flash under a
  clause meant for composite thumbnails, and a model-less `series` pattern.
- Corpus examples are the spine, not a stencil: hold the invariants (finish,
  palette, light, the family's Panels/Never, crop, the exact text strings) and
  vary everything else per slot (angle, prop, distance, accent, composition) so
  no two slots are interchangeable. A set that differs only by its headline
  string has under-used its freedom; varying an invariant is a gate failure,
  not variation.
- With the per-slot cap at 40 the default is depth, not one-shot: after a
  panel passes its gate, critique it and, if a concrete flaw is named, i2i
  refine (pass in `imageUrls`) and add one variation candidate — each step
  preflighted and gated, the whole chain preflighted before step 1 so depth
  never overruns the section cap.
