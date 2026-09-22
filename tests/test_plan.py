"""The composition plan: keep-clear regions from a preset, plan validation,
and the plan -> compose-spec step."""

import pytest
from PIL import Image

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


def test_validate_hybrid_rule():
    base = {"family": "template-mockup"}
    # a well-formed hybrid item: a MODEL_KIND, rendered_by model, with a reason, no text
    ok = {**base, "items": [{"id": "mark", "kind": "applied-mockup", "rendered_by": "model",
                             "reason": "the page mark on the tote is bespoke"}]}
    assert plan.validate(ok) == []
    # rendered_by: model on a compose-able kind is refused
    on_compose = {**base, "items": [{"id": "t", "kind": "tile", "rendered_by": "model", "reason": "x"}]}
    assert any("cannot be rendered_by: model" in p for p in plan.validate(on_compose))
    # a MODEL_KIND left as compose is refused (it must be model-rendered)
    as_compose = {**base, "items": [{"id": "m", "kind": "brush-mask"}]}
    assert any("hybrid-only" in p for p in plan.validate(as_compose))
    # a model item needs a reason and carries no text
    no_reason = {**base, "items": [{"id": "m", "kind": "face-box", "rendered_by": "model"}]}
    assert any("needs a reason" in p for p in plan.validate(no_reason))
    with_text = {**base, "items": [{"id": "m", "kind": "brush-mask", "rendered_by": "model",
                                    "reason": "organic", "text": "erase"}]}
    assert any("carries no text" in p for p in plan.validate(with_text))


def test_to_spec_drops_model_rendered_items():
    p = {"slot": "S05-m1", "family": "template-mockup", "size": "720x720",
         "items": [{"id": "card", "kind": "card"},
                   {"id": "mark", "kind": "applied-mockup", "rendered_by": "model", "reason": "bespoke mark"}]}
    spec = plan.to_spec(p, {"photo": "steps/p.png"})
    # the composed chrome keeps the card; the model item is painted by the worker's node, not compose
    assert spec["chrome"] == [{"id": "card", "kind": "card"}]


def test_keepclear_cli(capsys):
    assert cli.main(["--keepclear", "panel-overlay"]) == 0
    assert "panel" in capsys.readouterr().out


def test_build_then_spec_from_plan_round_trips(tmp_path):
    p = plan.build("dark-composite", "720x720", preset="model-picker",
                   slot="S07-m1", derived_from={"style": "dark-composite", "device": "model-picker"})
    assert p["family"] == "dark-composite" and p["preset"] == "model-picker" and p["size"] == "720x720"
    assert {panel["panel"] for panel in p["panels"]} == {"photo", "thumb-a", "thumb-b"}
    assert p["derived_from"]["device"] == "model-picker" and plan.validate(p) == []
    # the plan renders through spec-from-plan + the compose CLI
    plan.write_plan(tmp_path / "plan.yaml", p)
    steps = tmp_path / "steps"
    steps.mkdir()
    for n in ("photo", "thumb-a", "thumb-b"):
        Image.new("RGB", (400, 400), "red").save(steps / f"{n}.png")
    out_spec = tmp_path / "compose-S07-m1.yaml"
    assert cli.main(["--spec-from-plan", str(tmp_path / "plan.yaml"), "--out", str(out_spec)]
                    + [f"--image={n}=steps/{n}.png" for n in ("photo", "thumb-a", "thumb-b")]) == 0
    png = tmp_path / "out.png"
    assert cli.main([str(out_spec), "--out", str(png)]) == 0 and png.exists()


@pytest.mark.parametrize("size,preset,panels", [
    ("480x480", "stacked-square", {"before", "after", "result"}),  # 1:1 slot: the default's 21:10 does not fit
    ("720x343", None, {"before", "result"}),                      # 21:10 slot: the default wide card
])
def test_slot_size_selects_the_variant_whose_aspect_fits(tmp_path, size, preset, panels):
    """The brief's `> device:` picks a preset; with none, a slot whose size the
    family default cannot render falls to the variant that can — so a 1:1
    before-after slot composes as `stacked-square`, not a rejected 21:10 card."""
    assert cli.preset_for_size("before-after", size) == preset
    assert cli.preset_for_size("before-after", size, "stacked-square") == "stacked-square", "an explicit preset wins"
    p = plan.build("before-after", size, slot="S07-m1")
    assert p.get("preset") == preset and {x["panel"] for x in p["panels"]} == panels
    assert plan.validate(p) == []
    plan.write_plan(tmp_path / "plan.yaml", p)
    (tmp_path / "steps").mkdir()
    for n in panels:
        Image.new("RGB", (400, 400), "red").save(tmp_path / "steps" / f"{n}.png")
    spec = tmp_path / "compose-S07-m1.yaml"
    assert cli.main(["--spec-from-plan", str(tmp_path / "plan.yaml"), "--out", str(spec)]
                    + [f"--image={n}=steps/{n}.png" for n in sorted(panels)]) == 0
    png = tmp_path / "out.png"
    assert cli.main([str(spec), "--out", str(png)]) == 0
    assert Image.open(png).size == tuple(int(v) for v in size.split("x"))
