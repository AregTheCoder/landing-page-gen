"""lp-corpus: scrape Picsart landing pages into a sectioned Markdown corpus."""

import argparse
import sys
from pathlib import Path

import yaml

from . import attrs, db, discover, media, sectionize, similar, skeleton, snapshot, styles, taxonomy

DEFAULT_DB = Path("corpus/corpus.db")
PAGES_YAML = Path("corpus/pages.yaml")


def log(msg):
    print(msg, file=sys.stderr, flush=True)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        prog="lp-corpus",
        description="Scrape Picsart landing pages into a sectioned Markdown corpus.",
    )
    p.add_argument("--db", type=Path, default=DEFAULT_DB, help="SQLite file (default corpus/corpus.db)")
    p.add_argument("--pages-dir", type=Path, default=snapshot.PAGES_DIR, help="snapshot folder (default corpus/pages)")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("init", help="Create the database schema")

    d = sub.add_parser("discover", help="Crawl picsart.com hubs for landing-page URLs")
    d.add_argument("--out", type=Path, default=PAGES_YAML)
    d.add_argument("--depth", type=int, default=2)
    d.add_argument("--limit", type=int, default=300)
    d.add_argument("--seed", action="append", default=[], help="extra URL or path to include and expand (repeatable)")

    f = sub.add_parser("fetch", help="Snapshot pages: HTML (reassembled), screenshot, media geometry")
    f.add_argument("urls", nargs="*", help="page URLs or paths")
    f.add_argument("--family", action="append", default=[], help="fetch every page of this family from pages.yaml (repeatable)")
    f.add_argument("--all", action="store_true", help="fetch every page in pages.yaml")
    f.add_argument("--no-render", action="store_true", help="skip Playwright (no screenshot, no rendered sizes)")
    f.add_argument("--no-media", action="store_true", help="keep media as CDN links instead of downloading into media/")
    f.add_argument("--force", action="store_true", help="re-fetch pages that already have a snapshot")
    f.add_argument("--sectionize", action="store_true", help="index each page right after fetching it")

    s = sub.add_parser("sectionize", help="Split snapshots into typed sections; stamp ids; index in the DB")
    s.add_argument("slugs", nargs="*")
    s.add_argument("--all", action="store_true", help="every fetched page")

    md = sub.add_parser("media", help="Download a snapshot's images and videos into media/ and link them locally")
    md.add_argument("slugs", nargs="*")
    md.add_argument("--all", action="store_true", help="every fetched page")

    k = sub.add_parser("skeleton", help="Emit skeleton.md (+ slots.json): all text, every media node as a slot block")
    k.add_argument("slug")
    k.add_argument("--out", type=Path, required=True)

    sm = sub.add_parser("similar", help="Find the k closest sections of one type, with their media")
    sm.add_argument("--type", required=True, choices=db.SECTION_TYPES)
    sm.add_argument("--query", required=True, help="headline plus body text of the target section")
    sm.add_argument("-k", type=int, default=3)
    sm.add_argument("--exclude", help="page slug to leave out (the page the skeleton came from)")
    sm.add_argument("--style", help="prefer sections whose media carry this style family, as family[/variant] (e.g. dark-composite/light)")
    sm.add_argument("--attr", action="append", default=[], metavar="KEY=VALUE",
                    help="prefer sections whose media attribute matches, e.g. ground=black (repeatable)")
    sm.add_argument("--exclude-asset", help="skip sections showing this source asset (8-hex id or any part of its src)")
    sm.add_argument("--any-media", action="store_true", help="also return sections without creative/thumbnail media")
    sm.add_argument("--out", type=Path, required=True, help="folder for the excerpts and media")

    st = sub.add_parser("styles", help="Tag creative media with a style family (Claude vision) -> corpus/styles.yaml + media.style")
    st.add_argument("--styles", type=Path, default=styles.STYLES_YAML, help="yaml of tags (default corpus/styles.yaml)")
    st.add_argument("--apply-only", action="store_true", help="only mirror the yaml into the DB, no classification")
    st.add_argument("--force", action="store_true", help="re-classify media that already have a tag")
    st.add_argument("--model", default=styles.MODEL)
    st.add_argument("--limit", type=int, help="classify at most this many (for a trial pass)")
    st.add_argument("--from-attrs", action="store_true", help="derive the yaml from corpus/attributes.yaml through the rule table (no model)")
    st.add_argument("--attrs", type=Path, default=attrs.ATTRIBUTES_YAML, help="attributes yaml for --from-attrs")

    at = sub.add_parser("attrs", help="Describe every distinct generated-role asset with Claude vision -> corpus/attributes.yaml, media.attrs, media.style")
    at.add_argument("--attrs", type=Path, default=attrs.ATTRIBUTES_YAML)
    at.add_argument("--frames", type=Path, default=attrs.FRAMES_DIR, help="cache of video poster frames")
    at.add_argument("--model", default=attrs.MODEL, help="model for card/panel/wide assets")
    at.add_argument("--model-tiles", default=attrs.MODEL_TILES, help="model for tile-class assets")
    at.add_argument("--limit", type=int)
    at.add_argument("--force", action="store_true", help="re-describe assets already in the yaml")
    at.add_argument("--roles", default=",".join(db.GENERATED_ROLES), help="comma list of media roles (default creative,thumbnail)")
    at.add_argument("--kinds", default="image,video")
    at.add_argument("--types", help="comma list of section types to restrict to")
    at.add_argument("--no-video", action="store_true")
    at.add_argument("--workers", type=int, default=8)
    at.add_argument("--dry-run", action="store_true", help="count candidates and estimate cost; no model call")
    at.add_argument("--apply-only", action="store_true", help="mirror the yaml into the DB through the rule table; no model call")

    tx = sub.add_parser("taxonomy", help="Cross-tab the tagged assets and lay out contact sheets -> report.md, groups.json, PNGs")
    tx.add_argument("--attrs", type=Path, default=attrs.ATTRIBUTES_YAML)
    tx.add_argument("--out", type=Path, default=Path("corpus/taxonomy"))
    tx.add_argument("--by", default="type,aspect_class,ground,layout", help="comma list of grouping keys (type is always first)")
    tx.add_argument("--min", type=int, default=5, help="groups with fewer assets share one sheet per type")
    tx.add_argument("--per-cell", type=int, default=12, help="thumbnails per sheet")

    a = p.parse_args(argv)
    if a.cmd == "init":
        db.connect(a.db).close()
        print(f"schema ready: {a.db}")
        return 0
    if a.cmd == "discover":
        return cmd_discover(a)
    if a.cmd == "fetch":
        return cmd_fetch(a)
    if a.cmd == "sectionize":
        return cmd_sectionize(a)
    if a.cmd == "media":
        return cmd_media(a)
    if a.cmd == "styles":
        return cmd_styles(a)
    if a.cmd == "attrs":
        return cmd_attrs(a)
    if a.cmd == "taxonomy":
        return cmd_taxonomy(a)
    if a.cmd == "skeleton":
        con = db.connect(a.db)
        out, n_sections, n_gen, n_all = skeleton.write_skeleton(con, a.slug, a.out)
        print(f"{out}: {n_sections} sections, {n_all} slots ({n_gen} to generate); slots.json alongside")
        return 0
    if a.cmd == "similar":
        con = db.connect(a.db)
        try:
            similar.split_style(a.style)
        except ValueError as exc:
            p.error(str(exc))
        attr_filter = dict(kv.split("=", 1) for kv in a.attr)
        bad = set(attr_filter) - set(attrs.FIELDS)
        if bad:
            p.error(f"unknown attribute(s) {', '.join(sorted(bad))}; one of {', '.join(attrs.FIELDS)}")
        rows = similar.find_similar(con, a.type, a.query, k=a.k, exclude=a.exclude, need_media=not a.any_media,
                                    style=a.style, attrs=attr_filter or None, exclude_asset=a.exclude_asset)
        if not rows:
            log(f"no {a.type} sections in the corpus" + (" with generated-role media" if not a.any_media else ""))
            return 1
        with similar.FrameGrabber() as grabber:
            similar.write_examples(con, rows, a.out, log=log, grabber=grabber)
        fam = similar.split_style(a.style)[0]
        tagged = sum(1 for r in rows if con.execute(
            "SELECT 1 FROM media WHERE section_id = ? AND style = ?", (r["id"], fam)).fetchone()) if fam else 0
        print(f"{len(rows)} {a.type} example(s)" + (f", {tagged} tagged {a.style}" if a.style else "") + f" -> {a.out}")
        return 0
    return 2


