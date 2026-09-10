# Picsart Flow — the node-based creation pipeline (comprehensive analysis)

Investigated 2026-09-10 from Picsart's own product (browsed
`picsart.com/workflows` and the Flow editor; web search was down, so this is
first-party UI evidence, not secondary articles). **This corrects an earlier
mis-scoping:** the `research/picsart-mp-scene/` doc analysed the MP Scene media
SDK, which turns out to be *one node's backend* inside the larger product
described here. The product Areg meant is **Picsart Flow**.

## What Picsart Flow is

A **node-based, canvas AI creation pipeline builder.** The editor's own words:

> "Add your first node to the canvas. **Each node is a creative step in your
> workflow.**"

You place creative-step **nodes** on a canvas and wire them into a **pipeline**
(a directed graph) that carries an idea from input to finished creative,
orchestrating multiple AI models along the way. A saved graph is a **Workflow**
(type shown literally as `Workflow`, with an output size, e.g. 612×1088,
720×1280). Workflows are reusable, browsable templates: "Copy a flow, make it
yours, and move from idea to finished creative faster."

This is the **"levels of creation and a pipeline"**: the levels are the node
kinds (the creative steps); the pipeline is how their outputs feed forward and
fan out.

## The nodes (the "levels of creation")

From the editor's "add a node" palette — *each node can generate OR upload* its
content:

| Node | Role |
|---|---|
| **Image** | Generate or upload an image |
| **Video** | Generate or upload a video |
| **Text** | Write or generate text |
| **Audio** | Generate or upload audio |
| **Motion** *(New)* | Motion Graphics |

Plus flow-control / IO nodes seen in the quick-composer bar and on templates:
**START**, **END**, **REF** (reference), and a **DOCUMENT INPUT NODE**. So a
flow has inputs (upload / reference / document / prompt), creative-step nodes
(image/video/text/audio/motion), and outputs (END), wired on the canvas.

Two ways to build one:
1. **Manual** — drop nodes on the canvas and connect them.
2. **Text-to-flow** — the composer bar ("Describe what you want to create…")
   assembles a flow for you from a prompt (agentic pipeline authoring).

## How a workflow runs (two real template examples)

**A. "Create Animated Videos from Photos with Relight"** (612×1088):
> Upload a single photo → generate a short 9:16 animation → instantly create
> three relit versions: **Twilight, Sunny, Wind**.

Pipeline shape: one input → an animation step → a **fan-out** into three relight
variants. Tags name the engines it chains: `photo_to_video`, `relight`,
`ai_video`, `runway`.

**B. "Ethereal Studio Motion"** (720×1280):
> Upload your product packshot → place it in a clean studio scene with pastel
> poppy flowers → get a **2K 9:16 image** and a matching **4-second 720p MP4**.

Pipeline shape: product input → scene-composite (place subject in a generated
scene) → **two outputs of different media types** (a still + a motion video).
Tags: `ai photoshoot`, `product photography`, `motion effect`,
`cinematic product video`, `packshot`.

Both are: **input asset → generative transform(s) → fan-out into variants /
multi-format outputs**, across several models, in one graph.

## The catalogue

Workflows are organised by creative intent:
- Art, illustration & concept
- Design assets & elements
- E-commerce & product content
- Marketing & advertising
- Photo editing & enhancement
- Social media & creator content
- Stories
- Video & motion

Plus user collections (Product content, Brand design, Social content) and
"My content". Each template shows a preview (often a short video), a
description, tags, an output size, and a **"Use this workflow"** button that
opens it in the editor.

## Where MP Scene fits (reconciling the earlier doc)

The **Motion (Motion Graphics)** node is almost certainly backed by the **MP
Scene engine** analysed in `research/picsart-mp-scene/analysis.md` (scene
templates, looks, transitions, render). And the **Image** node is backed by the
same generative models we call directly (`picsart_generate` → Nano Banana Pro).
So the earlier analysis was not wrong — it was **one layer** (the motion/
compositing backend) of Flow. Flow is the orchestration product; the MCP
`picsart_*` tools we already use are the per-node engines underneath it.

## How Picsart Flow relates to landing-page-gen — this is the important part

**Picsart Flow is the first-party, productised analogue of our entire
orchestration.** Our `workflow.yaml` — a per-slot graph of creative steps
(generate → gate → compose) — is conceptually the *same object* as a Flow: a
pipeline of creative-step nodes. Picsart built the visual, human-facing version
of what we build headlessly for landing pages.

| | landing-page-gen | Picsart Flow |
|---|---|---|
| Form | Headless, agent-driven, YAML + code | Visual canvas, GUI, human-driven (+ text-to-flow) |
| Unit | `workflow.yaml` per slot | a Flow graph |
| Nodes | "generate panel", "lp-compose chrome", "gate" | Image / Video / Text / Audio / Motion (+ START/REF/END) |
| Orchestration | manager spawns workers; one model pinned (pro) | one canvas chains many models |
| Governance | preflight, credit-guard cap, ledger, blindness, gates | none exposed to us; runs in the product |
| Output | 20 slots injected into a page's HTML | one finished creative (still/video/set) |
| Corpus/quality | corpus-anchored, blind, reviewer-gated | trending-template driven, one-click remix |

**Reads and implications:**
1. **It validates our architecture.** Picsart independently converged on "chain
   creative-step nodes into a pipeline" — exactly what `workflow.yaml` encodes.
   The node kinds (Image/Video/Motion) match our slot families.
