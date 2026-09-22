"""lp-compose: a style-family template plus the worker's panel PNGs becomes
the composite card. Solid-colour fixture panels make the geometry checkable."""

import pytest
import yaml
from PIL import Image

from landing_page_gen.compose import cli, draw, layout
from landing_page_gen.compose.families import FAMILIES, RATIOS, nearest_ratio


def write_spec(tmp_path, family="before-after", size="720x720", **extra):
    steps = tmp_path / "steps"
    steps.mkdir(exist_ok=True)
    Image.new("RGB", (400, 800), "red").save(steps / "a.png")
    Image.new("RGB", (400, 800), "blue").save(steps / "b.png")
    panels = {name: {"image": f"steps/{'ab'[i % 2]}.png"} for i, name in enumerate(FAMILIES[family]["panels"])}
    path = tmp_path / "compose.yaml"
    path.write_text(yaml.safe_dump({"slot": "S07-m1", "family": family, "size": size, "panels": panels, **extra}))
    return path


def rewrite(path, **changes):
    spec = yaml.safe_load(path.read_text())
    spec.update(changes)
    path.write_text(yaml.safe_dump(spec))
    return path


def out_rect(layout, name):
    return tuple(v / cli.SS for v in layout["panels"][name]["rect"])


def test_compose_before_after_geometry_ground_and_pill(tmp_path):
    spec = write_spec(tmp_path)
    out = tmp_path / "steps" / "S07-m1-3-1.png"
    assert cli.main([str(spec), "--out", str(out)]) == 0
    im = Image.open(out)
    assert im.size == (720, 720) and im.mode == "RGBA"
    layout = cli.resolve(cli.load_spec(spec))
    _, drawn = cli.compose(layout)

    def centre(name):
        x0, y0, x1, y1 = out_rect(layout, name)
        return im.getpixel((int((x0 + x1) / 2), int((y0 + y1) / 2)))[:3]
    assert centre("before") == (255, 0, 0) and centre("after") == (0, 0, 255) and centre("result") == (255, 0, 0)
    assert im.getpixel((1, 1))[3] == 0, "transparent ground shows through the rounded corner (the page supplies it)"
    x0, y0, x1, y1 = (int(v) for v in drawn["before-pill"])
    bx0, by0, bx1, by1 = out_rect(layout, "before")
    assert bx0 < x0 < x1 < bx1 and by0 < y0 < y1 < by1, "pill sits inside its panel"
    px = [im.getpixel((x, y)) for x in range(x0 + 1, x1 - 1, 2) for y in range(y0 + 1, y1 - 1, 2)]
    assert any(p[0] > 230 and p[1] > 230 and p[2] > 230 for p in px), "white glyphs"
    assert any(60 < p[0] < 200 and p[1] < 60 and p[2] < 60 for p in px), "translucent dark fill over the red panel"
    tx0, ty0, tx1, ty1 = (int(v) for v in drawn["tile"])
    tile = [im.getpixel((x, y)) for x in range(tx0 + 2, tx1 - 2, 3) for y in range(ty0 + 2, ty1 - 2, 3)]
    assert sum(p[:3] == (0, 0, 0) and p[3] > 200 for p in tile) > len(tile) * 0.6 and any(p[0] > 200 for p in tile), "black tile, white icon"


@pytest.mark.parametrize("family", sorted(FAMILIES))
def test_every_family_composes_at_slot_size(tmp_path, family):
    extra = {"chrome": {"headline": {"text": "Pottery classes"}}} if family == "template-mockup" else {}
    fw, fh = FAMILIES[family]["aspect"]
    size = (720, round(720 * fh / fw))
    layout = cli.resolve(cli.load_spec(write_spec(tmp_path, family, size=f"{size[0]}x{size[1]}", **extra)))
    im, drawn = cli.compose(layout)
    assert im.size == size
    assert set(drawn) == {c["id"] for c in FAMILIES[family]["chrome"]}
    if FAMILIES[family]["ground"].get("fill") is None:
        assert im.mode == "RGBA" and im.getpixel((0, 0))[3] == 0, "transparent ground keeps its rounded corners"


