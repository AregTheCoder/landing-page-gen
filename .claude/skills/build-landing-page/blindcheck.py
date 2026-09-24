"""Manager's blindness check of a run, before any worker is spawned.

    uv run python .claude/skills/build-landing-page/blindcheck.py runs/<run> [Sxx]

Reads slots.json for the page's own asset identifiers (the 8-hex uuid prefix
of each src, as attrs.asset_id names it, and the 8-hex hash suffix of each
local file name), greps every sections/*/brief.md and sections/*/examples/*.md
for them, and flags a brief frontmatter line (snapshot:, source:) that points a
worker at the original. Prints one line per problem; exit 0 when the run is
blind. `similar --exclude <page>` alone is not enough: a block shared
site-wide (the tutorial grid) shows the page's own images on other pages.

Pass one section id (Sxx) to check only that section, so the manager can clear
and spawn a worker the moment its brief is written without waiting for the rest.
The page-wide id set is read from slots.json either way, so a single-section
check still catches this page's own images that leaked into that one brief."""
import json
import re
import sys
from pathlib import Path

HEX8 = re.compile(r"^[0-9a-f]{8}$")
POINTERS = re.compile(r"^(snapshot|source): ", re.M)


def identifiers(slots):
    """{8-hex id: slot id} for every slot's src prefix and local hash suffix."""
    ids = {}
    for slot_id, s in slots.items():
        stem = Path((s.get("src") or "").split("?")[0]).stem
        if HEX8.match(stem[:8]):
            ids.setdefault(stem[:8], slot_id)
        suffix = Path(s.get("local") or "").stem.rsplit("-", 1)[-1]
        if HEX8.match(suffix):
            ids.setdefault(suffix, slot_id)
    return ids


def check(run, section=None):
    run = Path(run)
    slots_path = run / "slots.json"
    if not slots_path.exists():
        return ["slots.json missing"]
    ids = identifiers(json.loads(slots_path.read_text())["slots"])
    problems = []
    if section is not None:
        secs = [run / "sections" / section] if (run / "sections" / section).exists() else []
    else:
        secs = sorted((run / "sections").glob("S*")) if (run / "sections").exists() else []
    for sec in secs:
        for f in [sec / "brief.md", *sorted(sec.glob("examples/*.md")),
                  *sorted(sec.glob("composition-*.yaml")), *sorted(sec.glob("compose-*.yaml"))]:
            if not f.exists():
                continue
            text = f.read_text()
            for i, slot in sorted(ids.items()):
                if i in text:
                    problems.append(f"{sec.name}: {f.relative_to(run)} names {i} ({slot})")
            if f.name == "brief.md":
                for m in POINTERS.finditer(text):
                    problems.append(f"{sec.name}: brief.md carries {m.group(1)}: (a worker with Bash/Read can open the original)")
    return problems


def main(argv):
    if len(argv) not in (1, 2):
        print(__doc__)
        return 2
    run, section = argv[0], (argv[1] if len(argv) == 2 else None)
    problems = check(run, section)
    for p in problems:
        print(p)
    if not problems:
        scope = f"{run} {section}" if section else run
        print(f"{scope}: blind (no original asset id or snapshot pointer in briefs and examples)")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
