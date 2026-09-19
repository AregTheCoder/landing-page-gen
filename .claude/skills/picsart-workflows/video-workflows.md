# Video workflows

Video is 7 to 18 times the cost of an image. Always draft first. On the
board every step below is a `video` node (`tool: picsart_generate`) fed by
the still's node through `in:` and `extra.startFrame`; the still comes from
the family's image recipe (`image-workflows.md`). The board carries
`kind: video`, and `lp-flow check` then enforces the still recipe plus the
two video nodes below and every rule in this file. The Flow gallery's video
templates (a photo-to-motion pass fanned out into relit variants) fit only
when the slot is a video; see `flow-boards.md` for the template test.

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
  kept static (no animated typography); every prompt ends with ", no other
  text, no logos or watermarks". Check the words on the strip.
- `result.md` for a video slot carries `poster:` (the accepted still) and
  `duration_s:` (the measured length) beside `chosen:`; `lp-inject` ships the
  poster and sets `muted autoplay loop playsinline`.
