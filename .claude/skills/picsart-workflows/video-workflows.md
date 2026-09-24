# Video workflows

Video is 7 to 18 times the cost of an image. Always draft first. On the
board every step below is a `video` node (`tool: picsart_generate`) fed by
the still's node through `in:` and `extra.startFrame`; the still comes from
the family's image recipe (`image-workflows.md`). The board carries
`kind: video`, and `lp-flow check` then enforces the still recipe plus the
two video nodes below and every rule in this file. The Flow gallery's video
templates (a photo-to-motion pass fanned out into relit variants) fit only
when the slot is a video; see `flow-boards.md` for the template test.

## Timeline: templated callouts (0 credits)

Many callout clips are not generated motion at all: a composition changes
state on a static camera (ai-image-enhancer S07, S10, S11 and S13, and their
twins on --unblur, --unpixelate and video-enhancer). The skeleton's
`> motion:` line says which kind a slot is: `timeline <preset>` for a
`ui-demo` or `transition` original at 1:1 on a static camera, `generative`
for everything else (the recipe below). The poster frame hides a callout's
chrome, so the preset is often a TODO the manager resolves from the
original's strip.

| preset | original | length | states |
|---|---|---|---|
| `enhance-reveal` | S10 | 4 s | the flawed card; a compare-handle sweep reveals the fix; the Before goes small top left, the After tall right, a checklist ticks in |
| `product-bento` | S11 | 7 s | a soft product sharpens under the handle; a shop card (name, price, button); the bento with the page's tool tiles |
| `prompt-to-result` | S13 | 10 s | the result full bleed (a still, or a clip); the prompt types on black; the prompt column with the tool mark (the voice line only when the copy offers audio), the result with a play mark |
| `brand-to-mockup` | S07 | 6 s | the photo card; the caption types in a selection box and the title sets; the bento with the tool tile and the design applied as a mockup |

The board is `kind: timeline`: the poster family's still recipe, then one
`node: motion` on `tool: lp-compose` with `timeline: motion-<slot>.yaml`
(the brief writes the spec; `lp-flow check` enforces both). The worker
generates only the panels the brief's `## Timeline` table names, then runs
`lp-compose --timeline`. Every block keeps its category (compose/assets/blocks.yaml):
the tool tiles show the page's own tools, a checklist row or product string is
page copy (`> chrome:`), and the Before is the After degraded. The clip is
judged on its strip like any other (length, pace, loop). A `prompt-to-result`
whose result is a real clip runs the recipe below for that clip first, and
the timeline then embeds it.

## Recipe: still to motion

1. image recipe → accepted still. This is also the `poster:` in `result.md`.
2. draft: `seedance-2.0-mini`, `duration: 5`, `resolution: 720p`,
   `generateAudio: false`, `extra: {startFrame: "<step N passed>"}`, prompt =
   camera move + subject motion in one sentence each, "slow", "subtle" by
   default; `async: true`. The instant it returns, record the job handle,
   then poll at most three times: `picsart_job_status`, one Bash `sleep` of
   the job's `progress.estimatedSecondsLeft` (clamped 45–540 s), then
   `picsart_job_status`. The instant the clip URL arrives, write it into the
   node's `outputs` before downloading. Gate: motion matches the prompt, no
   morphing, first frame equals the still. The draft checks the motion
   prompt, not the length: it stays at 5 s.
3. final: `seedance-2.5`, same params, `duration: <target>` (below), 720p
   (1080p only if the slot is wider than 1300 px and the brief allows 90
   credits). 7 credits per second at 720p (35 / 70 / 140 / 210 for 5 / 10 /
   20 / 30 s; `endFrame` is free) — preflight it anyway and record the
   quote in the node. Gate as above, plus the target length
   (`picsart_media_probe_media`) and, for a loop, the seam.
4. extend, only when the target is above 30 s: `seedance-2.5-video-extend`
   with `videoUrls: ["<step N passed>"]` (the final's node), `duration` = the
   remainder, `aspectRatio: adaptive`; 25 cr / 5 s, 75 / 15 s. Each pass is
   its own gated node; the first extend is drafted on
   `seedance-2.0-mini-video-extend` (10 cr) when more than one pass is needed.

There is no text-to-motion recipe: a video node never takes `imageUrls`
(references are read for the look, never wired), and a slot with no still
wanted is not a video slot.

## Duration: faithful to the original

The brief's `## Video` section names the **target duration**, taken from the
slot's `> duration:` line (the original clip's length, rounded). The final
matches it: one `seedance-2.5` call with `duration: <target>` up to 30 s, an
extend pass beyond that. A 5 s clip in a 10 s slot is a `[duration]` flag in
`lp-bench` and a `loop` score below 3 in review. Cost arithmetic for a slot:
still chain ~13–15 + draft 10 + 7 × target seconds (a 10 s original ≈ 95, a
30 s original ≈ 235). When the quoted cost of the faithful length exceeds
the section's advisory cap, stop and report the quote against the target
instead of shipping a shorter clip silently.

## Rules

- A video slot's family is its poster frame's family (`style-families.md`,
  slot classes `callout-1:1-video`, `hero-1:1-video`); the still comes from
  that family's main panel, never from a composite. The brief's family block
  carries a **Motion** line (what the corpus clips of this family do: motion
  kind, camera, pace, loop share, typical length); the prompt's two motion
  sentences follow it.
- `generateAudio: false` always; landing pages autoplay muted.
- Aspect: use the slot's aspect if Seedance supports it (16:9 9:16 1:1 4:3
  3:4 21:9), else `adaptive` with a startFrame already in the right ratio.
- Loop: every corpus clip is played on `loop`, but only about 30 % close on
  their first frame (measured `loop`; the rest cut back visibly). When the
  brief's Motion line shows a high loop share, or the slot's own `> attrs:`
  says `loop=true`, wire `extra.endFrame: "<step N passed>"` to the same
  still as the startFrame on the final so the clip closes where it opened;
  check the seam on the strip (last frame against first). It costs nothing
  extra (quoted 2026-09-19).
- Every `<step N passed>` in a video node names an earlier node that `in:`
  also lists; the still nodes for `startFrame`/`endFrame`, video nodes for
  `videoUrls`. A literal URL is refused by `lp-flow check`.
- Download the mp4 to `steps/`, then write a 3-frame strip beside it —
  `uv run lp-corpus frames steps/<slot>-<node>-<n>.mp4 --out steps/<slot>-<node>-strip.png`
  — and `Read` the strip; `picsart_media_probe_media` gives duration, fps and
  size. Do not judge from the URL. The reviewer reads the same strip.
- Never run two paid video steps without a gate in between.
- Text: only the brief's `## Text in image` strings, quoted verbatim and
  kept static (no animated typography in a generated clip); every prompt ends
  with ", no other text, no logos or watermarks". Check the words on the
  strip. Typing and ticking text exists only in a timeline, and only with the
  exact `> chrome:` strings, drawn by lp-compose.
- `result.md` for a video slot carries `poster:` (the accepted still) and
  `duration_s:` (the measured length) beside `chosen:`; `lp-inject` ships the
  poster and sets `muted autoplay loop playsinline`.
