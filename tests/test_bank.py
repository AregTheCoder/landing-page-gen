"""The chrome block bank: a template is a skeleton, and a block fills one of
its slots only when its category is accepted, it can draw in the slot's shape,
its hard context holds on the page, and the worker says why it belongs."""

import yaml
from PIL import Image

from landing_page_gen.compose import bank, cli, degrade, families, models, plan, roles
from landing_page_gen.compose.families import FAMILIES

SUNBURST = "GPT Image 2.5 Sunburst"


def _picks(**fills):
    return {"fills": [{"slot": k, **v, "because": "a test"} for k, v in fills.items()]}


def _cands(p, slot):
    s = next(x for x in p["slots"] if x["id"] == slot)
    return {(c["block"], c.get("tool")) for c in s.get("candidates") or []}, {e["block"]: e["why"] for e in s.get("excluded") or []}


def test_every_block_is_of_a_category_draws_known_kinds_in_known_shapes():
    from landing_page_gen.compose import kinds
    v = bank.vocab()
    for name, b in v["blocks"].items():
        assert b["category"] in v["categories"], name
        assert b["means"] and b["when"], name
        for shape, fields in b["draw"].items():
            assert shape in v["shapes"] and fields["kind"] in kinds.KINDS, (name, shape)
        for r in b.get("requires") or []:
            assert r in {"two-states", "state", "two-pictures", "page-tool", "generator", "spec", "copy", "verb",
                         "options", "prompt", "panel"}, (name, r)
    for fam, f in FAMILIES.items():
        for variant in families.layout_names(fam):
            for sl in cli.template(fam, variant)["slots"]:
                assert sl["shape"] in v["shapes"] and set(sl["accepts"]) <= set(v["categories"]), (fam, variant, sl["id"])


def test_a_template_says_nothing_about_a_page():
    """A skeleton's slots carry geometry and look, never content: no text,
    glyph, model, tool or colours outside the exemplar record."""
    content = {"text", "icon", "model", "tool", "title", "label", "active_text", "rows_text", "colours", "items",
               "name", "caption", "sliders", "rows", "fields", "result"}
    for fam, f in FAMILIES.items():
        for variant in families.layout_names(fam):
            t = cli.template(fam, variant)
            assert "chrome" not in t, (fam, variant)
            for sl in t["slots"]:
                assert not content & set(sl), (fam, variant, sl["id"], content & set(sl))


def test_every_tool_glyph_is_drawable_and_every_page_rule_names_a_tool():
    from landing_page_gen.compose.draw import ICONS
    v = roles.vocab()
    assert {t["icon"] for t in v["tools"].values()} <= set(ICONS)
    assert all(r["tool"] in v["tools"] and r.get("degrade", "blur") in degrade.MODES for r in v["pages"])
    assert roles.page_tool("roas-calculator") == {"tool": "calculator"}


def test_the_sheet_tool_enum_is_the_tool_vocabulary():
    from landing_page_gen.corpus import attrs, label
    assert set(attrs.CHROME_TOOLS) == set(roles.vocab()["tools"]) | {"other"}
    clean, err = label._check_items([{"kind": "tile", "placement": "beside", "tool": "enhance"}])
    assert err is None and clean[0]["tool"] == "enhance"
    assert label._check_items([{"kind": "tile", "placement": "beside", "tool": "magic"}])[1]


def test_corpus_blocks_get_the_role_their_kind_and_text_settle():
    from landing_page_gen.corpus import roles as corpus_roles
    got = {t: corpus_roles.role_of(dict(kind=k, text=t)) for k, t in [
        ("pill", "Before"), ("pill", "GPT Image 1.5|Midjourney V7"), ("chip", "4K"), ("button", "Generate"),
        ("tile", "Aa Aa"), ("tile", "Grok Imagine"), ("tile", ""), ("pill", "Try it")]}
    assert got == {"Before": "state-label", "GPT Image 1.5|Midjourney V7": "attribution", "4K": "spec",
                   "Generate": "action", "Aa Aa": "derived", "Grok Imagine": "attribution", "": "tool",
                   "Try it": "action"}
    assert "state-pill" in bank.evidence_matches({"kind": "pill", "text": "Before"}, corpus_roles.role_of)
    assert bank.evidence_matches({"kind": "vs-badge", "text": "VS"}, corpus_roles.role_of) == ["vs-badge"]


def test_page_tool_and_named_tools():
    assert roles.page_tool("ai-image-enhancer--unpixelate-image") == {"tool": "enhance", "degrade": "pixelate"}
    assert roles.page_tool("birthday-card-maker") == {}
    assert roles.named_tools("Upscale it, then remove the background") == ["upscale", "remove-bg"]


