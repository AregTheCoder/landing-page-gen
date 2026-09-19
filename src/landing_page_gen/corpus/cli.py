"""lp-corpus: scrape Picsart landing pages into a sectioned Markdown corpus."""

import argparse
import sys
from pathlib import Path

import yaml

from . import apiclient, attrs, calibration, db, discover, doctor, embed, label, ledger, library, media, pool, sectionize, sheets, similar, skeleton, snapshot, stock, styles, taxonomy, widen

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
    sm.add_argument("--media-per-example", type=int, default=similar.MAX_EXAMPLE_MEDIA,
                    help="images per example section written to --out (default 1)")
    sm.add_argument("--exclude", help="page slug to leave out (the page the skeleton came from)")
    sm.add_argument("--style", help="prefer sections whose media carry this style family, as family[/variant] (e.g. dark-composite/light)")
    sm.add_argument("--attr", action="append", default=[], metavar="KEY=VALUE",
                    help="prefer sections whose media attribute matches, e.g. ground=black (repeatable)")
    sm.add_argument("--exclude-asset", action="append", default=[], metavar="ID",
                    help="skip sections showing this source asset: the 8-hex uuid prefix of its src (attrs.asset_id) "
                         "or the 8-hex hash of its local file name; repeatable, one per slot of the page")
    sm.add_argument("--any-media", action="store_true", help="also return sections without creative/thumbnail media")
    sm.add_argument("--kind", choices=("image", "video"),
                    help="prefer sections with media of this kind and write that media first (a video slot wants clips: "
                         "a clip is excerpted as a first/middle/last 3-frame strip)")
    sm.add_argument("--widen", type=int, default=0, metavar="N",
                    help="add N reverse-image neighbours of the --style family from corpus/widened/ as look references")
    sm.add_argument("--pool", type=int, default=0, metavar="N",
                    help="add N kept licensed stock images of the --style family from corpus/pool/ as look references")
    sm.add_argument("--seed", default="", help="rotation seed for --pool (the run folder name): same seed, same picks")
    sm.add_argument("--pool-aspect", choices=sectionize.ASPECT_CLASSES, help="only pool entries of this aspect class")
    sm.add_argument("--out", type=Path, required=True, help="folder for the excerpts and media")

    w = sub.add_parser("widen", help="Reverse-image search every tagged asset of a family -> corpus/widened/<family>.yaml")
    w.add_argument("family", choices=db.STYLES)
    w.add_argument("--backend", choices=widen.BACKENDS, default="serpapi-lens",
                   help="serpapi-lens (Google Lens via SerpApi, SERPAPI_KEY) or vision-web (Cloud Vision, GOOGLE_VISION_API_KEY)")
    w.add_argument("--limit", type=int, help="search at most this many assets")
    w.add_argument("--exact", action="store_true", help="exact matches (the photo's own stock page) instead of visual neighbours")
    w.add_argument("--out", type=Path, default=widen.WIDENED_DIR)

    pl = sub.add_parser("pool", help="Licensed stock pool per family: search -> sheets -> labels; served by `similar --pool`")
    pl.add_argument("stage", choices=("search", "sheets", "labels", "embed", "calibrate", "quota", "index", "find"),
                    help="search = fetch, dedupe and rank new candidates; sheets = contact sheets of pending entries; "
                         "labels = merge the answers, keep or drop; embed = build the CLIP cache the clip ranker reads; "
                         "calibrate = turn the answers into a threshold and per-term keep rates; quota = how much each family is owed; "
                         "index = merge descriptions (--from) and rebuild the content index; find = rank images for a slot by --need x score")
    pl.add_argument("family", nargs="?", choices=db.STYLES, help="style family (labels without one merges every family)")
    pl.add_argument("--terms", action="append", default=[],
                    help="search term (repeatable; default: the family's corpus/references search_terms)")
    pl.add_argument("--limit-per-term", type=int, default=30,
                    help="admitted candidates per platform per term per run (default 30)")
    pl.add_argument("--platform", action="append", choices=stock.PLATFORMS + ("all",),
                    help="repeatable; default all (a platform with no key is skipped)")
    pl.add_argument("--orientation", choices=stock.ORIENTATIONS, help="passed to every API; default: the family's own shape")
    pl.add_argument("--pages", type=int, default=1, help="how deep to page, breadth-first (default 1)")
    pl.add_argument("--min-width", type=int, default=pool.MIN_WIDTH, help=f"reject narrower photos (default {pool.MIN_WIDTH})")
    pl.add_argument("--keep-floor", type=float, default=pool.KEEP_FLOOR,
                    help="calibrated keep rate below which a term gets no second page")
    pl.add_argument("--explore", type=float, default=pool.EXPLORE,
                    help="share of below-threshold candidates sheeted anyway (default 0.1)")
    pl.add_argument("--composition", choices=pool.COMPOSITIONS, default=pool.BARE,
                    help="bare = the raw photograph that goes inside the chrome (default); "
                         "layout = a picture that already carries the arrangement "
                         "(split, grid, collage, mockup scene)")
    pl.add_argument("--max-per-creator", type=int, default=pool.MAX_PER_CREATOR,
                    help=f"cap on one creator's shoot per term (default {pool.MAX_PER_CREATOR}); "
                         "raise it for template families, where a serial set is the point")
    pl.add_argument("--no-threshold", action="store_true", help="sheet everything: ignore the calibrated auto-drop")
    pl.add_argument("--deep", action="store_true",
                    help="page every term to the full --pages depth: ignore the keep-floor and "
                         "yield-floor early-stops so a page-1-exhausted term still reaches new photos "
                         "deeper in. Trades relevance for volume; the threshold and review still curate")
    pl.add_argument("--kind", choices=("image", "video"), default="image",
                    help="pool search: photos (default) or clips (Pexels and Pixabay video APIs; the poster frame is "
                         "what gets hashed, ranked and sheeted; served by `similar --pool N --kind video` as strips)")
    pl.add_argument("--dry-run", action="store_true", help="print the planned requests per platform and make none")
    pl.add_argument("--refresh", action="store_true", help="bypass the response cache (Pixabay keeps its 24 h floor)")
    pl.add_argument("--max-requests", type=int, default=0, help="stop the run after this many API requests (0 = tier caps only)")
    pl.add_argument("--resheet", action="store_true", help="rebuild sheets for entries already stamped with one")
    pl.add_argument("--rank", choices=tuple(pool.RANKERS), help="ranker (default: clip when `uv sync --extra embed` is installed)")
    pl.add_argument("--describe", action="store_true", help="pool embed: report the cache instead of building it")
    pl.add_argument("--write", action="store_true", help="pool calibrate: write _calibration.yaml instead of only printing it")
    pl.add_argument("--family-check", action="store_true", help="pool calibrate: also run the leave-one-out family agreement check (needs the clip cache)")
    pl.add_argument("--quota-base", type=int, default=pool.QUOTA_BASE, help="candidates per platform for the largest family")
    pl.add_argument("--from", dest="from_jsonl", type=Path, help="pool index: merge descriptions from this {id, description} JSONL before rebuilding")
    pl.add_argument("--need", help="pool find: the slot's content need, e.g. 'product on pink seamless, hard shadow'")
    pl.add_argument("--aspect", help="pool find: restrict to one aspect_class, e.g. 3:4")
    pl.add_argument("--state", action="append", choices=("pending", "kept", "dropped"),
                    help="pool find: entry state(s) to search (repeatable; default kept)")
    pl.add_argument("-k", type=int, default=10, help="pool find: how many results (default 10)")
    pl.add_argument("--out", type=Path, default=pool.POOL_DIR)

    st = sub.add_parser("styles", help="Derive corpus/styles.yaml from the attributes through the rule table, or mirror it into media.style")
    st.add_argument("--styles", type=Path, default=styles.STYLES_YAML, help="yaml of tags (default corpus/styles.yaml)")
    st.add_argument("--apply-only", action="store_true", help="only mirror the yaml into the DB")
    st.add_argument("--from-attrs", action="store_true", help="derive the yaml from corpus/attributes.yaml through the rule table")
    st.add_argument("--attrs", type=Path, default=attrs.ATTRIBUTES_YAML, help="attributes yaml for --from-attrs")

    at = sub.add_parser("attrs", help="Measure every distinct generated-role asset (ground, layout, panels, before/after) -> corpus/attributes.yaml, media.attrs, media.style")
    at.add_argument("--attrs", type=Path, default=attrs.ATTRIBUTES_YAML)
    at.add_argument("--frames", type=Path, default=attrs.FRAMES_DIR, help="cache of video poster frames")
    at.add_argument("--limit", type=int)
    at.add_argument("--force", action="store_true", help="re-measure assets already in the yaml")
    at.add_argument("--roles", default=",".join(db.GENERATED_ROLES), help="comma list of media roles (default creative,thumbnail)")
    at.add_argument("--kinds", default="image,video")
    at.add_argument("--types", help="comma list of section types to restrict to")
    at.add_argument("--no-video", action="store_true")
    at.add_argument("--dry-run", action="store_true", help="count candidates only; measure nothing")
    at.add_argument("--apply-only", action="store_true", help="mirror the yaml into the DB through the rule table")

    fr = sub.add_parser("frames", help="Grab a clip's sampled frames and write its 3-frame strip (first, middle, last) -> --out; prints the measured motion fields")
    fr.add_argument("video", help="a local clip or a URL")
    fr.add_argument("--out", type=Path, required=True, help="the strip PNG")
    fr.add_argument("--keep-frames", action="store_true", help="leave the five sampled frames beside the strip")

    mo = sub.add_parser("motion", help="Measure the motion fields (pace, loop, camera when it holds) of the video records that lack them -> attributes.yaml, media.attrs; --summary per family, --write-doc sets the **Motion:** lines")
    mo.add_argument("--attrs", type=Path, default=attrs.ATTRIBUTES_YAML)
    mo.add_argument("--frames", type=Path, default=attrs.FRAMES_DIR)
    mo.add_argument("--limit", type=int)
    mo.add_argument("--force", action="store_true", help="re-measure videos that already have motion fields")
    mo.add_argument("--summary", action="store_true", help="print what each family's labelled clips do and stop")
    mo.add_argument("--write-doc", action="store_true", help="with --summary: set each family block's **Motion:** line")
    mo.add_argument("--doc", type=Path, default=styles.DOC)

    sh = sub.add_parser("sheets", help="Lay the assets that still need semantic fields on numbered contact sheets -> corpus/labels/")
    sh.add_argument("--attrs", type=Path, default=attrs.ATTRIBUTES_YAML)
    sh.add_argument("--out", type=Path, default=sheets.LABELS_DIR)
    sh.add_argument("--per-sheet", type=int, default=sheets.PER_SHEET)
    sh.add_argument("--thumb", type=int, default=sheets.THUMB)
    sh.add_argument("--columns", type=int, default=sheets.COLUMNS)
    sh.add_argument("--limit", type=int, help="write at most this many sheets (a trial pass)")
    sh.add_argument("--skip-resolved", action="store_true",
                    help="leave out assets the measured fields alone already place in a family")

    lb = sub.add_parser("labels", help="Merge every <sheet>.answers.yaml into corpus/attributes.yaml, media.attrs, media.style")
    lb.add_argument("--attrs", type=Path, default=attrs.ATTRIBUTES_YAML)
    lb.add_argument("--labels", type=Path, default=sheets.LABELS_DIR)
    lb.add_argument("--prompt", action="store_true", help="print the labelling prompt and stop")

    tx = sub.add_parser("taxonomy", help="Cross-tab the tagged assets and lay out contact sheets -> report.md, groups.json, PNGs")
    tx.add_argument("--attrs", type=Path, default=attrs.ATTRIBUTES_YAML)
    tx.add_argument("--out", type=Path, default=Path("corpus/taxonomy"))
    tx.add_argument("--by", default="type,aspect_class,ground,layout", help="comma list of grouping keys (type is always first)")
    tx.add_argument("--min", type=int, default=5, help="groups with fewer assets share one sheet per type")
    tx.add_argument("--per-cell", type=int, default=12, help="thumbnails per sheet")

    org = sub.add_parser("organise", help="Rebuild library/: a browsable tree of pages + assets filed by model -> art_style -> structure, each with a Markdown sidecar")
    org.add_argument("--root", type=Path, default=library.LIBRARY_DIR)
    org.add_argument("--attrs", type=Path, default=attrs.ATTRIBUTES_YAML)
    org.add_argument("--styles", type=Path, default=styles.STYLES_YAML)
    org.add_argument("--frames", type=Path, default=attrs.FRAMES_DIR)
    org.add_argument("--dry-run", action="store_true", help="count what would be built, write nothing")

    fb = sub.add_parser("feedback", help="Queue a finished run's data-suspect originals (benchmark family-mismatch flags on chrome-unanswered tags) for re-labelling first")
    fb.add_argument("run", type=Path, help="runs/<run> with benchmark.md and slots.json")
    fb.add_argument("--attrs", type=Path, default=attrs.ATTRIBUTES_YAML)

    sub.add_parser("doctor", help="Verify the corpus conforms to the metastructure (snapshots indexed, assets measured, styles synced, labels in-enum, pool well-formed); exits non-zero on an ERROR")

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
    if a.cmd == "frames":
        return cmd_frames(a)
    if a.cmd == "motion":
        return cmd_motion(a)
    if a.cmd == "sheets":
        return cmd_sheets(a)
    if a.cmd == "labels":
        return cmd_labels(a)
    if a.cmd == "taxonomy":
        return cmd_taxonomy(a)
    if a.cmd == "organise":
        return cmd_organise(a)
    if a.cmd == "feedback":
        return cmd_feedback(a)
    if a.cmd == "doctor":
        return doctor.report(doctor.run(a.db))
    if a.cmd == "widen":
        try:
            path, searched, added = widen.widen(a.family, styles.load(), backend=a.backend, limit=a.limit,
                                                exact=a.exact, out_dir=a.out, log=log)
        except ValueError as exc:
            p.error(str(exc))
        print(f"{path}: {searched} asset(s) searched, {added} match(es) added")
        return 0
    if a.cmd == "pool":
        if a.stage in ("search", "sheets") and not a.family:
            p.error(f"pool {a.stage} needs a family")
        try:
            if a.stage == "quota":
                counts = pool.family_counts()
                cal = calibration.load()
                kept = {fam: sum(1 for e in pool.load(fam, a.out)["entries"].values() if e.get("state") == "kept")
                        for fam in db.STYLES}
                print(f"{'family':22} {'corpus':>7} {'kept':>6} {'quota':>7} {'per term':>9}")
                for fam in sorted(db.STYLES, key=lambda f: counts.get(f, 0)):
                    terms = pool.reference_terms(fam) or [""]
                    want, per_term = pool.plan_search(fam, counts, terms, a.quota_base, cal)
                    print(f"{fam:22} {counts.get(fam, 0):7} {kept[fam]:6} {want:7} {per_term:9}")
                return 0
            if a.stage == "calibrate":
                fams = [a.family] if a.family else list(db.STYLES)
                entries = {fam: pool.load(fam, a.out)["entries"] for fam in fams}
                cal = calibration.calibrate(entries)
                if a.family_check:
                    try:
                        encoder = embed.load_encoder()
                    except ImportError as exc:
                        p.error(str(exc))
                    emb, _ = embed.corpus_embeddings(encoder, cache_dir=Path(a.out) / "_embed", log=log)
                    hints = {attrs.asset_id(src): (rec.get("family_hint") or None)
                             for src, rec in attrs.load().items()}
                    cal["family_check"] = calibration.family_check(emb, hints)
                for name, rec in (cal.get("rankers") or {}).items():
                    print(f"{name}: {rec['labels']} label(s), keep rate {rec['keep_rate']}, auc {rec['auc']}")
                    print(f"  threshold {rec['threshold']} at recall {rec['threshold_recall']} "
                          f"-> would skip {rec['would_skip']} of the labelled set")
                    for fam, f in (rec.get("families") or {}).items():
                        print(f"  {fam:22} {f['labels']:4} labels  keep {f['keep_rate']:<6} threshold {f['threshold']}")
                    for fam, terms in (rec.get("terms") or {}).items():
                        for term, t in terms.items():
                            if t.get("prune"):
                                print(f"  prune? {fam} {term!r}: {t['kept']}/{t['n']} kept")
                if cal.get("family_check"):
                    fc = cal["family_check"]
                    print(f"family check on {fc['n']} asset(s): argmax vs tag {fc['argmax_vs_tag']}, "
                          f"merged photo families {fc['argmax_vs_tag_merged_photo']}, "
                          f"vs hint {fc['argmax_vs_hint']} (hint vs tag {fc['hint_vs_tag']})")
                if a.write:
                    print(f"{calibration.save(cal, Path(a.out) / '_calibration.yaml')}: written")
                return 0
            if a.stage == "embed":
                if a.describe:
                    for model, rec in (embed.describe(Path(a.out) / "_embed") or {}).items():
                        for name, info in rec.items():
                            top = ", ".join(f"{f} {n}" for f, n in list(info["families"].items())[:5])
                            print(f"{model} {name}: {info['rows']} rows, dim {info['dim']}"
                                  + (f" ({top})" if top else ""))
                    return 0
                try:
                    encoder = embed.load_encoder()
                except ImportError as exc:
                    p.error(str(exc))
                _, stats = embed.corpus_embeddings(encoder, cache_dir=Path(a.out) / "_embed",
                                                   refresh=a.refresh, log=log)
                print(f"{stats['rows']} corpus still(s) on {encoder.name}: "
                      f"{stats['embedded']} embedded, {stats['reused']} reused -> {a.out}/_embed")
                return 0
            if a.stage == "search":
                chosen = [pf for pf in (a.platform or []) if pf != "all"]
                platforms = tuple(chosen) if chosen else stock.PLATFORMS
                run_id = __import__("datetime").datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
                # no key anywhere is an error pool.search raises; do not open a
                # ledger (and leave an empty sqlite behind) to find that out
                have_keys, _ = stock.keys_available(platforms)
                led = ledger.Ledger(Path(a.out) / "_api.sqlite") if have_keys else None
                client = apiclient.Client(ledger=led, run_id=run_id, max_requests=a.max_requests,
                                          refresh=a.refresh, log=log) if have_keys else None
                # load attributes+styles once here; plan/search thread these
                # through baseline/_freq/_fields/corpus_embeddings, which each
                # used to re-load them (~33x per search before this).
                common = dict(terms=a.terms or None, platforms=platforms, orientation=a.orientation,
                              pages=a.pages, min_width=a.min_width, keep_floor=a.keep_floor,
                              composition=a.composition,
                              attrs_mapping=attrs.load(), styles_mapping=styles.load(),
                              pool_dir=a.out, client=client)
                if a.dry_run:
                    common["ranker_name"] = a.rank
                if a.dry_run:
                    planned, stats = pool.plan(a.family, log=log, **common)
                    for pf, rec in planned.items():
                        windows = " ".join(f"{w['used']}/{int(w['cap'] * 0.9)} per {w['seconds']}s"
                                           for w in rec["windows"]) or "no ledger"
                        print(f"  {pf:9} {rec['planned']:4} planned  {rec['cached']:4} cached  "
                              f"{rec['to_fetch']:4} to fetch   {windows}   {'ok' if rec['ok'] else 'OVER BUDGET'}")
                    for pf in stats["skipped_platforms"]:
                        print(f"  {pf:9} no {stock.KEYS[pf]}; skipped")
                    print(f"dry run: {a.family} — {stats['terms']} term(s), pages <= {a.pages}, no requests made")
                    return 0
                paths, stats = pool.search(a.family, limit_per_term=a.limit_per_term, explore=a.explore,
                                           use_threshold=not a.no_threshold, ranker_name=a.rank,
                                           max_per_creator=a.max_per_creator, deep=a.deep, kind=a.kind,
                                           run_id=run_id, log=log, **common)
                for pf, st in stats["platforms"].items():
                    pre = st["prefiltered"]
                    print(f"  {pf:9} {st['requests']:4} req  {st['cache_hits']:3} cached  {st['results']:5} results  "
                          f"{st['dup_id']:5} known  {pre['aspect'] + pre['min_width'] + pre['no_image'] + pre['licence']:4} prefiltered  "
                          f"{st['admitted']:4} admitted  {st['thumb_bytes'] // 1024:6} KiB"
                          + (f"  STOPPED ({st['stopped']})" if st["stopped"] else ""))
                if led is not None:
                    led.append_run(stats)
                    led.prune()  # else _api.sqlite grows unbounded (10 MB and counting)
                for path in paths:
                    print(f"{path}: {stats['raw']} found, {stats['new']} new, {stats['dropped']} dropped "
                          f"({stats['dropped_by']['corpus']} corpus, {stats['dropped_by']['pool']} pool, "
                          f"{stats['dropped_by']['threshold']} below threshold)"
                          + (" (rate limited, re-run to resume)" if stats["rate_limited"] else ""))
            elif a.stage == "sheets":
                _, stats = pool.build_sheets(a.family, pool_dir=a.out, resheet=a.resheet,
                                             attrs_mapping=attrs.load(), styles_mapping=styles.load(), log=log)
                print(f"{stats['sheets']} sheet(s) for {stats['pending']} pending entr(ies) -> {a.out}/sheets")
            elif a.stage == "index":
                from . import poolindex
                if a.from_jsonl:
                    m = poolindex.merge_descriptions(a.from_jsonl, pool_dir=a.out, log=log)
                    print(f"descriptions: {m['set']} set from {m['ids']} id(s), {m['orphans']} with no pool entry")
                stats = poolindex.build(pool_dir=a.out, log=log)
            elif a.stage == "find":
                from . import poolindex
                rows = poolindex.find(need=a.need, family=a.family, aspect=a.aspect,
                                      state=tuple(a.state) if a.state else ("kept",), k=a.k, pool_dir=a.out)
                if not rows:
                    print("no matches")
                for r in rows:
                    print(f"{r['id']:20} {r['family']:20} {r['aspect_class'] or '?':6} "
                          f"score {r['score']:.3f}  {r['state']}")
                    print(f"    {(r['description'] or '(no description yet)')[:160]}")
            else:
                stats = pool.ingest_labels(a.family, pool_dir=a.out, log=log)
                for err in stats["errors"]:
                    log(f"  {err}")
                print(f"{stats['answered']}/{stats['sheets']} sheet(s) answered: "
                      f"{stats['kept']} kept, {stats['dropped']} dropped")
        except ValueError as exc:
            p.error(str(exc))
        return 0
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
                                    style=a.style, attrs=attr_filter or None, exclude_asset=a.exclude_asset, kind=a.kind)
        if not rows:
            log(f"no {a.type} sections in the corpus" + (" with generated-role media" if not a.any_media else ""))
            return 1
        fam = similar.split_style(a.style)[0]
        if (a.widen or a.pool) and not fam:
            p.error("--widen and --pool need --style: neighbours and the pool are stored per family")
        with similar.FrameGrabber() as grabber:
            similar.write_examples(con, rows, a.out, log=log, grabber=grabber, max_media=a.media_per_example, kind=a.kind)
            if a.widen:
                picks = widen.pick(fam, a.widen, exclude_asset=a.exclude_asset)
                if not picks:
                    log(f"no widened neighbours for {fam}: run `lp-corpus widen {fam}` first")
                widen.write_examples(picks, a.out, media.download, similar.to_png, log=log, start=len(rows) + 1)
            if a.pool:
                # content-match the slot's query against the described pool when an
                # index exists (photos only); else fall back to the seeded shuffle.
                # A video slot takes kept clips, served as 3-frame strips.
                picks = None
                if a.kind != "video":
                    from . import poolindex
                    picks = poolindex.picks_for(a.query, fam, a.pool, aspect=a.pool_aspect,
                                                exclude_asset=a.exclude_asset, pool_dir=pool.POOL_DIR)
                if picks is None:
                    picks = pool.pick(fam, a.pool, a.seed, exclude_asset=a.exclude_asset, aspect_class=a.pool_aspect,
                                      kind=a.kind)
                if not picks:
                    log(f"no kept pool {a.kind or 'image'} entries for {fam}: run `lp-corpus pool search {fam}"
                        f"{' --kind video' if a.kind == 'video' else ''}` and answer the sheets")
                pool.write_examples(picks, a.out, media.download, similar.to_png, log=log,
                                    start=len(rows) + 1 + a.widen, grabber=grabber)
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
    a.out.write_text(styles.dump_yaml(rows, sort_keys=False, allow_unicode=True))
    counts = {}
    for r in rows:
        counts[r["family"]] = counts.get(r["family"], 0) + 1
    print(f"{len(rows)} pages -> {a.out}")
    for fam, n in sorted(counts.items(), key=lambda kv: str(kv[0])):
        print(f"  {fam}: {n}")
    return 0


