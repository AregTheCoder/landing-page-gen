"""The read-time taxonomy: structure_of (coarse picture shape), model_of (who
generated an asset from where it is placed), the slug helpers, and the
idempotent finish->art_style migration that rides inside label.ingest."""

import yaml

from landing_page_gen.corpus import attrs, label, sheets, taxonomy
from test_attrs import build


# --- Part B: structure_of -----------------------------------------------------

def test_structure_measured_rules():
    cases = [
        ({"before_after": True, "layout": "single"}, "before-after"),          # 1 beats 10
        ({"ground": "checkerboard", "layout": "single"}, "cutout-checkerboard"),  # 2
        ({"layout": "column-main"}, "column-main"),                            # 7
        ({"layout": "two-up", "panel_count": 2}, "side-by-side"),              # 8
        ({"layout": "grid", "panel_count": 2}, "side-by-side"),                # 8 (<=2)
        ({"layout": "grid", "panel_count": 6}, "grid-set"),                    # 9 (3+)
        ({"layout": "single"}, "single-picture"),                             # 10
        ({"ground": "photo-full-bleed", "layout": "overlay"}, "panel-overlay"),  # 4 beats 10
        ({}, None),                                                            # 11
    ]
    for rec, expected in cases:
        assert taxonomy.structure_of(rec)[0] == expected, rec
    assert all(taxonomy.structure_of(r)[0] in (taxonomy.STRUCTURES + (None,)) for r, _ in cases)


def test_structure_labelled_precedence_and_source():
    # rule 1 (pixel) beats card even with a mockup-card chrome present
    assert taxonomy.structure_of({"before_after": True, "chrome": ["mockup-card"], "ui_mockup": "app-card"})[0] == "before-after"
    # rule 5 (vs-badge) beats rule 6 (card) ...
    assert taxonomy.structure_of({"chrome": ["vs-badge"], "ui_mockup": "app-card"})[0] == "side-by-side"
    # ... and rule 6 (card) beats rule 8 (layout)
    assert taxonomy.structure_of({"chrome": ["mockup-card"], "layout": "two-up"})[0] == "card"
    assert taxonomy.structure_of({"ui_mockup": "product-card", "layout": "grid", "panel_count": 6})[0] == "card"
    # source: an answered chrome (even empty) is labelled evidence; no chrome is measured
    assert taxonomy.structure_of({"chrome": [], "layout": "single"}) == ("single-picture", "labelled")
    assert taxonomy.structure_of({"layout": "single"}) == ("single-picture", "measured")


# --- Part C: model_of + helpers ----------------------------------------------

def P(slug, type="hero", headline=None):
    return {"slug": slug, "family": None, "type": type, "headline": headline, "role": "creative", "kind": "image", "slot": "S01-m1"}


def test_model_of_rules():
    known = {"flux-3", "dall-e-3", "recraft-v4-1"}
    # exclusive ai-models page
    assert taxonomy.model_of([P("ai-models--flux-3")], known) == ("flux-3", "page", [])
    # own page + a tool page -> still that one ai-models page
    assert taxonomy.model_of([P("ai-models--flux-3"), P("ai-image-generator")], known) == ("flux-3", "page", [])
    # shared across two ai-models pages -> general
    assert taxonomy.model_of([P("ai-models--flux-3"), P("ai-models--dall-e-3")], known)[1] == "shared"
    # headline naming a known model is a strict upgrade of the page set
    assert taxonomy.model_of([P("ai-image-generator", headline="Created with Recraft V4 1")], known) == ("recraft-v4-1", "headline", [])
    # two headlines conflict -> general
    m, e, names = taxonomy.model_of([P("g", headline="Made with Flux 3"), P("g2", headline="Created with DALL E 3")], known)
    assert m is None and e == "conflict" and names == ["dall-e-3", "flux-3"]
    # a headline naming an unknown model falls back to the page set
    assert taxonomy.model_of([P("ai-models--flux-3", headline="Made with Nonesuch 9")], known) == ("flux-3", "page", [])
    # link-grid placements are never evidence
    assert taxonomy.model_of([P("ai-models--flux-3", type="link-grid")], known) == (None, None, [])
    # a lone compare page yields the pair, general
    assert taxonomy.model_of([P("compare-models--flux-3-vs-dall-e-3")], known) == (None, "compare", ["flux-3", "dall-e-3"])
    # tool-only -> general
    assert taxonomy.model_of([P("ai-image-generator")], known) == (None, None, [])


