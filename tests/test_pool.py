"""The licensed stock pool: search, dedupe, rank, sheets, labels, serving —
with the network stubbed."""
import json
import random
import re

import yaml
from PIL import Image

from landing_page_gen.corpus import ledger, phash, pool, similar, stock, taxonomy
from test_embed import FakeEncoder, solid

FAMILY = "full-bleed"
CORPUS_SRC = "https://cdn-basic-content-api.picsart.io/p/aabbccdd-aaaa-4000-8000-000000000001.png"


def noise_image(seed, size=(48, 48)):
    rng = random.Random(seed)
    im = Image.new("RGB", size)
    im.putdata([(rng.randrange(256), rng.randrange(256), rng.randrange(256))
                for _ in range(size[0] * size[1])])
    return im


def gradient_image(size=(64, 48)):
    w, h = size
    im = Image.new("RGB", size)
    im.putdata([(x * 255 // w, y * 255 // h, (x + y) * 255 // (w + h))
                for y in range(h) for x in range(w)])
    return im


def test_dhash_survives_resize_and_hamming_counts_bits():
    im = gradient_image()
    big = im.resize((im.width * 3, im.height * 3), Image.LANCZOS)
    assert phash.hamming(phash.dhash(im), phash.dhash(big)) <= 2
    assert phash.hamming("0" * 16, "f" * 16) == 64 and phash.hamming("00", "00") == 0
    h, hm = phash.dhash_pair(im)
    assert h == phash.dhash(im) and hm == phash.dhash(im.transpose(Image.FLIP_LEFT_RIGHT))


def pexels_payload(ids):
    return {"photos": [
        {"id": i, "url": f"https://www.pexels.com/photo/x-{i}/",
         "src": {"original": f"https://images.pexels.com/{i}/orig.jpeg",
                 "large": f"https://images.pexels.com/{i}/large.jpeg"},
         "photographer": f"Photographer {i}", "photographer_url": f"https://www.pexels.com/@p{i}",
         "width": 3000, "height": 2000} for i in ids]}


def test_stock_clients_normalise_and_need_keys(monkeypatch):
    ms = stock.pexels_search("cup", "k", fetch=lambda u, headers=None: pexels_payload([7]))
    assert ms[0] == {"id": "pexels-7", "url": "https://www.pexels.com/photo/x-7/",
                     "image": "https://images.pexels.com/7/orig.jpeg",
                     "thumb": "https://images.pexels.com/7/large.jpeg",
                     "creator": "Photographer 7", "creator_url": "https://www.pexels.com/@p7",
                     "platform": "Pexels", "licence": "pexels", "attribution_required": False,
                     "width": 3000, "height": 2000}
    urls = []
    stock.pexels_search("cup", "k", per_page=500, page=3, fetch=lambda u, headers=None: urls.append(u) or {})
    assert "per_page=80" in urls[0] and "page=3" in urls[0], "the page max is asked for, the page walked"
    payload = {"results": [
        {"id": "abc", "urls": {"full": "https://images.unsplash.com/photo-abc", "raw": "https://images.unsplash.com/photo-abc?ixid=xyz", "regular": "https://images.unsplash.com/photo-abc?w=1080"},
         "links": {"html": "https://unsplash.com/photos/abc", "download_location": "https://api.unsplash.com/photos/abc/download"},
         "user": {"name": "U", "links": {"html": "https://unsplash.com/@u"}}, "width": 4000, "height": 3000},
        {"id": "plus", "urls": {"full": "https://plus.unsplash.com/premium-1"}, "links": {}, "user": {}}]}
    ms = stock.unsplash_search("cup", "k", fetch=lambda u, headers=None: payload)
    assert len(ms) == 1 and ms[0]["id"] == "unsplash-abc"  # the Unsplash+ premium photo is dropped
    assert ms[0]["download_location"] == "https://api.unsplash.com/photos/abc/download"
    # the eval copy is a resize of raw with the ixid kept, not the 1080 px regular
    assert ms[0]["thumb"] == f"https://images.unsplash.com/photo-abc?ixid=xyz&w={stock.THUMB_PX}&h={stock.THUMB_PX}&fit=max&q=75&fm=jpg"
    monkeypatch.delenv("PEXELS_API_KEY", raising=False)
    try:
        stock.key_for("pexels")
        assert False, "should need a key"
    except ValueError as exc:
        assert "PEXELS_API_KEY" in str(exc)


def test_pixabay_parses_and_keeps_its_key_out_of_the_url_we_log():
    urls = []

    def fetch(url, headers=None):
        urls.append(url)
        return {"hits": [{"id": 42, "pageURL": "https://pixabay.com/photos/cup-42/",
                          "largeImageURL": "https://cdn.pixabay.com/42_1280.jpg",
                          "webformatURL": "https://cdn.pixabay.com/42_640.jpg",
                          "user": "Ann", "user_id": 7, "imageWidth": 3000, "imageHeight": 2000}]}
    ms = stock.pixabay_search("cup", "SECRET", per_page=999, orientation="portrait", min_width=1200, fetch=fetch)
    assert ms[0] == {"id": "pixabay-42", "url": "https://pixabay.com/photos/cup-42/",
                     "image": "https://cdn.pixabay.com/42_1280.jpg",
                     "thumb": "https://cdn.pixabay.com/42_640.jpg",
                     "creator": "Ann", "creator_url": "https://pixabay.com/users/Ann-7/",
                     "platform": "Pixabay", "licence": "pixabay", "attribution_required": False,
                     "width": 3000, "height": 2000}
    assert "per_page=200" in urls[0] and "orientation=vertical" in urls[0] and "min_width=1200" in urls[0]
    # the secret is in the URL the client builds; the ledger is what strips it
    key, endpoint, params = ledger.Ledger.cache_key("pixabay", urls[0])
    assert "SECRET" not in json.dumps(params) and endpoint == "pixabay.com/api/"


def test_licence_vocabulary_and_key_discovery(monkeypatch):
    assert stock.licence_key("Pexels") == "pexels" and stock.licence_key("pexels") == "pexels"
    assert stock.licence_key("CC BY") == "cc-by" and stock.attribution_required("cc-by") is True
    assert stock.licence_key("CC BY-NC") == "unknown", "an unlisted licence never passes as pooled"
    assert stock.attribution_required("pexels") is False
    for pf in stock.PLATFORMS:
        assert stock.PLATFORM_LABELS[pf] in stock.PLATFORM_HOSTS
    found, missing = stock.keys_available(stock.PLATFORMS, keys={"pexels": "k"}, environ={})
    assert found == {"pexels": "k"} and missing == ["unsplash", "pixabay"]
    found, missing = stock.keys_available(("pixabay",), environ={"PIXABAY_API_KEY": "p"})
    assert found == {"pixabay": "p"} and missing == []


def write_corpus_hashes(pool_dir, image):
    pool_dir.mkdir(parents=True, exist_ok=True)
    (pool_dir / "_hashes.yaml").write_text(yaml.safe_dump(
        {CORPUS_SRC: {"phash": phash.dhash(image), "family": FAMILY}}))


SEEDS = {"1": "unique", "2": "corpus-photo", "3": "unique"}  # 3 repeats 1's picture


def fake_download(url, dest, timeout=60):
    i = url.split("images.pexels.com/")[1].split("/")[0]
    noise_image(SEEDS[i]).save(dest, format="PNG")
    return dest


def run_search(pool_dir, fetch, **kw):
    # histogram, explicitly: an unnamed ranker defaults to clip, whose cache_dir
    # would then be the real corpus/pool/_embed — these tests would both read and
    # overwrite the production baseline. They are about dedupe, not ranking.
    kw.setdefault("ranker_name", "histogram")
    return pool.search(FAMILY, terms=["cup"], platforms=("pexels",), keys={"pexels": "k"},
                       fetch=fetch, download=fake_download, to_png=similar.to_png,
                       pool_dir=pool_dir, attrs_mapping={}, styles_mapping={},
                       log=lambda m: None, **kw)


def test_search_dedupes_against_corpus_and_pool_and_resumes(tmp_path):
    write_corpus_hashes(tmp_path, noise_image("corpus-photo"))
    fetches = []

    def fetch(url, headers=None):
        fetches.append(url)
        return pexels_payload([1, 2, 3])
    paths, stats = run_search(tmp_path, fetch)
    assert (stats["raw"], stats["new"], stats["dropped"]) == (3, 1, 2)
    entries = yaml.safe_load(paths[0].read_text())["entries"]
    assert entries["pexels-1"]["state"] == "pending"
    assert entries["pexels-1"]["aspect_class"] == "3:2" and entries["pexels-1"]["term"] == "cup"
    assert entries["pexels-2"]["state"] == "dropped" and "corpus aabbccdd (hamming 0)" in entries["pexels-2"]["drop"]
    assert entries["pexels-3"]["state"] == "dropped" and "pool pexels-1" in entries["pexels-3"]["drop"]
    # a second pass re-adds nothing: every id is already in the yaml, any state
    _, stats2 = run_search(tmp_path, fetch)
    assert stats2["raw"] == 0 and stats2["new"] == 0
    assert set(yaml.safe_load(paths[0].read_text())["entries"]) == {"pexels-1", "pexels-2", "pexels-3"}


def test_search_survives_a_rate_limit_and_needs_terms(tmp_path, monkeypatch):
    write_corpus_hashes(tmp_path, noise_image("corpus-photo"))

    def fetch(url, headers=None):
        raise stock.RateLimited(url)
    paths, stats = run_search(tmp_path, fetch)
    assert stats["rate_limited"] and stats["new"] == 0 and paths[0].exists()
    monkeypatch.setattr(pool, "REFERENCES_DIR", tmp_path / "none")
    try:
        pool.search(FAMILY, keys={"pexels": "k"}, platforms=("pexels",), pool_dir=tmp_path,
                    attrs_mapping={}, styles_mapping={}, log=lambda m: None)
        assert False, "should need terms"
    except ValueError as exc:
        assert "search terms" in str(exc)
    try:
        pool.search("no-such-family", terms=["x"], pool_dir=tmp_path)
        assert False
    except ValueError as exc:
        assert "style family" in str(exc)


def query_of(url):
    import urllib.parse
    return dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(url).query))