def cmd_discover(a):
    seeds = list(discover.SEEDS) + [discover.normalize(u) for u in a.seed if discover.normalize(u)]
    pages = discover.crawl(seeds=seeds, depth=a.depth, limit=a.limit, log=log)
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


def inventory():
    return yaml.safe_load(PAGES_YAML.read_text()) if PAGES_YAML.exists() else []


def cmd_fetch(a):
    targets = [(u, None) for u in a.urls]
    if a.all or a.family:
        for row in inventory():
            if a.all or row.get("family") in a.family:
                targets.append((row["path"], row.get("family")))
    if not targets:
        log("fetch: give URLs, --family <f> or --all")
        return 2
    if not a.force:
        # meta.json is written last, so its presence means the whole page landed
        done = lambda u: (a.pages_dir / snapshot.slug_for(u) / "meta.json").exists()  # noqa: E731
        skipped = [u for u, _ in targets if done(u)]
        targets = [(u, f) for u, f in targets if not done(u)]
        if skipped:
            log(f"skipping {len(skipped)} already fetched (use --force to redo)")
    con = db.connect(a.db) if a.sectionize else None
    failures = []

    def run(renderer):
        for i, (url, family) in enumerate(targets, 1):
            log(f"[{i}/{len(targets)}] {url}")
            try:
                page_dir = snapshot.save_page(url, a.pages_dir, renderer=renderer, family=family, log=log,
                                              localise=not a.no_media)
                if con is not None:
                    sectionize.sectionize_page(page_dir, con, log=log)
            except Exception as exc:  # keep going through the inventory
                failures.append((url, repr(exc)))
                log(f"  FAILED {url}: {exc!r}")

    if a.no_render:
        run(None)
    else:
        with snapshot.Renderer() as renderer:
            run(renderer)
    print(f"fetched {len(targets) - len(failures)}/{len(targets)} pages -> {a.pages_dir}")
    for url, err in failures:
        print(f"  failed: {url}: {err}")
    return 1 if failures else 0


