"""The hooks are plain scripts run by Claude Code on the system python3, so
they are tested the same way: subprocess, JSON on stdin, JSON (or nothing) on
stdout. LP_RUNS_CURRENT points them at a temporary run folder."""

import json
import os
import subprocess
import sys
from pathlib import Path

HOOKS = Path(__file__).resolve().parents[1] / "hooks"
GEN = "mcp__b05f6314-91d1-4820-aed3-620c98a82b3f__picsart_generate"
PRE = "mcp__b05f6314-91d1-4820-aed3-620c98a82b3f__picsart_preflight"


def run_hook(name, payload, run_dir):
    env = {**os.environ, "LP_RUNS_CURRENT": str(run_dir)}
    out = subprocess.run(
        [sys.executable, str(HOOKS / name)], input=json.dumps(payload),
        capture_output=True, text=True, env=env, check=True,
    ).stdout.strip()
    return json.loads(out) if out else None


def decision(out):
    return out["hookSpecificOutput"]["permissionDecision"], out["hookSpecificOutput"]["permissionDecisionReason"]


def make_run(tmp_path, **budget):
    run = tmp_path / "run"
    run.mkdir()
    (run / "budget.json").write_text(json.dumps(budget))
    return run


def preflight(run, model, credits, params=None):
    run_hook("log_generation.py", {
        "tool_name": PRE,
        "tool_input": {"model": model, "params": params or {"prompt": "x"}},
        "tool_response": {"content": [{"type": "text", "text": json.dumps({"model": model, "valid": True, "credits": credits})}]},
    }, run)


def test_guard_denies_wrong_connector(tmp_path):
    run = make_run(tmp_path, run_credits=300)
    out = run_hook("credit_guard.py", {"tool_name": "mcp__1efb7d8c-x__picsart_generate", "tool_input": {"model": "m"}}, run)
    assert decision(out)[0] == "deny"
    assert "wrong connector" in decision(out)[1]


def test_guard_allows_when_no_run_is_active(tmp_path):
    out = run_hook("credit_guard.py", {"tool_name": GEN, "tool_input": {"model": "m"}}, tmp_path / "absent")
    assert out is None


def test_guard_denies_dry_run(tmp_path):
    run = make_run(tmp_path, run_credits=300, dry_run=True)
    out = run_hook("credit_guard.py", {"tool_name": GEN, "tool_input": {"model": "gemini-3-pro-image"}}, run)
    assert decision(out)[0] == "deny"
    assert "Dry run" in decision(out)[1]


def test_guard_requires_preflight_then_enforces_cap(tmp_path):
    run = make_run(tmp_path, run_credits=12)
    call = {"tool_name": GEN, "tool_input": {"model": "gemini-3-pro-image", "prompt": "x"}}

    out = run_hook("credit_guard.py", call, run)
    assert "No preflight quote" in decision(out)[1]

    preflight(run, "gemini-3-pro-image", 5)
    assert run_hook("credit_guard.py", call, run) is None  # 0 + 5 <= 12

    # Two paid calls logged at 5 each: 10 spent, next would be 15 > 12.
    for _ in range(2):
        run_hook("log_generation.py", {**call, "tool_response": {"results": [{"url": "https://gcdn.picsart.com/a.png"}]}}, run)
    out = run_hook("credit_guard.py", call, run)
    assert decision(out)[0] == "deny"
    assert "budget exceeded" in decision(out)[1]


def test_logger_records_urls_model_and_quote(tmp_path):
    run = make_run(tmp_path, run_credits=300)
    preflight(run, "picsart-enhance", 2)
    run_hook("log_generation.py", {
        "tool_name": "mcp__b05f6314-91d1-4820-aed3-620c98a82b3f__picsart_enhance",
        "tool_input": {"image": "https://gcdn.picsart.com/in.png", "scaleFactor": 2},
        "tool_response": {"results": [{"url": "https://gcdn.picsart.com/out.png"}]},
    }, run)
    rows = [json.loads(l) for l in (run / "ledger.jsonl").read_text().splitlines()]
    assert rows[0]["tool"] == "picsart_preflight" and rows[0]["quoted_credits"] == 2
    assert rows[1]["tool"] == "picsart_enhance"
    assert rows[1]["model"] == "picsart-enhance"          # default model for the tool
    assert rows[1]["quoted_credits"] == 2                  # taken from the preflight row
    assert rows[1]["connector"] == "b05f6314"
    assert "https://gcdn.picsart.com/out.png" in rows[1]["urls"]


