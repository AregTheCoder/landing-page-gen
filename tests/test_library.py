"""The generated library tree: bucketing (by-model vs general, _unlabelled
stand-ins, Screenshots), the Markdown sidecars, page dossiers, INDEX matrices,
hardlinking, and an idempotent rebuild. taxonomy is exercised in its own test;
here structure_of/model_of are pinned so the filing logic is what is measured."""

import os

import yaml

from landing_page_gen.corpus import attrs, cli, db, library, media, taxonomy
from test_attrs import build, HERO1

HERO2 = HERO1.replace("hero1", "hero2")


def test_tree_path_partitions_and_unlabelled():
    base = {"role": "creative", "kind": "image"}
    assert library.tree_path({**base, "model": "flux-3", "art_style": "photo", "structure": "single-picture"}) \
        == __import__("pathlib").Path("Images/by-model/flux-3/photo/single-picture")
    assert library.tree_path({**base, "model": None, "art_style": "photo", "structure": "card"}) \
        == __import__("pathlib").Path("Images/general/photo/card")
    assert str(library.tree_path({**base, "model": None, "art_style": None, "structure": None})) \
        == "Images/general/_unlabelled/_unlabelled"
    assert str(library.tree_path({**base, "kind": "video", "model": "flux-3", "art_style": "photo", "structure": "single-picture"})) \
        == "Videos/by-model/flux-3/photo/single-picture"
    assert str(library.tree_path({"role": "ui-screenshot", "kind": "image"})) == "Screenshots"


def _rec(**over):
    rec = {"key": "abc-1234", "kind": "image", "role": "creative", "src": "https://cdn.x/a.png",
           "ext": "png", "file": "abc-1234.png", "local": "corpus/x/abc-1234.png", "missing": False,
           "asset_id": "abc", "phash": "ff00", "measured": {"ground": "black", "layout": "single", "panel_count": 1,
           "before_after": False, "aspect_class": "1:1", "size": "card", "width": 480, "height": 480,
           "nat_width": 1024, "nat_height": 1024, "aspect": "1:1", "duration": None},
           "labelled": {"chrome": ["tile"], "subject": "product", "text_in_image": "none", "ui_mockup": "none",
           "description": "a thing", "confidence": 0.9, "fields": ["chrome"], "sheet": "s1", "at": "2026-09-14"},
           "family": "dark-composite", "variant": None, "tier": "corpus", "licence": "picsart",
           "art_style": "photo", "structure": "single-picture", "structure_source": "measured",
           "model": "flux-3", "model_evidence": "page", "models": [],
           "placements": [{"slug": "ai-image-generator", "slot": "S01-m1", "type": "hero", "headline": "Make it"}],
           "poster": None}
    rec.update(over)
    return rec


def test_sidecar_frontmatter_and_body():
    md = library.sidecar(_rec())
    front = yaml.safe_load(md.split("---")[1])
    assert front["key"] == "abc-1234" and front["model"] == "flux-3"
    assert front["structure"] == "single-picture" and front["structure_source"] == "measured"
    assert front["labelled"]["chrome"] == ["tile"]
    assert front["placements"][0] == {"page": "ai-image-generator", "slot": "S01-m1", "section": "S01",
                                       "type": "hero", "headline": "Make it"}
    assert front["library"] == "Images/by-model/flux-3/photo/single-picture"
    assert "## Appears on" in md and "Pages/ai-image-generator/page.md#s01" in md


def test_missing_asset_sidecar_flags_it():
    md = library.sidecar(_rec(missing=True))
    assert yaml.safe_load(md.split("---")[1])["missing"] is True