2. **Their productised patterns are our roadmap.** "Ethereal Studio Motion"
   (packshot → studio-scene composite → 2K still + motion) is precisely the
   layered-composite-then-animate pipeline we are designing — and it maps onto
   our `template-mockup`/`dark-composite` families plus a Motion step. The
   relight fan-out ("Twilight/Sunny/Wind") is our "anchor-and-vary" variation
   pass, named and shipped.
3. **The build-vs-adopt question sharpens.** We already call Flow's *underlying
   engines* directly over MCP (`picsart_generate` = Image node; `picsart_media_*`
   = Motion node). Two paths forward:
   - **Keep composing engines ourselves** (today) — full control, our gates,
     blindness, credit caps, corpus anchoring; more to build.
   - **Target Flow itself** — *if* Flow exposes an API / runnable templates
     (unconfirmed; the editor is login-walled and no public API surfaced), a
     landing-page slot could be expressed as a Flow and run, inheriting its
     orchestration. Unknowns: API access, per-run cost, and whether our
     governance (preflight caps, blindness, gates) survives inside it.

## Is Flow programmable? (MCP probe result)

I searched every connected Picsart MCP connector for a Flow / run-workflow /
pipeline tool. **There is none.** The Flow node-canvas product is **GUI-only**
from our integration standpoint. What the MCP surface *does* expose is:

1. **The per-node engines** we already call — `picsart_generate` (the Image
   node's model), `picsart_media_*` / `picsart_media_export` (the Motion node's
   MP Scene engine, renders mp4/png/still server-side).
2. **A parallel, guided video/film production pipeline** built as widget-board
   tools — its own "levels of creation and a pipeline", API-side:
   `picsart_film_setup` → `picsart_shotlist_board` (shots: size, lens, light,
   palette, move, length) → `picsart_asset_review` (approve/return each asset) →
   `picsart_generate {async}` → `picsart_render_monitor` (live batch progress) →
   `picsart_video_review` → `picsart_media_export` / `final_cut`, with
   `picsart_model_choice` / `picsart_model_catalog` picking the model per stage.

So the productised pipeline concept exists on BOTH surfaces: **Flow** (visual,
node-canvas, consumer) and this **film/video board pipeline** (MCP, agent-
drivable). The film pipeline is the closest thing to Flow we could actually
call — but it targets multi-shot video, not landing-page stills.

## What is confirmed vs. still unknown

**Confirmed (first-party UI):** node kinds and that each is a creative step;
canvas graph + text-to-flow authoring; workflows are reusable typed templates
with sizes; multi-model orchestration; fan-out and multi-format outputs; the
category catalogue; MP Scene as the Motion backend.

**Unknown (behind login / not public):** exact model catalogue per node; the
run/execution engine and whether nodes gate; whether the consumer Flow product
is API-addressable (its editor is GUI+login only); sharing/remix and versioning
mechanics; limits.

**Newly measured (2026-09-10):** authoring + rendering an MP Scene workflow (the
Motion-node engine) via MCP is real and worked end to end — `apply_scene_template`
→ `validate_scene` → `contact_sheet` preview → `picsart_media_export`. A 7.5 s
1080×1080 three-clip composite MP4 rendered for **0 credits** (balance unchanged
at 1996). So the **compositing/render layer is not billed to the generation
credit pool** (at least for this render), and it is **ungoverned by our hooks** —
unlike `picsart_generate`. Artifact: `runs/pilot-layered/sections/P01/mp-scene.json`,
output `…/steps/reel.mp4`. Motion presets attach at the layer level, not inside
media clip content (validator: media content accepts kind/assetId/fit/align/
trim/speed/loop/volume/muted/bounds).

## Addendum 2026-09-10 (later the same day): the two probes, answered

1. **Picsart API platform** (`picsart.com/api-platform/docs/api-reference`,
   `docs.picsart.io`): the platform exposes `POST /workflows/{workflow}/execute`
   (sync, ~20 s), `POST /workflows/{workflow}/submit` + `GET
   /workflows/{workflow}/{id}/result` (async), bearer `PICSART_API_KEY`,
   params wrapped in `params`, credits in `response.usage.credits`. But
   `{workflow}` is a **model name** ("193 models"): one model run per call,
   the layer our `picsart_generate` sits on. No graph, no user-defined
   workflow, no node. The docs index has no "Flow" product at all.
2. **Flow's own tutorial** (`picsart.com/tutorials/how-to-build-your-first-ai-workflow/`):
   the editor is at `picsart.com/create/workflows` → "Create new workflow";
   steps are Input ("upload image, text prompt, or blank canvas") →
   Processing ("generate, remove background, enhance, or apply effects") →
   Output ("export format and quality"); "Drag from one step's output to the
   next step's input"; "Choose AI models" per step; test steps singly; save,
   share, team templates on Business; running costs Picsart credits; branches
   and conditions exist for larger flows; batch processing.

**Verdict: GUI-only.** Flow is a design reference *and* the model our
workflows now follow (`research/flow-restructure/analysis.md`): agents author
boards in Flow's node model and run them on the engines the connectors
expose, and `lp-flow sheet` renders the board for a person to rebuild on the
canvas.

## Recommended next step (as written before the addendum)

Answer the one question that decides everything: **is Picsart Flow programmable,
or GUI-only?** Two cheap probes, no credits:
1. Check the MCP connectors for any Flow/run-workflow tool (search the deferred
   tool list for `flow`, `workflow`, `pipeline`, `graph`).
2. Check `docs.picsart.io` / developer docs for a Flow API or "run workflow"
   endpoint once web access is back.

If Flow is API-addressable, evaluate expressing one landing-page composite slot
as a Flow and running it, versus our current hand-rolled pipeline. If it is
GUI-only, Flow stays a *design reference* (its node model and its productised
pipelines guide our own `workflow.yaml` patterns) rather than an integration.
