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

Default run cap 600 credits, enforced by hook. Per-slot caps are advisory
(image 40, video 60) and reviewed against the ledger.
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
- A slot's workflow is a Picsart Flow board: START, nodes each of one Flow
  kind on one engine and one model, END, wired by `in:`. Blank board by
  default; a gallery template only when its `fits` names the family and
  device, its shape covers every panel, and it moves no invariant — then the
  record names the template and what was adapted. The board is checked
  (`lp-flow check`) before the first call and rendered (`lp-flow sheet`) as
  the node sheet a person could rebuild on the Flow canvas. (2026-09-10,
  Areg's decision after the Flow analysis)
- Example, stock, pool and widened images are read, never wired: no URL from
  `examples/`, `corpus/references/`, `corpus/pool/` or `corpus/widened/`
  enters `imageUrls`, `startFrame` or `image`. The only REF a board takes is
  what the brief allows. Their licence is not ours (the pool's is known but
  still not a generation input) and the corpus is the look's spine, not its
  material. (2026-09-10)
- The look-corpus has four tiers with four uses: Picsart's own pages
  (layout and chrome; `similar`), licensed stock references (the photo
  genre; `## References`), the stock pool (kept Pexels/Unsplash photos,
  deduped by perceptual hash, served rotated by `similar --pool --seed`),
  and widened neighbours found by reverse image search on the corpus images
  (`lp-corpus widen`; more views of the same look, unknown licence, look
  only). A brief may carry all four; the last is searched by the pictures
  themselves, the others by words. (2026-09-10, pool added 2026-09-10)
- Pool variety comes from rotation, not volume: a brief keeps 2 corpus
  examples and at most 2 pool images, and the `--seed <run>` shuffle is what
  changes between runs. More images per brief cost more than they teach
  (plan.md 2026-09-08). (2026-09-10)
- Review is spawned per section (up to 3 that clear precheck together), the moment a worker passes precheck, not once for the whole wave at the end: review overlaps the running wave and no spawn approaches its turn limit. Supersedes the earlier reviewer-size caps (~4 sections in live-3, ~6 in showcase-1), which existed only because one spawn had to carry the whole wave (showcase-1: the 12-section spawn read everything and wrote nothing). (2026-09-11)
- Check Picsart Drive headroom before a run with derivative families (before-after, cutout-checkerboard, crop-frame's change_bg route): enhance/remove_bg/change_bg have no saveToDrive:false, so a full Drive blocks every after/cutout panel (showcase-1 S05, S08).
- An aspect the generate enum cannot quote (3:2) is generated at the nearest enum and delivered with a recorded centre-crop, never silently stretched (showcase-1 S12).
- The flat-rate edit tools (remove_bg 0, change_bg 2, enhance 2, topaz 3) cannot be preflight-quoted (preflight is generate-only), so the credit guard prices them from a fixed table (`_ledger.FIXED_PRICE`) and allows them without a preflight, counting the fixed cost against the run cap. This unblocks a true Route 2 cutout in the `layered` pattern; a generate model still needs its preflight. (2026-09-11, pilot-layered blocker resolved)
- `library/` is a derived, gitignored view of the corpus, rebuilt by `lp-corpus organise`; nothing in it is hand-edited (labels go through the sheets, everything else lives in attributes.yaml/styles.yaml/sections.md). Relabel -> regenerate -> an asset moves folder. (2026-09-14)
- `structure` (taxonomy.structure_of) is computed on read, not stored; its `single-picture`/`measured` bucket over-collects composite cards with transparent corners until their chrome is labelled — read `structure_source` for the confidence. (2026-09-14)
- Model-page galleries are reused under other models' headlines (7 pages), so a page-set alone can be ambiguous: a "made with X" headline is asset-level truth and a strict upgrade of the page set; two headlines conflict and the asset is `general`. Link-grid / tutorial-grid / resource-links thumbnails on model pages depict other pages and are never model evidence. (2026-09-14)
- A family tag whose `chrome` is unanswered is `provisional` (`styles.derive`): it may be a composite the measurer read as full-bleed. `similar` re-ranks so a verified (chrome-answered) same-family example outranks a provisional one, and outranks a text-only BM25 hit — retrieval serves the closest CORRECTLY-built example, not the closest section copy. (2026-09-14)
- Each corpus example in a brief now carries a `built:` field (its measured ground/layout/panels/chrome/art_style/structure) so the worker anchors on construction, not the 480px thumbnail; an example with no `built:` is unlabelled and its pixels are trusted less. (2026-09-14)
- The bench→data loop is closed: `lp-corpus feedback <run>` reads a run's `[resemblance]` family-mismatch flags, and for each original whose family is provisional (chrome unanswered) queues it in `corpus/labels/_relabel_queue.yaml`; `sheets.build` lays those suspect originals out first. A finding fixes the data, not only a prose rule. (2026-09-14)
- A slot's board is a PLANNED recipe, not a reactive one. Each family has a mandatory node pipeline in `picsart-workflows/recipes.md` (generate → i2i refine → the family's edit/compose → finishing enhance; + vectorize for a logo/mark), authored whole and preflighted before node 1. `lp-flow check` reads the board's `family:` line and fails a board that skips a planned node, so a lone-generate board no longer wires. Reactive depth ("add a refine only when a gate names a flaw") collapsed workflows to single generates whenever pass 1 looked acceptable (runs/page-logo-maker: 8 slots, ~1 paid node each). (2026-09-14)
- Picsart Drive fills up and then `picsart_enhance`/`change_bg`/`remove_bg` 403 ("storage limit reached") with no `saveToDrive` override, which hard-blocks any recipe ending in enhance — and, for video slots, the whole i2v chain (the still→enhance→startFrame dependency). The working substitute is the identical `topaz-upscale-image` model via `picsart_generate` with `saveToDrive:false` (same engine and cost). No Drive deletion is needed. Two follow-ups: `lp-flow check`'s NODE_ENGINES should accept topaz-via-generate for the `enhance` kind (it currently flags "enhance node on picsart_generate"), and `_ledger.FIXED_PRICE` should price it on the generate path (preflight returns null there, so the ledger under-counts ~3 cr/upscale). (2026-09-15, live-5)
- The 80-turn subagent cap is too low for a section with 8–10 tiles or for an async video slot; such workers stop mid-way ("stopped at its 80-turn limit"). When SendMessage is disabled the manager cannot resume them in place and must re-spawn — and a soft turn-limit checkpoint is NOT proof the agent is dead, so re-spawning a resume while the original is still running produces duplicate paid renders (live-5: ~190 of 902 credits was S06/S03 orphaned seedance-2.5 finals). Confirm death before re-spawning; shard multi-tile sections per-tile or raise the worker turn budget; and have video workers persist the async clip URL to workflow.yaml the instant `picsart_job_status` returns it, before download, so a turn-limit stop never orphans it. (2026-09-15, live-5)
- On a character/persona-generator page, favour the photo families (cinematic-still, full-bleed) over the corpus's composite tags where the slot-class default allows: the composite tags (cutout-checkerboard, mockup-card, prompt-card) rest on unanswered/mismatched chrome and would fabricate UI the page's real creatives don't carry. live-5 overrode S05/S11 to full-bleed and briefed S10 as dark-composite; family match 0.90 (vs 0.61 on the composite-heavy live-2/3). (2026-09-15, live-5)
- Compose templates must match a family's MODAL corpus layout, not one exemplar. A 2026-09-15 audit (research/template-audit/) of all six lp-compose templates vs their tagged corpus assets found every one was measured off a single hand-picked asset and generalised: dark-composite matched 0/13 (column on the wrong side, invented "4K" chip, missing magenta accent), template-mockup 1/14 (opaque-white ground vs transparent; 4 uniform tiles vs 3 mixed; blank headline bars that occur in 0/14), before-after encoded the rarest layout (1/20; modal is a wide 2.1:1 card), crop-frame the ground was black-not-white and the source is dimmed, cutout-checkerboard the ground is transparent-not-black. Four of six paint an opaque ground that is actually transparent (the page supplies the surround); the likely cause is an RGBA→RGB read making a transparent gutter look black. Standing rules now in research/template-audit/STANDARD.md: template the modal (≥10 sampled+viewed assets), measure ground from alpha, cite a living asset per chrome element, re-derive style-families Examples from styles.yaml, clean noisy tag populations before trusting counts. Corrected defaults + ground fixes are in families.py (each re-rendered and eyeballed); richer variants (crop-grid, /editor, partial-fill checker, compare-labels) are specified but deferred. (2026-09-15)
- Evidence rot: several templates and style-families Examples lines were built on assets that were later re-tagged to other families (dark-composite's 4eeca13c/86f73fc9 → full-bleed; template-mockup's 21cdafd9 → dark-composite), and nothing re-checked the template when its evidence moved. A cited asset id that is no longer tagged its family should fail a test. (2026-09-15)
- taxonomy.family_of over-fires on several families: ~half of crop-frame's 58 tags are pastatic designed-template mockups; 17 of before-after's are compare VS cards; 4/13 sampled cutout-checkerboard and 21/28 panel-overlay tags are other designs. Family counts are not trustworthy until a /label-corpus pass cleans these. (2026-09-15)

- The pool ranker orders candidates by fidelity to the family's own
  photography — the nearest cluster of its tagged corpus stills, gated by
  aspect ratio — never by subject alone, and never by the family's chrome:
  tiles, pills, panels and badges are drawn by `lp-compose` afterwards, so a
  bare photograph is what a reviewer judges. Its auto-drop threshold is set
  only from agent keep/drop answers, at ≥ 95% recall of what they kept, and
  always with a 10% exploration slice so the threshold stays falsifiable.
  CLIP is an optional extra (`uv sync --extra embed`); without it the
  histogram ranker orders the sheets and nothing is auto-dropped. (2026-09-16)
- Every pool entry carries a controlled licence key (`stock.LICENCES`) and
  `attribution_required`; a candidate whose licence is not one of them never
  enters the pool at all. A candidate is scored against all fifteen families
  and lives in exactly one family yaml — the searched one unless it is gated
  out or clearly beaten, and a reviewer's `best_family` moves it rather than
  losing it. (2026-09-16)
- Pool traffic is free-tier only (Pexels, Unsplash, Pixabay), cached and
  capped in code: zero credits, zero spend. The `hooks/` guards see MCP tool
  names only, so they cannot see, pace or ledger an `lp-corpus` HTTP call —
  `apiclient`/`ledger` are that guard, and `--dry-run` is how a sweep is
  costed before it is run. (2026-09-16)
- The cost of an agent role is **context × turns**, not bytes: cache-read is
  70–85% of every role's bill, so a file (or an image, or a skill companion)
  read once is paid for on every later turn of that agent. Optimise by cutting
  turns (bounded polling, a higher turn cap so a section finishes in one spawn)
  and per-turn context (a deterministic `brief.py` so the manager stops reading
  style-families.md/slots.json/examples in the wave; the reviewer reads
  workflow.yaml not flow.md). `lp-tokens <run>` measures it from the session
  transcript. (2026-09-16)
- Poll an async video job by its own estimate, not by spinning: record the job
  handle the instant generate returns, then at most three `job_status` per clip
  with one `sleep` of `progress.estimatedSecondsLeft` between — ten bare polls
  are ten turns, a sleep-and-check is one. (2026-09-16)
- `precheck.py` owns the credit reconciliation (spent vs the ledger rows, by
  prompt); the reviewer checks only the advisory cap and never greps the ledger
  (it was 40 of 122 reviewer turns in live-5). (2026-09-16)
- Parse the corpus YAML with the libyaml C loader/dumper (`styles.LOADER/
  DUMPER`, shared via `load_yaml`/`dump_yaml`) and index `media(src)` /
  `media(section_id)`: the two together take a maintenance command's YAML+DB
  cost from ~12s to under 1s. YAML stays the single committed form. (2026-09-16)
- `pool search` is breadth-first with two early-stops (`deepen`'s keep-floor and
  `YIELD_FLOOR`) that end a term after page 1 once its page-1 admittable photos
  are already held — so once every family's curated terms are page-1-exhausted
  the pool plateaus and neither `--pages` nor `--keep-floor` pulls anything new.
  To grow it: `--deep` (opt-in; pages every term to full `--pages` depth, keeping
  only the short-page and per-term-cap stops) and/or more `search_terms`. `--deep`
  trades relevance for volume; the calibrated threshold and review still curate.
  A term has ~5–7 real Pexels pages before it runs out. (2026-09-17)
- Playwright's `route.fulfill(path=)` serves a local clip without byte ranges, so
  Chromium reports `seekable [0, 0]` and every `currentTime` seek snaps to 0:
  the 286 "t=1 s" poster frames grabbed from local files were frame 0, and five
  seeks in one load gave five copies of it (motion measured exactly 0.0 on real
  clips). `similar._ranged_route` answers Range requests with 206 +
  Content-Range; CDN URLs always seeked fine. A frame after a seek is read by
  drawing the video onto a canvas and screenshotting the canvas (the element
  screenshot repaints the previous frame; `toDataURL` is refused on a tainted
  canvas). Measure a video's motion on frames, and check that the frames differ
  before trusting a number. (2026-09-19)
- A video is context only when its motion is: a poster frame tells a worker
  the look and nothing about what moves. Every corpus clip now carries measured
  `pace`, `loop`, `loop_seam`, `duration` (and `camera: static` when the frame
  holds) plus sheet-labelled `motion_kind`/`camera`; briefs get clips as
  first/middle/last strips (`similar --kind video`) and the family's
  **Motion:** line; workers and reviewers gate a clip on its strip
  (`lp-corpus frames`), never on the URL or the worker's `note:` (live-5's
  reviews paraphrased the worker). (2026-09-19)
