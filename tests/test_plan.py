"""The composition plan: keep-clear regions from a preset, the slots and
their candidate blocks, plan validation, and the plan + picks -> compose-spec
step."""

import copy

import pytest
import yaml
from PIL import Image

from landing_page_gen.compose import bank, cli, families, plan, roles


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


def _picks(**fills):
    return {"fills": [{"slot": k, **v, "because": v.get("because", "a test")} for k, v in fills.items()]}


def _images(tmp_path, p, colour="red"):
    steps = tmp_path / "steps"
    steps.mkdir(parents=True, exist_ok=True)
    out = {}
    for panel in plan.generated_panels(p):
        Image.new("RGB", (400, 400), colour).save(steps / f"{panel}.png")
        out[panel] = f"steps/{panel}.png"
    return out


def _render(tmp_path, p, picks, images=None):
    images = images or _images(tmp_path, p)
    (tmp_path / "s.yaml").write_text(yaml.safe_dump(plan.to_spec(p, images, picks), allow_unicode=True))
    return cli.compose(cli.resolve(cli.load_spec(tmp_path / "s.yaml")))


HSL = roles.facts_for("hsl-color", "Adjust the hue, saturation and lightness of any colour: Curves, Shadows, "
                      "Midtones, Highlights", generator="GPT Image 2.5 Sunburst")


def test_validate_catches_bad_family_preset_and_plan_items():
    assert plan.validate({"family": "prompt-card"}) == []
    assert any("not a compose family" in p for p in plan.validate({"family": "nope"}))
    assert any("no preset" in p for p in plan.validate({"family": "dark-composite", "preset": "ghost"}))
    bad = plan.validate({"family": "prompt-card", "items": [{"id": "x", "kind": "tile"}]})
    assert any("comes from a bank block" in p for p in bad), "a plan carries no compose chrome of its own"
    dup = plan.validate({"family": "prompt-card", "items": [
        {"id": "a", "kind": "brush-mask", "rendered_by": "model", "reason": "r"},
        {"id": "a", "kind": "face-box", "rendered_by": "model", "reason": "r"}]})
    assert any("repeated" in p for p in dup)
    assert any("not a slot" in p for p in plan.validate({"family": "prompt-card", "slots": [{"id": "ghost"}]}))


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


def test_a_plan_is_a_skeleton_its_slots_carry_candidates_not_chrome():
    before = copy.deepcopy(families.FAMILIES)
    p = plan.build("panel-overlay", "480x360", facts=HSL, slot="S03-m1")
    assert "items" not in p and [s["id"] for s in p["slots"]] == ["panel"]
    slot = p["slots"][0]
    assert slot == {**slot, "shape": "panel", "accepts": ["tool"], "required": True}
    assert [c["block"] for c in slot["candidates"]] == ["adjust-panel"] and slot["candidates"][0]["give"] == ["title", "sliders"]
    assert plan.validate(p) == []
    picks = _picks(panel={"block": "adjust-panel", "title": "Curves",
                          "sliders": [["Shadows", 10], ["Midtones", -4], ["Highlights", 22]]})
    assert plan.check_blocks(p, picks) == []
    assert families.FAMILIES == before, "the family template is never written through"


def test_picks_render_and_the_worker_supplies_every_string(tmp_path):
    p = plan.build("panel-overlay", "480x360", facts=HSL, slot="S03-m1")
    picks = _picks(panel={"block": "adjust-panel", "title": "Curves",
                          "sliders": [["Shadows", 10], ["Midtones", -4], ["Highlights", 22]]})
    _, drawn = _render(tmp_path, p, picks)
    assert set(drawn) == {"panel"}
    item = plan.picked_items(p, picks)[0]
    assert (item["kind"], item["title"], item["block"], item["category"]) == ("adjust-panel", "Curves", "adjust-panel", "tool")
    assert item["rect"] == (680, 300, 1490, 900), "the slot's geometry, the block's content"
    missing = plan.check_blocks(p, _picks(panel={"block": "adjust-panel", "sliders": [["Hue", 1]]}))
    assert any("needs `title:`" in e for e in missing)
    made_up = plan.check_blocks(p, _picks(panel={"block": "adjust-panel", "title": "Vibrance", "sliders": [["Hue", 1]]}))
    assert any("'Vibrance'" in e and "never makes" in e for e in made_up), "a string comes from the copy"


