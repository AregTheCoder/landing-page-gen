"""The composition plan: keep-clear regions from a preset, plan validation,
and the plan -> compose-spec step."""

import copy

import pytest
import yaml
from PIL import Image

from landing_page_gen.compose import cli, families, plan


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


def test_keep_clear_skips_chrome_under_the_panel_and_chrome_that_frames_the_subject():
    # template-mockup's card sits UNDER the photo (card layer): it hides nothing, so the
    # worker must not be told to keep the subject out of the whole panel (it used to be)
    assert plan.keep_clear("template-mockup") == {}
    assert plan.keep_clear("template-mockup", "palette-card") == {}
    # brackets, the crop grid and a selection box mark where the subject GOES
    assert plan.keep_clear("crop-frame") == {}
    assert plan.keep_clear("template-mockup", "selection-frame") == {}
    sel = plan.keep_clear("cutout-checkerboard", "selection-frame")
    assert {r["item"] for rs in sel.values() for r in rs} == {"badge-a", "badge-b"}, "the check badges still cover a corner"
    grid = plan.keep_clear("crop-frame", "crop-grid")
    items = {r["item"] for rs in grid.values() for r in rs}
    assert "grid" not in items and {"crop-badge", "ratio"} <= items, "badge and ratio label sit over the panels"


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


def test_validate_refuses_a_size_no_layout_fits(tmp_path):
    # a 342x282 before-after slot fits neither the 21:10 card nor the 1:1 stack: the plan
    # used to pass, the worker paid for the panels, and lp-compose exited at render
    p = plan.build("before-after", "342x282", slot="S07-m1")
    assert any("342x282" in e and "no before-after layout fits it" in e for e in plan.validate(p))
    (tmp_path / "s.yaml").write_text(yaml.safe_dump(plan.to_spec(p, {})))
    with pytest.raises(SystemExit, match="342x282"):
        cli.load_spec(tmp_path / "s.yaml")
    # a preset named for the wrong shape says which layout does fit
    wrong = plan.build("before-after", "720x343", preset="stacked-square", slot="S07-m1")
    assert any("the default fits it" in e for e in plan.validate(wrong))


def test_labels_fill_the_preset_slots_in_order_and_never_touch_the_template(tmp_path):
    before = copy.deepcopy(families.FAMILIES)
    p = plan.build("panel-overlay", "480x360", labels=["Curves", "Shadows", "Midtones", "Highlights"])
    items = {it["id"]: it for it in p["items"]}
    assert items["panel"]["title"] == items["tool-pill"]["text"] == "Curves", "the tool pill repeats the tool name"
    assert [s[0] for s in items["panel"]["sliders"]] == ["Shadows", "Midtones", "Highlights"]
    assert p["labels"] == ["Curves", "Shadows", "Midtones", "Highlights"] and plan.validate(p) == []
    short = {it["id"]: it for it in plan.build("panel-overlay", "480x360", labels=["Curves"])["items"]}
    assert [s[0] for s in short["panel"]["sliders"]] == ["Hue", "Saturation", "Lightness"], "a slot left off keeps the template's"
    swatch = next(it for it in plan.build("template-mockup", "800x800", preset="palette-card",
                                          labels=["#e01ee0", "#000000", "white", "#f5d90a"])["items"] if it["id"] == "swatch")
    assert swatch["colours"] == ["#e01ee0", "#000000", "white", "#f5d90a"], "the colours slot takes every remaining string"
    assert families.FAMILIES == before, "the family template is never written through"
    # the labelled plan renders
    Image.new("RGB", (400, 300), "red").save(tmp_path / "p.png")
    (tmp_path / "s.yaml").write_text(yaml.safe_dump(plan.to_spec(p, {"photo": "p.png"})))
    _, drawn = cli.compose(cli.resolve(cli.load_spec(tmp_path / "s.yaml")))
    assert {"panel", "tool-pill"} <= set(drawn)


def test_validate_refuses_labels_the_layout_cannot_draw():
    two = plan.build("dark-composite", "720x720", preset="model-picker", labels=["Seedance 2.5", "Kling"])
    assert any("draws 1 page string(s) (active row)" in e for e in plan.validate(two))
    assert any("must be none" in e for e in plan.validate(plan.build("dark-composite", "720x720", labels=["4K"])))


