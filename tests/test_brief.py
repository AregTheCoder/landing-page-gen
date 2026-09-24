"""brief.py assembles a section brief deterministically: template headings, no
original-asset pointers, the family block verbatim, the recipe from RECIPES, the
`> device:` line intact, a blindcheck-clean result, the Stands-in-for fallback,
and a video slot."""

import importlib.util
import json
import re
import sys
from pathlib import Path

import pytest

from landing_page_gen.flow import board

BRIEF_PY = Path(__file__).resolve().parents[1] / ".claude" / "skills" / "build-landing-page" / "brief.py"


@pytest.fixture(autouse=True)
def no_mode_evidence(request, monkeypatch):
    """The fixtures' sections are not about generation modes: brief them with
    no corpus evidence (every mode allowed) unless a test asks for the corpus."""
    if "corpus_modes" not in request.keywords:
        from landing_page_gen.corpus import genmode
        monkeypatch.setattr(genmode, "load", lambda *a, **k: {})


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
  image_model: gpt-image-2.5-sunburst
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
> style: outcome-tile
> attrs: ground=dark-composite
> text: "50% OFF" | "Buy now"
> device: none: single subject

## S03 hero

- t1 h2: Watch it move

{_slot("S03-m1", kind="video", src_id="eeeeeeee", local_id="ffffffff", aspect="9:16").replace("natural: 600x600", "natural: 600x600\nduration_s: 33.74")}
> annotation: slow push in on the subject.
> style: full-bleed
> attrs: ground=photo-full-bleed
> text: none
> device: none: single subject
> duration: 34  # original 33.74 s

## S04 callout

- t1 h2: Slide to adjust

