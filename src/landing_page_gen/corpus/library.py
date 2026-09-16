"""A browsable, generated view of the corpus. `organise` rebuilds `library/`
from committed sources: a folder per page (its documents + full-page shot), and
every image/video filed by who generated it (general vs a model) -> art style
-> structure, each asset carrying its metadata as a Markdown sidecar. The tree
is hardlinks (zero bytes, dedupes, never dangles); relabel -> regenerate -> an
asset moves folder. Nothing here is hand-edited; it is a projection, gitignored."""

import json
import os
import shutil
from collections import Counter, defaultdict
from pathlib import Path

import yaml

from . import db, media, sectionize, snapshot, styles, taxonomy

LIBRARY_DIR = Path("library")
UNLABELLED = "_unlabelled"
FOLDER = {"image": "Images", "video": "Videos"}
PAGE_FILES = ("page.png", "sections.md", "meta.json", "render.json")
LIBRARY_ROLES = ("creative", "thumbnail", "ui-screenshot")
SHELL_SLUGS = ()  # app-shell slugs with no snapshot are discovered from the DB (screenshot_path IS NULL)


# --- records -----------------------------------------------------------------

def _canonical(grp):
    """The largest rendition of an asset (px area), the one the tree links."""
    return max(grp, key=lambda r: (r["nat_width"] or r["width"] or 0) * (r["nat_height"] or r["height"] or 0))


def assets(con, attrs_mapping, styles_mapping, hashes, frames_dir):
    """One record per distinct asset (renditions merged), each carrying its
    measured and labelled fields, family, art_style, structure, model and
    placements — everything a sidecar and a bucket need."""
    known = taxonomy.model_slugs(con)
    places = taxonomy.placements(con)
    rows = con.execute(
        "SELECT m.section_id, m.slot_id, m.kind, m.role, m.src, m.alt, m.width, m.height, m.aspect, "
        "m.nat_width, m.nat_height, m.duration, m.local_path, m.style, "
        "s.type AS stype, s.sid AS ssid, s.headline AS sheadline, p.slug AS pslug "
        "FROM media m JOIN sections s ON m.section_id = s.id JOIN pages p ON s.page_id = p.id "
        "WHERE m.role IN (%s)" % ",".join("?" * len(LIBRARY_ROLES)), LIBRARY_ROLES).fetchall()
    grouped = defaultdict(list)
    for r in rows:
        grouped[r["src"].split("?")[0]].append(r)

    out = []
    for base, grp in grouped.items():
        row = _canonical(grp)
        srcs = sorted({r["src"] for r in grp})
        src = row["src"]
        key = Path(media.local_name(src)).stem
        attr = next((attrs_mapping[s] for s in [src] + srcs if s in attrs_mapping), {})
        local = row["local_path"]
        exists = bool(local) and Path(local).exists()
        family = None
        variant = None
        if src in styles_mapping or base in styles_mapping:
            tag = styles_mapping.get(src) or styles_mapping.get(base)
            family, variant = tag.get("style"), tag.get("variant")
        else:
            family, variant = taxonomy.family_of(attr)
        structure, structure_source = taxonomy.structure_of(attr)
        aps = [p for s in srcs for p in places.get(s, [])]
        model, evidence, models = taxonomy.model_of(aps, known)
        poster = frames_dir / f"{key}.png" if (frames_dir and (frames_dir / f"{key}.png").exists()) else None

        rec = {
            "key": key, "kind": row["kind"], "role": row["role"], "src": src,
            "ext": Path(local or media.local_name(src)).suffix.lstrip(".") or "bin",
            "file": Path(local).name if local else media.local_name(src),
            "local": local, "missing": not exists,
            "asset_id": key[:8], "phash": hashes.get(src) or hashes.get(base),
            "measured": {
                "ground": attr.get("ground"), "layout": attr.get("layout"),
                "panel_count": attr.get("panel_count"), "before_after": attr.get("before_after"),
                "aspect_class": sectionize.aspect_class(row["nat_width"], row["nat_height"]),
                "size": sectionize.size_class(row["width"], row["height"]),
                "width": row["width"], "height": row["height"],
                "nat_width": row["nat_width"], "nat_height": row["nat_height"],
                "aspect": row["aspect"], "duration": row["duration"],
            },
            "labelled": {k: attr.get(k) for k in
                         ("chrome", "subject", "text_in_image", "ui_mockup", "description", "confidence")} | {
                         "fields": attr.get("labelled"), "sheet": attr.get("sheet"), "at": attr.get("at")},
            "family": family, "variant": variant, "tier": "corpus", "licence": "picsart",
            "art_style": attr.get("art_style"),
            "structure": structure, "structure_source": structure_source,
            "model": model, "model_evidence": evidence, "models": models,
            "placements": sorted(aps, key=lambda p: (p.get("slug") or "", p.get("slot") or "")),
            "poster": f"{key}.png" if poster else None,
        }
        if len(srcs) > 1:
            rec["srcs"] = srcs
        out.append(rec)
    return out


