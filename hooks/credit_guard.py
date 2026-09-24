#!/usr/bin/env python3
"""PreToolUse hook on paid Picsart tools. Denies, with a reason the agent
sees, when: the call is on the wrong connector; the active run is a dry run;
no preflight quote exists for the model; the run credit cap would be
exceeded; or a generate leaves Drive auto-save on. With no active run (`runs/current` absent) it allows everything."""

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


DRIVE_ONLY = {  # paid tools with no saveToDrive flag -> the picsart_generate route (tool-map.md)
    "picsart_enhance": "model topaz-upscale-image (faces) or picsart-enhance, imageUrls: [<the image>]",
    "picsart_remove_bg": "model picsart-sod-v8-2, imageUrls: [<the image>]",
}


def main():
    data = L.read_hook_input()
    tool = data.get("tool_name", "")
    if not tool.startswith(L.SPEND_CONNECTOR):
        deny(f"{L.short_tool(tool)} was called on the wrong connector. "
             f"Paid Picsart calls go through the {L.SPEND_CONNECTOR} tools.")

    run = L.active_run(data)
    if not run.exists():
        return
    b = L.budget(run)
    if b.get("dry_run"):
        deny("Dry run: do not execute this step. Record it in workflow.yaml with its "
             "preflight quote and move on.")

    short = L.short_tool(tool)
    if short in DRIVE_ONLY:
        deny(f"{short} has no saveToDrive switch and 403s on Drive auto-save (blind-1-4, blind-2-5). Run the same "
             f"model through picsart_generate with saveToDrive: false: {DRIVE_ONLY[short]}. lp-flow check accepts "
             "that node kind on picsart_generate. Preflight picsart_generate with that model first.")
    rows = L.ledger_rows(run)
    model = L.model_of(tool, data.get("tool_input", {}))
    quote = L.quote_for(rows, model, short, data.get("tool_input", {}).get("prompt"))
    if quote is None and short in L.RENDER_TOOLS:
        deny(f"{short} is an MP Scene render with no measured price yet. Outside a run: render once, "
             f"read the picsart_credits delta, write it into hooks/_ledger.RENDER_PRICE, then retry.")
    if quote is None:
        deny(f"No preflight quote for model {model!r} in this run. Call picsart_preflight "
             f"with the same model and params first.")
    cap = b.get("run_credits")
    used = L.spent(rows)
    if cap is not None and used + quote > cap:
        deny(f"Run budget exceeded: {used} spent + {quote} quoted > {cap} cap. "
             f"Stop and report to the manager.")
    if short == "picsart_generate" and data.get("tool_input", {}).get("saveToDrive") is not False:
        deny("Pass saveToDrive: false on picsart_generate. The Drive auto-save fails on this account and "
             "Picsart reports it as HTTP 403 'content may violate usage policies', whatever the prompt "
             "(runs/composition-1: the same call passed with false, 403d without). The run keeps every "
             "URL in ledger.jsonl, so nothing needs Drive.")


if __name__ == "__main__":
    main()
