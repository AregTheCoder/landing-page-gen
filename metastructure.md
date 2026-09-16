# Data metastructure

How every piece of data in `landing-page-gen` is organised: where it lives, what
shape it has, what writes it, and what reads it. This is the map; `plan.md` holds
the decisions behind it and `prd.md` the quality rules. Paths are relative to the
repo root.

There are four data estates:

1. **Corpus** (`corpus/`) — the measured, labelled record of existing Picsart
   pages. Committed selectively; the source of truth for what "on-brand" means.
2. **Library** (`library/`) — a generated, browsable projection of the corpus.
   Zero-byte hardlinks, gitignored, never hand-edited.
3. **Runs** (`runs/`) — one folder per generation job; the working set and the
   output. Mostly gitignored except the small text artefacts.
4. **Reference & research** (`corpus/references/`, `corpus/pool/`,
   `corpus/widened/`, `research/`, `docs/`) — external look-alikes and analysis
   that inform generation but are never wired into a node.

The code that produces all of it is one package, `src/landing_page_gen/`, exposing
three console scripts: `lp-corpus` (build 1 & 2), `lp-compose` / `lp-flow`
(run-time helpers), `lp-inject` (build 3).

---

## 1. Corpus — `corpus/`

The deterministic record built outside the agent loop. Pipeline:
**snapshot → sectionize → DB → measure → label → derive**. Each stage writes a
distinct artefact; later stages never mutate an earlier stage's file by hand.

### 1.1 Page snapshots — `corpus/pages/<slug>/`

One folder per page, slug = URL path with `/` → `--` (`ai-models--flux-3`).
Produced by `lp-corpus fetch` (Playwright + Python reassembly of the React stream)
and `lp-corpus media`.

| File | What | Committed |
|---|---|---|
| `raw.html` | HTML exactly as served | no |
| `page.html` | reassembled `<main>`, stamped `data-lp-section`/`data-lp`/`data-lp-t`, media rewritten to local `media/` copies, served URL kept on `data-lp-src`/`data-lp-poster` | no |
| `media/<stem>-<8hex><ext>` | every `img`/`video`/`poster` downloaded; 8 hex = hash of the source URL | no (~4 GB total) |
| `page.png` | full-page screenshot (content-visibility override injected) | no |
| `render.json` | per-element rendered geometry (slot sizes only exist after layout) | no |
| `meta.json` | `slug, url, title, family, fetched_at, rendered, media{ok,failed}` | **yes** |
| `sections.md` | the page as typed Markdown sections, one block per section | **yes** |

Families: `tool`, `ai-models`, `compare-models`, `ai-tool`, `hub`, `other`, `home`.
The inventory of all known paths is `corpus/pages.yaml` (from `lp-corpus discover`);
10 paths are client-side app shells with no snapshot (marked `shell`).

### 1.2 The index — `corpus/corpus.db`

SQLite + FTS5, rebuilt by `lp-corpus sectionize`. Never hand-edited; it is a
projection of the snapshots plus `styles.yaml`. Tables:

- **pages** — `id, slug, url, family, title, fetched_at, html_path, screenshot_path`
- **sections** — `id, page_id, sid, idx, type, headline, md, text_len, media_count, selector`
- **media** — `id, section_id, slot_id, kind, role, src, alt, width, height, aspect, nat_width, nat_height, duration, local_path, selector, style, attrs`
- **texts** — `id, section_id, tid, tag, text, href, selector`
- **sections_fts** (+ shadow tables) — BM25 over section Markdown, what `similar` queries.

Indexed on `media(src)`, `media(section_id)`, `sections(page_id)` and
`texts(section_id)`, added by `connect()` on every open, so `attrs`/`styles`
apply their ~3300 per-src updates by index seek, not a table scan.

`media.src` is the unwrapped CDN asset URL and is the **join key** across the whole
corpus — `attributes.yaml`, `styles.yaml` and `references/` are all keyed by it.
`media.role` gates spend: `creative`/`thumbnail` are generated; `ui-screenshot`,
`icon`, `decorative` are kept from source.

