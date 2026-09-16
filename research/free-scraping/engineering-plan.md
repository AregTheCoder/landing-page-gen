# Free corpus expansion — optimal plan (accuracy · allocation · cost · API)

> **STATUS 2026-09-16 — ALL 9 STEPS BUILT AND RUN.** 168 tests green.
> Live run 1 (cinematic-still) is complete: 6 API requests, 474 candidates,
> 36 sheets reviewed by agents, 253 kept, calibrated.
> **Findings and corrections: `research/free-scraping/live-run-1.md`** — read
> that first, it supersedes several assumptions below.
>
> Headline: **the ranker barely works (AUC 0.596)** — the threshold skips only
> 7.2% of the pile, not the ~50% assumed here. Search-term quality is 2x more
> predictive (0.42–0.91 keep rate across six terms). Recommendation: keep the
> score as a sort order, retire it as a filter, and spend the effort on terms.
> Five bugs found and fixed live (span collapse, embed-cache thrashing,
> per-creator flooding, YAML answer format, best_family reporting).
>
> **NOTHING IS COMMITTED.** `corpus/pool/` and the four new modules are
> untracked on branch `template-standards`.
>
> Copied here from `~/.claude/plans/form-the-optimal-plan-zazzy-quokka.md`
> (2026-09-16) so it lives beside the sources it implements and the run that
> tested it. Siblings: `plan.md` (which free sources and why),
> `live-run-1.md` (what the first live sweep actually found).

## Context

Areg wants to grow the reference tiers (`corpus/pool/`, `corpus/widened/`) with
scraped stock images that look like the 2740 Picsart corpus assets, at $0,
optimised for: fidelity to the 15 style families, correct allocation into the
corpus tiers, zero credit spend, and efficient free-tier API use.
`research/free-scraping/plan.md` (2026-09-16) chose the sources; this is the
engineering design that makes the intake *accurate* and *cheap*.

**What exploration established** (drives every choice below):
- The pool pipeline (`pool.search → dedupe → score → sheets → kept → pick`) is
  built and tested but has **never run live**: `corpus/pool/` holds only
  `_hashes.yaml`, no API keys are set, and `pool.py`/`stock.py`/`phash.py`/
  `tests/test_pool.py`/`corpus/pool/` are **untracked** on branch
  `template-standards`. The redesign lands on those uncommitted files.
- **The ranker judges the wrong thing.** Mutual information vs family over the
  2039 tagged assets (H=2.97 bits): `chrome` 62 %, `ui_mockup` 33 % — both are
  Picsart *compose chrome* that never appears in a stock photo. `aspect_class`
  carries 33 % for free from w/h but is only a filter in `pick`, never scored.
  `ground`+`layout` (all `pool.score` uses) reach ~0.8 bits and are degenerate
  for the two largest families: full-bleed (756, zero 9:16) and cinematic-still
  (360, 100 % 9:16) differ *only* by aspect. Six families have <50 assets;
  31 of the 32 `provisional` (chrome-unanswered) tags sit in full-bleed.
- **API hygiene is absent**: `stock.fetch_json` has no retry/backoff/pacing/
  cache/budget; a 429 on one platform aborts *all* platforms; one page per term.
  **The hooks cannot help** — they match only `mcp__*__picsart_*`; `uv run`
  HTTP is invisible, uncapped, unledgered. Discipline must live in the clients.
- **Cost model**: Picsart credits $0 (no paid connector touched); third-party $0
  inside free tiers. The real costs are review tokens (linear in candidates
  sheeted), disk, and engineering days. **Ranker precision is the primary cost
  lever** — every wasted sheet cell is paid in tokens.

## Decisions (locked with the user)

1. **CLIP approved as an optional dependency group** `[embed]` — reverses
   `plan.md:83` ("no CLIP"); logged in plan.md/prd.md. Core install unchanged.
2. **Sheet review is agent-labelled** (like `/label-corpus`); human spot-checks.
3. **Images first; video is phase 2** (leave a `kind` seam only).

## Architecture