def inventory():
    return styles.load_yaml(PAGES_YAML.read_text()) if PAGES_YAML.exists() else []


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
    mapping, stats = attrs.run(con, limit=a.limit, force=a.force, roles=roles, kinds=tuple(a.kinds.split(",")),
                               types=types, no_video=a.no_video, dry_run=a.dry_run, log=log, path=a.attrs,
                               frames_dir=a.frames)
    e = stats["estimate"]
    print(f"attrs: {e['candidates']} candidates ({e['by_kind']['image']} images, {e['by_kind']['video']} videos; "
          + ", ".join(f"{s} {n}" for s, n in e["by_size"].items() if n) + ")")
    if a.dry_run:
        return 0
    n = attrs.apply(con, mapping)
    grounds = ", ".join(f"{g} {c}" for g, c in sorted(stats["grounds"].items(), key=lambda kv: -kv[1]))
    print(f"attrs: {stats['measured']} measured, {len(stats['skipped'])} skipped, {n} media rows touched -> {a.attrs}; "
          f"{grounds}; {len(mapping)} assets in yaml, "
          f"{100 * taxonomy.resolved_share(mapping):.0f} % resolve to a family from what is answered so far")
    for page, slot, reason in stats["skipped"][:20]:
        print(f"  skipped {page} {slot}: {reason}")
    print(f"next: lp-corpus sheets  ({len(sheets.pending(mapping))} assets need the semantic fields)")
    return 0


