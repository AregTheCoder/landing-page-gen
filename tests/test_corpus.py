"""Corpus pipeline on a saved streamed-SSR fixture: reassemble -> sectionize
-> skeleton -> similar. No network."""

import json

import pytest

from landing_page_gen.corpus import cli, db, sectionize, similar, skeleton, snapshot

FIXTURE = __import__("pathlib").Path(__file__).parent / "fixtures" / "streamed.html"
HERO1 = "https://cdn-cms-uploads.picsart.com/cms-uploads/hero1.avif"


def make_page(pages_dir, slug, render=None):
    soup = snapshot.snapshot_html(snapshot.reassemble(FIXTURE.read_text()))
    d = pages_dir / slug
    d.mkdir(parents=True)
    (d / "page.html").write_text(str(soup))
    (d / "meta.json").write_text(json.dumps({
        "slug": slug, "url": f"https://picsart.com/{slug}/", "title": f"{slug} | Picsart",
        "family": "tool", "fetched_at": "2026-09-04T00:00:00+00:00"}))
    if render is not None:
        (d / "render.json").write_text(json.dumps(render))
    return d


def hero_render():
    proxy = "/landings-ssr/_next/image/?url=https%3A%2F%2Fcdn-cms-uploads.picsart.com%2Fcms-uploads%2F{}.avif&w=3840&q=75"
    return [
        {"tag": "img", "src_attr": proxy.format("hero1"), "x": 0, "y": 0, "w": 300, "h": 450, "nat_w": 600, "nat_h": 900, "duration": None},
        {"tag": "img", "src_attr": proxy.format("hero2"), "x": 0, "y": 0, "w": 300, "h": 450, "nat_w": 600, "nat_h": 900, "duration": None},
        {"tag": "img", "src_attr": proxy.format("ghost"), "x": 0, "y": 0, "w": 0, "h": 0, "nat_w": None, "nat_h": None, "duration": None},
        {"tag": "video", "src_attr": "https://cdn-cms-uploads.picsart.com/cms-uploads/style.webm", "x": 0, "y": 0, "w": 640, "h": 360, "nat_w": 1280, "nat_h": 720, "duration": 8.4},
    ]


def test_reassemble_moves_segments_into_place_and_snapshot_is_standalone():
    soup = snapshot.reassemble(FIXTURE.read_text())
    main = soup.find("main")
    assert main.find("h1").get_text() == "Comic Book Generator"
    assert soup.find("template") is None
    assert soup.find("div", hidden=True) is None
    assert soup.find(class_="spinner") is None, "Suspense fallback must be replaced by its segment"
    snapshot.snapshot_html(soup)
    assert soup.find("script") is None
    assert soup.head.find("base")["href"] == "https://picsart.com/"
    assert soup.head.find("link", rel="stylesheet") is not None


def test_cdn_url_unwraps_next_image_proxy():
    assert sectionize.cdn_url("/landings-ssr/_next/image/?url=https%3A%2F%2Fcdn.x%2Fa.avif&w=3840&q=75") == "https://cdn.x/a.avif"
    assert sectionize.cdn_url("/img/a.png") == "https://picsart.com/img/a.png"
    assert sectionize.cdn_url("https://cdn.x/v.webm") == "https://cdn.x/v.webm"
    assert sectionize.aspect_of(1440, 810) == "16:9"
    assert sectionize.aspect_of(300, 450) == "2:3"
    assert sectionize.aspect_of(651, 366) == "16:9"
    assert [sectionize.aspect_class(*wh) for wh in ((879, 418), (202, 67), (180, 113), (318, 199), (13, 14), (62, 87), (196, 348))] \
        == ["2:1", "3:1", "16:10", "16:10", "1:1", "3:4", "9:16"]
    assert [sectionize.size_class(*wh) for wh in ((196, 348), (342, 282), (480, 480), (879, 418), (1440, 810), (0, 0))] \
        == ["tile", "card", "card", "panel", "wide", None]