def test_a_pick_must_be_the_slots_category_and_shape_and_say_why():
    p = plan.build("dark-composite", "720x720", facts=roles.facts_for("ai-image-enhancer", "Enhance photos",
                                                                      generator="GPT Image 2.5 Sunburst"))
    wrong = plan.check_blocks(p, _picks(**{"tile-1": {"block": "cta-button", "text": "Enhance"}}))
    assert any("is an action block; the slot takes" in e for e in wrong)
    shape = plan.check_blocks(p, _picks(**{"tile-1": {"block": "model-picker"}}))
    assert any("cannot draw in a tile" in e for e in shape)
    ghost = plan.check_blocks(p, _picks(ghost={"block": "palette"}))
    assert any("ghost: not a slot" in e for e in ghost)
    silent = plan.check_blocks(p, {"fills": [{"slot": "tile-1", "block": "generator-mark"}]})
    assert any("`because:` is missing" in e for e in silent)
    empty = plan.check_blocks(p, _picks(**{"tile-1": {"block": "generator-mark"}}))
    assert any("tile-2: a required slot" in e for e in empty) and any("tile-3: a required slot" in e for e in empty)
    twice = plan.check_blocks(p, _picks(**{"tile-1": {"block": "palette"}, "tile-2": {"block": "palette"},
                                           "tile-3": {"block": "generator-mark"}}))
    assert any("the same block as tile-1" in e for e in twice), "a composition says each thing once"
    ok = plan.check_blocks(p, _picks(**{"tile-1": {"block": "generator-mark"}, "tile-2": {"block": "tool-tile", "tool": "enhance"},
                                        "tile-3": {"block": "palette"}}))
    assert ok == []


def test_every_slot_can_take_some_block_and_every_exemplar_obeys_the_slot():
    """A slot no block of the bank can draw in is dead; an exemplar that breaks
    its slot's category or shape would make the golden render a lie."""
    blocks = bank.vocab()["blocks"]
    for fam, f in families.FAMILIES.items():
        for preset in families.layout_names(fam):
            t = cli.template(fam, preset)
            for sl in t["slots"]:
                assert any(b["category"] in sl["accepts"] and sl["shape"] in b["draw"] for b in blocks.values()), (fam, preset, sl["id"])
            ex = t["exemplar"]["fills"]
            assert set(ex) <= {s["id"] for s in t["slots"]}, (fam, preset)
            for sl in t["slots"]:
                if sl["id"] in ex:
                    b = blocks[ex[sl["id"]]["block"]]
                    assert b["category"] in sl["accepts"] and sl["shape"] in b["draw"], (fam, preset, sl["id"])
                else:
                    assert not sl.get("required"), (fam, preset, sl["id"], "a required slot the original filled")


def test_panel_overlay_cards_take_the_panel_and_the_hero_the_pill_never_both():
    # the template used to draw both, and the pill covered the panel's first slider row;
    # no corpus slot shows both: the hero carries the pill, the cards the panel
    card = plan.build("panel-overlay", "541x406", slot="S03-m1", section="use-case-grid")
    hero = plan.build("panel-overlay", "800x600", slot="S01-m1", section="hero")
    assert "preset" not in card and [s["id"] for s in card["slots"]] == ["panel"]
    assert hero["preset"] == "hero" and [s["id"] for s in hero["slots"]] == ["tool-pill"]
    assert {r["item"] for r in card["panels"][0]["keep_clear"]} == {"panel"}, "keep-clear follows the slot"
    assert {r["item"] for r in hero["panels"][0]["keep_clear"]} == {"tool-pill"}
    assert plan.build("dark-composite", "480x480", preset="model-picker", section="hero")["preset"] == "model-picker", \
        "the device still wins over the section"


def test_to_spec_is_the_picked_blocks_plus_images():
    p = plan.build("dark-composite", "720x720", preset="model-picker", slot="S07-m1",
                   facts=roles.facts_for("ai-image-generator", "Pick a model", generator="GPT Image 2.5 Sunburst"))
    spec = plan.to_spec(p, {"photo": "steps/S07-m1-1.png", "thumb-a": "steps/a.png"},
                        _picks(list={"block": "model-picker"}))
    assert spec["family"] == "dark-composite" and spec["preset"] == "model-picker" and spec["size"] == "720x720"
    assert spec["panels"] == {"photo": {"image": "steps/S07-m1-1.png", "anchor": "subject"},
                              "thumb-a": {"image": "steps/a.png", "anchor": "subject"}}  # scenes crop on their subject
    [item] = spec["chrome"]
    assert (item["id"], item["kind"], item["active_text"]) == ("list", "list-panel", "GPT Image 2.5 Sunburst")
    assert len(item["rows_text"]) == 3, "the picker's other rows come from the catalogue"
    assert plan.to_spec(p, {})["chrome"] == [], "no picks, no chrome"