def any_download(url, dest, timeout=60):
    """A deterministic picture per URL, for the multi-platform searches."""
    noise_image(url).save(dest, format="PNG")
    return dest


def pexels_page(page, n=80, offset=0):
    return pexels_payload([offset + (page - 1) * n + i for i in range(1, n + 1)])


def portrait_corpus(n=5, w=800, h=1400):
    """attrs/styles mappings for a family whose assets are all one shape."""
    attrs_mapping, styles_mapping = {}, {}
    for i in range(n):
        src = f"https://cdn.picsart.io/p/{i:08x}-0000-4000-8000-00000000000{i}.png"
        attrs_mapping[src] = {"width": w, "height": h}
        styles_mapping[src] = {"style": FAMILY}
    return attrs_mapping, styles_mapping


def test_search_isolates_platform_failures_and_skips_keyless_platforms(tmp_path):
    write_corpus_hashes(tmp_path, noise_image("far-away"))

    def fetch(url, headers=None):
        if "pexels" in url:
            raise stock.RateLimited(url)
        return {"hits": [{"id": i, "pageURL": f"https://pixabay.com/photos/c-{i}/",
                          "largeImageURL": f"https://cdn.pixabay.com/{i}_1280.jpg",
                          "webformatURL": f"https://cdn.pixabay.com/{i}_640.jpg",
                          "user": "Ann", "user_id": 7, "imageWidth": 3000, "imageHeight": 2000}
                         for i in (1, 2)]}
    paths, stats = pool.search(FAMILY, terms=["cup"], platforms=("pexels", "pixabay"),
                               keys={"pexels": "k", "pixabay": "p"}, fetch=fetch,
                               download=any_download, to_png=similar.to_png, pool_dir=tmp_path,
                               attrs_mapping={}, styles_mapping={}, ranker_name="histogram",
                               log=lambda m: None)
    # pexels is out for the run; pixabay was never touched by its refusal
    assert stats["platforms"]["pexels"]["stopped"] == "ratelimited" and stats["rate_limited"]
    assert stats["new"] == 2 and set(yaml.safe_load(paths[0].read_text())["entries"]) == {"pixabay-1", "pixabay-2"}
    # a platform with no key is skipped with a warning, not a failure
    _, stats2 = pool.search(FAMILY, terms=["cup"], platforms=stock.PLATFORMS, keys={"pexels": "k"},
                            fetch=lambda u, headers=None: {}, download=any_download,
                            to_png=similar.to_png, pool_dir=tmp_path, attrs_mapping={},
                            styles_mapping={}, ranker_name="histogram", log=lambda m: None)
    assert stats2["skipped_platforms"] == ["unsplash", "pixabay"]
    try:
        pool.search(FAMILY, terms=["cup"], platforms=("unsplash",), keys={}, pool_dir=tmp_path,
                    attrs_mapping={}, styles_mapping={}, log=lambda m: None)
        assert False, "no key anywhere should be an error"
    except ValueError as exc:
        assert "UNSPLASH_ACCESS_KEY" in str(exc)


def test_one_shoot_cannot_fill_a_sheet(tmp_path):
    """Frames from one session are different pictures, so the perceptual hash
    passes them, but they score alike and cluster onto one sheet. A live sweep
    gave a sheet 8 of 12 cells from three shoots."""
    write_corpus_hashes(tmp_path, noise_image("far-away"))
    payload = {"photos": [
        {"id": i, "url": f"https://www.pexels.com/photo/x-{i}/",
         "src": {"original": f"https://images.pexels.com/{i}/o.jpg"},
         "photographer": "One Shoot" if i <= 5 else f"Other {i}",
         "width": 3000, "height": 2000} for i in range(1, 8)]}
    paths, stats = pool.search(FAMILY, terms=["cup"], platforms=("pexels",), keys={"pexels": "k"},
                               fetch=lambda u, headers=None: payload, download=any_download,
                               to_png=similar.to_png, pool_dir=tmp_path, attrs_mapping={},
                               styles_mapping={}, cal={}, log=lambda m: None)
    entries = yaml.safe_load(paths[0].read_text())["entries"]
    kept = [e for e in entries.values() if e["state"] == "pending" and e["creator"] == "One Shoot"]
    assert len(kept) == pool.MAX_PER_CREATOR
    capped = [e for e in entries.values() if "One Shoot this pass" in (e.get("drop") or "")]
    assert len(capped) == 5 - pool.MAX_PER_CREATOR and stats["dropped_by"]["creator"] == len(capped)
    # the other creators are untouched
    assert sum(1 for e in entries.values() if e["state"] == "pending" and e["creator"] != "One Shoot") == 2
    # and the cap can be lifted
    _, stats2 = pool.search(FAMILY, terms=["cup"], platforms=("pexels",), keys={"pexels": "k"},
                            fetch=lambda u, headers=None: {"photos": [
                                dict(p, id=p["id"] + 100) for p in payload["photos"]]},
                            download=any_download, to_png=similar.to_png, pool_dir=tmp_path,
                            attrs_mapping={}, styles_mapping={}, cal={}, max_per_creator=0,
                            log=lambda m: None)
    assert stats2["dropped_by"]["creator"] == 0


