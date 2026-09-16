"""The CLIP cache: what it embeds, what it refuses to re-embed, and what it
says when the extra is missing — all with a fake encoder, so the suite never
imports torch."""
import random

import numpy as np
from PIL import Image

from landing_page_gen.corpus import embed, pool

FAMILY, OTHER = "full-bleed", "cinematic-still"


class FakeEncoder:
    """Mean colour and contrast as a unit vector: red pictures cluster away
    from blue ones, which is all the ranker tests need."""

    name = "fake__v1"
    dim = 8

    def __init__(self):
        self.calls = []

    def images(self, paths):
        self.calls.append([str(p) for p in paths])
        out = []
        for path in paths:
            with Image.open(path) as im:
                a = np.asarray(im.convert("RGB"), dtype=np.float64) / 255.0
            v = np.array([a[..., 0].mean(), a[..., 1].mean(), a[..., 2].mean(),
                          a.std(), 0.0, 0.0, 0.0, 0.1])
            out.append(v / (np.linalg.norm(v) or 1.0))
        return np.stack(out).astype(np.float32) if out else np.zeros((0, self.dim), dtype=np.float32)


def solid(path, colour, size=(32, 32), jitter=0):
    rng = random.Random(str(colour) + str(jitter))
    im = Image.new("RGB", size, colour)
    if jitter:
        im.putdata([tuple(min(255, max(0, c + rng.randrange(-jitter, jitter))) for c in colour)
                    for _ in range(size[0] * size[1])])
    im.save(path)
    return path


def corpus(tmp_path, n=4):
    """attrs/styles mappings for two colour-separated families on disk."""
    attrs_mapping, styles_mapping = {}, {}
    for i in range(n):
        for fam, colour in ((FAMILY, (200, 30, 30)), (OTHER, (30, 30, 200))):
            src = f"https://cdn.picsart.io/p/{fam[:2]}{i:06x}-0000-4000-8000-00000000000{i}.png"
            local = tmp_path / f"{fam}-{i}.png"
            solid(local, colour, jitter=20)
            attrs_mapping[src] = {"local": str(local), "kind": "image"}
            styles_mapping[src] = {"style": fam}
    return attrs_mapping, styles_mapping


def test_corpus_cache_is_incremental_and_never_write_once(tmp_path):
    enc = FakeEncoder()
    attrs_mapping, styles_mapping = corpus(tmp_path)
    cache = tmp_path / "_embed"
    emb, stats = embed.corpus_embeddings(enc, attrs_mapping, styles_mapping, cache_dir=cache, log=lambda m: None)
    assert stats == {"rows": 8, "embedded": 8, "reused": 0} and len(emb) == 8
    assert np.allclose(np.linalg.norm(emb.vectors, axis=1), 1.0), "vectors are unit length"
    # a second pass embeds nothing
    enc2 = FakeEncoder()
    emb2, stats2 = embed.corpus_embeddings(enc2, attrs_mapping, styles_mapping, cache_dir=cache, log=lambda m: None)
    assert stats2["embedded"] == 0 and stats2["reused"] == 8 and enc2.calls == []
    assert np.allclose(emb.vectors, emb2.vectors, atol=1e-3)
    # touching one file re-embeds exactly that row
    changed = next(iter(attrs_mapping.values()))["local"]
    solid(changed, (10, 200, 10), jitter=20)
    enc3 = FakeEncoder()
    _, stats3 = embed.corpus_embeddings(enc3, attrs_mapping, styles_mapping, cache_dir=cache, log=lambda m: None)
    assert stats3["embedded"] == 1 and len(enc3.calls[0]) == 1
    # re-tagging a family costs no embedding at all
    src = next(iter(styles_mapping))
    styles_mapping[src] = {"style": OTHER}
    enc4 = FakeEncoder()
    emb4, stats4 = embed.corpus_embeddings(enc4, attrs_mapping, styles_mapping, cache_dir=cache, log=lambda m: None)
    assert stats4["embedded"] == 0 and enc4.calls == []
    assert len(emb4.index_of(OTHER)) == 5 and len(emb4.index_of(FAMILY)) == 3
    # refresh re-embeds everything
    _, stats5 = embed.corpus_embeddings(FakeEncoder(), attrs_mapping, styles_mapping,
                                        cache_dir=cache, refresh=True, log=lambda m: None)
    assert stats5["embedded"] == 8


