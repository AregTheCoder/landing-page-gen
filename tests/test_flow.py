"""A workflow.yaml read as a Picsart Flow board: START -> nodes -> END."""
from pathlib import Path

import yaml

from landing_page_gen.flow import board, cli

PROMPT = "a red cup on a yellow seamless, no other text, no logos or watermarks"


def blank_board(**over):
    doc = {
        "slot": "S03-m1", "kind": "image", "board": "blank", "pattern": "anchored",
        "start": {"inputs": [{"id": "ref-hero", "kind": "ref", "url": "https://x/hero.png"}], "text": []},
        "steps": [
            {"id": 1, "node": "image", "in": ["start"], "tool": "picsart_generate", "model": "gpt-image-2.5-sunburst",
             "params": {"prompt": PROMPT, "aspectRatio": "4:3", "count": 1}, "quoted_credits": 5,
             "gate": "one cup, centred", "status": "done", "note": "one cup", "outputs": ["https://x/1.png"], "passed": "https://x/1.png"},
            {"id": 2, "node": "edit", "in": [1], "tool": "picsart_generate", "model": "picsart-qwen-image-edit",
             "params": {"prompt": "remove the saucer", "imageUrls": ["<step 1 passed>"]}, "quoted_credits": 4,
             "gate": "saucer gone", "status": "pending", "outputs": [], "passed": None, "note": ""},
        ],
        "final": {"url": None, "local": None}, "credits": {"quoted": 9, "spent": 5},
    }
    doc.update(over)
    return doc


def test_blank_board_wires():
    assert board.check(blank_board()) == []


def test_template_board_needs_its_source():
    problems = board.check(blank_board(board="template", template={"title": "Ethereal Studio Motion"}))
    assert any("template.url" in p for p in problems) and any("template.adapted" in p for p in problems)
    assert board.check(blank_board(board="template", template={
        "title": "Ethereal Studio Motion", "url": "https://picsart.com/workflows/", "adapted": "dropped the video leg"})) == []


def test_node_fed_by_a_later_node_or_wrong_engine_fails():
    doc = blank_board()
    doc["steps"][0]["in"] = [2]
    doc["steps"][1]["tool"] = "picsart_enhance"
    problems = board.check(doc)
    assert any("fed by node 2" in p for p in problems)
    assert any("edit node on picsart_enhance" in p for p in problems)


def test_enhance_via_generate_is_accepted_only_for_upscale_models():
    doc = board_of("full-bleed", ["image", "image", "enhance"])
    en = doc["steps"][2]
    en["tool"], en["model"] = "picsart_generate", "topaz-upscale-image"  # Drive-403 workaround
    assert board.check(doc) == []
    en["model"] = "gpt-image-2.5-sunburst"  # a plain generate is NOT an enhance
    problems = board.check(doc)
    assert any("enhance node on picsart_generate" in p for p in problems)
    # the message names the workaround, so a worker need not read board.py source
    assert any("topaz-upscale-image" in p for p in problems)


def test_cutout_via_generate_is_accepted_on_the_segmenter():
    """picsart_remove_bg 403s on Drive auto-save (blind-1-4): the segmenter runs
    through picsart_generate with saveToDrive:false, typed a cutout still."""
    doc = board_of("cutout-checkerboard", ["image", "cutout", "compose"])
    cut = doc["steps"][1]
    cut["tool"], cut["model"] = "picsart_generate", "picsart-sod-v8-2"
    assert board.check(doc) == []
    cut["model"] = "gpt-image-2.5-sunburst"
    assert any("cutout node on picsart_generate" in p for p in board.check(doc))


def board_of(family, kinds):
    """A minimal wired board of the given node kinds, tagged with a family, so
    the planned-recipe check can be exercised."""
    steps = []
    for i, k in enumerate(kinds, 1):
        tool = next(iter(board.NODE_ENGINES[k]), None)
        steps.append({"id": i, "node": k, "in": ["start"] if i == 1 else [i - 1],
                      "tool": tool, "model": "gpt-image-2.5-sunburst" if k == "image" else None,
                      "params": {"prompt": PROMPT} if k == "image" else {}, "quoted_credits": 5,
                      "gate": "ok", "status": "done"})
    return {"slot": "S01-m1", "board": "blank", "family": family, "steps": steps,
            "final": {"url": "https://x/f.png"}}


def test_recipe_flags_a_shallow_board():
    """full-bleed plans generate -> i2i refine -> enhance; a lone generate fails."""
    problems = board.check(board_of("full-bleed", ["image"]))
    assert any("plans 2 image nodes" in p for p in problems)
    assert any("plans a enhance node" in p for p in problems)


def test_recipe_passes_when_the_plan_is_realised():
    assert board.check(board_of("full-bleed", ["image", "image", "enhance"])) == []
    assert board.check(board_of("template-mockup", ["image", "image", "compose"])) == []


def test_recipe_flags_a_missing_family_specific_step():
    problems = board.check(board_of("template-mockup", ["image", "image"]))
    assert any("plans a compose node" in p for p in problems)
    # before-after's derived "after" step accepts an edit/enhance/cutout node
    assert board.check(board_of("before-after", ["image", "enhance", "compose"])) == []
    assert any("background or cutout or enhance" in p
               for p in board.check(board_of("before-after", ["image", "compose"])))


