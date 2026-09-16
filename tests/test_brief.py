"""brief.py assembles a section brief deterministically: template headings, no
original-asset pointers, the family block verbatim, the recipe from RECIPES, the
`> device:` line intact, a blindcheck-clean result, the Stands-in-for fallback,
and a video slot."""

import importlib.util
import json
import sys
from pathlib import Path

import pytest

from landing_page_gen.flow import board

BRIEF_PY = Path(__file__).resolve().parents[1] / ".claude" / "skills" / "build-landing-page" / "brief.py"


def load_brief():
    sys.path.insert(0, str(BRIEF_PY.parent))
    spec = importlib.util.spec_from_file_location("brief_mod", BRIEF_PY)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _slot(sid, kind="image", src_id="aaaaaaaa", local_id="bbbbbbbb", aspect="1:1"):
    return (
        f"```slot\n"
        f"id: {sid}\nkind: {kind}\nrole: creative\nsize: 300x300\nsize_class: tile\n"
        f"aspect: '{aspect}'\naspect_class: '{aspect}'\nnatural: 600x600\n"
        f"src: https://cdn.example.com/{src_id}-1111-2222-3333-444444444444.avif\n"
        f"local: corpus/pages/testpage/media/{src_id}-1111-2222-3333-444444444444-{local_id}.avif\n"
        f"```"
    )


SKELETON = f"""---
page: testpage
source: https://example.com/testpage/
snapshot: corpus/pages/testpage/page.html
brand: Picsart
audience: ''
defaults:
  image_model: gemini-3-pro-image
budget:
  run_credits: 200
  image_slot: 40
  video_slot: 90
notes: ''
---

# Test page

## S01 hero

- t1 h1: Make something great with the tool
- t2 p: A short body sentence about the thing it does.

{_slot("S01-m1")}
> annotation: one person on a seamless, even studio light.
> style: full-bleed
> attrs: ground=photo-full-bleed
> text: none
> device: none: single subject, no demonstration device

## S02 callout

- t1 h2: A prompt becomes a picture

{_slot("S02-m1", src_id="cccccccc", local_id="dddddddd")}
> annotation: a product on a dark card.
> style: prompt-card
> attrs: ground=dark-composite
> text: "50% OFF" | "Buy now"
> device: none: single subject

## S03 hero

- t1 h2: Watch it move

{_slot("S03-m1", kind="video", src_id="eeeeeeee", local_id="ffffffff", aspect="9:16")}
> annotation: slow push in on the subject.
> style: full-bleed
> attrs: ground=photo-full-bleed
> text: none
> device: none: single subject
"""


def build_run(tmp_path):
    run = tmp_path / "runs" / "brieftest"
    run.mkdir(parents=True)
    (run / "skeleton.md").write_text(SKELETON)
    slots = {"snapshot": "corpus/pages/testpage/page.html", "source": "https://example.com/testpage/",
             "slots": {}}
    for sid, sc, lc in [("S01-m1", "aaaaaaaa", "bbbbbbbb"), ("S02-m1", "cccccccc", "dddddddd"),
                        ("S03-m1", "eeeeeeee", "ffffffff")]:
        slots["slots"][sid] = {"src": f"https://cdn.example.com/{sc}-1111-2222-3333-444444444444.avif",
                               "local": f"x/{sc}-1111-2222-3333-444444444444-{lc}.avif"}
    (run / "slots.json").write_text(json.dumps(slots))
    (run / "budget.json").write_text(json.dumps({"dry_run": False}))
    return run


@pytest.fixture
def brief(monkeypatch):
    mod = load_brief()
    # stub the two helper commands so the test does not touch the corpus or network
    monkeypatch.setattr(mod.subprocess, "run",
                        lambda *a, **k: type("R", (), {"stdout": "start from a blank board", "stderr": ""})())
    return mod


def test_headings_recipe_device_and_no_pointers(tmp_path, brief):
    run = build_run(tmp_path)
    assert brief.main([str(run), "S01"]) == 0  # writes and passes blindcheck
    text = (run / "sections" / "S01" / "brief.md").read_text()

    for heading in ("## Page context", "## Section (verbatim from skeleton.md)", "## Style family: full-bleed",
                    "## Flow board", "## Text in image", "## Slots to produce",
                    "## Examples from the corpus", "## References", "## Shared context",
                    "## Budget", "## Output contract"):
        assert heading in text, heading

    section = text.split("## Style family")[0]
    for line in section.splitlines():
        assert not line.strip().startswith(("src:", "local:", "alt:")), line
    assert "source:" not in text and "snapshot:" not in text  # page context strips them

    # the family block is verbatim (minus the n= placeholders) and the recipe
    # comes from RECIPES, not a hand-typed table
    fam, stands_in = brief.family_block("full-bleed")
    assert stands_in is None and fam in text
    assert board.recipe_row("full-bleed") in text
    assert "> device: none: single subject, no demonstration device" in text
    # the Slots-to-produce class is <section type>-<aspect_class>
    slots_table = text.split("## Slots to produce")[1].split("## Examples")[0]
    assert "| hero-1:1 |" in slots_table


def test_stands_in_for_fallback_uses_the_named_family(tmp_path, brief):
    run = build_run(tmp_path)
    assert brief.main([str(run), "S02"]) == 0
    text = (run / "sections" / "S02" / "brief.md").read_text()
    assert "Stands in for: prompt-card" in text
    dark, _ = brief.family_block("dark-composite")
    assert dark in text  # the fallback family's block, not prompt-card's
    # the two text strings become a table
    assert '"50% OFF"' in text and '"Buy now"' in text and "call-to-action" in text


def test_video_slot_is_briefed_as_its_poster_family(tmp_path, brief):
    run = build_run(tmp_path)
    assert brief.main([str(run), "S03"]) == 0
    text = (run / "sections" / "S03" / "brief.md").read_text()
    assert "## Style family: full-bleed" in text
    assert "kind: video" in text  # the section block keeps the slot's kind
