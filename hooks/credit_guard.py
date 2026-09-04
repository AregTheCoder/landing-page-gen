#!/usr/bin/env python3
"""PreToolUse hook on paid Picsart tools. Denies, with a reason the agent
sees, when: the call is on the wrong connector; the active run is a dry run;
no preflight quote exists for the model; or the run credit cap would be
exceeded. With no active run (`runs/current` absent) it allows everything."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import _ledger as L  # noqa: E402


def deny(reason):
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "deny",
        "permissionDecisionReason": reason,
    }}))
    sys.exit(0)


def main():
    data = L.read_hook_input()
    tool = data.get("tool_name", "")
    if not tool.startswith(L.SPEND_CONNECTOR):
        deny(f"{L.short_tool(tool)} was called on the wrong connector. "
             f"Paid Picsart calls go through the {L.SPEND_CONNECTOR} tools.")

    run = L.current_run()
    if not run.exists():
        return
    b = L.budget(run)
    if b.get("dry_run"):
        deny("Dry run: do not execute this step. Record it in workflow.yaml with its "
             "preflight quote and move on.")

    rows = L.ledger_rows(run)
    model = L.model_of(tool, data.get("tool_input", {}))
    quote = L.last_quote(rows, model)
    if quote is None:
        deny(f"No preflight quote for model {model!r} in this run. Call picsart_preflight "
             f"with the same model and params first.")
    cap = b.get("run_credits")
    used = L.spent(rows)
    if cap is not None and used + quote > cap:
        deny(f"Run budget exceeded: {used} spent + {quote} quoted > {cap} cap. "
             f"Stop and report to the manager.")


if __name__ == "__main__":
    main()