- Duration is faithful to the original: live-5 shipped 5 s clips against
  10–34 s originals and nothing flagged it. The skeleton's `> duration:` line
  (the original's length) becomes the brief's target, `seedance-2.5` takes
  `duration: <target>` up to 30 s (extend beyond), `precheck.py` flags a final
  off the target, `lp-bench` flags `[duration]` outside 0.9–1.1 and `[loop]` when
  the original loops and the clip does not (live-5 re-benched: 4 duration and 3
  loop flags on 5 clips). Preflight `duration` > 5 s: its price is not in
  tool-map.md yet. (2026-09-19)
- `picsart_job_status` is hooked (PostToolUse): the clip URL an async generate
  never returns lands in `ledger.jsonl` at cost 0, so the isolation guard can
  admit an extend/edit node that wires it and `precheck.py` can require every
  done video node's URL to be in a job_status row and name extra seedance rows
  beyond the board's nodes (the orphaned finals). Workers write the URL into the
  node's `outputs` the instant it arrives, before the download. (2026-09-19)
- A generated video ships with its poster: `result.md` carries `poster:` (the
  accepted still) and `duration_s:`, `lp-inject` fits the poster like an image,
  sets it and writes `muted autoplay loop playsinline` instead of only dropping
  the snapshot's poster. The corpus reads `data-lp-poster` into `media.poster`
  (406/607 clips ship one) and `attrs` prefers that designer poster over a
  grabbed frame. (2026-09-19)
