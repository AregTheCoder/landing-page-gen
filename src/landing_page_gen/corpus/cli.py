"""lp-corpus: scrape Picsart landing pages into a sectioned Markdown corpus."""

import argparse
import sys
from pathlib import Path

import yaml

from . import db, discover

DEFAULT_DB = Path("corpus/corpus.db")


def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        prog="lp-corpus",
        description="Scrape Picsart landing pages into a sectioned Markdown corpus.",
    )
    p.add_argument("--db", type=Path, default=DEFAULT_DB, help="SQLite file (default corpus/corpus.db)")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("init", help="Create the database schema")

    d = sub.add_parser("discover", help="Crawl picsart.com hubs for landing-page URLs")
    d.add_argument("--out", type=Path, default=Path("corpus/pages.yaml"))
    d.add_argument("--depth", type=int, default=2)
    d.add_argument("--limit", type=int, default=300)
    d.add_argument("--seed", action="append", default=[], help="extra URL or path to include and expand (repeatable)")

    f = sub.add_parser("fetch", help="Render a page with Playwright; save HTML, screenshot, media list")
    f.add_argument("url")

    s = sub.add_parser("sectionize", help="Split a snapshot into typed sections and Markdown; index in the DB")
    s.add_argument("slug")

    k = sub.add_parser("skeleton", help="Emit skeleton.md: all text, every media node as a slot block")
    k.add_argument("slug")
    k.add_argument("--out", type=Path, required=True)

    m = sub.add_parser("similar", help="Find the k closest sections of one type, with their media")
    m.add_argument("--type", required=True, choices=db.SECTION_TYPES)
    m.add_argument("--query", required=True, help="headline plus body text of the target section")
    m.add_argument("-k", type=int, default=3)
    m.add_argument("--out", type=Path, required=True)

    a = p.parse_args(argv)
    if a.cmd == "init":
        db.connect(a.db).close()
        print(f"schema ready: {a.db}")
        return 0
    if a.cmd == "discover":
        seeds = list(discover.SEEDS) + [discover.normalize(u) for u in a.seed if discover.normalize(u)]
        pages = discover.crawl(seeds=seeds, depth=a.depth, limit=a.limit, log=lambda m: print(m, file=sys.stderr))
        rows = [{"path": path, **info} for path, info in sorted(pages.items(), key=lambda kv: (kv[1]["family"] or "zz", kv[0]))]
        a.out.parent.mkdir(parents=True, exist_ok=True)
        a.out.write_text(yaml.safe_dump(rows, sort_keys=False, allow_unicode=True))
        counts = {}
        for r in rows:
            counts[r["family"]] = counts.get(r["family"], 0) + 1
        print(f"{len(rows)} pages -> {a.out}")
        for fam, n in sorted(counts.items(), key=lambda kv: str(kv[0])):
            print(f"  {fam}: {n}")
        return 0
    sys.exit(f"lp-corpus {a.cmd}: not implemented yet (Milestone 1)")


if __name__ == "__main__":
    sys.exit(main())