def test_recipe_only_enforced_when_family_is_known():
    assert board.check(board_of("full-bleed", ["image"]))          # known -> flagged
    assert board.check({"slot": "S1", "board": "blank", "steps": board_of("x", ["image"])["steps"],
                        "final": {"url": "u"}}) == []               # no family -> not enforced


def video_node(i, model, upstream, **params):
    p = {"prompt": PROMPT, "aspectRatio": "1:1", "resolution": "720p", "duration": 5,
         "generateAudio": False, "async": True, "extra": {"startFrame": f"<step {upstream} passed>"}}
    p.update(params)
    return {"id": i, "node": "video", "in": [upstream], "tool": "picsart_generate", "model": model,
            "params": p, "quoted_credits": 10, "gate": "first frame equals the still", "status": "done"}


def video_board():
    """full-bleed still recipe then the two planned video nodes: mini draft, final."""
    doc = board_of("full-bleed", ["image", "image", "enhance"])
    doc["kind"] = "video"
    doc["steps"] += [video_node(4, "seedance-2.0-mini", 3), video_node(5, "seedance-2.5", 3)]
    return doc


def test_video_recipe_is_the_still_recipe_plus_draft_and_final():
    assert board.recipe_row("full-bleed", "video") == "generate -> i2i refine -> enhance -> video draft (mini) -> video final"
    assert board.recipe_row("full-bleed") == "generate -> i2i refine -> enhance"
    assert board.check(video_board()) == []
    shallow = video_board()
    shallow["steps"].pop()  # final missing
    assert any("plans a video node (a mini draft and a final" in p for p in board.check(shallow))
    # a record without kind: is a video board when it has a video node
    doc = video_board()
    doc.pop("kind")
    assert board.board_kind(doc) == "video" and board.check(doc) == []


def test_video_node_non_negotiables_are_checked_on_the_yaml():
    def problems(**over):
        doc = video_board()
        doc["steps"][4]["params"].update(over)
        return board.check(doc)
    assert any("generateAudio: false" in p for p in problems(generateAudio=True))
    assert any("async: true" in p for p in problems(**{"async": False}))
    assert any("wires imageUrls" in p for p in problems(imageUrls=["https://x/ref.png"]))
    assert any("above Seedance's 30 s" in p for p in problems(duration=45))
    assert any("literal URL" in p for p in problems(extra={"startFrame": "https://x/3.png"}))
    assert any("not an earlier still node" in p for p in problems(extra={"startFrame": "<step 4 passed>"}))
    assert any("but in: does not" in p for p in problems(extra={"startFrame": "<step 2 passed>"}))
    assert any("text-to-motion is not a recipe" in p for p in problems(extra={}))
    # the final before any mini draft
    doc = video_board()
    doc["steps"][3]["model"] = "seedance-2.5"
    assert any("before a mini draft node" in p for p in board.check(doc))
    # an extend node takes the earlier clip by reference, and a loop closes on the still
    doc = video_board()
    doc["steps"][4]["params"]["extra"]["endFrame"] = "<step 3 passed>"
    doc["steps"].append(video_node(6, "seedance-2.5-video-extend", 5, extra={}, videoUrls=["<step 5 passed>"]))
    assert board.check(doc) == []
    doc["steps"][5]["params"]["videoUrls"] = ["<step 3 passed>"]
    assert any("not an earlier video node" in p for p in board.check(doc))


def test_image_node_off_the_pro_model_needs_a_reason():
    doc = blank_board()
    doc["steps"][0]["model"] = "gemini-3.1-flash-image"
    assert any("without a reason" in p for p in board.check(doc))
    doc["steps"][0]["reason"] = 'section copy: "This image was generated with Gemini Flash"'
    assert board.check(doc) == []


def test_hybrid_chrome_item_and_ui_word_gate():
    # a plain edit node whose prompt names UI furniture, with no chrome_item, is smuggling chrome
    doc = blank_board()
    doc["steps"][1]["params"]["prompt"] = "add a translucent slider over the photo"
    assert any("prompt names UI (slider)" in p for p in board.check(doc))
    # claim it as a hybrid item on a generate/edit node with a reason: clean
    doc["steps"][1]["chrome_item"] = "mask"
    doc["steps"][1]["reason"] = "the brushed selection region is organic, not templatable"
    assert board.check(doc) == []
    # chrome_item without a reason, or on a non-image/edit node, both fail
    doc["steps"][1].pop("reason")
    assert any("without a reason" in p for p in board.check(doc))
    doc2 = board_of("full-bleed", ["image", "image", "enhance"])
    doc2["steps"][2]["chrome_item"] = "mark"
    doc2["steps"][2]["reason"] = "applied on packaging"
    assert any("chrome_item 'mark' on a enhance node" in p for p in board.check(doc2))


