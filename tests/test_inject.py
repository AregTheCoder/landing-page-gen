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

    report = inject.inject(run, log=lambda m: None)
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


def test_cli_returns_nonzero_on_missing_stamp(tmp_path):
    run = build_run(tmp_path)
    md = (run / "skeleton.md").read_text().replace("id: S01-m1\n", "id: S01-m1\nchosen: null\n", 1)
    md += "\n```slot\nid: S99-m1\nkind: image\nchosen: null\n```\n"
    (run / "page.md").write_text(md)
    assert inject.main([str(run)]) == 1
    assert json.loads((run / "slots.json").read_text())["page"] == "comic-book-generator"