### 1.3 Measured & labelled attributes — `corpus/attributes.yaml`

One entry per distinct asset, keyed by CDN src. Two-layer provenance:
`lp-corpus attrs` writes only what the **pixels** settle (`ground`, `layout`,
`panel_count`, `aspect_class`, `size`, geometry); `lp-corpus sheets` + `labels`
add the **semantic** fields from labelling contact sheets, validated against the
enums (`art_style`, `chrome`, `subject`, `text_in_image`, `ui_mockup`,
`family_hint`, `confidence`). The `labelled:` list records which fields came from a
sheet. **Never hand-edit this file** — the enums are pinned across `attrs.FIELDS`,
`picsart-workflows/style-families.md` and `tests/test_styles.py` and move together.

A long measuring pass checkpoints to `corpus/attributes.partial.jsonl` (an
append-only delta, gitignored) instead of re-dumping the whole 2.4 MB file every
100 assets; a crashed pass resumes from it and the final `merge_save` folds it in
and unlinks it.

Supporting label data:
- `corpus/labels/<asset>.png` + `*.manifest.yaml` — contact sheets asking for the
  unresolved fields; `<asset>.answers.yaml` is the filled-in answer merged by
  `lp-corpus labels`.
- `corpus/frames/` — video still-frames grabbed for measuring/labelling.
- `corpus/taxonomy/` — cross-tab contact sheets (`<type>_<aspect>_<ground>_<layout>.png`)
  and `report.md` from `lp-corpus taxonomy`.

### 1.4 Derived style families — `corpus/styles.yaml`

One entry per asset (keyed by src): `style` (one of the 15 families),
`variant`, `confidence`, `page`, `slot`, `source`. Derived by
`lp-corpus styles --from-attrs` through a rule table, re-applied to `media.style`
after every `sectionize`. A chrome-unanswered family is marked `provisional` so a
measured-only guess cannot out-rank a verified example at retrieval time. This is
the file that connects a corpus asset to the vocabulary in the
`picsart-workflows` skill.

### 1.5 Flow templates — `corpus/flow-templates.yaml`

Gallery Flow boards keyed by family/device, offered to a worker by
`lp-flow templates` when one fits.

---

## 2. Library — `library/`

A **generated** browsable projection, rebuilt whole by `lp-corpus organise`
(atomic tmp-swap). Hardlinks, so zero bytes and no dangling refs; **gitignored**;
never hand-edited (relabel → regenerate → the asset moves folder). Every field in
a sidecar lives in a committed source.

```
library/
  INDEX.md
  Pages/<slug>/        page dossier: documents + full-page screenshot
  Images/
    general/           assets with no specific AI model
    by-model/<model>/  filed under the model that made them
      -> <art_style>/<structure>/<asset>  + a Markdown sidecar per asset
  Videos/  (same general / by-model split)
  Screenshots/
```

Three axes decide an asset's path: `model_of` (who made it), `art_style` (photo,
3d-render, flat-vector, painterly-illustration, anime-cartoon, collage,
typography, ui-screenshot, mixed), `structure_of` (coarse 9-way layout). The
sidecar restates the asset's attributes beside the file so a person or an agent
can read it without a query. Assets awaiting a label sit under `_unlabelled`.

---

## 3. Runs — `runs/<run>/`

One folder per generation job. `runs/current` is a symlink to the active run; its
existence is what arms the credit-guard hook. Text artefacts are committed;
generated pixels and the ledger are gitignored.