def test_sectionize_types_roles_and_stamps(tmp_path):
    con = db.connect(tmp_path / "c.db")
    d = make_page(tmp_path / "pages", "comic-book-generator", hero_render())
    sections = sectionize.sectionize_page(d, con, log=lambda m: None)
    types = [(s["sid"], s["type"]) for s in sections]
    assert types == [("S01", "hero"), ("S02", "feature-callout"), ("S03", "tutorial-grid"), ("S04", "faq"),
                     ("S05", "testimonial"), ("S06", "link-grid"), ("S07", "footer")]
    hero = sections[0]
    assert hero["headline"] == "Comic Book Generator"
    assert [m["src"] for m in hero["media"]] == [HERO1, HERO1.replace("hero1", "hero2")], "0x0 image is dropped"
    assert hero["media"][0]["role"] == "creative"
    assert (hero["media"][0]["width"], hero["media"][0]["height"], hero["media"][0]["aspect"]) == (300, 450, "2:3")
    assert hero["media"][0]["nat_width"] == 600
    texts = [t["text"] for t in hero["texts"]]
    assert texts[:3] == ["Comic Book Generator", "Turn your story into a comic in minutes with any AI model .", "Start creating"]
    assert "mobile only" not in texts and "never visible" not in texts
    video = sections[1]["media"][0]
    assert (video["kind"], video["role"], video["duration"], video["aspect"]) == ("video", "creative", 8.4, "16:9")
    assert {m["role"] for m in sections[2]["media"]} == {"thumbnail"}
    assert sections[4]["media"][0]["role"] == "decorative"
    assert sections[6]["media"][0]["role"] == "icon"
    html = (d / "page.html").read_text()
    assert 'data-lp-section="S01"' in html and 'data-lp="S01-m1"' in html and 'data-lp-t="S01-t1"' in html
    assert (d / "sections.md").exists()
    # DB and FTS
    row = con.execute("SELECT count(*) FROM media WHERE role IN ('creative','thumbnail')").fetchone()
    assert row[0] == 5
    hit = con.execute("SELECT s.sid FROM sections_fts f JOIN sections s ON s.id = f.rowid WHERE sections_fts MATCH 'manga'").fetchone()
    assert hit["sid"] == "S02"
    assert f"]({HERO1})" in hero["md"], "without a local copy the media line links the CDN URL"
    # re-indexing replaces rather than duplicates
    sectionize.sectionize_page(d, con, log=lambda m: None)
    assert con.execute("SELECT count(*) FROM sections").fetchone()[0] == 7
    assert con.execute("SELECT count(*) FROM sections_fts WHERE sections_fts MATCH 'manga'").fetchone()[0] == 1


def test_sectionize_without_render_uses_attributes(tmp_path):
    con = db.connect(tmp_path / "c.db")
    d = make_page(tmp_path / "pages", "comic-book-generator")
    sections = sectionize.sectionize_page(d, con, log=lambda m: None)
    assert len(sections[0]["media"]) == 3, "without geometry nothing is known to be hidden"
    card = sections[2]["media"][0]
    assert (card["width"], card["height"], card["aspect"]) == (500, 300, "5:3")


def test_skeleton_and_slots_json(tmp_path):
    con = db.connect(tmp_path / "c.db")
    d = make_page(tmp_path / "pages", "comic-book-generator", hero_render())
    sectionize.sectionize_page(d, con, log=lambda m: None)
    out = tmp_path / "runs" / "r1" / "skeleton.md"
    path, n_sections, n_gen, n_all = skeleton.write_skeleton(con, "comic-book-generator", out)
    text = out.read_text()
    assert n_sections == 7 and n_gen == 5 and n_all == 7
    assert text.startswith("---\npage: comic-book-generator\n")
    assert "budget:\n  run_credits: 300" in text
    assert "\n## S01 hero\n" in text and "\n## S03 tutorial-grid\n" in text
    assert "- t1 h1: Comic Book Generator" in text
    # aspect is quoted on purpose: bare 9:16 is a sexagesimal integer to YAML 1.1 parsers
    assert "```slot\nid: S01-m1\nkind: image\nrole: creative\nsize: 300x450\nsize_class: tile\naspect: '2:3'\nnatural: 600x900\n" in text
    assert text.count("> annotation:") == 5, "one annotation line per generated-role slot"
    assert text.count("> text: TODO") == 5, "one text line per generated-role slot"
    assert text.count("> attrs: none (asset not measured") == 5, "an unmeasured slot says so instead of hiding it"
    slots = json.loads((out.parent / "slots.json").read_text())
    assert slots["slots"]["S01-m1"]["selector"] == '[data-lp="S01-m1"]'
    assert slots["slots"]["S01-m1"]["style"] is None and slots["slots"]["S01-m1"]["attrs"] is None, "untagged slots say so"
    assert slots["texts"]["S01-t1"] == {"tag": "h1", "selector": '[data-lp-t="S01-t1"]'}
    assert slots["sections"]["S02"] == {"type": "feature-callout", "selector": '[data-lp-section="S02"]'}


