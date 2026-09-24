# Tool map

Connector prefixes: `mcp__b05f6314-91d1-4820-aed3-620c98a82b3f__` (paid
calls, catalog, credits) and `mcp__3147bea9-f6b1-4574-96df-cbc4cb222497__`
(Media Tools: video reframe/describe, scene compose). Costs quoted with
`picsart_preflight` on 2026-09-04 (video extend/edit/reframe quoted the same
day, audio off); re-quote before relying on them.

## Steps

| Step | Tool | Model | Key params | Credits |
|---|---|---|---|---|
| Generate image (default) | `picsart_generate` | `gpt-image-2.5-sunburst` | `prompt`, `aspectRatio` (1:1 3:2 2:3 16:9 9:16 4:3 3:4), `quality` low/medium/high/xhigh/max (default high), `background` opaque/transparent, `count` 1, `imageUrls` ≤16, `saveToDrive: false` | 1 (medium), 2 (high), 7 (max), per image (preflight 2026-09-23) |
| Only when the image's own page copy names this model as its source | `picsart_generate` | `gemini-3.1-flash-image` | same; adds 4:5 5:4 3:2 ratios | 3 |
| Refine with references (i2i) | `picsart_generate` | `gpt-image-2.5-sunburst` | `imageUrls: [<hero or previous step>]` + prompt describing the change | 2 (high) |
| Targeted edit | `picsart_generate` | `picsart-qwen-image-edit` | `imageUrls: [<input>]`, `prompt` ("remove X", "swap Y", "restyle Z") | 4 |
| Replace background | `picsart_change_bg` | `recraftv3-replace-bg` | `image`, `prompt` for the new backdrop | 2 |
| Cutout | `picsart_generate` (not `picsart_remove_bg`: it 403s on Drive auto-save like `picsart_enhance`, blind-1-4 2026-09-24) | `picsart-sod-v8-2` as the `model` | `imageUrls: [<step N passed>]`, `saveToDrive: false` | 0 |
| Upscale / enhance | `picsart_generate` (not `picsart_enhance`: it has no `saveToDrive` and 403s on Drive auto-save, 3 of 3 runs on 2026-09-24) | `picsart-enhance` or `topaz-upscale-image` (faces) as the `model` | `imageUrls: [<step N passed>]`, `saveToDrive: false` | 2 (topaz 3) |
| Video draft | `picsart_generate` | `seedance-2.0-mini` | `duration` 5, `resolution` 720p, `generateAudio: false`, `async: true` | 10 |
| Video final (default) | `picsart_generate` | `seedance-2.5` | `duration` 4–30, `resolution` 480p/720p/1080p, `aspectRatio` incl. `adaptive`, `generateAudio: false`, `extra.startFrame` / `extra.endFrame` / `imageUrls` ≤30 | **7 per second at 720p**: 35 (5 s), 70 (10 s), 140 (20 s), 210 (30 s); `endFrame` adds nothing (quoted 2026-09-19); 90 (5 s 1080p) |
| Video extend | `picsart_generate` | `seedance-2.5-video-extend` (`seedance-2.0-mini-video-extend` as draft) | `videoUrls` (≤10 clips), `prompt`, `duration` 4–30, `resolution`, `aspectRatio: adaptive`, `generateAudio: false` | 25 (5 s 720p), 75 (15 s 720p); mini 10 (5 s 720p) |
| Video edit | `picsart_generate` | `seedance-2.5-video-edit` | `videoUrl`, `prompt`, optional `imageUrls` ≤30 refs, `resolution`, `generateAudio: false` | 30 (720p), 66 (1080p) |
| Reframe video (paid model) | `picsart_generate` | `luma-ray-flash-2-reframe-video` (`luma-ray-2-reframe-video` for quality) | `videoUrl`, `aspectRatio` (16:9 9:16 1:1 4:3 3:4 21:9 9:21), `prompt` | 36 (flash), 99 (ray 2) |
| Reframe / describe video | Media Tools `picsart_media_reframe_video`, `picsart_media_describe_video` | | | not on the paid connector; cost not quoted, check the result |
| Contact sheet, stills, export | `picsart_media_contact_sheet`, `picsart_media_export`, `picsart_media_probe_media`, `picsart_media_upload` | | | 0 |
| Composite card: ground, panels, chrome | `lp-compose` (local Pillow) | | `spec` (compose-<slot>.yaml), `--out`; `--describe <family>` lists the panels and their generate ratios | 0 |
| Templated callout clip | `lp-compose --timeline` (local: Pillow frames, Chromium WebCodecs VP9, WebM) | | `motion-<slot>.yaml` (the brief writes it), `--image <panel>=<path>`, `--out`, `--poster`; `--describe-timelines` lists the presets | 0 |
| Crop to exact slot size | `lp-inject` (local Pillow) | | | 0 |

Preflight for the editing models takes `params.imageUrls: [<url>]`, not
`image`. The tool call itself takes `image`.

## Flow nodes

The `node:` a step carries in `workflow.yaml` and the engine it runs on
(`flow-boards.md` has the full table): `image`, `edit`, `video` →
`picsart_generate`; `cutout` → `picsart_remove_bg`; `background` →
`picsart_change_bg`; `enhance` → `picsart_enhance`; `motion` →
`picsart_media_*`; `compose` → `lp-compose`; `text` and `ref` → no call.
`lp-flow check` refuses a kind on another engine.

## Support tools (free)

`picsart_preflight` (validate + quote), `picsart_model_params` (schema),
`picsart_model_catalog` (ids, ratios), `picsart_job_status` (async video),
`picsart_credits` (balance; manager only).

## GPT Image 2.5 Sunburst ratio map

Slot aspect → generate at: 16:9→16:9, 4:3→4:3, 3:2→3:2, 4:5→3:4
(crop), 5:4→4:3 (crop), 1:1→1:1, 9:16→9:16, 2:3→2:3, 21:9 and anything
wider→16:9 (crop). There is no 21:9: leave extra margin top and bottom. Cropping happens in `lp-inject`; leave
safe margin around the subject when the slot is a crop.
