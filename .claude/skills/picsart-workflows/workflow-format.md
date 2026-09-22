# workflow.yaml format: one Picsart Flow board per slot

One YAML document per slot, `---` separated, in the section folder. Written
in full before the first paid call; updated after every node runs. The
document *is* a Picsart Flow board (`flow-boards.md`): `start:` is the START
node, every `steps:` entry is one node on the canvas with the kind Flow gives
it and the nodes it is wired from, `final:` is the END node. `uv run lp-flow
check workflow.yaml` says whether it wires; `uv run lp-flow sheet` renders it
as the node sheet a person would rebuild in the Flow editor.

```yaml
slot: S03-m1
kind: image
board: blank                      # blank (default) | template
template: null                    # board: template only, see below
pattern: anchored                 # the board recipe from image-workflows.md
target: {size: 1440x810, aspect: "16:9", generate_ratio: "16:9"}
models: {primary: gemini-3-pro-image, reason: default}
start:                            # START: what enters the board
  inputs:
    - {id: ref-hero, kind: ref, url: "https://.../hero.png", use: "light and palette only"}
  text: ["50% OFF"]               # the brief's ## Text in image strings, verbatim
steps:                            # the nodes, in wiring order
  - id: 1
    node: image                   # Flow node kind: text | ref | image | edit | cutout | background | enhance | video | motion | compose
    in: [start]                   # the nodes this one takes its input from (start, or earlier ids)
    tool: picsart_generate
    model: gemini-3-pro-image
    params:
      prompt: "..., the headline \"50% OFF\" in bold white capitals across the top third, no other text, no logos or watermarks"
      aspectRatio: "16:9"
      resolution: 2K
      count: 1
      imageUrls: ["https://.../hero.png"]
    quoted_credits: 5
    gate: "product centred, \"50% OFF\" spelt exactly and no other text, palette matches hero"
    reason: ""                    # what this node varies or why it exists; required on any image node off gemini-3-pro-image
    status: pending               # pending | done | failed | skipped (dry run)
    outputs: []                   # URLs, filled after the call
    passed: null                  # URL that passed the gate, or null
    note: ""                      # what the gate saw
  - id: 2
    node: edit
    in: [1]
    tool: picsart_generate
    model: picsart-qwen-image-edit
    params: {prompt: "remove the second cup", imageUrls: ["<step 1 passed>"]}
    quoted_credits: 4
    gate: "cup gone, nothing else changed"
    status: pending
    outputs: []
    passed: null
    note: ""
  - id: 3
    node: enhance
    in: [2]
    tool: picsart_enhance
    model: picsart-enhance
    params: {image: "<step 2 passed>", scaleFactor: 2}
    quoted_credits: 2
    gate: "sharper, no plastic skin"
    status: pending
    outputs: []
    passed: null
    note: ""
final: {url: null, local: null, width: null, height: null}   # END
credits: {quoted: 11, spent: 0}
rounds: 1
```

A board copied from the Flow gallery names its source and what was changed
to fit the slot:

```yaml
board: template
template:
  title: Ethereal Studio Motion
  url: https://picsart.com/workflows/
  category: E-commerce & product content
  shape: "REF packshot -> Image (subject placed in a studio plate) -> END still + video"
  adapted: "video leg dropped; plate prompt from the family's References genre; text node added for the headline"
```

A video node carries the video non-negotiables explicitly:

```yaml
  - id: 2
    node: video
    in: [1]
    tool: picsart_generate
    model: seedance-2.5
    params:
      prompt: "the print slides between square, tall and wide frames, no other text, no logos or watermarks"
      aspectRatio: "1:1"
      resolution: 720p
      duration: 5
      generateAudio: false
      async: true
      extra: {startFrame: "<step 1 passed>"}
    quoted_credits: 35
    gate: "edges of the print stay visible, motion is smooth, nothing added"
    status: pending
    outputs: []
    passed: null
    note: ""
```

A compose node (composite recipe) is local and free; it is fed by every
panel node it places. The manager writes the composition plan
(`composition-<slot>.yaml`: panels + chrome items); the worker turns it into
the spec with `spec-from-plan` (adding only panel images) and renders that
spec — it never hand-authors the item list:

