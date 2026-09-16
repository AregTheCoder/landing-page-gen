"""Shared helpers for the landing-page-gen hooks.

Stdlib only and Python 3.9 compatible: hooks run on the system python3, not
the project venv, so they start fast and never depend on `uv sync`."""

import json
import os
import sys
from pathlib import Path

PAID_TOOLS = (
    "picsart_generate", "picsart_enhance", "picsart_remove_bg",
    "picsart_change_bg", "picsart_vectorize",
)
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


def last_quote(rows, model):
    for row in reversed(rows):
        if row.get("tool") == "picsart_preflight" and row.get("model") == model \
                and row.get("quoted_credits") is not None:
            return row["quoted_credits"]
    return None


def quote_for(rows, model):
    """Credits for a paid call: a flat-rate edit model's fixed price, or the
    last preflight quote for a generate model (None when it was not
    preflighted)."""
    if model in FIXED_PRICE:
        return FIXED_PRICE[model]
    return last_quote(rows, model)


def row_cost(row):
    if row.get("tool") not in PAID_TOOLS:
        return 0
    model = row.get("model")
    if model in FIXED_PRICE:
        return FIXED_PRICE[model]
    return row.get("quoted_credits") or 0


def spent(rows):
    return sum(row_cost(row) for row in rows)


def budget(run):
    path = run / "budget.json"
    return json.loads(path.read_text()) if path.exists() else {}