def test_legacy_record_is_inferred():
    doc = blank_board()
    for s in doc["steps"]:
        s.pop("node"), s.pop("in")
    doc.pop("board"), doc.pop("start")
    ns = board.nodes(doc)
    assert [n["node"] for n in ns] == ["image", "edit"]
    assert ns[0]["in"] == ["start"] and ns[1]["in"] == [1]
    assert board.check(doc) == []
    doc["steps"].append({"id": 3, "tool": "lp-compose", "params": {"spec": "compose-S03-m1.yaml"}, "gate": "panels unstretched"})
    assert board.nodes(doc)[2]["node"] == "compose" and board.nodes(doc)[2]["in"] == [2]


def test_sheet_renders_graph_and_node_rows(tmp_path):
    text = board.sheet([blank_board()])
    assert "flowchart LR" in text and "start --> n1" in text and "n1 --> n2" in text and "n2 --> end_" in text
    assert "| 1 | image | picsart_generate | gpt-image-2.5-sunburst | start |" in text
    assert "| 2 | edit | picsart_generate | picsart-qwen-image-edit | 1 |" in text
    wf = tmp_path / "workflow.yaml"
    wf.write_text(yaml.safe_dump(blank_board()))
    assert cli.main(["sheet", str(wf)]) == 0
    assert (tmp_path / "flow.md").read_text().startswith("# Flow board")
    assert cli.main(["check", str(wf)]) == 0


def test_templates_search(tmp_path):
    cat = tmp_path / "flow-templates.yaml"
    cat.write_text(yaml.safe_dump({"templates": [
        {"title": "Ethereal Studio Motion", "category": "E-commerce & product content", "tags": ["packshot"],
         "description": "packshot into a studio scene", "shape": "REF -> Image -> END",
         "fits": {"families": ["template-mockup"], "devices": ["applied-mockup"]}},
        {"title": "Relight", "category": "Video & motion", "tags": ["relight"], "description": "photo to video",
         "fits": {"families": ["cinematic-still"], "devices": ["none"]}},
    ]}))
    hits = board.find_templates(family="template-mockup", device="applied-mockup", path=cat)
    assert [t["title"] for t in hits] == ["Ethereal Studio Motion"]
    assert board.find_templates(family="full-bleed", query="relight", path=cat)[0]["title"] == "Relight"
    assert board.find_templates(family="full-bleed", path=cat) == []
    assert cli.main(["templates", "--family", "before-after", "--catalogue", str(cat)]) == 1


def test_shipped_catalogue_is_valid():
    ts = board.load_templates(Path(__file__).resolve().parents[1] / "corpus" / "flow-templates.yaml")
    assert ts, "corpus/flow-templates.yaml lists no templates"
    for t in ts:
        for key in ("title", "url", "category", "shape", "fits"):
            assert t.get(key) is not None, f"{t.get('title')}: {key} missing"


def timeline_board():
    """A templated callout clip: the poster family's still recipe, then one
    lp-compose motion node that renders the brief's motion spec."""
    doc = board_of("full-bleed", ["image", "image", "enhance"])
    doc["kind"] = "timeline"
    doc["steps"].append({"id": 4, "node": "motion", "in": [3], "tool": "lp-compose", "timeline": "motion-S01-m1.yaml",
                         "params": {}, "quoted_credits": 0, "gate": "strip reads the preset", "status": "done"})
    return doc


def test_timeline_recipe_is_the_still_recipe_plus_one_motion_node():
    assert board.recipe_row("full-bleed", "timeline") == "generate -> i2i refine -> enhance -> timeline (lp-compose --timeline)"
    assert board.recipe_row("dark-composite", "timeline") == "generate -> i2i refine -> timeline (lp-compose --timeline)"
    assert board.check(timeline_board()) == []
    no_spec = timeline_board()
    no_spec["steps"][-1].pop("timeline")
    assert any("names its motion spec" in p for p in board.check(no_spec))
    shallow = timeline_board()
    shallow["steps"].pop()
    assert any("plans a motion node" in p for p in board.check(shallow))


def test_a_still_from_a_video_models_clip_is_that_models_output():
    # qa-live-2 S06: the Sora page's result is a frame of a real sora-2 clip that starts from an image-model still
    doc = board_of("full-bleed", ["image", "image", "enhance"])
    doc["kind"] = "image"  # a still slot: its one video node is the source of a frame, not the slot's clip
    clip = video_node(4, "sora-2", 3, extra={}, imageUrls=["<step 3 passed>"])  # sora-2 takes its start still here
    frame = {"id": 5, "node": "compose", "in": [4], "tool": "lp-compose", "model": "lp-compose", "panel": "photo-3",
             "params": {}, "quoted_credits": 0, "gate": "the middle frame", "status": "done"}
    doc["steps"] += [clip, frame]
    req = {"photo-3": {"model": "sora-2", "because": "the page presents it as Sora 2's output"}}
    assert board.check(doc, req) == []  # no draft tier to draft on; the start still is the clip's input, not its lineage
    doc["steps"][3]["params"]["imageUrls"] = ["https://x/still.png"]
    assert any("literal URL" in p for p in board.check(doc, req))
    doc["steps"][3]["model"] = "seedance-2.5"  # a Seedance final still drafts first and takes extra.startFrame
    assert any("before a mini draft node" in p for p in board.check(doc))
