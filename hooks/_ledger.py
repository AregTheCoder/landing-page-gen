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


def current_run():
    override = os.environ.get("LP_RUNS_CURRENT")
    if override:
        return Path(override)
    root = Path(os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd()))
    return root / "landing-page-gen" / "runs" / "current"


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


def spent(rows):
    return sum(row.get("quoted_credits") or 0 for row in rows if row.get("tool") in PAID_TOOLS)


def budget(run):
    path = run / "budget.json"
    return json.loads(path.read_text()) if path.exists() else {}
