---
name: picsart-workflows
description: How to design, run, and review a multi-step Picsart workflow (generate, refine, edit, cutout, upscale, animate) for one landing-page media slot, with per-step evaluation gates and a fixed yaml format. Use when acting as section-worker or section-reviewer, or whenever chaining Picsart MCP tools for an image or video asset.
---

# picsart-workflows

A workflow is an ordered list of Picsart tool steps for one slot. Each
step's output URL feeds the next; each step ends with a gate you score before
moving on. Write the whole workflow first, preflight every paid step, then
execute. Read only the companion you need:

| File | Read when |
|---|---|
| `tool-map.md` | choosing a tool or model, checking cost, connector, params |
| `image-workflows.md` | the slot is an image: patterns, ratio map, prompt rules |
| `video-workflows.md` | the slot is a video: draft tier, startFrame, audio, extend |
| `workflow-format.md` | writing or editing `workflow.yaml`; the re-run-from-step rule |
| `evaluation.md` | scoring a gate, the final asset, or a whole workflow |
| `style-families.md` | never as a worker or reviewer: the brief's `## Style family` block is the copy you need (40 KB otherwise); only the manager reads the whole file |

## Non-negotiables

- Paid calls only through the `b05f6314` tools, only after
  `picsart_preflight` on the same model. The credit guard denies otherwise.
- Defaults: image `gemini-3-pro-image` (Nano Banana Pro), video
  `seedance-2.5` with `seedance-2.0-mini` as draft. Deviate only when the
  brief or the examples require it, and write the reason in the step.
- Models render text only from the brief's `## Text in image` table, each
  string quoted verbatim in the prompt; every generation prompt ends with
  ", no other text, no logos or watermarks". No logos, watermarks or UI,
  ever. Pills, tiles, frames, badges and their labels exist only when
  `lp-compose` draws them from a family template.
- View results by downloading them: `curl -sL <url> -o steps/<name>` then
  `Read` the file. There is no view tool.
- Video calls use `async: true` and `picsart_job_status` polling.
- Never touch files outside your section folder.
- Read each input once: the brief, one image per example, each render once
  at its gate. Do not re-open the brief or a companion file to re-check a
  rule you already read; quote it from memory or from your workflow.yaml.
