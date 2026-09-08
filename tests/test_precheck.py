"""The manager's precheck reads a section's record against the run ledger and
names every paperwork problem a review round used to catch."""
import importlib.util
import json
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / ".claude/skills/build-landing-page/precheck.py"
spec = importlib.util.spec_from_file_location("precheck", SCRIPT)
precheck = importlib.util.module_from_spec(spec)
spec.loader.exec_module(precheck)

PROMPT = "a red cup on a yellow seamless, no other text, no logos or watermarks"


def make_run(tmp_path, count=1, spent=5, with_preflight=True, final_exists=True, note="looks right"):
    run = tmp_path / "run"
    sec = run / "sections" / "S03"
    (sec / "steps").mkdir(parents=True)
    if final_exists:
        (sec / "steps" / "S03-m1-1-1.png").write_bytes(b"x")
    (sec / "workflow.yaml").write_text(
        "slot: S03-m1\nsteps:\n  - id: 1\n    tool: picsart_generate\n    model: gemini-3-pro-image\n"
        f"    params: {{prompt: '{PROMPT}', aspectRatio: '4:3', count: {count}}}\n    quoted_credits: 5\n"
        f"    gate: 'one cup, centred'\n    status: done\n    note: '{note}'\n"
        f"final: {{url: x, local: steps/S03-m1-1-1.png}}\ncredits: {{quoted: 5, spent: {spent}}}\n")
    (sec / "result.md").write_text("---\nchosen: x\nscores: {clean: 5}\n---\n")
    rows = []
    if with_preflight:
        rows.append({"tool": "picsart_preflight", "model": "gemini-3-pro-image",
                     "params": {"model": "gemini-3-pro-image", "params": {"prompt": PROMPT}}, "quoted_credits": 5})
    rows.append({"tool": "picsart_generate", "model": "gemini-3-pro-image",
                 "params": {"model": "gemini-3-pro-image", "prompt": PROMPT}, "quoted_credits": 5})
    (run / "ledger.jsonl").write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    return run


def test_clean_record_passes(tmp_path):
    assert precheck.check(make_run(tmp_path), "S03") == []


def test_every_paperwork_problem_is_named(tmp_path):
    problems = precheck.check(make_run(tmp_path, count=2, spent=10, with_preflight=False, final_exists=False, note=""), "S03")
    text = "\n".join(problems)
    assert "no preflight row" in text and "count 2" in text and "credits.spent 10 != ledger 5" in text
    assert "not on disk" in text and "without a gate observation" in text


def test_cli_exit_codes(tmp_path, capsys):
    run = make_run(tmp_path)
    assert precheck.main([str(run), "S03"]) == 0 and "clean record" in capsys.readouterr().out
    assert precheck.main([str(make_run(tmp_path / "b", count=2)), "S03"]) == 1
    assert precheck.check(tmp_path / "nowhere", "S03") == ["S03: workflow.yaml missing"]
