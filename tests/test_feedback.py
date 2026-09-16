"""The feedback loop: a run's benchmark family-mismatch flags on provisional
originals become a re-label queue that jumps the labelling line."""

import json

from landing_page_gen.corpus import feedback, sheets


def test_suspect_originals_only_provisional_resemblance(tmp_path):
    run = tmp_path / "run"
    run.mkdir()
    (run / "slots.json").write_text(json.dumps({"slots": {
        "S01-m1": {"src": "https://cdn.x/aaa.png"},   # provisional (chrome None) + resemblance -> suspect
        "S02-m1": {"src": "https://cdn.x/bbb.png"},   # chrome answered -> the tag is trusted, not suspect
        "S03-m1": {"src": "https://cdn.x/ccc.png"},   # flagged, but geometry not resemblance
    }}))
    (run / "benchmark.md").write_text(
        "## Flags\n\n"
        "- S01-m1 (hero): family full-bleed -> unresolved [resemblance]\n"
        "- S02-m1 (hero): family full-bleed -> dark-composite [resemblance]\n"
        "- S03-m1 (gallery): subject coverage 1.00 -> 0.24 [geometry]\n")
    mapping = {"https://cdn.x/aaa.png": {"chrome": None}, "https://cdn.x/bbb.png": {"chrome": ["tile"]}}
    assert feedback.suspect_originals(run, mapping) == {"https://cdn.x/aaa.png"}

    q = tmp_path / "q.yaml"
    assert feedback.enqueue({"https://cdn.x/aaa.png"}, q) == ["https://cdn.x/aaa.png"]
    assert feedback.load_queue(q) == {"https://cdn.x/aaa.png"}
    # merging is idempotent and additive
    assert feedback.enqueue({"https://cdn.x/aaa.png", "https://cdn.x/ddd.png"}, q) == \
        ["https://cdn.x/aaa.png", "https://cdn.x/ddd.png"]


def test_queue_priority_jumps_the_labelling_line():
    # aaa resolves to a family (would normally sort AFTER unresolved zzz); the
    # priority queue must still put it first.
    mapping = {
        "https://cdn.x/aaa.png": {"local": "x", "ground": "photo-full-bleed", "type": "hero", "layout": "single"},
        "https://cdn.x/zzz.png": {"local": "y", "ground": "gradient", "type": "hero", "layout": "grid"},
    }
    plain = [s for s, _ in sheets.pending(mapping)]
    assert plain[0] == "https://cdn.x/zzz.png", "normally the unresolved asset is hardest-first"
    prioritised = [s for s, _ in sheets.pending(mapping, priority={"https://cdn.x/aaa.png"})]
    assert prioritised[0] == "https://cdn.x/aaa.png", "a queued suspect jumps ahead of even an unresolved asset"
