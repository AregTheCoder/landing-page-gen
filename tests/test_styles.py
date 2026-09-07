"""Style families: the doc and the code agree (headings, block keys, slot
classes, templates, vocabulary), tags survive a re-index, the skeleton and
`similar` see them, and `lp-corpus styles` fills them."""

import re
import sqlite3

from PIL import Image

from landing_page_gen.compose.families import FAMILIES
from landing_page_gen.corpus import attrs, cli, db, media, sectionize, similar, skeleton, styles
from test_corpus import HERO1, fake_download_factory, hero_render, make_page

KEYS = ("**Use:**", "**Slots:**", "**Signature:**", "**Ground:**", "**Grid:**", "**Template:**", "**Chrome (lp-compose):**",
        "**Panels (worker):**", "**Palette:**", "**Text:**", "**Never:**", "**Examples:**")
ASSET_ID = re.compile(r"\b[0-9a-f]{8}\b")


def build(tmp_path, slugs):
    con = db.connect(tmp_path / "c.db")
    for slug in slugs:
        sectionize.sectionize_page(make_page(tmp_path / "pages", slug, hero_render()), con, log=lambda m: None)
    return con


def blocks(doc):
    """{family: block text} for the `## <family>` sections."""
    parts = doc.split("\n## ")[1:]
    return {p.split("\n", 1)[0].strip(): p for p in parts}


def line_of(block, key):
    return next(line for line in block.splitlines() if line.startswith(key))


def test_doc_headings_keys_and_key_order():
    doc = styles.DOC.read_text()
    heads = tuple(line[3:].strip() for line in doc.splitlines() if line.startswith("## "))
    assert heads[:2] == ("Vocabulary and constants", "Slot classes") and heads[2:] == db.STYLES
    for fam in db.STYLES:
        block = blocks(doc)[fam]
        positions = [block.index(key) for key in KEYS]
        assert positions == sorted(positions), (fam, "keys out of order")
    guide_lines = styles.guide().splitlines()
    assert "## full-bleed" in guide_lines and any(line.startswith("**Signature:**") for line in guide_lines)
    assert not any(line.startswith(("**Panels", "**Grid", "**Never")) for line in guide_lines), "the classifier sees Use/Signature/Ground/Chrome only"


def test_template_lines_match_compose_templates():
    doc = styles.DOC.read_text()
    templated = set()
    for fam in db.STYLES:
        value = line_of(blocks(doc)[fam], "**Template:**")[len("**Template:**"):].strip()
        m = re.match(r"lp-compose: ([a-z-]+)", value)
        if m:
            templated.add(m.group(1))
        else:
            assert value.startswith(("none; brief as ", "none (", "kept-from-source (")), (fam, value)
            for fallback in re.findall(r"brief as ([a-z-]+)", value):
                assert fallback in db.STYLES, (fam, fallback)
    assert templated == set(FAMILIES), "every compose template is documented as such, and only those"


def test_slot_class_table_pins_db_constants_and_block_slots():
    doc = styles.DOC.read_text()
    table = doc.split("\n## Slot classes\n")[1].split("\n## ")[0]
    rows = [line for line in table.splitlines() if line.startswith("| ") and not line.startswith("| class") ]
    classes, used = {}, set()
    for row in rows:
        cells = [c.strip() for c in row.strip("|").split("|")]
        cls, typ, role, aspect, _size, assets, _fams, families, _note = cells
        assert typ in db.SECTION_TYPES and role in db.GENERATED_ROLES and aspect in sectionize.ASPECT_CLASSES, row
        assert int(assets) > 0
        for token in re.findall(r"\b([a-z]+(?:-[a-z]+)+)(?:/[a-z]+)?", families):
            if token in db.STYLES:
                used.add(token)
        classes[cls] = families
    assert set(db.STYLES) <= used, f"families never allowed by any slot class: {set(db.STYLES) - used}"
    for fam in db.STYLES:
        slots_line = line_of(blocks(doc)[fam], "**Slots:**")
        for cls in re.findall(r"\b([a-z]+-\d+:\d+(?:-video)?)", slots_line):
            assert cls in classes, (fam, cls, "not a slot-class row")
            assert fam in classes[cls], (fam, cls, "row does not list this family")


def test_examples_name_distinct_assets_and_grounds_are_named():
    doc = styles.DOC.read_text()
    for fam in db.STYLES:
        ids = ASSET_ID.findall(line_of(blocks(doc)[fam], "**Examples:**"))
        assert len(ids) >= 2 and len(ids) == len(set(ids)), (fam, ids)
        ground = line_of(blocks(doc)[fam], "**Ground:**")
        for variant in re.findall(r"\| ([a-z]+):", ground):
            assert variant in attrs.ENUMS["ground"] or variant in ("none", "transparent") or variant in {
                "light", "checker", "colour"}, (fam, variant)


def test_vocabulary_bullets_equal_attribute_enums():
    doc = styles.DOC.read_text()
    vocab = doc.split("\n## Vocabulary and constants\n")[1].split("\n## ")[0]
    found = {}
    for line in vocab.splitlines():
        m = re.match(r"- \*\*([a-z_]+)\*\*: (.+)$", line)
        if m and " | " in m.group(2):
            found[m.group(1)] = tuple(v.strip() for v in m.group(2).split("|"))
    expected = {k: v for k, v in attrs.ENUMS.items() if k != "family_hint"}
    assert found == expected


def test_old_db_gains_style_and_attrs_columns(tmp_path):
    path = tmp_path / "old.db"
    con = sqlite3.connect(path)
    con.executescript(db.SCHEMA.replace("  style TEXT,\n", "").replace("  attrs TEXT,\n", ""))
    con.close()
    con = db.connect(path)
    assert {"style", "attrs"} <= {r["name"] for r in con.execute("PRAGMA table_info(media)")}


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
    assert '> annotation: TODO what this image should show (source alt: "comic panel of a hero")\n> style: full-bleed\n> text: TODO' in text
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
