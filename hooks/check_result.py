#!/usr/bin/env python3
"""SubagentStop hook for section-worker. Finds the section the worker was
writing to (first runs/.../sections/Sxx path in its transcript, i.e. the
section named in its assignment; workers list other sections later) and blocks the
stop until workflow.yaml and result.md exist there with their required keys."""

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import _ledger as L  # noqa: E402

REQUIRED = {
    "workflow.yaml": ("slot:", "steps:", "final:"),
    "result.md": ("chosen:", "scores:"),
}
SECTION_RE = re.compile(r"/sections/(S\d+)\b")


def missing_in(folder):
    problems = []
    for name, keys in REQUIRED.items():
        path = folder / name
        if not path.exists():
            problems.append(f"{name} is missing")
            continue
        text = path.read_text(errors="ignore")
        absent = [k for k in keys if k not in text]
        if absent:
            problems.append(f"{name} lacks {', '.join(absent)}")
    return problems


def main():
    data = L.read_hook_input()
    if data.get("stop_hook_active"):
        return
    transcript = Path(data.get("transcript_path", ""))
    text = transcript.read_text(errors="ignore") if transcript.exists() else ""
    sids = SECTION_RE.findall(text)
    run = L.current_run()
    if not sids or not run.exists():
        return
    folder = run / "sections" / sids[0]
    problems = missing_in(folder)
    if problems:
        print(json.dumps({
            "decision": "block",
            "reason": f"Not finished for {sids[0]}: " + "; ".join(problems)
                      + ". Write both files per the output contract, then stop.",
        }))


if __name__ == "__main__":
    main()