def test_search_walks_pages_breadth_first_and_stops_on_a_short_or_stale_page(tmp_path):
    write_corpus_hashes(tmp_path, noise_image("far-away"))
    seen = []

    def fetch(url, headers=None):
        q = query_of(url)
        page = int(q["page"])
        seen.append((q["query"], page))
        # the two terms find different photos, or the second would stale out on page 1
        return pexels_page(page, offset=0 if q["query"] == "cup" else 10_000) if page < 3 else {"photos": []}
    pool.search(FAMILY, terms=["cup", "mug"], platforms=("pexels",), keys={"pexels": "k"},
                fetch=fetch, download=any_download, to_png=similar.to_png, pool_dir=tmp_path,
                attrs_mapping={}, styles_mapping={}, pages=3, limit_per_term=500,
                cal={}, log=lambda m: None)
    # every term sees page 1 before any sees page 2: a spent budget still covers them all
    assert seen[:2] == [("cup", 1), ("mug", 1)] and seen[2:4] == [("cup", 2), ("mug", 2)]
    # a short page ends that term
    assert ("cup", 3) in seen and seen.count(("cup", 3)) == 1

    # a full page of ids we already hold yields nothing new and ends the term
    stale = []

    def fetch_stale(url, headers=None):
        stale.append(url)
        return pexels_page(1)
    _, stats = pool.search(FAMILY, terms=["cup"], platforms=("pexels",), keys={"pexels": "k"},
                           fetch=fetch_stale, download=any_download, to_png=similar.to_png,
                           pool_dir=tmp_path, attrs_mapping={}, styles_mapping={}, pages=3,
                           cal={}, log=lambda m: None)
    assert len(stale) == 1 and stats["new"] == 0
    assert stats["platforms"]["pexels"]["dup_id"] == 80


def test_search_deepens_only_terms_the_reviewers_keep(tmp_path):
    write_corpus_hashes(tmp_path, noise_image("far-away"))
    seen = []

    def fetch(url, headers=None):
        q = query_of(url)
        seen.append((q["query"], int(q["page"])))
        return pexels_page(int(q["page"]), offset=0 if q["query"] == "good" else 10_000)
    cal = {"rankers": {"histogram": {"terms": {FAMILY: {
        "good": {"n": 40, "kept": 20, "keep_rate": 0.5},
        "bad": {"n": 40, "kept": 1, "keep_rate": 0.03}}}}}}
    pool.search(FAMILY, terms=["good", "bad"], platforms=("pexels",), keys={"pexels": "k"},
                fetch=fetch, download=any_download, to_png=similar.to_png, pool_dir=tmp_path,
                attrs_mapping={}, styles_mapping={}, pages=2, limit_per_term=500,
                cal=cal, ranker_name="histogram", log=lambda m: None)
    assert ("good", 2) in seen and ("bad", 2) not in seen, "a term reviewers drop gets no second page"


def test_prefilters_reject_on_metadata_without_downloading(tmp_path):
    write_corpus_hashes(tmp_path, noise_image("far-away"))
    attrs_mapping, styles_mapping = portrait_corpus()
    downloaded = []

    def counting_download(url, dest, timeout=60):
        downloaded.append(url)
        return any_download(url, dest)

    def fetch(url, headers=None):
        return {"photos": [
            {"id": 1, "url": "u1", "src": {"original": "https://images.pexels.com/1/o.jpg"},
             "photographer": "A", "width": 1400, "height": 2400},   # portrait, big enough: kept
            {"id": 2, "url": "u2", "src": {"original": "https://images.pexels.com/2/o.jpg"},
             "photographer": "B", "width": 3000, "height": 2000},   # landscape: wrong shape
            {"id": 3, "url": "u3", "src": {"original": "https://images.pexels.com/3/o.jpg"},
             "photographer": "C", "width": 400, "height": 700},     # too small
            {"id": 4, "url": "u4", "src": {"original": ""},
             "photographer": "D", "width": 800, "height": 1400}]}   # no image
    paths, stats = pool.search(FAMILY, terms=["cup"], platforms=("pexels",), keys={"pexels": "k"},
                               fetch=fetch, download=counting_download, to_png=similar.to_png,
                               pool_dir=tmp_path, attrs_mapping=attrs_mapping,
                               styles_mapping=styles_mapping, cal={}, log=lambda m: None)
    pf = stats["platforms"]["pexels"]
    assert pf["prefiltered"] == {"no_image": 1, "min_width": 1, "aspect": 1, "licence": 0}
    assert len(downloaded) == 1 and stats["new"] == 1, "only the admitted photo costs bytes"
    assert set(yaml.safe_load(paths[0].read_text())["entries"]) == {"pexels-1"}
    assert pf["thumb_bytes"] > 0


def test_auto_orientation_is_asked_of_the_api_when_the_family_is_one_shape(tmp_path):
    write_corpus_hashes(tmp_path, noise_image("far-away"))
    attrs_mapping, styles_mapping = portrait_corpus()
    urls = []
    pool.search(FAMILY, terms=["cup"], platforms=("pexels",), keys={"pexels": "k"},
                fetch=lambda u, headers=None: urls.append(u) or {}, download=any_download,
                to_png=similar.to_png, pool_dir=tmp_path, attrs_mapping=attrs_mapping,
                styles_mapping=styles_mapping, cal={}, log=lambda m: None)
    assert "orientation=portrait" in urls[0]
    allowed, auto = pool.family_orientations(FAMILY, attrs_mapping, styles_mapping)
    assert auto == "portrait" and allowed == {"portrait"}
    # a family that uses every shape filters nothing and asks for nothing
    mixed_attrs, mixed_styles = portrait_corpus()
    for i, (src, rec) in enumerate(mixed_attrs.items()):
        rec.update({"width": 3000, "height": 2000} if i % 2 else {"width": 800, "height": 1400})
    allowed, auto = pool.family_orientations(FAMILY, mixed_attrs, mixed_styles)
    assert auto is None and allowed == {"portrait", "landscape"}


def test_dry_run_plans_the_requests_without_making_any(tmp_path):
    def boom(url, headers=None):
        raise AssertionError("a dry run must not fetch")
    plan, stats = pool.plan(FAMILY, terms=["cup", "mug"], platforms=("pexels",),
                            keys={"pexels": "k"}, pages=2, pool_dir=tmp_path,
                            attrs_mapping={}, styles_mapping={}, cal={}, log=lambda m: None)
    assert plan["pexels"]["planned"] == 4 and plan["pexels"]["to_fetch"] == 4
    assert stats["dry_run"] and stats["terms"] == 2
    _ = boom  # the planner never takes a fetcher at all


def test_threshold_auto_drops_the_tail_but_keeps_an_exploration_slice(tmp_path):
    write_corpus_hashes(tmp_path, noise_image("far-away"))
    cal = {"rankers": {"histogram": {"threshold": 0.9}}}  # above anything a noise image scores

    def fetch(url, headers=None):
        return pexels_page(1, n=40)
    paths, stats = pool.search(FAMILY, terms=["cup"], platforms=("pexels",), keys={"pexels": "k"},
                               fetch=fetch, download=any_download, to_png=similar.to_png,
                               pool_dir=tmp_path, attrs_mapping={}, styles_mapping={},
                               limit_per_term=500, cal=cal, ranker_name="histogram",
                               log=lambda m: None)
    entries = yaml.safe_load(paths[0].read_text())["entries"]
    explored = [e for e in entries.values() if e.get("explored")]
    dropped = [e for e in entries.values() if "below calibrated threshold" in (e.get("drop") or "")]
    assert dropped and explored, "the tail is dropped, a slice of it still reaches a sheet"
    assert all(e["state"] == "pending" for e in explored)
    assert stats["auto_dropped"] == len(dropped) == stats["dropped_by"]["threshold"]
    assert len(explored) + len(dropped) == 40
    # deterministic in the id, so a re-run samples the same tail
    assert pool.explored("pexels-1") == pool.explored("pexels-1")
    # and the threshold can be switched off entirely
    _, stats2 = pool.search(FAMILY, terms=["cup"], platforms=("pexels",), keys={"pexels": "k"},
                            fetch=lambda u, headers=None: pexels_page(1, n=10, offset=500), download=any_download,
                            to_png=similar.to_png, pool_dir=tmp_path, attrs_mapping={},
                            styles_mapping={}, cal=cal, use_threshold=False,
                            ranker_name="histogram", log=lambda m: None)
    assert stats2["auto_dropped"] == 0 and stats2["new"] == 10


