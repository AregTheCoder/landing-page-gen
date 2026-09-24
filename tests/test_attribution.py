"""A picture a page presents as a named model's output is made on that model:
compose.models.made_by names it, lp-flow check enforces it down the lineage."""

from landing_page_gen.compose import models
from landing_page_gen.flow import board


def test_pages_and_pickers_name_the_model_each_panel_must_come_from():
    page = models.made_by("ai-models--recraft-v4-styles-pro-vector", panels=["photo", "thumb-a"])
    assert {r["model"] for r in page.values()} == {"recraftv4_styles_pro_vector"}
    assert models.made_by("ai-models--nano-banana-pro")["*"]["model"] == "gemini-3-pro-image", "a slug alias"
    vs = models.made_by("compare-models--gpt-image-1-5-vs-flux-2-pro", "vs-two-up", panels=["left", "right"])
    assert (vs["left"]["model"], vs["right"]["model"]) == ("gpt-image-1.5", "flux-2-pro")
    picker = models.made_by("ai-image-generator", "dark-composite", "model-picker",
                            [{"kind": "list-panel", "active_text": "Seedream 5.0 Pro"}], ["photo"])
    assert picker["photo"]["model"] == "seedream-5.0-pro"
    assert models.made_by("hsl-color", "panel-overlay", panels=["photo"]) == {}, "a tool page attributes nothing"
    assert models.made_by("ai-models--lyria-3") == {}, "an audio model's page is illustrated"
    assert models.made_by("ai-models--midjourney")["*"]["model"].startswith("no:"), "not on the connector"
    assert "not mapped" in models.made_by("ai-models--kling")["*"]["model"], "ambiguous slugs are never guessed"


def _board(models_by_step, panels=None):
    steps = [{"id": i + 1, "node": "image", "in": ["start"] if i % 2 == 0 else [i], "tool": "picsart_generate",
              "model": m} for i, m in enumerate(models_by_step)]
    for sid, name in (panels or {}).items():
        steps[sid - 1]["panel"] = name
    steps.append({"id": len(steps) + 1, "node": "compose", "in": [s["id"] for s in steps], "tool": "lp-compose"})
    return {"slot": "S01-m1", "steps": steps, "final": {}}


def test_lp_flow_check_holds_every_generative_node_upstream_of_a_panel_to_its_model():
    req = {"photo": {"model": "recraftv4", "because": "page"}, "thumb-a": {"model": "recraftv4", "because": "page"}}
    ok = _board(["recraftv4", "recraftv4", "recraftv4", "recraftv4"], {2: "photo", 4: "thumb-a"})
    assert board.attribution_problems(ok, req) == []
    assert not [p for p in board.check(ok, req) if "without a reason" in p], "an attributed model needs no reason"
    refined = _board(["recraftv4", "gemini-3-pro-image", "recraftv4", "recraftv4"], {2: "photo", 4: "thumb-a"})
    assert any("node 2" in p and "recraftv4's output" in p for p in board.attribution_problems(refined, req))
    unmarked = _board(["recraftv4"] * 4)
    assert any("no node marks `panel: photo`" in p for p in board.attribution_problems(unmarked, req))
    whole = _board(["recraftv4", "gemini-3-pro-image"])
    assert board.attribution_problems(whole, {"*": {"model": "recraftv4", "because": "page"}})
    cannot = board.attribution_problems(ok, {"*": {"model": "no: midjourney is not on the connector", "because": "page"}})
    assert cannot and "cannot be generated truthfully" in cannot[0]


def test_a_prompt_cards_inputs_are_not_the_models_output():
    from landing_page_gen.compose import plan
    card = {"family": "prompt-card", "preset": "m-01ff9e", "facts": {"page": "ai-models--sora-2"},
            "panels": [{"panel": "photo"}, {"panel": "photo-2"}, {"panel": "photo-3"}]}
    assert plan.claimed_panels(card) == ["photo-3"]  # the result; the reference clip and photo are the user's
    assert set(plan.made_by(card, None)) == {"photo-3"}
    other = {"family": "dark-composite", "panels": [{"panel": "photo"}, {"panel": "photo-2"}]}
    assert plan.claimed_panels(other) == ["photo", "photo-2"]