{_slot("S04-m1", src_id="99999999", local_id="88888888", aspect="4:3").replace("size: 300x300", "size: 480x360")}
> annotation: a portrait, the tool panel over the lower right.
> style: panel-overlay
> attrs: ground=photo-full-bleed
> text: none
> device: none: adjustment panel over the photo
"""


def build_run(tmp_path):
    run = tmp_path / "runs" / "brieftest"
    run.mkdir(parents=True)
    (run / "skeleton.md").write_text(SKELETON)
    slots = {"snapshot": "corpus/pages/testpage/page.html", "source": "https://example.com/testpage/",
             "slots": {}}
    for sid, sc, lc in [("S01-m1", "aaaaaaaa", "bbbbbbbb"), ("S02-m1", "cccccccc", "dddddddd"),
                        ("S03-m1", "eeeeeeee", "ffffffff"), ("S04-m1", "99999999", "88888888")]:
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
    assert "Stands in for: outcome-tile" in text
    full, _ = brief.family_block("full-bleed")
    assert full in text  # the fallback family's block (full-bleed), not outcome-tile's
    # the two text strings become a table
    assert '"50% OFF"' in text and '"Buy now"' in text and "call-to-action" in text


def test_video_slot_is_briefed_as_its_poster_family_with_a_video_section(tmp_path, brief, monkeypatch):
    run = build_run(tmp_path)
    calls = []
    monkeypatch.setattr(brief.subprocess, "run",
                        lambda cmd, **k: (calls.append(cmd), type("R", (), {"stdout": "ok", "stderr": ""})())[1])
    assert brief.main([str(run), "S03"]) == 0
    text = (run / "sections" / "S03" / "brief.md").read_text()
    assert "## Style family: full-bleed" in text
    assert "kind: video" in text  # the section block keeps the slot's kind
    assert "`kind: video`" in text and board.recipe_row("full-bleed", "video") in text
    video = text.split("## Video\n")[1].split("## Text in image")[0]
    assert "seedance-2.0-mini" in video and "seedance-2.5" in video and "generateAudio: false" in video
    # faithful to the original (34 s asked) but capped by budget.video_seconds (30 by default)
    assert "S03-m1: **30 s** (original 33.74 s; capped at budget.video_seconds 30" in video
    assert "Motion (what this family's corpus clips do):" in video and "poster:" in video and "duration_s:" in video
    similar_cmd = next(c for c in calls if "similar" in c)
    assert similar_cmd[similar_cmd.index("--kind") + 1] == "video"
    # an image section asks for no kind and gets no Video section
    calls.clear()
    assert brief.main([str(run), "S01"]) == 0
    assert "--kind" not in next(c for c in calls if "similar" in c)
    assert "## Video" not in (run / "sections" / "S01" / "brief.md").read_text()


def test_section_block_keeps_a_hyphenated_type(brief):
    text = "## S05 feature-callout\n\n- t1 h2: x\n\n## S06 how-it-works\n\n- t1 h2: y\n"
    assert brief.section_block(text, "S05")[1] == "feature-callout", "`\\w+` cut this to 'feature' and similar refused it"
    assert brief.section_block(text, "S06") == ("## S06 how-it-works\n\n- t1 h2: y", "how-it-works")


def test_target_duration_follows_the_directive_then_the_original_then_the_cap(brief):
    assert brief.target_duration({"duration_s": 8.4}, None, 30) == (8, "original 8.4 s")
    assert brief.target_duration({"duration_s": 8.4}, "12  # manager override", 30)[0] == 12
    assert brief.target_duration({}, None, 30) == (5, "no original length; 5 s default")
    assert brief.target_duration({"duration_s": 33.74}, "34", 30)[0] == 30
    assert brief.target_duration({"duration_s": 2.5}, None, 30)[0] == 4, "Seedance's floor"


def test_composition_section_lists_panels_and_keep_clear(tmp_path, brief):
    run = build_run(tmp_path)
    assert brief.main([str(run), "S04"]) == 0
    text = (run / "sections" / "S04" / "brief.md").read_text()
    assert "## Panels and keep-clear" in text
    assert "| photo | scene | 4:3 |" in text, "the real panel, what it holds and its generate ratio, not '1 panel'"
    kc = text.split("## Panels and keep-clear")[1]
    assert "panel [0.425" in kc, "the adjust panel's keep-clear region, computed not guessed"
    assert "(see below)" in text.split("## Panels")[0], "the slots table points at the panel breakdown"
    # the machine-readable composition plan is written per slot
    import yaml as _yaml
    plan_path = run / "sections" / "S04" / "composition-S04-m1.yaml"
    assert plan_path.exists() and "composition-S04-m1.yaml" in text
    cp = _yaml.safe_load(plan_path.read_text())
    assert cp["family"] == "panel-overlay" and cp["size"] == "600x450", \
        "composed at the source's resolution (natural 600x600), in the 480x360 box's shape"
    assert cp["derived_from"]["style"] == "panel-overlay"
    assert any(p["panel"] == "photo" and p["keep_clear"] for p in cp["panels"])


def _with_chrome(line, text="none"):
    """The fixture skeleton with S04 (panel-overlay) carrying a `> chrome:` line."""
    return SKELETON.replace("> text: none\n> device: none: adjustment panel over the photo",
                            f"> text: {text}\n> device: none: adjustment panel over the photo\n> chrome: {line}")


def test_the_plan_is_a_skeleton_and_the_brief_lists_each_slots_candidates(tmp_path, brief):
    import yaml as _yaml

    from landing_page_gen.compose import plan
    run = build_run(tmp_path)
    (run / "skeleton.md").write_text(_with_chrome('"Curves" | "Shadows" | "Midtones" | "Highlights"'))
    assert brief.main([str(run), "S04"]) == 0
    cp = _yaml.safe_load((run / "sections" / "S04" / "composition-S04-m1.yaml").read_text())
    assert "items" not in cp and [s["id"] for s in cp["slots"]] == ["panel"], "a callout is a card: the panel slot alone"
    assert [c["block"] for c in cp["slots"][0]["candidates"]] == ["adjust-panel"]
    assert cp["derived_from"]["chrome"].startswith('"Curves"'), "the skeleton line is recorded, so a stale plan shows"
    text = (run / "sections" / "S04" / "brief.md").read_text()
    blocks = text.split("## Blocks")[1]
    assert "slot **panel** (panel; takes tool; required)" in blocks and "**adjust-panel**" in blocks
    assert "--check-blocks composition-<slot>.yaml blocks-<slot>.yaml" in blocks
    picks = {"fills": [{"slot": "panel", "block": "adjust-panel", "title": "Curves", "because": "the copy's tool",
                        "sliders": [["Shadows", 5], ["Midtones", 0], ["Highlights", -8]]}]}
    assert plan.check_blocks(cp, picks) == [], "a `> chrome:` string may be drawn"


@pytest.mark.parametrize("line,text,match", [
    ("TODO the page strings", "none", "no resolved `> chrome:` line yet: the strings the chrome may say"),
    ('"Curves"', '"Curves"', "on both `> text:` and `> chrome:`"),
])
def test_brief_refuses_an_unresolved_or_doubled_chrome_line(tmp_path, brief, line, text, match):
    run = build_run(tmp_path)
    (run / "skeleton.md").write_text(_with_chrome(line, text))
    with pytest.raises(SystemExit, match=re.escape(match)):
        brief.main([str(run), "S04"])


def test_a_hand_edited_plan_survives_a_re_run_and_a_changed_line_needs_replan(tmp_path, brief):
    import yaml as _yaml
    run = build_run(tmp_path)
    (run / "skeleton.md").write_text(_with_chrome('"Curves"'))
    assert brief.main([str(run), "S04"]) == 0
    path = run / "sections" / "S04" / "composition-S04-m1.yaml"
    cp = _yaml.safe_load(path.read_text())
    cp["slots"][0]["rect"] = [640, 280, 1450, 880]  # the manager moves the panel off the subject
    path.write_text(_yaml.safe_dump(cp, sort_keys=False))
    assert brief.main([str(run), "S04"]) == 0
    assert _yaml.safe_load(path.read_text())["slots"][0]["rect"] == [640, 280, 1450, 880], \
        "a re-run keeps the hand-edited plan (it used to rewrite it)"
    (run / "skeleton.md").write_text(_with_chrome('"Levels"'))
    with pytest.raises(SystemExit, match="--replan"):
        brief.main([str(run), "S04"])
    assert brief.main([str(run), "S04", "--replan"]) == 0
    fresh = _yaml.safe_load(path.read_text())
    assert "rect" not in fresh["slots"][0] and fresh["labels"] == ["Levels"], "--replan rebuilds from the new line"


def test_render_size_is_the_display_box_at_the_source_resolution(brief):
    assert brief.render_size({"size": "480x480", "natural": "720x720"}) == "720x720"
    assert brief.render_size({"size": "294x196", "natural": "512x288"}) == "432x288", "object-fit crop keeps the box's shape"
    assert brief.render_size({"size": "480x480", "natural": "320x320"}) == "480x480", "never below the display box"
    assert brief.render_size({"size": "480x480"}) == "480x480"
    five_four = lambda w, h: abs((w / h) / 1.25 - 1) <= 0.02  # noqa: E731
    assert brief.render_size({"size": "342x282", "natural": "728x600"}, five_four, [(5, 4)]) == "728x582", \
        "a 5:4 layout in a 342x282 card composes at 5:4; the page trims the rest"


def test_only_generated_stills_get_a_composition_plan(tmp_path, brief):
    # an icon kept from source in a composable section used to get a plan too, which the
    # size check then refused (42x48 fits no layout), stopping the whole brief
    run = build_run(tmp_path)
    icon = _slot("S04-m2", src_id="77777777", local_id="66666666").replace("role: creative", "role: icon") \
        .replace("size: 300x300", "size: 42x48")
    (run / "skeleton.md").write_text(SKELETON.replace("> device: none: adjustment panel over the photo\n",
                                                      "> device: none: adjustment panel over the photo\n\n" + icon + "\n"))
    assert brief.main([str(run), "S04"]) == 0
    sec = run / "sections" / "S04"
    assert [p.name for p in sec.glob("composition-*.yaml")] == ["composition-S04-m1.yaml"]
    assert "| S04-m2 | image | icon | 42x48 |" in (sec / "brief.md").read_text()
    assert "kept from source" in (sec / "brief.md").read_text().split("| S04-m2 |")[1].split("\n")[0]


def test_preset_falls_to_the_variant_the_slot_size_fits(brief):
    # before-after's default is the wide 21:10 card; a 1:1 slot with no device
    # is briefed (panels table, slot count, composition plan) as stacked-square
    assert brief._preset("before-after", "none", "480x480") == "stacked-square"
    assert brief._preset("before-after", "none", "720x343") is None
    assert brief._preset("dark-composite", "model-picker", "480x480") == "model-picker", "the device still wins"
    rows = brief.composition_section("before-after", "none", "480x480")
    assert "| after |" in rows and "| after |" not in brief.composition_section("before-after", "none", "720x343")
    # a section whose slots need different presets: each slot counts its own panels and
    # each preset gets its own table, so the brief agrees with the per-slot plans
    records = [{"id": "S07-m1", "size": "720x343", "role": "creative"}, {"id": "S07-m2", "size": "480x480", "role": "creative"}]
    table = brief.slots_table(records, "feature-callout", "before-after", "none")
    assert "| S07-m1 |" in table and "2 panels" in table.split("| S07-m2 |")[0]
    assert "3 panels" in table.split("| S07-m2 |")[1], "the 1:1 slot's stacked-square has before, after, result"
    mixed = brief.composition_section("before-after", "none", sizes=[(r["id"], r["size"]) for r in records])
    assert "Slots S07-m1 (default layout):" in mixed and "Slots S07-m2 (stacked-square layout):" in mixed
    assert mixed.count("| panel | holds | generate at |") == 2 and "| after |" in mixed.split("S07-m2")[1]
    same = brief.composition_section("before-after", "none", sizes=[("S07-m1", "720x343"), ("S07-m3", "879x418")])
    assert same == brief.composition_section("before-after", "none", "720x343"), "one preset: the one-table brief, unchanged"


def test_one_slot_of_a_section_is_briefed_with_its_own_lines():
    brief = load_brief()
    block = ("## S09 tutorial-grid\n\n- t1 h2: Guides\n\n"
             "```slot\nid: S09-m1\nkind: image\n```\n> annotation: TODO\n> device: TODO none | two-up\n\n"
             "```slot\nid: S09-m2\nkind: image\n```\n> annotation: a desk\n> device: none: a planning desk\n")
    got = brief.only_slot(block, "S09-m2")
    assert "S09-m1" not in got and "- t1 h2: Guides" in got
    assert brief.directives(got)["device"] == "none: a planning desk"  # not the first slot's TODO
    with pytest.raises(SystemExit):
        brief.only_slot(block, "S09-m9")


def test_a_family_that_is_never_generated_is_refused_at_the_brief():
    brief = load_brief()
    assert brief.never_generated(brief.family_block("editor-canvas")[0])
    assert brief.never_generated(brief.family_block("model-card")[0])
    assert not brief.never_generated(brief.family_block("full-bleed")[0])


def test_a_blind_block_carries_nothing_read_off_the_original():
    brief = load_brief()
    block = ("## S09 tutorial-grid\n\n- t1 h2: Guides\n\n"
             "```slot\nid: S09-m2\nkind: image\nrole: thumbnail\n```\n"
             "> annotation: an overhead desk\n> style: full-bleed\n> attrs: ground=photo-full-bleed\n"
             "> prior: style full-bleed 99 %\n> text: none\n> device: none: a desk\n> chrome: none\n")
    blind = brief.blind_block(block)
    assert "desk" not in blind and "attrs" not in blind and "> style" not in blind
    assert "> prior: style full-bleed 99 %" in blind  # corpus-wide advice is context, not the original
    got = brief.blind_block(block, {"S09-m2": {"style": "full-bleed", "annotation": "a laptop", "text": "none"}})
    assert brief.directives(got)["annotation"] == "a laptop" and "desk" not in got


def test_a_proposal_whose_value_carries_a_colon_still_reads():
    brief = load_brief()
    got = brief.read_proposal("style: full-bleed\ndevice: none: one frame of a clip\nannotation: >-\n  a woman\n  at dusk\ntext: none\n")
    assert got["device"] == "none: one frame of a clip" and got["annotation"] == "a woman at dusk" and got["text"] == "none"
    assert brief.read_proposal('style: full-bleed\ndevice: "none: quoted"\n')["device"] == "none: quoted"


def test_proposal_brief_names_the_families_with_a_layout_at_the_slot_size():
    """blind-2-4 proposed mockup-card for a 16:10 card; no mockup-card layout takes it."""
    brief = load_brief()
    fit = brief.families_that_fit("800x501")
    assert "mockup-card" not in fit and "prompt-card" in fit and "full-bleed" in fit
    assert "mockup-card" in brief.families_that_fit("480x480")
    assert not {"editor-canvas", "model-card"} & set(fit), "never-generated families are not offered"


def test_the_proposal_offers_layouts_by_panels_and_slots_never_by_original():
    """blind-2: three plans fell back to a default layout that could not show the
    proposed device; the proposal now picks the layout from this menu."""
    brief = load_brief()
    menu = brief.layouts_menu("480x480", ["template-mockup", "full-bleed"])
    assert "`default`: 1 panel" in menu and "`editor`:" in menu and "full-bleed" not in menu
    assert "original" not in menu and not re.search(r"\b[0-9a-f]{8}\b", menu), "a layout is described, never its source"
