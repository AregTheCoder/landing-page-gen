"""Draw random slots for a trial and set up one run folder per slot.

    uv run python .claude/skills/build-landing-page/pick.py --prefix blind-2 --n 5 --cap 6 --seed 7

Only slots the procedure lets us generate are drawn (SKILL.md §1.3): an image
whose role is generated, whose slot class the `## Slot classes` table does not
keep from source (the link-grid 5:4 thumbnails: blind-1 drew three of them),
whose labelled family is not a never-generated one, on a page whose
made-by attribution can be honoured. Each run gets `skeleton.md` +
`slots.json` (`lp-corpus skeleton`), `budget.json` and a blind
`shared-context.md`; the draw goes to `runs/<prefix>-plan.json`."""

import argparse
import json
import random
import re
import sqlite3
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(HERE))
import brief  # noqa: E402
from landing_page_gen.compose import models  # noqa: E402
from landing_page_gen.corpus.db import GENERATED_ROLES  # noqa: E402

ROW_RE = re.compile(r"^\| [a-z]+-[\d:]+(?:-video)? \|.*\|$", re.M)


def kept_classes():
    """(section type, role, aspect) of the slot classes whose table row keeps them from source."""
    out = set()
    for m in ROW_RE.finditer(brief.STYLE_FAMILIES.read_text()):
        cells = [c.strip() for c in m.group(0).strip("|").split("|")]
        if "kept-from-source" in cells[-1] or "kept-from-source" in cells[-2]:
            out.add((cells[1], cells[2], cells[3]))
    return out


def never_families():
    return {f for f in brief.family_names() if brief.never_generated(brief.family_block(f)[0])}


def candidates(con):
    """(slug, slot id, section type, class) of every image slot we may generate."""
    kept, never = kept_classes(), never_families()
    rows = con.execute("""select p.slug, m.slot_id, s.type, m.role, m.aspect, m.style, m.width, m.height
        from media m join sections s on s.id = m.section_id join pages p on p.id = s.page_id
        where m.kind = 'image' and m.local_path is not null""")
    out = []
    for slug, sid, typ, role, aspect, style, w, h in rows:
        cls = f"{typ}-{aspect}" if aspect else typ
        if role not in GENERATED_ROLES or (typ, role, aspect) in kept or (style or "").split("/")[0] in never or not (w and h):
            continue
        out.append((slug, sid, typ, cls))
    return out


def honest(slug):
    return not any(str(v["model"]).startswith("no:") for v in models.made_by(slug).values())


SHARED = """# Shared context: {run} (blind run)

One slot of the page {page} is made: {slot}; the rest of the page stays as it is. Nobody on this run has described the original image: decide from the page, the section copy and the corpus context what this slot should be, as the page's designer would.
"""


def setup(run, slug, sid, cap):
    (run / "sections").mkdir(parents=True, exist_ok=True)
    subprocess.run(["uv", "run", "lp-corpus", "skeleton", slug, "--out", str(run / "skeleton.md")],
                   cwd=REPO, check=True, capture_output=True)
    slots = json.loads((run / "slots.json").read_text())["slots"]
    if sid not in slots:
        return None
    (run / "budget.json").write_text(json.dumps({"run_credits": cap, "dry_run": False}))
    (run / "shared-context.md").write_text(SHARED.format(run=run.name, page=slug, slot=sid))
    return slots[sid].get("size")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--prefix", required=True)
    ap.add_argument("--n", type=int, default=5)
    ap.add_argument("--cap", type=int, default=6, help="credits per run")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--db", default=str(REPO / "corpus" / "corpus.db"))
    a = ap.parse_args(argv)
    with sqlite3.connect(a.db) as con:
        pool = candidates(con)
    rng = random.Random(a.seed)
    rng.shuffle(pool)
    plan, pages, types = [], set(), set()
    for slug, sid, typ, cls in pool:
        if len(plan) == a.n:
            break
        # one slot per page and per section type (galleries are half the pool; a trial
        # must reach the layered contexts too), only on pages whose model we can name
        if slug in pages or typ in types or not honest(slug):
            continue
        run = REPO / "runs" / f"{a.prefix}-{len(plan) + 1}"
        if run.exists():
            sys.exit(f"pick.py: {run} exists; choose another --prefix")
        size = setup(run, slug, sid, a.cap)
        if size is None:
            continue
        pages.add(slug)
        types.add(typ)
        plan.append([run.name, slug, sid, size, typ, cls])
        print(f"{run.name}: {slug} {sid} ({typ}, {cls})")
    (REPO / "runs" / f"{a.prefix}-plan.json").write_text(json.dumps(plan))
    return 0


if __name__ == "__main__":
    sys.exit(main())