```
references/<family>.yaml (search_terms, photography.genre)
        │ terms, quota ∝ √(n_max/n_family)
        ▼
 stock.SEARCH[pexels|unsplash|pixabay] ──► apiclient.Client ──► ledger (_api.sqlite: cache + request log)
        │ normalised records (id,url,image,thumb,creator,licence,w,h)
        ▼
 prefilters (id dup, min_width, orientation)  — zero bytes
        ▼
 fetch_thumb (≤480px PNG, corpus/pool/thumbs/)  — CDN bytes, not API requests
        ▼
 dhash dedupe (corpus ≤10, pool ≤6)  ──► Ranker[clip|histogram] scores ALL 15 families
        ▼
 allocate: argmax w/ margin, searched family as prior ──► exactly one <family>.yaml, state pending
        │ below calibrated threshold → dropped unsheeted (10% exploration slice kept)
        ▼
 anchored contact sheets ──► /review-pool (agents write .answers.yaml) ──► pool labels
        ▼
 pool calibrate ──► _calibration.yaml (threshold, per-term keep-rate) ──► feeds search depth + quota
        ▼
 pick (kept, tier=pool) ──► similar --pool ──► p<n>-pool.md   (read, never wired)
```

Tier routing: known licence → `pool` (servable); unknown → `widened` (look-only,
never kept/served). Nothing scraped ever enters `attributes.yaml`/`corpus.db`.

---

## Part A — API efficiency and cost control

### A1. `corpus/apiclient.py` (new, stdlib only)
Transport + backoff + sliding-window limiter + `Client`. Not named `http.py`
(shadows stdlib).

```python
UA = "lp-corpus/0.1 (landing-page-gen stock pool)"
LIMITS = {"pexels": [(200, 3600), (20_000, 30*86400)],
          "unsplash": [(50, 3600)],            # UNSPLASH_PRODUCTION=1 -> [(1000, 3600)]
          "pixabay": [(100, 60)]}              # flickr/openverse: phase 2
SAFETY = 0.9; MIN_INTERVAL = {"pixabay": 0.6, "default": 0.25}
MAX_ATTEMPTS = 4; MAX_WAIT = 120; RESERVE = 2
class RateLimited(Exception)     # moves here; stock.RateLimited aliases it
class BudgetExceeded(Exception)  # (platform, retry_at)
class AuthError(Exception)       # 401/403 -> skip platform
class Unavailable(Exception)     # 5xx/timeout after MAX_ATTEMPTS
def urllib_transport(url, headers, timeout=60) -> (status, headers, bytes)
def from_fetch(fetch) -> transport          # adapts legacy fetch(url, headers=None) stubs
class Limiter(limits, safety, min_interval, clock)   # not_before / hint(Retry-After, X-Ratelimit-*) / wait_for
class Client(transport, ledger, limiter, clock, sleep, rng, run_id, max_requests, refresh, log)
    def fetch_for(platform, cacheable=True) -> fetch(url, headers=None)   # the seam stock.*_search take
    stats[platform] = {requests, cache_hits, waits, wait_s, retries, stopped}
```
`Client.get` order: cache-key (secret `key=` stripped) → cache read (honour
`MIN_TTL` under `--refresh`) → per-run `max_requests` → window counts from the
ledger → sleep or `BudgetExceeded` if wait > `MAX_WAIT` → transport → log row
(429/5xx count against windows too) → 2xx cache+return / 401-403 `AuthError` /
429 hint+retry / 5xx backoff 1,2,4 s × jitter. Sliding window over the
*persistent* log, not an in-memory bucket: a resumed run after a crash cannot
re-trip the hour cap. Tests inject `transport`, `FakeClock().time/.sleep`, `rng`.

### A2. `corpus/ledger.py` (new) — one gitignored sqlite `corpus/pool/_api.sqlite`
Tables `responses(cache_key PK, platform, endpoint, params, status, body,
fetched_at)` and `requests(platform, endpoint, ts, status, cached, attempt,
remaining, run_id)`. `TTL` 7 d (Flickr ≤24 h later); `MIN_TTL = {"pixabay":
86400}` (ToS requires 24 h caching). Only 2xx cached; cache hits logged but
excluded from window counts. The `requests` table **is** the budget — no
separate `_budget.yaml`. `append_run(report)` → committed `corpus/pool/_runs.jsonl`.
Re-runs inside TTL cost zero requests; a crash loses nothing (ids are written at
the end, pages replay from cache).

### A3. `stock.py` changes
- `PLATFORMS += ("pixabay",)`, `KEYS["pixabay"] = "PIXABAY_API_KEY"`,
  `PER_PAGE = {"pexels": 80, "unsplash": 30, "pixabay": 200}` — always request
  the platform max; requests cost the same at any size.
- `page=1` param on all clients. `pixabay_search(term, key, per_page, orientation,
  page, min_width, fetch)`: `image_type=photo, safesearch=true`, orientation
  `horizontal|vertical`; record maps `pageURL, largeImageURL/webformatURL, user,
  user_id`. Emits `licence: "pixabay"` (controlled key, see C2).
