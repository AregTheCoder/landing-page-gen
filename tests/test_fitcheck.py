"""The layout check a brief runs before anything is spent (compose/fitcheck.py):
the three layout faults the live runs paid for, as synthetic readings."""

from landing_page_gen.compose import cli, fitcheck


def _reading(*boxes, size=(1600, 1600), split=None):
    return {"id": "0000beef", "size": list(size),
            "regions": [{"kind": "picture", "box": list(b), **({"split": split} if split else {})} for b in boxes]}


def test_a_layout_that_fits_its_original_raises_nothing():
    stretcher = _reading((0, 0, 784, 572), (816, 0, 1600, 572), (0, 602, 1600, 1600))
    assert fitcheck.check(cli.template("crop-frame", "stretch"), stretcher) == []
    assert "panels" in fitcheck.check(cli.template("crop-frame"), stretcher)[0]  # the crop layout has two


def test_two_side_by_side_panels_are_not_a_compare_card():
    card = _reading((200, 160, 1400, 1120), size=(1600, 1280), split=0.43)
    two_up = {"aspect": (5, 4), "panels": {"photo": {"rect": (40, 40, 780, 1240)}, "photo-2": {"rect": (820, 40, 1560, 1240)}}}
    compare = {"aspect": (5, 4), "panels": {"photo": {"rect": (200, 160, 1400, 1120)}, "photo-2": {"rect": (200, 160, 1400, 1120)}}}
    assert fitcheck.check(two_up, card)[0].startswith("boxes:")
    assert fitcheck.check(compare, card) == []


def test_pictures_in_a_thin_band_are_a_different_device():
    wide = _reading((0, 0, 700, 1600), (740, 0, 1600, 1600))
    band = {"aspect": (1, 1), "panels": {"photo": {"rect": (240, 684, 532, 1016)}, "photo-2": {"rect": (572, 684, 1360, 1064)}}}
    assert any(w.startswith("scale:") for w in fitcheck.check(band, wide))


def test_one_full_picture_is_named_as_full_bleed_and_no_reading_is_said():
    got = fitcheck.check(cli.template("crop-frame"), _reading((0, 0, 1600, 1600)))
    assert "full-bleed" in got[0]
    assert fitcheck.check(cli.template("dark-composite"), None)[0].startswith("no reading")


def test_a_cover_crop_anchored_on_the_subject_keeps_the_face():
    from landing_page_gen.compose import subject
    found = {"w": 1024, "h": 1536, "faces": [[350, 188, 645, 484]], "people": [], "salient": None}
    frame = (738, 590)  # a wide card from a tall picture: the centre crop loses the top of the head
    centre = subject.crop_box((1024, 1536), frame, (0.5, 0.5))
    assert subject.cut(found, centre)
    at = subject.anchor((1024, 1536), frame, subject.box(found), subject.EYE_LINE)
    assert not subject.cut(found, subject.crop_box((1024, 1536), frame, at))


def test_a_spec_from_a_plan_anchors_its_scenes_on_the_subject():
    from landing_page_gen.compose import plan
    cp = {"slot": "S01-m1", "family": "crop-frame", "size": "1600x1600",
          "panels": [{"panel": "source", "holds": "scene", "fit": "cover"}, {"panel": "cut", "holds": "subject", "fit": "contain"}]}
    spec = plan.to_spec(cp, {"source": "a.png", "cut": "b.png"})
    assert spec["panels"]["source"]["anchor"] == "subject" and "anchor" not in spec["panels"]["cut"]
