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
    if list(folder.glob("proposal-*.yaml")) and not (folder / "workflow.yaml").exists():
        return []  # a blind run's phase 1: the proposal is the whole deliverable, the board comes in phase 2
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


FOLDER_RE = re.compile(r"(/\S*?/runs/[^/\s`'\"]+)/sections/(S\d+)\b")


def assigned_folder(transcript):
    """The section folder the worker was given by path (`.../runs/<run>/sections/Sxx`),
    so a worker of another run is checked in its own run, not in runs/current."""
    if not transcript.exists():
        return None
    m = FOLDER_RE.search(first_user_message(transcript))
    return Path(m.group(1)) / "sections" / m.group(2) if m else None


def main():
    data = L.read_hook_input()
    if data.get("stop_hook_active"):
        return
    transcript = Path(data.get("agent_transcript_path") or data.get("transcript_path", ""))
    sid = assigned_section(transcript)
    folder = assigned_folder(transcript)
    if folder is None:
        run = L.current_run()
        if not sid or not run.exists():
            return
        folder = run / "sections" / sid
    elif not folder.parent.parent.exists():
        return
    problems = missing_in(folder)
    if problems:
        print(json.dumps({
            "decision": "block",
            "reason": f"Not finished for {sid}: " + "; ".join(problems)
                      + ". Write both files per the output contract, then stop.",
        }))


if __name__ == "__main__":
    main()
