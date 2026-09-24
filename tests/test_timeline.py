"""Templated callout videos (compose/timeline.py)."""

import struct

import pytest
from PIL import Image

from landing_page_gen.compose import roles, timeline

ENHANCER = roles.facts_for("ai-image-enhancer", "Fix lighting and color", ["Brightness", "Color"])


def test_value_holds_before_and_after_and_eases_between():
    keys = [{"t": 1, "opacity": 0}, {"t": 2, "opacity": 1}]
    assert timeline.value(keys, "opacity", 0) == 0 and timeline.value(keys, "opacity", 3) == 1
    assert timeline.value(keys, "opacity", 1.5) == pytest.approx(0.5)
    assert timeline.value(keys, "opacity", 1.25) < 0.25  # eased, not linear
    assert timeline.value(keys, "rect", 1, default="x") == "x"


@pytest.mark.parametrize("preset", list(timeline.PRESETS))
def test_every_preset_builds_valid_with_its_strings_and_the_pages_tools(preset):
    _, _, strings = timeline.PRESETS[preset]
    words = [f"word {i}" for i in range(len(strings))]
    spec = timeline.build(preset, "480x480", words, roles.facts_for("ai-image-enhancer", " ".join(words), words))
    assert timeline.validate(spec) == []
    for ly in spec["layers"]:
        assert ly["role"] and ly["keys"] and ("kind" in ly or ly.get("panel") in spec["panels"])
    tools = [ly["tool"] for ly in spec["layers"] if ly.get("role") == "tool"]
    assert all(t in ("enhance", "generate") for t in tools)


def test_an_empty_string_or_a_non_square_size_is_refused():
    spec = timeline.build("product-bento", "480x480", ["Bag", "$49"], ENHANCER)
    assert any("button is empty" in p for p in timeline.validate(spec))
    spec = timeline.build("enhance-reveal", "640x480", ["Brightness"], ENHANCER)
    assert any("1:1" in p for p in timeline.validate(spec))


def test_a_claim_the_page_never_makes_is_refused():
    spec = timeline.build("enhance-reveal", "480x480", ["Removes watermarks"],
                          roles.facts_for("ai-image-enhancer", "Fix lighting"))
    assert any("never makes" in p for p in timeline.validate(spec))


def test_frames_show_the_before_then_the_after(tmp_path):
    im = Image.new("RGB", (400, 400))
    for x in range(0, 400, 8):
        im.paste((255, 255, 255), (x, 0, x + 4, 400))
    im.save(tmp_path / "p.png")
    spec = timeline.build("enhance-reveal", "160x160", ["Brightness", "Color"], ENHANCER)
    r = timeline.Renderer(spec, {"photo": tmp_path / "p.png"})

    def detail(t):  # stripe contrast inside the hero card
        g = r.frame(t).convert("L").crop((40, 40, 120, 120))
        lo, hi = g.getextrema()
        return hi - lo

    assert detail(0.4) < detail(1.7)  # blurred before the sweep, sharp after it
    assert r.frame(3.9).size == (160, 160)


def test_mux_writes_a_webm_with_duration_and_a_cluster_per_keyframe():
    chunks = [(0, True, b"k0"), (33333, False, b"d1"), (2_000_000, True, b"k2")]
    out = timeline.mux(chunks, (96, 96), 2.1)
    assert out.startswith(b"\x1a\x45\xdf\xa3") and b"webm" in out and b"V_VP9" in out
    i = out.index(b"\x44\x89") + 3  # Duration: id, 1-byte size (8), then the double
    assert struct.unpack(">d", out[i:i + 8])[0] == pytest.approx(2100)
    assert out.count(b"\x1f\x43\xb6\x75") == 2


def test_render_is_a_clip_chromium_reads_at_the_planned_length(tmp_path):
    pytest.importorskip("playwright")
    from landing_page_gen.corpus import motion
    from landing_page_gen.corpus.similar import FrameGrabber
    Image.new("RGB", (200, 200), (200, 60, 40)).save(tmp_path / "p.png")
    spec = timeline.build("enhance-reveal", "96x96", ["Brightness", "Color"], ENHANCER)
    try:
        n, secs = timeline.render(spec, {"photo": tmp_path / "p.png"}, tmp_path / "o.webm", tmp_path / "poster.png")
    except Exception as exc:  # no Chromium / WebCodecs here
        pytest.skip(f"Chromium encode unavailable: {exc}")
    assert (n, secs) == (120, 4.0) and (tmp_path / "poster.png").exists()
    with FrameGrabber() as g:
        duration, _ = motion.probe(tmp_path / "o.webm", g, tmp_path, "o")
    assert duration == pytest.approx(4.0, abs=0.05)


def test_the_skeleton_says_timeline_only_for_a_static_square_callout():
    from landing_page_gen.corpus.skeleton import motion_line
    assert motion_line({"motion_kind": "transition", "camera": "static", "chrome": ["compare-handle"]}, 480, 480) \
        .startswith("timeline enhance-reveal")
    assert motion_line({"motion_kind": "ui-demo", "camera": "static", "chrome": ["prompt-panel"]}, 480, 480) \
        .startswith("timeline prompt-to-result")
    # a callout's chrome comes after its poster frame, so an empty bag leaves the pick to the manager
    assert motion_line({"motion_kind": "ui-demo", "camera": "static", "chrome": []}, 480, 480).startswith("timeline TODO")
    assert motion_line({"motion_kind": "subject-motion", "camera": "static"}, 480, 480).startswith("generative")
    assert motion_line({"motion_kind": "transition", "camera": "static"}, 627, 523).startswith("generative")
    assert motion_line({}, 480, 480).startswith("TODO")
