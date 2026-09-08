"""Attribute tagging: schema shape, dedup by src, the pixel measuring pass,
the labelling sheets and their answers, apply through the rule table
surviving a re-index, the report, and `similar` filtering on family/variant
and attributes."""

import json

import numpy as np
import yaml
from PIL import Image

from landing_page_gen.corpus import (attrs, cli, db, label, measure, media, sectionize, sheets, similar,
                                     skeleton, styles, taxonomy)
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


def test_vocabulary_covers_every_field_and_the_rules_are_total():
    asked = set(sheets.SEMANTIC) | set(measure.FIELDS)
    assert asked == set(attrs.FIELDS), "every field is either measured or asked for on a sheet"
    assert set(measure.FIELDS) & set(sheets.SEMANTIC) == set(), "and never both"
    for name, (values, definition) in attrs.FIELDS.items():
        assert isinstance(values, tuple) or values in ("integer", "number", "boolean", "string"), name
        assert definition and label.check(name, next(iter(values)) if isinstance(values, tuple) else 1)[1] is None
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
    assert e["candidates"] == len(cands) and e["by_kind"]["video"] == 1 and e["by_size"]["tile"] >= 1
    assert attrs.asset_id("https://cdn.x/cms-uploads/21cdafd9-b685-4558-94a5-8d5495a624f9.webp?r=1") == "21cdafd9"


def test_picture_skips_svg_and_grabs_video_frames(tmp_path, monkeypatch):
    con, pages = build(tmp_path, ["comic-book-generator"], monkeypatch)
    cands = {c["src"]: c for c in attrs.candidates(con, {})}
    svg = tmp_path / "x.svg"
    svg.write_text("<svg/>")
    rec = dict(cands[HERO1], local_path=str(svg))
    assert attrs.picture(rec, tmp_path / "frames") == (None, "svg")
    path, shown = attrs.picture(cands[HERO1], tmp_path / "frames")
    assert path.exists() and shown.endswith(".avif")
    g = FakeGrabber()
    path, shown = attrs.picture(cands[VIDEO], tmp_path / "frames", grabber=g)
    assert path.exists() and shown.endswith(".png") and len(g.calls) == 1
    attrs.picture(cands[VIDEO], tmp_path / "frames", grabber=g)
    assert len(g.calls) == 1, "the frame is cached"


def test_run_measures_is_resumable_and_apply_survives_reindex(tmp_path, monkeypatch):
    con, pages = build(tmp_path, ["comic-book-generator"], monkeypatch)
    yml, frames = tmp_path / "attributes.yaml", tmp_path / "frames"
    mapping, stats = attrs.run(con, dry_run=True, path=yml, frames_dir=frames)
    assert stats["estimate"]["candidates"] == 5 and not yml.exists(), "a dry run counts and writes nothing"
    mapping, stats = attrs.run(con, limit=1, path=yml, frames_dir=frames, grabber=FakeGrabber())
    assert stats["measured"] == 1 and len(mapping) == 1
    mapping, stats = attrs.run(con, path=yml, frames_dir=frames, grabber=FakeGrabber())
    assert stats["measured"] == 4 and len(mapping) == 5, "a second run only measures what is left"
    saved = attrs.load(yml)
    rec = saved[HERO1]
    assert rec["source"] == "measured" and rec["ground"] == "solid-colour" and rec["before_after"] is False
    assert rec["page"] == "comic-book-generator" and rec["n_rows"] == 1 and rec["type"] == "hero"
    assert not any(f in rec for f in sheets.SEMANTIC), "the pixels answer no semantic field"
    assert saved[VIDEO]["kind"] == "video" and saved[VIDEO]["local"].endswith(".png")
    # a pass writes only what it measured, so a labelling merge that lands
    # while it runs survives its final save, and --force keeps the answers
    labelled = dict(mapping[HERO1], subject="person", finish="photo", labelled=["finish", "subject"], source="sheet")
    attrs.save({**attrs.load(yml), HERO1: labelled, "https://cdn.x/hand-written.png": {"ground": "white"}}, yml)
    mapping, stats = attrs.run(con, path=yml, frames_dir=frames, grabber=FakeGrabber(), force=True)
    assert stats["measured"] == 5 and "https://cdn.x/hand-written.png" in attrs.load(yml)
    again = attrs.load(yml)[HERO1]
    assert again["subject"] == "person" and again["labelled"] == ["finish", "subject"] and again["source"] == "sheet"
    assert again["ground"] == "solid-colour", "the pixel fields are measured again"
    # the sheet answers complete the record; the rule table then names a family
    for src in saved:
        saved[src].update({k: v for k, v in DARK_LIGHT.items() if k in sheets.SEMANTIC})
        saved[src].update({"ground": "light-grey", "layout": "column-main", "panel_count": 1})
    attrs.save(saved, yml)
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


