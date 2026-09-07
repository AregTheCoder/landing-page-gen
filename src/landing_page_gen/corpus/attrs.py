"""Visual attributes of corpus media, one record per distinct asset.

`lp-corpus attrs` shows every generated-role image, every creative video (as
a poster frame) and every thumbnail to Claude vision once per CDN src and
stores what it sees (ground, layout, chrome, text, mockup, subject, finish)
in corpus/attributes.yaml. `taxonomy.family_of` turns those attributes into
a style family without another model call; `apply` mirrors attributes,
family and role fixes into the media table after every re-index."""

import datetime
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import yaml

from . import db, media, sectionize, styles, taxonomy
from .similar import FrameGrabber

ATTRIBUTES_YAML = Path("corpus/attributes.yaml")
FRAMES_DIR = Path("corpus/frames")
MODEL = "claude-opus-5"          # composites: chrome and text need the detail
MODEL_TILES = "claude-sonnet-5"  # gallery tiles and thumbnails: 512 px is all there is
PX = {"tile": 512, "card": 768, "panel": 768, "wide": 768}
CHECKPOINT = 25
# rough all-in cost per asset in USD (system prompt cached, ~150 output tokens, low effort)
COST = {"claude-opus-5": 0.014, "claude-sonnet-5": 0.006, "claude-haiku-4-5": 0.004}

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
                "vs-badge", "play-button", "cursor", "selection-handles", "slider", "arrow", "size-label", "swatch"),
               "every non-photo element present: tile = black square with a white line icon; pill = rounded label over a "
               "photo; chip = small dark or white label; brackets = white L corners marking a crop; badge = small "
               "coloured square with a check; button = solid rounded call-to-action; prompt-panel = dark card with "
               "prompt text and a Generate button; mockup-card = a fake app, profile, product or template card; "
               "model-logo = a third-party model mark; vs-badge = a round VS mark; play-button = a triangle over a "
               "still; cursor and selection-handles = editor furniture; slider = a before/after handle; arrow; "
               "size-label = a pixel size or format string; swatch = a colour or gradient sample tile"),
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


def _prop(spec):
    values, _ = spec
    if isinstance(values, tuple):
        return {"type": "string", "enum": list(values)}
    return {"type": values}


SCHEMA = {
    "type": "object",
    "properties": {k: ({"type": "array", "items": _prop(v)} if k == "chrome" else _prop(v)) for k, v in FIELDS.items()},
    "required": list(FIELDS),
    "additionalProperties": False,
}
PROVENANCE = ("model", "px", "at", "page", "slot", "type", "page_family", "kind", "size", "aspect_class",
              "n_rows", "n_pages", "role", "local")


def load(path=ATTRIBUTES_YAML):
    return styles.load(path)


def save(mapping, path=ATTRIBUTES_YAML):
    styles.save(mapping, path)


def system_prompt():
    lines = ["You describe Picsart landing-page images for a design taxonomy. Look only at what is in the picture.",
             "Fields:"]
    for name, (values, definition) in FIELDS.items():
        if name == "chrome":
            lines.append(f"- {name} (list, any of {', '.join(values)}): {definition}")
        elif isinstance(values, tuple):
            lines.append(f"- {name} (one of {', '.join(values)}): {definition}")
        else:
            lines.append(f"- {name} ({values}): {definition}")
    lines += ["", "Style families, for family_hint only:", styles.guide()]
    return "\n".join(lines)


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
            "src": src, "local_path": best["local_path"], "kind": best["kind"], "role": best["role"],
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
    src = Path(local) if local and Path(local).exists() else rec["src"]
    png = frames_dir / f"{Path(local).stem if local else asset_id(rec['src'])}.png"
    if not png.exists():
        if grabber is None:
            raise RuntimeError("no frame grabber")
        grabber.grab(src, png, at=1.0)
    return png


def picture(rec, frames_dir=FRAMES_DIR, grabber=None):
    """(base64 PNG, path shown) for a candidate, or (None, reason) when it
    cannot be looked at: SVG, an undownloadable asset, a video with no grabber."""
    px = PX[rec["size"]]
    if rec["kind"] == "video":
        try:
            png = frame_for(rec, frames_dir, grabber)
        except Exception as exc:
            return None, f"frame: {exc}"
        return styles.encode(png, px), str(png)
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
    try:
        return styles.encode(path, px), str(path)
    except Exception as exc:
        return None, f"decode: {exc}"


def context_line(rec):
    kind = "video, shown as its frame at 1 s" if rec["kind"] == "video" else "image"
    return (f"Context: a {rec['type']} section on a {rec['page_family'] or 'tool'} page; rendered "
            f"{rec['width']}x{rec['height']} px, aspect {rec['aspect_class']}, size class {rec['size']}; {kind}.")


def model_for(rec, model=MODEL, model_tiles=MODEL_TILES):
    return model_tiles if rec["size"] == "tile" else model


