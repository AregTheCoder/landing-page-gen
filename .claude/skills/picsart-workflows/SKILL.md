---
name: picsart-workflows
description: How to design, run, and review a Picsart Flow board (a node graph of generate, refine, edit, cutout, upscale, animate, compose steps) for one landing-page media slot, with a gate after every node and a fixed yaml format. Use when acting as section-worker or section-reviewer, or whenever chaining Picsart MCP tools for an image or video asset.
---

# picsart-workflows

A workflow is a **Picsart Flow board** for one slot: START, a graph of
nodes each on one engine and one model, END. Each node's output URL feeds
the nodes wired from it; each node ends with a gate you score before moving
on. Build the board from a blank canvas (or copy a gallery template when it
fits, `flow-boards.md`), write it whole, preflight every paid node, check
that it wires, then execute. Read only the companion you need:

| File | Read when |
|---|---|
| `flow-boards.md` | starting a slot: what a board is, node kinds and their engines, blank board vs gallery template, the canvas sheet |
| `tool-map.md` | choosing an engine or model for a node, checking cost, connector, params |
| `image-workflows.md` | the slot is an image: board recipes (direct, anchored, cutout, series, composite, layered), ratio map, prompt rules |
| `video-workflows.md` | the slot is a video: draft tier, startFrame, audio, extend |
| `workflow-format.md` | writing or editing `workflow.yaml`; the re-run-as-new-node rule |
| `evaluation.md` | scoring a gate, the final asset, or a whole board |
| `style-families.md` | never as a worker or reviewer: the brief's `## Style family` block is the copy you need (40 KB otherwise); only the manager reads the whole file |

## Non-negotiables

- Paid calls only through the `b05f6314` tools, only after
  `picsart_preflight` on the same model. The credit guard denies otherwise.
- Every image node is `gemini-3-pro-image` (Nano Banana Pro); a video node
  is `seedance-2.5` with `seedance-2.0-mini` as draft. The one exception is
  truthfulness: an image whose section copy explicitly names the model that
  generated it is made with that model, the copy quoted in the node's
  `reason` (`image-workflows.md`). Nothing else — price, string length, a
  gallery of many tiles, a template's own model — moves a node off the pro
  model.
- Models render text only from the brief's `## Text in image` table, each
  string quoted verbatim in the prompt; every generation prompt ends with
  ", no other text, no logos or watermarks". No logos, watermarks or UI,
  ever. Pills, tiles, frames, badges and their labels exist only when
  `lp-compose` draws them from a family template.
- Corpus examples and widened neighbours (`examples/*.md`, `origin:
  widened`) are read for the look and never wired into a node: no example,
  stock or widened URL in `imageUrls`, `startFrame` or `image`. The only
  REF a board takes is what the brief allows (the hero URL).
- View results by downloading them: `curl -sL <url> -o steps/<name>` then
  `Read` the file. There is no view tool.
- Video calls use `async: true` and `picsart_job_status` polling.
- Never touch files outside your section folder.
- Read each input once: the brief, one image per example, each render once
  at its gate. Do not re-open the brief or a companion file to re-check a
  rule you already read; quote it from memory or from your workflow.yaml.