def test_sheets_stamp_their_cells_and_never_resheet_them(tmp_path):
    seed_entries(tmp_path, n=4, state="pending")
    written, stats = pool.build_sheets(FAMILY, pool_dir=tmp_path, attrs_mapping={},
                                       styles_mapping={}, log=lambda m: None)
    assert stats == {"pending": 4, "sheets": 1}
    entries = pool.load(FAMILY, tmp_path)["entries"]
    assert all(e["sheet"] == written[0]["name"] for e in entries.values())
    # a second pass has nothing new to review: tokens follow what a search found
    _, stats2 = pool.build_sheets(FAMILY, pool_dir=tmp_path, attrs_mapping={},
                                   styles_mapping={}, log=lambda m: None)
    assert stats2 == {"pending": 0, "sheets": 0}
    _, stats3 = pool.build_sheets(FAMILY, pool_dir=tmp_path, attrs_mapping={},
                                   styles_mapping={}, resheet=True, log=lambda m: None)
    assert stats3 == {"pending": 4, "sheets": 1}


CINEMATIC = "cinematic-still"


def two_family_corpus(tmp_path, n=6):
    """Red landscape/portrait full-bleed against blue 9:16 cinematic-still —
    separable by colour for the fake encoder, and by shape for the gates."""
    attrs_mapping, styles_mapping = {}, {}
    for i in range(n):
        for fam, colour, (w, h), aspect in (
                (FAMILY, (200, 30, 30), (3000, 2000) if i % 2 else (1500, 2000), "3:2" if i % 2 else "3:4"),
                (CINEMATIC, (30, 30, 200), (1080, 1920), "9:16")):
            # real corpus ids are the uuid's first 8 hex, and blindcheck greps for exactly that
            prefix = "fb" if fam == FAMILY else "cc"
            src = f"https://cdn.picsart.io/p/{prefix}{i:06x}-0000-4000-8000-00000000000{i}.png"
            local = tmp_path / f"c-{fam}-{i}.png"
            solid(local, colour, jitter=20)
            attrs_mapping[src] = {"local": str(local), "kind": "image", "width": w, "height": h,
                                  "aspect_class": aspect, "ground": "photo-full-bleed", "layout": "single"}
            styles_mapping[src] = {"style": fam}
    return attrs_mapping, styles_mapping


def coloured_download(url, dest, timeout=60):
    """Blue for the photo we expect to be reallocated, red otherwise. The real
    downloader writes bytes to a `.bin`, so the format cannot come from the name."""
    colour = (30, 30, 200) if "blue" in url else (200, 30, 30)
    rng = random.Random(str(colour))
    im = Image.new("RGB", (32, 32))
    im.putdata([tuple(min(255, max(0, c + rng.randrange(-20, 20))) for c in colour)
                for _ in range(32 * 32)])
    im.save(dest, format="PNG")
    return dest


def shaped_payload(photos):
    return {"photos": [{"id": i, "url": f"https://www.pexels.com/photo/{tagname}-{i}/",
                        "src": {"original": f"https://images.pexels.com/{tagname}-{i}/o.jpg"},
                        "photographer": f"P{i}", "width": w, "height": h}
                       for i, tagname, w, h in photos]}


def test_clip_ranker_scores_every_family_gates_shape_and_reallocates(tmp_path):
    write_corpus_hashes(tmp_path, noise_image("far-away"))
    attrs_mapping, styles_mapping = two_family_corpus(tmp_path)
    ranker = pool.ClipRanker(encoder=FakeEncoder(), cache_dir=tmp_path / "_embed")
    payload = shaped_payload([(1, "blue", 1440, 2560), (2, "red", 3000, 2000)])
    paths, stats = pool.search(FAMILY, terms=["cup"], platforms=("pexels",), keys={"pexels": "k"},
                               fetch=lambda u, headers=None: payload, download=coloured_download,
                               to_png=similar.to_png, pool_dir=tmp_path, attrs_mapping=attrs_mapping,
                               styles_mapping=styles_mapping, ranker=ranker, cal={}, log=lambda m: None)
    assert stats["ranker"] == "clip" and stats["moved"] == 1
    by_family = {path.stem: yaml.safe_load(path.read_text())["entries"] for path in paths}
    # the 9:16 blue photo was searched as full-bleed and belongs to cinematic-still
    moved = by_family[CINEMATIC]["pexels-1"]
    assert moved["moved_from"] == FAMILY and moved["searched_family"] == FAMILY
    assert moved["best_family"] == CINEMATIC and moved["family_scores"][FAMILY] == 0.0
    assert "pexels-1" not in by_family.get(FAMILY, {}), "an entry lives in exactly one family yaml"
    # the landscape red photo stays where it was searched
    stayed = by_family[FAMILY]["pexels-2"]
    assert "moved_from" not in stayed and stayed["best_family"] == FAMILY
    assert stayed["family_scores"][CINEMATIC] == 0.0, "a landscape photo is gated out of 9:16"
    assert all(re.fullmatch(r"[0-9a-f]{8}", a) for a in stayed["nearest"]), "nearest stays corpus asset ids"
    assert sum(len(e) for e in by_family.values()) == len(pool.all_entries(tmp_path))


def test_ratio_gates_agree_with_the_rule_table_and_a_split_gates_everything(tmp_path):
    # the rule table splits the two photo families on 9:16 alone, so the gates must too
    rec = {"ground": "photo-full-bleed", "layout": "single", "panel_count": 1,
           "aspect_class": "9:16", "type": "gallery"}
    assert taxonomy.family_of(rec)[0] == CINEMATIC
    assert taxonomy.family_of(dict(rec, aspect_class="3:2"))[0] == FAMILY
    assert pool.RATIO_GATES[CINEMATIC](9 / 16) and not pool.RATIO_GATES[FAMILY](9 / 16)
    assert pool.RATIO_GATES[FAMILY](3 / 2) and not pool.RATIO_GATES[CINEMATIC](3 / 2)
    # a photo that is already a before/after split is not raw material for any family
    attrs_mapping, styles_mapping = two_family_corpus(tmp_path, n=3)
    ranker = pool.ClipRanker(encoder=FakeEncoder(), cache_dir=tmp_path / "_embed")
    ranker.prepare(FAMILY, attrs_mapping, styles_mapping, log=lambda m: None)
    thumb = solid(tmp_path / "cand.png", (200, 30, 30), jitter=20)
    scores = ranker.score(thumb, {"before_after": True}, (3000, 2000))
    assert set(scores) == {FAMILY, CINEMATIC} and all(v[0] == 0.0 for v in scores.values())
    assert ranker.score(thumb, {}, (3000, 2000))[FAMILY][0] > 0


