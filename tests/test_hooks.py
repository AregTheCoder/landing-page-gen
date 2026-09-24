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


def test_guard_denies_a_generate_that_saves_to_drive(tmp_path):
    # Drive auto-save came back as a 403 'content policy' block on any prompt (composition-1)
    run = make_run(tmp_path, run_credits=300)
    preflight(run, "gemini-3-pro-image", 5)
    call = {"tool_name": GEN, "tool_input": {"model": "gemini-3-pro-image", "prompt": "x"}}
    out = run_hook("credit_guard.py", call, run)
    assert decision(out)[0] == "deny" and "saveToDrive: false" in decision(out)[1]
    call["tool_input"]["saveToDrive"] = False
    assert run_hook("credit_guard.py", call, run) is None


def test_guard_requires_preflight_then_enforces_cap(tmp_path):
    run = make_run(tmp_path, run_credits=12)
    call = {"tool_name": GEN, "tool_input": {"model": "gemini-3-pro-image", "prompt": "x", "saveToDrive": False}}

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


def test_a_generate_is_priced_by_its_own_preflight_not_the_models_latest(tmp_path):
    # random-2: parallel workers on one model; each generate took whichever quote came last
    run = make_run(tmp_path, run_credits=300)
    preflight(run, "gpt-image-2.5-sunburst", 2, {"prompt": "a sneaker"})
    preflight(run, "gpt-image-2.5-sunburst", 1, {"prompt": "a bouquet"})
    for prompt in ("a sneaker", "a bouquet", "never preflighted"):
        run_hook("log_generation.py", {
            "tool_name": GEN, "tool_input": {"model": "gpt-image-2.5-sunburst", "prompt": prompt, "saveToDrive": False},
            "tool_response": {"results": [{"url": f"https://gcdn.picsart.com/{len(prompt)}.png"}]},
        }, run)
    rows = [json.loads(l) for l in (run / "ledger.jsonl").read_text().splitlines()]
    assert [r["quoted_credits"] for r in rows[2:]] == [2, 1, 1]  # an unmatched prompt keeps the model's latest


def test_a_failed_paid_call_is_logged_at_its_quote_with_no_url(tmp_path):
    # qa-live-3: picsart_enhance answered 403 and the balance still moved 2 credits
    run = make_run(tmp_path, run_credits=300)
    preflight(run, "picsart-enhance", 2)
    for tool in (GEN.replace("picsart_generate", "picsart_enhance"), GEN.replace("picsart_generate", "picsart_preflight")):
        run_hook("log_generation.py", {"hook_event_name": "PostToolUseFailure", "tool_name": tool,
                                       "tool_input": {"model": "picsart-enhance"}, "error": "HTTP 403"}, run)
    rows = [json.loads(l) for l in (run / "ledger.jsonl").read_text().splitlines()]
    assert len(rows) == 2  # the preflight and the failed enhance; a failed quote spends nothing
    assert rows[-1]["failed"] and rows[-1]["urls"] == [] and rows[-1]["quoted_credits"] == 2
    sys.path.insert(0, str(HOOKS))
    import _ledger as L
    assert L.spent(rows) == 0  # logged for the record; the cap does not count a call that failed


def test_job_status_row_carries_the_clip_url_and_unlocks_it(tmp_path):
    """An async video generate returns no URL; the clip arrives via
    picsart_job_status. Logged at cost 0, it lets a later extend node wire it."""
    run = make_run(tmp_path, run_credits=300)
    preflight(run, "seedance-2.5", 35)
    clip = "https://gcdn.picsart.com/editing-temp/clip.mp4"
    extend = {"tool_name": GEN, "tool_input": {"model": "seedance-2.5-video-extend", "params": {"videoUrls": [clip]}}}
    assert decision(run_hook("isolation_guard.py", extend, run))[0] == "deny", "not in the run yet"
    run_hook("log_generation.py", {
        "tool_name": "mcp__b05f6314-91d1-4820-aed3-620c98a82b3f__picsart_job_status",
        "tool_input": {"jobId": "job-1"},
        "tool_response": {"status": "completed", "results": [{"url": clip}]},
    }, run)
    rows = [json.loads(l) for l in (run / "ledger.jsonl").read_text().splitlines()]
    assert rows[-1]["tool"] == "picsart_job_status" and clip in rows[-1]["urls"]
    assert run_hook("isolation_guard.py", extend, run) is None
    # the credit guard's spend is untouched by the job_status row
    out = run_hook("credit_guard.py", {"tool_name": GEN, "tool_input": {"model": "seedance-2.5", "prompt": "x", "saveToDrive": False}}, run)
    assert out is None  # 0 spent + 35 <= 300