def test_validate_hybrid_rule():
    base = {"family": "template-mockup"}
    ok = {**base, "items": [{"id": "mark", "kind": "applied-mockup", "rendered_by": "model",
                             "reason": "the page mark on the tote is bespoke"}]}
    assert plan.validate(ok) == []
    on_compose = {**base, "items": [{"id": "t", "kind": "tile", "rendered_by": "model", "reason": "x"}]}
    assert any("cannot be rendered_by: model" in p for p in plan.validate(on_compose))
    no_reason = {**base, "items": [{"id": "m", "kind": "face-box", "rendered_by": "model"}]}
    assert any("needs a reason" in p for p in plan.validate(no_reason))
    with_text = {**base, "items": [{"id": "m", "kind": "brush-mask", "rendered_by": "model",
                                    "reason": "organic", "text": "erase"}]}
    assert any("carries no text" in p for p in plan.validate(with_text))


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


def test_hex_swatch_colours_and_a_moved_selection_box_render(tmp_path):
    # a palette may take `> chrome:` hex colours; the manager may move a slot by rect in the plan
    facts = roles.facts_for("card-maker", "Design a card", labels=["#e01ee0", "#000000"], generator="Nano Banana Pro")
    p = plan.build("template-mockup", "800x800", preset="palette-card", slot="S01-m1", facts=facts)
    picks = _picks(swatch={"block": "palette", "colours": ["#e01ee0", "#000000"]},
                   **{"tile-accent": {"block": "maker-glyph"}, "tile-tool": {"block": "generator-mark"}})
    assert plan.check_blocks(p, picks) == []
    assert plan.picked_items(p, picks)[0]["colours"] == ["#e01ee0", "#000000"]
    _render(tmp_path / "a", p, picks)
    q = plan.build("cutout-checkerboard", "800x800", preset="selection-frame", slot="S01-m1")
    next(s for s in q["slots"] if s["id"] == "select")["rect"] = [40, 40, 300, 300]
    fills = cli.template("cutout-checkerboard", "selection-frame")["exemplar"]["fills"]
    _, drawn = _render(tmp_path / "b", q, {"fills": fills})
    x0, y0, x1, y1 = drawn["select"]
    assert (round(x0), round(y0)) == (20, 20), "an explicit rect wins over the template's panel anchor"


def test_build_then_spec_from_plan_round_trips(tmp_path):
    facts = roles.facts_for("ai-image-generator", "Choose the model", generator="GPT Image 2.5 Sunburst")
    p = plan.build("dark-composite", "720x720", preset="model-picker", slot="S07-m1", facts=facts,
                   derived_from={"style": "dark-composite", "device": "model-picker"})
    assert p["family"] == "dark-composite" and p["preset"] == "model-picker" and p["size"] == "720x720"
    assert {panel["panel"] for panel in p["panels"]} == {"photo", "thumb-a", "thumb-b"}
    assert p["derived_from"]["device"] == "model-picker" and plan.validate(p) == []
    plan.write_plan(tmp_path / "plan.yaml", p)
    (tmp_path / "blocks.yaml").write_text(yaml.safe_dump(_picks(list={"block": "model-picker"})))
    steps = tmp_path / "steps"
    steps.mkdir()
    for n in ("photo", "thumb-a", "thumb-b"):
        Image.new("RGB", (400, 400), "red").save(steps / f"{n}.png")
    out_spec = tmp_path / "compose-S07-m1.yaml"
    args = [f"--image={n}=steps/{n}.png" for n in ("photo", "thumb-a", "thumb-b")]
    with pytest.raises(SystemExit, match="pass --blocks"):
        cli.main(["--spec-from-plan", str(tmp_path / "plan.yaml"), "--out", str(out_spec), *args])
    assert cli.main(["--spec-from-plan", str(tmp_path / "plan.yaml"), "--blocks", str(tmp_path / "blocks.yaml"),
                     "--out", str(out_spec), *args]) == 0
    assert yaml.safe_load(out_spec.read_text())["blocks"] == "blocks.yaml"
    made = yaml.safe_load((tmp_path / "made-by.yaml").read_text())
    assert made["S07-m1"]["photo"]["model"] == "gpt-image-2.5-sunburst", "the picker's tick binds the picture's model"
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
    fills = cli.template("before-after", preset)["exemplar"]["fills"]
    _, _ = _render(tmp_path, p, {"fills": fills})
    out = tmp_path / "out.png"
    assert cli.main([str(tmp_path / "s.yaml"), "--out", str(out)]) == 0
    assert Image.open(out).size == tuple(int(v) for v in size.split("x"))