def test_slug_helpers():
    assert taxonomy.slugify("Flux 2 Max") == "flux-2-max"
    assert taxonomy.slugify("DALL·E 3") == "dall-e-3"
    assert taxonomy.model_slug("ai-models--flux-3") == "flux-3"
    assert taxonomy.model_slug("ai-image-generator") is None
    assert taxonomy.display_name("Flux 2 Max AI Image Generator") == "Flux 2 Max"
    assert taxonomy.display_name("Recraft V4") == "Recraft V4"


def test_placements_and_model_slugs_on_a_db(tmp_path, monkeypatch):
    con, _ = build(tmp_path, ["ai-models--flux-3", "ai-image-generator"], monkeypatch)
    assert "flux-3" in taxonomy.model_slugs(con)
    pl = taxonomy.placements(con)
    assert isinstance(pl, dict) and pl, "generated-role media are placed"
    for ps in pl.values():
        assert all({"slug", "type", "headline", "role", "kind", "slot"} <= set(p) for p in ps)


# --- migration idempotence (rides inside label.ingest) ------------------------

def _labels_dir(tmp_path):
    d = tmp_path / "labels"
    d.mkdir()
    man = {"sheet": "s1", "fields": ["chrome", "finish", "subject"],
           "answers": "s1.answers.yaml", "cells": {1: {"src": "https://cdn.x/a.png"}}}
    (d / "s1.yaml").write_text(yaml.safe_dump(man, sort_keys=False))
    (d / "s1.answers.yaml").write_text("# a labeller's note\n1:\n  finish: 3d\n  subject: product\n")
    # an orphan answers file with no manifest (the naming scheme changed once)
    (d / "orphan.answers.yaml").write_text("1:\n  finish: collage\n")
    return d


def test_ingest_migrates_finish_idempotently(tmp_path):
    d = _labels_dir(tmp_path)
    mapping = {"https://cdn.x/a.png": {"finish": "screenshot", "labelled": ["finish", "subject"], "subject": "product"}}
    _, stats = label.ingest(dict(mapping), d, log=lambda m: None)
    assert stats["migrated"] >= 3, "answers file, orphan, manifest all rewritten"
    # manifest fields renamed
    assert yaml.safe_load((d / "s1.yaml").read_text())["fields"] == ["art_style", "chrome", "subject"]
    # answers value mapped, leading comment preserved
    ans = (d / "s1.answers.yaml").read_text()
    assert ans.startswith("# a labeller's note")
    assert yaml.safe_load(ans)[1] == {"art_style": "3d-render", "subject": "product"}
    assert yaml.safe_load((d / "orphan.answers.yaml").read_text())[1] == {"art_style": "collage"}
    # migrate_record renames the key, maps the value and rewrites labelled (isolated)
    fresh = {"finish": "screenshot", "labelled": ["finish", "subject"], "subject": "product"}
    label.migrate_record(fresh, {"errors": []})
    assert fresh["art_style"] == "ui-screenshot" and "finish" not in fresh
    assert fresh["labelled"] == ["art_style", "subject"]
    # a second ingest migrates nothing
    _, again = label.ingest({}, d, log=lambda m: None)
    assert again["migrated"] == 0


def test_dropped_value_is_reported_not_kept():
    stats = {"errors": []}
    rec = {"finish": "watercolour"}
    label.migrate_record(rec, stats)
    assert "art_style" not in rec and "finish" not in rec
    assert any("no art_style mapping" in e for e in stats["errors"])


