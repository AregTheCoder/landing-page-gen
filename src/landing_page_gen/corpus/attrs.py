"""Visual attributes of corpus media, one record per distinct asset.

`lp-corpus attrs` measures every generated-role image and every creative
video (as a poster frame) once per CDN src: `measure` reads ground, layout,
panel count and before/after off the pixels and writes them to
corpus/attributes.yaml. The semantic fields (chrome, text, mockup, subject,
finish) are answered afterwards from the labelling sheets (`sheets`,
`labels`), so no vision API is in the loop. `taxonomy.family_of` turns a
finished record into a style family; `apply` mirrors attributes, family and
role fixes into the media table after every re-index."""

import datetime
import json
import multiprocessing
from pathlib import Path

import yaml

from . import db, measure, media, sectionize, styles, taxonomy
from .similar import FrameGrabber

ATTRIBUTES_YAML = Path("corpus/attributes.yaml")
FRAMES_DIR = Path("corpus/frames")
CHECKPOINT = 100
# a local video above this is streamed from the CDN: page.route fulfils a file
# in one piece, and a 188 MB clip takes the browser down with it
MAX_LOCAL_VIDEO = 32 * 1024 * 1024
FRAME_DEADLINE = 25  # seconds per video before Chromium is assumed hung
FRAME_CHUNK = 8      # videos per child process

# field -> (enum values, or a JSON type name; one-line definition the model reads)
FIELDS = {
    "ground": (("black", "white", "light-grey", "solid-colour", "gradient", "photo-full-bleed", "checkerboard", "mixed"),
               "the slot's background behind the panels; photo-full-bleed when one picture fills the whole slot"),
    "layout": (("single", "two-up", "split", "column-main", "grid", "stacked", "overlay"),
               "single = one picture; two-up = two equal panels side by side; split = one panel divided in halves; "
               "column-main = a narrow column of small items beside one main panel; grid = 3+ equal cells; "
               "stacked = panels one above the other; overlay = a card or cutout laid over a picture or ground"),
    "panel_count": ("integer", "number of rounded picture areas (photos, renders, cutouts), 0 to 8; chrome does not count"),
    "chrome": (("tile", "pill", "chip", "brackets", "badge", "button", "prompt-panel", "mockup-card", "model-logo",
                "vs-badge", "play-button", "cursor", "selection-handles", "slider", "arrow", "size-label", "swatch",
                "adjust-panel"),
               "every non-photo element present: tile = black square with a white line icon; pill = rounded label over a "
               "photo; chip = small dark or white label; brackets = white L corners marking a crop; badge = small "
               "coloured square with a check; button = solid rounded call-to-action; prompt-panel = dark card with "
               "prompt text and a Generate button; mockup-card = a fake app, profile, product or template card; "
               "model-logo = a third-party model mark; vs-badge = a round VS mark; play-button = a triangle over a "
               "still; cursor and selection-handles = editor furniture; slider = a labelled track with a knob (an adjustment "
               "control) or a before/after handle; arrow; size-label = a pixel size or format string; swatch = a colour or "
               "gradient sample tile; adjust-panel = a dark rounded tool panel laid over the photo (chip row, sliders, values)"),
    "text_in_image": (("none", "labels-only", "headline", "body"),
                      "none; labels-only = only short labels on chrome; headline = a designed headline or slogan "
                      "inside a picture or card; body = sentences of readable text"),
    "ui_mockup": (("none", "editor-canvas", "app-card", "prompt-ui", "product-card", "browser-window", "phone-frame"),
                  "what product interface, if any, the image imitates: editor-canvas = an image on a canvas with handles, "
                  "grid or cursor; app-card = a social or profile card; prompt-ui = a prompt box with a button; "
                  "product-card = a shop card with price or order button; browser-window; phone-frame"),
    "subject": (("person", "product", "scene", "food", "animal", "abstract", "typography", "illustration", "object", "multiple"),
                "the main photographic subject"),
    "finish": (("photo", "3d", "flat-illustration", "collage", "screenshot", "mixed"),
               "photo = editorial photography; 3d = rendered; flat-illustration; collage = cutouts over shapes and brush "
               "strokes on a flat ground; screenshot = a real product screen; mixed"),
    "before_after": ("boolean", "true when the image shows the same picture twice, before and after an edit"),
    "description": ("string", "one line, at most 20 words, what a designer would call this image"),
    "family_hint": (tuple(db.STYLES) + ("other",), "your best guess at the style family described below, or other"),
    "confidence": ("number", "0 to 1, how sure you are of the family hint"),
}
ENUMS = {k: v[0] for k, v in FIELDS.items() if isinstance(v[0], tuple)}


MEASURED = measure.FIELDS
PROVENANCE = ("source", "labelled", "sheet", "at", "page", "slot", "type", "page_family", "kind", "size",
              "aspect_class", "n_rows", "n_pages", "role", "local", "seam")


def load(path=ATTRIBUTES_YAML):
    return styles.load(path)


