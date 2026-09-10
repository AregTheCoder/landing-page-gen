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
