# Picsart's own workflow engine — "MP Scene" — analysis

Investigated 2026-09-10 via the read-only `picsart_media_*` tools (no credits,
no renders). This is what Picsart's first-party "workflow" tool actually is,
how it works, and how it relates to `landing-page-gen`.

## What it is (one line)

A **declarative video / motion-graphics / presentation composition engine** —
an SDK ("Media Platform SDK", renderers **Jet** and **V3/Replay**, translator
layer `mp-ai-tools`) exposed over MCP as the `picsart_media_*` tools. You bring
assets **by URL**; it **composes, animates, and renders** them into mp4/png.
It is **not** an image generator and does no photographic generation itself.

This is a different axis from our project. We *generate the pixels* of still
slots with Nano Banana Pro. MP Scene *assembles and animates* assets on a
timeline. The word "workflow" collides; the systems barely overlap on
generation and overlap heavily on **assembly** (our `lp-compose`) and **video**
(which we skip today).

## The core model — an "MP Scene" document

A scene is a composition (`width`/`height`/`fps`/`duration`) holding layers.

- **Layer content kinds:** `text`, `media`, `color`, `scene_ref`, `scene`,
  `track`, `captions`, `shape`.
- **Each layer carries:** transform (position/scale/anchor), **animations**
  (keyframes *and* per-frame Lua expressions), **effects**, **masks** (bezier
  `shape` path or embedded Lottie), **blend modes**, **looks**, **motion
  presets**, plus **audio tracks** and **captions** at the scene level.
- **Composition by reference — the powerful part:** a `scene_ref` makes a whole
  scene a layer/clip. References resolve local-first (`scenes{}` map →
  ancestors → template registry → remote `https` MP Scene, inlined, to depth 8,
  5 MiB / 10 s / SSRF-guarded). So scenes nest into scenes: a montage of
  `scene_ref` clips *is* a multi-scene storyboard.
- **Authoritative schema:** `get_scene_schema` returns a ~66 KB JSON Schema
  (`MpMediaContent` et al.); anything that validates renders.
- **Limits:** ≤3600 s, ≤100 layers, ≤20 audio tracks, ≤4096×4096. Active
  engine v3.

## The authoring surface

**Scene templates (~30, `mpscene://<id>`)** — parameterized reusable scenes,
each with a typed parameter schema (`describe_scene_template`). By category:

- **slide** (a whole deck system): title, bullets (+animated), quote, section
  divider (+animated), statement, comparison (two-column), photo-caption,
  closing. 1920×1080, text+colour.
- **title_card:** product-card (full-bleed hero + headline + subtitle),
  lower-third, end-card (CTA), title-card.
- **montage / motion:** montage (clip reel with a transition per seam),
  ken-burns, burst (radial photo burst), countdown, grid-reveal, split-screen,
  card-fan.
- **collage** (image grid, row-major), **framing** (crop = a moving camera
  window on one clip), **mask** (heart).

Templates are **variadic + content-free + style-free**: you bind a `cards` /
`clips` / `photos` list of any length; each item is an image URL, a video (with
`trim`), a `scene_ref` sub-scene, text, or colour; the template owns geometry
and motion only. "Generative templates" (montage/collage/heart) means they
*expand programmatically from the bound list* — **not** AI generation.

**Looks (17)** — chainable per-layer visual treatments (`resolve_looks`):
- Framing/geometry: `rounded_corners`, `clip_path`, `photo_frame`,
  `reflection`, `tilt_3d`, `tilt_reflection`, `blur_fill` (aspect conversion).
- Grade/texture: `duotone`, `light_leak`, `vintage_bw`, `vcr`, `shimmer`.
- **UI chrome (!):** `play_badge`, `social_frame`, `social_post`,
  `chat_bubble`, `chat_input`, `selection_chrome`. These draw exactly the kind
  of app-UI chrome our composite families need and `lp-compose` can't.

**Motion presets (9):** fade in/out, slide in/out, zoom-in, scale-pop,
ken-burns, glow-pulse. **Transitions (~18):** crossfade, push, slide,
card-flip, page-curl, zoom-through, plus elaborate AE-converted ones (camera
whip, shape-reveal, splatter, cubes, kaleida, free-fall, manga-page).

**Recipes** — first-party authoring guides written in **Agent-Skills-format
markdown** (the same format as our `.claude/skills`): figma-storyboard→scene,
fragment-matching a reference video, motion-extraction, asset-audit,
scene-format-architecture. Meta-knowledge for driving the engine.

## How it works (the pipeline)

1. **Discover** — `quickstart` (how-to index), `get_capabilities`
   (effects/looks/limits), `list_scene_templates`, `list_recipes`.