def describe(client, png_b64, context, system, model):
    """One asset -> (attributes dict, usage) or (None, usage) on refusal."""
    response = client.messages.create(
        model=model, max_tokens=400,
        system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
        output_config={"effort": "low", "format": {"type": "json_schema", "schema": SCHEMA}},
        messages=[{"role": "user", "content": [
            {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": png_b64}},
            {"type": "text", "text": context + " Fill every field."},
        ]}],
    )
    usage = getattr(response, "usage", None)
    totals = {k: getattr(usage, k, 0) or 0 for k in ("input_tokens", "cache_read_input_tokens", "output_tokens")}
    if response.stop_reason == "refusal":
        return None, totals
    data = json.loads(next(b.text for b in response.content if b.type == "text"))
    data["panel_count"] = max(0, min(8, int(data.get("panel_count") or 0)))
    return data, totals


def record(rec, data, model, shown):
    """The yaml value: the model's fields plus provenance."""
    out = dict(data)
    out.update({"model": model, "px": PX[rec["size"]], "at": datetime.date.today().isoformat(),
                "page": rec["page"], "slot": rec["slot"], "type": rec["type"], "page_family": rec["page_family"],
                "kind": rec["kind"], "size": rec["size"], "aspect_class": rec["aspect_class"],
                "n_rows": rec["n_rows"], "n_pages": rec["n_pages"], "role": rec["role"], "local": shown})
    return out


def estimate(todo, model=MODEL, model_tiles=MODEL_TILES):
    by = {}
    for rec in todo:
        m = model_for(rec, model, model_tiles)
        by[m] = by.get(m, 0) + 1
    return {"candidates": len(todo), "by_model": by,
            "by_kind": {k: sum(1 for r in todo if r["kind"] == k) for k in ("image", "video")},
            "by_size": {s: sum(1 for r in todo if r["size"] == s) for s in sectionize.SIZE_CLASSES},
            "usd": round(sum(COST.get(m, 0.01) * n for m, n in by.items()), 2)}


def run(con, model=MODEL, model_tiles=MODEL_TILES, limit=None, force=False, roles=None, kinds=("image", "video"),
        types=None, workers=8, no_video=False, dry_run=False, log=print, path=ATTRIBUTES_YAML,
        frames_dir=FRAMES_DIR, client=None, grabber=None):
    """Describe every untagged candidate. Frames are grabbed first (Playwright
    is not thread-safe), then the model calls run in a pool with a checkpoint
    every CHECKPOINT results. Returns (mapping, stats)."""
    mapping = load(path)
    roles = tuple(roles) if roles else db.GENERATED_ROLES
    if no_video:
        kinds = tuple(k for k in kinds if k != "video")
    todo = candidates(con, mapping, roles, tuple(kinds), types, force)[:limit]
    stats = {"estimate": estimate(todo, model, model_tiles), "tagged": 0, "skipped": [],
             "usage": {"input_tokens": 0, "cache_read_input_tokens": 0, "output_tokens": 0}}
    if dry_run or not todo:
        return mapping, stats
    videos = [r for r in todo if r["kind"] == "video"]
    if videos:
        own = grabber is None
        g = grabber or FrameGrabber().__enter__()
        try:
            for i, r in enumerate(videos, 1):
                try:
                    frame_for(r, frames_dir, g)
                except Exception as exc:
                    log(f"  frame {r['page']} {r['slot']}: {exc!r}")
                if i % 25 == 0:
                    log(f"  frames {i}/{len(videos)}")
        finally:
            if own:
                g.__exit__(None, None, None)
    if client is None:
        import anthropic
        client = anthropic.Anthropic()
    system = system_prompt()

    def one(rec):
        b64, shown = picture(rec, frames_dir, None)
        if b64 is None:
            return rec, None, shown, None
        try:
            data, usage = describe(client, b64, context_line(rec), system, model_for(rec, model, model_tiles))
            return rec, data, shown, usage
        except Exception as exc:  # one bad request must not stop the pass
            log(f"  {rec['page']} {rec['slot']}: {exc!r}")
            return rec, None, f"error: {exc!r}", None

    with ThreadPoolExecutor(workers) as ex:
        for i, (rec, data, shown, usage) in enumerate(ex.map(one, todo), 1):
            if usage:
                for k in stats["usage"]:
                    stats["usage"][k] += usage.get(k, 0)
            if data is None:
                stats["skipped"].append((rec["page"], rec["slot"], shown))
            else:
                mapping[rec["src"]] = record(rec, data, model_for(rec, model, model_tiles), shown)
                stats["tagged"] += 1
            if i % CHECKPOINT == 0:
                log(f"  {i}/{len(todo)}")
                save(mapping, path)
    save(mapping, path)
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
        con.execute("UPDATE media SET attrs = ?, style = ? WHERE src = ?", (json.dumps(fields), style, src))
        role = taxonomy.role_fix(rec)
        if role:
            con.execute("UPDATE media SET role = ? WHERE src = ?", (role, src))
    con.commit()
    return con.total_changes - before
