"""Attribute tagging: schema shape, dedup by src, resumable run with a fake
model, apply through the rule table surviving a re-index, the report, and
`similar` filtering on family/variant and attributes."""

import json

from PIL import Image

from landing_page_gen.corpus import attrs, cli, db, media, sectionize, similar, skeleton, styles, taxonomy
from test_corpus import HERO1, fake_download_factory, hero_render, make_page

HERO2 = HERO1.replace("hero1", "hero2")
VIDEO = "https://cdn-cms-uploads.picsart.com/cms-uploads/style.webm"
DARK_LIGHT = {"ground": "light-grey", "layout": "column-main", "panel_count": 1, "chrome": ["tile", "chip"],
              "text_in_image": "labels-only", "ui_mockup": "none", "subject": "product", "finish": "photo",
              "before_after": False, "description": "a product photo beside two tool tiles", "family_hint": "dark-composite",
              "confidence": 0.8}


class FakeGrabber:
    def __init__(self):
        self.calls = []

    def grab(self, src, png, at=1.0):
        self.calls.append((str(src), at))
        Image.new("RGB", (16, 9), "green").save(png, format="PNG")
        return png


def build(tmp_path, slugs, monkeypatch):
    monkeypatch.setattr(media, "download", fake_download_factory([]))
    pages = tmp_path / "pages"
    con = db.connect(tmp_path / "c.db")
    for slug in slugs:
        d = make_page(pages, slug, hero_render())
        media.localise_page(d, log=lambda m: None)
        sectionize.sectionize_page(d, con, log=lambda m: None)
    return con, pages


def test_schema_is_structured_output_safe_and_rules_total():
    assert attrs.SCHEMA["additionalProperties"] is False
    assert set(attrs.SCHEMA["required"]) == set(attrs.SCHEMA["properties"]) == set(attrs.FIELDS)
    for name, prop in attrs.SCHEMA["properties"].items():
        leaf = prop["items"] if prop.get("type") == "array" else prop
        assert leaf.get("type") in ("string", "integer", "number", "boolean"), name
        assert "minimum" not in leaf and "maxLength" not in leaf, "structured output rejects range constraints"
    assert set(attrs.ENUMS["family_hint"]) == set(db.STYLES) | {"other"}
    # every ground x layout x finish combination has an answer or is honestly unresolved
    for g in attrs.ENUMS["ground"]:
        for lay in attrs.ENUMS["layout"]:
            for fin in attrs.ENUMS["finish"]:
                fam, variant = taxonomy.family_of({"ground": g, "layout": lay, "finish": fin, "chrome": [], "type": "hero"})
                assert fam is None or fam in db.STYLES


def test_candidates_dedup_by_src_and_carry_classes(tmp_path, monkeypatch):
    con, _ = build(tmp_path, ["comic-book-generator", "manga-maker", "storyboard-generator"], monkeypatch)
    cands = attrs.candidates(con, {})
    by_src = {c["src"]: c for c in cands}
    hero = by_src[HERO1]
    assert hero["n_pages"] == 3 and hero["n_rows"] == 3, "one candidate stands for every page that reuses the asset"
    assert hero["size"] == "tile" and hero["aspect_class"] == "2:3" and hero["kind"] == "image"
    assert by_src[VIDEO]["kind"] == "video" and by_src[VIDEO]["aspect_class"] == "16:9"
    assert cands == sorted(cands, key=lambda c: (c["type"], c["page"], c["slot"]))
    assert attrs.candidates(con, {HERO1: {}}) == [c for c in cands if c["src"] != HERO1], "tagged assets are skipped"
    assert len(attrs.candidates(con, {HERO1: {}}, force=True)) == len(cands)
    e = attrs.estimate(cands)
    assert e["candidates"] == len(cands) and e["by_kind"]["video"] == 1 and e["usd"] > 0
    assert attrs.asset_id("https://cdn.x/cms-uploads/21cdafd9-b685-4558-94a5-8d5495a624f9.webp?r=1") == "21cdafd9"


def test_picture_skips_svg_and_grabs_video_frames(tmp_path, monkeypatch):
    con, pages = build(tmp_path, ["comic-book-generator"], monkeypatch)
    cands = {c["src"]: c for c in attrs.candidates(con, {})}
    svg = tmp_path / "x.svg"
    svg.write_text("<svg/>")
    rec = dict(cands[HERO1], local_path=str(svg))
    assert attrs.picture(rec, tmp_path / "frames") == (None, "svg")
    b64, shown = attrs.picture(cands[HERO1], tmp_path / "frames")
    assert b64 and shown.endswith(".avif")
    g = FakeGrabber()
    b64, shown = attrs.picture(cands[VIDEO], tmp_path / "frames", grabber=g)
    assert b64 and shown.endswith(".png") and len(g.calls) == 1
    attrs.picture(cands[VIDEO], tmp_path / "frames", grabber=g)
    assert len(g.calls) == 1, "the frame is cached"


