"""Shared helpers for the landing-page-gen hooks.

Stdlib only and Python 3.9 compatible: hooks run on the system python3, not
the project venv, so they start fast and never depend on `uv sync`."""

import json
import os
import re
import sys
from pathlib import Path

PAID_TOOLS = (
    "picsart_generate", "picsart_enhance", "picsart_remove_bg",
    "picsart_change_bg", "picsart_vectorize",
    "picsart_media_video_render", "picsart_media_export", "picsart_media_video_create",
)
# MP Scene renders (the `motion` node's engines): paid per render, no preflight,
# and no price known yet. The guard denies them until a measured price lands in
# RENDER_PRICE (read one render's picsart_credits delta, then write it here).
RENDER_TOOLS = ("picsart_media_video_render", "picsart_media_export", "picsart_media_video_create")
RENDER_PRICE = {}
SPEND_CONNECTOR = "mcp__b05f6314"
DEFAULT_MODELS = {
    "picsart_enhance": "picsart-enhance",
    "picsart_remove_bg": "picsart-sod-v8-2",
    "picsart_change_bg": "recraftv3-replace-bg",
    "picsart_vectorize": "recraft-vectorize",
}

# Flat-rate edit models. picsart_preflight is generate-only and returns
# credits: null for these, so they can never carry a preflight quote; their
# price is fixed and known (tool-map.md), and the guard uses it directly.
FIXED_PRICE = {
    "picsart-sod-v8-2": 0,       # remove_bg / cutout
    "recraftv3-replace-bg": 2,   # change_bg / background
    "picsart-enhance": 2,        # enhance / upscale
    "topaz-upscale-image": 3,    # enhance, faces
}


def current_run():
    """<repo>/runs/current, located from this file: CLAUDE_PROJECT_DIR points
    at the workspace folder, not this repo, and the cwd is not guaranteed."""
    override = os.environ.get("LP_RUNS_CURRENT")
    if override:
        return Path(override)
    return Path(__file__).resolve().parents[1] / "runs" / "current"


RUN_RE = re.compile(r"(/\S*?/runs/[^/\s`'\"]+)/sections/S\d+")


def first_user_message(transcript):
    """Text of the first non-meta user turn in a transcript jsonl, else ""."""
    for line in transcript.read_text(errors="ignore").splitlines():
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if row.get("type") != "user" or row.get("isMeta"):
            continue
        content = row.get("message", {}).get("content", "")
        if isinstance(content, list):
            content = " ".join(b.get("text", "") for b in content if isinstance(b, dict))
        return str(content)
    return ""


def agent_transcript(data):
    """The calling subagent's own transcript: the hook's agent_transcript_path,
    else <session transcript>/subagents/agent-<agent_id>.jsonl; None for the
    main session."""
    if data.get("agent_transcript_path"):
        return Path(data["agent_transcript_path"])
    aid, tp = data.get("agent_id"), data.get("transcript_path")
    if aid and tp:
        return Path(tp[:-len(".jsonl")] if tp.endswith(".jsonl") else tp) / "subagents" / f"agent-{aid}.jsonl"
    return None


def active_run(data):
    """The run a call belongs to: the run folder the calling worker was given
    by path in its first message (so workers of several runs build in parallel,
    each capped and logged in its own run), else runs/current."""
    t = agent_transcript(data)
    if t is not None and t.exists():
        m = RUN_RE.search(first_user_message(t))
        runs = Path(os.environ.get("LP_RUNS_DIR") or Path(__file__).resolve().parents[1] / "runs")
        if m and Path(m.group(1)).parent.resolve() == runs.resolve() and Path(m.group(1)).is_dir():
            return Path(m.group(1))
    return current_run()


def read_hook_input():
    return json.load(sys.stdin)


def short_tool(tool_name):
    return tool_name.rsplit("__", 1)[-1]


def model_of(tool_name, tool_input):
    return tool_input.get("model") or DEFAULT_MODELS.get(short_tool(tool_name))


def ledger_rows(run):
    path = run / "ledger.jsonl"
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def prompt_of(row):
    p = row.get("params") or {}
    return (p.get("prompt") or (p.get("params") or {}).get("prompt") or "").strip()


def last_quote(rows, model, prompt=None):
    """The latest preflight quote for `model`: the one for this prompt when it was
    preflighted. Parallel workers share a model at different prices, so the
    model's latest quote alone is another call's (random-2: 28 of 35 generates)."""
    fallback = None
    for row in reversed(rows):
        if row.get("tool") == "picsart_preflight" and row.get("model") == model \
                and row.get("quoted_credits") is not None:
            if prompt is None or prompt_of(row) == prompt.strip():
                return row["quoted_credits"]
            if fallback is None:
                fallback = row["quoted_credits"]
    return fallback


def quote_for(rows, model, tool=None, prompt=None):
    """Credits for a paid call: a flat-rate edit model's fixed price, an MP Scene
    render's measured price, or the preflight quote for a generate model and its
    prompt (None when it was not preflighted, or the render is not priced yet)."""
    if tool in RENDER_TOOLS:
        return RENDER_PRICE.get(tool)
    if model in FIXED_PRICE:
        return FIXED_PRICE[model]
    return last_quote(rows, model, prompt)


def row_cost(row):
    tool = row.get("tool")
    if tool not in PAID_TOOLS or row.get("failed"):
        return 0  # a failed call is logged for the record; twice a 403'd enhance moved the balance by nothing
    if tool in RENDER_TOOLS:
        return RENDER_PRICE.get(tool, 0)
    model = row.get("model")
    if model in FIXED_PRICE:
        return FIXED_PRICE[model]
    return row.get("quoted_credits") or 0


def spent(rows):
    return sum(row_cost(row) for row in rows)


def budget(run):
    path = run / "budget.json"
    return json.loads(path.read_text()) if path.exists() else {}
