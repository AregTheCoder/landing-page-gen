"""lp-inject on the fixture page: chosen media cropped into the slot, null
chosen -> placeholder, untouched slots kept, changed text written back."""

import json

from PIL import Image

from landing_page_gen.corpus import db, sectionize, skeleton
from landing_page_gen.inject import cli as inject
from test_corpus import hero_render, make_page


def build_run(tmp_path):
    con = db.connect(tmp_path / "c.db")
    d = make_page(tmp_path / "pages", "comic-book-generator", hero_render())
    sectionize.sectionize_page(d, con, log=lambda m: None)
    run = tmp_path / "runs" / "dry"
    skeleton.write_skeleton(con, "comic-book-generator", run / "skeleton.md")
    return run


def test_parse_page_md_reads_slots_and_texts(tmp_path):
    run = build_run(tmp_path)
    slots, texts = inject.parse_page_md((run / "skeleton.md").read_text())
    assert slots["S01-m1"]["kind"] == "image" and slots["S02-m1"]["kind"] == "video"
    assert texts["S01-t1"] == "Comic Book Generator"
    assert texts["S01-t3"] == "Start creating", "the -> href suffix is not part of the text"


def test_inject_fills_placeholders_keeps_and_rewrites_text(tmp_path):
    run = build_run(tmp_path)
    chosen = tmp_path / "hero.png"
    Image.new("RGB", (1600, 900), "red").save(chosen)          # wider than the 300x450 slot
    md = (run / "skeleton.md").read_text()
    md = md.replace("id: S01-m1\nkind: image\n", f"id: S01-m1\nkind: image\nchosen: {chosen}\n", 1)
    md = md.replace("id: S02-m1\nkind: video\n", "id: S02-m1\nkind: video\nchosen: null\n", 1)
    md = md.replace("- t1 h1: Comic Book Generator", "- t1 h1: Comic Maker")
    (run / "page.md").write_text(md)

    report = inject.inject(run, log=lambda m: None, localise_css_assets=False)
    assert report["filled"] == ["S01-m1"] and report["placeholders"] == ["S02-m1"]
    assert "S03-m1" in report["kept"] and report["texts_changed"] == 1 and report["missing"] == []
    html = (run / "dist" / "index.html").read_text()
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")
    hero = soup.select_one('[data-lp="S01-m1"]')
    assert hero["src"] == "media/gen/S01-m1.png" and hero["data-lp-chosen"] == str(chosen)
    assert Image.open(run / "dist" / "media" / "gen" / "S01-m1.png").size == (300, 450), "centre-cropped to the slot"
    ph = soup.select_one('[data-lp="S02-m1"]')
    assert ph.name == "img" and ph["src"] == "media/gen/S02-m1-placeholder.png"
    assert Image.open(run / "dist" / "media" / "gen" / "S02-m1-placeholder.png").size == (640, 360)
    assert soup.select_one('[data-lp="S03-m1"]')["src"].startswith("/landings-ssr/"), "kept slot untouched"
    assert soup.find("h1").get_text() == "Comic Maker"
    assert soup.select_one('[data-lp-t="S01-t2"]').get_text(" ", strip=True).startswith("Turn your story"), "unchanged text left alone"


def test_looks_like_html_detects_a_stale_chunk():
    # A stale, redeployed chunk serves the app-shell HTML with a 200 — must not
    # be saved as CSS (the live-5 formatting bug).
    assert inject.looks_like_html("<!DOCTYPE html><html>...")
    assert inject.looks_like_html("   <html lang=\"en\"><head>")
    assert not inject.looks_like_html(".a{color:red}")
    assert not inject.looks_like_html("@layer base;@layer utils{.flex{display:flex}}")


def test_absolutise_css_urls_keeps_the_page_self_contained():
    u = "https://picsart.com/landings-ssr/_next/static/chunks/abc.css"
    css = ('a{background:url(/f/x.png)} b{src:url("y.woff2")} '
           'c{background:url(data:image/png;base64,Z)} d{background:url(https://z/i.png)}')
    out = inject.absolutise_css_urls(css, u)
    assert 'url("https://picsart.com/f/x.png")' in out            # root-relative -> origin
    assert 'url("https://picsart.com/landings-ssr/_next/static/chunks/y.woff2")' in out  # relative -> chunk dir
    assert "url(data:image/png;base64,Z)" in out                  # data URI untouched
    assert "url(https://z/i.png)" in out                          # already absolute untouched


def test_cli_returns_nonzero_on_missing_stamp(tmp_path):
    run = build_run(tmp_path)
    md = (run / "skeleton.md").read_text().replace("id: S01-m1\n", "id: S01-m1\nchosen: null\n", 1)
    md += "\n```slot\nid: S99-m1\nkind: image\nchosen: null\n```\n"
    (run / "page.md").write_text(md)
    assert inject.main([str(run), "--no-localise-css"]) == 1
    assert json.loads((run / "slots.json").read_text())["page"] == "comic-book-generator"


def test_inject_resolves_run_relative_chosen(tmp_path, monkeypatch):
    run = build_run(tmp_path)
    steps = run / "sections" / "S01" / "steps"
    steps.mkdir(parents=True)
    Image.new("RGB", (600, 900), "green").save(steps / "S01-m1-3-1.png")
    md = (run / "skeleton.md").read_text()
    md = md.replace("id: S01-m1\nkind: image\n", "id: S01-m1\nkind: image\nchosen: sections/S01/steps/S01-m1-3-1.png\n", 1)
    (run / "page.md").write_text(md)
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)  # the path is run-relative, not cwd-relative
    report = inject.inject(run, log=lambda m: None, localise_css_assets=False)
    assert report["filled"] == ["S01-m1"]
    assert Image.open(run / "dist" / "media" / "gen" / "S01-m1.png").size == (300, 450)
    from bs4 import BeautifulSoup
    soup = BeautifulSoup((run / "dist" / "index.html").read_text(), "html.parser")
    assert soup.select_one('[data-lp="S01-m1"]')["data-lp-chosen"] == "sections/S01/steps/S01-m1-3-1.png"


def test_inject_assembles_page_md_from_result_frontmatter(tmp_path):
    """A7: with sections/*/result.md present, lp-inject writes page.md itself
    (chosen + workflow per slot) instead of the manager hand-writing it."""
    run = build_run(tmp_path)
    chosen = tmp_path / "hero.png"
    Image.new("RGB", (1600, 900), "red").save(chosen)
    (run / "sections" / "S01").mkdir(parents=True)
    (run / "sections" / "S01" / "result.md").write_text(
        f"---\nsection: S01\nslots:\n  S01-m1:\n    chosen: {chosen}\n    local: steps/x.png\n---\nprose\n")
    (run / "sections" / "S02").mkdir(parents=True)
    (run / "sections" / "S02" / "result.md").write_text(
        "---\nsection: S02\nslots:\n  S02-m1:\n    chosen: null\n---\nprose\n")
    assert not (run / "page.md").exists()

    report = inject.inject(run, log=lambda m: None, localise_css_assets=False)

    page = (run / "page.md").read_text()
    assert "chosen:" in page and "workflow: sections/S01/workflow.yaml" in page
    assert report["filled"] == ["S01-m1"] and report["placeholders"] == ["S02-m1"]
    assert "S03-m1" in report["kept"]