def test_layout_intake_keeps_the_splits_the_bare_intake_throws_away(tmp_path):
    """Two different things are wanted from stock: the raw photograph that goes
    inside the chrome, and a picture already laid out like the chrome. The
    second is exactly what the bare intake scores 0, so the mode has to reach
    the gate — otherwise no collage or split can ever enter the pool."""
    attrs_mapping, styles_mapping = two_family_corpus(tmp_path, n=3)
    thumb = solid(tmp_path / "split.png", (200, 30, 30), jitter=20)
    scored = {}
    for mode in pool.COMPOSITIONS:
        ranker = pool.ClipRanker(encoder=FakeEncoder(), cache_dir=tmp_path / "_embed",
                                 composition=mode)
        ranker.prepare(FAMILY, attrs_mapping, styles_mapping, log=lambda m: None)
        scored[mode] = ranker.score(thumb, {"before_after": True}, (3000, 2000))[FAMILY][0]
    assert scored[pool.BARE] == 0.0, "a pre-split photo is not raw material"
    assert scored[pool.LAYOUT] > 0.0, "the same photo IS a compositional reference"


def test_an_indistinct_family_cannot_receive_a_reallocation(tmp_path):
    """`self - bg` is the normaliser AND the confidence. On the real corpus
    outcome-tile scores 0.011 (16 assets, barely distinct from anything) and
    full-bleed 0.029 (so broad it IS the background); dividing by either
    saturates every candidate to 1.0, which is how outcome-tile swallowed 219
    portrait photos on the first live sweep."""
    attrs_mapping, styles_mapping = two_family_corpus(tmp_path, n=4)
    ranker = pool.ClipRanker(encoder=FakeEncoder(), cache_dir=tmp_path / "_embed")
    ranker.prepare(FAMILY, attrs_mapping, styles_mapping, log=lambda m: None)
    for fam, rec in ranker.families.items():
        assert rec["reliable"] is (rec["span"] >= pool.SPAN_MIN), fam
    # a family whose own photographs are indistinct is not a place to move to
    ranker.families[CINEMATIC].update(span=0.001, reliable=False)
    assert ranker.reliable(FAMILY) and not ranker.reliable(CINEMATIC)
    # the divisor is floored, so a collapsed span cannot saturate the score
    ranker.families[CINEMATIC].update(**{"self": 0.35, "bg": 0.34})
    blue = solid(tmp_path / "blue-cand.png", (30, 30, 200), jitter=20)
    assert ranker.score(blue, {}, (1440, 2560))[CINEMATIC][0] < 1.0
    # and the histogram ranker never reallocates at all
    assert pool.HistogramRanker().reliable(FAMILY) is False


