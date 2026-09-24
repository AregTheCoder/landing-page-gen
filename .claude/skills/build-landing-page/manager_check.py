"""The manager's procedure, checked before anything is injected.

    uv run python .claude/skills/build-landing-page/manager_check.py runs/<run>

The worker is held to its board by hooks and `lp-flow check`; this holds the
manager to SKILL.md. blind-1 skipped every step below and shipped five slots
nobody reviewed. `lp-inject` runs it on any managed run (one with
`budget.json`) and refuses to inject while it names a problem:

- `report.md` exists and records the start balance (§1.2);
- no generated slot is one the procedure keeps from source: a role that is
  never generated, a kept-from-source slot class, a never-generated family (§1.3);
- every generated slot's family makes a generation mode its context allows
  (corpus/genmode.py), or its brief carries `> mode: <mode> because <reason>`;
- every section with a chosen asset has a clean precheck (§5.1) and a
  `review-N.md` whose last verdict is `accept`, within two rework rounds (§5.2-3).
"""

import json
import re
import sys
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import brief  # noqa: E402
import pick  # noqa: E402
import precheck  # noqa: E402
from landing_page_gen.corpus.db import GENERATED_ROLES  # noqa: E402

VERDICT_RE = re.compile(r"^verdict:\s*(accept|rework|block)", re.M)
MAX_REVIEWS = 3  # the first review and two rework rounds


def frontmatter(path):
    m = re.match(r"^---\n(.*?)\n---", path.read_text(), re.S)
    return yaml.safe_load(m.group(1)) or {} if m else {}


def chosen_slots(res):
    return [sid for sid, s in (res.get("slots") or {}).items() if (s or {}).get("chosen")]


def last_verdict(folder):
    reviews = sorted(folder.glob("review-*.md"), key=lambda p: int(re.sub(r"\D", "", p.stem) or 0))
    if not reviews:
        return None, 0
    m = VERDICT_RE.search(reviews[-1].read_text())
    return (m.group(1) if m else "unreadable"), len(reviews)


def mode_problem(run, sxx, folder, n_media, section_type, fm):
    text = (folder / "brief.md").read_text() if (folder / "brief.md").exists() else ""
    fam = re.search(r"^## Style family: ([a-z0-9-]+)", text, re.M)
    if not fam:
        return f"{sxx}: brief.md names no style family"
    d = brief.directives(text)
    try:
        brief.check_mode(sxx, brief.mode_expectation(fm, section_type, n_media), fam.group(1),
                         d.get("text", "none"), d.get("mode"))
    except SystemExit as e:
        return str(e).replace("brief.py: ", "")
    return None


def check(run):
    run = Path(run)
    problems = []
    report = run / "report.md"
    if not report.exists() or not re.search(r"^#+ *Start\b.*?\d", report.read_text(), re.M | re.S):
        problems.append("report.md is missing or records no start balance (SKILL §1.2)")
    skeleton = (run / "skeleton.md").read_text()
    fm, _ = brief.read_frontmatter(skeleton)
    slots = json.loads((run / "slots.json").read_text())["slots"]
    kept, never = pick.kept_classes(), pick.never_families()
    for folder in sorted((run / "sections").glob("S*")):
        res_path = folder / "result.md"
        if not res_path.exists():
            continue
        res = frontmatter(res_path)
        made = chosen_slots(res)
        if not made or res.get("status") == "blocked":
            continue
        sxx = folder.name
        block, section_type = brief.section_block(skeleton, sxx)
        records = {r["id"]: r for r in brief.slot_records(block)}
        for sid in made:
            meta, rec = slots.get(sid) or {}, records.get(sid) or {}
            role, aspect = rec.get("role") or meta.get("role"), rec.get("aspect") or meta.get("aspect")
            if role not in GENERATED_ROLES:
                problems.append(f"{sid}: role {role} is never generated (§1.3)")
            if (section_type, role, aspect) in kept:
                problems.append(f"{sid}: {section_type} {role} {aspect} is kept from source (the slot-class table)")
            if (meta.get("style") or "").split("/")[0] in never:
                problems.append(f"{sid}: labelled {meta['style']}, a never-generated family")
        mp = mode_problem(run, sxx, folder, len(records), section_type, fm)
        if mp:
            problems.append(mp)
        problems += [f"{sxx}: precheck: {p}" for p in precheck.check(run, sxx)]
        verdict, n = last_verdict(folder)
        if verdict is None:
            problems.append(f"{sxx}: no review-N.md: spawn a section-reviewer (§5.2)")
        elif verdict != "accept":
            problems.append(f"{sxx}: last review says {verdict} (§5.3: rework, or mark the slot blocked)")
        if n > MAX_REVIEWS:
            problems.append(f"{sxx}: {n} reviews, over the two rework rounds (§5.3)")
    return problems


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 1:
        print(__doc__)
        return 2
    problems = check(argv[0])
    for p in problems:
        print(p)
    print(f"{Path(argv[0]).name}: {'procedure followed' if not problems else str(len(problems)) + ' problem(s)'}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
