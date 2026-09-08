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


def test_styles_cli_derives_from_attrs_and_applies(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(media, "download", fake_download_factory([]))
    pages = tmp_path / "pages"
    media.localise_page(make_page(pages, "comic-book-generator", hero_render()), log=lambda m: None)
    dbp = str(tmp_path / "c.db")
    assert cli.main(["--db", dbp, "--pages-dir", str(pages), "sectionize", "--all"]) == 0
    con = db.connect(tmp_path / "c.db")
    hero2 = HERO1.replace("hero1", "hero2")
    attrs_yaml, styles_yaml = tmp_path / "attributes.yaml", tmp_path / "styles.yaml"
    base = {"ground": "light-grey", "layout": "column-main", "panel_count": 1, "chrome": ["tile", "chip"],
            "text_in_image": "labels-only", "ui_mockup": "none", "subject": "product", "finish": "photo",
            "before_after": False, "family_hint": "dark-composite", "confidence": 0.8, "source": "sheet",
            "page": "comic-book-generator", "slot": "S01-m1"}
    styles.save({HERO1: base, hero2: dict(base, before_after=True, slot="S01-m2")}, attrs_yaml)

    assert cli.main(["--db", dbp, "styles", "--styles", str(styles_yaml)]) == 2, "one of the two modes is required"
    assert cli.main(["--db", dbp, "styles", "--styles", str(styles_yaml), "--attrs", str(attrs_yaml),
                     "--from-attrs"]) == 0
    assert "2 entries derived" in capsys.readouterr().out
    tags = styles.load(styles_yaml)
    assert tags[HERO1] == {"style": "dark-composite", "variant": "light", "confidence": 0.8,
                           "page": "comic-book-generator", "slot": "S01-m1", "source": "rules"}
    assert tags[hero2]["style"] == "before-after"
    assert {r[0] for r in con.execute("SELECT style FROM media WHERE style IS NOT NULL")} == {"dark-composite", "before-after"}
    # a re-index drops the tags; --apply-only re-mirrors the yaml
    assert cli.main(["--db", dbp, "--pages-dir", str(pages), "sectionize", "--all"]) == 0
    assert "0 style-tagged" in capsys.readouterr().out, "sectionize re-applies the default yaml, which is absent here"
    assert cli.main(["--db", dbp, "styles", "--styles", str(styles_yaml), "--apply-only"]) == 0
    assert "2 media rows tagged" in capsys.readouterr().out


def test_reference_files_name_families_and_carry_the_required_keys():
    """corpus/references/<family>.yaml (written by /collect-references) stays
    pinned to db.STYLES and to the schema in reference-format.md; a
    **References:** line in the doc names an existing file."""
    import yaml
    refs = styles.DOC.parents[3] / "corpus" / "references"
    required = ("family", "collected", "by", "photography", "examples", "creators", "picsart_specific", "prompt_guidance", "open")
    for path in refs.glob("*.yaml"):
        if path.name.startswith("_"):
            continue
        assert path.stem in db.STYLES, path
        d = yaml.safe_load(path.read_text())
        assert d["family"] == path.stem and all(k in d for k in required), (path, [k for k in required if k not in d])
        assert len(d["examples"]) >= 5, path
        for e in d["examples"]:
            assert "pexels.com" in e["url"] or "unsplash.com" in e["url"], (path, e["url"])
    doc = styles.DOC.read_text()
    for m in re.finditer(r"\*\*References:\*\* (corpus/references/([a-z-]+)\.yaml)", doc):
        assert (styles.DOC.parents[3] / m.group(1)).exists() and m.group(2) in db.STYLES, m.group(0)
