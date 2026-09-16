"""CLIP embeddings of the corpus stills and the pool's candidate thumbs.

The histogram ranker orders a sheet by colour, which cannot tell a family's
photography from any other photo of the same palette — and cannot tell
full-bleed from cinematic-still at all, since both are one photo filling the
frame. An embedding can, so `pool.ClipRanker` scores a candidate by how close
it sits to the family's *own* photographs.

Torch is a large dependency and nothing in generation needs it, so it lives
behind an optional extra (`uv sync --extra embed`) and every entry point takes
an injected encoder: the tests use a tiny fake and never import torch. Without
the extra the pool falls back to the histogram ranker and auto-drops nothing.

The cache is fingerprinted and incremental, not write-once like
`pool._hashes.yaml`: a re-measured corpus, a re-tagged family or a deleted
file all resolve on the next call without a full re-embed."""

import json
from pathlib import Path

import numpy as np

from . import attrs, styles

MODEL, PRETRAINED = "ViT-B-32", "laion2b_s34b_b79k"
EMBED_DIR = Path("corpus/pool/_embed")
BATCH = 64
KINDS = ("image",)  # phase 2: "video", whose poster frame stands in for the still
INSTALL_HINT = ("CLIP ranking needs the optional extra: `uv sync --extra embed` "
                "(open_clip_torch + torch, ~1 GB once the weights are cached)")


def tag(model=MODEL, pretrained=PRETRAINED):
    return f"{model}__{pretrained}"


def available():
    """Is the extra installed? Checked without importing torch."""
    import importlib.util
    return all(importlib.util.find_spec(m) is not None for m in ("open_clip", "torch"))


def device():
    import torch
    return "mps" if torch.backends.mps.is_available() else "cpu"


class OpenClipEncoder:
    """The real encoder. Computes in fp32 even on MPS — fp16 LayerNorm there
    has a history of returning NaNs, and the saving is not worth a silent one."""

    def __init__(self, model=MODEL, pretrained=PRETRAINED, dev=None):
        import open_clip
        import torch
        self.torch = torch
        self.device = dev or device()
        self.model, _, self.preprocess = open_clip.create_model_and_transforms(
            model, pretrained=pretrained, precision="fp32", device=self.device)
        self.model.eval()
        self.name = tag(model, pretrained)
        self.dim = self.model.visual.output_dim

    def _open(self, path):
        from PIL import Image
        with Image.open(path) as im:
            if im.mode in ("RGBA", "LA", "P"):
                im = im.convert("RGBA")
                ground = Image.new("RGBA", im.size, "white")  # the same white the measure copy composites on
                ground.alpha_composite(im)
                im = ground
            return im.convert("RGB")

    def images(self, paths):
        out = []
        for i in range(0, len(paths), BATCH):
            batch = [self.preprocess(self._open(p)) for p in paths[i:i + BATCH]]
            with self.torch.inference_mode():
                v = self.model.encode_image(self.torch.stack(batch).to(self.device))
                v = v / v.norm(dim=-1, keepdim=True)
            out.append(v.float().cpu().numpy())
        return np.concatenate(out) if out else np.zeros((0, self.dim), dtype=np.float32)

    def texts(self, texts):
        """The seam for a zero-shot prior. Deliberately unused by the ranker:
        CLIP's text tower keys on subject nouns and truncates at 77 tokens,
        which is the wrong end of what separates these families."""
        import open_clip
        tokens = open_clip.tokenize(texts).to(self.device)
        with self.torch.inference_mode():
            v = self.model.encode_text(tokens)
            v = v / v.norm(dim=-1, keepdim=True)
        return v.float().cpu().numpy()


def load_encoder(model=MODEL, pretrained=PRETRAINED, dev=None):
    try:
        return OpenClipEncoder(model, pretrained, dev)
    except ImportError as exc:
        raise ImportError(INSTALL_HINT) from exc


def fingerprint(path):
    """What makes a cached row stale: the file's identity, not its name."""
    st = Path(path).stat()
    return f"{path}|{st.st_mtime_ns}|{st.st_size}"


def corpus_rows(attrs_mapping=None, styles_mapping=None, kinds=KINDS):
    """The corpus stills worth embedding: tagged with a family, not
    provisional (a chrome-unanswered tag may be a composite the measurer read
    as a photo, and full-bleed holds almost all of them), of a kind we can
    embed, and present on disk."""
    attrs_mapping = attrs.load() if attrs_mapping is None else attrs_mapping
    styles_mapping = styles.load() if styles_mapping is None else styles_mapping
    rows, seen = [], set()
    for src in sorted(styles_mapping):
        tagrec = styles_mapping.get(src) or {}
        family = tagrec.get("style")
        if not family or tagrec.get("provisional"):
            continue
        rec = attrs_mapping.get(src) or {}
        if rec.get("kind") and rec["kind"] not in kinds:
            continue
        local = rec.get("local")
        if not local or not Path(local).exists():
            continue
        # One row per asset id: the same asset is served under several srcs
        # (query-string renditions), and the cache is keyed by id — duplicates
        # would both collapse it and double-weight the asset in a baseline.
        aid = attrs.asset_id(src)
        if aid in seen:
            continue
        seen.add(aid)
        rows.append({"id": aid, "src": src, "family": family,
                     "local": str(local), "key": fingerprint(local)})
    return rows


