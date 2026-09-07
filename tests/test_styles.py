"""Style families: the doc and the code agree, tags survive a re-index,
the skeleton and `similar` see them, and `lp-corpus styles` fills them."""

import sqlite3

from PIL import Image

from landing_page_gen.compose.families import FAMILIES
from landing_page_gen.corpus import cli, db, media, sectionize, similar, skeleton, styles
from test_corpus import HERO1, fake_download_factory, hero_render, make_page

KEYS = ("**Use:**", "**Ground:**", "**Grid 1:1", "**Grid 16:9", "**Chrome", "**Panels", "**Palette:**", "**Never:**", "**Examples:**")


def build(tmp_path, slugs):
    con = db.connect(tmp_path / "c.db")
    for slug in slugs:
        sectionize.sectionize_page(make_page(tmp_path / "pages", slug, hero_render()), con, log=lambda m: None)
    return con


def test_doc_blocks_match_code():
    doc = styles.DOC.read_text()
    heads = tuple(line[3:].strip() for line in doc.splitlines() if line.startswith("## "))
    assert heads[0] == "Vocabulary and constants" and heads[1:] == db.STYLES
    for block in doc.split("\n## ")[2:]:
        for key in KEYS:
            assert key in block, (block.splitlines()[0], key)
    assert set(FAMILIES) <= set(db.STYLES), "every compose template is a documented family"
    assert "## full-bleed" in styles.guide() and "**Panels" not in styles.guide()


def test_old_db_gains_style_column(tmp_path):
    path = tmp_path / "old.db"
    con = sqlite3.connect(path)
    con.executescript(db.SCHEMA.replace("  style TEXT,\n", ""))
    con.close()
    con = db.connect(path)
    assert "style" in {r["name"] for r in con.execute("PRAGMA table_info(media)")}


def test_apply_survives_reindex_and_skeleton_shows_style(tmp_path):
    con = build(tmp_path, ["comic-book-generator"])
    mapping = {HERO1: {"style": "full-bleed", "confidence": 0.95}}
    assert styles.apply(con, mapping) == 1
    sectionize.sectionize_page(tmp_path / "pages" / "comic-book-generator", con, log=lambda m: None)
    assert con.execute("SELECT style FROM media WHERE src = ?", (HERO1,)).fetchone()[0] is None, "re-index drops tags"
    styles.apply(con, mapping)
    assert con.execute("SELECT style FROM media WHERE src = ?", (HERO1,)).fetchone()[0] == "full-bleed"
    out = tmp_path / "r" / "skeleton.md"
    skeleton.write_skeleton(con, "comic-book-generator", out)
    text = out.read_text()
    assert text.count("> style:") == 5, "one style line per generated-role slot"
    assert '> annotation: TODO what this image should show (source alt: "comic panel of a hero")\n> style: full-bleed\n' in text
    assert "> style: TODO one of dark-composite | before-after | crop-frame" in text


def test_similar_prefers_style_then_falls_back(tmp_path, monkeypatch):
    con = build(tmp_path, ["comic-book-generator", "manga-maker", "storyboard-generator"])
    con.execute("""UPDATE media SET style = 'full-bleed' WHERE src = ? AND section_id IN
                   (SELECT s.id FROM sections s JOIN pages p ON p.id = s.page_id WHERE p.slug = 'storyboard-generator')""", (HERO1,))
    con.commit()
    q = "Comic Book Generator turn your story into a comic"
    rows = similar.find_similar(con, "hero", q, k=2, exclude="comic-book-generator", style="full-bleed")
    assert [r["slug"] for r in rows] == ["storyboard-generator", "manga-maker"], "tagged page first, untagged fills up"
    rows = similar.find_similar(con, "hero", q, k=2, exclude="comic-book-generator", style="prompt-card")
    assert {r["slug"] for r in rows} == {"manga-maker", "storyboard-generator"}, "no tagged hits: type-only fallback"
    rows = similar.find_similar(con, "hero", "", k=1, exclude="comic-book-generator", style="full-bleed")
    assert rows[0]["slug"] == "storyboard-generator", "empty query still prefers the tagged page"

    def fake_download(url, dest, timeout=60):
        Image.new("RGB", (4, 4), "red").save(dest, format="PNG")
        return dest
    monkeypatch.setattr(similar, "download", fake_download)
    body = similar.write_examples(con, rows, tmp_path / "ex", log=lambda m: None)[0].read_text()
    assert "style: full-bleed, local: 1-storyboard-generator-S01-m1.png" in body and "style: untagged" in body


def test_styles_cli_classifies_by_alt_then_model_and_applies(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(media, "download", fake_download_factory([]))
    pages = tmp_path / "pages"
    media.localise_page(make_page(pages, "comic-book-generator", hero_render()), log=lambda m: None)
    dbp = str(tmp_path / "c.db")
    assert cli.main(["--db", dbp, "--pages-dir", str(pages), "sectionize", "--all"]) == 0
    con = db.connect(tmp_path / "c.db")
    con.execute("UPDATE media SET alt = 'before change' WHERE src = ?", (HERO1.replace("hero1", "hero2"),))
    con.commit()
    calls = []

    def fake_classify(client, path, system, model):
        calls.append((path, model))
        return "dark-composite", 0.8
    monkeypatch.setattr(styles, "classify", fake_classify)
    monkeypatch.setattr(styles, "guide", lambda: "guide")
    monkeypatch.setattr("anthropic.Anthropic", lambda: object())
    yml = tmp_path / "styles.yaml"
    assert cli.main(["--db", dbp, "styles", "--styles", str(yml)]) == 0
    out = capsys.readouterr().out
    assert "1 tagged by alt, 1 sent to claude-opus-5, 2 media rows tagged" in out and "dark-composite: 1" in out
    assert len(calls) == 1 and calls[0][0].endswith(".avif"), "only the hero without a 'before' alt goes to the model"
    tags = styles.load(yml)
    assert tags[HERO1]["style"] == "dark-composite" and tags[HERO1]["page"] == "comic-book-generator"
    assert tags[HERO1.replace("hero1", "hero2")] == {"style": "before-after", "confidence": 1.0, "page": "comic-book-generator", "slot": "S01-m2"}
    assert {r[0] for r in con.execute("SELECT style FROM media WHERE style IS NOT NULL")} == {"dark-composite", "before-after"}
    # a second run has nothing left to classify; --apply-only re-mirrors after a re-index
    calls.clear()
    assert cli.main(["--db", dbp, "styles", "--styles", str(yml)]) == 0 and calls == []
    assert cli.main(["--db", dbp, "--pages-dir", str(pages), "sectionize", "--all"]) == 0
    assert "0 style-tagged" in capsys.readouterr().out, "sectionize re-applies the default yaml, which is absent here"
    assert cli.main(["--db", dbp, "styles", "--styles", str(yml), "--apply-only"]) == 0
    assert "2 media rows tagged" in capsys.readouterr().out
