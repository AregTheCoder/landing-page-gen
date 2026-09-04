"""lp-inject: write the chosen media from a run's page.md back into the page's
HTML snapshot and emit dist/index.html. Implementation lands in Milestone 2."""

import argparse
import sys
from pathlib import Path


def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        prog="lp-inject",
        description="Inject a run's chosen media into the source HTML snapshot.",
    )
    p.add_argument("run", type=Path, help="run folder containing page.md and slots.json")
    p.add_argument("--out", type=Path, help="output folder (default <run>/dist)")
    a = p.parse_args(argv)
    out = a.out or a.run / "dist"
    sys.exit(f"lp-inject: not implemented yet (Milestone 2); would write {out}")


if __name__ == "__main__":
    sys.exit(main())