def variant_spec(tmp_path, variant, **extra):
    path = write_spec(tmp_path, "dark-composite", variant=variant, **extra)
    spec = yaml.safe_load(path.read_text())
    names = cli.template("dark-composite", variant)["panels"]
    Image.new("RGB", (400, 400), "green").save(tmp_path / "steps" / "c.png")
    spec["panels"] = {name: {"image": f"steps/{'abc'[i % 3]}.png"} for i, name in enumerate(names)}
    path.write_text(yaml.safe_dump(spec))
    return path


def test_dark_composite_device_variants(tmp_path):
    layout = cli.resolve(cli.load_spec(variant_spec(tmp_path, "reference-thumbs")))
    im, drawn = cli.compose(layout)
    assert set(layout["panels"]) == {"photo", "thumb-a", "thumb-b"} and set(drawn) == {"tile-1", "chip"}
    for name, colour in (("photo", (255, 0, 0)), ("thumb-a", (0, 0, 255)), ("thumb-b", (0, 128, 0))):
        x0, y0, x1, y1 = out_rect(layout, name)
        assert im.getpixel((int((x0 + x1) / 2), int((y0 + y1) / 2))) == colour, name
    assert out_rect(layout, "thumb-a")[2] < out_rect(layout, "photo")[0], "thumbnails sit in the left column"
    layout = cli.resolve(cli.load_spec(variant_spec(tmp_path, "model-picker", chrome={"list": {"active_text": "Recraft V4"}})))
    im, drawn = cli.compose(layout)
    assert set(drawn) == {"list"} and set(layout["panels"]) == {"photo", "thumb-a", "thumb-b"}
    x0, y0, x1, y1 = (int(v) for v in drawn["list"])
    px = [im.getpixel((x, y)) for x in range(x0 + 3, x1 - 3, 5) for y in range(y0 + 3, y1 - 3, 5)]
    assert sum(max(p) < 70 for p in px) > len(px) * 0.6, "dark list card"
    assert any(min(p) > 230 for p in px), "a white check, disc or name on the active row"
    layout = cli.resolve(cli.load_spec(variant_spec(tmp_path, "two-up")))
    im, drawn = cli.compose(layout)
    assert set(layout["panels"]) == {"photo", "photo-b"} and set(drawn) == {"tile-1"}
    assert out_rect(layout, "photo")[2] < out_rect(layout, "photo-b")[0]
    assert {nearest_ratio(*(lambda r: (r[2] - r[0], r[3] - r[1]))(p["rect"]))
            for p in cli.template("dark-composite", "reference-thumbs")["panels"].values()} == {"3:4", "1:1"}
    with pytest.raises(SystemExit, match="dark-composite has no variant 'nope'; one of reference-thumbs, model-picker, two-up"):
        cli.load_spec(rewrite(write_spec(tmp_path, "dark-composite"), variant="nope"))
    with pytest.raises(SystemExit, match="panel 'thumb-a' has no image"):
        cli.load_spec(rewrite(write_spec(tmp_path, "dark-composite"), variant="reference-thumbs"))
    with pytest.raises(SystemExit, match="has no variant 'two-up'"):
        cli.load_spec(rewrite(write_spec(tmp_path, "before-after"), variant="two-up"))
    assert cli.main(["--describe", "dark-composite"]) == 0


def test_describe_names_the_variants(capsys):
    cli.main(["--describe", "dark-composite"])
    out = capsys.readouterr().out
    assert "variant reference-thumbs" in out and "panel thumb-a" in out and "list (list-panel, text)" in out
    assert "variant two-up" in out and "panel photo-b" in out and "generate at 9:16" in out


def test_omit_and_override(tmp_path):
    spec = write_spec(tmp_path, omit=["tile"], chrome={"before-pill": {"text": "Original", "style": "solid-light"}})
    _, drawn = cli.compose(cli.resolve(cli.load_spec(spec)))
    assert "tile" not in drawn and "before-pill" in drawn