2. **Author** — `apply_scene_template(uri, params)` → a scene; or hand-write a
   scene JSON; edit with `patch_scene` / `expand_scene_ref`;
   `translate_scene` converts between engine dialects.
3. **Validate** — `validate_scene` (schema) and `query_layout` (computed
   positions/sizes).
4. **Preview cheaply** — `contact_sheet` samples frames at chosen timestamps
   without a full render.
5. **Render** — `export` / `video_render` → final mp4/png on the CDN. This is
   the heavy, paid step (cost not probed — needs confirming before use).
6. **Assets** — URL-only; a drag-and-drop upload widget turns a local file into
   a URL; `probe_media` / the asset-audit recipe check alpha/dims/aspect first.

## How it relates to landing-page-gen

| Dimension | landing-page-gen | Picsart MP Scene |
|---|---|---|
| Job | **Generate** still-slot pixels | **Compose/animate/render** assets |
| Generation | Nano Banana Pro + gates | none — assets by URL |
| Assembly / chrome | `lp-compose` (local Pillow, static) | full timeline: layers, masks, **looks**, transitions, nested scenes |
| "Workflow" file | `workflow.yaml` (generate plan + audit) | MP Scene JSON (a render document) |
| Know-how | `.claude/skills` | recipes (same Agent-Skills md) |
| Output | PNG injected into HTML | mp4 / png render |
| Time / animation | none | native — its whole point |

**They are complementary, not competing.** Ours makes the picture; MP Scene
arranges and moves pictures.

### Where MP Scene could plug into our pipeline

- **Replace `lp-compose` for the composite/assembled families (A).** Our
  hand-drawn chrome maps almost 1:1 onto MP templates + looks:
  - `template-mockup` card+tiles ≈ `product-card` + `rounded_corners` +
    `collage` of tile cells.
  - `dark-composite` reference-thumbs / model-picker ≈ `collage` / `grid-reveal`
    + `play_badge` + a list panel; `two-up` ≈ `split-screen`.
  - `before-after` ≈ `split-screen` or the `crop` camera window.
  - the tilt/reflection chrome we fake in Pillow ≈ `tilt_3d` /
    `tilt_reflection` / `reflection` looks (real 3D + grounded shadow).
- **Unlock the UI-chrome families we deferred.** `prompt-card`,
  `editor-canvas`, `panel-overlay` need app-UI chrome (`social_frame`,
  `chat_input`, `selection_chrome`, `social_post`) that `lp-compose` cannot
  draw and we currently brief down to `full-bleed`.
- **Unlock video slots.** Hero/feature videos, product reveals, gallery
  montages — `montage`, `ken-burns`, `burst`, `product-card` motion — which we
  skip entirely today. (Our project already reserves `seedance` for generated
  video; MP Scene is the *editing/compositing* layer that would sit on top.)
- **Feeds the layered-photo work directly.** Generate the harmonised layered
  plate with Nano Banana Pro (our new `layered` pattern), then hand it to MP
  Scene as the `media` layer of a `product-card` / `collage` / `montage` to add
  chrome and motion — MP Scene is the "assemble" half we do in Pillow now.

### What it does NOT do for us

- No photographic generation, relighting, or harmonisation — the layered-photo
  hard problem stays with Nano Banana Pro.
- Rendering is time-based and paid per render (heavier than emitting a static
  PNG); worth it for video/animated deliverables, overkill for a plain static
  card unless we want the chrome/looks quality.
- Adopting it means workers author **MP Scene JSON + render** instead of a
  Pillow spec — a real build (schema, a `compose-*.yaml` → MP-Scene translator,
  render-cost governance in the hooks).

## Open questions to resolve before adopting

1. **Render cost & governance** — what does an `export` / `video_render` cost,
   and can it be preflight-quoted so the credit-guard can cap it? (Our hooks
   only govern the five generate/edit tools today; MP renders would be
   ungoverned.)
2. **Still-PNG export path** — can MP Scene export a single-frame PNG at a
   sensible cost to replace an `lp-compose` static card, or is it economical
   only for video?
3. **Fit with `lp-inject`** — MP renders land as CDN URLs; our injector expects
   local media. A small download step (as we already do for generations).
4. **Build scope** — a `compose-*.yaml` → `apply_scene_template` translator for
   the families that map cleanly, versus keeping `lp-compose` for static cards
   and using MP Scene only for video + UI-chrome families.

## Recommended next step

A **one-scene evaluation** (small, paid render): rebuild one existing composite
— e.g. the live-4 `template-mockup` callout — as an MP Scene
(`product-card` + `collage` tiles + `rounded_corners`/`selection_chrome`
looks), render one still/short, and compare against the `lp-compose` version on
quality and cost. That answers Q1–Q2 concretely and tells us whether MP Scene
earns a place in the pipeline before any bigger build.