def test_without_facts_a_plan_lists_slots_but_no_candidates():
    for fam, f in FAMILIES.items():
        for v in families.layout_names(fam):
            p = plan.build(fam, None, preset=v)
            assert "facts" not in p and all("candidates" not in s for s in p["slots"]), (fam, v)


def test_an_enhancer_page_offers_its_own_tool_and_the_generators_mark():
    f = roles.facts_for("ai-image-enhancer", "Enhance image quality with AI. Upscale to 4K.", generator=SUNBURST)
    p = plan.build("dark-composite", "720x720", facts=f)
    cands, excluded = _cands(p, "tile-2")
    assert {("tool-tile", "enhance"), ("tool-tile", "upscale"), ("generator-mark", None), ("palette", None)} <= cands
    assert "crop" not in {t for _, t in cands}, "a tool the page never names is never offered"
    assert "only a Gemini picture carries the sparkle" in excluded["maker-glyph"]
    picks = _picks(**{"tile-1": {"block": "generator-mark"}, "tile-2": {"block": "tool-tile", "tool": "enhance"},
                      "tile-3": {"block": "palette"}})
    assert plan.check_blocks(p, picks) == []
    items = {it["id"]: it for it in plan.picked_items(p, picks)}
    assert (items["tile-1"]["kind"], items["tile-1"]["model"]) == ("mark-tile", SUNBURST)
    assert (items["tile-2"]["icon"], items["tile-2"]["fill"]) == ("enhance", (225, 30, 224)), "the slot keeps its accent"


def test_a_page_with_no_picsart_tool_offers_no_tool_block():
    f = roles.facts_for("birthday-card-maker", "Make a birthday card", generator=SUNBURST)
    p = plan.build("dark-composite", "720x720", facts=f)
    cands, excluded = _cands(p, "tile-2")
    assert not {b for b, _ in cands} & {"tool-tile", "tool-icon"}
    assert excluded["tool-tile"] == "the page names no Picsart tool"
    crop = plan.check_blocks(p, _picks(**{"tile-1": {"block": "generator-mark"}, "tile-2": {"block": "tool-tile", "tool": "crop"},
                                          "tile-3": {"block": "palette"}}))
    assert any("shows the crop tool" in e for e in crop), "the old default crop tile is a false claim here"


def test_an_unpromised_spec_is_a_false_claim():
    f = roles.facts_for("ai-image-enhancer", "Sharper photos", generator=SUNBURST)
    p = plan.build("dark-composite", "720x720", preset="reference-thumbs", facts=f)
    four_k = _picks(**{"tile-1": {"block": "generator-mark"}, "chip": {"block": "spec-label", "text": "4K"}})
    assert plan.check_blocks(p, four_k) == [], "4K is a spec the enhance tool can honestly make"
    p = plan.build("dark-composite", "720x720", preset="reference-thumbs",
                   facts=roles.facts_for("background-remover", "Cut out any photo", generator=SUNBURST))
    assert any("'4K' is a claim" in e for e in plan.check_blocks(p, four_k))


def test_the_sparkle_is_geminis_and_only_a_gemini_picture_carries_it():
    """The template sparkle is the Gemini symbol: on a picture made on GPT Image
    2.5 Sunburst the attribution is the OpenAI mark, and made-by binds it."""
    f = roles.facts_for("roas-calculator", "What is ROAS", generator=SUNBURST)
    p = plan.build("dark-composite", "720x720", facts=f)
    sparkle = plan.check_blocks(p, _picks(**{"tile-1": {"block": "maker-glyph"}}))
    assert any("only a Gemini picture carries the sparkle" in e for e in sparkle)
    forged = bank.claim_problems({"id": "t", "kind": "tile", "icon": "sparkle", "category": "attribution"}, f,
                                 bank.context(p))
    assert any("gemini mark" in e and "openai" in e for e in forged)
    gemini = roles.facts_for("roas-calculator", "", generator="Nano Banana Pro")
    q = plan.build("dark-composite", "720x720", facts=gemini)
    [glyph] = plan.picked_items(q, _picks(**{"tile-1": {"block": "maker-glyph"}}))
    assert glyph["icon"] == "sparkle" and not bank.claim_problems(glyph, gemini, bank.context(q))
    mark = plan.picked_items(p, _picks(**{"tile-1": {"block": "generator-mark"}}))
    got = models.made_by("roas-calculator", "dark-composite", None, mark, ["photo"])
    assert got["photo"]["model"] == "gpt-image-2.5-sunburst"


