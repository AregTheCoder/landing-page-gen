# Output contract for a section-worker

Folder: `<run>/sections/<Sxx>/`. The SubagentStop hook blocks a worker from
finishing until `workflow.yaml` and `result.md` exist with the required keys.

```
brief.md            written by the manager, read-only
examples/           corpus excerpts and media, read-only
workflow.yaml       one document per slot (--- separated), see picsart-workflows/workflow-format.md
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
    chosen: https://...            # final asset URL (also in workflow.yaml final.url)
    local: steps/S03-m1-4-1.png
    pattern: anchored
    credits: 17
    scores: {fit: 4, resemblance: 4, consistency: 5, clean: 5, artefacts: 4, geometry: 5, legibility: 4}
    workflow_score: {justified: 5, gated: 5, quote_respected: 5}
status: done | blocked
---

## Rationale
Why this pattern, why these steps, what the gates caught.

## Alternatives considered
Models or patterns rejected and why (one line each).

## What I would change
The one thing a second round should try first.
```

Required keys the hook checks: `chosen:` and `scores:` in `result.md`;
`slot:`, `steps:`, `final:` in `workflow.yaml`.

## Rework

When the manager sends "Rework: re-run from step N", keep steps before N and
their URLs, edit step N onward in `workflow.yaml`, re-run, append to
`result.md` under `## Round 2`, and update the frontmatter.