def test_media_role_size_beats_alt_words():
    from bs4 import BeautifulSoup
    root = BeautifulSoup("<section><h2>How Recraft works</h2></section>", "html.parser").section

    def role(alt, w=480, kind="image", typ="feature-callout"):
        return sectionize.media_role(None, kind, alt, w, w, typ, root)
    assert role("How Recraft V4 works in Picsart") == "creative", "a 480 px image titled how-it-works is the callout's creative, not a screenshot"
    assert role("", kind="video") == "ui-screenshot", "a video under a how-it-works headline is a product demo"
    assert role("AI logo and brand kit") == "creative", "a card-sized image about logos is a creative"
    assert role("First block decoration", w=194, typ="testimonial") == "decorative", "a small decoration outside a creative section stays decorative"
    assert role("Picsart editor interface") == "ui-screenshot", "interface words on an image still mean a screenshot"


def test_similar_returns_other_pages_heroes_with_media(tmp_path, monkeypatch):
    con = db.connect(tmp_path / "c.db")
    for slug in ("comic-book-generator", "manga-maker", "storyboard-generator"):
        sectionize.sectionize_page(make_page(tmp_path / "pages", slug, hero_render()), con, log=lambda m: None)
    rows = similar.find_similar(con, "hero", "Comic Book Generator turn your story into a comic", k=3, exclude="comic-book-generator")
    assert [r["type"] for r in rows] == ["hero", "hero"]
    assert {r["slug"] for r in rows} == {"manga-maker", "storyboard-generator"}
    assert similar.find_similar(con, "pricing", "Pro Ultra", k=3) == []
    # excerpts: media is downloaded and converted; stub the network
    from PIL import Image

    def fake_download(url, dest, timeout=60):
        Image.new("RGB", (4, 4), "red").save(dest, format="PNG")
        return dest
    monkeypatch.setattr(similar, "download", fake_download)
    written = similar.write_examples(con, rows, tmp_path / "examples", log=lambda m: None)
    assert [p.name for p in written] == ["1-manga-maker-S01.md", "2-storyboard-generator-S01.md"]
    body = written[0].read_text()
    assert "type: hero" in body and "## S01 hero" in body
    assert (tmp_path / "examples" / "1-manga-maker-S01-m1.png").exists()
    assert "local: 1-manga-maker-S01-m1.png" in body and "media_total: 2" in body


def test_cli_sectionize_and_skeleton(tmp_path, capsys):
    pages = tmp_path / "pages"
    make_page(pages, "comic-book-generator", hero_render())
    dbp = str(tmp_path / "c.db")
    assert cli.main(["--db", dbp, "--pages-dir", str(pages), "sectionize", "--all"]) == 0
    assert "corpus: 1 pages, 7 sections, 7 media" in capsys.readouterr().out
    out = tmp_path / "runs" / "x" / "skeleton.md"
    assert cli.main(["--db", dbp, "skeleton", "comic-book-generator", "--out", str(out)]) == 0
    assert out.exists() and (out.parent / "slots.json").exists()
    with pytest.raises(SystemExit):
        cli.main(["--db", dbp, "skeleton", "nope", "--out", str(out)])


def test_type_from_component_labels():
    assert sectionize.type_from_labels(["container", "15_53802_use-cases"]) == "use-case-grid"
    assert sectionize.type_from_labels(["banner-block", "-background-remover-_banner-block"]) == "feature-callout"
    assert sectionize.type_from_labels(["promotional-component-vibes"]) == "gallery"
    assert sectionize.type_from_labels(["howto-section", "7_how-to_howto"]) == "how-it-works"
    assert sectionize.type_from_labels(["container"]) is None


def test_slug_for():
    assert snapshot.slug_for("https://picsart.com/ai-image-generator/") == "ai-image-generator"
    assert snapshot.slug_for("/ai-models/flux-3/") == "ai-models--flux-3"
    assert snapshot.slug_for("https://picsart.com/") == "home"


