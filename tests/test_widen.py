"""Reverse-image widening of a family's look-corpus, with the network stubbed."""
import yaml

from landing_page_gen.corpus import similar, widen

STYLES = {
    "https://cdn-basic-content-api.picsart.io/p/5d8ec016-aaaa-4000-8000-000000000001.png": {"style": "template-mockup"},
    "https://cdn-basic-content-api.picsart.io/p/21cdafd9-aaaa-4000-8000-000000000002.png": {"style": "template-mockup"},
    "https://cdn-basic-content-api.picsart.io/p/f746795b-aaaa-4000-8000-000000000003.png": {"style": "dark-composite"},
}


def lens_payload(url):
    n = url[-5]
    return {"visual_matches": [
        {"title": f"cup {n}", "link": f"https://www.pexels.com/photo/cup-{n}/", "source": "Pexels",
         "image": {"link": f"https://images.pexels.com/{n}/a.jpeg"}, "thumbnail": {"link": f"https://t/{n}a.jpg"}},
        {"title": "ours", "link": "https://picsart.com/poster-maker/", "source": "Picsart", "image": {"link": "https://cdn.picsart.com/x.png"}},
        {"title": f"cup {n} again", "link": f"https://shop.example/{n}", "source": "shop.example",
         "image": {"link": f"https://images.pexels.com/{n}/a.jpeg"}},
        {"title": f"mug {n}", "link": f"https://unsplash.com/photos/mug-{n}", "source": "Unsplash",
         "image": {"link": f"https://images.unsplash.com/{n}/b.jpeg"}},
    ]}


def test_family_assets_and_lens_parse():
    rows = widen.family_assets(STYLES, "template-mockup")
    assert [a for a, _ in rows] == ["21cdafd9", "5d8ec016"]
    ms = widen.lens_matches("https://x/1.png", "k", fetch=lambda url, data=None: lens_payload(url))
    assert ms[0]["page"].startswith("https://www.pexels.com") and ms[0]["image"].endswith("a.jpeg")


def test_widen_writes_yaml_drops_own_site_and_duplicates(tmp_path):
    calls = []

    def fetch(url, data=None):
        calls.append(url)
        return lens_payload(url.split("url=")[1].split("&")[0].replace("%3A", ":").replace("%2F", "/"))
    path, searched, added = widen.widen("template-mockup", STYLES, key="k", out_dir=tmp_path, fetch=fetch, log=lambda m: None)
    data = yaml.safe_load(path.read_text())
    assert searched == 2 and added == 4 and set(data["assets"]) == {"5d8ec016", "21cdafd9"}
    ms = data["assets"]["5d8ec016"]["visual"]["matches"]
    assert [m["source"] for m in ms] == ["Pexels", "Unsplash"]  # picsart.com dropped, duplicate image dropped
    # a second pass re-searches nothing
    widen.widen("template-mockup", STYLES, key="k", out_dir=tmp_path, fetch=fetch, log=lambda m: None)
    assert len(calls) == 2


def test_widen_needs_a_key_and_a_known_backend(tmp_path, monkeypatch):
    monkeypatch.delenv("SERPAPI_KEY", raising=False)
    try:
        widen.widen("template-mockup", STYLES, out_dir=tmp_path, fetch=lambda u, d=None: {})
        assert False, "should need a key"
    except ValueError as exc:
        assert "SERPAPI_KEY" in str(exc)
    try:
        widen.widen("template-mockup", STYLES, backend="bing", key="k", out_dir=tmp_path)
        assert False
    except ValueError as exc:
        assert "backend" in str(exc)


def test_vision_parse():
    payload = {"responses": [{"webDetection": {
        "visuallySimilarImages": [{"url": "https://a/1.jpg"}, {"url": "https://b/2.jpg"}],
        "fullMatchingImages": [{"url": "https://images.pexels.com/9/x.jpeg"}],
        "pagesWithMatchingImages": [{"url": "https://www.pexels.com/photo/x-9/", "pageTitle": "X"}]}}]}
    ms = widen.vision_matches("https://x/1.png", "k", fetch=lambda u, d=None: payload)
    assert [m["image"] for m in ms] == ["https://a/1.jpg", "https://b/2.jpg"]
    ex = widen.vision_matches("https://x/1.png", "k", exact=True, fetch=lambda u, d=None: payload)
    assert ex[0]["page"] == "https://www.pexels.com/photo/x-9/" and ex[0]["title"] == "X"


def test_pick_round_robins_and_excludes(tmp_path):
    fetch = lambda url, data=None: lens_payload(url.split("url=")[1].split("&")[0].replace("%3A", ":").replace("%2F", "/"))
    path, _, _ = widen.widen("template-mockup", STYLES, key="k", out_dir=tmp_path, fetch=fetch, log=lambda m: None)
    picks = widen.pick("template-mockup", 3, path=path)
    assert len(picks) == 3 and len({p["from_asset"] for p in picks}) == 2  # one from each asset first
    # an excluded id (the page's own picture on another site) never comes back
    for p in widen.pick("template-mockup", 4, exclude_asset=["cup-1"], path=path):
        assert "cup-1" not in p["page"]


def test_write_examples_marks_origin(tmp_path):
    from PIL import Image

    def fake_download(url, dest, timeout=60):
        Image.new("RGB", (4, 4), "blue").save(dest, format="PNG")
        return dest
    ms = [{"image": "https://images.pexels.com/1/a.jpeg", "page": "https://www.pexels.com/photo/cup-1/",
           "source": "Pexels", "title": "cup", "from_asset": "5d8ec016"}]
    written = widen.write_examples(ms, tmp_path / "examples", fake_download, similar.to_png, log=lambda m: None, start=3)
    assert [p.name for p in written] == ["w3-widened.md"]
    body = written[0].read_text()
    assert "origin: widened" in body and "from_asset: 5d8ec016" in body and "never" in body
    assert (tmp_path / "examples" / "w3-widened.png").exists()
