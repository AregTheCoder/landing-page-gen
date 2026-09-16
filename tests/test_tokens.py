"""lp-tokens on a synthetic session: dedup by message.id, worker/reviewer
classification, resume spawns and the manager window."""

import json
from pathlib import Path

from landing_page_gen import tokens


def _asst(mid, blocks, usage, ts="2026-01-01T00:00:00Z"):
    return {"type": "assistant", "timestamp": ts,
            "message": {"id": mid, "model": "claude-opus-4-8", "role": "assistant",
                        "content": blocks, "usage": usage}}


def _user(text, ts="2026-01-01T00:00:00Z"):
    return {"type": "user", "timestamp": ts, "message": {"role": "user", "content": text}}


def _tool_result(tid, text):
    return {"type": "user", "message": {"role": "user",
            "content": [{"type": "tool_result", "tool_use_id": tid,
                         "content": [{"type": "text", "text": text}]}]}}


def _usage(inp=0, out=0, read=0, cw5m=0, cw1h=0):
    return {"input_tokens": inp, "output_tokens": out, "cache_read_input_tokens": read,
            "cache_creation_input_tokens": cw5m + cw1h,
            "cache_creation": {"ephemeral_5m_input_tokens": cw5m, "ephemeral_1h_input_tokens": cw1h}}


def _write_jsonl(path, records):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(r) + "\n" for r in records))


def _agent(sub, name, tid, first_user, records):
    _write_jsonl(sub / f"agent-{name}.jsonl", [_user(first_user)] + records)
    (sub / f"agent-{name}.meta.json").write_text(json.dumps({"toolUseId": tid, "description": name}))


def _build(tmp_path):
    session = tmp_path / "sess.jsonl"
    sub = tmp_path / "sess" / "subagents"

    # Two worker agents for S01 (a spawn + a resume) and one reviewer for S01+S02.
    _agent(sub, "w1", "tu_w1a", "Section S01: build the hero.", [
        _asst("wm1", [{"type": "tool_use", "id": "r1", "name": "Read",
                       "input": {"file_path": "/x/runs/live-9/sections/S01/brief.md"}}],
              _usage(inp=1, out=10, read=100)),
        _tool_result("r1", "brief text " * 10),
        _asst("wm2", [{"type": "tool_use", "name": "mcp__x__picsart_job_status", "input": {}},
                      {"type": "tool_use", "name": "Bash", "input": {"command": "sleep 60"}}],
              _usage(inp=1, out=20, read=200)),
    ])
    _agent(sub, "w2", "tu_w1b", "Section S01 (runs/live-9/sections/S01): continue (resumed).", [
        _asst("wr1", [{"type": "text", "text": "resuming"}], _usage(inp=1, out=5, read=50)),
    ])
    _agent(sub, "rev", "tu_rev", "Review sections S01 and S02 of run runs/live-9.", [
        _asst("rv1", [{"type": "tool_use", "name": "Bash",
                       "input": {"command": "grep x runs/live-9/ledger.jsonl"}}],
              _usage(inp=1, out=8, read=80)),
    ])

    # Manager main session: a human prompt, two Agent spawns, a duplicated-usage
    # turn (same id twice), then a task-notification and an unrelated prompt.
    dup = _usage(inp=2, out=560, read=41616, cw5m=27414)
    main = [
        _user("According to the rules, generate images for runs/live-9."),
        _asst("mm1", [{"type": "tool_use", "id": "tu_w1a", "name": "Agent",
                       "input": {"description": "Section S01 worker"}}], dup),
        _asst("mm1", [{"type": "tool_use", "id": "tu_w1b", "name": "Agent",
                       "input": {"description": "Section S01 worker"}}], dup),  # same id, duplicated usage
        _asst("mm2", [{"type": "tool_use", "id": "tu_rev", "name": "Agent",
                       "input": {"description": "Review S01 S02"}}], _usage(inp=1, out=30, read=5000)),
        _user("<task-notification> done"),
        _asst("mm3", [{"type": "text", "text": "wrote report"}], _usage(inp=1, out=40, read=6000)),
        _user("now do something unrelated"),
        _asst("mm4", [{"type": "text", "text": "unrelated"}], _usage(inp=1, out=999, read=99999)),
    ]
    _write_jsonl(session, main)
    return session


def test_analyse_classifies_dedups_and_windows(tmp_path):
    session = _build(tmp_path)
    data = tokens.analyse("live-9", session, tokens.PRICING["claude-opus-4-8"])

    workers = data["workers"]
    reviewers = data["reviewers"]
    assert len(workers) == 2 and {w.section for w in workers} == {"S01"}
    assert data["spawns_per_section"]["S01"] == 2  # a spawn + a resume
    assert len(reviewers) == 1 and reviewers[0].section == "S01+S02"

    # Manager window stops at the task-notification's following real prompt:
    # mm1(once, deduped), mm2, mm3 counted; the unrelated mm4 excluded.
    mgr = data["manager"]
    assert mgr.turns == 3
    # mm1's duplicated usage counted once: output 560 + 30 + 40.
    assert mgr.usage.output == 560 + 30 + 40
    assert mgr.usage.read == 41616 + 5000 + 6000

    # Worker tool-call tallies.
    w1 = next(w for w in workers if w.turns == 2)
    assert w1.job_polls == 1 and w1.sleeps == 1
    assert w1.read_bytes["brief"] > 0
    # Reviewer ledger grep counted.
    assert reviewers[0].ledger_bash == 1


def test_1h_and_5m_cache_write_priced_apart(tmp_path):
    r = tokens.AgentReport(role="manager", label="m")
    r.usage.add(_usage(cw5m=1_000_000, cw1h=1_000_000))
    price = tokens.PRICING["claude-opus-4-8"]
    # 5m at 18.75/M + 1h at 30/M == 48.75 for a million of each.
    assert abs(r.cost(price) - 48.75) < 1e-6