```
runs/<run>/
  skeleton.md          INPUT: page frontmatter + one H2 per section + a `slot`
                       block per media node + `> annotation:` lines. From
                       `lp-corpus skeleton`, hand-edited. (committed)
  slots.json           the DOM stamps every slot maps back to (for lp-inject)
  shared-context.md    brand/audience/style context shared to all workers
  budget.json          credit cap for the run
  sections/S01..Snn/
    brief.md           the manager's brief for this slot (family block + text)
    examples/          look-only corpus/pool excerpts: <n>-<slug>-<slot>.png + .md
    workflow.yaml      the Picsart Flow board: START, nodes (one kind/engine/model,
                       `in:` wiring, a gate each), END. lp-flow check'd before running.
    flow.md            rendered node sheet for the Flow canvas
    steps/             every intermediate + final pixel the board produced
    result.md          the worker's output contract (chosen asset, credits, verdict)
  ledger.jsonl         one row per paid call (URL, cost) — written by the hook
  report.md            OUTPUT: per-slot workflow, credits quoted vs spent, rounds, verdict
  contact-sheet.png    overview of the run's finals
  dist/index.html      OUTPUT: the snapshot with chosen media + text injected (lp-inject)
```

Data flow through a run: `skeleton.md` (+ `similar` examples) → worker authors
`workflow.yaml` → runs it → `steps/` + `result.md` → reviewer critiques →
manager writes `report.md` → `lp-inject` writes `dist/`. Examples and corpus refs
are read for the look only and are **never** wired into a node (`imageUrls`,
`startFrame`, `image`).

---

## 4. Reference, pool & research (look-only, external)

Never wired into a node; they widen what a family's photography can look like.

| Path | What | Written by | Keys / no paid calls |
|---|---|---|---|
| `corpus/references/<family>.yaml` + `_manifest.yaml` | Pexels/Unsplash photos and creators matching a family's photography | `/collect-references` → `reference-collector` | free |
| `corpus/pool/<family>.yaml` + `_hashes.yaml` | licensed stock, pHash-deduped vs corpus+pool, ranked; kept/dropped via sheets | `lp-corpus pool` | PEXELS/UNSPLASH keys |
| `corpus/widened/<family>.yaml` | reverse-image neighbours of the family's assets | `lp-corpus widen` | SERPAPI/GOOGLE_VISION key |
| `research/<topic>/` | design notes and analysis (MP Scene, Flow, layered photos, style gaps, context gap) | by hand | — |
| `docs/` | GitHub Pages: `index.html`, `progress.html` (every final across runs), `.nojekyll` | by hand | — |

`similar` can splice these in as look-only example files (`w<n>-widened.md`,
`p<n>-pool.md`), rotated per run by `--seed`.

---

## Invariants

- **CDN src is the universal key.** `media.src` joins the DB, `attributes.yaml`,
  `styles.yaml` and the reference files. Asset URLs are opaque handles — passed
  verbatim, never parsed.
- **8-hex basename is load-bearing.** It names the local media copy and is the
  stable identity across snapshot, library and examples.
- **Generated vs source of truth.** `library/`, sidecars, `corpus.db` and
  `dist/` are projections — regenerate them, never edit them. Hand-editable
  sources: `sections.md`, `meta.json`, `pages.yaml`, label `*.answers.yaml`,
  `skeleton.md`, the reference/research YAML.
- **Measured, then labelled.** `attrs` writes pixel-settled fields; `sheets`/`labels`
  add semantic ones; enums are pinned across three files and change together.
- **Look-only never becomes input.** Corpus, references, pool and widened assets
  inform the prompt; they are never node inputs.
- **A run's spend is auditable.** Every paid URL is in `ledger.jsonl`; `report.md`
  reconciles quoted vs spent against the `picsart_credits` delta.
- **The corpus is verifiable.** `lp-corpus doctor` is the machine check of this
  document: every snapshot indexed, every generated asset measured, `styles.yaml`
  derived from `attributes.yaml` and mirrored into `media.style`, every label
  inside its enum, the pool well-formed. Run it after a scrape (and in CI); an
  ERROR means a stage was skipped or a source hand-edited, and it exits non-zero.
  A new page conforms to this format by passing through the full pipeline and
  clearing `doctor` — that is the intake contract.