def cmd_frames(a):
    import tempfile
    from . import motion
    src = a.video if a.video.startswith(("http://", "https://")) else Path(a.video).resolve()
    if isinstance(src, Path) and not src.exists():
        log(f"frames: {src} not found")
        return 1
    with tempfile.TemporaryDirectory() as tmp:
        frames_dir = a.out.parent if a.keep_frames else Path(tmp)
        with similar.FrameGrabber() as g:
            duration, paths = motion.probe(src, g, frames_dir, a.out.stem)
        fields = motion.measure(paths)
        motion.strip(paths, a.out)
    print(f"{a.out}: {f'{duration:.2f}' if duration else '?'} s; "
          + " ".join(f"{k}={v}" for k, v in fields.items()))
    return 0


def cmd_motion(a):
    from . import motion
    mapping = attrs.load(a.attrs)
    if a.summary or a.write_doc:
        summ = motion.summary(mapping)
        for fam, s in summ.items():
            print(f"  {fam:20} {motion.motion_line(fam, s)[len('**Motion:** '):]}")
        if a.write_doc:
            written = motion.write_doc(summ, a.doc)
            print(f"motion: **Motion:** line set for {len(written)} families -> {a.doc}")
        return 0
    con = db.connect(a.db)
    clips = {r["src"]: r["local_path"] for r in con.execute(
        "SELECT DISTINCT src, local_path FROM media WHERE kind = 'video' AND local_path IS NOT NULL")}
    changed, stats = attrs.backfill_motion(mapping, clips, frames_dir=a.frames, limit=a.limit, force=a.force, log=log)
    n = 0
    if changed:
        mapping = attrs.merge_save(changed, a.attrs)
        n = attrs.apply(con, mapping)
    print(f"motion: {stats['measured']}/{stats['todo']} videos measured, {len(stats['skipped'])} skipped, "
          f"{n} media rows touched -> {a.attrs}")
    for src in stats["skipped"][:10]:
        print(f"  skipped {src}")
    return 0


