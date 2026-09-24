"""manager_check.py holds the manager to SKILL.md before lp-inject: blind-1
shipped slots with no report, no review and a kept-from-source class."""
import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parents[1] / ".claude" / "skills" / "build-landing-page"


def load():
    sys.path.insert(0, str(HERE))
    spec = importlib.util.spec_from_file_location("manager_check_mod", HERE / "manager_check.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def slot(sid, typ_aspect):
    return f"```slot\nid: {sid}\nkind: image\nrole: thumbnail\nsize: 342x282\naspect: '{typ_aspect}'\n```\n"


def make_run(tmp_path, section_type, aspect, family):
    run = tmp_path / "run"
    sec = run / "sections" / "S03"
    sec.mkdir(parents=True)
    (run / "budget.json").write_text(json.dumps({"run_credits": 6, "dry_run": False}))
    (run / "skeleton.md").write_text(f"---\npage: p\npage_family: tool\n---\n\n## S03 {section_type}\n\n- t1 h2: Hi\n\n"
                                     + slot("S03-m1", aspect))
    (run / "slots.json").write_text(json.dumps({"slots": {"S03-m1": {"role": "thumbnail", "aspect": aspect}}}))
    (sec / "result.md").write_text("---\nsection: S03\nslots:\n  S03-m1:\n    chosen: steps/x.png\nstatus: done\n---\n")
    (sec / "brief.md").write_text(f"# Brief\n\n## Style family: {family}\n")
    return run, sec


def test_a_run_nobody_reviewed_is_refused_and_a_followed_one_passes(tmp_path, monkeypatch):
    mc = load()
    monkeypatch.setattr(mc.precheck, "check", lambda run, sid: [])
    monkeypatch.setattr(mc.brief, "mode_expectation", lambda *a: {"allowed": ["layered"], "shares": {}, "n": 50,
                                                                   "basis": "link-grid x many"})
    run, sec = make_run(tmp_path, "link-grid", "5:4", "full-bleed")
    problems = mc.check(run)
    assert any("report.md" in p for p in problems)
    assert any("kept from source" in p for p in problems), "a link-grid 5:4 thumbnail is never generated"
    assert any("full-bleed makes standalone" in p for p in problems)
    assert any("no review-N.md" in p for p in problems)

    run2, sec2 = make_run(tmp_path / "b", "link-grid", "16:9", "prompt-card")
    (run2 / "report.md").write_text("# Report\n\n## Start\n\nbalance: 117\n")
    (sec2 / "review-1.md").write_text("verdict: rework\n")
    assert [p for p in mc.check(run2) if "last review says rework" in p]
    (sec2 / "review-2.md").write_text("verdict: accept\n")
    assert mc.check(run2) == []
