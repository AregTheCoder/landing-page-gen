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
            {"id": 1, "node": "image", "in": ["start"], "tool": "picsart_generate", "model": "gemini-3-pro-image",
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
    en["model"] = "gemini-3-pro-image"  # a plain generate is NOT an enhance
    problems = board.check(doc)
    assert any("enhance node on picsart_generate" in p for p in problems)
    # the message names the workaround, so a worker need not read board.py source
    assert any("topaz-upscale-image" in p for p in problems)


def board_of(family, kinds):
    """A minimal wired board of the given node kinds, tagged with a family, so
    the planned-recipe check can be exercised."""
    steps = []
    for i, k in enumerate(kinds, 1):
        tool = next(iter(board.NODE_ENGINES[k]), None)
        steps.append({"id": i, "node": k, "in": ["start"] if i == 1 else [i - 1],
                      "tool": tool, "model": "gemini-3-pro-image" if k == "image" else None,
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
    assert "| 1 | image | picsart_generate | gemini-3-pro-image | start |" in text
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