# ---------- local media ----------

from landing_page_gen.corpus import media  # noqa: E402

PROXY_HERO1 = "/landings-ssr/_next/image/?url=https%3A%2F%2Fcdn-cms-uploads.picsart.com%2Fcms-uploads%2Fhero1.avif&w=3840&q=75"


def fake_download_factory(calls):
    from PIL import Image

    def fake_download(url, dest, timeout=60):
        calls.append(url)
        if "ghost" in url:
            raise OSError("404")
        Image.new("RGB", (4, 4), "blue").save(dest, format="PNG")
        return dest
    return fake_download


def test_local_name_is_readable_unique_and_stable():
    a = media.local_name("https://cdn.x/cms-uploads/84bdf497-68e2.avif")
    assert a.startswith("84bdf497-68e2-") and a.endswith(".avif")
    assert media.local_name("https://cdn.x/cms-uploads/84bdf497-68e2.avif") == a
    assert media.local_name("https://cdn.x/a.png?type=webp&r=400") != media.local_name("https://cdn.x/a.png")
    assert media.local_name("https://cdn.x/noext").endswith("-" + media.local_name("https://cdn.x/noext")[-12:-4] + ".bin")


def test_media_localises_page_and_is_idempotent(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(media, "download", fake_download_factory(calls))
    d = make_page(tmp_path / "pages", "comic-book-generator")
    counts = media.localise_page(d, log=lambda m: None)
    assert counts == {"ok": 7, "failed": 1}
    assert len(list((d / "media").iterdir())) == 7
    assert json.loads((d / "meta.json").read_text())["media"] == counts
    from bs4 import BeautifulSoup
    soup = BeautifulSoup((d / "page.html").read_text(), "html.parser")
    assert soup.find("base") is None
    hero1 = soup.find("img", alt="comic panel of a hero")
    assert hero1["src"].startswith("media/hero1-") and hero1["src"].endswith(".avif")
    assert hero1["data-lp-src"] == PROXY_HERO1
    assert not hero1.has_attr("srcset") and not hero1.has_attr("sizes")
    assert soup.find("picture").find("source") is None
    ghost = soup.find("img", alt="never shown")
    assert ghost["src"] == "https://cdn-cms-uploads.picsart.com/cms-uploads/ghost.avif" and ghost["data-lp-src"]
    assert soup.find("video")["src"].startswith("media/style-") and soup.find("video")["data-lp-src"].endswith("style.webm")
    assert soup.find("a", string="any AI model")["href"] == "https://picsart.com/ai-models/"
    assert soup.find("link", rel="stylesheet")["href"].startswith("https://")
    html_before = (d / "page.html").read_text()
    calls.clear()
    assert media.localise_page(d, log=lambda m: None) == {"ok": 7, "failed": 1}
    assert calls == ["https://cdn-cms-uploads.picsart.com/cms-uploads/ghost.avif"], "only the failed asset is retried"
    assert (d / "page.html").read_text() == html_before


def test_sectionize_after_media_keeps_src_geometry_and_fills_local_path(tmp_path, monkeypatch):
    monkeypatch.setattr(media, "download", fake_download_factory([]))
    con = db.connect(tmp_path / "c.db")
    d = make_page(tmp_path / "pages", "comic-book-generator", hero_render())
    media.localise_page(d, log=lambda m: None)
    sections = sectionize.sectionize_page(d, con, log=lambda m: None)
    assert [s["type"] for s in sections][:4] == ["hero", "feature-callout", "tutorial-grid", "faq"]
    hero = sections[0]
    assert hero["media"][0]["src"] == HERO1, "DB keeps the CDN URL"
    assert hero["media"][0]["width"] == 300, "geometry still matched through data-lp-src"
    assert hero["media"][0]["local"].startswith("media/hero1-")
    rows = con.execute("SELECT slot_id, local_path FROM media ORDER BY id").fetchall()
    assert rows[0]["local_path"] == str(d / hero["media"][0]["local"])
    assert all(r["local_path"] for r in rows), "the 0x0 ghost was dropped, everything else is local"
    html = (d / "page.html").read_text()
    assert 'data-lp-src="' in html and 'data-lp="S01-m1"' in html, "re-sectionizing keeps the source attribute"
    md = (d / "sections.md").read_text()
    assert f'](media/hero1-' in md and f'.avif "{HERO1}")' in md, "sections.md links the local file, CDN URL as title"


def test_similar_reuses_local_media(tmp_path, monkeypatch):
    monkeypatch.setattr(media, "download", fake_download_factory([]))
    con = db.connect(tmp_path / "c.db")
    for slug in ("comic-book-generator", "manga-maker"):
        d = make_page(tmp_path / "pages", slug, hero_render())
        media.localise_page(d, log=lambda m: None)
        sectionize.sectionize_page(d, con, log=lambda m: None)

    def no_network(url, dest, timeout=60):
        raise AssertionError(f"unexpected download of {url}")
    monkeypatch.setattr(similar, "download", no_network)
    rows = similar.find_similar(con, "hero", "comic", k=1, exclude="comic-book-generator")
    written = similar.write_examples(con, rows, tmp_path / "ex", log=lambda m: None)
    assert (tmp_path / "ex" / "1-manga-maker-S01-m1.png").exists()
    assert "local: 1-manga-maker-S01-m1.png" in written[0].read_text()


def test_fetch_localises_by_default(tmp_path, monkeypatch):
    monkeypatch.setattr(snapshot, "fetch_html", lambda url, timeout=30: FIXTURE.read_text())
    monkeypatch.setattr(media, "download", fake_download_factory([]))
    d = snapshot.save_page("/comic-book-generator/", tmp_path / "pages", renderer=None, log=lambda m: None)
    assert json.loads((d / "meta.json").read_text())["media"] == {"ok": 7, "failed": 1}
    assert "<base" not in (d / "page.html").read_text() and (d / "media").is_dir()
    d2 = snapshot.save_page("/manga-maker/", tmp_path / "pages", renderer=None, log=lambda m: None, localise=False)
    assert "<base" in (d2 / "page.html").read_text() and not (d2 / "media").exists()


def test_fetch_records_app_shell_without_snapshot(tmp_path, monkeypatch):
    shell = "<html><head><title>Picsart</title></head><body><div id='root'></div><script>x</script></body></html>"
    monkeypatch.setattr(snapshot, "fetch_html", lambda url, timeout=30: shell)
    d = snapshot.save_page("/ai-enhance/", tmp_path / "pages", renderer=None, log=lambda m: None)
    meta = json.loads((d / "meta.json").read_text())
    assert meta["shell"] is True and meta["title"] == "Picsart"
    assert not (d / "page.html").exists() and not (d / "media").exists()
    assert not cli.is_snapshot(d)


def test_cli_media_all(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(media, "download", fake_download_factory([]))
    pages = tmp_path / "pages"
    make_page(pages, "comic-book-generator")
    assert cli.main(["--pages-dir", str(pages), "media", "--all"]) == 0
    assert "media: 7 files downloaded or present, 1 failed" in capsys.readouterr().out
    slots = tmp_path / "s" / "skeleton.md"
    dbp = str(tmp_path / "c.db")
    assert cli.main(["--db", dbp, "--pages-dir", str(pages), "sectionize", "--all"]) == 0
    assert cli.main(["--db", dbp, "skeleton", "comic-book-generator", "--out", str(slots)]) == 0
    assert json.loads((slots.parent / "slots.json").read_text())["slots"]["S01-m1"]["local"].endswith(".avif")
    skel = slots.read_text()
    assert "\nlocal: " in skel and "/media/hero1-" in skel, "slot blocks name the local file"


def test_sectionize_prefers_displayed_copy_over_zero_size_duplicate(tmp_path):
    """Some pages render the same img twice, the first copy at 0x0 (product-ad-maker).
    The first DOM occurrence is kept and takes the displayed copy's geometry."""
    con = db.connect(tmp_path / "c.db")
    render = hero_render()
    ghost = dict(render[0], w=0, h=0, y=6854)
    d = make_page(tmp_path / "pages", "comic-book-generator", [ghost] + render)
    hero = sectionize.sectionize_page(d, con, log=lambda m: None)[0]
    assert [m["src"] for m in hero["media"]] == [HERO1, HERO1.replace("hero1", "hero2")]
    assert (hero["media"][0]["width"], hero["media"][0]["height"]) == (300, 450)
