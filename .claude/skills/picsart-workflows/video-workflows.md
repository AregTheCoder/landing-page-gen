# Video workflows

Video is 7 to 18 times the cost of an image. Always draft first. On the
board every step below is a `video` node (`tool: picsart_generate`) fed by
the still's node through `in:` and `extra.startFrame`; the still comes from
an image recipe (`image-workflows.md`). The Flow gallery's video templates
(a photo-to-motion pass fanned out into relit variants) fit only when the
slot is a video; see `flow-boards.md` for the template test.

## Recipes

**still to motion** (default): the slot has an accepted still, or a still
can be produced with an image pattern first.
1. image pattern → accepted still (this is also the `poster`).
2. draft: `seedance-2.0-mini`, `duration: 5`, `resolution: 720p`,
   `generateAudio: false`, `extra: {startFrame: <still url>}`, prompt =
   camera move + subject motion in one sentence each, "slow", "subtle" by
   default; `async: true`, poll `picsart_job_status`. Gate: motion matches
   the prompt, no morphing, first frame equals the still.
3. final: `seedance-2.5`, same params at 720p (1080p only if the slot is
   wider than 1300 px and the brief allows 90 credits). Gate as above.

**text to motion**: no still exists and none is wanted. `seedance-2.0-mini`
draft with `imageUrls` references from the examples, then `seedance-2.5`.

**extend**: the slot needs more than 30 s or a loop. Final clip →
`seedance-2.5-video-extend`. Preflight first; cost is unquoted.

## Rules

- A video slot's family is its poster frame's family (`style-families.md`,
  slot classes `callout-1:1-video`, `hero-1:1-video`); the still comes from
  that family's main panel, never from a composite.
- `generateAudio: false` always; landing pages autoplay muted.
- Aspect: use the slot's aspect if Seedance supports it (16:9 9:16 1:1 4:3
  3:4 21:9), else `adaptive` with a startFrame already in the right ratio.
- Duration 5 s unless the brief says otherwise; loops read best at 5–8 s.
- Download the mp4 to `steps/`, extract a check frame with
  `picsart_media_probe_media` or view the poster; do not judge from the URL.
- Never run two paid video steps without a gate in between.
- Text: only the brief's `## Text in image` strings, quoted verbatim and
  kept static (no animated typography); every prompt ends with ", no other
  text, no logos or watermarks". Check the words on the check frame.
