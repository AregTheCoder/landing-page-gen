"""lp-corpus doctor: does the corpus conform to the metastructure?

The pipeline (fetch -> sectionize -> media -> attrs -> sheets -> labels ->
styles -> taxonomy -> organise) enforces the format one stage at a time; this
checks the whole estate at once, so a fresh scrape cannot quietly land
half-processed. ERROR findings mean the data is inconsistent and exit non-zero;
WARN findings are reported but expected to occur (unmeasurable assets, assets
still awaiting a label).

Checks:
- every snapshot with a `sections.md` is indexed in the DB, and vice versa;
- every generated-role asset with a readable local file is measured;
- `styles.yaml` is exactly what re-deriving from `attributes.yaml` produces;
- `media.style` mirrors `styles.yaml` (the apply/mirror step was run);
- every stored label value is inside its enum (`attrs.FIELDS` via `label.check`);
- no attributes entry points at a src the DB no longer has;
- every pool entry carries the required fields, a known licence, and its family.
"""

from __future__ import annotations

import json
from collections import namedtuple
from pathlib import Path

from . import attrs, db, label, sheets, stock, styles, taxonomy

Finding = namedtuple("Finding", "level code message")
ERROR, WARN = "ERROR", "WARN"

PAGES_DIR = Path("corpus/pages")
POOL_DIR = Path("corpus/pool")
POOL_REQUIRED = ("url", "image", "creator", "platform", "licence", "phash", "score", "state")
SKIP_SUFFIXES = (".svg",)  # never measured (vector), so never a coverage gap


def _snapshots(con, pages_dir):
    out = []
    db_slugs = {r["slug"] for r in con.execute("SELECT slug FROM pages")}
    disk = {p.name for p in Path(pages_dir).iterdir() if p.is_dir() and (p / "sections.md").exists()} \
        if Path(pages_dir).is_dir() else set()
    for slug in sorted(disk - db_slugs):
        out.append(Finding(ERROR, "snapshot-not-indexed", f"{slug}: has sections.md but no DB page (run sectionize)"))
    for slug in sorted(db_slugs - disk):
        out.append(Finding(WARN, "db-page-no-snapshot", f"{slug}: in the DB with no snapshot on disk"))
    return out


def _measured(con, mapping):
    out = []
    rows = con.execute(
        "SELECT DISTINCT src, local_path FROM media WHERE role IN ('creative','thumbnail')").fetchall()
    unmeasured = []
    for r in rows:
        src, local = r["src"], r["local_path"]
        if src in mapping:
            continue
        if not local or local.lower().endswith(SKIP_SUFFIXES) or not Path(local).exists():
            continue  # vector or already-gone file: not a coverage gap
        unmeasured.append(src)
    if unmeasured:
        out.append(Finding(WARN, "unmeasured", f"{len(unmeasured)} generated asset(s) with a local file are not "
                                               f"measured (run attrs), e.g. {attrs.asset_id(unmeasured[0])}"))
    return out


def _styles_synced(mapping, tags):
    derived = {}
    for src, rec in mapping.items():
        fam, _ = taxonomy.family_of(rec)
        if fam:
            derived[src] = fam
    out = []
    dk, sk = set(derived), set(tags)
    if dk - sk:
        out.append(Finding(ERROR, "styles-missing",
                           f"{len(dk - sk)} asset(s) resolve to a family but are absent from styles.yaml "
                           f"(run styles --from-attrs)"))
    stale = sk - dk
    if stale:
        out.append(Finding(ERROR, "styles-stale",
                           f"{len(stale)} styles.yaml entr(y/ies) no longer derive from attributes "
                           f"(run styles --from-attrs)"))
    disagree = [src for src in dk & sk if (tags[src] or {}).get("style") != derived[src]]
    if disagree:
        out.append(Finding(ERROR, "styles-drift",
                           f"{len(disagree)} family disagreement(s) between styles.yaml and attributes "
                           f"(run styles --from-attrs), e.g. {attrs.asset_id(disagree[0])}"))
    return out


def _db_mirror(con, tags):
    """media.style should equal the derived family for every tagged src."""
    db_style = {}
    for r in con.execute("SELECT src, style FROM media"):
        db_style.setdefault(r["src"], set()).add(r["style"])
    missing = 0
    example = None
    for src, tag in tags.items():
        want = (tag or {}).get("style")
        got = db_style.get(src)
        if got is None:
            continue  # src is not in the DB at all: an orphan, reported separately
        if want and want not in got:
            missing += 1
            example = example or src
    if missing:
        return [Finding(ERROR, "db-mirror-stale",
                       f"{missing} tagged src(s) whose media.style does not match styles.yaml "
                       f"(run styles --from-attrs to re-mirror), e.g. {attrs.asset_id(example)}")]
    return []


