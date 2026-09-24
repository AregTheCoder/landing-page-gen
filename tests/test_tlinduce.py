"""Learning from clips: icons named by their shape (compose/icons.py), and a
storyboard's choreography followed and replayed (compose/tlinduce.py)."""

import numpy as np
from PIL import Image, ImageDraw

from landing_page_gen.compose import draw, icons, tlinduce
from landing_page_gen.corpus import layout


def test_every_icon_we_draw_is_recognised_as_itself():
    for name in draw.ICONS:
        im = Image.new("RGBA", (120, 120), (20, 20, 20, 255))
        draw.icon(im, (10, 10, 110, 110), name)
        assert icons.classify(im, (20, 20, 20))[0] == name, name


def test_a_learned_glyph_stands_for_its_tool_only_where_one_fits():
    from landing_page_gen.compose import roles
    assert {"remove-bg", "crop-bold", "text-to-image"} <= set(draw.ICONS)  # drawn and recognised like the rest
    assert roles.icon_tool("remove-bg") == "remove-bg" and roles.icon_tool("crop-bold") == "crop"
    assert roles.icon_tool("star") is None and "picsart" not in draw.ICONS  # no tool, no maker's claim


def test_a_blank_crop_is_no_icon():
    assert icons.classify(Image.new("RGB", (60, 60), (30, 30, 30)), (30, 30, 30)) == (None, 0.0)


def _frame(card_x, red=0.0, size=160):
    im = Image.new("RGB", (size, size), (0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((card_x, 50, card_x + 50, 110), radius=8, fill=(240, 240, 240))
    d.rectangle((card_x + 10, 60, card_x + 40, 70), fill=(20, 20, 20))  # something on the card to follow
    if red:
        c = tuple(round(v * red) for v in (220, 40, 40))
        d.rounded_rectangle((100, 120, 150, 150), radius=6, fill=c)
    return im


def test_a_moving_card_is_followed_and_its_replay_matches_the_clip(tmp_path):
    """Two holds: a card on the left; the card moved right and a red card
    arrived. The replay follows the card (one layer across both states) and
    plays close to the clip's own samples."""
    store = tmp_path / "boards"
    folder = store / "clip0001"
    folder.mkdir(parents=True)
    xs = [10] * 8 + [10 + 20 * k for k in range(1, 5)] + [90] * 8
    reds = [0] * 8 + [k / 4 for k in range(1, 5)] + [1] * 8
    frames = np.stack([np.asarray(_frame(x, r).resize((96, 96)), np.uint8) for x, r in zip(xs, reds)])
    np.savez_compressed(folder / "samples.npz", frames=frames, step=0.1)
    states = []
    for k, (x, r, t0, t1) in enumerate(((10, 0, 0.0, 0.8), (90, 1, 1.2, 2.0))):
        key = f"s{k}.png"
        _frame(x, r).save(folder / key)
        states.append({"k": k, "t0": t0, "t1": t1, "t": (t0 + t1) / 2, "key": key,
                       "reading": layout.read(folder / key, {"lines": []})})
    board = {"id": "clip0001", "page": "test", "slot": "S01-m1", "duration": 2.0, "size": [160, 160], "step": 0.1,
             "states": states, "transitions": [{"from": 0, "to": 1, "t0": 0.7, "t1": 1.2, "type": "slide"}]}
    got = tlinduce.learn(board, store, tmp_path / "work")
    assert got["followed"] >= 1, got
    assert got["error"] < 0.08, got
