"""The reference pool: licensed stock, unique, per style family.

The fourth reference tier. The corpus is Picsart's own pages, `references/`
is hand-verified stock URLs, `widened/` is licence-unknown reverse-image
neighbours; the pool is Pexels/Unsplash photos found by the family's own
search terms, deduplicated by perceptual hash against the corpus and against
itself, ranked against the family's measured look, and kept or dropped from
contact sheets like the label sheets. `similar --pool N --seed <run>` serves
kept entries into a brief's examples with a per-run rotation, so consecutive
runs see different on-style references. Pool images are look references
only: never uploaded, never passed as `imageUrls`, never injected."""

import datetime
import hashlib
import math
import random
import shutil
from collections import Counter
from pathlib import Path

import numpy as np
import yaml

from . import apiclient, attrs, calibration, db, embed, measure, phash, sectionize, stock, styles, taxonomy

POOL_DIR = Path("corpus/pool")
REFERENCES_DIR = Path("corpus/references")
POOL_DUP = 6     # hamming to another pool entry at or under this: the same photo twice
CORPUS_DUP = 10  # to a corpus asset: looser on purpose — a pool photo that IS a
                 # corpus source photo would hand a worker the page's own original
HIST_BINS = 4    # 4x4x4 = 64-bin RGB histogram, same 256 px copy measure uses
W_HIST, W_FIELDS = 0.7, 0.3
BASELINE_MAX = 200
NEAREST_K = 5
PER_SHEET = 12
ANCHORS = 3     # the family's own photographs at the top of every sheet: the target, not candidates
NOTE_MAX = 120
STATES = ("pending", "kept", "dropped")
# which measured fields say "usable for this family": before-after corpus assets
# measure `split`, but the photo a worker needs there is a plain single, so only
# the ground counts towards its rank
RANK_FIELDS = {"before-after": ("ground",)}
DEFAULT_RANK_FIELDS = ("ground", "layout")
MIN_WIDTH = 1200        # below this a photo cannot fill a slot, whatever it looks like
YIELD_FLOOR = 0.20      # a page admitting less than this share of new candidates ends the term
KEEP_FLOOR = 0.25       # a calibrated term under this keep rate never gets a second page
# Stock is mostly 3:2 and 2:3 while the corpus is mostly 1:1 and 5:4, so the
# prefilter matches on orientation (what a crop can still fix) rather than on
# aspect class (which would reject nearly everything usable).
LANDSCAPE_R, PORTRAIT_R = 1.15, 0.87
ORIENTATION_MIN_SHARE = 0.05   # a shape the family uses at least this often is allowed
AUTO_ORIENTATION_SHARE = 0.80  # a shape this dominant is asked of the API, not filtered after
EXPLORE = 0.10  # share of below-threshold candidates sheeted anyway, so the threshold stays falsifiable
# One shoot yields many near-identical frames: different pictures, so the
# perceptual hash passes them, and similar enough to score alike and land on
# one sheet. A live sweep put 8 of 12 cells on a sheet from three shoots,
# leaving four independent candidates — the rest was review spent twice.
MAX_PER_CREATOR = 3
QUOTA_BASE = 60         # candidates per platform for the largest family; thin ones get more
REALLOC_MARGIN = 0.10   # a candidate moves family only on a clear win, not on noise
W_CLIP, W_ASPECT, W_FIELDS_CLIP = 0.60, 0.25, 0.15
SHRINK = 8              # pseudo-counts pulling a thin family toward the whole corpus
K_MIN, K_MAX = 3, 8     # nearest-cluster size, scaled to the family (vs-two-up has 12 assets)
# `self - bg` is how far a family's own photographs sit from everyone else's:
# the normaliser, and also a confidence. It collapses for two opposite reasons
# — a family too small to estimate (outcome-tile, 16 assets, span 0.011) and one
# so broad it IS the background (full-bleed, 630 assets, span 0.029) — and in
# both cases dividing by it saturates every candidate to 1.0. Floor the divisor,
# and let no family below the floor RECEIVE a reallocation: if it cannot be told
# apart, moving a photo into it is not a judgement, it is noise.
SPAN_MIN = 0.05
# The two photo families are both one picture filling the frame and differ only
# by shape, so shape is a gate, not a score term. Bands, not aspect classes:
# `sectionize.aspect_class` snaps to the nearest of 14, which would reject a 2:3
# portrait that crops to 9:16 perfectly well.
RATIO_GATES = {"cinematic-still": lambda r: r is not None and r <= 0.80,
               "full-bleed": lambda r: r is None or r > 0.60}
# Two things a family needs from stock, and they are not interchangeable. BARE is
# the raw photograph that goes inside Picsart's chrome — the pool's original and
# default intake. LAYOUT is a picture that already carries an arrangement (a
# split, a grid, a collage, a mockup scene): a compositional reference for how
# the panels sit, which the bare intake scores 0 by design. Kept apart on every
# entry so a brief can ask for one without being served the other.
BARE, LAYOUT = "bare", "layout"
COMPOSITIONS = (BARE, LAYOUT)


def family_path(family, pool_dir=POOL_DIR):
    return Path(pool_dir) / f"{family}.yaml"


def load(family, pool_dir=POOL_DIR):
    path = family_path(family, pool_dir)
    data = (styles.load_yaml(path.read_text()) or {}) if path.exists() else {}
    data.setdefault("family", family)
    data.setdefault("entries", {})
    for entry in data["entries"].values():  # entries written before the vocabulary carry a label
        if entry.get("licence"):
            entry["licence"] = stock.licence_key(entry["licence"])
    return data


# A dropped entry is never sheeted, served or re-ranked again; calibration reads
# only its drop/term/family bookkeeping, so these ranking by-products are dead
# weight on disk. attribution_required and tier:pool are constants every reader
# already defaults, so they are never written.
_DROP_ON_DROPPED = ("nearest", "family_scores", "features", "thumb", "creator_url")


def _slim(entry):
    e = {k: v for k, v in entry.items()
         if k != "attribution_required" and not (k == "tier" and v == "pool")}
    if e.get("state") == "dropped":
        for k in _DROP_ON_DROPPED:
            e.pop(k, None)
    return e


