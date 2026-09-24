"""Reading a composite off its pixels (corpus/layout.py) and turning a reading
into a template (compose/induce.py): synthetic pictures with known answers."""

import numpy as np
from PIL import Image, ImageDraw

from landing_page_gen.compose import induce, replica
from landing_page_gen.corpus import layout


def _noise(size, seed=1):
    rng = np.random.default_rng(seed)
    return Image.fromarray(rng.integers(0, 255, (size[1], size[0], 3), dtype=np.uint8))


def _bento(path, ground=(255, 255, 255, 255)):
    """1600 px: two black cards and a photo on a ground, 16 px gutters (the ROAS bento)."""
    im = Image.new("RGBA", (1600, 1600), ground)
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((232, 232, 792, 504), radius=24, fill=(0, 0, 0, 255))
    d.rounded_rectangle((232, 520, 792, 984), radius=24, fill=(0, 0, 0, 255))
    d.rounded_rectangle((300, 800, 700, 880), radius=12, fill=(255, 255, 255, 255))  # a field in the second card
    im.paste(_noise((562, 752)), (808, 232))
    im.save(path)
    return path


def _line(text, box):
    return {"text": text, "conf": 1.0, "box": list(box), "words": []}


def test_cards_pictures_and_fields_are_read_on_a_flat_ground(tmp_path):
    p = _bento(tmp_path / "bento.png")
    reading = {"lines": [_line("Revenue ÷ Ad Spend", (288, 340, 700, 390))]}
    got = layout.read(p, reading)
    assert got["ground"] == [255, 255, 255]
    kinds = sorted(r["kind"] for r in got["regions"])
    assert kinds == ["card", "card", "picture"]
    cards = [r for r in got["regions"] if r["kind"] == "card"]
    assert all(r["fill"] == [0, 0, 0] for r in cards)
    assert all(abs(r["radius"] - 24) <= 6 for r in cards)
    assert any(c["kind"] == "field" for r in cards for c in r["children"])  # the white input box
    assert got["texts"][0]["region"] is not None


def test_transparent_gutters_between_panels_that_touch_the_edge(tmp_path):
    im = Image.new("RGBA", (1600, 1600), (0, 0, 0, 0))
    im.paste(_noise((784, 1600), 2), (0, 0))
    im.paste(_noise((784, 1600), 3), (816, 0))
    im.save(tmp_path / "two.png")
    got = layout.read(tmp_path / "two.png", {"lines": []})
    assert got["ground"] == "transparent"
    assert [r["kind"] for r in got["regions"]] == ["picture", "picture"]


def test_lettering_on_a_transparent_sheet_is_not_a_picture(tmp_path):
    im = Image.new("RGBA", (800, 800), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    for x in (120, 300, 480):  # three shaded strokes, like the digits of a "2024" sticker
        for k in range(10):
            d.arc((x + k, 300 + k, x + 160 - k, 500 - k), 0, 300, fill=(40 + 20 * k, 200 - 15 * k, 90, 255), width=1)
    im.paste(_noise((200, 160), 6), (300, 600))  # and one real photo
    im.save(tmp_path / "sticker.png")
    got = layout.read(tmp_path / "sticker.png", {"lines": []})
    assert [r["kind"] for r in got["regions"]] == ["picture"] and got["regions"][0]["box"][1] >= 590


def _compare_card(path):
    """A compare card (add-shadow-to-image S11): one rounded card on black, its
    Before left of a white divider at 40 % and its After right of it."""
    card = _noise((600, 480), 4)
    card.paste(_noise((360, 480), 5), (240, 0))
    ImageDraw.Draw(card).rectangle((238, 0, 243, 479), fill=(255, 255, 255))
    mask = Image.new("L", card.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, 599, 479), radius=30, fill=255)
    im = Image.new("RGB", (800, 640), (0, 0, 0))
    im.paste(card, (100, 80), mask)
    im.save(path)
    return path


def test_a_compare_card_is_one_picture_split_at_its_divider(tmp_path):
    p = _compare_card(tmp_path / "compare.png")
    got = layout.read(p, {"lines": []})
    assert [r["kind"] for r in got["regions"]] == ["picture"] and abs(got["regions"][0]["split"] - 0.4) < 0.02
    lay = induce.induce({"id": "c0ffee00", "page": "add-shadow-to-image", "slot": "S11-m2", "local": str(p), **got})
    assert list(lay["panels"]) == ["photo", "photo-2"]  # the Before and the After, one card
    assert lay["panels"]["photo"]["rect"] == lay["panels"]["photo-2"]["rect"]
    assert abs(lay["panels"]["photo-2"]["seam"] - 0.4) < 0.02
    assert [(s["shape"], s["accepts"]) for s in lay["slots"]] == [("seam", ["comparison"])]
    assert [f["block"] for f in lay["exemplar"]["fills"].values()] == ["compare-handle"]
    plain = layout.read(_bento(tmp_path / "bento.png"), {"lines": []})
    assert all(r.get("split") is None for r in plain["regions"])  # a photo with no divider is not one