def test_mp_scene_render_is_denied_until_priced_then_counted(tmp_path, monkeypatch):
    run = make_run(tmp_path, run_credits=20)
    render = {"tool_name": "mcp__b05f6314-91d1-4820-aed3-620c98a82b3f__picsart_media_video_render",
              "tool_input": {"scene": {"width": 720}}}
    out = run_hook("credit_guard.py", render, run)
    assert decision(out)[0] == "deny" and "no measured price" in decision(out)[1]
    # a measured price makes it an ordinary paid call: allowed, logged, counted toward the cap
    ledger = HOOKS / "_ledger.py"
    original = ledger.read_text()
    ledger.write_text(original.replace("RENDER_PRICE = {}", 'RENDER_PRICE = {"picsart_media_video_render": 15}'))
    try:
        assert run_hook("credit_guard.py", render, run) is None
        run_hook("log_generation.py", {**render, "tool_response": {"url": "https://gcdn.picsart.com/r.mp4"}}, run)
        rows = [json.loads(l) for l in (run / "ledger.jsonl").read_text().splitlines()]
        assert rows[-1]["tool"] == "picsart_media_video_render" and rows[-1]["quoted_credits"] == 15
        out = run_hook("credit_guard.py", render, run)
        assert decision(out)[0] == "deny" and "budget exceeded" in decision(out)[1], "15 spent + 15 > 20"
    finally:
        ledger.write_text(original)


def test_check_result_blocks_until_contract_is_met(tmp_path):
    run = make_run(tmp_path)
    section = run / "sections" / "S03"
    section.mkdir(parents=True)
    # The main-session transcript names another section first; the worker's
    # own transcript names S03 in its assignment and lists S09 later.
    main = tmp_path / "main.jsonl"
    main.write_text(json.dumps({"type": "user", "message": {"role": "user", "content": f"earlier: {run}/sections/S01/brief.md"}}) + "\n")
    worker = tmp_path / "agent.jsonl"
    worker.write_text("\n".join([
        json.dumps({"type": "user", "isMeta": True, "message": {"role": "user", "content": [{"type": "text", "text": "skill preamble"}]}}),
        json.dumps({"type": "user", "message": {"role": "user", "content": f"Section S03. Work only inside `{run}/sections/S03/`."}}),
        json.dumps({"type": "assistant", "message": {"role": "assistant", "content": [{"type": "text", "text": f"listing {run}/sections/S09"}]}}),
    ]) + "\n")
    payload = {"transcript_path": str(main), "agent_transcript_path": str(worker), "stop_hook_active": False}

    out = run_hook("check_result.py", payload, run)
    assert out["decision"] == "block" and "S03" in out["reason"]
    (section / "proposal-S03-m1.yaml").write_text("style: full-bleed\n")  # a blind run's phase 1 ends here
    assert run_hook("check_result.py", payload, run) is None

    (section / "workflow.yaml").write_text("slot: S03-m1\nsteps: []\nfinal: {url: x}\n")
    (section / "result.md").write_text("---\nchosen: x\nscores: {}\n---\n")
    assert run_hook("check_result.py", payload, run) is None
    assert run_hook("check_result.py", {**payload, "stop_hook_active": True}, run) is None
    # a worker of another run is checked in its own run, whatever runs/current names
    other = tmp_path / "runs" / "other"
    (other / "sections" / "S03").mkdir(parents=True)  # same section id as the finished one in runs/current
    worker.write_text(json.dumps({"type": "user", "message": {"role": "user", "content": f"Section folder: {other}/sections/S03"}}) + "\n")
    out = run_hook("check_result.py", payload, run)
    assert out["decision"] == "block" and "S03" in out["reason"], "checked in its own run, not in runs/current"