def save(data, pool_dir=POOL_DIR):
    path = family_path(data["family"], pool_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    out = dict(data)
    out["entries"] = {eid: _slim(e) for eid, e in sorted(data["entries"].items())}
    path.write_text(styles.dump_yaml(out, sort_keys=False, allow_unicode=True, width=1000))
    return path


def all_entries(pool_dir=POOL_DIR):
    """{entry id: entry} across every family's yaml: an id found for one
    family is never re-fetched for another, and dedupe is pool-wide."""
    out = {}
    for path in sorted(Path(pool_dir).glob("*.yaml")):
        if path.name.startswith("_"):
            continue
        for eid, e in ((styles.load_yaml(path.read_text()) or {}).get("entries") or {}).items():
            out[eid] = e
    return out


def corpus_hashes(pool_dir=POOL_DIR, attrs_path=attrs.ATTRIBUTES_YAML, styles_path=styles.STYLES_YAML,
                  attrs_mapping=None, styles_mapping=None, refresh=False, log=print):
    """{src: {phash, family}} of every measured corpus asset, cached in
    `<pool_dir>/_hashes.yaml`.

    Incremental, not write-once. This file is what stops a stock photo that IS
    one of Picsart's own source images from entering the pool — it caught 23 of
    them in the first sweep — so a corpus that has grown since the file was
    written must not leave its new assets unprotected. Hashes only what is
    missing, drops what has gone, and rewrites only on a change."""
    path = Path(pool_dir) / "_hashes.yaml"
    cached = {} if refresh else ((styles.load_yaml(path.read_text()) or {}) if path.exists() else {})
    mapping = attrs.load(attrs_path) if attrs_mapping is None else attrs_mapping
    tags = styles.load(styles_path) if styles_mapping is None else styles_mapping
    out, hashed = dict(cached), 0
    for src, rec in mapping.items():
        family = (tags.get(src) or {}).get("style")
        keep = cached.get(src)
        if keep and keep.get("phash"):
            out[src] = {"phash": keep["phash"], "family": family}  # a re-tag costs no hashing
            continue
        local = rec.get("local")
        if not local or not Path(local).exists():
            continue
        try:
            out[src] = {"phash": phash.dhash(local), "family": family}
            hashed += 1
        except Exception:  # an unreadable file has no identity to protect
            continue
    # Add-only, and only ever from the mapping it was given: a hash kept for an
    # asset no longer in the corpus guards a photo that cannot reach a worker
    # anyway, while dropping rows would let an injected empty mapping erase the
    # file. `family` is provenance — dedupe reads only the phash — but it goes
    # stale across a re-tag, so it is refreshed for free while we are here.
    if out != cached:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(styles.dump_yaml(out, sort_keys=False, allow_unicode=True, width=1000))
        log(f"{path}: {len(out)} corpus assets ({hashed} newly hashed)")
    return out


def nearest_dup(h, hm, hashed, cap):
    """(distance, name) of the closest hash within cap, the mirror tried too.
    `hashed` is a list of (int-hash, name): the caller parses the corpus/pool
    hex once per search instead of this loop re-parsing it per candidate."""
    hi, hmi = int(h, 16), int(hm, 16)
    best = None
    for other, name in hashed:
        d = min((hi ^ other).bit_count(), (hmi ^ other).bit_count())
        if d <= cap and (best is None or d < best[0]):
            best = (d, name)
    return best


def histogram(path):
    """Normalised 64-bin RGB histogram of the same 256 px copy the corpus was
    measured on (alpha composited on white)."""
    rgb, _ = measure.pixels(path)
    q = np.clip((rgb * HIST_BINS).astype(int), 0, HIST_BINS - 1)
    idx = (q[..., 0] * HIST_BINS + q[..., 1]) * HIST_BINS + q[..., 2]
    counts = np.bincount(idx.ravel(), minlength=HIST_BINS ** 3).astype(np.float64)
    return counts / counts.sum()


def baseline(family, attrs_mapping=None, styles_mapping=None, sample=BASELINE_MAX):
    """The family's measured look: [(asset id, histogram)] over its tagged
    assets and the frequency of each measured ground/layout value."""
    attrs_mapping = attrs.load() if attrs_mapping is None else attrs_mapping
    styles_mapping = styles.load() if styles_mapping is None else styles_mapping
    srcs = sorted(src for src, tag in styles_mapping.items() if (tag or {}).get("style") == family)
    hists, freq = [], {f: {} for f in DEFAULT_RANK_FIELDS}
    for src in srcs:
        rec = attrs_mapping.get(src) or {}
        for f in freq:
            if rec.get(f):
                freq[f][rec[f]] = freq[f].get(rec[f], 0) + 1
        local = rec.get("local")
        if len(hists) < sample and local and Path(local).exists():
            try:
                hists.append((attrs.asset_id(src), histogram(local)))
            except Exception:
                continue
    freq = {f: {v: c / (sum(vals.values()) or 1) for v, c in vals.items()} for f, vals in freq.items()}
    return hists, freq


def score(hist, features, hists, freq, family):
    """(score, nearest corpus asset ids). Histogram intersection with the
    top-NEAREST_K nearest baseline assets — nearest cluster, not centroid,
    since a family's photography can be bimodal — plus how common the
    candidate's measured fields are in the family."""
    sims = sorted(((float(np.minimum(hist, h).sum()), aid) for aid, h in hists), reverse=True)[:NEAREST_K]
    hist_part = sum(s for s, _ in sims) / len(sims) if sims else 0.0
    fields = RANK_FIELDS.get(family, DEFAULT_RANK_FIELDS)
    field_part = sum(freq.get(f, {}).get(features.get(f), 0.0) for f in fields) / len(fields)
    return round(W_HIST * hist_part + W_FIELDS * field_part, 3), [aid for _, aid in sims]


# Each intake mode reads its own block of corpus/references/<family>.yaml: the
# bare photograph and the arrangement are found by different queries and
# described to a reviewer in different words.
REFERENCE_BLOCK = {BARE: ("photography", "genre"), LAYOUT: ("layout", "arrangement")}


def _reference_block(family, composition, references_dir=None):
    path = Path(references_dir or REFERENCES_DIR) / f"{family}.yaml"
    if not path.exists():
        return {}
    data = styles.load_yaml(path.read_text()) or {}
    return data.get(REFERENCE_BLOCK[composition][0]) or {}


def reference_terms(family, references_dir=None, composition=BARE):
    """The family's search terms for this intake mode."""
    return list(_reference_block(family, composition, references_dir).get("search_terms") or [])


def reference_genre(family, references_dir=None, composition=BARE):
    """What a reviewer is actually being asked to match: the photography genre
    for the bare intake, the arrangement for the layout one."""
    block = _reference_block(family, composition, references_dir)
    return (block.get(REFERENCE_BLOCK[composition][1]) or "").strip()


def family_locals(family, attrs_mapping=None, styles_mapping=None):
    """{asset id: local file} for the family's own assets that are on disk."""
    attrs_mapping = attrs.load() if attrs_mapping is None else attrs_mapping
    styles_mapping = styles.load() if styles_mapping is None else styles_mapping
    out = {}
    for src, tag in styles_mapping.items():
        if (tag or {}).get("style") != family or (tag or {}).get("provisional"):
            continue
        local = (attrs_mapping.get(src) or {}).get("local")
        if local and Path(local).exists():
            out.setdefault(attrs.asset_id(src), str(local))
    return out


def anchor_items(family, chunk, locals_by_id, n=ANCHORS):
    """The corpus assets to show above a sheet's candidates: the ones those
    candidates point at most often, so the reviewer sees the target the
    ranker was measuring against rather than a generic idea of the family."""
    counts = Counter(aid for _, e in chunk for aid in (e.get("nearest") or []) if aid in locals_by_id)
    picked = [aid for aid, _ in counts.most_common(n)]
    for aid in sorted(locals_by_id):
        if len(picked) >= n:
            break
        if aid not in picked:
            picked.append(aid)
    return [(aid, {"local": locals_by_id[aid]}) for aid in picked[:n]]


def thumb_path(eid, pool_dir=POOL_DIR):
    return Path(pool_dir) / "thumbs" / f"{eid}.png"


def fetch_thumb(entry_or_photo, dest, download, to_png, stats=None):
    """The eval copy: the 640 px rendition, re-encoded to PNG at example size.
    An interrupted fetch leaves no `.bin`/`.part` behind for the next run to
    mistake for a finished download."""
    if dest.exists():
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(".bin")
    try:
        download(entry_or_photo.get("thumb") or entry_or_photo["image"], tmp)
        if stats is not None and tmp.exists():
            stats["thumb_bytes"] += tmp.stat().st_size
        return to_png(tmp)
    except Exception:
        for stray in (tmp, tmp.with_suffix(".bin.part"), dest.with_suffix(".png.part")):
            try:
                stray.unlink()
            except OSError:
                pass
        raise


def orientation_bucket(w, h):
    """The crop-relevant shape of a photo: what a slot can still be cut from."""
    if not w or not h:
        return None
    r = w / h
    return "landscape" if r >= LANDSCAPE_R else "portrait" if r <= PORTRAIT_R else "square"


def family_orientations(family, attrs_mapping=None, styles_mapping=None, min_share=ORIENTATION_MIN_SHARE):
    """(allowed shapes, the one to ask the API for). Read from the family's
    own tagged assets: cinematic-still is 100% portrait, so it never downloads
    a landscape page; full-bleed uses all three and filters nothing."""
    attrs_mapping = attrs.load() if attrs_mapping is None else attrs_mapping
    styles_mapping = styles.load() if styles_mapping is None else styles_mapping
    counts = Counter()
    for src, tag in styles_mapping.items():
        if (tag or {}).get("style") != family:
            continue
        rec = attrs_mapping.get(src) or {}
        bucket = orientation_bucket(rec.get("width"), rec.get("height")) or _bucket_of_aspect(rec.get("aspect_class"))
        if bucket:
            counts[bucket] += 1
    total = sum(counts.values())
    if not total:
        return None, None  # nothing measured: filter nothing
    shares = {b: n / total for b, n in counts.items()}
    allowed = {b for b, share in shares.items() if share >= min_share} or set(shares)
    if "square" in allowed:
        allowed = allowed | {"square"}
    top, top_share = max(shares.items(), key=lambda kv: kv[1])
    return allowed, (top if top_share >= AUTO_ORIENTATION_SHARE else None)


def _bucket_of_aspect(aspect_class):
    """The orientation an aspect class implies, for records measured before
    width and height were kept."""
    if not aspect_class or ":" not in str(aspect_class):
        return None
    w, h = (int(x) for x in str(aspect_class).split(":"))
    return orientation_bucket(w, h)


class DirectFetcher:
    """The unmetered path: an injected stub in tests, or a bare client. The
    metered one is `apiclient.Client`, which has the same two members."""

    def __init__(self, fetch=None):
        self.fetch = fetch or stock.fetch_json
        self.stats = {}
        self.ledger = None

    def stat(self, platform):
        return self.stats.setdefault(platform, {})

    def fetch_for(self, platform, cacheable=True):
        return self.fetch


def platform_stats():
    return {"requests": 0, "cache_hits": 0, "waits": 0, "wait_s": 0.0, "retries": 0, "stopped": None,
            "pages": 0, "results": 0, "dup_id": 0, "admitted": 0,
            "prefiltered": {"no_image": 0, "min_width": 0, "aspect": 0, "licence": 0},
            "thumb_bytes": 0, "thumb_failed": 0, "errors": 0}


class HistogramRanker:
    """The 2026-09-10 ranker, unchanged: colour against the family's own
    assets. It orders a sheet; it cannot judge one family against another."""

    name = "histogram"
    cross_family = False

    def __init__(self):
        self.family = self.hists = self.freq = None

    def prepare(self, family, attrs_mapping=None, styles_mapping=None, log=print):
        self.family = family
        attrs_mapping = attrs.load() if attrs_mapping is None else attrs_mapping
        styles_mapping = styles.load() if styles_mapping is None else styles_mapping
        self.hists, self.freq = baseline(family, attrs_mapping, styles_mapping)

    def reliable(self, family):
        return False

    def score(self, thumb, features, ratio=None):
        sc, nearest = score(histogram(thumb), features, self.hists, self.freq, self.family)
        return {self.family: (sc, nearest)}


class ClipRanker:
    """How close a candidate sits to a family's *own* photographs.

    The similarity is calibrated per family — against how tightly the family
    holds together (`self`) and what a wrong-family photo scores (`bg`) — so
    the numbers mean the same thing across families and the argmax is a real
    comparison. A thin family is shrunk toward the whole corpus rather than
    trusted on a dozen assets, and shape is a gate rather than a term."""

    name = "clip"
    cross_family = True

    def __init__(self, encoder=None, cache_dir=embed.EMBED_DIR, refresh=False, composition=BARE):
        self.encoder, self.cache_dir, self.refresh = encoder, cache_dir, refresh
        self.composition = composition
        self.emb = None
        self.families = {}
        self._vecs = {}

    def prepare(self, family, attrs_mapping=None, styles_mapping=None, log=print):
        self.encoder = self.encoder or embed.load_encoder()
        # load once here; _freq/_fields/baseline below all reuse these mappings
        attrs_mapping = attrs.load() if attrs_mapping is None else attrs_mapping
        styles_mapping = styles.load() if styles_mapping is None else styles_mapping
        self.emb, _ = embed.corpus_embeddings(self.encoder, attrs_mapping, styles_mapping,
                                              cache_dir=self.cache_dir, refresh=self.refresh, log=log)
        vectors = self.emb.vectors
        if not len(vectors):
            return
        sims = vectors @ vectors.T
        np.fill_diagonal(sims, -1.0)  # leave-one-out: nothing is its own neighbour
        for fam in sorted({f for f in self.emb.families if f}):
            idx = self.emb.index_of(fam)
            n = len(idx)
            k = int(np.clip(n // 8, K_MIN, K_MAX))
            own = float(np.mean(self._topk(sims[np.ix_(idx, idx)], k))) if n > 1 else 1.0
            other = np.setdiff1d(np.arange(len(vectors)), idx)
            bg = float(np.mean(self._topk(sims[np.ix_(other, idx)], k))) if len(other) else 0.0
            self.families[fam] = {"idx": idx, "n": n, "k": k, "self": own, "bg": bg,
                                  "span": own - bg, "reliable": (own - bg) >= SPAN_MIN,
                                  "aspect": self._freq(fam, "aspect_class", attrs_mapping, styles_mapping),
                                  "fields": self._fields(fam, attrs_mapping, styles_mapping)}

    @staticmethod
    def _topk(matrix, k):
        """Mean of each row's top-k, the nearest cluster rather than a centroid."""
        if not matrix.size:
            return np.zeros(1)
        k = min(k, matrix.shape[1])
        part = np.sort(matrix, axis=1)[:, -k:]
        return part.mean(axis=1)

    def _freq(self, family, field, attrs_mapping, styles_mapping):
        attrs_mapping = attrs.load() if attrs_mapping is None else attrs_mapping
        styles_mapping = styles.load() if styles_mapping is None else styles_mapping
        counts = Counter()
        for src, tag in styles_mapping.items():
            if (tag or {}).get("style") != family:
                continue
            value = (attrs_mapping.get(src) or {}).get(field)
            if value:
                counts[value] += 1
        total = sum(counts.values())
        if not total:
            return {}
        classes = len(sectionize.ASPECT_CLASSES)
        return {v: (c + 0.5) / (total + 0.5 * classes) for v, c in counts.items()}

    def _fields(self, family, attrs_mapping, styles_mapping):
        _, freq = baseline(family, attrs_mapping, styles_mapping, sample=0)
        return freq

    def embed_all(self, thumbs, log=print):
        """Embed every candidate in one batched pass before scoring."""
        self._vecs, _ = embed.candidate_embeddings(self.encoder, thumbs, cache_dir=self.cache_dir,
                                                   refresh=self.refresh, log=log)

    def reliable(self, family):
        """May this family receive a cross-family move? Only if its own
        photographs are measurably distinct from everyone else's."""
        return bool((self.families.get(family) or {}).get("reliable"))

    def vector_for(self, thumb):
        for eid, vec in self._vecs.items():
            if str(thumb).endswith(f"{eid}.png"):
                return vec
        return self.encoder.images([Path(thumb)])[0]

    def score(self, thumb, features, ratio=None):
        """{family: (score, nearest corpus asset ids)} over every family."""
        if self.emb is None or not len(self.emb.vectors):
            return {}
        v = np.asarray(self.vector_for(thumb), dtype=np.float32)
        sims = self.emb.vectors @ v
        overall = float(np.mean(np.sort(sims)[-K_MAX:]))
        aspect = sectionize.aspect_class(*_ratio_size(ratio)) if ratio else None
        out = {}
        for fam, rec in self.families.items():
            if self.composition == BARE and features.get("before_after"):
                out[fam] = (0.0, [])  # a pre-split photo is not raw material, whatever it looks like
                continue
            gate = RATIO_GATES.get(fam)
            if gate and not gate(_ratio_of(ratio)):
                out[fam] = (0.0, [])
                continue
            own = sims[rec["idx"]]
            k = min(rec["k"], len(own))
            top = np.sort(own)[-k:]
            sim = float(top.mean())
            shrunk = (rec["n"] * sim + SHRINK * overall) / (rec["n"] + SHRINK)
            span = max(rec["self"] - rec["bg"], SPAN_MIN)
            clip_part = float(np.clip((shrunk - rec["bg"]) / span, 0.0, 1.0))
            freq = rec["aspect"]
            aspect_part = (freq.get(aspect, 0.0) / max(freq.values())) if freq and aspect else 0.0
            fields = RANK_FIELDS.get(fam, DEFAULT_RANK_FIELDS)
            field_part = sum(rec["fields"].get(f, {}).get(features.get(f), 0.0) for f in fields) / len(fields)
            total = W_CLIP * clip_part + W_ASPECT * aspect_part + W_FIELDS_CLIP * field_part
            nearest = [self.emb.ids[i] for i in rec["idx"][np.argsort(own)[-k:]][::-1]]
            out[fam] = (round(total, 3), nearest)
        return out


def _ratio_of(ratio):
    if not ratio or not ratio[0] or not ratio[1]:
        return None
    return ratio[0] / ratio[1]


def _ratio_size(ratio):
    return (ratio[0], ratio[1]) if ratio else (None, None)


RANKERS = {"histogram": HistogramRanker, "clip": ClipRanker}


def make_ranker(name=None, encoder=None, cache_dir=embed.EMBED_DIR, refresh=False,
                composition=BARE, log=print):
    """The named ranker, or the best available one: clip when the extra is
    installed, else histogram — which orders the sheets but auto-drops nothing."""
    if name is None:
        name = "clip" if (encoder is not None or embed.available()) else "histogram"
        if name == "histogram":
            log(f"  {embed.INSTALL_HINT}; ranking on histograms")
    if name == "clip":
        return ClipRanker(encoder=encoder, cache_dir=cache_dir, refresh=refresh,
                          composition=composition)
    return HistogramRanker()


def family_counts(styles_mapping=None):
    """{family: tagged assets}: how well covered each family already is."""
    styles_mapping = styles.load() if styles_mapping is None else styles_mapping
    counts = Counter()
    for tag in styles_mapping.values():
        fam = (tag or {}).get("style")
        if fam:
            counts[fam] += 1
    return counts


def quota(family, counts, base=QUOTA_BASE, cal=None, ranker_name="histogram"):
    """How many candidates a family is worth this run: inversely to how much
    corpus it already has, by the square root — vs-two-up (15 assets) gets
    about seven times full-bleed's (756), not fifty times. Once the family
    has been reviewed, a low keep rate asks for proportionally more raw
    results to end up with the same number of usable ones."""
    if not counts:
        return base
    n = max(1, counts.get(family, 0))
    want = math.ceil(base * math.sqrt(max(counts.values()) / n))
    rate = ((cal or {}).get("rankers", {}).get(ranker_name, {}).get("families", {})
            .get(family, {}) or {}).get("keep_rate")
    if rate is not None:
        want = math.ceil(want / max(rate, 0.1))
    return want


def plan_search(family, counts, terms, base=QUOTA_BASE, cal=None, ranker_name="histogram"):
    """(quota, limit per term) for one family's search."""
    want = quota(family, counts, base, cal, ranker_name)
    per_term = int(min(max(want / max(len(terms), 1), 5), stock.PER_PAGE["pexels"]))
    return want, per_term


def explored(eid, share=EXPLORE):
    """Is this candidate in the exploration slice? Deterministic in the id, so
    a re-run sheets the same tail and the sample is never cherry-picked."""
    if share <= 0:
        return False
    return int(hashlib.sha1(eid.encode()).hexdigest()[:8], 16) / 0xFFFFFFFF < share


def deepen(family, term, cal, ranker="histogram", keep_floor=KEEP_FLOOR, pages=1):
    """Is this term worth another page? An unjudged term gets exactly one
    extra page (explore once); a judged one gets the rest only if reviewers
    keep its candidates often enough."""
    rate = calibration.keep_rate_for(cal, ranker, family, term)
    if rate is None:
        return True
    return rate >= keep_floor


def _resolve(family, terms, platforms, keys, pool_dir, references_dir=None, composition=BARE):
    """The shared prologue of `search` and `plan`: validate, find the terms,
    and keep only the platforms this machine has a key for."""
    if family not in db.STYLES:
        raise ValueError(f"unknown style family {family!r}; one of {', '.join(db.STYLES)}")
    terms = list(terms or reference_terms(family, references_dir, composition))
    if not terms:
        where = f"{REFERENCE_BLOCK[composition][0]}.search_terms"
        raise ValueError(f"no {composition} search terms: pass --terms or collect "
                         f"{where} into corpus/references/{family}.yaml first")
    api_keys, missing = stock.keys_available(platforms, keys)
    if not api_keys:
        names = ", ".join(stock.KEYS[pf] for pf in platforms)
        raise ValueError(f"no API key for any of {', '.join(platforms)}: set {names} in the environment")
    return terms, api_keys, missing


def plan(family, terms=None, platforms=stock.PLATFORMS, orientation=None, keys=None, pages=1,
         min_width=MIN_WIDTH, pool_dir=POOL_DIR, client=None, attrs_mapping=None,
         styles_mapping=None, cal=None, keep_floor=KEEP_FLOOR, ranker_name=None,
         composition=BARE, references_dir=None, log=print):
    """What a search would ask for, without asking: the real clients build
    their real URLs against a recording stub, and each is looked up in the
    cache. Nothing is fetched and nothing is written."""
    terms, api_keys, missing = _resolve(family, terms, platforms, keys, pool_dir, references_dir,
                                        composition)
    ranker_name = ranker_name or ("clip" if embed.available() else "histogram")
    cal = calibration.load() if cal is None else cal
    allowed, auto = family_orientations(family, attrs_mapping, styles_mapping)
    orient = orientation or auto
    out = {pf: {"planned": 0, "cached": 0, "to_fetch": 0, "windows": [], "ok": True} for pf in api_keys}
    ledger = getattr(client, "ledger", None)
    for page in range(1, max(1, pages) + 1):
        for platform in api_keys:
            for term in terms:
                if page > 1 and not deepen(family, term, cal, ranker_name, keep_floor, pages):
                    continue
                urls = []
                stock.SEARCH[platform](term, api_keys[platform], per_page=stock.PER_PAGE[platform],
                                       orientation=orient, page=page, min_width=min_width,
                                       fetch=lambda u, headers=None: urls.append(u) or {})
                for url in urls:
                    out[platform]["planned"] += 1
                    hit = None
                    if ledger is not None:
                        key, _, _ = ledger.cache_key(platform, url)
                        hit = ledger.get(key, platform)
                    out[platform]["cached" if hit is not None else "to_fetch"] += 1
    if ledger is not None and client is not None:
        for platform, rec in out.items():
            windows = client.limiter.windows(platform)
            for (cap, secs), (n, _) in zip(windows, ledger.counts(platform, windows)):
                room = max(1, int(cap * client.limiter.safety)) - n
                rec["windows"].append({"cap": cap, "seconds": secs, "used": n, "room": room})
                rec["ok"] = rec["ok"] and rec["to_fetch"] <= room
    return out, {"family": family, "terms": len(terms), "pages": pages, "dry_run": True,
                 "orientation": orient, "skipped_platforms": missing}


def search(family, terms=None, platforms=stock.PLATFORMS, limit_per_term=30, orientation=None, keys=None,
           fetch=None, client=None, download=None, to_png=None, pool_dir=POOL_DIR,
           attrs_mapping=None, styles_mapping=None, hashes=None, pages=1, min_width=MIN_WIDTH,
           keep_floor=KEEP_FLOOR, cal=None, explore=EXPLORE, use_threshold=True,
           max_per_creator=MAX_PER_CREATOR, ranker=None, ranker_name=None, run_id=None,
           composition=BARE, references_dir=None, log=print):
    """Walk the terms breadth-first (every term sees page 1 before any sees
    page 2, so a spent budget still covers them all), admitting what the
    metadata alone cannot rule out, then hash, measure and rank each new
    photo's thumb, drop duplicates of the corpus and of the pool (best-scored
    survivor wins) and write the rest as `pending`.

    One platform's refusal stops that platform, never the others; a candidate
    below the calibrated threshold is dropped without ever costing a sheet
    cell, bar a deterministic exploration slice that keeps the threshold
    honest. Returns (written paths, stats)."""
    terms, api_keys, missing = _resolve(family, terms, platforms, keys, pool_dir, references_dir,
                                        composition)
    client = client or DirectFetcher(fetch)
    ranker = ranker if ranker is not None else make_ranker(ranker_name, composition=composition, log=log)
    cal = calibration.load() if cal is None else cal
    if download is None:
        from .media import download
    if to_png is None:
        from .similar import to_png
    hashes = corpus_hashes(pool_dir, attrs_mapping=attrs_mapping, styles_mapping=styles_mapping,
                           log=log) if hashes is None else hashes
    existing = all_entries(pool_dir)
    data = load(family, pool_dir)
    allowed, auto = family_orientations(family, attrs_mapping, styles_mapping)
    orient = orientation or auto
    for pf in missing:
        log(f"  {pf}: {stock.KEYS[pf]} not set; skipped")
    stats = {"run_id": run_id, "family": family, "ranker": ranker.name, "searched": 0, "raw": 0,
             "new": 0, "dropped": 0, "auto_dropped": 0, "moved": 0, "rate_limited": False,
             "orientation": orient, "skipped_platforms": missing,
             "dropped_by": {"corpus": 0, "pool": 0, "threshold": 0, "creator": 0},
             "platforms": {pf: platform_stats() for pf in api_keys}}

    raw = {}
    admitted = Counter()

    def admit(ph, platform, term):
        pf = stats["platforms"][platform]
        if not ph.get("image"):
            pf["prefiltered"]["no_image"] += 1
            return False
        if ph["id"] in existing or ph["id"] in raw:
            pf["dup_id"] += 1
            return False
        if stock.licence_key(ph.get("licence")) == "unknown":
            pf["prefiltered"]["licence"] += 1  # look-only: the widened tier's business, not the pool's
            return False
        if min_width and ph.get("width") and ph["width"] < min_width:
            pf["prefiltered"]["min_width"] += 1
            return False
        bucket = orientation_bucket(ph.get("width"), ph.get("height"))
        if allowed and bucket and bucket not in allowed:
            pf["prefiltered"]["aspect"] += 1
            return False
        raw[ph["id"]] = dict(ph, term=term)
        pf["admitted"] += 1
        return True

    done, stopped = set(), {}
    for page in range(1, max(1, pages) + 1):
        for platform in api_keys:
            if platform in stopped:
                continue
            pf = stats["platforms"][platform]
            for term in terms:
                if (platform, term) in done:
                    continue
                if page > 1 and not deepen(family, term, cal, ranker.name, keep_floor, pages):
                    done.add((platform, term))
                    continue
                try:
                    photos = stock.SEARCH[platform](term, api_keys[platform], per_page=stock.PER_PAGE[platform],
                                                    orientation=orient, page=page, min_width=min_width,
                                                    fetch=client.fetch_for(platform))
                except (apiclient.RateLimited, apiclient.BudgetExceeded,
                        apiclient.AuthError, apiclient.Unavailable) as exc:
                    reason = type(exc).__name__.lower()
                    stopped[platform] = reason
                    pf["stopped"] = reason
                    stats["rate_limited"] = stats["rate_limited"] or isinstance(exc, apiclient.RateLimited)
                    log(f"  {platform} stopped ({reason}); keeping what it found")
                    break
                except apiclient.ClientError as exc:  # this URL, not this platform
                    pf["errors"] += 1
                    log(f"  {platform} {term!r}: {exc}")
                    done.add((platform, term))
                    continue
                stats["searched"] += 1
                pf["pages"] += 1
                pf["results"] += len(photos)
                # Admit up to the cap, not past it. Admitting the whole page first
                # and checking after overshoots by the page size — 80 on Pexels,
                # 200 on Pixabay — and every surplus candidate is a sheet cell
                # paid for in review tokens.
                room = max(limit_per_term - admitted[(platform, term)], 0)
                n_new = considered = 0
                for ph in photos:
                    if n_new >= room:
                        break
                    considered += 1
                    if admit(ph, platform, term):
                        n_new += 1
                admitted[(platform, term)] += n_new
                # the yield floor judges the admit rate over what was actually
                # looked at, so stopping at the cap never reads as a bad term
                if (len(photos) < stock.PER_PAGE[platform] or admitted[(platform, term)] >= limit_per_term
                        or n_new < YIELD_FLOOR * max(considered, 1)):
                    done.add((platform, term))
    stats["raw"] = len(raw)

    grabbed = {}
    for eid, ph in raw.items():
        pf = stats["platforms"].get(eid.split("-")[0]) or platform_stats()
        dest = thumb_path(eid, pool_dir)
        try:
            fetch_thumb(ph, dest, download, to_png, stats=pf)
            grabbed[eid] = dest
        except Exception as exc:  # one dead photo must not stop the pass
            pf["thumb_failed"] += 1
            log(f"  {eid}: {exc}")

    ranker.prepare(family, attrs_mapping, styles_mapping, log=log)
    if grabbed and hasattr(ranker, "embed_all"):
        ranker.embed_all(grabbed, log=log)
    candidates = []
    for eid, dest in grabbed.items():
        ph = raw[eid]
        try:
            h, hm = phash.dhash_pair(dest)
            features = {k: v for k, v in measure.measure(dest).items()
                        if k in ("ground", "layout", "panel_count", "before_after")}
            scores = ranker.score(dest, features, (ph.get("width"), ph.get("height")))
        except Exception as exc:
            log(f"  {eid}: {exc}")
            continue
        sc, nearest = scores.get(family, (0.0, []))
        target = family
        if ranker.cross_family and scores:
            # only a family that can be told apart is a place to move a photo to
            movable = {f: v for f, v in scores.items() if ranker.reliable(f)}
            if movable:
                best, (best_sc, best_nearest) = max(movable.items(), key=lambda kv: kv[1][0])
                # a gated-out family or a clear win moves the candidate; noise does not
                if best_sc > 0 and (sc <= 0 or best_sc - sc >= REALLOC_MARGIN):
                    target, sc, nearest = best, best_sc, best_nearest
        candidates.append((sc, eid, ph, h, hm, features, nearest, target, scores))

    corpus_hashed = [(int(rec["phash"], 16), attrs.asset_id(src)) for src, rec in hashes.items()]
    pool_hashed = [(int(e["phash"], 16), other) for other, e in existing.items() if e.get("phash")]
    today = datetime.date.today().isoformat()
    datas = {family: data}
    by_creator = Counter()
    for sc, eid, ph, h, hm, features, nearest, target, scores in sorted(candidates, key=lambda c: c[0], reverse=True):
        entry = {"url": ph["url"], "image": ph["image"], "thumb": ph.get("thumb", ""),
                 "creator": ph["creator"], "creator_url": ph.get("creator_url", ""),
                 "platform": ph["platform"], "licence": stock.licence_key(ph.get("licence")),
                 "attribution_required": bool(stock.attribution_required(ph.get("licence"))),
                 "tier": "pool", "width": ph.get("width"), "height": ph.get("height"),
                 "aspect_class": sectionize.aspect_class(ph.get("width"), ph.get("height")),
                 "term": ph["term"], "collected": today, "phash": h, "ranker": ranker.name,
                 "searched_family": family, "composition": composition,
                 "features": features, "score": sc, "nearest": nearest, "state": "pending"}
        # Report only families we would actually act on. An indistinct family
        # (floored span) still scores high on anything — advertising it as
        # `best_family` on a sheet asks a reviewer to trust a judgement the
        # ranker itself has already refused to make.
        reportable = {f: v for f, v in scores.items() if ranker.reliable(f)}
        if reportable:
            top = sorted(reportable.items(), key=lambda kv: -kv[1][0])[:3]
            entry["family_scores"] = {fam: value[0] for fam, value in top}
            entry["best_family"] = top[0][0]
        if target != family:
            entry["moved_from"] = family
            stats["moved"] += 1
        if ph.get("download_location"):
            entry["download_location"] = ph["download_location"]
        threshold = calibration.threshold_for(cal, ranker.name, target) if use_threshold else None
        dup = nearest_dup(h, hm, corpus_hashed, CORPUS_DUP)
        if dup:
            entry.update(state="dropped", drop=f"near-dup of corpus {dup[1]} (hamming {dup[0]})")
            stats["dropped_by"]["corpus"] += 1
        else:
            dup = nearest_dup(h, hm, pool_hashed, POOL_DUP)
            if dup:
                entry.update(state="dropped", drop=f"near-dup of pool {dup[1]} (hamming {dup[0]})")
                stats["dropped_by"]["pool"] += 1
            elif max_per_creator and ph.get("creator"):
                seen = by_creator[ph["creator"]]
                if seen >= max_per_creator:
                    entry.update(state="dropped",
                                 drop=f"more than {max_per_creator} from {ph['creator']} this pass")
                    stats["dropped_by"]["creator"] += 1
        if entry["state"] == "pending" and threshold is not None and sc < threshold:
            if explored(eid, explore):
                entry["explored"] = True  # the slice that keeps the threshold from confirming itself
            else:
                entry.update(state="dropped",
                             drop=f"below calibrated threshold {threshold} ({ranker_name}, {today})")
                stats["dropped_by"]["threshold"] += 1
                stats["auto_dropped"] += 1
        if entry["state"] == "pending":
            pool_hashed.append((int(h, 16), eid))
            by_creator[ph.get("creator") or ""] += 1
            stats["new"] += 1
        else:
            stats["dropped"] += 1
        datas.setdefault(target, load(target, pool_dir))["entries"][eid] = entry
    for platform, st in stats["platforms"].items():
        st.update({k: v for k, v in (client.stat(platform) or {}).items() if k in st})
    return [save(d, pool_dir) for _, d in sorted(datas.items())], stats


def sheet_name(family, ids):
    """Named after the family and the entries on it, like the label sheets: a
    rebuilt sheet of the same cells keeps its answers file, a different one
    never inherits it."""
    return f"{family}-{hashlib.sha1(chr(10).join(sorted(ids)).encode()).hexdigest()[:6]}"


def prompt(family, references_dir=None, composition=BARE):
    genre = reference_genre(family, references_dir, composition)
    lines = [
        f"Review one contact sheet of licensed stock candidates for the `{family}` style family.",
        "",
        f"**Row 1 is {ANCHORS} Picsart originals of this family, captioned `ref <id>`.** They are the",
        "target, not candidates: do not judge them. Numbered cells (#1, #2, ...) start on row 2 and",
        "read left to right, top to bottom, best-ranked first; the manifest yaml beside the sheet",
        "names each cell's source.",
        ""]
    if genre:
        heading = ("The photography this family needs:" if composition == BARE
                   else "The arrangement this family needs:")
        lines += [heading, "", f"> {genre}", ""]
    lines += [
        "Write <sheet>.answers.yaml beside the sheet, one line per cell:",
        "", "```yaml", "1: keep", "2: drop", "3: {keep: true, subject: person}",
        "4: {keep: false, best_family: cinematic-still}",
        "5:", "  keep: true", "  note: 'slight text overlay, top right'",
        "```", "",
        "A `note` goes in the indented block form above, or quoted. In the one-line",
        "`{...}` form an unquoted note breaks the file: a comma ends the value, and a",
        "`#` (as in `same shoot as #10`) starts a comment that eats the closing brace.",
        "",
    ]
    if composition == BARE:
        lines += [
            "keep = the photograph a worker could build this family's slot from; drop = off-style,",
            "watermarked, text-heavy, or a near-duplicate of another cell. Judge the photograph only:",
            "the tiles, pills, panels and badges of the family are drawn by lp-compose afterwards, so a",
            "bare photo is what you should be seeing.",
            ""]
    else:
        lines += [
            "**These cells are judged on their arrangement, not their photography.** They were",
            "collected because they are already laid out like this family's slot — a split, a grid, a",
            "collage, a mockup scene — and they are kept as compositional references for how the",
            "panels sit. A mediocre photograph in exactly the right arrangement is a keep; a beautiful",
            "single frame that carries no arrangement is a drop.",
            "",
            "So the bare-sheet rules invert on two points. **Text, logos and watermarks are expected**",
            "— a laid-out picture is usually a marketing artifact — and are not grounds to drop on",
            "their own; say in the `note` what Picsart would have to strip. And **cells from one",
            "shoot are not duplicates** where this family tiles a repeating motif: that serial set is",
            "the point, so keep the ones that differ and say so.",
            "",
            "Still drop: another product's UI (a competitor's editor is not an arrangement Picsart can",
            "reuse), an arrangement this family never uses, anything unusable on a product page",
            "(explicit, smoking, branded beyond a strippable mark), and genuine near-identical repeats.",
            ""]
    lines += [
        f"`subject` (optional): one of {', '.join(attrs.ENUMS['subject'])}.",
        f"`best_family` (optional): a better-fitting family from {', '.join(db.STYLES)} — a good photo",
        "in the wrong place moves there instead of being lost.",
        f"`note` (optional): up to {NOTE_MAX} characters, for why a borderline call went the way it did.",
        "Leave a cell out if you cannot judge it; an unanswered cell stays pending."]
    return "\n".join(lines)


def build_sheets(family, pool_dir=POOL_DIR, per_sheet=PER_SHEET, thumb=320, columns=4,
                 download=None, to_png=None, resheet=False, anchors=ANCHORS,
                 attrs_mapping=None, styles_mapping=None, references_dir=None, log=print):
    """Contact sheets of the family's pending entries, best score first, with
    a manifest beside each; missing thumbs are re-fetched when a downloader
    is given (they are gitignored), skipped otherwise.

    An entry is stamped with its sheet here, not at merge time, and a stamped
    entry is never sheeted again unless asked: review tokens then scale with
    what a search found, not with how large the pool has grown."""
    data = load(family, pool_dir)
    out_dir = Path(pool_dir) / "sheets"
    out_dir.mkdir(parents=True, exist_ok=True)
    # the anchors come from the corpus, which is large: resolve it once, not once per sheet
    anchor_pool = family_locals(family, attrs_mapping, styles_mapping) if anchors else {}
    pending = []
    for eid, e in data["entries"].items():
        if e.get("state") != "pending" or e.get("tier", "pool") != "pool":
            continue
        if e.get("sheet") and not resheet:
            continue
        dest = thumb_path(eid, pool_dir)
        if not dest.exists():
            if download is None:
                log(f"  {eid}: no thumb (re-run search on this machine, or pass a downloader)")
                continue
            try:
                fetch_thumb(e, dest, download, to_png)
            except Exception as exc:
                log(f"  {eid}: {exc}")
                continue
        pending.append((eid, e))
    pending.sort(key=lambda kv: -(kv[1].get("score") or 0))
    written = []
    # One sheet never mixes intake modes: a bare photograph and an arrangement
    # are judged against different things, and a reviewer given both under one
    # instruction can only be wrong about half of them.
    by_mode = {}
    for eid, e in pending:
        by_mode.setdefault(e.get("composition") or BARE, []).append((eid, e))
    for mode in COMPOSITIONS:
        mode_pending = by_mode.get(mode) or []
        for i in range(0, len(mode_pending), per_sheet):
            chunk = mode_pending[i:i + per_sheet]
            name = sheet_name(family, [eid for eid, _ in chunk])
            png = out_dir / f"{name}.png"
            refs = anchor_items(family, chunk, anchor_pool, anchors) if anchors else []
            # pad the anchor row so the candidates start on a fresh row
            pad = [("", {"local": None})] * ((-len(refs)) % columns) if refs else []
            head = refs + pad
            items = head + [(eid, {"local": str(thumb_path(eid, pool_dir))}) for eid, _ in chunk]

            def caption(n, key, rec, _head=len(head), _chunk=chunk):
                if n < _head:
                    return f"ref {key}" if key else ""
                return f"#{n - _head + 1} {key} {_chunk[n - _head][1].get('score')}"
            taxonomy.contact_sheet(items, png, per_cell=len(items), thumb=thumb, columns=columns,
                                   caption=caption)
            manifest = {"sheet": name, "family": family, "composition": mode,
                        "answers": f"{name}.answers.yaml",
                        "anchors": [aid for aid, _ in refs],
                        "genre": reference_genre(family, references_dir, mode),
                        "cells": {n + 1: {"id": eid, "url": e["url"], "creator": e["creator"],
                                          "platform": e["platform"], "score": e.get("score"),
                                          "aspect_class": e.get("aspect_class"), "term": e.get("term"),
                                          "searched_family": e.get("searched_family"),
                                          "best_family": e.get("best_family"),
                                          "family_scores": e.get("family_scores"),
                                          "explored": e.get("explored")}
                                  for n, (eid, e) in enumerate(chunk)}}
            (out_dir / f"{name}.yaml").write_text(styles.dump_yaml(manifest, sort_keys=False, allow_unicode=True, width=1000))
            for eid, e in chunk:
                data["entries"][eid]["sheet"] = name
            written.append({"name": name, "png": png, "cells": len(chunk), "composition": mode,
                            "answered": (out_dir / f"{name}.answers.yaml").exists()})
    per = max((s["cells"] for s in written), default=0)
    lines = [f"# Pool sheets: {family}", "",
             f"{len(written)} sheet(s) of at most {per} numbered cell(s) each, "
             f"covering {len(pending)} pending entr(ies); "
             f"{sum(1 for s in written if s['answered'])}/{len(written)} answered.",
             "Those counts are for the whole family — one sheet holds only its own cells.",
             "Each sheet's manifest names its `composition`: read the matching prompt below.", ""]
    for mode in COMPOSITIONS:
        if any(s["composition"] == mode for s in written):
            lines += [f"## Prompt — {mode}", "", prompt(family, references_dir, mode), ""]
    (out_dir / f"README-{family}.md").write_text("\n".join(lines))
    save(data, pool_dir)
    return written, {"pending": len(pending), "sheets": len(written)}


def parse_answer(value):
    """(keep, extras, error) for one cell's answer: `keep`/`drop`, a boolean,
    or a mapping with `keep` and an optional `subject`, `best_family` or
    `note`. A rejected value is reported, never written."""
    extras = {}
    if isinstance(value, dict):
        allowed = {"keep", "subject", "best_family", "note"}
        unknown = [k for k in value if k not in allowed]
        if unknown:
            # `{keep: true, note: a, b}` parses: the comma ends the note and `b`
            # becomes a key. Refusing it is how that truncation gets noticed.
            return None, {}, f"unknown key(s) {', '.join(map(str, unknown))}; quote the note or use block form"
        subject = value.get("subject")
        if subject is not None:
            if subject not in attrs.ENUMS["subject"]:
                return None, {}, f"subject: {subject!r}"
            extras["subject"] = subject
        best = value.get("best_family")
        if best is not None:
            if best not in db.STYLES:
                return None, {}, f"best_family: {best!r}"
            extras["best_family"] = best
        note = value.get("note")
        if note is not None:
            if not isinstance(note, str) or len(note) > NOTE_MAX:
                return None, {}, f"note: must be a string of at most {NOTE_MAX} characters"
            extras["note"] = note
        value = value.get("keep")
    if isinstance(value, str) and value.strip().lower() in ("keep", "drop"):
        return value.strip().lower() == "keep", extras, None
    if isinstance(value, bool):
        return value, extras, None
    return None, {}, f"{value!r} is not keep or drop"


def ingest_labels(family=None, pool_dir=POOL_DIR, keys=None, fetch=stock.fetch_json, log=print):
    """Merge every answered pool sheet into its family yaml: kept entries are
    re-checked against the corpus hashes (a threshold change must not smuggle
    a duplicate through) and kept Unsplash photos get their one download
    ping. Returns stats."""
    out_dir = Path(pool_dir) / "sheets"
    stats = {"sheets": 0, "answered": 0, "kept": 0, "dropped": 0, "moved": 0, "errors": []}
    datas = {}
    for man_path in sorted(out_dir.glob("*.yaml")) if out_dir.exists() else []:
        if man_path.name.endswith(".answers.yaml"):
            continue
        man = styles.load_yaml(man_path.read_text()) or {}
        fam = man.get("family")
        if not fam or (family and fam != family):
            continue
        stats["sheets"] += 1
        answers_path = out_dir / man.get("answers", man_path.stem + ".answers.yaml")
        if not answers_path.exists():
            continue
        stats["answered"] += 1
        cells = man.get("cells") or {}
        data = datas.setdefault(fam, load(fam, pool_dir))
        try:
            answers = styles.load_yaml(answers_path.read_text()) or {}
        except yaml.YAMLError as exc:
            # one unparseable sheet must not cost the other thirty-five their merge
            first = str(exc).splitlines()[0]
            stats["errors"].append(f"{answers_path.name}: not valid yaml ({first}); fix and re-run")
            continue
        if not isinstance(answers, dict):
            stats["errors"].append(f"{answers_path.name}: expected one answer per cell number")
            continue
        for key, answer in answers.items():
            try:
                n = int(key)
            except (TypeError, ValueError):
                stats["errors"].append(f"{man_path.name} cell {key!r}: not a cell number")
                continue
            info = cells.get(n)
            entry = data["entries"].get((info or {}).get("id"))
            if entry is None:
                stats["errors"].append(f"{man_path.name} cell {n}: not on this sheet")
                continue
            keep, extras, err = parse_answer(answer)
            if err:
                stats["errors"].append(f"{man_path.name} cell {n}: {err}")
                continue
            target = extras.pop("best_family", None)
            entry.update(extras)
            entry["sheet"] = man.get("sheet", man_path.stem)
            if target and target != fam:
                # the right photograph in the wrong place: move it rather than lose it
                moved = data["entries"].pop(info["id"])
                moved["moved_from"] = fam
                moved["score"] = (moved.get("family_scores") or {}).get(target, moved.get("score"))
                # kept means kept for the family the reviewer named; otherwise it
                # goes back on that family's next sheet rather than being judged here
                moved["state"] = "kept" if keep else "pending"
                if keep:
                    moved.pop("drop", None)
                    stats["kept"] += 1
                else:
                    moved.pop("sheet", None)
                datas.setdefault(target, load(target, pool_dir))["entries"][info["id"]] = moved
                stats["moved"] += 1
                continue
            entry["state"] = "kept" if keep else "dropped"
            if not keep:
                entry["drop"] = "off-style (sheet answer)"
            stats["kept" if keep else "dropped"] += 1
    if any(e.get("state") == "kept" for d in datas.values() for e in d["entries"].values()):
        hashed = [(int(rec["phash"], 16), attrs.asset_id(src)) for src, rec in corpus_hashes(pool_dir, log=log).items()]
        for data in datas.values():
            for eid, e in data["entries"].items():
                if e.get("state") != "kept":
                    continue
                dup = nearest_dup(e["phash"], e["phash"], hashed, CORPUS_DUP)
                if dup:
                    e.update(state="dropped", drop=f"near-dup of corpus {dup[1]} (hamming {dup[0]})")
                    stats["errors"].append(f"{eid}: kept but within {CORPUS_DUP} of corpus {dup[1]}; dropped")
                    stats["kept"] -= 1
                    stats["dropped"] += 1
                elif e.get("download_location") and not e.get("downloaded"):
                    try:
                        stock.unsplash_track_download(e["download_location"], stock.key_for("unsplash", (keys or {}).get("unsplash")), fetch=fetch)
                        e["downloaded"] = True
                    except Exception as exc:
                        stats["errors"].append(f"{eid}: download ping failed ({exc}); re-run labels")
    for data in datas.values():
        save(data, pool_dir)
    return stats


def pick(family, k, seed, exclude_asset=(), aspect_class=None, pool_dir=POOL_DIR):
    """Up to k kept entries for a brief: aspect-filtered, blind to the run's
    own assets (an excluded 8-hex id anywhere in the entry drops it), rotated
    by a seeded shuffle — the same run always sees the same picks, the next
    run different ones, with nothing written at read time."""
    ids = list(exclude_asset or [])
    out = []
    for eid, e in sorted(load(family, pool_dir)["entries"].items()):
        if e.get("state") != "kept" or e.get("tier", "pool") != "pool":
            continue
        if aspect_class and e.get("aspect_class") != aspect_class:
            continue
        text = " ".join([e.get("url") or "", e.get("image") or "", e.get("drop") or "",
                         *(e.get("nearest") or [])])
        if any(i in text for i in ids):
            continue
        out.append(dict(e, id=eid))
    random.Random(f"{seed}:{family}").shuffle(out)
    return out[:k]


def write_examples(picks, out_dir, download, to_png, pool_dir=POOL_DIR, log=print, start=1):
    """One `p<n>-pool.md` plus PNG per pick, beside the corpus excerpts: a
    licensed look reference with its credit line. The frontmatter carries no
    corpus asset id, hash, `nearest` list or snapshot/source key, so the
    manager's blindness check stays clean by construction."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for n, e in enumerate(picks, start):
        stem = f"p{n}-pool"
        dest = out_dir / f"{stem}.png"
        local = thumb_path(e["id"], pool_dir)
        try:
            if local.exists():
                shutil.copyfile(local, dest)
                to_png(dest)
            else:
                fetch_thumb(e, dest, download, to_png)
        except Exception as exc:  # a dead photo is not fatal
            log(f"  could not fetch {e['image']}: {exc}")
            continue
        md = out_dir / f"{stem}.md"
        licence = stock.licence_key(e.get("licence"))
        meta = stock.LICENCES[licence]
        required = e.get("attribution_required")
        required = meta["attribution_required"] if required is None else required
        credit = f"Photo by {e['creator']} on {e['platform']} ({meta['label']}"
        credit += "; attribution required)" if required else ")"
        md.write_text("\n".join([
            "---", "origin: pool", f"platform: {e['platform']}", f"creator: {e['creator']!r}",
            f"page: {e['url']}", f"licence: {licence}",
            f"attribution_required: {str(bool(required)).lower()}", f"local: {dest.name}", "---", "",
            f"A licensed stock photograph matching this family's photography. {credit}.",
            "Look reference only: read it for finish, light, subject genre and framing. It is never",
            "uploaded, passed as `imageUrls`, or injected; Picsart's chrome and ground still come",
            "from the family block.", ""]))
        written.append(md)
        log(f"  {md.name}: {e['creator']} on {e['platform']}")
    return written
