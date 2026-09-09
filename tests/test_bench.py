"""lp-bench pairs each generated crop with the original it replaced, measures
both alike, and flags what the review rubric would."""
import json

import numpy as np
from PIL import Image

from landing_page_gen.inject import bench


def tile(path, ground, subject, frac):
    im = Image.new("RGB", (144, 256), ground)
    h, w = int(256 * frac), int(144 * 0.7)
    im.paste(Image.new("RGB", (w, h), subject), ((144 - w) // 2, (256 - h) // 2))
    im.save(path)


def test_flags_fire_on_a_pale_small_tile_and_stay_quiet_on_a_faithful_photo(tmp_path):
    run, orig = tmp_path / "run", tmp_path / "orig"
    gen = run / "dist" / "media" / "gen"
    gen.mkdir(parents=True)
    orig.mkdir()
    tile(orig / "s03.png", (240, 30, 60), (20, 30, 90), 0.85)         # saturated red ground, a navy subject filling 85 %
    tile(gen / "S03-m1.png", (250, 250, 250), (128, 128, 128), 0.30)  # white ground, a grey subject at 30 %
    photo = (np.random.default_rng(3).uniform(0.4, 1.0, size=(196, 294, 3)) * 255).astype("uint8")
    for p in (orig / "s09.png", gen / "S09-m1.png"):
        Image.fromarray(photo).save(p)
    (gen / "S09-m2-placeholder.png").write_bytes(b"")
    slots = {"page": "p", "sections": {"S03": {"type": "gallery"}, "S09": {"type": "tutorial-grid"}}, "slots": {
        "S03-m1": {"src": "https://cdn/a.avif", "local": str(orig / "s03.png"), "size": [196, 348]},
        "S09-m1": {"src": "https://cdn/b.avif", "local": str(orig / "s09.png"), "size": [294, 196]},
        "S09-m2": {"src": "https://cdn/c.avif", "local": None, "size": [294, 196]}}}
    (run / "slots.json").write_text(json.dumps(slots))
    assert bench.main([str(run), "--attrs", str(tmp_path / "none.yaml")]) == 0
    result = bench.bench(run, tmp_path / "none.yaml")
    s03 = [f for f in result["flags"] if f.startswith("S03-m1")]
    assert any("subject coverage" in f and "[geometry]" in f for f in s03), "a subject shrinking from 85 % to 30 % is a geometry flag"
    assert any("ground saturation" in f and "[resemblance]" in f for f in s03), "a saturated ground turning white is a resemblance flag"
    assert any("ground lightness" in f for f in s03), "red to white is a lightness change as well"
    assert any(f.startswith("S03-m1 (gallery): family") for f in s03), "a colour tile and a white tile derive different families"
    assert not [f for f in result["flags"] if f.startswith("S09")], "a faithful photo raises nothing; a placeholder is not scored"
    assert result["means"]["S03"]["d_coverage"] < -0.25 and result["means"]["page"]["n"] == 2
    text = (run / "benchmark.md").read_text()
    assert "\n| S03-m1 |" in text and "\n| S09-m1 |" in text and "S09-m2" not in text, "one table row per scored slot"
    assert "## Means" in text and "\n| S03 |" in text and "\n| page |" in text
    assert "## Flags" in text and text.index("## Flags") < text.index("S03-m1 (gallery): subject coverage")


def card(path, panels):
    """A black 720 px card with coloured panels at the given (x0, y0, x1, y1) fractions and one dark-grey tile."""
    im = Image.new("RGB", (720, 720), (0, 0, 0))
    for i, (x0, y0, x1, y1) in enumerate(panels):
        im.paste(Image.new("RGB", (int((x1 - x0) * 720), int((y1 - y0) * 720)), [(200, 40, 60), (40, 80, 220), (240, 170, 30)][i % 3]),
                 (int(x0 * 720), int(y0 * 720)))
    im.paste(Image.new("RGB", (160, 160), (28, 28, 30)), (0, 0))
    im.save(path)


def test_pictures_counts_panels_and_flags_a_composite_that_lost_its_device(tmp_path):
    run, orig = tmp_path / "run", tmp_path / "orig"
    gen = run / "dist" / "media" / "gen"
    gen.mkdir(parents=True)
    orig.mkdir()
    card(orig / "s01.png", [(0.26, 0, 1, 1), (0, 0.51, 0.23, 0.74), (0, 0.77, 0.23, 1)])  # main + two thumbnails
    card(gen / "S01-m1.png", [(0, 0, 0.74, 1)])                                            # main only
    card(gen / "S04-m1.png", [(0, 0, 0.74, 1)])
    assert bench.pictures(orig / "s01.png") == 3 and bench.pictures(gen / "S01-m1.png") == 1, "tiles and gutters do not count"
    (run / "sections" / "S01").mkdir(parents=True)
    (run / "sections" / "S01" / "compose-S01-m1.yaml").write_text("family: dark-composite\n")
    slots = {"page": "p", "sections": {"S01": {"type": "hero"}, "S04": {"type": "feature-callout"}}, "slots": {
        "S01-m1": {"src": "https://cdn/a.avif", "local": str(orig / "s01.png"), "size": [480, 480]},
        "S04-m1": {"src": "https://cdn/b.avif", "local": str(orig / "s01.png"), "size": [480, 480]}}}
    (run / "slots.json").write_text(json.dumps(slots))
    result = bench.bench(run, tmp_path / "none.yaml")
    assert any(f.startswith("S01-m1 (hero): pictures 3 -> 1") and f.endswith("[fit]") for f in result["flags"])
    assert not [f for f in result["flags"] if "pictures" in f and f.startswith("S04")], "no compose spec, so the proxy stays quiet"
    bench.write_md(result, run / "benchmark.md")
    assert "| pictures |" in (run / "benchmark.md").read_text() and "| 3 / 1 |" in (run / "benchmark.md").read_text()