def is_snapshot(d):
    """A complete snapshot: meta.json is written last; app shells have no page.html."""
    return (d / "meta.json").exists() and (d / "page.html").exists()


def page_dirs(a):
    if a.all:
        return sorted(d for d in a.pages_dir.iterdir() if is_snapshot(d))
    return [a.pages_dir / s for s in a.slugs]


def for_each_page(a, step):
    """Run step(page_dir) over the requested snapshots; collect failures."""
    dirs = page_dirs(a)
    if not dirs:
        log(f"{a.cmd}: give slugs or --all")
        return None
    failures = []
    for d in dirs:
        if not is_snapshot(d):
            failures.append((d.name, "no complete snapshot (missing, partial, or an app shell)"))
            log(f"{d.name}: no complete snapshot; run `lp-corpus fetch` first")
            continue
        try:
            step(d)
        except Exception as exc:
            failures.append((d.name, repr(exc)))
            log(f"  FAILED {d.name}: {exc!r}")
    return failures


def cmd_media(a):
    counts = {"ok": 0, "failed": 0}

    def step(d):
        c = media.localise_page(d, log=log)
        counts["ok"] += c["ok"]
        counts["failed"] += c["failed"]

    failures = for_each_page(a, step)
    if failures is None:
        return 2
    print(f"media: {counts['ok']} files downloaded or present, {counts['failed']} failed -> {a.pages_dir}")
    for slug, err in failures:
        print(f"  failed: {slug}: {err}")
    return 1 if failures else 0