# --- tree paths + sidecars ---------------------------------------------------

def tree_path(rec):
    """The folder (relative to library/) this asset files under."""
    if rec["role"] == "ui-screenshot":
        return Path("Screenshots")
    top = FOLDER.get(rec["kind"], "Images")
    who = f"by-model/{rec['model']}" if rec["model"] else "general"
    return Path(top) / who / (rec["art_style"] or UNLABELLED) / (rec["structure"] or UNLABELLED)


def _paragraph(rec):
    m = rec["measured"]
    bits = []
    size = f"{m['nat_width']}x{m['nat_height']}" if m["nat_width"] else (rec["measured"]["aspect"] or "")
    bits.append(f"A {rec['kind']} ({rec['role']}){f', {size}' if size else ''}{f', class {m['size']}' if m['size'] else ''}.")
    if m["ground"] or m["layout"]:
        bits.append(f"Ground {m['ground'] or '?'}, layout {m['layout'] or '?'}"
                    + (f", {m['panel_count']} panels" if m["panel_count"] is not None else "") + ".")
    if rec["family"]:
        bits.append(f"Family {taxonomy.style_label(rec['family'], rec['variant'])}.")
    if rec["model"]:
        bits.append(f"Made with {rec['model']} ({rec['model_evidence']}).")
    elif rec["model_evidence"]:
        bits.append(f"General ({rec['model_evidence']}).")
    alt = next((p.get("headline") for p in rec["placements"] if p.get("headline")), None)
    if alt:
        bits.append(f'"{alt.strip()}".')
    bits.append(f"Appears on {len({p['slug'] for p in rec['placements']})} page(s).")
    return " ".join(b for b in bits if b)


def sidecar(rec):
    """Markdown: YAML frontmatter (the fields) + a readable paragraph + an
    'Appears on' list. No timestamp, so a rebuild with unchanged inputs is
    byte-identical."""
    front = {"key": rec["key"], "kind": rec["kind"], "role": rec["role"], "asset_id": rec["asset_id"],
             "file": rec["file"]}
    if rec["poster"]:
        front["poster"] = rec["poster"]
    if rec["missing"]:
        front["missing"] = True
    front["src"] = rec["src"]
    if rec.get("srcs"):
        front["srcs"] = rec["srcs"]
    front["phash"] = rec["phash"]
    front["model"] = rec["model"]
    front["model_evidence"] = rec["model_evidence"]
    if rec["models"]:
        front["models"] = rec["models"]
    front["art_style"] = rec["art_style"]
    front["structure"] = rec["structure"]
    front["structure_source"] = rec["structure_source"]
    front["family"] = rec["family"]
    front["variant"] = rec["variant"]
    front["tier"] = rec["tier"]
    front["licence"] = rec["licence"]
    front["measured"] = rec["measured"]
    front["labelled"] = rec["labelled"]
    front["placements"] = [{"page": p["slug"], "slot": p.get("slot"), "section": (p.get("slot") or "").split("-")[0],
                            "type": p.get("type"), "headline": p.get("headline")} for p in rec["placements"]]
    front["library"] = str(tree_path(rec))
    dumped = styles.dump_yaml(front, sort_keys=False, allow_unicode=True, width=1000).rstrip()
    lines = ["---", dumped, "---", "", _paragraph(rec), "", "## Appears on"]
    depth = len(tree_path(rec).parts) + 1  # sidecar sits one level deeper than its folder root
    up = "../" * depth
    for p in rec["placements"]:
        anchor = (p.get("slot") or "").split("-")[0].lower()
        head = f' — "{p["headline"].strip()}"' if p.get("headline") else ""
        lines.append(f"- [{p['slug']} · {p.get('slot')}]({up}Pages/{p['slug']}/page.md#{anchor}){head}")
    return "\n".join(lines) + "\n"


