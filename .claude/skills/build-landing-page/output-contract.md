# Output contract for a section-worker

Folder: `<run>/sections/<Sxx>/`. The SubagentStop hook blocks a worker from
finishing until `workflow.yaml` and `result.md` exist with the required keys.

```
brief.md            written by the manager, read-only
examples/           corpus excerpts and media, read-only
workflow.yaml       one Flow board per slot (--- separated), see picsart-workflows/workflow-format.md
flow.md             the boards as node sheets (`uv run lp-flow sheet workflow.yaml`), what a person would rebuild on the Flow canvas
compose-<slot>.yaml the lp-compose spec of a composite slot: family, size, one image per panel
steps/              every downloaded intermediate and final asset, named <slot>-<step>-<n>.<ext>
result.md           frontmatter + prose, format below
review-N.md         written by the reviewer, one per round
```

## result.md

```markdown
---
section: S03
slots:
  S03-m1:
    chosen: https://...            # final asset URL, or a composite's run-relative path (sections/S03/steps/S03-m1-3-1.png)
    local: steps/S03-m1-4-1.png
    pattern: anchored
    board: blank                    # or "template: <title>"
    nodes: 4
    credits: 17
    scores: {fit: 4, resemblance: 4, consistency: 5, clean: 5, text: 5, artefacts: 4, geometry: 5, legibility: 4}
    workflow_score: {justified: 5, gated: 5, quote_respected: 5, board: 5}
status: done | blocked
---

## Rationale
Why this board (blank or which template), why these nodes, what the gates caught.

## Alternatives considered
Models or patterns rejected and why (one line each).

## What I would change
The one thing a second round should try first.
```

Required keys the hook checks: `chosen:` and `scores:` in `result.md`;
`slot:`, `steps:`, `final:` in `workflow.yaml`.

## Rework

When the manager sends "Rework: re-run from node N", keep nodes before N and
their URLs, edit node N onward in `workflow.yaml`, re-run, regenerate
`flow.md`, append to `result.md` under `## Round 2`, and update the
frontmatter.