```yaml
  - id: 3
    node: compose
    in: [1, 2]
    tool: lp-compose
    # first: uv run lp-compose spec-from-plan composition-S07-m1.yaml \
    #          --image photo=steps/S07-m1-1-1.png --image thumb-a=steps/S07-m1-2-1.png \
    #          --out compose-S07-m1.yaml   (adds only image paths; items come from the plan)
    params: {spec: compose-S07-m1.yaml, out: steps/S07-m1-3-1.png}
    quoted_credits: 0
    gate: "every plan item present, placed and labelled as the plan says; panels unstretched; subject inside each panel; chrome legible at 480 px; no string twice"
    status: pending
    outputs: []              # the local path when done
    passed: null
    note: ""
final: {url: null, local: steps/S07-m1-3-1.png, width: 720, height: 720}
```

A **hybrid** chrome item — one the composition plan marks `rendered_by: model`
because it is too organic or bespoke for `lp-compose` to draw (a brushed mask,
the page's mark applied on packaging, a face box with keypoints) — is painted
inside its own generate/edit node, which carries `chrome_item:` naming the plan
item and a `reason:`. The prompt mentions that item and nothing else UI; the
compose node then draws every OTHER item (compose skips the model item):

```yaml
  - id: 2
    node: edit
    in: [1]
    tool: picsart_generate
    model: picsart-qwen-image-edit
    chrome_item: mark              # the plan item this node renders (rendered_by: model)
    reason: "the page's mark on the tote is a bespoke placement, not templatable"
    params: {prompt: "apply the mark (applied-mockup) onto the tote, nothing else changed", imageUrls: ["<step 1 passed>"]}
    quoted_credits: 4
    gate: "the mark sits on the tote, matches its reason, no text, nothing else changed"
    status: pending
    outputs: []
    passed: null
    note: ""
```

A text node is the worker's own writing, no call: it holds a prompt or a
string set that several image nodes share (a Series envelope), so the shared
words exist once on the board.

```yaml
  - id: 1
    node: text
    in: [start]
    params: {text: "editorial photo, hard even studio flash, seamless yellow, one product centred, 25 % margin"}
    quoted_credits: 0
    gate: "envelope holds every invariant from the brief and shared context"
    status: done
    outputs: []
    passed: null
    note: "checked against the family block"
```

## Rules

- `in:` names where a node's input comes from: `start`, or ids of earlier
  nodes. A node never lists a later node. `<step N passed>` placeholders in
  `params` are replaced by the real URL when node N passes and must agree
  with `in:`.
- `node:` is the kind Flow would give the step; `tool:` is the engine it
  runs on (`tool-map.md`, "Flow nodes"). `lp-flow check` refuses a kind on
  the wrong engine (an `edit` node on `picsart_enhance`).
- `chrome_item:` marks a generate/edit node that paints a hybrid plan item
  (`rendered_by: model`); it needs a `reason:` and its prompt names that item.
  `lp-flow check` lints a generate/edit node that has NO `chrome_item` but
  whose prompt names UI (`slider`, `toolbar`, `dropdown`, …): chrome is
  `lp-compose`'s, never a model's, unless the plan marks it hybrid.
- `board: blank` is the default. `board: template` needs `template.title`,
  `template.url` and `template.adapted`; a template never overrides the
  model rule, the text rule or the family's **Never** list (`flow-boards.md`).
- A failed gate means: change that node's params (or model) and re-run it
  as a **new node** with the next id, the same `in:`, its own quote, outputs
  and note; the failed node stays with `passed: false`. Do not restart the
  board.
- Rework from the reviewer: "re-run from node N" keeps nodes < N and their
  outputs, edits N onward, sets `rounds: 2`.
- Dry run: every paid node ends `status: skipped`, `quoted_credits` filled;
  nothing is composed and `final` stays null. The manager sums
  `credits.quoted` across slots.
- `lp-compose` and `text` nodes need no preflight and quote 0; a compose
  node's `outputs` and `passed` are section-relative paths. A composite's
  `final.url` stays null and `final.local` is the composite; `result.md`
  names it as `chosen:` relative to the run
  (`sections/S07/steps/S07-m1-3-1.png`). Rework that starts at a compose
  node costs nothing.
- `credits.spent` must equal the sum of this slot's rows in
  `<run>/ledger.jsonl`; the reviewer checks.
- Records from before boards (live-1 to live-4) have no `node:`/`in:`;
  `lp-flow` infers them from the tool and the placeholders, so old runs
  still read as boards. New records write both explicitly.