def test_run_is_resumable_and_apply_survives_reindex(tmp_path, monkeypatch, capsys):
    con, pages = build(tmp_path, ["comic-book-generator"], monkeypatch)
    calls = []

    def fake_describe(client, png_b64, context, system, model):
        calls.append((context, model))
        return dict(DARK_LIGHT), {"input_tokens": 10, "cache_read_input_tokens": 5, "output_tokens": 3}
    monkeypatch.setattr(attrs, "describe", fake_describe)
    monkeypatch.setattr(attrs, "system_prompt", lambda: "system")
    yml, frames = tmp_path / "attributes.yaml", tmp_path / "frames"
    mapping, stats = attrs.run(con, dry_run=True, path=yml, frames_dir=frames, client=object())
    assert stats["estimate"]["candidates"] == 5 and calls == [] and not yml.exists()
    mapping, stats = attrs.run(con, limit=1, path=yml, frames_dir=frames, client=object(), grabber=FakeGrabber())
    assert stats["tagged"] == 1 and len(mapping) == 1 and len(calls) == 1
    assert calls[0][0].startswith("Context: a feature-callout section on a tool page") and "video" in calls[0][0]
    assert calls[0][1] == attrs.MODEL, "a panel-class asset goes to the main model"
    mapping, stats = attrs.run(con, path=yml, frames_dir=frames, client=object(), grabber=FakeGrabber())
    assert stats["tagged"] == 4 and len(mapping) == 5 and len(calls) == 5, "second run only describes what is left"
    assert any("hero section" in c[0] and c[1] == attrs.MODEL_TILES for c in calls), "tile-class assets go to the tile model"
    assert stats["usage"] == {"input_tokens": 40, "cache_read_input_tokens": 20, "output_tokens": 12}
    saved = attrs.load(yml)
    rec = saved[HERO1]
    assert rec["chrome"] == ["tile", "chip"] and rec["before_after"] is False and rec["px"] == 512
    assert rec["page"] == "comic-book-generator" and rec["n_rows"] == 1 and rec["type"] == "hero"
    assert saved[VIDEO]["kind"] == "video" and saved[VIDEO]["local"].endswith(".png")
    # apply: attrs JSON with the derived variant, family, and the role fix; a re-index drops them; sectionize --all restores
    n = attrs.apply(con, saved)
    assert n >= 3
    row = con.execute("SELECT style, attrs, role FROM media WHERE src = ?", (HERO1,)).fetchone()
    assert row["style"] == "dark-composite" and json.loads(row["attrs"])["variant"] == "light" and row["role"] == "creative"
    out = tmp_path / "r" / "skeleton.md"
    skeleton.write_skeleton(con, "comic-book-generator", out)
    text = out.read_text()
    assert "> style: dark-composite/light\n" in text and "size_class: tile\n" in text
    sectionize.sectionize_page(pages / "comic-book-generator", con, log=lambda m: None)
    assert con.execute("SELECT attrs FROM media WHERE src = ?", (HERO1,)).fetchone()[0] is None
    monkeypatch.setattr(attrs, "ATTRIBUTES_YAML", yml)
    monkeypatch.setattr(attrs, "load", lambda path=yml: styles.load(yml))
    assert cli.main(["--db", str(tmp_path / "c.db"), "--pages-dir", str(pages), "sectionize", "--all"]) == 0
    assert con.execute("SELECT style FROM media WHERE src = ?", (HERO1,)).fetchone()[0] == "dark-composite"


def test_rules_table_and_role_fix():
    cases = [
        ({"before_after": True, "ground": "black"}, ("before-after", None)),
        ({"chrome": ["brackets", "tile"], "ground": "white"}, ("crop-frame", None)),
        ({"ground": "checkerboard", "finish": "photo"}, ("cutout-checkerboard", "checker")),
        ({"chrome": ["prompt-panel"], "ground": "black"}, ("prompt-card", None)),
        ({"layout": "two-up", "chrome": ["vs-badge", "pill"], "ground": "light-grey"}, ("vs-two-up", None)),
        ({"ui_mockup": "app-card", "ground": "black", "layout": "split"}, ("mockup-card", None)),
        ({"chrome": ["mockup-card", "tile"], "text_in_image": "headline", "ground": "black"}, ("template-mockup", "black")),
        ({"ui_mockup": "editor-canvas", "type": "link-grid", "ground": "white"}, ("editor-canvas", None)),
        ({"type": "link-grid", "chrome": ["chip"], "ground": "light-grey", "layout": "stacked"}, ("model-card", None)),
        (DARK_LIGHT, ("dark-composite", "light")),
        ({"ground": "photo-full-bleed", "aspect_class": "9:16", "type": "gallery", "panel_count": 1}, ("cinematic-still", None)),
        ({"finish": "collage", "ground": "solid-colour"}, ("graphic-collage", None)),
        ({"type": "gallery", "ground": "white", "size": "tile", "panel_count": 1}, ("outcome-tile", None)),
        ({"ground": "photo-full-bleed", "panel_count": 1, "type": "hero", "aspect_class": "1:1"}, ("full-bleed", None)),
        ({"ground": "gradient", "layout": "grid", "panel_count": 6}, (None, None)),
    ]
    for rec, expected in cases:
        assert taxonomy.family_of(rec) == expected, rec
    assert taxonomy.role_fix({"role": "creative", "finish": "screenshot"}) == "ui-screenshot"
    assert taxonomy.role_fix({"role": "creative", "ui_mockup": "app-card", "finish": "photo"}) is None
    assert taxonomy.role_fix({"role": "ui-screenshot", "finish": "photo", "ui_mockup": "none"}) == "creative"
    assert taxonomy.style_label("dark-composite", "light") == "dark-composite/light"


