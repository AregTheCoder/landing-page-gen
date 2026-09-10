# Flow boards: how a slot's workflow is a Picsart Flow

Picsart Flow (`picsart.com/create/workflows`, gallery at
`picsart.com/workflows`) is Picsart's own workflow tool: a canvas where a
creative is built as a graph of **nodes**. Its own words: "Each node is a
creative step in your workflow." An input step (START: an upload, a
reference, a prompt, or a blank canvas), processing nodes (Image, Video,
Text, Audio, Motion — each on one AI model, "generate, remove background,
enhance, or apply effects"), an output step (END: format and quality), wired
by dragging one step's output to the next step's input. A saved graph is a
**Workflow** typed with its output size; the gallery holds reusable ones
("Copy a flow, make it yours"). The editor is login-walled and has no API;
what the MCP connectors expose are the engines behind its nodes
(`picsart_generate` is the Image node's model, `picsart_media_*` the Motion
node's engine).

So a worker works **in Flow's model, on Flow's engines**: every slot is a
board authored in `workflow.yaml` (`workflow-format.md`) and run node by
node over MCP. `uv run lp-flow sheet` renders the board as the node sheet a
person places and wires on the Flow canvas, unchanged; `flow.md` in the
section folder is that sheet. Nothing about a board is ours that Flow does
not have: the node kinds, the wiring, the one-model-per-node, the typed
output. What we add is what Flow leaves to the person: a gate after every
node, a preflight quote before every paid one, the ledger, blindness, and
the corpus anchor.

## Node kinds and their engines

| Flow node | `node:` | engine (`tool:`) | model | what it is |
|---|---|---|---|---|
| START | `start:` | — | — | the brief's text strings, REF inputs (hero URL from shared context), the family's panels |
| Text | `text` | none | — | a prompt envelope or string set the worker writes once and other nodes share |
| Reference | `ref` (in `start.inputs`) | none | — | a URL that enters as `imageUrls` or `startFrame`; never a widened or stock image |
| Image | `image` | `picsart_generate` | `gemini-3-pro-image` | generate a panel; also i2i refine with the pass in `imageUrls` |
| Image (edit) | `edit` | `picsart_generate` | `picsart-qwen-image-edit` | targeted change of one thing |
| Image (cutout) | `cutout` | `picsart_remove_bg` | `picsart-sod-v8-2` | transparent PNG of the subject |
| Image (background) | `background` | `picsart_change_bg` | `recraftv3-replace-bg` | new backdrop behind a cutout |
| Image (enhance) | `enhance` | `picsart_enhance` | `picsart-enhance` / `topaz-upscale-image` | upscale |
| Video | `video` | `picsart_generate` | `seedance-2.5` (`seedance-2.0-mini` draft) | still to motion, extend, edit |
| Motion | `motion` | `picsart_media_*` | — | MP Scene compose and render (0 credits measured 2026-09-10) |
| Compose | `compose` | `lp-compose` | — | the family's chrome and ground around the panels; Flow has no node for Picsart's own card chrome, this is ours |
| END | `final:` | — | — | the slot's asset at the slot's size |

## Blank board first; a gallery template when one fits

A worker builds every board **from a blank canvas**: START, the nodes the
recipe needs (`image-workflows.md`, `video-workflows.md`), END. That is the
default and needs no justification.

A **Flow gallery template** may be copied instead when one fits the slot.
The catalogue is `corpus/flow-templates.yaml` (the manager refreshes it from
the gallery before a run); ask it:

```
uv run lp-flow templates --family <family> --device <device> [--query "<H2 words>"]
```

Use a template when, and only when, all three hold:

1. its `fits` names your family, and your device when the slot has one;
2. its `shape` covers every panel the brief's `## Slots to produce` lists
   (a single-still template does not fit a `reference-thumbs` composite);
3. copying it changes nothing an invariant pins: the model rule (every image
   node on `gemini-3-pro-image` unless the copy names another), the text
   rule, the family's **Panels** and **Never** lines, the ratio map.

Then `board: template` with `title`, `url`, `shape` and `adapted` (one
sentence: what you dropped, added or re-pointed). A template is a node
shape and an order of operations, not a look: its example pictures are not
your references, its prompts are not your prompts, and its models are
replaced by ours where they differ. When no template passes all three
tests, `lp-flow templates` prints "start from a blank board" and you do.

## What every board carries

- **START** lists the strings from `## Text in image` and any REF the brief
  allows (the hero URL under the anchored rule). Corpus example images and
  widened neighbours are read, never wired: they are look references and
  their licence is not ours.
- **One model per node**, written on the node. Every image node is
  `gemini-3-pro-image`; a non-pro model needs `reason:` quoting the section
  copy that names it (`image-workflows.md`, "Prompt rules").
- **A gate on every node** and a preflight quote on every paid one, before
  the first call. `lp-flow check` before you run; the manager's `precheck.py`
  runs it again.
- **Depth is nodes, not re-rolls**: a pass is followed by a critique and,
  when a concrete flaw is named, an i2i `image` node fed by it and one
  variation node, each gated (`image-workflows.md`, "Longer workflows").
- **The sheet**: after the last node, `uv run lp-flow sheet workflow.yaml`
  writes `flow.md` beside it. The reviewer reads the sheet first; a person
  can rebuild the board in the Flow editor from it node by node.

## Where the two surfaces differ, honestly

Flow runs on Picsart's credits inside the product; ours run on the API
credits the `b05f6314` connector spends, capped by the run hook. Flow's Text
node can generate text; ours never does (picture text comes from the
manager's `> text:` line). Flow has Audio; landing pages autoplay muted, so
no board has an audio node. Flow's canvas cannot be driven from here, so
"use a template" means copying its node shape onto our engines, not running
it in the product; the sheet is what closes that gap for a person.
