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

## Rules

- `<step N passed>` placeholders are replaced by the real URL when step N
  passes. A step never references a step after it.
- A failed gate means: change that step's params (or model) and re-run that
  step; do not restart the chain. Increment nothing but `credits.spent`.
- Rework from the reviewer: "re-run from step N" keeps steps < N and their
  outputs, edits N onward, sets `rounds: 2`.
- Dry run: every paid step ends `status: skipped`, `quoted_credits` filled,
  `final.url: null`. The manager sums `credits.quoted` across slots.
- `credits.spent` must equal the sum of this slot's rows in
  `<run>/ledger.jsonl`; the reviewer checks.