# --- linking -----------------------------------------------------------------

def link(src, dest, stats):
    """Hardlink src -> dest; on a cross-device or permission error, copy and
    count it. dest never pre-exists in the fresh tmp tree."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.link(src, dest)
    except OSError:
        shutil.copy2(src, dest)
        stats["copied"] += 1


# --- page dossiers -----------------------------------------------------------

def _pages_from(pages_yaml):
    """{slug: {from: {slugs}, to: {slugs}}} from corpus/pages.yaml (a list of
    {path, from} entries; `from` is the path a page was discovered through)."""
    data = styles.load_yaml(Path(pages_yaml).read_text()) if Path(pages_yaml).exists() else []
    entries = data if isinstance(data, list) else list((data.get("pages") or data or {}).values())
    rel = defaultdict(lambda: {"from": set(), "to": set()})
    for info in entries:
        if not isinstance(info, dict) or not info.get("path"):
            continue
        slug = snapshot.slug_for(info["path"])
        frm = info.get("from")
        for other in (frm if isinstance(frm, list) else [frm] if frm else []):
            oslug = snapshot.slug_for(other)
            rel[slug]["from"].add(oslug)
            rel[oslug]["to"].add(slug)
    return rel


def page_md(con, slug, recs_by_src, related):
    row = con.execute("SELECT * FROM pages WHERE slug = ?", (slug,)).fetchone()
    secs = con.execute("SELECT * FROM sections WHERE page_id = ? ORDER BY idx", (row["id"],)).fetchall()
    media_rows = con.execute(
        "SELECT m.*, s.sid AS ssid, s.type AS stype FROM media m JOIN sections s ON m.section_id = s.id "
        "WHERE s.page_id = ? ORDER BY s.idx, m.slot_id", (row["id"],)).fetchall()
    front = {"slug": slug, "url": row["url"], "title": row["title"], "family": row["family"],
             "fetched_at": row["fetched_at"], "sections": len(secs), "media": len(media_rows),
             "snapshot": f"corpus/pages/{slug}"}
    lines = ["---", styles.dump_yaml(front, sort_keys=False, allow_unicode=True, width=1000).rstrip(), "---", ""]
    if row["screenshot_path"]:
        lines += ["![full page](page.png)", ""]
    rel = related.get(slug, {})
    if rel.get("from"):
        lines.append("Found via: " + ", ".join(sorted(rel["from"])))
    if rel.get("to"):
        lines.append("Leads to: " + ", ".join(sorted(rel["to"])))
    lines += ["", "## Sections", "", "| sid | type | headline | media |", "|---|---|---|---|"]
    counts = Counter(m["ssid"] for m in media_rows)
    for s in secs:
        lines.append(f'<a id="{s["sid"].lower()}"></a>| {s["sid"]} | {s["type"]} | '
                     f'{(s["headline"] or "").strip()[:60]} | {counts.get(s["sid"], 0)} |')
    lines += ["", "## Assets", "", "| slot | role | kind | model | art_style | structure | family | asset |",
              "|---|---|---|---|---|---|---|---|"]
    for m in media_rows:
        rec = recs_by_src.get(m["src"].split("?")[0])
        if rec is None:  # icon / decorative — kept from source
            lines.append(f"| {m['slot_id']} | {m['role']} | {m['kind']} | — | — | — | — | kept from source |")
            continue
        sidecar_rel = f"../../{tree_path(rec)}/{rec['key']}.md"
        lines.append(f"| {m['slot_id']} | {rec['role']} | {rec['kind']} | {rec['model'] or 'general'} | "
                     f"{rec['art_style'] or '—'} | {rec['structure'] or '—'} | "
                     f"{taxonomy.style_label(rec['family'], rec['variant']) or '—'} | [{rec['key'][:8]}]({sidecar_rel}) |")
    return "\n".join(lines) + "\n"


# --- indexes -----------------------------------------------------------------

def _write_index(folder, title, counts, leaves):
    lines = [f"# {title}", ""]
    if counts:
        lines += ["| child | assets |", "|---|---|"]
        for name, n in sorted(counts.items()):
            lines.append(f"| [{name}]({name}/INDEX.md) | {n} |")
        lines.append("")
    if leaves:
        lines += ["| asset | family | model | pages |", "|---|---|---|---|"]
        for rec in sorted(leaves, key=lambda r: r["key"]):
            lines.append(f"| [{rec['key'][:8]}]({rec['key']}.md) | {rec['family'] or '—'} | "
                         f"{rec['model'] or 'general'} | {len({p['slug'] for p in rec['placements']})} |")
    (folder / "INDEX.md").write_text("\n".join(lines) + "\n")


def indexes(root, placed):
    """An INDEX.md at every folder level: child folders with recursive counts,
    and (at a leaf) the assets themselves."""
    by_folder = defaultdict(list)
    for rec, dest in placed:
        by_folder[dest.parent].append(rec)
    # recursive counts per directory
    subtotal = Counter()
    for folder, recs in by_folder.items():
        node = folder
        while True:
            subtotal[node] += len(recs)
            if node == root:
                break
            node = node.parent
    for folder in sorted({d for d, _ in [(f, None) for f in by_folder] } | set(subtotal), key=lambda p: len(p.parts)):
        children = {c.name: subtotal[c] for c in folder.iterdir() if c.is_dir()} if folder.exists() else {}
        leaves = by_folder.get(folder, [])
        title = str(folder.relative_to(root)) if folder != root else "library"
        _write_index(folder, title, children, leaves)


def root_index(root, recs, pages_n, shells_n):
    imgs = [r for r in recs if r["kind"] == "image" and r["role"] != "ui-screenshot"]
    vids = [r for r in recs if r["kind"] == "video"]
    shots = [r for r in recs if r["role"] == "ui-screenshot"]

    def matrix(items):
        styles = sorted({r["art_style"] or UNLABELLED for r in items})
        structs = sorted({r["structure"] or UNLABELLED for r in items})
        cell = Counter((r["art_style"] or UNLABELLED, r["structure"] or UNLABELLED) for r in items)
        head = "| art_style \\ structure | " + " | ".join(structs) + " |"
        sep = "|" + "---|" * (len(structs) + 1)
        body = [f"| {st} | " + " | ".join(str(cell.get((st, sc), 0)) for sc in structs) + " |" for st in styles]
        return "\n".join([head, sep] + body)

    by_model = Counter(r["model"] for r in recs if r["model"])
    no_art = sum(1 for r in imgs + vids if not r["art_style"])
    missing = sum(1 for r in recs if r["missing"])
    no_poster = sum(1 for r in vids if not r["poster"])
    measured = Counter(r["structure_source"] for r in recs if r["structure"])
    lines = ["# Corpus library", "",
             f"{len(imgs)} images, {len(vids)} videos, {len(shots)} screenshots, "
             f"{pages_n} pages (+{shells_n} app shells).", "",
             "## Images — art_style × structure", "", matrix(imgs), "",
             "## Videos — art_style × structure", "", matrix(vids), "",
             "## By model", "", "| model | assets |", "|---|---|"]
    for m, n in by_model.most_common():
        lines.append(f"| [{m}](Images/by-model/{m}/INDEX.md) | {n} |")
    lines += ["", "## Gaps", "",
              f"- {no_art} without art_style; {missing} missing files; {no_poster} videos without poster",
              f"- structure source: {measured.get('measured', 0)} measured, {measured.get('labelled', 0)} labelled"]
    (root / "INDEX.md").write_text("\n".join(lines) + "\n")


# --- orchestration -----------------------------------------------------------

def _snapshot_dir(pages_dir, slug):
    return Path(pages_dir) / slug


def organise(root, con, attrs_mapping, styles_mapping, hashes, pages_dir, pages_yaml, frames_dir,
             dry_run=False, log=print):
    root = Path(root)
    recs = assets(con, attrs_mapping, styles_mapping, hashes, frames_dir)
    recs_by_src = {r["src"].split("?")[0]: r for r in recs}
    page_rows = con.execute("SELECT slug, screenshot_path FROM pages ORDER BY slug").fetchall()
    dossiers = [r["slug"] for r in page_rows if r["screenshot_path"]]
    shells = [r["slug"] for r in page_rows if not r["screenshot_path"]]
    counts = {"images": sum(1 for r in recs if r["kind"] == "image" and r["role"] != "ui-screenshot"),
              "videos": sum(1 for r in recs if r["kind"] == "video"),
              "screenshots": sum(1 for r in recs if r["role"] == "ui-screenshot"),
              "pages": len(dossiers), "shells": len(shells),
              "missing": sum(1 for r in recs if r["missing"]),
              "no_poster": sum(1 for r in recs if r["kind"] == "video" and not r["poster"]),
              "no_art": sum(1 for r in recs if r["kind"] == "image" and r["role"] != "ui-screenshot" and not r["art_style"])}
    if dry_run:
        return counts

    tmp = root.with_suffix(".tmp")
    if tmp.exists():
        shutil.rmtree(tmp)
    stats = {"copied": 0}
    placed = []
    for rec in recs:
        folder = tmp / tree_path(rec)
        if rec["local"] and not rec["missing"]:
            link(rec["local"], folder / rec["file"], stats)
        if rec["poster"] and (frames_dir / rec["poster"]).exists():
            link(frames_dir / rec["poster"], folder / rec["poster"], stats)
        (folder).mkdir(parents=True, exist_ok=True)
        (folder / f"{rec['key']}.md").write_text(sidecar(rec))
        placed.append((rec, folder / rec["file"]))

    related = _pages_from(pages_yaml)
    for slug in dossiers:
        pdir = tmp / "Pages" / slug
        pdir.mkdir(parents=True, exist_ok=True)
        snap = _snapshot_dir(pages_dir, slug)
        for name in PAGE_FILES:
            srcf = snap / ("screenshot.png" if name == "page.png" else name)
            if srcf.exists():
                link(srcf, pdir / name, stats)
        (pdir / "page.md").write_text(page_md(con, slug, recs_by_src, related))
    (tmp / "Pages").mkdir(parents=True, exist_ok=True)
    (tmp / "Pages" / "INDEX.md").write_text(
        "# Pages\n\n" + "".join(f"- [{s}]({s}/page.md)\n" for s in dossiers)
        + "\n## App shells (no snapshot)\n\n" + "".join(f"- {s}\n" for s in shells))

    indexes(tmp, placed)
    root_index(tmp, recs, len(dossiers), len(shells))

    if root.exists():
        shutil.rmtree(root)
    os.replace(tmp, root)
    counts["copied"] = stats["copied"]
    return counts