def _fixture(tmp_path, monkeypatch):
    con, pages = build(tmp_path, ["ai-models--flux-3", "some-tool"], monkeypatch)
    # a rendition of HERO1: same base, a query string, larger -> merges, becomes canonical
    row = con.execute("SELECT * FROM media WHERE src = ? LIMIT 1", (HERO1,)).fetchone()
    con.execute("INSERT INTO media (section_id, slot_id, kind, role, src, alt, width, height, aspect, "
                "nat_width, nat_height, duration, local_path, style, attrs, selector) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (row["section_id"], row["slot_id"], "image", "creative", HERO1 + "?w=2000", None,
                 900, 1350, "2:3", 2000, 3000, None, row["local_path"], None, None, "x"))
    # one media row becomes a screenshot; another loses its local file
    con.execute("UPDATE media SET role = 'ui-screenshot' WHERE src = ?", (HERO2,))
    con.execute("UPDATE media SET local_path = NULL WHERE kind = 'video'")
    # one page has a snapshot (gets a dossier); the other is an app shell (no snapshot)
    con.execute("UPDATE pages SET screenshot_path = 'screenshot.png' WHERE slug = 'ai-models--flux-3'")
    con.execute("UPDATE pages SET screenshot_path = NULL WHERE slug = 'some-tool'")
    con.commit()
    attrs_mapping = {HERO1: {"art_style": "photo", "chrome": ["tile"], "ground": "black"},
                     HERO2: {"art_style": None}}
    monkeypatch.setattr(taxonomy, "structure_of", lambda rec: ("single-picture", "measured") if rec.get("art_style") else (None, None))
    monkeypatch.setattr(taxonomy, "model_of", lambda aps, known: ("flux-3", "page", []) if any(
        p.get("slug") == "ai-models--flux-3" for p in aps) else (None, None, []))
    frames = tmp_path / "frames"
    frames.mkdir()
    return con, pages, attrs_mapping, frames


def test_organise_builds_tree_hardlinks_and_is_idempotent(tmp_path, monkeypatch, capsys):
    con, pages, attrs_mapping, frames = _fixture(tmp_path, monkeypatch)
    root = tmp_path / "library"
    c = library.organise(root, con, attrs_mapping, {}, {}, pages, tmp_path / "pages.yaml", frames, log=lambda m: None)

    # renditions merged: one sidecar for HERO1, keyed by the canonical (larger) rendition
    hero_dir = root / "Images/by-model/flux-3/photo/single-picture"
    mds = [p for p in hero_dir.glob("*.md") if p.name != "INDEX.md"]
    assert len(mds) == 1, "the two renditions of HERO1 merged into one asset"
    front = yaml.safe_load(mds[0].read_text().split("---")[1])
    assert front["src"].endswith("?w=2000") and "srcs" in front, "the largest rendition is canonical, both srcs listed"

    # the screenshot files under Screenshots, not Images
    assert list((root / "Screenshots").glob("*.md")), "the ui-screenshot role lands flat under Screenshots"

    # hardlink: the linked media shares its inode with the corpus original
    img = next(hero_dir.glob("*.webp"), None) or next(hero_dir.glob("*.png"), None)
    if img:
        assert os.stat(img).st_nlink >= 2

    # the video lost its local file -> missing sidecar, no crash
    vid_md = next((p for p in root.rglob("*.md") if "Videos" in str(p) and p.name != "INDEX.md"), None)
    if vid_md:
        assert yaml.safe_load(vid_md.read_text().split("---")[1]).get("missing") is True

    # page dossier: tables, kept-from-source; the shell is listed without a dossier
    page_md = (root / "Pages/ai-models--flux-3/page.md").read_text()
    assert "## Sections" in page_md and "## Assets" in page_md
    assert not (root / "Pages/some-tool/page.md").exists(), "an app shell gets no dossier"
    pages_index = (root / "Pages/INDEX.md").read_text()
    assert "App shells" in pages_index and "some-tool" in pages_index
    assert (root / "INDEX.md").read_text().startswith("# Corpus library")
    assert "art_style" in (root / "INDEX.md").read_text() and "structure" in (root / "INDEX.md").read_text()

    # idempotent: rebuild is byte-identical and leaves no tmp
    before = mds[0].read_text()
    library.organise(root, con, attrs_mapping, {}, {}, pages, tmp_path / "pages.yaml", frames, log=lambda m: None)
    assert mds[0].read_text() == before
    assert not (tmp_path / "library.tmp").exists()


def test_dry_run_writes_nothing(tmp_path, monkeypatch):
    con, pages, attrs_mapping, frames = _fixture(tmp_path, monkeypatch)
    root = tmp_path / "library"
    counts = library.organise(root, con, attrs_mapping, {}, {}, pages, tmp_path / "pages.yaml", frames,
                              dry_run=True, log=lambda m: None)
    assert not root.exists() and counts["images"] >= 1
