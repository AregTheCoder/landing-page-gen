"""lp-compose: a style-family template plus the worker's panel PNGs becomes
the composite card. Solid-colour fixture panels make the geometry checkable."""

import pytest
import yaml
from PIL import Image

from landing_page_gen.compose import cli, draw
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
    assert im.size == (720, 720) and im.mode == "RGB"
    layout = cli.resolve(cli.load_spec(spec))
    _, drawn = cli.compose(layout)

    def centre(name):
        x0, y0, x1, y1 = out_rect(layout, name)
        return im.getpixel((int((x0 + x1) / 2), int((y0 + y1) / 2)))
    assert centre("before") == (255, 0, 0) and centre("after") == (0, 0, 255) and centre("result") == (255, 0, 0)
    assert im.getpixel((1, 1)) == (0, 0, 0), "the black ground shows through the rounded corner"
    x0, y0, x1, y1 = (int(v) for v in drawn["before-pill"])
    bx0, by0, bx1, by1 = out_rect(layout, "before")
    assert bx0 < x0 < x1 < bx1 and by0 < y0 < y1 < by1, "pill sits inside its panel"
    px = [im.getpixel((x, y)) for x in range(x0 + 1, x1 - 1, 2) for y in range(y0 + 1, y1 - 1, 2)]
    assert any(p[0] > 230 and p[1] > 230 and p[2] > 230 for p in px), "white glyphs"
    assert any(60 < p[0] < 200 and p[1] < 60 and p[2] < 60 for p in px), "translucent dark fill over the red panel"
    tx0, ty0, tx1, ty1 = (int(v) for v in drawn["tile"])
    tile = [im.getpixel((x, y)) for x in range(tx0 + 2, tx1 - 2, 3) for y in range(ty0 + 2, ty1 - 2, 3)]
    assert sum(p == (0, 0, 0) for p in tile) > len(tile) * 0.7 and any(p[0] > 200 for p in tile), "black tile, white icon"


@pytest.mark.parametrize("family", sorted(FAMILIES))
def test_every_family_composes_at_slot_size(tmp_path, family):
    extra = {"chrome": {"headline": {"text": "Pottery classes"}}} if family == "template-mockup" else {}
    layout = cli.resolve(cli.load_spec(write_spec(tmp_path, family, **extra)))
    im, drawn = cli.compose(layout)
    assert im.size == (720, 720)
    assert set(drawn) == {c["id"] for c in FAMILIES[family]["chrome"]}
    if FAMILIES[family]["ground"].get("fill") is None:
        assert im.mode == "RGBA" and im.getpixel((0, 0))[3] == 0, "transparent ground keeps its rounded corners"


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
