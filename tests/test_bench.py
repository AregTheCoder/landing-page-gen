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
