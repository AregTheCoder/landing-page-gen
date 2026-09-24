"""lp-bench pairs each generated crop with the original it replaced, measures
both alike, and flags what the review rubric would."""
import json
from pathlib import Path

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


def test_video_slots_are_scored_on_first_frame_length_and_seam(tmp_path, monkeypatch):
    run, orig = tmp_path / "run", tmp_path / "orig"
    gen = run / "dist" / "media" / "gen"
    gen.mkdir(parents=True)
    orig.mkdir()
    photo = (np.random.default_rng(5).uniform(0.4, 1.0, size=(196, 196, 3)) * 255).astype("uint8")
    (orig / "clip.webm").write_bytes(b"webm")
    (gen / "S06-m1.mp4").write_bytes(b"mp4")
    (gen / "S06-m1-poster.png").write_bytes(b"")  # lp-inject's poster copy is not a slot
    fake = {"clip": (10.1, {"pace": "slow", "loop": True, "loop_seam": 0.95}),
            "S06-m1": (5.0, {"pace": "slow", "loop": False, "loop_seam": 0.6})}

    def video_stats(path, grabber, tmp):
        first = Path(tmp) / f"{path.stem}-f0.png"
        first.parent.mkdir(parents=True, exist_ok=True)
        Image.fromarray(photo).save(first)
        duration, fields = fake[path.stem]
        return duration, first, fields
    monkeypatch.setattr(bench, "video_stats", video_stats)
    slots = {"page": "p", "sections": {"S06": {"type": "feature-callout"}}, "slots": {
        "S06-m1": {"src": "https://cdn/v.webm", "local": str(orig / "clip.webm"), "size": [539, 539]}}}
    (run / "slots.json").write_text(json.dumps(slots))
    result = bench.bench(run, tmp_path / "none.yaml")
    assert [r["slot"] for r in result["rows"]] == ["S06-m1"]
    assert any(f.startswith("S06-m1 (feature-callout): duration 10.1 s -> 5.0 s") and f.endswith("[duration]") for f in result["flags"])
    assert any("the original loops and this does not [loop]" in f for f in result["flags"])
    assert not [f for f in result["flags"] if "[resemblance]" in f or "[geometry]" in f], "same first frame: the picture metrics stay quiet"
    bench.write_md(result, run / "benchmark.md")
    text = (run / "benchmark.md").read_text()
    assert "## Video" in text and "| S06-m1 | 10.1 s / 5.0 s | 0.50 | 0.95 / 0.60 | slow / slow |" in text


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


def test_composition_flags_a_chrome_kind_the_spec_never_draws(tmp_path):
    run, orig = tmp_path / "run", tmp_path / "orig"
    gen = run / "dist" / "media" / "gen"
    gen.mkdir(parents=True)
    orig.mkdir()
    card(orig / "s07.png", [(0.44, 0, 1, 1), (0, 0.42, 0.42, 0.70), (0, 0.72, 0.42, 1)])  # model-picker modal
    card(gen / "S07-m1.png", [(0, 0, 0.56, 1)])
    (run / "sections" / "S07").mkdir(parents=True)
    # a model-picker spec draws the list-panel (option-list) but no tile
    (run / "sections" / "S07" / "compose-S07-m1.yaml").write_text(  # a spec draws its picked blocks, nothing else
        "family: dark-composite\nvariant: model-picker\nsize: 480x480\n"
        "chrome:\n- {id: list, kind: list-panel, block: model-picker, active_text: Recraft V4}\n")
    slots = {"page": "p", "sections": {"S07": {"type": "feature-callout"}}, "slots": {
        "S07-m1": {"src": "https://cdn/a.avif", "local": str(orig / "s07.png"), "size": [480, 480],
                   "attrs": {"chrome": ["option-list", "tile"],
                             "chrome_items": [{"kind": "option-list", "placement": "beside", "state": {"active": 1}},
                                              {"kind": "tile", "placement": "beside", "count": 2}],
                             "labelled": ["chrome_items"]}}}}
    (run / "slots.json").write_text(json.dumps(slots))
    result = bench.bench(run, tmp_path / "none.yaml")
    row = result["rows"][0]
    assert row["composition"] == {"orig": ["option-list", "tile"], "gen": ["option-list"], "missing": ["tile"], "extra": []}
    assert any(f.startswith("S07-m1 (feature-callout): chrome") and "missing tile [composition]" in f for f in result["flags"])
    assert not [f for f in result["flags"] if "[fit]" in f], "the labelled composition supersedes the pictures proxy"
    bench.write_md(result, run / "benchmark.md")
    assert "| chrome orig -> gen |" in (run / "benchmark.md").read_text()
    assert "| option-list+tile -> option-list |" in (run / "benchmark.md").read_text()
    # a spec the worker renamed is found through result.md's compose: field
    (run / "sections" / "S07" / "compose-S07-m1.yaml").rename(run / "sections" / "S07" / "compose-S07-m1-split.yaml")
    (run / "sections" / "S07" / "result.md").write_text(
        "---\nsection: S07\nslots:\n  S07-m1:\n    chosen: x.png\n    compose: compose-S07-m1-split.yaml\n---\n")
    row = bench.bench(run, tmp_path / "none.yaml")["rows"][0]
    assert row["composition"]["gen"] == ["option-list"]
    assert row["gen_family"] == "dark-composite"  # the family the spec drew, not a guess from its pixels


def test_every_compose_kind_maps_to_a_corpus_chrome_kind():
    """A compose kind bench cannot map is silently dropped from the chrome
    comparison, so KINDS and COMPOSE_KIND must not drift; every target is a
    corpus kind (attrs.CHROME_KINDS) or None for text-only chrome."""
    from landing_page_gen.compose import kinds
    from landing_page_gen.corpus import attrs
    assert set(kinds.KINDS) <= set(bench.COMPOSE_KIND), set(kinds.KINDS) - set(bench.COMPOSE_KIND)
    assert {v for v in bench.COMPOSE_KIND.values() if v} <= set(attrs.CHROME_KINDS)
    assert not set(kinds.MODEL_KINDS) & set(kinds.KINDS), "model-rendered kinds are never compose-drawn"