def test_check_result_falls_back_to_transcript_path(tmp_path):
    run = make_run(tmp_path)
    (run / "sections" / "S05").mkdir(parents=True)
    transcript = tmp_path / "t.jsonl"
    transcript.write_text(json.dumps({"type": "user", "message": {"role": "user", "content": f"Section S05. Work in {run}/sections/S05/."}}) + "\n")
    out = run_hook("check_result.py", {"transcript_path": str(transcript), "stop_hook_active": False}, run)
    assert out["decision"] == "block" and "S05" in out["reason"]


def test_parallel_workers_are_logged_and_capped_in_their_own_runs(tmp_path):
    """Each worker's calls go to the run its first message names, not to
    runs/current, so several runs build at once (blind-1 ran serially)."""
    runs = tmp_path / "runs"
    a, b, current = runs / "trial-1", runs / "trial-2", runs / "other"
    for r, cap in ((a, 2), (b, 12), (current, 50)):
        (r / "sections" / "S01").mkdir(parents=True)
        (r / "budget.json").write_text(json.dumps({"run_credits": cap}))
    session = tmp_path / "session.jsonl"
    session.write_text("")
    (tmp_path / "session" / "subagents").mkdir(parents=True)
    for aid, r in (("w1", a), ("w2", b)):
        (tmp_path / "session" / "subagents" / f"agent-{aid}.jsonl").write_text(json.dumps(
            {"type": "user", "message": {"content": f"Section S01. Work only inside `{r}/sections/S01/`."}}) + "\n")
    env = {**os.environ, "LP_RUNS_CURRENT": str(current), "LP_RUNS_DIR": str(runs)}

    def hook(name, payload):
        out = subprocess.run([sys.executable, str(HOOKS / name)], input=json.dumps(payload), capture_output=True,
                             text=True, env=env, check=True).stdout.strip()
        return json.loads(out) if out else None
    call = {"tool_name": GEN, "tool_input": {"model": "gemini-3-pro-image", "prompt": "x", "saveToDrive": False},
            "transcript_path": str(session)}
    quote = {"tool_name": GEN.replace("picsart_generate", "picsart_preflight"),
             "tool_input": {"model": "gemini-3-pro-image", "prompt": "x"}, "tool_response": '{"credits": 5}',
             "transcript_path": str(session)}
    for aid in ("w1", "w2"):
        hook("log_generation.py", {**quote, "agent_id": aid})
    assert (a / "ledger.jsonl").exists() and (b / "ledger.jsonl").exists() and not (current / "ledger.jsonl").exists()
    assert decision(hook("credit_guard.py", {**call, "agent_id": "w1"}))[0] == "deny", "5 > trial-1's cap of 2"
    assert hook("credit_guard.py", {**call, "agent_id": "w2"}) is None, "5 <= trial-2's cap of 12"


def test_tools_without_a_drive_switch_are_denied_with_the_generate_route(tmp_path):
    run = make_run(tmp_path, run_credits=20)
    for tool, model in (("picsart_enhance", "topaz-upscale-image"), ("picsart_remove_bg", "picsart-sod-v8-2")):
        out = run_hook("credit_guard.py", {"tool_name": GEN.replace("picsart_generate", tool),
                                           "tool_input": {"image": "https://gcdn.picsart.com/a.png"}}, run)
        verdict, reason = decision(out)
        assert verdict == "deny" and "picsart_generate" in reason and model in reason
