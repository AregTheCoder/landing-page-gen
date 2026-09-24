"""Generation modes: Picsart's pictures are standalone generations only where
it showcases many options side by side; elsewhere templates or layered."""
import collections
import importlib.util
import sqlite3
from pathlib import Path

import pytest

from landing_page_gen.corpus import genmode

BRIEF_PY = Path(__file__).resolve().parents[1] / ".claude" / "skills" / "build-landing-page" / "brief.py"


def test_mode_of_reads_chrome_panels_and_set_type():
    assert genmode.mode_of({"chrome": ["tile"], "panel_count": 1}) == "layered"
    assert genmode.mode_of({"panel_count": 2}) == "layered"
    assert genmode.mode_of({"before_after": True}) == "layered"
    assert genmode.mode_of({"ui_mockup": "prompt-bar"}) == "layered"
    assert genmode.mode_of({"text_in_image": "headline", "art_style": "typography"}) == "design"
    assert genmode.mode_of({"text_in_image": "none", "art_style": "photo", "chrome": ["none"]}) == "standalone"
    assert genmode.mode_of({}) is None


def table(**contexts):
    return {k.replace("__", "|"): collections.Counter(v) for k, v in contexts.items()}


def test_allowed_modes_are_the_leading_ones_to_seventy_percent():
    tab = table(**{"feature-callout__single": {"layered": 94, "standalone": 6},
                   "gallery__many__designed": {"design": 56, "layered": 38, "standalone": 6},
                   "gallery__many": {"standalone": 91, "layered": 9},
                   "hero": {"layered": 5}})  # under MIN_N: no evidence
    assert genmode.expect(tab, "feature-callout", 1)["allowed"] == ["layered"]
    maker = genmode.expect(tab, "gallery", 12, "birthday-card-maker", "tool")
    assert maker["allowed"] == ["design", "layered"] and maker["basis"] == "gallery x many x designed"
    assert genmode.expect(tab, "gallery", 12, "ai-models--flux", "ai-models")["allowed"] == ["standalone"], "backs off to type x band"
    assert genmode.expect(tab, "hero", 1)["allowed"] == list(genmode.MODES), "no evidence: every mode"


def test_a_family_fits_by_the_mode_it_makes():
    layered, gallery = {"allowed": ["layered"]}, {"allowed": ["standalone"]}
    assert not genmode.fits(layered, "full-bleed") and genmode.fits(layered, "prompt-card")
    assert genmode.fits(gallery, "full-bleed") and not genmode.fits(gallery, "dark-composite")
    design = {"allowed": ["design"]}
    assert genmode.fits(design, "full-bleed", '"Happy Birthday"') and not genmode.fits(design, "full-bleed")
    assert not genmode.fits(design, "template-mockup"), "a design inside editor chrome is layered"
    assert genmode.fits(design, "graphic-collage")


def test_the_real_corpus_keeps_bare_pictures_to_galleries_and_tutorials():
    db = Path(__file__).resolve().parents[1] / "corpus" / "corpus.db"
    if not db.exists():
        pytest.skip("no corpus.db")
    with sqlite3.connect(db) as con:
        tab = genmode.table(con)
    assert genmode.expect(tab, "feature-callout", 1, "ai-image-enhancer", "tool")["allowed"] == ["layered"]
    assert genmode.expect(tab, "hero", 1, "x", "tool")["allowed"] == ["layered"]
    assert genmode.expect(tab, "link-grid", 8, "ai-video-editor", "tool")["allowed"] == ["layered"]
    assert "standalone" in genmode.expect(tab, "gallery", 8, "ai-models--flux-2-pro", "ai-models")["allowed"]
    assert genmode.expect(tab, "tutorial-grid", 4, "ai-models--flux-2-pro", "ai-models")["allowed"] == ["standalone"]


def test_brief_refuses_a_family_of_another_mode_unless_the_slot_says_why():
    spec = importlib.util.spec_from_file_location("brief_mode", BRIEF_PY)
    brief = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(brief)
    e = {"allowed": ["layered"], "shares": {"layered": 0.9, "standalone": 0.1}, "n": 300, "basis": "link-grid x many"}
    with pytest.raises(SystemExit, match="full-bleed makes standalone"):
        brief.check_mode("S14", e, "full-bleed", "none", None)
    brief.check_mode("S14", e, "prompt-card", "none", None)
    brief.check_mode("S14", e, "full-bleed", "none", "standalone because the copy lists twelve sample outputs")
    with pytest.raises(SystemExit):
        brief.check_mode("S14", e, "full-bleed", "none", "standalone")  # an override needs its reason
