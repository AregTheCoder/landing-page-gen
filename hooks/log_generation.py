#!/usr/bin/env python3
"""PostToolUse hook on Picsart preflight and paid tools. Appends one row per
call to runs/current/ledger.jsonl: timestamp, tool, connector, model, params,
every URL in the response, and the credits (quoted directly for preflight,
taken from the last preflight of the same model for paid calls)."""

import datetime
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import _ledger as L  # noqa: E402

URL_RE = re.compile(r"https?://[^\s\"'\\<>]+")
CREDITS_RE = re.compile(r'credits\\*"\s*:\s*(\d+)')


def main():
    data = L.read_hook_input()
    run = L.current_run()
    if not run.exists():
        return
    tool_name = data.get("tool_name", "")
    tool = L.short_tool(tool_name)
    tool_input = data.get("tool_input", {})
    response_text = json.dumps(data.get("tool_response", ""))
    model = L.model_of(tool_name, tool_input)

    if tool == "picsart_preflight":
        found = CREDITS_RE.search(response_text)
        credits = int(found.group(1)) if found else None
    else:
        credits = L.last_quote(L.ledger_rows(run), model)

    row = {
        "ts": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        "tool": tool,
        "connector": tool_name.split("__")[1][:8] if "__" in tool_name else "",
        "model": model,
        "params": tool_input,
        "urls": sorted(set(URL_RE.findall(response_text))),
        "quoted_credits": credits,
    }
    with (run / "ledger.jsonl").open("a") as fh:
        fh.write(json.dumps(row) + "\n")


if __name__ == "__main__":
    main()