# --- enum pinning -------------------------------------------------------------

def test_finish_is_gone_and_migration_maps_into_the_enum():
    assert "finish" not in attrs.FIELDS and "art_style" in attrs.FIELDS
    assert "art_style" in sheets.SEMANTIC and "finish" not in sheets.SEMANTIC
    mapped = set(label.RENAMED["finish"][1].values())
    assert mapped <= set(attrs.ENUMS["art_style"]), "every migrated value is a real art_style"


# --- Part D: composition_of / device_of and the rule edits (layered overhaul) ---

def test_family_rule_edits_use_the_new_fields():
    # rule 6: a compare card measured as `split` with model-logo + pill is vs-two-up
    assert taxonomy.family_of({"chrome": ["model-logo", "pill"], "layout": "split",
                               "type": "feature-callout", "ground": "photo-full-bleed"})[0] == "vs-two-up"
    # but not on a link-grid (those are model cards / thumbnails)
    assert taxonomy.family_of({"chrome": ["model-logo", "pill"], "layout": "split",
                               "type": "link-grid", "ground": "white"})[0] != "vs-two-up"
    # rule 11b: a labelled beside tile on a flat single card is dark-composite...
    assert taxonomy.family_of({"chrome": ["tile"], "chrome_items": [{"kind": "tile", "placement": "beside"}],
                               "layout": "single", "ground": "black", "panel_count": 1, "type": "feature-callout"})[0] == "dark-composite"
    # ...but a bare `tile` in the bag with no labelled placement does not over-fire
    assert taxonomy.family_of({"chrome": ["tile"], "layout": "single", "ground": "black",
                               "panel_count": 1, "type": "feature-callout"})[0] != "dark-composite"
    # the late rule: a headline card on a flat ground with no tool chrome is template-mockup
    assert taxonomy.family_of({"chrome": [], "chrome_items": [], "text_in_image": "headline",
                               "ground": "solid-colour", "ui_mockup": "none", "layout": "single",
                               "type": "gallery", "panel_count": 1})[0] == "template-mockup"
    # a gallery headline card no longer mis-resolves to outcome-tile
    assert taxonomy.family_of({"text_in_image": "headline", "ground": "white", "layout": "stacked",
                               "type": "gallery", "panel_count": 1, "chrome": [], "chrome_items": []})[0] == "template-mockup"


def test_composition_of():
    assert taxonomy.composition_of({})[0] is None
    assert taxonomy.composition_of({"chrome_items": []}) == ("plain", "plain", "derived")
    beside = {"chrome_items": [{"kind": "tile", "placement": "beside"}]}
    assert taxonomy.composition_of(beside) == ("beside", "beside:tile", "derived")
    over = {"chrome_items": [{"kind": "adjust-panel", "placement": "overlay"}]}
    assert taxonomy.composition_of(over)[0] == "overlaid"
    layered = {"labelled": ["chrome_items"], "chrome_items": [
        {"kind": "option-list", "placement": "beside"},
        {"kind": "tile", "placement": "beside", "count": 2},
        {"kind": "chip", "placement": "overlay"}]}
    comp, key, source = taxonomy.composition_of(layered)
    assert comp == "layered" and key == "beside:option-list+tile*2/overlay:chip" and source == "labelled"


def test_device_of():
    assert taxonomy.device_of({"chrome_items": [
        {"kind": "option-list", "placement": "beside", "state": {"active": 1}}]}) == "model-picker"
    assert taxonomy.device_of({"panel_count": 3, "chrome_items": [
        {"kind": "tile", "placement": "beside"}]}) == "reference-thumbs"
    assert taxonomy.device_of({"panel_count": 2, "chrome_items": []}) == "two-up"
    assert taxonomy.device_of({"art_style": "photo", "ui_mockup": "none", "chrome_items": [
        {"kind": "mockup-card", "placement": "beside"}]}) == "applied-mockup"
    assert taxonomy.device_of({}) == "none"