def noise(w=256, h=256, seed=0, lo=0.4, hi=1.0):
    rng = np.random.default_rng(seed)
    a = rng.uniform(lo, hi, size=(h, w, 3))
    return Image.fromarray((a * 255).astype("uint8"), "RGB")


def smooth(w=128, h=200):
    """A picture with photographic statistics: varied, but no hard edges of
    its own, so a divider stands out the way it does in a real composite."""
    yy, xx = np.mgrid[0:h, 0:w]
    a = 0.5 + 0.4 * np.sin(xx / 19.0) * np.cos(yy / 23.0)
    return np.repeat(a[..., None], 3, axis=2)


def test_measure_reads_ground_layout_panels_and_before_after(tmp_path):
    def saved(im, name):
        path = tmp_path / name
        im.save(path)
        return path

    two_up = Image.new("RGB", (256, 160), "black")
    for x0 in (12, 138):
        two_up.paste(Image.new("RGB", (106, 120), "white"), (x0, 20))
    m = measure.measure(saved(two_up, "two-up.png"))
    assert (m["ground"], m["layout"], m["panel_count"]) == ("black", "two-up", 2)

    checker = Image.new("RGB", (256, 256), "#ffffff")
    for y in range(0, 256, 16):
        for x in range(0, 256, 16):
            if (x // 16 + y // 16) % 2:
                checker.paste(Image.new("RGB", (16, 16), "#e6e6e6"), (x, y))
    assert measure.measure(saved(checker, "checker.png"))["ground"] == "checkerboard"

    m = measure.measure(saved(noise(), "photo.png"))
    assert (m["ground"], m["layout"], m["panel_count"]) == ("photo-full-bleed", "single", 1)
    assert m["before_after"] is False

    half = smooth()
    ba = Image.fromarray((np.concatenate([half, half * 0.4], axis=1) * 255).astype("uint8"), "RGB")
    m = measure.measure(saved(ba, "before-after.png"))
    assert m["layout"] == "split" and m["panel_count"] == 2 and m["before_after"] is True
    assert 0.45 < m["seam"][0] < 0.55 and m["seam"][1] > measure.SPLIT_CORR

    grad = Image.merge("RGB", [Image.linear_gradient("L")] * 3)
    assert measure.measure(saved(grad, "grad.png"))["ground"] == "gradient"

    cutout = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
    cutout.paste(Image.new("RGBA", (120, 120), (200, 30, 30, 255)), (68, 68))
    m = measure.measure(saved(cutout, "cutout.png"))
    assert "ground" not in m, "a transparent border means the page supplies the ground"

    assert measure.measure(saved(noise(seed=2), "alt.png"), alt="Before and after removing the background")["before_after"]

    off = np.concatenate([smooth()[:, :48], smooth()[:, 48:] * 0.4], axis=1)
    m = measure.measure(saved(Image.fromarray((off * 255).astype("uint8"), "RGB"), "off-centre.png"))
    assert m["layout"] == "split" and m["before_after"] is False, "an off-centre divider is two panels, not an edit"
    assert "before_after" in sheets.fields_for(m), "so the sheet asks about it"


def test_sheets_group_the_pending_assets_and_labels_merge_the_answers(tmp_path):
    png = tmp_path / "a.png"
    Image.new("RGB", (40, 30), "red").save(png)
    mapping = {}
    for i in range(14):
        mapping[f"https://cdn.x/{i:08x}-aaaa.png"] = {
            "ground": "black", "layout": "column-main", "panel_count": 2, "before_after": False,
            "source": "measured", "type": "feature-callout", "page": f"p{i}", "slot": "S06-m1", "size": "card",
            "aspect_class": "1:1", "kind": "image", "role": "creative", "page_family": "tool",
            "n_rows": 1, "n_pages": 1, "local": str(png)}
    # one asset the measured fields alone already place in a family
    mapping["https://cdn.x/ffffffff-bbbb.png"] = dict(mapping["https://cdn.x/00000000-aaaa.png"],
                                                      ground="photo-full-bleed", layout="single", panel_count=1,
                                                      type="hero", local=str(png))
    built, stats = sheets.build(mapping, tmp_path / "labels", per_sheet=12, thumb=80, columns=4)
    assert stats["pending"] == 15 and stats["sheets"] == 3
    assert [s["cells"] for s in built] == [12, 2, 1], "12 per sheet, then the rest of each group"
    assert built[-1]["group"][0] == "hero", "assets that already resolve to a family come last"
    assert sheets.pending(mapping, skip_resolved=True) and len(sheets.pending(mapping, skip_resolved=True)) == 14
    first = built[0]
    assert first["png"].exists() and Image.open(first["png"]).width == 4 * 80
    man = yaml.safe_load((tmp_path / "labels" / f"{first['name']}.yaml").read_text())
    assert man["cells"][1]["asset"] == "00000000" and man["cells"][1]["ground"] == "black"
    assert man["fields"] == sorted(sheets.SEMANTIC), "every measurable field is already answered"
    index = sheets.write_index(built, tmp_path / "labels", stats)
    assert "chrome (list, any of tile" in index.read_text()

    answers = {1: {k: v for k, v in DARK_LIGHT.items() if k in sheets.SEMANTIC},
               2: {"finish": "nope", "subject": "person"},
               3: {"chrome": "tile, chip"},
               9: {"chrome": ["telephone"]},
               99: {"subject": "person"}}
    (tmp_path / "labels" / man["answers"]).write_text(yaml.safe_dump(answers))
    merged, stats = label.ingest(mapping, tmp_path / "labels", log=lambda m: None)
    assert stats["answered"] == 1 and stats["sheets"] == 3 and stats["cells"] == 3
    one = merged["https://cdn.x/00000000-aaaa.png"]
    assert one["source"] == "sheet" and one["sheet"] == first["name"] and one["finish"] == "photo"
    assert one["labelled"] == sorted(sheets.SEMANTIC) and one["ground"] == "black", "measured fields survive"
    assert taxonomy.family_of(one) == ("dark-composite", None), "black is the family default ground"
    two = merged["https://cdn.x/00000001-aaaa.png"]
    assert two["subject"] == "person" and "finish" not in two, "a value outside the enum is dropped, not written"
    assert merged["https://cdn.x/00000002-aaaa.png"]["chrome"] == ["chip", "tile"], "a comma list is a chrome list"
    assert any("finish: 'nope'" in e for e in stats["errors"])
    assert any("chrome: telephone" in e for e in stats["errors"])
    assert any("cell 99" in e for e in stats["errors"])
    cov = label.coverage(merged)
    assert cov["subject"] == round(2 / 15, 3) and cov["ground"] == 1.0 and cov["complete"] < 1

    # rebuilding drops the fully answered asset and never hands its answers file
    # to a sheet of different pictures
    again, stats = sheets.build(merged, tmp_path / "labels", per_sheet=12, thumb=80, columns=4)
    assert stats["pending"] == 14 and [s["name"] for s in again] != [s["name"] for s in built]
    assert not any(s["answered"] for s in again), "the answered sheet's name is not reused"
    kept = yaml.safe_load((tmp_path / "labels" / f"{first['name']}.yaml").read_text())
    assert kept["cells"][1]["src"] == "https://cdn.x/00000000-aaaa.png", "its manifest still matches its answers"
    merged, stats = label.ingest(merged, tmp_path / "labels", log=lambda m: None)
    assert stats["cells"] == 3, "re-ingesting the same answers is idempotent"


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
        ({"chrome": ["adjust-panel", "chip", "slider"], "ground": "photo-full-bleed", "layout": "overlay", "finish": "photo",
          "type": "use-case-grid"}, ("panel-overlay", None)),
        ({"chrome": ["adjust-panel", "slider"], "ground": "white", "layout": "overlay", "finish": "photo",
          "type": "use-case-grid"}, ("panel-overlay", "white")),
        ({"chrome": ["pill", "badge"], "ground": "photo-full-bleed", "layout": "single", "panel_count": 1, "finish": "photo",
          "type": "hero"}, ("panel-overlay", None)),
        ({"chrome": ["pill"], "ground": "photo-full-bleed", "layout": "single", "panel_count": 1, "finish": "photo",
          "type": "hero"}, ("full-bleed", None)),
        ({"chrome": ["slider", "tile"], "ground": "black", "layout": "column-main", "finish": "photo", "type": "feature-callout"},
         ("dark-composite", None)),  # a slider alone is not the panel: only overlay layouts or adjust-panel say panel-overlay
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
