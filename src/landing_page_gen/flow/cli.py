"""lp-flow: check a slot's workflow.yaml as a Picsart Flow board, render its
canvas sheet, or search the gallery template catalogue."""

import argparse
import sys
from pathlib import Path

from . import board


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="lp-flow", description="Picsart Flow boards for landing-page slots.")
    sub = p.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("check", help="Does every board in these workflow.yaml files wire START -> nodes -> END?")
    c.add_argument("files", nargs="+", type=Path)

    s = sub.add_parser("sheet", help="Render a workflow.yaml as the node sheet a person rebuilds on the Flow canvas")
    s.add_argument("file", type=Path)
    s.add_argument("--out", type=Path, help="write here (default: flow.md beside the workflow)")

    t = sub.add_parser("templates", help="Gallery templates that fit a family, device or query words")
    t.add_argument("--family")
    t.add_argument("--device")
    t.add_argument("--query", default="")
    t.add_argument("--catalogue", type=Path, default=board.TEMPLATES_YAML)

    a = p.parse_args(argv)
    if a.cmd == "check":
        problems = [pr for f in a.files for pr in board.check_file(f)]
        for pr in problems:
            print(pr)
        print(f"{len(a.files)} file(s): {'boards wire' if not problems else str(len(problems)) + ' problem(s)'}")
        return 1 if problems else 0
    if a.cmd == "sheet":
        out = a.out or a.file.with_name("flow.md")
        out.write_text(board.sheet_file(a.file))
        print(out)
        return 0
    if a.cmd == "templates":
        hits = board.find_templates(a.family, a.device, a.query, a.catalogue)
        if not hits:
            print("no template fits: start from a blank board")
            return 1
        for t in hits:
            fits = t.get("fits") or {}
            print(f"- {t['title']} [{t.get('category', '')}] {t.get('url', '')}\n"
                  f"    shape: {t.get('shape', '')}\n"
                  f"    fits: families {', '.join(fits.get('families') or []) or '—'}; "
                  f"devices {', '.join(fits.get('devices') or []) or '—'}")
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
