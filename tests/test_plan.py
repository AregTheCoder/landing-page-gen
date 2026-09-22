"""The composition plan: keep-clear regions from a preset, plan validation,
and the plan -> compose-spec step."""

import pytest

from landing_page_gen.compose import cli, plan


def test_keep_clear_reports_overlay_regions_only():
    # panel-overlay: the adjust panel (and tool pill) sit over the photo, so the
    # worker must leave that region as backdrop
    kc = plan.keep_clear("panel-overlay")
    assert "photo" in kc
    items = {r["item"] for r in kc["photo"]}
    assert "panel" in items
    panel = next(r for r in kc["photo"] if r["item"] == "panel")
    assert panel["rect"] == [680, 300, 1490, 900], "the exact region layered-1 hand-transcribed"
    assert all(0 <= v <= 1 for v in panel["frac"])
    # beside-chrome families have nothing over the panel
    assert plan.keep_clear("dark-composite") == {}
    assert plan.keep_clear("prompt-card") == {}


def test_keep_clear_scales_with_size():
    small = plan.keep_clear("panel-overlay", size=(800, 600))
    r = next(x for x in small["photo"] if x["item"] == "panel")
    assert r["rect"] == [340, 150, 745, 450], "half the REF size -> half the pixels"


def test_validate_catches_bad_family_preset_and_kind():
    assert plan.validate({"family": "prompt-card"}) == []
    assert any("not a compose family" in p for p in plan.validate({"family": "nope"}))
    assert any("no preset" in p for p in plan.validate({"family": "dark-composite", "preset": "ghost"}))
    bad = plan.validate({"family": "prompt-card", "items": [{"id": "x", "kind": "telephone"}]})
    assert any("not drawable" in p for p in bad)
    dup = plan.validate({"family": "prompt-card", "items": [{"id": "a", "kind": "tile"}, {"id": "a", "kind": "chip"}]})
    assert any("repeated" in p for p in dup)


def test_to_spec_carries_the_plan_verbatim_plus_images():
    p = {"slot": "S07-m1", "family": "dark-composite", "preset": "model-picker", "size": "720x720",
         "items": [{"id": "list", "active_text": "Seedance 2.5"}], "omit": ["tile-3"]}
    spec = plan.to_spec(p, {"photo": "steps/S07-m1-1.png", "thumb-a": "steps/a.png"})
    assert spec["family"] == "dark-composite" and spec["preset"] == "model-picker" and spec["size"] == "720x720"
    assert spec["panels"] == {"photo": {"image": "steps/S07-m1-1.png"}, "thumb-a": {"image": "steps/a.png"}}
    assert spec["chrome"] == [{"id": "list", "active_text": "Seedance 2.5"}] and spec["omit"] == ["tile-3"]


def test_keepclear_cli(capsys):
    assert cli.main(["--keepclear", "panel-overlay"]) == 0
    assert "panel" in capsys.readouterr().out