- Thumb renditions (must satisfy 256 px measure/CLIP and 320 px sheet cell,
  stored ≤480 px): Pexels `src.large`; Unsplash `urls.raw + &w=640&h=640&fit=max
  &q=75&fm=jpg` (keeps `ixid`), fallback `urls.small`; Pixabay `webformatURL`
  (640; `largeImageURL` is the "mass download" the ToS forbids).
- `keys_available(platforms, keys) -> ({platform: key}, [missing])` — replaces
  the eager `key_for` loop at `pool.search:185`; a missing key **skips that
  platform with a warning**; `ValueError` only when no platform has a key.
- `SEARCH_VIDEO = {}` left as the phase-2 seam.

### A4. `pool.search` loop rewrite (breadth-first, isolated, budgeted)
```
for page in 1..pages:                        # every term sees page 1 before any sees page 2
  for platform in live - stopped:
    for term in terms - done:
      if page > 1 and not deepen(family, term, page, calibration): done.add; continue
      try: photos = SEARCH[platform](..., per_page=PER_PAGE[pf], page=page, fetch=client.fetch_for(pf))
      except (RateLimited, BudgetExceeded, AuthError, Unavailable): stopped.add(pf); break   # isolation
      except ClientError: done.add((pf, term)); continue
      n_new = admit(photos)                  # A5
      if short page or admitted >= limit_per_term or n_new < YIELD_FLOOR*len(photos): done.add
```
`--limit-per-term` (default 30) now means *admitted candidates per (platform,
term) per run*; `--pages N` (default 1 = today's behaviour). `deepen()` reads
`_calibration.yaml` via `calibration.keep_rate_for(cal, family, term)`: no
record → page 2 only ("explore once"); `keep_rate ≥ KEEP_FLOOR (0.25)` → up to
`--pages`; else stop. `stats["rate_limited"]` stays a bool.

### A5. Pre-download filters (metadata only, zero bytes) — counted in stats
1. no `image` → `no_image`; 2. id in any family yaml or in `raw` → `dup_id`;
3. `width < MIN_WIDTH (1200)` → `min_width` (Pixabay also server-side);
4. **orientation bucket** not in the family's allowed set → `aspect`. Buckets
   landscape (w/h ≥ 1.15) / square / portrait (≤ 0.87), allowed when ≥ 5 % of the
   family's tagged assets; square always passes (crops to 5:4 losing ~20 %).
   Class-exact matching would reject nearly all stock (3:2 vs corpus 1:1/5:4).
5. `auto_orientation`: when one bucket holds ≥ 80 % of the family and
   `--orientation` is unset, pass it to the API — cinematic-still never downloads
   a landscape page. Measured: cinematic-still 100 % portrait, model-card 100 %
   landscape, full-bleed 55/30/14 (all three allowed).

### A6. Thumbs, never-re-sheet, observability
- `fetch_thumb` keeps its contract; counts `thumb_bytes`; cleans `.bin`/`.part`
  on failure; `ThreadPoolExecutor(6)` (CDN bytes are not API requests). Reuses
  `media.download` (`.part` → `os.replace`, UA). ~3.5 GB per 10k candidates as
  PNG in gitignored `corpus/pool/thumbs/`.
- `build_sheets` stamps `entry["sheet"]` **at build time** and skips entries
  already carrying `sheet` unless `--resheet` → review tokens ∝ `new`, not pool size.
- `stats` gains `platforms[pf] = {requests, cache_hits, waits, wait_s, retries,
  stopped, pages, results, prefiltered{no_image,min_width,aspect}, dup_id,
  admitted, thumb_bytes, thumb_failed, errors}`, `skipped_platforms`,
  `dropped_by{corpus,pool,threshold}`, `auto_dropped`, `moved`, `elapsed_s`,
  `run_id`, `dry_run`. Printed as a table; appended to `_runs.jsonl`.
- `pool.plan(...)` / `--dry-run`: walks the same loop, asks the cache without
  writing, prints per platform `planned / cached / to_fetch / hour x/cap /
  month x/cap / ok`, makes no calls.

### A7. CLI flags (`cli.py`)
`pool search [family|--all] --pages N --dry-run --refresh --max-requests N
--min-width N --keep-floor F --platform {pexels,unsplash,pixabay,all}
(append; default all, replaces both) --resheet --rank {clip,histogram}
--quota BASE --explore F --no-threshold`; new stages `pool embed [--refresh|
--describe]`, `pool calibrate [family] [--write] [--family-check]`, `pool quota`.

---

## Part B — Accuracy: the ranker

### B1. `corpus/embed.py` (new) — CLIP behind `[embed]`, incremental cache
```toml
[project.optional-dependencies]
embed = ["open_clip_torch>=2.24", "torch>=2.2"]
```
```python
MODEL, PRETRAINED = "ViT-B-32", "laion2b_s34b_b79k"   # tag ViT-B-32__laion2b_s34b_b79k
EMBED_DIR = Path("corpus/pool/_embed"); BATCH = 64; KINDS = ("image",)   # phase 2: + "video" (posters in corpus/frames)
INSTALL_HINT = "CLIP ranking needs the optional extra: `uv sync --extra embed` (~1 GB with weights)"
def available() -> bool; def device() -> "mps"|"cpu"
def load_encoder(...) -> Encoder        # lazy import; ImportError(INSTALL_HINT)
class Encoder(Protocol): name, dim; images(paths) -> (n,dim) float32 L2-normalised; texts(...)  # seam only
def corpus_rows(attrs, styles, kinds)   # tagged, NON-provisional, kind in kinds, local exists; key = local|mtime_ns|size
def corpus_embeddings(encoder, ..., refresh=False) -> CorpusEmbeddings(ids, families, vectors)
def candidate_embeddings(encoder, thumbs: {eid: Path}, ...) -> {eid: vec}
def describe(...)
```
On disk `corpus/pool/_embed/<tag>/{corpus,candidates}.npy` (float16) +
`.json` rows. **Invalidation** (the point where it must not copy write-once
`_hashes.yaml`): recompute `corpus_rows()` every call, keep rows whose `key` is
unchanged, embed only new/changed, drop vanished, always refresh `family` from
the current styles mapping. Compute fp32 on MPS (fp16 LayerNorm NaN risk); only
storage is fp16. Tests inject a `FakeEncoder(dim=8)` (mean-colour vector) —
no torch in the test suite. `.gitignore` += `corpus/pool/_embed/`.

### B2. `Ranker` protocol + registry in `pool.py`
```python
class Ranker(Protocol):
    name: str; cross_family: bool
    def prepare(self, family, attrs_mapping, styles_mapping, log): ...
    def score(self, thumb, features, aspect_w_h) -> {family: (score, nearest_ids)}
class HistogramRanker   # today's baseline()/score() moved, maths unchanged; cross_family=False
class ClipRanker(encoder=None, cache_dir, refresh)       # prepare() builds all-family baselines once per process
RANKERS = {"histogram": HistogramRanker, "clip": ClipRanker}
def make_ranker(name=None, encoder=None, log) # None -> clip if available else histogram (logged once)
```

### B3. CLIP score for family f, candidate v
```
K_f      = clamp(n_f // 8, 3, 8)                          # vs-two-up 12->3, model-card 61->7, full-bleed 665->8
sim_f    = mean(top-K_f cosine(v, f's non-provisional vectors))
sim_f'   = (n_f·sim_f + M·sim_all)/(n_f + M), M=8      # shrink thin families toward whole-corpus top-8
clip_part   = clip((sim_f' - bg_f)/(self_f - bg_f), 0, 1)  # self_f = LOO tightness of f; bg_f = other families' assets vs f
aspect_part = p_f(aspect_class)/max_a p_f(a)              # Laplace α=0.5 over ASPECT_CLASSES; normalised so spread families aren't penalised
field_part  = today's freq mean over RANK_FIELDS.get(f, ("ground","layout"))
score_f  = gate_f(w/h, features) · (0.60·clip_part + 0.25·aspect_part + 0.15·field_part)
nearest  = the K_f corpus asset ids behind sim_f            # 8-hex ids -> pick()'s blindness scan keeps working
```
Weights are a prior, revised only from `calibrate` output (no auto-fit under
200 labels). Text-side zero-shot prior against `photography.genre`: **rejected
for v1** (subject-noun bias, 77-token truncation); `Encoder.texts` kept as seam.

**Gates** (multiplicative 0/1, never terms) — **on ratio bands, not exact class**
(`sectionize.aspect_class` snaps to the nearest of 14 classes, so exact `9:16`
would reject croppable 2:3 portraits):
```python
RATIO_GATES = {"cinematic-still": lambda r: r <= 0.80,   # 3:4, 2:3, 9:16 -> crop to 9:16 loses <= ~16% width
               "full-bleed":      lambda r: r >  0.60}   # excludes near-9:16 (corpus full-bleed has zero 9:16)
# measured before_after=True -> 0 for every family (the worker builds the split)
```
Resolves the full-bleed/cinematic-still degeneracy by construction. Test pins
the gate to `taxonomy.family_of` (a `photo-full-bleed/single/9:16/gallery`
record → cinematic-still).

Entry additions: `ranker`, `searched_family`, `tier`; clip-only `family_scores`
(top-3), `best_family`, `moved_from`.

---

## Part C — Allocation

### C1. Cross-family allocation (in `search`, clip only)
Score every family; **allocate to argmax with a margin**, searched family as
prior: move when the searched family is gated to 0, or `best − searched ≥
REALLOC_MARGIN (0.10)`; else stay, with `best_family` recorded for the
reviewer. `search` returns `(paths, stats)` — one yaml per family written;
`stats["moved"]`. Each eid lives in exactly one family yaml (`all_entries` is
pool-wide; test asserts `Σ len(entries) == len(all_entries())`).

### C2. Licence vocabulary + tier routing (`stock.py`)
```python
LICENCES = {"pexels": {label, attribution_required: False, url}, "unsplash": {...False}, "pixabay": {...False},
            "cc0": {...False}, "cc-by": {...True}, "cc-by-sa": {...True}, "unknown": {attribution_required: None}}
PLATFORM_LABELS = {"pexels": "Pexels", "unsplash": "Unsplash", "pixabay": "Pixabay"}; PLATFORM_HOSTS = {...}
def licence_key(value) -> str    # case-insensitive key-or-label lookup; else "unknown"
```
Clients emit **keys** (`licence: "pexels"`, not labels) + `attribution_required`.
`pool.load()` normalises legacy `Pexels` on read. Routing in `search`:
`unknown` → `tier: widened, state: dropped, drop: "licence unknown: look-only
tier"`; else `tier: pool`. `pick` serves `tier == "pool"` only; `build_sheets`
skips widened. `write_examples` frontmatter `licence: pexels`,
`attribution_required: false`; credit line `Photo by {creator} on {platform}
({label}[; attribution required])`. `tests/test_styles.py` pool pins →
`platform ∈ PLATFORM_LABELS.values()`, `licence ∈ LICENCES`, `kept ⇒ licence !=
unknown and tier == pool`, `family_scores` keys ⊆ `db.STYLES`.

### C3. Per-family quota (spend where the corpus is thin)
```python
QUOTA_BASE = 60
def quota(family, counts, base=QUOTA_BASE): return ceil(base * sqrt(max(counts.values()) / max(counts[family], 1)))
# full-bleed 60, template-mockup 115, before-after 193, dark-composite 324, vs-two-up 426  (per platform)
def plan_search(...)  # limit_per_term = clamp(quota / len(terms), 5, 80)
```
√ not 1/n (vs-two-up gets 7× full-bleed, not 50×). Once `_calibration.yaml`
exists, divide by the family's keep_rate (floor 0.1). `pool search --all`
iterates `db.STYLES` with per-family limits and orientation hints; `pool quota`
prints the table.

---

## Part D — Review and calibration loop

### D1. Anchored sheets (`build_sheets`, `prompt`, `parse_answer`, `ingest_labels`)
- Row 1 of every sheet = 3 corpus **anchors** (family's most central
  non-provisional images by LOO similarity when the clip cache exists; else the
  ids most frequent in the chunk's `nearest`), captioned `ref <id>`; candidates
  `#1…#12` from row 2. `taxonomy.contact_sheet(items, per_cell=…)` truncates at
  `per_cell` → pass `per_cell = 12 + len(anchors)` and a caption lambda offset
  by `len(anchors)`. Manifest gains `anchors`, `genre` (the family's
  `photography.genre` prose), per-cell `family_scores/best_family/searched_family/explored`.
- `prompt(family, references_dir)` includes the genre prose verbatim, "row 1 is
  three Picsart originals — the target, not candidates", and the answer format:
  `keep | drop | {keep: bool, subject?, best_family?, note?}`.
- `parse_answer`: `best_family ∈ db.STYLES` else error; `note ≤ 120 chars`.
- `ingest_labels`: `best_family ≠ sheet family` → remove from this yaml, insert
  into `best_family`'s with `moved_from`, `score = family_scores.get(best)`,
  state `kept` if keep else `pending`; `nearest` recomputed from the clip cache.

### D2. `.claude/skills/review-pool/SKILL.md` (new, `disable-model-invocation: true`)
Copied section-for-section from `label-corpus/SKILL.md`: §1 build (`pool
search` optional, `pool sheets <family>`, read `README-<family>.md`); §2 fan out
one subagent per sheet, ≤8 at a time, task quoted with pool paths and the
keep/drop/best_family format, "leave a cell out if you cannot judge"; §3 merge
(`pool labels`); **§4 (new)** `pool calibrate <family> --write` and report
threshold / would_skip / prune candidates / family_check. Rules: never hand-edit
`corpus/pool/*.yaml`; `best_family` only from `db.STYLES`; no `pool search`
while a merge is in flight. `label-corpus` untouched.

### D3. `corpus/calibration.py` (new, small) + `pool calibrate`
Labelled set = entries with `sheet` set **and** state kept/dropped by an answer
(auto-drops and dup-drops excluded). Writes `corpus/pool/_calibration.yaml`
(committed) only with `--write`:
```yaml
generated: 2026-09-16   min_labels: 30   target_recall: 0.95
rankers:
  clip:
    labels, keep_rate, auc, precision_at: {12,24,48}, deciles: [{lo,hi,n,kept}]
    threshold: 0.34          # largest score edge keeping >= target_recall of kept
    threshold_recall, would_skip
    families: {cinematic-still: {labels, keep_rate, auc, threshold}, full-bleed: {..., threshold: null}}  # < min_labels -> global
    terms:  {full-bleed: {"surreal miniature photography": {n, kept, keep_rate, prune: true}}}   # ONE shape, read by deepen() too
    platforms: {Pexels: {n, keep_rate}, ...}
  histogram: {...}
family_check: {method: leave-one-out top-K over corpus embeddings, n, argmax_vs_tag,
               argmax_vs_tag_merged_photo, argmax_vs_hint, hint_vs_tag, confusion}
```
Accessors: `load()`, `threshold_for(cal, ranker, family)`,
`keep_rate_for(cal, family, term)` (used by `search.deepen`). Prune rule
`n ≥ 20 and keep_rate < 0.1` — **report only**; terms belong to
`corpus/references/` (`/collect-references`). Per-family threshold when `labels
≥ 30`, else the ranker's global; none under 30 labels total.

**How `search` consumes it**: below `threshold_for` → `state: dropped, drop:
"below calibrated threshold 0.34 (clip, <date>)"`, never sheeted — except a
deterministic **exploration slice** `--explore 0.10` (`sha1(eid)` bucket,
flagged `explored: true`) so the threshold cannot become self-confirming.
`--no-threshold` disables. Histogram ranker: nothing is ever auto-dropped.

**Non-circular check** (`--family-check`): LOO argmax family per tagged corpus
image vs (a) styles tag, (b) `family_hint`, (c) hint-vs-tag as the ceiling —
raw **and** with full-bleed∪cinematic-still merged (hint agrees with tag only
~49 %, 11 % on cinematic-still: labellers called every vertical full-bleed).
Vision-neighbour check is a hook `family_check(..., widened_dir=None)`, active
once `widen --backend vision-web` has produced yamls (phase 2).

---

## Reconciliations between the two halves (decided here)
1. **Licence values are keys** (`pexels`, `pixabay`), never labels; `licence_key()` normalises.
2. **One `_calibration.yaml` shape** (D3); `search.deepen` reads it through `calibration.keep_rate_for`.
3. **Gates on ratio bands** (B3), prefilter on orientation buckets (A5): the prefilter saves bytes coarsely, the gate decides family finely; a 2:3 portrait passes both for cinematic-still.
4. **`sheet` stamped at build time** (A6); calibration's labelled set additionally requires an answered state.
5. **`search` returns `(paths, stats)`**; CLI prints one line per family written.

## Phase 2 (deferred, seams left)
Video (`SEARCH_VIDEO`, `embed.KINDS += "video"`, posters via `attrs.grab_frames`
— Playwright grabber, no ffmpeg VP9); Openverse/Flickr clients (`LIMITS`
entries, `licence` cc keys already in vocabulary); Vision drip (`widen
--backend vision-web`, 1000 free/mo, monthly cron) feeding `family_check`;
`library.organise(..., pool_entries=None)` once kept > 100; fix write-once
`_hashes.yaml` with the same fingerprint approach.

## Files

**New**: `src/landing_page_gen/corpus/apiclient.py`, `ledger.py`, `embed.py`,
`calibration.py`; `.claude/skills/review-pool/SKILL.md`;
`tests/test_apiclient.py`, `tests/test_embed.py`.
**Changed**: `corpus/stock.py`, `corpus/pool.py`, `corpus/cli.py`,
`pyproject.toml` (`[embed]` extra), `.gitignore` (`corpus/pool/_api.sqlite*`,
`corpus/pool/_embed/`), `tests/test_pool.py`, `tests/test_styles.py`,
`CLAUDE.md`, `plan.md`, `prd.md`.
**Reused as-is**: `measure.pixels` (256 px, composite on white) for both
histogram and CLIP input; `phash.dhash_pair`/`hamming`; `media.download`
(`.part`→`os.replace`); `similar.to_png` (≤480 px); `taxonomy.contact_sheet`;
`sectionize.aspect_class`/`ASPECT_CLASSES`; `attrs.asset_id`/`load`;
`styles.load`; `db.STYLES`; `pool.reference_terms`; `unsplash_track_download`
(now through the paced client, `cacheable=False`).

## Docs (exact text)
- **plan.md row (2026-09-16)** — "Pool ranker on CLIP, optional": RANKERS =
  histogram (unchanged) + clip (ViT-B/32 laion2b, fp32 MPS, `[embed]` extra);
  score 0.6 calibrated top-K cosine to the family's non-provisional stills
  (K=n/8 in 3..8, shrunk by 8 pseudo-counts) + 0.25 aspect typicality + 0.15
  ground/layout, gated by aspect ratio band and measured before/after; scored
  against all 15 families, allocated to argmax when gated or trailing ≥0.10;
  anchored agent-reviewed sheets (`/review-pool`) with `best_family`; `pool
  calibrate` → auto-drop threshold at 95 % recall with a 10 % exploration
  slice; `pool quota` ∝ √(n_max/n). **Rationale**: reverses 2026-09-10 "no
  CLIP" because the sheet pass is agent-labelled — tokens, not a human hour,
  are the cost, and a ranker that only *orders* the pass saves none; pHash/
  histograms cannot tell full-bleed from cinematic-still. Text prior rejected.
- **plan.md row (2026-09-16)** — "Stock API traffic is metered by the code":
  `apiclient`/`ledger` sliding-window caps at 90 % of each free tier, backoff
  honouring Retry-After/X-Ratelimit-*, 7-day cache (Pixabay ≥24 h by ToS),
  `--max-requests`, `--dry-run`, `_runs.jsonl`; hooks only see `picsart_*`.
- **prd.md bullets (2026-09-16)**: (1) ranker orders by fidelity to the
  family's own photography, never subject alone; auto-drop threshold only from
  agent answers at ≥95 % recall with an exploration slice; CLIP optional,
  histogram fallback never auto-drops. (2) every pool entry carries a controlled
  licence key + `attribution_required`; unknown licence → widened, never kept;
  one family yaml per entry, `best_family` moves it. (3) pool traffic is
  free-tier only, cached and capped in code; zero credits, zero spend.
- **CLAUDE.md**: `PIXABAY_API_KEY` in the key list ("missing keys skip that
  platform"); `pool embed/calibrate/quota`, `--rank`, `--pages --dry-run`;
  `uv sync --extra embed`.

## Implementation order (each step leaves the suite green)
0. *Recommend* committing the untracked pool baseline first so the redesign is a reviewable diff (Areg's call; not done by me).
1. `apiclient.py` + tests (pure, no sqlite) → `ledger.py` + tests → wire `Client`.
2. `stock.py`: `page`, `PER_PAGE`, thumb renditions, `pixabay_search`, `keys_available`, `LICENCES`/`licence_key`; test updates.
3. `pool.search` rewrite (isolation, pagination, prefilters, stats, dry-run, tier routing, `(paths, stats)`), `build_sheets` sheet-stamp; `cli.py` flags.
4. **First live sweep** (needs `PEXELS_API_KEY` at minimum): one family, `--pages 1 --dry-run` then live; confirms hygiene before any ranker work.
5. `pyproject [embed]`, `embed.py`, `tests/test_embed.py`; `Ranker` protocol, `HistogramRanker` (move), `ClipRanker` (baselines, gates, aspect), `make_ranker`, `--rank`, `pool embed`.
6. Cross-family allocation; anchored sheets + `prompt`/`parse_answer`/move-on-ingest; `review-pool` skill.
7. Agent review of the first sweep's sheets → labels.
8. `calibration.py`, `pool calibrate`, threshold + exploration in `search`, `deepen()`; `quota()`, `pool quota`, `--all`.
9. plan.md rows, prd.md bullets, CLAUDE.md.

## Verification
- `uv run pytest` green at every step (134 → ~160). New tests, house style
  (injected `fetch`/`transport`/`encoder`, `tmp_path`, fake clock, synthetic
  images, `log=lambda m: None`, idempotence asserted, no conftest):
  - apiclient: sliding window sleeps with fake clock; 429 + Retry-After then
    success; 5xx backoff caps attempts; cache hit = zero transport calls and
    expires; `--refresh` refetches Pexels but Pixabay stays cached <24 h;
    budget refusal isolates platforms; `X-Ratelimit-Remaining` sets not_before;
    `max_requests`; 401 → AuthError no retry; runs.jsonl append + prune.
  - pool/search: platform failure isolation; key-missing skips platform;
    breadth-first pagination + short/low-yield stop; deepen only calibrated
    terms; prefilters download nothing; auto-orientation; dry-run makes no
    calls; Pixabay parse + key redaction; thumb bytes counted / `.part`
    cleaned; already-sheeted skipped.
  - ranker/allocation: clip scores all families, gates ratio bands, moves a
    2:3/9:16 found via full-bleed into cinematic-still with `moved_from`,
    `Σ entries == all_entries`; before/after split gates to 0; ratio gate
    agrees with `taxonomy.family_of`; thin family shrinks toward global;
    histogram ranker unchanged (existing tests pass with `rank="histogram"`).
  - embed: incremental cache re-embeds only touched rows, re-tag updates
    family without re-embed, provisional excluded, `kind: video` skipped,
    ImportError names `uv sync --extra embed`, `make_ranker(None)` falls back.
  - sheets/calibrate: anchors + genre in manifest/README; `best_family` moves
    entry, invalid → error; calibrate writes deciles/threshold (recall ≥ 0.95)/
    prune/platform rates, idempotent with injected `today`; search auto-drops
    below threshold with reason, keeps ~10 % `explored`, `--no-threshold`
    keeps all; family_check LOO on FakeEncoder corpus = 1.0, merged bucket reported.
  - licence: `CC BY-NC` → `unknown` → widened/dropped, never sheeted/picked;
    legacy `Pexels` normalised; `write_examples` credit line + no 8-hex ids
    (blindcheck invariant kept).
- **End-to-end** (requires a real `PEXELS_API_KEY`; others optional):
  `uv run lp-corpus pool search cinematic-still --pages 1 --dry-run` (prints
  plan, zero calls) → live run → `_runs.jsonl` line, `cinematic-still.yaml`
  pending entries all portrait, `_api.sqlite` populated; re-run → `requests: 0,
  cache_hits > 0`; `pool sheets cinematic-still` → sheets with 3 anchors and
  genre in README; `/review-pool cinematic-still` → answers merged; `pool
  calibrate cinematic-still` prints threshold and family_check.
- `uv run lp-corpus pool embed --describe` reports model tag, rows per family,
  device; second run embeds 0 rows.

## Cost model (steady state)
- **Credits**: 0. **$**: 0 — no paid fallback exists in this path (Vision/
  Scraping Robot are separate modules, untouched).
- **Requests**: worst case 99 terms × 3 platforms × 3 pages = 891/sweep.
  Pexels 297/20,000 per month (1.5 %); Pixabay ~4 min at 90/min, no monthly
  cap; **Unsplash demo (45 usable/hr) is the binding constraint** → run one
  family per invocation (≤24/platform), 4 sweeps/month ≈ 1,200 req/platform/
  month; re-runs inside 7 days are free. Production Unsplash is 1000/hr today
  (docs), not 5000 — set `UNSPLASH_PRODUCTION=1` after approval.
- **Tokens**: first month ~2–2.5k cells after prefilters + 50 % threshold →
  ~200 sheets × ~3k ≈ 0.6 M tokens once; steady state ~40 sheets ≈ 120k/month.
  Never-re-sheet makes this ∝ `new`.
- **Disk**: ~3.5 GB thumbs per 10k candidates (gitignored); embed cache ~2 MB
  per 2000 rows; torch + weights ~1 GB once (`~/.cache/huggingface`).

## Risks
- **CLIP subject bias** (a portrait scores well against any portrait-heavy
  family regardless of grade): mitigated by the Picsart-photography baseline,
  self/bg normalisation, the bias-free aspect term, and a threshold set from
  reviewer answers — `calibrate`'s per-term table is where residual bias shows.
- **Self-confirming threshold**: exploration slice on by default.
- **`family_hint` as ground truth** agrees with tags only ~49 %; report the
  merged bucket and the hint-vs-tag ceiling or the check indicts the wrong party.
- **Unverified numbers**: Pixabay 500-hit cap, Pixabay URL expiry (fallback:
  one cached `api/?id=` refresh), Flickr per_page, Openverse quota — all phase 2
  or defensive.
- **Untracked baseline**: the pool tier has never been committed; step 0 is
  strongly recommended so this lands as a diff.