def test_rows_skip_provisional_videos_and_missing_files(tmp_path):
    attrs_mapping, styles_mapping = corpus(tmp_path, n=1)
    srcs = list(styles_mapping)
    # a provisional tag may be a composite the measurer misread: never a baseline
    styles_mapping[srcs[0]]["provisional"] = True
    # video is phase 2; its poster frame stands in later
    attrs_mapping[srcs[1]]["kind"] = "video"
    rows = embed.corpus_rows(attrs_mapping, styles_mapping)
    assert rows == []
    attrs_mapping[srcs[1]]["kind"] = "image"
    assert [r["id"] for r in embed.corpus_rows(attrs_mapping, styles_mapping)]
    attrs_mapping[srcs[1]]["local"] = str(tmp_path / "gone.png")
    assert embed.corpus_rows(attrs_mapping, styles_mapping) == []


def test_one_row_per_asset_id_so_the_cache_settles(tmp_path):
    """The same asset is served under several srcs (query-string renditions).
    The cache is keyed by asset id, so duplicate rows collapse it and it never
    stops re-embedding them — 67 of 1852 corpus stills, every single run."""
    attrs_mapping, styles_mapping = corpus(tmp_path, n=1)
    src = next(iter(styles_mapping))
    rendition = src.replace(".png", ".png?w=800")  # same asset, different URL
    attrs_mapping[rendition] = dict(attrs_mapping[src])
    styles_mapping[rendition] = dict(styles_mapping[src])
    rows = embed.corpus_rows(attrs_mapping, styles_mapping)
    assert len(rows) == len({r["id"] for r in rows}), "ids are unique"
    cache = tmp_path / "_embed"
    _, first = embed.corpus_embeddings(FakeEncoder(), attrs_mapping, styles_mapping,
                                       cache_dir=cache, log=lambda m: None)
    enc = FakeEncoder()
    _, second = embed.corpus_embeddings(enc, attrs_mapping, styles_mapping,
                                        cache_dir=cache, log=lambda m: None)
    assert second["embedded"] == 0 and enc.calls == [], "a settled cache embeds nothing"
    assert second["reused"] == first["rows"]


def test_candidate_cache_accumulates_across_runs(tmp_path):
    cache = tmp_path / "_embed"
    a = solid(tmp_path / "a.png", (200, 30, 30))
    b = solid(tmp_path / "b.png", (30, 30, 200))
    vecs, stats = embed.candidate_embeddings(FakeEncoder(), {"pexels-1": a}, cache_dir=cache, log=lambda m: None)
    assert set(vecs) == {"pexels-1"} and stats["embedded"] == 1
    enc = FakeEncoder()
    vecs2, stats2 = embed.candidate_embeddings(enc, {"pexels-1": a, "pexels-2": b}, cache_dir=cache, log=lambda m: None)
    assert set(vecs2) == {"pexels-1", "pexels-2"} and stats2["embedded"] == 1, "only the new thumb is embedded"
    assert enc.calls == [[str(b)]]
    info = embed.describe(cache_dir=cache)
    assert info["fake__v1"]["candidates"]["rows"] == 2 and info["fake__v1"]["candidates"]["dim"] == 8


def test_missing_extra_names_the_install_and_falls_back_to_histogram(monkeypatch):
    """Holds whether or not the extra is installed on this machine."""
    monkeypatch.setattr(embed, "available", lambda: False)
    ranker = pool.make_ranker(None, log=lambda m: None)
    assert ranker.name == "histogram", "without the extra the pool still ranks, it just cannot auto-drop"
    # and with it, clip is the default
    monkeypatch.setattr(embed, "available", lambda: True)
    assert pool.make_ranker(None, log=lambda m: None).name == "clip"
    # the install hint is what a missing import must say
    import builtins
    real_import = builtins.__import__

    def no_clip(name, *a, **k):
        if name in ("open_clip", "torch"):
            raise ImportError(name)
        return real_import(name, *a, **k)
    monkeypatch.setattr(builtins, "__import__", no_clip)
    try:
        embed.load_encoder()
        assert False, "should refuse without the extra"
    except ImportError as exc:
        assert "uv sync --extra embed" in str(exc)


def test_empty_corpus_never_writes_the_baseline_away(tmp_path):
    """A run from the wrong directory reads zero rows (attrs/styles resolve
    relative paths). Writing that would wipe 1785 vectors and leave the ranker
    silently ranking against nothing — it happened once."""
    enc = FakeEncoder()
    attrs_mapping, styles_mapping = corpus(tmp_path)
    cache = tmp_path / "_embed"
    emb, _ = embed.corpus_embeddings(enc, attrs_mapping, styles_mapping, cache_dir=cache, log=lambda m: None)
    assert len(emb) == 8
    empty, stats = embed.corpus_embeddings(FakeEncoder(), {}, {}, cache_dir=cache, log=lambda m: None)
    assert len(empty) == 0, "the caller still sees what it asked for"
    again, stats = embed.corpus_embeddings(FakeEncoder(), attrs_mapping, styles_mapping,
                                           cache_dir=cache, log=lambda m: None)
    assert stats["embedded"] == 0 and len(again) == 8, "the baseline survived"
