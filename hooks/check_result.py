#!/usr/bin/env python3
"""SubagentStop hook for section-worker. Finds the section the worker was
assigned ("Section Sxx. Work only inside ..." in its prompt, else the run's
section folder its transcript names most often) and blocks the stop until
workflow.yaml and result.md exist there with their required keys."""

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


ASSIGNMENT_RE = re.compile(r"Section (S\d+)\. Work only inside")


def section_of(text, run):
    """The worker's own section: the one named in its assignment sentence, else
    the section folder of this run that its transcript names most often (a
    worker writes many files there; a stray example path appears once)."""
    assigned = set(ASSIGNMENT_RE.findall(text))
    if len(assigned) == 1:
        return assigned.pop()
    if len(assigned) > 1:
        return None  # the transcript holds every worker's assignment (trial-6: five spawns, every stop judged as S01); whose stop this is cannot be told, so do not block
    counts = {}
    for sid in SECTION_RE.findall(text):
        if (run / "sections" / sid).exists():
            counts[sid] = counts.get(sid, 0) + 1
    return max(counts, key=counts.get) if counts else None


def main():
    data = L.read_hook_input()
    if data.get("stop_hook_active"):
        return
    transcript = Path(data.get("transcript_path", ""))
    text = transcript.read_text(errors="ignore") if transcript.exists() else ""
    run = L.current_run()
    if not run.exists():
        return
    sid = section_of(text, run)
    if not sid:
        return
    folder = run / "sections" / sid
    problems = missing_in(folder)
    if problems:
        print(json.dumps({
            "decision": "block",
            "reason": f"Not finished for {sid}: " + "; ".join(problems)
                      + ". Write both files per the output contract, then stop.",
        }))


if __name__ == "__main__":
    main()