def test_a_picker_names_the_generating_model_among_same_kind_peers_and_is_never_blank():
    facts = roles.facts_for("ai-image-generator", "Choose", labels=["Veo 3.1"], generator="GPT Image 2.5 Sunburst")
    p = plan.build("dark-composite", "720x720", preset="model-picker", facts=facts)
    [item] = plan.picked_items(p, _picks(list={"block": "model-picker"}))
    assert item["active_text"] == "GPT Image 2.5 Sunburst" and len(item["rows_text"]) == 3
    assert not any(r.startswith("GPT") for r in item["rows_text"]), "peers from other makers"
    video = plan.picked_items(p, _picks(list={"block": "model-picker", "active": "Veo 3.1"}))[0]
    assert "Sora 2" in video["rows_text"], "a video model's peers are video models"
    assert plan.check_blocks(p, _picks(list={"block": "model-picker", "active": "Veo 3.1"})) == [], \
        "a model `> chrome:` names may be ticked (made-by then binds it)"
    stray = plan.check_blocks(p, _picks(list={"block": "model-picker", "active": "Flux 2 Pro"}))
    assert any("neither makes the picture nor is a model the page presents" in e for e in stray)


def test_blank_chrome_is_refused_and_derived_chrome_renders_from_the_panel(tmp_path):
    tile = {"id": "t", "kind": "tile", "rect": [0, 0, 10, 10]}
    assert plan.blank_chrome(tile) and not plan.blank_chrome({**tile, "icon": "crop"})
    assert plan.blank_chrome({"id": "p", "kind": "profile-card", "rect": [0, 0, 10, 10], "name": "a", "caption": "b"})
    facts = roles.facts_for("brand-kit-generator", "Your brand palette", generator="Nano Banana Pro")
    p = plan.build("template-mockup", "720x720", facts=facts)
    ghost = plan.check_blocks(p, _picks(**{"tile-1": {"block": "maker-glyph"}, "tile-2": {"block": "generator-mark"},
                                           "swatch": {"block": "palette", "colours": {"from": "ghost"}}}))
    assert any("from panel 'ghost'" in e for e in ghost)
    im = Image.new("RGB", (400, 400), (230, 40, 40))
    im.paste((20, 60, 200), (0, 0, 200, 400))
    (tmp_path / "steps").mkdir()
    im.save(tmp_path / "steps" / "photo.png")
    picks = _picks(**{"tile-1": {"block": "maker-glyph"}, "tile-2": {"block": "generator-mark"}, "swatch": {"block": "palette"}})
    assert plan.check_blocks(p, picks) == []
    (tmp_path / "s.yaml").write_text(yaml.safe_dump(plan.to_spec(p, {"photo": "steps/photo.png"}, picks)))
    layout = cli.resolve(cli.load_spec(tmp_path / "s.yaml"))
    swatch = next(it for it in layout["chrome"] if it["id"] == "swatch")
    assert {tuple(c) for c in swatch["colours"]} >= {(230, 40, 40), (20, 60, 200)}


def test_a_measured_compare_card_derives_its_before_from_the_after():
    """m-56db0c is one photo split by a seam: the panel under the seam's After
    is its twin, so it is the After degraded, never a second generation, and the
    compare handle fits the seam (blind-1-3 was blocked on two separate photos)."""
    p = plan.build("before-after", "728x582", preset="m-56db0c", facts={"page": "remove-object-from-photo", "degrade": "pixelate"})
    by = {x["panel"]: x for x in p["panels"]}
    assert by["photo"]["from"] == "photo-2" and by["photo"]["degrade"] == "pixelate"
    assert plan.generated_panels(p) == ["photo-2"]
    assert {"block": "compare-handle"} in p["slots"][0]["candidates"]
    assert plan.build("before-after", "728x582", preset="m-56db0c")["panels"][0]["degrade"] == "blur", "no fault named: blur"
