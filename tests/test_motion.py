"""Motion measurements from sampled frames: sampling instants, the measured
fields on synthetic frames, the 3-frame strip, and the per-family summary that
becomes a **Motion:** line."""

import numpy as np
from PIL import Image

from landing_page_gen.corpus import motion


def blocky(seed=0, h=72, w=128, block=8):
    """A smooth-ish textured scene: random 8 px blocks, so a few px of shift
    reads as motion without every pixel changing."""
    rng = np.random.default_rng(seed)
    small = rng.random((h // block, w // block)).astype(np.float32) * 0.6 + 0.2
    return np.kron(small, np.ones((block, block), dtype=np.float32))


def test_times_are_spaced_inside_the_clip():
    assert motion.times(10) == [0.2, 2.6, 5.0, 7.4, 9.8]
    assert motion.times(0.3) == [0.15] * 5, "a clip shorter than two edges collapses onto its middle"
    assert motion.times(None) == [0.2] * 5


def test_static_scene_is_still_static_and_loops():
    out = motion.measure([blocky()] * 5)
    assert out["pace"] == "still" and out["camera"] == "static" and out["loop"] is True and out["motion"] < 0.01


def test_subject_motion_keeps_a_static_camera():
    base = blocky()
    frames = []
    for i in range(5):
        f = base.copy()
        f[30:42, 50 + 3 * i:62 + 3 * i] = 1.0  # a bright patch drifting through the centre
        frames.append(f)
    out = motion.measure(frames)
    assert out["camera"] == "static", "the edges hold, so the camera does"
    assert out["motion"] > 0


def test_pan_and_push_in_are_not_written_as_static():
    base = blocky()
    pan = motion.measure([np.roll(base, 3 * i, axis=1) for i in range(5)])
    assert "camera" not in pan and pan["pace"] != "still"
    zoom = []
    for i in range(5):  # a push-in: the border content changes while the centre roughly holds
        crop = base[i:72 - i, i * 2:128 - i * 2] if i else base
        zoom.append(np.asarray(Image.fromarray((crop * 255).astype("uint8")).resize((128, 72)), dtype=np.float32) / 255)
    assert "camera" not in motion.measure(zoom)


def test_hard_cut_blocks_the_camera_and_the_loop():
    a, b = blocky(1), blocky(2)
    out = motion.measure([a, a, b, b, b])
    assert "camera" not in out and out["loop"] is False


def test_strip_is_first_middle_last(tmp_path):
    paths = []
    for i, colour in enumerate(["red", "orange", "yellow", "green", "blue"]):
        p = tmp_path / f"f{i}.png"
        Image.new("RGB", (16, 9), colour).save(p)
        paths.append(p)
    out = motion.strip(paths, tmp_path / "strip.png")
    with Image.open(out) as im:
        assert im.size == (16 * 3 + 4 * 2, 9)
        assert im.getpixel((0, 4)) == (255, 0, 0) and im.getpixel((20, 4)) == (255, 255, 0) and im.getpixel((40, 4)) == (0, 0, 255)


def video_rec(**over):
    rec = {"kind": "video", "type": "hero", "ground": "photo-full-bleed", "layout": "single", "panel_count": 1,
           "chrome": [], "art_style": "photo", "pace": "slow", "loop": True, "duration": 8.0,
           "motion_kind": "subject-motion", "camera": "static"}
    rec.update(over)
    return rec


def test_summary_and_motion_line_follow_the_labelled_clips():
    mapping = {f"https://x/{i}.webm": video_rec(duration=6 + i) for i in range(6)}
    mapping["https://x/6.webm"] = video_rec(camera="pan", motion_kind="camera-move")
    mapping["https://x/img.png"] = {"kind": "image", "type": "hero"}
    summ = motion.summary(mapping)
    assert set(summ) == {"full-bleed"}
    s = summ["full-bleed"]
    assert s["n"] == 7 and s["motion_kind"] == "subject-motion" and s["camera"] == "static" and s["pace"] == "slow"
    assert s["loop_share"] == 1.0 and s["median_s"] == 8.0
    assert motion.motion_line("full-bleed", s) == \
        "**Motion:** 7 corpus clips; subject-motion; camera static; pace slow; 100 % loop; median 8.0 s."
    thin = motion.summary({f"https://x/{i}.webm": video_rec() for i in range(3)})
    assert thin["full-bleed"]["motion_kind"] is None, "fewer than min_n answers: no modal value"


def test_write_doc_sets_the_line_after_references_and_replaces_it(tmp_path):
    doc = tmp_path / "families.md"
    doc.write_text("# Families\n\n## full-bleed\n**Use:** photos.\n**References:** corpus/references/full-bleed.yaml\n\n"
                   "## cinematic-still\n**Use:** film.\n")
    s = {"n": 7, "motion_kind": "subject-motion", "camera": "static", "pace": "slow", "loop_share": 1.0, "median_s": 8.0}
    assert motion.write_doc({"full-bleed": s, "cinematic-still": s, "nope": s}, doc) == ["full-bleed", "cinematic-still"]
    text = doc.read_text()
    assert "**References:** corpus/references/full-bleed.yaml\n**Motion:** 7 corpus clips" in text
    assert text.endswith("## cinematic-still\n**Use:** film.\n**Motion:** 7 corpus clips; subject-motion; camera static; pace slow; 100 % loop; median 8.0 s.\n")
    motion.write_doc({"full-bleed": {**s, "n": 9}}, doc)
    text = doc.read_text()
    assert text.count("**Motion:**") == 2 and "9 corpus clips" in text and "7 corpus clips; subject-motion; camera static; pace slow; 100 % loop; median 8.0 s.\n\n## cinematic" not in text