def test_fit_cover_anchor_and_contain():
    im = Image.new("RGB", (200, 100), "red")
    im.paste("blue", (100, 0, 200, 100))
    assert draw.fit(im, (100, 100), "cover", "left").getpixel((50, 50))[:3] == (255, 0, 0)
    assert draw.fit(im, (100, 100), "cover", "right").getpixel((50, 50))[:3] == (0, 0, 255)
    c = draw.fit(im, (100, 100), "contain")
    assert c.getpixel((50, 10))[3] == 0 and c.getpixel((25, 50))[:3] == (255, 0, 0)


def test_describe_lists_panels_and_generate_ratios(capsys):
    assert cli.main(["--describe", "crop-frame"]) == 0
    out = capsys.readouterr().out
    assert "panel source" in out and "panel result" in out
    assert cli.main(["--describe", "panel-overlay"]) == 0
    out2 = capsys.readouterr().out
    assert "fills the slot" in out2 and "panel (adjust-panel, text)" in out2 and "tool-pill (tool-pill, text)" in out2
    assert any(f"generate at {r}" in out for r in RATIOS)
    assert nearest_ratio(970, 1600) == "9:16" and nearest_ratio(1180, 1600) == "3:4" and nearest_ratio(600, 630) == "1:1"


def test_spec_errors_name_the_problem(tmp_path):
    spec = write_spec(tmp_path)
    with pytest.raises(SystemExit, match="unknown family 'nope'"):
        cli.load_spec(rewrite(spec, family="nope"))
    with pytest.raises(SystemExit, match="1280x720 is not 1:1"):
        cli.load_spec(rewrite(spec, family="before-after", size="1280x720"))
    panels = yaml.safe_load(spec.read_text())["panels"]
    panels["after"]["image"] = "steps/missing.png"
    with pytest.raises(SystemExit, match="panel 'after': steps/missing.png not found"):
        cli.load_spec(rewrite(spec, size="720x720", panels=panels))
    del panels["after"]
    with pytest.raises(SystemExit, match="panel 'after' has no image"):
        cli.load_spec(rewrite(spec, panels=panels))
    with pytest.raises(SystemExit, match="unknown family 'nope'"):
        cli.main(["--describe", "nope"])