def test_a_seam_panel_shows_its_image_right_of_the_divider_only(tmp_path):
    from landing_page_gen.compose import cli
    Image.new("RGB", (100, 80), (255, 0, 0)).save(tmp_path / "before.png")
    Image.new("RGB", (100, 80), (0, 0, 255)).save(tmp_path / "after.png")
    base = {"rect": (0, 0, 200, 160), "fit": "cover", "anchor": "center", "under": None, "dim": None,
            "trim": None, "crop": None, "degrade": None, "radius": 0}
    lay = {"size": (200, 160), "out": (200, 160), "scale": 200 / 1600, "ground": {"fill": (0, 0, 0)},
           "radius": 0, "tilt": 0, "chrome": [],
           "panels": {"photo": {**base, "image": tmp_path / "before.png", "seam": None},
                      "photo-2": {**base, "image": tmp_path / "after.png", "seam": 0.4}}}
    im = cli.compose(lay)[0].convert("RGB")
    assert im.getpixel((40, 80))[0] > 200 and im.getpixel((120, 80))[2] > 200


def test_a_string_is_given_its_bank_category():
    assert induce.text_category("Before") == "state-label"
    assert induce.text_category("4K") == "spec"
    assert induce.text_category("1080 x 1350") == "spec"
    assert induce.text_category("SVG") == "spec"
    assert induce.text_category("Generate") == "action"
    assert induce.text_category("$49.99") == "context"
    assert induce.text_category("A dreamy, high-fashion beauty portrait of a woman") == "action"
    assert induce.text_category("Revenue ÷ Ad Spend") == "statement"


def test_an_induced_layout_is_a_skeleton_that_carries_no_page_words(tmp_path):
    p = _bento(tmp_path / "bento.png")
    lines = [_line("Revenue ÷ Ad Spend", (288, 340, 700, 390)),
             _line("Google Ads", (300, 600, 560, 650)), _line("Facebook Ads", (300, 680, 600, 730))]
    rd = {"id": "deadbeef", "page": "roas-calculator", "slot": "S04-m1", "local": str(p),
          **layout.read(p, {"lines": lines})}
    lay = induce.induce(rd, "dark-composite")
    assert lay["aspect"] == (1, 1)
    assert list(lay["panels"]) == ["photo"] and lay["panels"]["photo"]["holds"] == "scene"
    shapes = {s["id"]: (s["shape"], s["accepts"]) for s in lay["slots"]}
    assert ("card", ["statement"]) in shapes.values()
    blocks = {f["block"] for f in lay["exemplar"]["fills"].values()}
    assert "statement" in blocks
    text = str(lay)
    assert "Revenue" not in text and "Google" not in text  # the template never carries the original's words
    assert all(s.get("type") for s in lay["slots"] if s["shape"] == "card")  # each text slot keeps its measured type


def test_two_layouts_are_one_when_their_parts_coincide():
    a = {"aspect": (1, 1), "panels": {"photo": {"rect": (800, 200, 1400, 1000)}},
         "slots": [{"shape": "card", "rect": (200, 200, 780, 500)}]}
    b = {"aspect": (1, 1), "panels": {"photo": {"rect": (810, 205, 1400, 990)}},
         "slots": [{"shape": "card", "rect": (205, 200, 780, 510)}]}
    c = {**b, "slots": [{"shape": "bar", "rect": (205, 200, 780, 510)}]}
    assert induce.same_layout(a, b)
    assert not induce.same_layout(a, c)


def test_a_replica_fills_each_block_from_the_lines_in_its_box():
    form = {"kind": "form-card", "fields": [["Input one", "0"]], "result": ["Result:", "0"]}
    lines = [_line("Ad Spend", (100, 100, 300, 130)), _line("$70", (100, 150, 200, 180)),
             _line("Ad Revenue", (100, 200, 300, 230)), _line("$ 500", (100, 250, 200, 280)),
             _line("Your ROAS is:", (700, 120, 1000, 170)), _line("7.14", (800, 200, 900, 250))]
    got = replica.fill(form, lines)
    assert got["fields"] == [["Ad Spend", "$70"], ["Ad Revenue", "$ 500"]]
    assert got["result"] == ["Your ROAS is:", "7.14"]
    rows = replica.fill({"kind": "list-card", "rows": []},
                        [_line("G Google Ads", (100, 100, 400, 140)), _line("Picsart Ad", (100, 200, 400, 240)),
                         _line("Maker", (100, 245, 250, 285))])
    assert rows["rows"] == ["Google Ads", "Picsart Ad Maker"]  # the logo read as a letter goes; a wrap joins its row


def test_the_probe_set_names_layouts_that_exist():
    import yaml
    names = yaml.safe_load(replica.PROBE.read_text())
    assert {n for _, _, n in replica.layouts(names)} == set(names)  # a renamed layout would drop out of the probe silently
