import json

import yaml

from landing_page_gen.corpus import poolindex, pool


def _entry(**kw):
    base = dict(state="pending", best_family="outcome-tile", searched_family="outcome-tile",
                aspect_class="3:4", score=0.6, composition="bare", licence="pexels",
                creator="A", url="u", image="i")
    base.update(kw)
    return base


def _write_pool(tmp, entries):
    (tmp / "outcome-tile.yaml").write_text(yaml.safe_dump(
        {"family": "outcome-tile", "entries": entries}))


def test_merge_writes_descriptions_into_the_yaml_and_skips_orphans(tmp_path):
    _write_pool(tmp_path, {"pexels-1": _entry(), "pexels-2": _entry(score=0.4)})
    jsonl = tmp_path / "d.jsonl"
    jsonl.write_text("\n".join(json.dumps(r) for r in [
        {"id": "pexels-1", "description": "A single cupcake on a white plate.<pad><pad>"},
        {"id": "pexels-2", "description": "A yellow bottle on a white surface."},
        {"id": "pexels-999", "description": "orphan, no entry"}]))
    stats = poolindex.merge_descriptions(jsonl, pool_dir=tmp_path, log=lambda m: None)
    assert stats == {"set": 2, "ids": 3, "orphans": 1}
    data = pool.load("outcome-tile", tmp_path)
    # the <pad> leak is cleaned on the way in
    assert data["entries"]["pexels-1"]["description"] == "A single cupcake on a white plate."


def test_build_and_find_rank_by_text_match_then_score(tmp_path):
    _write_pool(tmp_path, {
        "pexels-1": _entry(description="A single cupcake with pink frosting on a white plate."),
        "pexels-2": _entry(description="A yellow bottle on a white background.", score=0.9),
        "pexels-3": _entry(description="A cupcake tray, chocolate cupcakes, white surface.", score=0.5)})
    got = poolindex.build(pool_dir=tmp_path, log=lambda m: None)
    assert got == {"rows": 3, "with_description": 3}

    # a content query ranks the best text match first; OR-matching still lets a
    # partial hit ("white") appear, but the cupcake images outrank the bottle
    hits = poolindex.find(need="cupcake white plate", state=("pending",), pool_dir=tmp_path)
    ids = [h["id"] for h in hits]
    assert ids[0] == "pexels-1"
    assert ids.index("pexels-1") < ids.index("pexels-2")
    assert ids.index("pexels-3") < ids.index("pexels-2")

    # no need -> pure score order; the bottle (0.9) leads
    hits = poolindex.find(need=None, state=("pending",), pool_dir=tmp_path)
    assert [h["id"] for h in hits][0] == "pexels-2"

    # hard filters: aspect + family + state
    assert poolindex.find(aspect="16:9", state=("pending",), pool_dir=tmp_path) == []
    assert poolindex.find(state=("kept",), pool_dir=tmp_path) == []