class Embeddings:
    """Rows aligned with vectors, plus the per-family index the ranker wants."""

    def __init__(self, rows, vectors):
        self.rows = rows
        self.vectors = vectors
        self.ids = [r["id"] for r in rows]
        self.families = np.array([r.get("family") for r in rows], dtype=object)

    def __len__(self):
        return len(self.rows)

    def index_of(self, family):
        return np.flatnonzero(self.families == family)


def _cache_paths(cache_dir, name, encoder_name):
    base = Path(cache_dir) / encoder_name
    return base / f"{name}.npy", base / f"{name}.json"


def _read_cache(npy, meta):
    if not (npy.exists() and meta.exists()):
        return {}, None
    try:
        info = json.loads(meta.read_text())
        vectors = np.load(npy)
    except Exception:
        return {}, None
    rows = info.get("rows") or []
    if len(rows) != len(vectors):
        return {}, None
    return {r["id"]: (r, vectors[i]) for i, r in enumerate(rows)}, info


def _embed_missing(encoder, rows, cached, log):
    """Embed only what changed; carry the rest over verbatim."""
    todo = [r for r in rows if r["id"] not in cached or cached[r["id"]][0].get("key") != r["key"]]
    fresh = {}
    if todo:
        log(f"  embedding {len(todo)} of {len(rows)} on {getattr(encoder, 'name', '?')}")
        vectors = encoder.images([Path(r["local"]) for r in todo])
        fresh = {r["id"]: v for r, v in zip(todo, vectors)}
    out = []
    for r in rows:
        vec = fresh.get(r["id"])
        if vec is None:
            vec = cached[r["id"]][1]
        out.append(np.asarray(vec, dtype=np.float32))
    return (np.stack(out) if out else np.zeros((0, getattr(encoder, "dim", 512)), dtype=np.float32)), len(todo)


def _write_cache(npy, meta, rows, vectors, encoder):
    npy.parent.mkdir(parents=True, exist_ok=True)
    np.save(npy, vectors.astype(np.float16))  # storage only: the cosine is computed in fp32
    meta.write_text(json.dumps({"model": getattr(encoder, "name", "?"),
                                "dim": int(vectors.shape[1]) if len(vectors) else 0,
                                "rows": rows}, indent=1))


def corpus_embeddings(encoder, attrs_mapping=None, styles_mapping=None, cache_dir=EMBED_DIR,
                      refresh=False, kinds=KINDS, log=print):
    """Every tagged corpus still as a unit vector. The family is refreshed
    from the current tags on every call, so a re-tag costs no embedding."""
    rows = corpus_rows(attrs_mapping, styles_mapping, kinds)
    npy, meta = _cache_paths(cache_dir, "corpus", getattr(encoder, "name", "?"))
    cached, _ = ({}, None) if refresh else _read_cache(npy, meta)
    vectors, n_new = _embed_missing(encoder, rows, cached, log)
    if rows or not cached:
        _write_cache(npy, meta, rows, vectors, encoder)
    else:
        # attrs/styles resolve relative paths, so a run from the wrong directory
        # reads zero rows — and writing that emptied a 1785-vector baseline once,
        # leaving the ranker silently scoring against nothing. Keep what we have.
        log(f"  corpus rows are empty; keeping the cached baseline ({len(cached)} vectors)")
    return Embeddings(rows, vectors), {"rows": len(rows), "embedded": n_new,
                                       "reused": len(rows) - n_new}


def candidate_embeddings(encoder, thumbs, cache_dir=EMBED_DIR, refresh=False, log=print):
    """{entry id: unit vector} for candidate thumbs. A thumb is written once
    and never rewritten, so its id plus its fingerprint is enough."""
    rows = [{"id": eid, "local": str(path), "key": fingerprint(path)}
            for eid, path in sorted(thumbs.items()) if Path(path).exists()]
    npy, meta = _cache_paths(cache_dir, "candidates", getattr(encoder, "name", "?"))
    cached, _ = ({}, None) if refresh else _read_cache(npy, meta)
    keep = {eid: rec for eid, rec in cached.items()}  # candidates accumulate across runs
    vectors, n_new = _embed_missing(encoder, rows, cached, log)
    merged_rows = [dict(r) for r in rows]
    merged = {r["id"]: v for r, v in zip(merged_rows, vectors)}
    for eid, (row, vec) in keep.items():
        if eid not in merged:
            merged_rows.append(row)
            merged[eid] = vec
    order = [r["id"] for r in merged_rows]
    stacked = np.stack([np.asarray(merged[i], dtype=np.float32) for i in order]) if order else \
        np.zeros((0, getattr(encoder, "dim", 512)), dtype=np.float32)
    _write_cache(npy, meta, merged_rows, stacked, encoder)
    return {eid: merged[eid] for eid in (r["id"] for r in rows)}, {"rows": len(rows), "embedded": n_new}


def describe(cache_dir=EMBED_DIR, encoder_name=None, log=print):
    """What the cache holds, per model: rows, families, dimension."""
    out = {}
    base = Path(cache_dir)
    for model_dir in sorted(base.glob("*")) if base.exists() else []:
        if encoder_name and model_dir.name != encoder_name:
            continue
        rec = {}
        for name in ("corpus", "candidates"):
            npy, meta = model_dir / f"{name}.npy", model_dir / f"{name}.json"
            cached, info = _read_cache(npy, meta)
            if info is None:
                continue
            families = {}
            for row, _ in cached.values():
                if row.get("family"):
                    families[row["family"]] = families.get(row["family"], 0) + 1
            rec[name] = {"rows": len(cached), "dim": info.get("dim"),
                         "families": dict(sorted(families.items(), key=lambda kv: -kv[1]))}
        out[model_dir.name] = rec
    return out