def test_a_model_page_marks_its_own_model():
    f = roles.facts_for("ai-models--nano-banana-pro", "Create with Nano Banana Pro", models=["Nano Banana Pro"],
                        generator=SUNBURST)
    p = plan.build("prompt-card", "720x720", preset="column", facts=f)
    [mark] = plan.picked_items(p, _picks(mark={"block": "generator-mark"}))
    assert (mark["model"], mark["rect"]) == ("Nano Banana Pro", (0, 0, 550, 430))
    wrong = plan.check_blocks(p, _picks(mark={"block": "generator-mark", "model": SUNBURST},
                                        prompt={"block": "prompt-card", "text": "a red fox"}))
    assert any("openai mark" in e for e in wrong), "a model page's picture is the page model's"


def test_a_mark_attributes_its_panels_but_a_bare_maker_key_does_not():
    mark = {"id": "mark", "kind": "mark-tile", "category": "attribution", "model": "Nano Banana Pro"}
    got = models.made_by("ai-image-generator", "prompt-card", "column", [mark], ["photo"])
    assert got["photo"]["model"] == "gemini-3-pro-image"
    assert models.made_by("ai-image-generator", "prompt-card", "column", [{**mark, "model": "gemini"}], ["photo"]) == {}
    assert models.made_by("ai-image-generator", "prompt-card", "column",
                          [{**mark, "model": "Mystery 9"}], ["photo"])["photo"]["model"].startswith("no:")


def test_state_labels_need_two_states_and_the_right_word():
    f = roles.facts_for("ai-image-enhancer", "Before and after", generator=SUNBURST)
    lone = plan.build("before-after", "480x480", preset="pill", labels=["After"], facts=f)
    assert any("no block can honestly fill it" in e for e in plan.validate(lone)), "a lone After has no Before"
    p = plan.build("before-after", "480x480", preset="pill", labels=["After"], pair="S01-m1", facts=f)
    assert plan.validate(p) == [] and p["state"] == "after"
    [pill] = plan.picked_items(p, _picks(state={"block": "state-pill"}))
    assert (pill["text"], pill["corner"]) == ("After", "br"), "the After's pill sits bottom right"
    assert p["panels"][0]["keep_clear"][0]["frac"][0] > 0.5, "the keep-clear follows the pill to the right"
    swapped = plan.check_blocks(p, _picks(state={"block": "state-pill", "text": "Before"}))
    assert any("says 'Before' on the after panel" in e for e in swapped)


def test_the_before_is_the_after_degraded_so_only_the_after_is_generated(tmp_path):
    f = roles.facts_for("ai-image-enhancer--unpixelate-image", "", generator=SUNBURST)
    p = plan.build("before-after", "1060x504", facts=f)
    assert plan.generated_panels(p) == ["result"]
    Image.new("RGB", (800, 600), "red").save(tmp_path / "r.png")
    picks = _picks(**{"before-pill": {"block": "state-pill"}, "after-pill": {"block": "state-pill"}})
    assert plan.check_blocks(p, picks) == []
    spec = plan.to_spec(p, {"result": "r.png"}, picks)
    assert spec["panels"]["before"] == {"image": "r.png", "degrade": "pixelate", "anchor": "subject"}
    (tmp_path / "s.yaml").write_text(yaml.safe_dump(spec))
    assert cli.main([str(tmp_path / "s.yaml"), "--out", str(tmp_path / "o.png")]) == 0


def test_a_compare_slider_degrades_only_left_of_the_handle(tmp_path):
    im = Image.new("RGB", (1600, 1000))
    for x in range(0, 1600, 20):  # stripes, which a blur flattens
        im.paste((255, 255, 255), (x, 0, x + 10, 1000))
    im.save(tmp_path / "p.png")
    p = plan.build("before-after", "800x500", facts=roles.facts_for("ai-image-enhancer", "", generator=SUNBURST))
    assert p["preset"] == "compare-slider" and plan.validate(p) == []
    picks = _picks(handle={"block": "compare-handle"})
    assert plan.check_blocks(p, picks) == []
    (tmp_path / "s.yaml").write_text(yaml.safe_dump(plan.to_spec(p, {"photo": "p.png"}, picks)))
    cli.main([str(tmp_path / "s.yaml"), "--out", str(tmp_path / "o.png")])
    out = Image.open(tmp_path / "o.png").convert("L")
    band = lambda x0: [out.getpixel((x, 100)) for x in range(x0, x0 + 60)]  # noqa: E731
    assert max(band(80)) - min(band(80)) < max(band(600)) - min(band(600))


