#!/usr/bin/env python3
"""SubagentStop hook for section-worker. Reads the worker's own transcript
(`agent_transcript_path`; the input's `transcript_path` is the main session,
which mentions every section) and takes the section from the worker's first
user message, its assignment ("Section S07. Work only inside
.../sections/S07/"). Blocks the stop until workflow.yaml and result.md exist
there with their required keys."""

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
SECTION_RE = re.compile(r"(?:/sections/|\bSection )(S\d+)\b")


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


def assigned_section(transcript):
    if not transcript.exists():
        return None
    sids = SECTION_RE.findall(first_user_message(transcript))
    if not sids:  # older transcripts without a user turn: first mention anywhere
        sids = SECTION_RE.findall(transcript.read_text(errors="ignore"))
    return sids[0] if sids else None


def main():
    data = L.read_hook_input()
    if data.get("stop_hook_active"):
        return
    transcript = Path(data.get("agent_transcript_path") or data.get("transcript_path", ""))
    sid = assigned_section(transcript)
    run = L.current_run()
    if not sid or not run.exists():
        return
    problems = missing_in(run / "sections" / sid)
    if problems:
        print(json.dumps({
            "decision": "block",
            "reason": f"Not finished for {sid}: " + "; ".join(problems)
                      + ". Write both files per the output contract, then stop.",
        }))


if __name__ == "__main__":
    main()
