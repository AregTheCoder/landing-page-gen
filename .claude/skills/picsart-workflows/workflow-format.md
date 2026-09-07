# workflow.yaml format

One YAML document per slot, `---` separated, in the section folder. Written
in full before the first paid call; updated after every step.

```yaml
slot: S03-m1
kind: image
pattern: anchored
target: {size: 1440x810, aspect: "16:9", generate_ratio: "16:9"}
models: {primary: gemini-3-pro-image, reason: default}
steps:
  - id: 1
    tool: picsart_generate
    model: gemini-3-pro-image
    params:
      prompt: "..., no text or logos"
      aspectRatio: "16:9"
      resolution: 2K
      count: 2
      imageUrls: ["https://.../hero.png"]
    quoted_credits: 10
    gate: "one candidate with the product centred, no text, palette matches hero"
    status: pending          # pending | done | failed | skipped (dry run)
    outputs: []              # URLs, filled after the call
    passed: null             # URL that passed the gate, or null
    note: ""                 # what the gate saw
  - id: 2
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
    tool: picsart_enhance
    model: picsart-enhance
    params: {image: "<step 2 passed>", scaleFactor: 2}
    quoted_credits: 2
    gate: "sharper, no plastic skin"
    status: pending
    outputs: []
    passed: null
    note: ""
final: {url: null, local: null, width: null, height: null}
credits: {quoted: 16, spent: 0}
rounds: 1
```

A video step carries the video non-negotiables explicitly:

```yaml
  - id: 2
    tool: picsart_generate
    model: seedance-2.5
    params:
      prompt: "the print slides between square, tall and wide frames, no text or logos"
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

A compose step (composite pattern) is local and free:

```yaml
  - id: 3
    tool: lp-compose
    params: {spec: compose-S07-m1.yaml, out: steps/S07-m1-3-1.png}
    quoted_credits: 0
    gate: "panels unstretched, subject inside each panel, pills legible at 480 px"
    status: pending
    outputs: []              # the local path when done
    passed: null
    note: ""
final: {url: null, local: steps/S07-m1-3-1.png, width: 720, height: 720}
```

## Rules

- `<step N passed>` placeholders are replaced by the real URL when step N
  passes. A step never references a step after it.
- A failed gate means: change that step's params (or model) and re-run that
  step; do not restart the chain. Increment nothing but `credits.spent`.
- Rework from the reviewer: "re-run from step N" keeps steps < N and their
  outputs, edits N onward, sets `rounds: 2`.
- Dry run: every paid step ends `status: skipped`, `quoted_credits` filled;
  nothing is composed and `final` stays null. The manager sums
  `credits.quoted` across slots.
- `lp-compose` steps need no preflight and quote 0; their `outputs` and
  `passed` are section-relative paths. A composite's `final.url` stays null
  and `final.local` is the composite; `result.md` names it as `chosen:`
  relative to the run (`sections/S07/steps/S07-m1-3-1.png`). Rework that
  starts at a compose step costs nothing.
- `credits.spent` must equal the sum of this slot's rows in
  `<run>/ledger.jsonl`; the reviewer checks.