def test_degrade_modes_keep_size_and_alpha_and_are_deterministic():
    im = Image.new("RGBA", (300, 200), (200, 120, 40, 255))
    im.putpixel((0, 0), (0, 0, 0, 0))
    for mode in degrade.MODES:
        a, b = degrade.degrade(im, mode), degrade.degrade(im, mode)
        assert a.size == im.size and a.getpixel((0, 0))[3] == 0 and a.tobytes() == b.tobytes(), mode


def test_a_required_slot_no_block_can_fill_names_the_layouts_that_can():
    """roas-calculator names no Picsart tool, so the dark-composite column's
    tool box has only borrowed candidates; the bento layout is the page's own."""
    f = roles.facts_for("roas-calculator", "The ROAS formula is simple: Revenue ÷ Ad Spend. Platforms like "
                        "Google Ads, Facebook Ads and Picsart's Ad Maker.", generator=SUNBURST,
                        page_copy="Ad Spend | Ad Revenue | Your ROAS is:")
    only_tools = plan.build("crop-frame", "720x720", preset="crop-grid", facts=f)
    probs = plan.validate(only_tools)
    assert not any("crop-badge" in e and "required" in e for e in probs), "an optional slot may stay empty"
    p = plan.build("dark-composite", "720x720", preset="bento", facts=f)
    assert plan.validate(p) == []
    assert ("calculator", None) in _cands(p, "foot")[0], "the page's own tool is its calculator"
    picks = _picks(**{"card-a": {"block": "statement", "text": "Revenue ÷ Ad Spend"},
                      "card-b": {"block": "channel-list", "rows": ["Google Ads", "Facebook Ads", "Ad Maker"]},
                      "foot": {"block": "calculator", "fields": [["Ad Spend", "$ 70"], ["Ad Revenue", "$ 500"]],
                               "result": ["Your ROAS is:", "7.14"]}})
    assert plan.check_blocks(p, picks) == []
    paraphrase = plan.check_blocks(p, {**picks, "fills": [{**picks["fills"][0], "text": "Revenue / Spend"}, *picks["fills"][1:]]})
    assert any("'Revenue / Spend'" in e for e in paraphrase), "a statement is the copy's own words"


def test_timeline_layers_are_held_to_the_same_claims():
    from landing_page_gen.compose import timeline
    spec = timeline.build("enhance-reveal", "480x480", ["Removes watermarks"],
                          roles.facts_for("ai-image-enhancer", "Fix lighting"))
    assert any("never makes" in p for p in timeline.validate(spec))


def test_a_calculators_result_is_its_own_example_worked_through():
    f = roles.facts_for("roas-calculator", "ROAS measures revenue per dollar of ad spend", generator=SUNBURST,
                        page_copy="Ad Spend | Ad Revenue | Your ROAS is:")
    p = plan.build("dark-composite", "720x720", preset="bento", facts=f)

    def calc(result):
        return plan.check_blocks(p, _picks(**{
            "card-a": {"block": "statement", "text": "ROAS measures revenue per dollar of ad spend"},
            "card-b": {"block": "channel-list", "rows": ["Ad Spend"]},
            "foot": {"block": "calculator", "fields": [["Ad Spend", "$ 1,200"], ["Ad Revenue", "$ 8,400"]],
                     "result": ["Your ROAS is:", result]}}))
    assert calc("7.00") == [] and calc("7") == []
    assert any("is not computed from the fields" in e for e in calc("7.14")), "another picture's example, pasted"


def test_exemplars_carry_no_pages_words():
    """A template's exemplar is a record of what went where, not text to reuse:
    it holds generic interface labels and placeholders, never a page's copy or
    an original's example numbers (a worker once copied a record verbatim)."""
    generic = {"before", "after", "vs", "generate", "add to bag", "hsl", "hue", "saturation", "lightness", "x2",
               "4k", "high", "max", "enrich", "1 image", "", *(r.casefold() for r in ("1:1", "4:3", "3:4", "16:9", "2:3"))}
    placeholder = ("a line of", "channel ", "input ", "result",
                   # induced layouts' placeholders (compose/induce.py): shaped like the original, never its words
                   "row ", "option ", "choice ", "a choice", "a line under", "the prompt that", "label", "action", "model")
    for fam, f in FAMILIES.items():
        for variant in families.layout_names(fam):
            for it in plan.exemplar_items(fam, variant):
                for s in bank.item_strings(it) + [str(v) for fld in it.get("fields") or [] for v in fld[1:]]:
                    fold = s.casefold()
                    assert fold in generic or fold.startswith(placeholder) or fold == "0", (fam, variant, it["id"], s)