def _labels_in_enum(mapping):
    out = []
    bad = 0
    example = None
    for src, rec in mapping.items():
        for field in sheets.SEMANTIC:
            if field in rec and rec[field] is not None:
                _, err = label.check(field, rec[field])
                if err:
                    bad += 1
                    example = example or f"{attrs.asset_id(src)} {err}"
                    break
    if bad:
        out.append(Finding(ERROR, "off-enum-label",
                          f"{bad} asset(s) carry a label outside its enum (never hand-edit attributes.yaml), "
                          f"e.g. {example}"))
    return out


def _chrome_items(mapping):
    """chrome_items must validate, its kinds must equal the plain `chrome` bag,
    and a chrome-answered asset still missing its items is the campaign backlog."""
    out = []
    off_enum = 0
    off_example = None
    drift = 0
    drift_example = None
    pending = 0
    for src, rec in mapping.items():
        items = rec.get("chrome_items")
        if items is not None:
            _, err = label.check("chrome_items", items)
            if err:
                off_enum += 1
                off_example = off_example or f"{attrs.asset_id(src)} {err}"
                continue
            bag = set(rec.get("chrome") or [])
            if {it["kind"] for it in items} != bag:
                drift += 1
                drift_example = drift_example or attrs.asset_id(src)
        elif rec.get("chrome"):  # a non-empty answered bag with no items yet
            pending += 1
    if off_enum:
        out.append(Finding(ERROR, "chrome-items-off-enum",
                           f"{off_enum} asset(s) have a chrome_items entry outside the vocabulary, e.g. {off_example}"))
    if drift:
        out.append(Finding(ERROR, "chrome-bag-drift",
                           f"{drift} asset(s) whose chrome_items kinds != the chrome bag, e.g. {drift_example}"))
    if pending:
        out.append(Finding(WARN, "chrome-items-pending",
                           f"{pending} chrome-answered asset(s) still await a labelled composition (chrome_items)"))
    return out


def _orphans(con, mapping):
    db_srcs = {r["src"] for r in con.execute("SELECT DISTINCT src FROM media")}
    orphans = [src for src in mapping if src not in db_srcs]
    if orphans:
        return [Finding(WARN, "orphan-attributes",
                       f"{len(orphans)} attributes entr(y/ies) point at a src no longer in the DB "
                       f"(a page changed or was dropped)")]
    return []


def _pool(pool_dir):
    out = []
    for path in sorted(Path(pool_dir).glob("*.yaml")):
        if path.name.startswith("_"):
            continue
        data = styles.load_yaml(path.read_text()) or {}
        if data.get("family") != path.stem:
            out.append(Finding(ERROR, "pool-family", f"{path.name}: family {data.get('family')!r} != {path.stem!r}"))
        for eid, e in (data.get("entries") or {}).items():
            missing = [k for k in POOL_REQUIRED if k not in e]
            if missing:
                out.append(Finding(ERROR, "pool-fields", f"{path.name} {eid}: missing {', '.join(missing)}"))
            if e.get("licence") and stock.licence_key(e["licence"]) not in stock.LICENCES:
                out.append(Finding(ERROR, "pool-licence", f"{path.name} {eid}: licence {e['licence']!r} not in vocabulary"))
            if e.get("state") not in ("pending", "kept", "dropped"):
                out.append(Finding(ERROR, "pool-state", f"{path.name} {eid}: state {e.get('state')!r}"))
    return out


DB_PATH = Path("corpus/corpus.db")


def run(db_path=DB_PATH, pages_dir=PAGES_DIR, pool_dir=POOL_DIR,
        attrs_path=attrs.ATTRIBUTES_YAML, styles_path=styles.STYLES_YAML):
    con = db.connect(Path(db_path))
    mapping = attrs.load(attrs_path)
    tags = styles.load(styles_path)
    findings = []
    findings += _snapshots(con, pages_dir)
    findings += _measured(con, mapping)
    findings += _styles_synced(mapping, tags)
    findings += _db_mirror(con, tags)
    findings += _labels_in_enum(mapping)
    findings += _chrome_items(mapping)
    findings += _orphans(con, mapping)
    findings += _pool(pool_dir)
    return findings


def report(findings, log=print):
    errors = [f for f in findings if f.level == ERROR]
    warns = [f for f in findings if f.level == WARN]
    for f in errors:
        log(f"ERROR {f.code}: {f.message}")
    for f in warns:
        log(f"warn  {f.code}: {f.message}")
    if not findings:
        log("doctor: corpus conforms to the metastructure (no findings)")
    else:
        log(f"doctor: {len(errors)} error(s), {len(warns)} warning(s)")
    return 1 if errors else 0