def save(mapping, path=ATTRIBUTES_YAML):
    styles.save(mapping, path)


def merge_save(fresh, path=ATTRIBUTES_YAML):
    """Write what this pass produced on top of whatever is on the disk now.
    A measuring pass takes minutes; a labelling merge that lands while it runs
    must not be overwritten by its final save."""
    disk = load(path)
    disk.update(fresh)
    save(disk, path)
    return disk


def keep_answers(new, old):
    """A re-measure replaces the pixel fields and keeps every answered one:
    labelling is the expensive half."""
    if not old:
        return new
    for field in list(FIELDS) + ["labelled", "sheet"]:
        if field in old and field not in new:
            new[field] = old[field]
    if new.get("labelled"):
        new["source"] = "sheet"
    return new


def candidates(con, mapping, roles=db.GENERATED_ROLES, kinds=("image", "video"), types=None, force=False):
    """One record per distinct src (the row with the largest rendered box
    stands for all of them), with how many rows and pages share it. Ordered by
    (type, slug, slot) so --limit always extends the same prefix."""
    marks = lambda seq: ",".join("?" * len(seq))  # noqa: E731
    sql = f"""SELECT m.*, s.type, p.slug, p.family AS page_family FROM media m
              JOIN sections s ON s.id = m.section_id JOIN pages p ON p.id = s.page_id
              WHERE m.role IN ({marks(roles)}) AND m.kind IN ({marks(kinds)})"""
    params = list(roles) + list(kinds)
    if types:
        sql += f" AND s.type IN ({marks(types)})"
        params += list(types)
    by_src = {}
    for r in con.execute(sql, params):
        rec = by_src.get(r["src"])
        if rec is None:
            rec = by_src[r["src"]] = {"src": r["src"], "rows": [], "pages": set(), "types": set()}
        rec["rows"].append(r)
        rec["pages"].add(r["slug"])
        rec["types"].add(r["type"])
    out = []
    for src, rec in by_src.items():
        if not force and src in mapping:
            continue
        best = max(rec["rows"], key=lambda r: (r["width"] or 0) * (r["height"] or 0))
        out.append({
            "src": src, "local_path": best["local_path"], "kind": best["kind"], "role": best["role"], "alt": best["alt"],
            "slot": best["slot_id"], "page": best["slug"], "page_family": best["page_family"], "type": best["type"],
            "width": best["width"], "height": best["height"], "aspect": best["aspect"], "duration": best["duration"],
            "aspect_class": sectionize.aspect_class(best["width"], best["height"]),
            "size": sectionize.size_class(best["width"], best["height"]) or "card",
            "n_rows": len(rec["rows"]), "n_pages": len(rec["pages"]), "types": sorted(rec["types"]),
        })
    out.sort(key=lambda c: (c["type"], c["page"], c["slot"]))
    return out


def asset_id(src):
    """First 8 hex of the CDN uuid: how reports and Examples lines name an asset."""
    stem = Path(src.split("?")[0]).stem
    return stem[:8]


def frame_for(rec, frames_dir, grabber):
    """The poster frame of a video, grabbed once and cached."""
    frames_dir = Path(frames_dir)
    frames_dir.mkdir(parents=True, exist_ok=True)
    local = rec.get("local_path")
    path = Path(local) if local else None
    usable = path is not None and path.exists() and path.stat().st_size <= MAX_LOCAL_VIDEO
    src = path if usable else rec["src"]
    png = frames_dir / f"{Path(local).stem if local else asset_id(rec['src'])}.png"
    if not png.exists():
        if grabber is None:
            raise RuntimeError("frame not cached; run the pass again")
        grabber.grab(src, png, at=1.0)
    return png


def picture(rec, frames_dir=FRAMES_DIR, grabber=None):
    """(path to a still of this asset, that path as a string), or
    (None, reason) when there is nothing to look at: SVG, an undownloadable
    asset, a video with no frame grabber."""
    if rec["kind"] == "video":
        try:
            png = frame_for(rec, frames_dir, grabber)
        except Exception as exc:
            return None, f"frame: {exc}"
        return png, str(png)
    local = rec.get("local_path")
    path = Path(local) if local else None
    if path is None or not path.exists():
        Path(frames_dir).mkdir(parents=True, exist_ok=True)
        path = Path(frames_dir) / media.local_name(rec["src"])
        if not path.exists():
            try:
                media.download(rec["src"], path)
            except Exception as exc:
                return None, f"download: {exc}"
    if path.suffix.lower() == ".svg":
        return None, "svg"
    return path, str(path)


def grab_chunk(videos, frames_dir):
    """Cache a few videos' frames in one browser. Runs in a child process;
    every argument has to stay picklable."""
    with FrameGrabber() as g:
        for rec in videos:
            try:
                frame_for(rec, frames_dir, g)
            except Exception as exc:
                print(f"  frame {rec['page']} {rec['slot']}: {exc!r}", flush=True)