def test_check_result_blocks_until_contract_is_met(tmp_path):
    run = make_run(tmp_path)
    section = run / "sections" / "S03"
    section.mkdir(parents=True)
    transcript = tmp_path / "t.jsonl"
    transcript.write_text(json.dumps({"input": {"file_path": f"{run}/sections/S03/brief.md"}}) + "\n")
    payload = {"transcript_path": str(transcript), "stop_hook_active": False}

    out = run_hook("check_result.py", payload, run)
    assert out["decision"] == "block" and "S03" in out["reason"]

    (section / "workflow.yaml").write_text("slot: S03-m1\nsteps: []\nfinal: {url: x}\n")
    (section / "result.md").write_text("---\nchosen: x\nscores: {}\n---\n")
    assert run_hook("check_result.py", payload, run) is None
    assert run_hook("check_result.py", {**payload, "stop_hook_active": True}, run) is None


def test_check_result_accepts_composite_contract(tmp_path):
    """A composite slot has no URL: final.url is null, chosen is a run-relative path."""
    import yaml
    run = make_run(tmp_path)
    section = run / "sections" / "S07"
    section.mkdir(parents=True)
    transcript = tmp_path / "t.jsonl"
    transcript.write_text(json.dumps({"input": {"file_path": f"{run}/sections/S07/brief.md"}}) + "\n")
    payload = {"transcript_path": str(transcript), "stop_hook_active": False}
    (section / "workflow.yaml").write_text(
        "slot: S07-m1\nsteps:\n  - id: 3\n    tool: lp-compose\n"
        "    params: {spec: compose-S07-m1.yaml, out: steps/S07-m1-3-1.png}\n    quoted_credits: 0\n"
        "final: {url: null, local: steps/S07-m1-3-1.png, width: 720, height: 720}\n")
    (section / "result.md").write_text(
        "---\nsection: S07\nslots:\n  S07-m1:\n    chosen: sections/S07/steps/S07-m1-3-1.png\n"
        "    scores: {clean: 5}\n---\n")
    assert run_hook("check_result.py", payload, run) is None
    assert yaml.safe_load((section / "workflow.yaml").read_text())["steps"][0]["tool"] == "lp-compose"


def test_check_result_takes_the_assigned_section_not_a_stray_path(tmp_path):
    run = make_run(tmp_path)
    for sid in ("S03", "S09"):
        (run / "sections" / sid).mkdir(parents=True)
    transcript = tmp_path / "t.jsonl"
    lines = [json.dumps({"input": {"file_path": f"{run}/sections/S09/brief.md"}}),  # a stray earlier path
             json.dumps({"prompt": f"Section S03. Work only inside `{run}/sections/S03/`. Read `brief.md` first."}),
             json.dumps({"input": {"file_path": f"{run}/sections/S03/workflow.yaml"}})]
    transcript.write_text("\n".join(lines) + "\n")
    payload = {"transcript_path": str(transcript), "stop_hook_active": False}
    out = run_hook("check_result.py", payload, run)
    assert out["decision"] == "block" and "S03" in out["reason"] and "S09" not in out["reason"]
    # without the assignment sentence, the most-named existing section wins
    transcript.write_text("\n".join(lines[0:1] + lines[2:] * 2) + "\n")
    out = run_hook("check_result.py", payload, run)
    assert "S03" in out["reason"]
    # a transcript holding several assignments is the manager's, not one worker's: whose stop this is cannot be told, so no block
    lines.append(json.dumps({"prompt": f"Section S09. Work only inside `{run}/sections/S09/`. Read `brief.md` first."}))
    transcript.write_text("\n".join(lines) + "\n")
    assert run_hook("check_result.py", payload, run) is None
