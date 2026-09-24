#!/usr/bin/env python3
"""PreToolUse hook on paid Picsart tools. Enforces run isolation: a paid call
may reference (imageUrls, image, startFrame, ...) only image URLs that an
earlier node in the SAME run already produced. Corpus assets, stock/pool/widened
references, prior-run outputs and anything from Picsart Drive are never in this
run's ledger, so wiring one into a node is denied here -- even when it was
laundered through media_upload (that upload is not a paid tool and never enters
the ledger). Text-only generations carry no reference URL and always pass.

With no active run (`runs/current` absent) it allows everything, like the
credit guard. Fails open on an unexpected internal error so a bug can never
brick a paid run; the URL check itself fails closed."""

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import _ledger as L  # noqa: E402

URL_RE = re.compile(r"https?://[^\s\"'\\<>]+")


def deny(reason):
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "deny",
        "permissionDecisionReason": reason,
    }}))
    sys.exit(0)


def normalize(url):
    """Drop query and fragment so a within-run URL still matches when it comes
    back as a ?download= variant; two distinct assets never share a base."""
    return url.split("#", 1)[0].split("?", 1)[0]


def main():
    data = L.read_hook_input()
    run = L.active_run(data)
    if not run.exists():
        return

    params = data.get("tool_input", {}) or {}
    referenced = {normalize(u) for u in URL_RE.findall(json.dumps(params))}
    if not referenced:
        return  # text-only generation, nothing wired

    allowed = set()
    for row in L.ledger_rows(run):
        for u in row.get("urls", []):
            allowed.add(normalize(u))

    outside = sorted(referenced - allowed)
    if outside:
        deny(
            "Run isolation: this call wires image URL(s) that no earlier node "
            "in this run produced: " + ", ".join(outside) + ". Every node input "
            "must be generated inside the current run. Corpus, references, "
            "prior-run outputs and Drive assets are read for the look only, "
            "never wired into a node."
        )


if __name__ == "__main__":
    try:
        main()
    except Exception:
        # Fail open: never brick a paid run over a guard bug.
        pass