def test_report_and_sheets(tmp_path):
    png = tmp_path / "a.png"
    Image.new("RGB", (40, 30), "red").save(png)
    mapping = {}
    for i in range(6):
        mapping[f"https://cdn.x/{i:08x}-aaaa.png"] = dict(DARK_LIGHT, type="feature-callout", aspect_class="1:1", page=f"p{i}",
                                                          slot="S06-m1", n_rows=2, local=str(png), size="card")
    mapping["https://cdn.x/ffffffff-bbbb.png"] = dict(DARK_LIGHT, ground="gradient", layout="grid", type="gallery",
                                                      aspect_class="9:16", page="g", slot="S03-m1", n_rows=1, local="missing.png")
    report, n_groups, n_unresolved = taxonomy.write_report(mapping, tmp_path / "tax", min_n=5, per_cell=4)
    text = report.read_text()
    assert n_groups == 2 and n_unresolved == 1
    assert "| 1:1 | light-grey | column-main | 6 | 12 | 6 | 100 | dark-composite/light 6 | dark-composite 6 |" in text
    assert "## Unresolved (1)" in text and "g S03-m1 (gallery, 9:16)" in text
    sheet = tmp_path / "tax" / "feature-callout_1x1_light-grey_column-main.png"
    assert sheet.exists() and Image.open(sheet).width == 6 * 200
    assert (tmp_path / "tax" / "gallery_rest.png").exists()
    groups = json.loads((tmp_path / "tax" / "groups.json").read_text())
    assert groups[0]["assets"] == 6 and groups[0]["families"] == {"dark-composite/light": 6}
    assert taxonomy.resolved_share(mapping) == 6 / 7


def test_similar_filters_variant_attrs_and_asset(tmp_path, monkeypatch):
    con, _ = build(tmp_path, ["comic-book-generator", "manga-maker", "storyboard-generator"], monkeypatch)
    con.execute("""UPDATE media SET style = 'dark-composite', attrs = ? WHERE src = ? AND section_id IN
                   (SELECT s.id FROM sections s JOIN pages p ON p.id = s.page_id WHERE p.slug = 'storyboard-generator')""",
                (json.dumps({"ground": "light-grey", "variant": "light"}), HERO1))
    con.commit()
    q = "Comic Book Generator turn your story into a comic"
    rows = similar.find_similar(con, "hero", q, k=2, exclude="comic-book-generator", style="dark-composite/light")
    assert [r["slug"] for r in rows] == ["storyboard-generator", "manga-maker"], "variant match first, untagged fills"
    rows = similar.find_similar(con, "hero", q, k=1, exclude="comic-book-generator", attrs={"ground": "light-grey"})
    assert rows[0]["slug"] == "storyboard-generator"
    rows = similar.find_similar(con, "hero", q, k=3, exclude="comic-book-generator", exclude_asset="hero1")
    assert rows == [], "every hero shows the excluded asset"
    assert similar.split_style("dark-composite/light") == ("dark-composite", "light")
    try:
        similar.split_style("nope")
        assert False
    except ValueError:
        pass


def test_styles_derive_keeps_manual_entries():
    existing = {"a": {"style": "full-bleed", "confidence": 1.0, "page": "x", "slot": "S01-m1"},
                "b": {"style": "crop-frame", "source": "rules", "page": "y", "slot": "S02-m1"}}
    derived = styles.derive({"a": DARK_LIGHT, "b": DARK_LIGHT, "c": {"ground": "gradient", "layout": "grid"}}, existing)
    assert derived["a"]["style"] == "full-bleed", "legacy entries without a source count as manual"
    assert derived["b"] == {"style": "dark-composite", "variant": "light", "confidence": 0.8, "page": None, "slot": None, "source": "rules"}
    assert "c" not in derived, "unresolved assets get no style entry"