def cmd_sheets(a):
    mapping = attrs.load(a.attrs)
    if not mapping:
        log(f"sheets: {a.attrs} is empty; run `lp-corpus attrs` first")
        return 1
    built, stats = sheets.build(mapping, a.out, per_sheet=a.per_sheet, thumb=a.thumb, columns=a.columns,
                                limit=a.limit, skip_resolved=a.skip_resolved)
    index = sheets.write_index(built, a.out, stats)
    print(f"sheets: {stats['pending']} assets pending in {stats['groups']} groups -> {stats['sheets']} sheets "
          f"({stats['answered']} already answered) in {a.out}; prompt in {index}")
    return 0


def cmd_labels(a):
    if a.prompt:
        print(sheets.prompt())
        return 0
    con = db.connect(a.db)
    mapping = attrs.load(a.attrs)
    mapping, stats = label.ingest(mapping, a.labels, log=log)
    attrs.save(mapping, a.attrs)
    n = attrs.apply(con, mapping)
    cov = label.coverage(mapping)
    print(f"labels: {stats['answered']}/{stats['sheets']} sheets answered, {stats['cells']} cells merged, "
          f"{stats['migrated']} files/records migrated, {n} media rows touched -> {a.attrs}")
    done = round(cov["complete"] * len(mapping))
    print(f"  {done}/{len(mapping)} records complete, "
          f"{100 * taxonomy.resolved_share(mapping):.0f} % resolve to a family")
    for err in stats["errors"][:20]:
        print(f"  {err}")
    return 1 if stats["errors"] else 0