def cmd_sectionize(a):
    con = db.connect(a.db)
    failures = for_each_page(a, lambda d: sectionize.sectionize_page(d, con, log=log))
    if failures is None:
        return 2
    n_pages, n_sections, n_media = con.execute(
        "SELECT (SELECT count(*) FROM pages), (SELECT count(*) FROM sections), (SELECT count(*) FROM media)").fetchone()
    attrs.apply(con, attrs.load())  # re-indexing recreates media rows without their attributes, families, role fixes
    n_styled = styles.apply(con, styles.load())
    print(f"corpus: {n_pages} pages, {n_sections} sections, {n_media} media ({n_styled} style-tagged) in {a.db}")
    for slug, err in failures:
        print(f"  failed: {slug}: {err}")
    return 1 if failures else 0


def cmd_attrs(a):
    con = db.connect(a.db)
    if a.apply_only:
        mapping = attrs.load(a.attrs)
        n = attrs.apply(con, mapping)
        print(f"attrs: {len(mapping)} assets applied, {n} media rows touched, "
              f"{100 * taxonomy.resolved_share(mapping):.0f} % resolve to a family")
        return 0
    roles = tuple(a.roles.split(",")) if a.roles else None
    types = tuple(a.types.split(",")) if a.types else None
    mapping, stats = attrs.run(con, model=a.model, model_tiles=a.model_tiles, limit=a.limit, force=a.force, roles=roles,
                               kinds=tuple(a.kinds.split(",")), types=types, workers=a.workers, no_video=a.no_video,
                               dry_run=a.dry_run, log=log, path=a.attrs, frames_dir=a.frames)
    e = stats["estimate"]
    print(f"attrs: {e['candidates']} candidates ({e['by_kind']['image']} images, {e['by_kind']['video']} videos; "
          + ", ".join(f"{s} {n}" for s, n in e["by_size"].items() if n) + "); "
          + ", ".join(f"{m} x{n}" for m, n in e["by_model"].items()) + f"; about ${e['usd']}")
    if a.dry_run:
        return 0
    n = attrs.apply(con, mapping)
    u = stats["usage"]
    print(f"attrs: {stats['tagged']} described, {len(stats['skipped'])} skipped, {n} media rows touched -> {a.attrs}; "
          f"tokens in {u['input_tokens']} (cached {u['cache_read_input_tokens']}) out {u['output_tokens']}; "
          f"{len(mapping)} assets in yaml, {100 * taxonomy.resolved_share(mapping):.0f} % resolve to a family")
    for page, slot, reason in stats["skipped"][:20]:
        print(f"  skipped {page} {slot}: {reason}")
    return 0


def cmd_taxonomy(a):
    mapping = attrs.load(a.attrs)
    if not mapping:
        log(f"taxonomy: {a.attrs} is empty; run `lp-corpus attrs` first")
        return 1
    report, n_groups, n_unresolved = taxonomy.write_report(mapping, a.out, keys=tuple(a.by.split(",")), min_n=a.min,
                                                            per_cell=a.per_cell)
    print(f"taxonomy: {len(mapping)} assets in {n_groups} groups, {n_unresolved} unresolved -> {report}")
    return 0


def cmd_styles(a):
    con = db.connect(a.db)
    if a.from_attrs:
        mapping = styles.derive(attrs.load(a.attrs), styles.load(a.styles))
        styles.save(mapping, a.styles)
        n = styles.apply(con, mapping)
        print(f"styles: {len(mapping)} entries derived from {a.attrs} -> {a.styles}; {n} media rows tagged")
        return 0
    if a.apply_only:
        n = styles.apply(con, styles.load(a.styles))
        print(f"styles: {n} media rows tagged from {a.styles}")
        return 0
    mapping, n_alt, n_model, n_rows = styles.run(con, model=a.model, limit=a.limit, force=a.force, log=log, path=a.styles)
    hist = {}
    for v in mapping.values():
        hist[v["style"]] = hist.get(v["style"], 0) + 1
    print(f"styles: {n_alt} tagged by alt, {n_model} sent to {a.model}, {n_rows} media rows tagged -> {a.styles}")
    for style, n in sorted(hist.items(), key=lambda kv: -kv[1]):
        print(f"  {style}: {n}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