def grab_frames(videos, frames_dir, grabber=None, log=print, deadline=FRAME_DEADLINE, chunk=FRAME_CHUNK):
    """Cache one poster frame per video. Serially, in child processes of a few
    videos each: Playwright is not thread safe, and one clip in a few hundred
    hangs Chromium in a way no in-process timeout can interrupt, so the child
    is given a deadline and killed. Frames are cached, so the videos a killed
    chunk did not reach are simply picked up by the next run. A caller that
    passes its own grabber (a test, a handful of videos) stays in process."""
    if grabber is not None:
        for rec in videos:
            try:
                frame_for(rec, frames_dir, grabber)
            except Exception as exc:
                log(f"  frame {rec['page']} {rec['slot']}: {exc!r}")
        return
    ctx = multiprocessing.get_context("spawn")
    for i in range(0, len(videos), chunk):
        part = videos[i:i + chunk]
        proc = ctx.Process(target=grab_chunk, args=(part, str(frames_dir)))
        proc.start()
        proc.join(deadline * len(part))
        if proc.is_alive():
            proc.terminate()
            proc.join(5)
            log(f"  frames {i + 1}-{i + len(part)}: chromium hung, chunk killed")
        log(f"  frames {min(i + chunk, len(videos))}/{len(videos)}")


def record(rec, data, shown, source="measured"):
    """The yaml value: the measured (or answered) fields plus provenance."""
    out = dict(data)
    out.update({"source": source, "at": datetime.date.today().isoformat(),
                "page": rec["page"], "slot": rec["slot"], "type": rec["type"], "page_family": rec["page_family"],
                "kind": rec["kind"], "size": rec["size"], "aspect_class": rec["aspect_class"],
                "n_rows": rec["n_rows"], "n_pages": rec["n_pages"], "role": rec["role"], "local": shown})
    return out


def estimate(todo):
    return {"candidates": len(todo),
            "by_kind": {k: sum(1 for r in todo if r["kind"] == k) for k in ("image", "video")},
            "by_size": {s: sum(1 for r in todo if r["size"] == s) for s in sectionize.SIZE_CLASSES}}


def run(con, limit=None, force=False, roles=None, kinds=("image", "video"), types=None, no_video=False,
        dry_run=False, log=print, path=ATTRIBUTES_YAML, frames_dir=FRAMES_DIR, grabber=None):
    """Measure every candidate that has no record yet: video poster frames
    first (Playwright is not thread-safe and the frames are cached), then one
    `measure.measure` per asset, checkpointing the yaml every CHECKPOINT
    results. Returns (mapping, stats)."""
    mapping = load(path)
    written = set()  # what to flush: --force re-measures assets already in the yaml
    roles = tuple(roles) if roles else db.GENERATED_ROLES
    if no_video:
        kinds = tuple(k for k in kinds if k != "video")
    todo = candidates(con, mapping, roles, tuple(kinds), types, force)[:limit]
    stats = {"estimate": estimate(todo), "measured": 0, "skipped": [], "grounds": {}}
    if dry_run or not todo:
        return mapping, stats
    videos = [r for r in todo if r["kind"] == "video"]
    if videos:
        grab_frames(videos, frames_dir, grabber, log)
    for i, rec in enumerate(todo, 1):
        path_or_none, shown = picture(rec, frames_dir, None)
        data = None
        if path_or_none is not None:
            try:
                data = measure.measure(path_or_none, rec.get("alt"))
            except Exception as exc:  # one unreadable file must not stop the pass
                shown = f"measure: {exc!r}"
        if data is None:
            stats["skipped"].append((rec["page"], rec["slot"], shown))
        else:
            mapping[rec["src"]] = keep_answers(record(rec, data, shown), mapping.get(rec["src"]))
            written.add(rec["src"])
            stats["measured"] += 1
            g = data.get("ground")
            stats["grounds"][g] = stats["grounds"].get(g, 0) + 1
        if i % CHECKPOINT == 0:
            log(f"  {i}/{len(todo)}")
            mapping = merge_save({k: mapping[k] for k in written}, path)
    mapping = merge_save({k: mapping[k] for k in written}, path)
    return mapping, stats


def apply(con, mapping):
    """Mirror attributes into media.attrs (JSON, with the derived variant),
    the derived family into media.style and role fixes into media.role, for
    every row that shares the src. Returns rows touched."""
    before = con.total_changes
    for src, rec in mapping.items():
        style, variant = taxonomy.family_of(rec)
        fields = {k: rec.get(k) for k in FIELDS if k in rec}
        fields["variant"] = variant
        fields["source"] = rec.get("source")  # measured | sheet: the skeleton's `> attrs:` line shows it
        con.execute("UPDATE media SET attrs = ?, style = ? WHERE src = ?", (json.dumps(fields), style, src))
        role = taxonomy.role_fix(rec)
        if role:
            con.execute("UPDATE media SET role = ? WHERE src = ?", (role, src))
    con.commit()
    return con.total_changes - before