def test_panel_overlay_fills_the_slot_at_two_aspects_and_tilts(tmp_path):
    spec = write_spec(tmp_path, "panel-overlay", size="541x406", omit=["tool-pill"])
    im, drawn = cli.compose(cli.resolve(cli.load_spec(spec)))
    assert im.size == (541, 406) and set(drawn) == {"panel"}
    assert im.getpixel((270, 100))[:3] == (255, 0, 0), "the photo fills the slot"
    x0, y0, x1, y1 = (int(v) for v in drawn["panel"])
    assert 0.4 < x0 / 541 < 0.45 and 0.23 < y0 / 406 < 0.27 and x1 < 541 and y1 < 406, "panel over the lower right"
    px = [im.getpixel((x, y))[:3] for x in range(x0 + 4, x1 - 4, 6) for y in range(y0 + 4, y1 - 4, 6)]
    assert sum(max(p) < 60 for p in px) > len(px) * 0.5, "dark panel"
    assert any(p[0] > 200 and p[1] < 120 for p in px), "a hue chip or the knob shows"
    assert im.getpixel((1, 1))[3] == 0, "transparent ground keeps the rounded corners"
    hero = write_spec(tmp_path, "panel-overlay", size="550x440", omit=["panel"])
    im, drawn = cli.compose(cli.resolve(cli.load_spec(hero)))
    assert im.size == (550, 440) and set(drawn) == {"tool-pill"}
    x0, y0, x1, y1 = (int(v) for v in drawn["tool-pill"])
    assert im.getpixel(((x0 + x1) // 2, y1 - 4))[:3] == (255, 255, 255), "white label pill"
    tilted = write_spec(tmp_path, "panel-overlay", size="541x406", omit=["tool-pill"], ground="tilted")
    im, _ = cli.compose(cli.resolve(cli.load_spec(tilted)))
    assert im.mode == "RGBA" and im.getpixel((0, 0))[3] == 0 and im.getpixel((5, 203))[3] == 0, "tilted cards leave the edges clear"
    assert im.getpixel((200, 203))[3] == 255
    with pytest.raises(SystemExit, match="720x720 is not 4:3 or 5:4"):
        cli.load_spec(write_spec(tmp_path, "panel-overlay", size="720x720"))
    assert cli.main(["--describe", "panel-overlay"]) == 0


def test_layer_order_and_top_split(tmp_path):
    """A card on the default `card` layer draws under the panel; lifted to
    `overlay` it draws over it; on `top` it is composited after the tilt."""
    steps = tmp_path / "steps"
    steps.mkdir()
    img = steps / "p.png"
    Image.new("RGB", (400, 400), "red").save(img)

    def layout(card_layer, tilt=0):
        return {"size": (200, 200), "out": (100, 100), "scale": 200 / 1600 * cli.SS, "radius": 0,
                "ground": {"fill": (0, 0, 0)}, "tilt": tilt,
                "panels": {"photo": {"rect": (0, 0, 200, 200), "fit": "cover", "anchor": "center",
                                     "under": None, "image": img}},
                "chrome": [{"id": "c", "kind": "card", "rect": (40, 40, 160, 160), "fill": (0, 0, 255),
                            "layer": card_layer}]}

    assert cli.compose(layout("card"))[0].getpixel((50, 50))[:3] == (255, 0, 0), "card under the panel"
    assert cli.compose(layout("overlay"))[0].getpixel((50, 50))[:3] == (0, 0, 255), "overlay over the panel"
    assert cli.compose(layout("top"))[0].getpixel((50, 50))[:3] == (0, 0, 255), "top composited after the tilt"


def test_unknown_chrome_kind_names_the_registry(tmp_path):
    layout = {"size": (100, 100), "out": (100, 100), "scale": 0.125, "radius": 0,
              "ground": {"fill": None}, "tilt": 0, "panels": {},
              "chrome": [{"id": "x", "kind": "telephone"}]}
    with pytest.raises(SystemExit) as e:
        cli.compose(layout)
    assert "unknown chrome kind" in str(e.value) and "telephone" in str(e.value)


# --- Wave 4: spec grammar + placement -----------------------------------------

def _variant_spec(tmp_path, family, preset, **extra):
    """A spec whose panels cover the preset (not just the base family)."""
    steps = tmp_path / "steps"
    steps.mkdir(parents=True, exist_ok=True)
    tmpl = cli.template(family, preset)
    for i, name in enumerate(tmpl["panels"]):
        Image.new("RGB", (400, 400), ("red", "blue", "green")[i % 3]).save(steps / f"{name}.png")
    spec = tmp_path / "s.yaml"
    body = {"family": family, "preset": preset, "size": "720x720",
            "panels": {n: {"image": f"steps/{n}.png"} for n in tmpl["panels"]}, **extra}
    spec.write_text(yaml.safe_dump(body))
    return spec


def test_preset_is_an_alias_for_variant(tmp_path):
    spec = _variant_spec(tmp_path, "dark-composite", "model-picker")
    ids = {c["id"] for c in cli.resolve(cli.load_spec(spec))["chrome"]}
    assert "list" in ids, "preset: selects the device variant exactly like variant:"


def test_optional_panel_is_dropped(tmp_path):
    steps = tmp_path / "steps"
    steps.mkdir()
    Image.new("RGB", (400, 400), "red").save(steps / "photo.png")
    spec = tmp_path / "s.yaml"
    spec.write_text(yaml.safe_dump({"family": "dark-composite", "preset": "model-picker", "size": "720x720",
                                    "panels": {"photo": {"image": "steps/photo.png"},
                                               "thumb-a": {"optional": True}, "thumb-b": {"optional": True}}}))
    assert set(cli.resolve(cli.load_spec(spec))["panels"]) == {"photo"}, "optional panels with no image are skipped"


def test_ground_word_overrides_the_family_fill(tmp_path):
    black = _variant_spec(tmp_path / "a", "template-mockup", None, ground="black")
    assert cli.resolve(cli.load_spec(black))["ground"] == {"fill": (0, 0, 0)}
    clear = _variant_spec(tmp_path / "b", "dark-composite", None, ground="transparent")
    assert cli.resolve(cli.load_spec(clear))["ground"] == {"fill": None}


def test_list_form_adds_a_placed_item_and_keeps_the_family(tmp_path):
    spec = _variant_spec(tmp_path, "dark-composite", None, chrome=[
        {"id": "note", "kind": "label", "text": "NEW",
         "place": {"of": "canvas", "anchor": "br", "w": 200, "h": 80, "inset": 40}}])
    out = tmp_path / "steps" / "o.png"
    assert cli.main([str(spec), "--out", str(out)]) == 0
    _, drawn = cli.compose(cli.resolve(cli.load_spec(spec)))
    assert {"tile-1", "tile-2", "tile-3"} <= set(drawn), "the family's own chrome still draws"
    x0, y0, x1, y1 = drawn["note"]
    assert x0 > 360 and y0 > 360 and x1 <= 720 and y1 <= 720, "the added label sits bottom-right"


def test_unknown_override_id_warns_instead_of_silent_noop(tmp_path, capsys):
    spec = _variant_spec(tmp_path, "dark-composite", None, chrome={"chip": {"text": "1080p"}})
    cli.resolve(cli.load_spec(spec))
    assert "chrome 'chip' is not in dark-composite" in capsys.readouterr().err


def test_layout_place_math_and_repeat():
    boxes = {"canvas": (0, 0, 1600, 1200)}
    assert layout.to_rect({"of": "canvas", "anchor": "br", "w": 400, "h": 300, "inset": 40}, boxes) == (1160, 860, 1560, 1160)
    assert layout.to_rect({"of": "canvas", "anchor": "tl", "w": "25%", "h": 0.5}, boxes) == (0, 0, 400, 600)
    reps = layout.expand_repeat({"id": "t", "kind": "tile", "rect": (0, 0, 300, 1000), "repeat": 3, "dir": "column", "gap": 50})
    assert [x["id"] for x in reps] == ["t-1", "t-2", "t-3"]
    assert reps[0]["rect"] == (0, 0, 300, 300) and reps[2]["rect"] == (0, 700, 300, 1000)


def test_prompt_card_preset_draws_card_left_of_result(tmp_path):
    spec = _variant_spec(tmp_path, "prompt-card", None, chrome={"prompt-text": {"text": "a red fox"}})
    layout_ = cli.resolve(cli.load_spec(spec))
    im, drawn = cli.compose(layout_)
    assert set(drawn) == {"prompt", "prompt-text", "generate"}
    assert drawn["prompt"][2] < out_rect(layout_, "result")[0], "the dark prompt column sits left of the result"
    assert im.mode == "RGB", "black ground flattens to RGB"


def test_vs_two_up_preset_puts_the_badge_on_the_seam(tmp_path):
    spec = _variant_spec(tmp_path, "vs-two-up", None)
    layout_ = cli.resolve(cli.load_spec(spec))
    im, drawn = cli.compose(layout_)
    assert set(drawn) == {"vs"}
    lx0, lx1 = out_rect(layout_, "left")[0], out_rect(layout_, "left")[2]
    rx0 = out_rect(layout_, "right")[0]
    bx0, _, bx1, _ = drawn["vs"]
    assert lx1 < (bx0 + bx1) / 2 < rx0 + (out_rect(layout_, "right")[2] - rx0), "VS badge sits over the seam"
    assert im.mode == "RGB", "light-grey ground flattens to RGB"