def cmd_feedback(a):
    from . import feedback
    suspects, queue = feedback.from_run(a.run, a.attrs)
    print(f"feedback: {len(suspects)} data-suspect original(s) from {a.run} queued; "
          f"{len(queue)} in the re-label queue -> {feedback.QUEUE_PATH}")
    return 0


def cmd_organise(a):
    con = db.connect(a.db)
    attrs_mapping = attrs.load(a.attrs)
    styles_mapping = styles.load(a.styles)
    hashes = {src: (e or {}).get("phash") for src, e in
              (styles.load_yaml((pool.POOL_DIR / "_hashes.yaml").read_text()) or {}).items()} \
        if (pool.POOL_DIR / "_hashes.yaml").exists() else {}
    c = library.organise(a.root, con, attrs_mapping, styles_mapping, hashes,
                         a.pages_dir, PAGES_YAML, a.frames, dry_run=a.dry_run, log=log)
    verb = "would organise" if a.dry_run else "organised"
    extra = f", {c['copied']} copied not linked" if c.get("copied") else ""
    print(f"library ({verb}): {c['images']} images, {c['videos']} videos, {c['screenshots']} screenshots, "
          f"{c['pages']} pages (+{c['shells']} app shells) -> {a.root}; "
          f"{c['missing']} missing files, {c['no_poster']} videos without poster, "
          f"{c['no_art']} images without art_style{extra}")
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
    log("styles: give --from-attrs (derive from the attributes) or --apply-only (mirror the yaml)")
    return 2


if __name__ == "__main__":
    sys.exit(main())