def test_every_text_field_a_preset_draws_is_a_label_slot():
    # a text field with no `> chrome:` slot is a placeholder no skeleton line can change
    # (crop-frame's bracket label was one); a slot naming a field that is gone fills nothing
    for fam, f in families.FAMILIES.items():
        for preset in (None, *(f.get("variants") or {})):
            drawn = set()
            for it in cli.template(fam, preset)["chrome"]:
                drawn |= {f"{it['id']}.{k}" for k in ("text", "label", "title", "active_text", "colours") if k in it}
                drawn |= {f"{it['id']}.sliders.{i}" for i in range(len(it.get("sliders") or []))}
            assert drawn == {t for _, ts in families.LABELS.get((fam, preset), []) for t in ts}, (fam, preset)


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
    # a 1:1 size picks the before-after variant it fits, as plan.build does (it used to exit)
    assert cli.main(["--keepclear", "before-after", "480x480"]) == 0
    assert "after-pill" in capsys.readouterr().out


@pytest.mark.parametrize("ground", ["colour", "mixed", "gradient", "checker"])
def test_a_ground_variant_compose_cannot_draw_falls_back_to_the_family_ground(tmp_path, ground):
    # a slot styled template-mockup/colour used to reach lp-compose as ground: colour and exit
    # AFTER the panels were generated; the plan keeps the variant on record and draws the default
    p = plan.build("template-mockup", "480x480", ground=ground, slot="S01-m1")
    assert "ground" not in p and p["ground_variant"] == ground and plan.validate(p) == []
    Image.new("RGB", (400, 400), "red").save(tmp_path / "p.png")
    (tmp_path / "s.yaml").write_text(yaml.safe_dump(plan.to_spec(p, {"photo": "p.png"})))
    cli.compose(cli.resolve(cli.load_spec(tmp_path / "s.yaml")))
    assert plan.build("template-mockup", "480x480", ground="black")["ground"] == "black", "a drawable word passes through"
    assert any("cannot be drawn" in e for e in plan.validate({"family": "template-mockup", "ground": ground})), \
        "a hand-written undrawable ground is caught before any credit is spent"


def test_validate_rejects_a_colour_the_renderer_cannot_draw():
    ok = {"family": "template-mockup", "preset": "palette-card",
          "items": [{"id": "swatch", "kind": "swatch", "colours": ["#e01ee0", "black", [242, 242, 244], [1, 2, 3, 255]]}]}
    assert plan.validate(ok) == []
    bad = {"family": "template-mockup", "items": [{"id": "swatch", "kind": "swatch", "colours": ["#e01ee0", "not-a-colour"]}]}
    assert any("not-a-colour" in e for e in plan.validate(bad))


def test_hex_swatch_colours_and_a_moved_selection_box_render(tmp_path):
    # the manager may write hex colours and move an anchored selection box by rect in the plan
    for fam, preset, over in (("template-mockup", "palette-card", {"id": "swatch", "colours": ["#e01ee0", "#000000"]}),
                              ("cutout-checkerboard", "selection-frame", {"id": "select", "rect": [40, 40, 300, 300]})):
        p = plan.build(fam, "800x800", preset=preset, slot="S01-m1")
        for it in p["items"]:
            if it["id"] == over["id"]:
                it.update(over)
        assert plan.validate(p) == []
        steps = tmp_path / fam / "steps"
        steps.mkdir(parents=True)
        images = {}
        for panel in p["panels"]:
            Image.new("RGB", (400, 400), "red").save(steps / f"{panel['panel']}.png")
            images[panel["panel"]] = f"steps/{panel['panel']}.png"
        spec = plan.to_spec(p, images)
        path = tmp_path / fam / "s.yaml"
        path.write_text(yaml.safe_dump(spec))
        _, drawn = cli.compose(cli.resolve(cli.load_spec(path)))
        if over["id"] == "select":
            x0, y0, x1, y1 = drawn["select"]
            assert (round(x0), round(y0)) == (20, 20), "an explicit rect wins over the template's panel anchor"


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