def test_a_thin_family_is_shrunk_toward_the_whole_corpus(tmp_path):
    """vs-two-up has 15 assets against full-bleed's 756: its own dozen cannot
    carry a score on their own, so the whole corpus pulls it back."""
    attrs_mapping, styles_mapping = two_family_corpus(tmp_path, n=8)
    ranker = pool.ClipRanker(encoder=FakeEncoder(), cache_dir=tmp_path / "_embed")
    ranker.prepare(FAMILY, attrs_mapping, styles_mapping, log=lambda m: None)
    assert ranker.families[FAMILY]["n"] == 8 and ranker.families[FAMILY]["k"] == pool.K_MIN
    # k scales with the family, clamped at both ends
    assert ranker.families[FAMILY]["k"] == int(min(max(8 // 8, pool.K_MIN), pool.K_MAX))
    assert 0.0 <= ranker.families[FAMILY]["bg"] < ranker.families[FAMILY]["self"] <= 1.0


def test_rank_prefers_the_family_look_and_before_after_scores_ground_only():
    red_h = pool_histogram(Image.new("RGB", (32, 32), (200, 30, 30)))
    blue_h = pool_histogram(Image.new("RGB", (32, 32), (30, 30, 200)))
    hists = [("11111111", red_h)]
    freq = {"ground": {"solid-colour": 1.0}, "layout": {"split": 1.0}}
    feats = {"ground": "solid-colour", "layout": "single"}
    red_score, nearest = pool.score(red_h, feats, hists, freq, "before-after")
    blue_score, _ = pool.score(blue_h, feats, hists, freq, "before-after")
    assert red_score > blue_score and nearest == ["11111111"]
    # before-after ranks on ground alone (its corpus assets measure split);
    # any other family averages ground and layout, so the mismatch halves it
    assert pool.score(red_h, feats, hists, freq, "before-after")[0] > \
        pool.score(red_h, feats, hists, freq, "full-bleed")[0]


def pool_histogram(im):
    import io
    buf = io.BytesIO()
    im.save(buf, format="PNG")
    buf.seek(0)
    return pool.histogram(buf)


def seed_entries(pool_dir, n=6, state="kept", **overrides):
    data = pool.load(FAMILY, pool_dir)
    for i in range(1, n + 1):
        eid = f"pexels-{i}"
        im = noise_image(f"e{i}")
        pool.thumb_path(eid, pool_dir).parent.mkdir(parents=True, exist_ok=True)
        im.save(pool.thumb_path(eid, pool_dir))
        data["entries"][eid] = dict(
            {"url": f"https://www.pexels.com/photo/x-{i}/", "image": f"https://images.pexels.com/{i}/orig.jpeg",
             "thumb": f"https://images.pexels.com/{i}/large.jpeg", "creator": f"Photographer {i}",
             "creator_url": "", "platform": "Pexels", "licence": "Pexels", "width": 3000, "height": 2000,
             "aspect_class": "3:2", "term": "cup", "collected": "2026-09-12", "phash": phash.dhash(im),
             "features": {"ground": "solid-colour"}, "score": round(0.9 - i * 0.1, 2),
             "nearest": [], "state": state}, **overrides)
    pool.save(data, pool_dir)
    return data


def test_sheets_and_labels_flip_states_and_validate(tmp_path):
    seed_entries(tmp_path, n=4, state="pending")
    written, stats = pool.build_sheets(FAMILY, pool_dir=tmp_path, attrs_mapping={},
                                       styles_mapping={}, log=lambda m: None)
    assert stats == {"pending": 4, "sheets": 1} and written[0]["png"].exists()
    sheets_dir = tmp_path / "sheets"
    man = yaml.safe_load((sheets_dir / f"{written[0]['name']}.yaml").read_text())
    assert [c["id"] for c in man["cells"].values()] == ["pexels-1", "pexels-2", "pexels-3", "pexels-4"]  # score order
    assert "keep" in (sheets_dir / f"README-{FAMILY}.md").read_text()
    # corpus re-check: cell 1's photo is (now) a corpus asset, so keeping it must fail
    write_corpus_hashes(tmp_path, noise_image("e1"))
    (sheets_dir / man["answers"]).write_text(yaml.safe_dump(
        {1: "keep", 2: "drop", 3: {"keep": True, "subject": "person"}, 4: {"keep": True, "subject": "alien"}}))
    stats = pool.ingest_labels(FAMILY, pool_dir=tmp_path, log=lambda m: None)
    entries = pool.load(FAMILY, tmp_path)["entries"]
    assert entries["pexels-1"]["state"] == "dropped" and "corpus aabbccdd" in entries["pexels-1"]["drop"]
    assert entries["pexels-2"]["state"] == "dropped" and entries["pexels-2"]["drop"] == "off-style (sheet answer)"
    assert entries["pexels-3"]["state"] == "kept" and entries["pexels-3"]["subject"] == "person"
    assert entries["pexels-4"]["state"] == "pending"  # bad subject: reported, not written
    assert any("subject" in e for e in stats["errors"]) and any("corpus aabbccdd" in e for e in stats["errors"])
    assert (stats["kept"], stats["dropped"]) == (1, 2)


def test_sheets_carry_anchors_and_genre_and_best_family_moves_an_entry(tmp_path):
    write_corpus_hashes(tmp_path, noise_image("far-away"))  # or the merge rebuilds the real corpus
    attrs_mapping, styles_mapping = two_family_corpus(tmp_path, n=3)
    refs = tmp_path / "references"
    refs.mkdir()
    (refs / f"{FAMILY}.yaml").write_text(yaml.safe_dump(
        {"photography": {"genre": "One uninterrupted picture that fills the slot."}}))
    seed_entries(tmp_path, n=2, state="pending",
                 family_scores={FAMILY: 0.4, CINEMATIC: 0.8}, searched_family=FAMILY)
    written, _ = pool.build_sheets(FAMILY, pool_dir=tmp_path, attrs_mapping=attrs_mapping,
                                   styles_mapping=styles_mapping, references_dir=refs,
                                   log=lambda m: None)
    sheets_dir = tmp_path / "sheets"
    man = yaml.safe_load((sheets_dir / f"{written[0]['name']}.yaml").read_text())
    assert len(man["anchors"]) == pool.ANCHORS and all(re.fullmatch(r"[0-9a-f]{8}", a) for a in man["anchors"])
    assert man["genre"].startswith("One uninterrupted picture")
    assert man["cells"][1]["family_scores"] == {FAMILY: 0.4, CINEMATIC: 0.8}
    readme = (sheets_dir / f"README-{FAMILY}.md").read_text()
    assert "Row 1 is 3 Picsart originals" in readme and "One uninterrupted picture" in readme
    assert "best_family" in readme
    # a reviewer moves the good photo to where it belongs; the other is judged here
    (sheets_dir / man["answers"]).write_text(yaml.safe_dump(
        {1: {"keep": True, "best_family": CINEMATIC}, 2: {"keep": True, "note": "borderline crop"}}))
    stats = pool.ingest_labels(FAMILY, pool_dir=tmp_path, log=lambda m: None)
    assert stats["moved"] == 1 and stats["kept"] == 2
    assert "pexels-1" not in pool.load(FAMILY, tmp_path)["entries"]
    moved = pool.load(CINEMATIC, tmp_path)["entries"]["pexels-1"]
    assert moved["moved_from"] == FAMILY and moved["state"] == "kept" and moved["score"] == 0.8
    assert pool.load(FAMILY, tmp_path)["entries"]["pexels-2"]["note"] == "borderline crop"


def test_one_unparseable_answers_file_does_not_sink_the_merge(tmp_path):
    """19% of a live review pass wrote `{keep: true, note: a, b}` — a flow
    mapping where the comma ends the value. One bad file used to abort the
    whole merge and cost the other sheets their labour."""
    write_corpus_hashes(tmp_path, noise_image("far-away"))
    seed_entries(tmp_path, n=4, state="pending")
    written, _ = pool.build_sheets(FAMILY, pool_dir=tmp_path, attrs_mapping={},
                                   styles_mapping={}, log=lambda m: None)
    sheets_dir = tmp_path / "sheets"
    man = yaml.safe_load((sheets_dir / f"{written[0]['name']}.yaml").read_text())
    # the exact shape the reviewers produced: `#10` starts a yaml comment, which
    # eats the closing brace, so the flow mapping runs on into the next line
    (sheets_dir / man["answers"]).write_text(
        "1: {keep: true, note: same shoot as #10 but a distinct frame}\n2: drop\n")
    stats = pool.ingest_labels(FAMILY, pool_dir=tmp_path, log=lambda m: None)
    assert stats["kept"] == 0 and any("not valid yaml" in e for e in stats["errors"])
    assert pool.load(FAMILY, tmp_path)["entries"]["pexels-1"]["state"] == "pending"
    # a comma instead parses, silently truncating the note into a junk key
    keep, extras, err = pool.parse_answer({"keep": True, "note": "warm bokeh", "grade muted": None})
    assert err and "unknown key" in err and not extras
    # the same answers, written the way the prompt now shows, merge fine
    (sheets_dir / man["answers"]).write_text(
        "1:\n  keep: true\n  note: 'low-key night portrait, warm bokeh'\n")
    stats = pool.ingest_labels(FAMILY, pool_dir=tmp_path, log=lambda m: None)
    assert stats["kept"] == 1 and not stats["errors"]
    assert pool.load(FAMILY, tmp_path)["entries"]["pexels-1"]["note"] == "low-key night portrait, warm bokeh"


def test_answers_reject_an_unknown_family_or_an_overlong_note():
    keep, extras, err = pool.parse_answer({"keep": False, "best_family": "cinematic-still"})
    assert keep is False and extras["best_family"] == "cinematic-still" and err is None
    assert pool.parse_answer({"keep": True, "best_family": "nope"})[2].startswith("best_family")
    assert pool.parse_answer({"keep": True, "note": "x" * (pool.NOTE_MAX + 1)})[2].startswith("note")
    assert pool.parse_answer({"keep": True, "note": "fine"})[1]["note"] == "fine"


def test_labels_ping_unsplash_downloads_once(tmp_path):
    write_corpus_hashes(tmp_path, noise_image("far-away"))
    seed_entries(tmp_path, n=1, state="pending",
                 download_location="https://api.unsplash.com/photos/abc/download")
    written, _ = pool.build_sheets(FAMILY, pool_dir=tmp_path, attrs_mapping={},
                                   styles_mapping={}, log=lambda m: None)
    (tmp_path / "sheets" / f"{written[0]['name']}.answers.yaml").write_text("1: keep\n")
    pings = []
    pool.ingest_labels(FAMILY, pool_dir=tmp_path, keys={"unsplash": "k"},
                       fetch=lambda u, headers=None: pings.append(u), log=lambda m: None)
    assert pings == ["https://api.unsplash.com/photos/abc/download"]
    assert pool.load(FAMILY, tmp_path)["entries"]["pexels-1"]["downloaded"] is True
    # a second merge does not ping again
    pool.ingest_labels(FAMILY, pool_dir=tmp_path, keys={"unsplash": "k"},
                       fetch=lambda u, headers=None: pings.append(u), log=lambda m: None)
    assert len(pings) == 1


def judged(pool_dir, rows, family=FAMILY):
    """Entries as a finished review pass leaves them: scored, sheeted, answered."""
    data = pool.load(family, pool_dir)
    for i, (score, keep, term) in enumerate(rows, 1):
        eid = f"pexels-{i}"
        data["entries"][eid] = {
            "url": f"https://www.pexels.com/photo/x-{i}/", "image": f"https://images.pexels.com/{i}/o.jpg",
            "creator": "P", "platform": "Pexels", "licence": "pexels", "tier": "pool",
            "phash": "0" * 16, "score": score, "state": "kept" if keep else "dropped",
            "term": term, "ranker": "histogram", "sheet": "sheet-abc",
            **({} if keep else {"drop": "off-style (sheet answer)"})}
    pool.save(data, pool_dir)
    return data


def test_calibrate_finds_a_threshold_prunes_terms_and_search_obeys_it(tmp_path):
    from landing_page_gen.corpus import calibration
    # scores correlate with keeping; "dud" is a term nobody keeps
    rows = [(0.9, 1, "good"), (0.85, 1, "good"), (0.8, 1, "good"), (0.75, 1, "good"),
            (0.7, 1, "good"), (0.65, 0, "good"), (0.6, 1, "good"), (0.55, 0, "good")]
    rows += [(0.5 - i * 0.02, 0, "dud") for i in range(22)]
    judged(tmp_path, rows)
    cal = calibration.calibrate({FAMILY: pool.load(FAMILY, tmp_path)["entries"]}, today="2026-09-16")
    rec = cal["rankers"]["histogram"]
    assert rec["labels"] == 30 and rec["auc"] > 0.9
    assert rec["threshold"] is not None and rec["threshold_recall"] >= 0.95
    assert rec["would_skip"] > 0.5, "most of the pile is below the bar"
    assert sum(d["n"] for d in rec["deciles"]) == 30
    assert rec["terms"][FAMILY]["dud"]["prune"] is True
    assert "prune" not in rec["terms"][FAMILY]["good"]
    assert rec["platforms"]["Pexels"]["n"] == 30
    # the accessors the search loop reads
    assert calibration.threshold_for(cal, "histogram", FAMILY) == rec["threshold"]
    assert calibration.keep_rate_for(cal, "histogram", FAMILY, "dud") == 0.0
    assert calibration.keep_rate_for(cal, "histogram", FAMILY, "never seen") is None
    # a dropped-by-dedupe entry was never judged and must not count as a label
    data = pool.load(FAMILY, tmp_path)
    data["entries"]["pexels-99"] = dict(data["entries"]["pexels-1"],
                                        state="dropped", drop="near-dup of corpus aabbccdd (hamming 0)")
    pool.save(data, tmp_path)
    again = calibration.calibrate({FAMILY: pool.load(FAMILY, tmp_path)["entries"]}, today="2026-09-16")
    assert again["rankers"]["histogram"]["labels"] == 30
    assert calibration.save(again, tmp_path / "_calibration.yaml").exists()


def test_quota_is_inverse_square_root_of_what_the_corpus_already_has():
    counts = {FAMILY: 756, CINEMATIC: 360, "vs-two-up": 15}
    assert pool.quota(FAMILY, counts) == 60           # the largest family gets the base
    assert pool.quota("vs-two-up", counts) == 426     # about 7x, not 50x
    assert pool.quota(CINEMATIC, counts) == 87
    assert pool.quota("unseen", {}) == pool.QUOTA_BASE
    # a family whose candidates rarely survive review asks for proportionally more
    cal = {"rankers": {"histogram": {"families": {FAMILY: {"keep_rate": 0.2}}}}}
    assert pool.quota(FAMILY, counts, cal=cal) == 300
    # per-term limits stay inside what a page can return
    _, per_term = pool.plan_search("vs-two-up", counts, ["a", "b"])
    assert per_term == 80 and pool.plan_search(FAMILY, counts, ["a"] * 30)[1] == 5


def test_family_check_is_leave_one_out_and_reports_the_merged_photo_bucket(tmp_path):
    from landing_page_gen.corpus import calibration, embed as embed_mod
    attrs_mapping, styles_mapping = two_family_corpus(tmp_path, n=4)
    emb, _ = embed_mod.corpus_embeddings(FakeEncoder(), attrs_mapping, styles_mapping,
                                         cache_dir=tmp_path / "_embed", log=lambda m: None)
    fc = calibration.family_check(emb)
    assert fc["n"] == 8 and fc["argmax_vs_tag"] == 1.0, "colour-separated families are perfectly recovered"
    assert fc["argmax_vs_tag_merged_photo"] == 1.0
    assert set(fc["confusion"]) == {FAMILY, CINEMATIC}
    # the hint is the only non-circular signal, and it is reported against the tag too
    hints = {aid: CINEMATIC for aid in emb.ids}
    fc2 = calibration.family_check(emb, hints)
    assert fc2["argmax_vs_hint"] == 0.5 and fc2["hint_vs_tag"] == 0.5


def test_pick_rotates_by_seed_and_stays_blind(tmp_path):
    seed_entries(tmp_path, n=6)
    a = [e["id"] for e in pool.pick(FAMILY, 3, "runs/live-5", pool_dir=tmp_path)]
    assert a == [e["id"] for e in pool.pick(FAMILY, 3, "runs/live-5", pool_dir=tmp_path)]  # same run, same picks
    b = [e["id"] for e in pool.pick(FAMILY, 3, "runs/live-6", pool_dir=tmp_path)]
    assert a != b, "a new run rotates to different picks"
    # an excluded 8-hex id anywhere in the entry drops it
    data = pool.load(FAMILY, tmp_path)
    data["entries"]["pexels-1"]["nearest"] = ["deadbeef"]
    data["entries"]["pexels-2"]["url"] = "https://blog.example/deadbeef-cup/"
    pool.save(data, tmp_path)
    for e in pool.pick(FAMILY, 6, "s", exclude_asset=["deadbeef"], pool_dir=tmp_path):
        assert e["id"] not in ("pexels-1", "pexels-2")
    # aspect filter
    data["entries"]["pexels-3"]["aspect_class"] = "1:1"
    pool.save(data, tmp_path)
    assert {e["id"] for e in pool.pick(FAMILY, 6, "s", aspect_class="1:1", pool_dir=tmp_path)} == {"pexels-3"}
    # only kept entries are served
    data["entries"]["pexels-4"]["state"] = "pending"
    pool.save(data, tmp_path)
    assert "pexels-4" not in {e["id"] for e in pool.pick(FAMILY, 6, "s", pool_dir=tmp_path)}


def test_write_examples_is_licensed_and_blind(tmp_path):
    seed_entries(tmp_path, n=2)
    picks = pool.pick(FAMILY, 2, "s", pool_dir=tmp_path)
    out = tmp_path / "examples"
    written = pool.write_examples(picks, out, fake_download, similar.to_png,
                                  pool_dir=tmp_path, log=lambda m: None, start=3)
    assert [p.name for p in written] == ["p3-pool.md", "p4-pool.md"]
    body = written[0].read_text()
    assert "origin: pool" in body and "licence: pexels" in body and "never" in body
    assert "attribution_required: false" in body and "Photo by Photographer 1 on Pexels" in body
    assert (out / "p3-pool.png").exists()
    for md in written:
        text = md.read_text()
        assert not re.search(r"\b[0-9a-f]{8}\b", text), "no 8-hex asset id may reach a brief"
        assert not re.search(r"^(snapshot|source): ", text, re.M)


def test_each_intake_mode_reads_its_own_reference_block(tmp_path):
    """The bare photograph and the arrangement are found by different queries
    and described to a reviewer in different words, so they live in different
    blocks. A mode with no terms must say which block is empty."""
    refs = tmp_path / "references"
    refs.mkdir()
    (refs / f"{FAMILY}.yaml").write_text(yaml.safe_dump({
        "photography": {"genre": "One picture filling the slot.",
                        "search_terms": ["moody portrait"]},
        "layout": {"arrangement": "Two panels split down the middle.",
                   "search_terms": ["before after split screen"]}}))
    assert pool.reference_terms(FAMILY, refs) == ["moody portrait"]
    assert pool.reference_terms(FAMILY, refs, pool.LAYOUT) == ["before after split screen"]
    assert pool.reference_genre(FAMILY, refs).startswith("One picture")
    assert pool.reference_genre(FAMILY, refs, pool.LAYOUT).startswith("Two panels")
    # a family collected for bare only names the block the layout sweep needs
    (refs / f"{CINEMATIC}.yaml").write_text(yaml.safe_dump(
        {"photography": {"genre": "g", "search_terms": ["t"]}}))
    assert pool.reference_terms(CINEMATIC, refs, pool.LAYOUT) == []
    try:
        pool._resolve(CINEMATIC, None, ("pexels",), {"pexels": "k"}, tmp_path, refs, pool.LAYOUT)
        assert False, "should refuse a sweep with no terms"
    except ValueError as exc:
        assert "layout.search_terms" in str(exc)


def test_a_sheet_never_mixes_intake_modes_and_each_gets_its_own_prompt(tmp_path):
    """A bare photograph and an arrangement are judged against different
    things. One sheet carrying both, under one instruction, can only be right
    about half of it."""
    write_corpus_hashes(tmp_path, noise_image("far-away"))
    attrs_mapping, styles_mapping = two_family_corpus(tmp_path, n=3)
    refs = tmp_path / "references"
    refs.mkdir()
    (refs / f"{FAMILY}.yaml").write_text(yaml.safe_dump({
        "photography": {"genre": "One picture filling the slot."},
        "layout": {"arrangement": "Two equal panels, hard vertical divide."}}))
    seed_entries(tmp_path, n=4, state="pending")
    data = pool.load(FAMILY, tmp_path)
    for i, eid in enumerate(sorted(data["entries"])):
        data["entries"][eid]["composition"] = pool.LAYOUT if i < 2 else pool.BARE
    pool.save(data, tmp_path)
    written, _ = pool.build_sheets(FAMILY, pool_dir=tmp_path, per_sheet=12, attrs_mapping=attrs_mapping,
                                   styles_mapping=styles_mapping, references_dir=refs,
                                   log=lambda m: None)
    modes = sorted(s["composition"] for s in written)
    assert modes == [pool.BARE, pool.LAYOUT], "one sheet per mode, not one sheet of both"
    sheets_dir = tmp_path / "sheets"
    for sheet in written:
        man = yaml.safe_load((sheets_dir / f"{sheet['name']}.yaml").read_text())
        assert man["composition"] == sheet["composition"]
        entries = pool.load(FAMILY, tmp_path)["entries"]
        assert {entries[c["id"]]["composition"] for c in man["cells"].values()} == {man["composition"]}
    readme = (sheets_dir / f"README-{FAMILY}.md").read_text()
    assert "## Prompt — bare" in readme and "## Prompt — layout" in readme
    assert "One picture filling the slot" in readme and "Two equal panels" in readme
    # the layout prompt must invert the two bare rules, or reviewers drop what it collected
    layout = pool.prompt(FAMILY, refs, pool.LAYOUT)
    assert "watermarks are expected" in layout and "not duplicates" in layout
    assert "text-heavy" in pool.prompt(FAMILY, refs, pool.BARE)


def test_limit_per_term_caps_admissions_not_pages(tmp_path):
    """The cap used to be checked after a whole page was admitted, so a limit
    of 3 against an 80-result page let all 80 in. Every surplus candidate is a
    sheet cell paid for in review tokens."""
    write_corpus_hashes(tmp_path, noise_image("far-away"))
    payload = {"photos": [{"id": i, "url": f"https://www.pexels.com/photo/p-{i}/",
                           "src": {"original": f"https://images.pexels.com/photos/{i}/p.jpeg"},
                           "photographer": f"P{i}", "width": 3000, "height": 2000}
                          for i in range(1, stock.PER_PAGE["pexels"] + 1)]}
    _, stats = pool.search(FAMILY, terms=["cup"], platforms=("pexels",), keys={"pexels": "k"},
                           fetch=lambda u, headers=None: payload, download=any_download,
                           to_png=similar.to_png, pool_dir=tmp_path, attrs_mapping={},
                           styles_mapping={}, ranker_name="histogram", limit_per_term=3,
                           max_per_creator=99, log=lambda m: None)
    assert stats["raw"] == 3, f"admitted {stats['raw']} against a cap of 3"
    assert stats["platforms"]["pexels"]["results"] == stock.PER_PAGE["pexels"], "the page still arrived whole"


def test_cli_search_reaches_pool_search_with_every_flag_once(tmp_path, monkeypatch):
    """The unit tests call pool.search directly, so nothing covered the CLI's
    own argument wiring — and `composition` went out both inside the shared
    kwargs and again explicitly, which is a TypeError on every invocation.
    This asserts the call is made, once, with the flags the user typed."""
    from landing_page_gen.corpus import cli
    seen = {}

    def fake_search(family, **kw):
        seen["family"], seen["kw"] = family, kw
        return [], {"platforms": {}, "skipped_platforms": [], "raw": 0, "new": 0,
                    "dropped": 0, "moved": 0, "auto_dropped": 0, "elapsed_s": 0.0,
                    "ranker": "histogram", "dropped_by": {}, "rate_limited": False}
    monkeypatch.setattr(pool, "search", fake_search)
    monkeypatch.setattr(stock, "keys_available", lambda platforms, keys=None, environ=None: ({}, []))
    rc = cli.main(["pool", "search", FAMILY, "--out", str(tmp_path), "--composition", "layout",
                   "--limit-per-term", "7", "--max-per-creator", "8", "--rank", "histogram",
                   "--platform", "pexels"])
    assert rc == 0, "the CLI search path runs"
    assert seen["family"] == FAMILY
    assert seen["kw"]["composition"] == pool.LAYOUT
    assert seen["kw"]["limit_per_term"] == 7 and seen["kw"]["max_per_creator"] == 8
    assert seen["kw"]["platforms"] == ("pexels",)


def test_corpus_hashes_is_incremental_and_cannot_be_erased(tmp_path):
    """Write-once was the bug: this file is what stops a stock photo that IS one
    of Picsart's own source images from entering the pool, so a corpus that has
    grown since it was written must not leave the new assets unguarded. It also
    must survive an injected empty mapping."""
    a, b = noise_image("one"), noise_image("two")
    pa, pb = tmp_path / "a.png", tmp_path / "b.png"
    a.save(pa); b.save(pb)
    src_a, src_b = "https://cdn.picsart.io/a.png", "https://cdn.picsart.io/b.png"
    attrs_mapping = {src_a: {"local": str(pa)}}
    styles_mapping = {src_a: {"style": FAMILY}}
    first = pool.corpus_hashes(pool_dir=tmp_path, attrs_mapping=attrs_mapping,
                               styles_mapping=styles_mapping, log=lambda m: None)
    assert set(first) == {src_a} and first[src_a]["family"] == FAMILY
    # the corpus grows: the new asset is hashed, the old one is not re-hashed
    attrs_mapping[src_b] = {"local": str(pb)}
    styles_mapping[src_b] = {"style": CINEMATIC}
    second = pool.corpus_hashes(pool_dir=tmp_path, attrs_mapping=attrs_mapping,
                                styles_mapping=styles_mapping, log=lambda m: None)
    assert set(second) == {src_a, src_b}
    assert second[src_a]["phash"] == first[src_a]["phash"]
    # a re-tag refreshes provenance without re-hashing
    styles_mapping[src_a] = {"style": CINEMATIC}
    third = pool.corpus_hashes(pool_dir=tmp_path, attrs_mapping=attrs_mapping,
                               styles_mapping=styles_mapping, log=lambda m: None)
    assert third[src_a]["family"] == CINEMATIC and third[src_a]["phash"] == first[src_a]["phash"]
    # an empty mapping never erases it — the tests inject exactly that
    kept = pool.corpus_hashes(pool_dir=tmp_path, attrs_mapping={}, styles_mapping={},
                              log=lambda m: None)
    assert kept == third


def test_ranker_prepare_reuses_passed_mappings_without_reloading(monkeypatch):
    """B3: when the CLI hands prepare the attributes/styles mappings, the ranker
    threads them through baseline/_freq and never re-reads the yaml."""
    attrs_mapping, styles_mapping = portrait_corpus()
    loads = {"attrs": 0, "styles": 0}
    monkeypatch.setattr(pool.attrs, "load", lambda *a, **k: loads.__setitem__("attrs", loads["attrs"] + 1))
    monkeypatch.setattr(pool.styles, "load", lambda *a, **k: loads.__setitem__("styles", loads["styles"] + 1))
    pool.HistogramRanker().prepare(FAMILY, attrs_mapping, styles_mapping)
    assert loads == {"attrs": 0, "styles": 0}


def test_nearest_dup_takes_int_hashes_parsed_once():
    """B6: nearest_dup compares against pre-parsed int hashes (min over the
    mirror), so the corpus/pool hex is parsed once per search, not per candidate."""
    hashed = [(int("0" * 16, 16), "a"), (int("f" * 16, 16), "b")]
    assert pool.nearest_dup("0" * 16, "1" * 16, hashed, 6) == (0, "a")
    # the mirror is what is within cap: h ("0f"*8, 32 bits from both) is beyond
    # cap, but the mirror hm equals "b"
    assert pool.nearest_dup("0f" * 8, "f" * 16, hashed, 6) == (0, "b")
    assert pool.nearest_dup("5" * 16, "a" * 16, hashed, 6) is None
