"""Labelling contact sheets: how the semantic attribute fields get filled in
without a vision API.

`lp-corpus sheets` lays every asset that still lacks a field on 12-cell PNG
sheets, grouped by what `measure` already read off the pixels, and writes a
yaml manifest beside each sheet. A labeller — an agent given the sheet with
`Read`, or a person — answers one sheet in `<sheet>.answers.yaml` keyed by
cell number; `lp-corpus labels` merges the answers into attributes.yaml."""

import hashlib
from pathlib import Path

import yaml

from . import attrs, measure, styles, taxonomy

LABELS_DIR = Path("corpus/labels")
PER_SHEET = 12
THUMB = 320
COLUMNS = 4
# what a sheet always asks for: the fields no pixel statistic can settle
SEMANTIC = ("chrome", "text_in_image", "ui_mockup", "subject", "finish", "description",
            "family_hint", "confidence")


def fields_for(rec):
    """The fields this asset's cell has to answer: the semantic ones, plus any
    measurable field the pixel pass left empty — and `before_after` whenever a
    divider was found but not centred enough to call it, since that answer
    decides the first rule in the table."""
    out = list(SEMANTIC) + [f for f in measure.FIELDS if rec.get(f) is None]
    if rec.get("seam") and not rec.get("before_after") and "before_after" not in out:
        out.append("before_after")
    return out


def pending(mapping, skip_resolved=False):
    """[(src, rec)] for every asset with an unanswered field, hardest first:
    assets the measured fields alone cannot place into a family come before
    the ones that already have a fallback answer."""
    out = [(src, rec) for src, rec in mapping.items()
           if any(rec.get(f) is None for f in SEMANTIC) and rec.get("local")]
    if skip_resolved:
        out = [(src, rec) for src, rec in out if taxonomy.family_of(rec)[0] is None]
    out.sort(key=lambda kv: (taxonomy.family_of(kv[1])[0] is not None, group_key(kv[1]), kv[0]))
    return out


def group_key(rec):
    """(type, ground, layout) with a name for the fields the pixels left open:
    an asset whose ground the file cannot say is a cutout the page grounds."""
    return tuple(str(rec.get(k) or "unknown") for k in ("type", "ground", "layout"))


def sheet_name(key, srcs):
    """Named after its group and the assets on it: a rebuilt sheet of the same
    cells keeps its name, and a sheet of different cells never inherits an
    answers file written for other pictures."""
    digest = hashlib.sha1("\n".join(sorted(srcs)).encode()).hexdigest()[:6]
    return "_".join(k.replace("/", "-").replace(":", "x") for k in key) + f"-{digest}"


def cell(src, rec):
    keep = ("page", "slot", "type", "size", "aspect_class", "kind", "n_rows", "n_pages")
    out = {"src": src, "asset": attrs.asset_id(src)}
    out.update({k: rec.get(k) for k in keep})
    out.update({f: rec.get(f) for f in measure.FIELDS if rec.get(f) is not None})
    return out


def build(mapping, out_dir=LABELS_DIR, per_sheet=PER_SHEET, thumb=THUMB, columns=COLUMNS,
          limit=None, skip_resolved=False):
    """Write the sheets and their manifests. Returns (sheets, stats)."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    todo = pending(mapping, skip_resolved)
    groups, order = {}, []
    for src, rec in todo:
        key = group_key(rec)
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append((src, rec))
    sheets = []
    for key in order:
        items = groups[key]
        for i in range(0, len(items), per_sheet):
            if limit and len(sheets) >= limit:
                break
            chunk = items[i:i + per_sheet]
            name = sheet_name(key, [src for src, _ in chunk])
            png = out_dir / f"{name}.png"
            taxonomy.contact_sheet(chunk, png, per_cell=per_sheet, thumb=thumb, columns=columns,
                                   caption=lambda n, src, rec: f"#{n + 1} {attrs.asset_id(src)} {rec.get('size') or ''}")
            fields = sorted({f for _, rec in chunk for f in fields_for(rec)})
            manifest = {"sheet": name, "group": dict(zip(("type", "ground", "layout"), key)),
                        "fields": fields, "answers": f"{name}.answers.yaml",
                        "cells": {n + 1: cell(src, rec) for n, (src, rec) in enumerate(chunk)}}
            (out_dir / f"{name}.yaml").write_text(yaml.safe_dump(manifest, sort_keys=False, allow_unicode=True, width=1000))
            sheets.append({"name": name, "png": png, "cells": len(chunk), "group": key, "fields": fields,
                           "answered": (out_dir / f"{name}.answers.yaml").exists()})
    stats = {"pending": len(todo), "groups": len(groups), "sheets": len(sheets),
             "answered": sum(1 for s in sheets if s["answered"])}
    return sheets, stats


def prompt():
    """What a labeller is told: the field definitions, the families behind
    family_hint, and the answer format."""
    lines = ["Label one contact sheet of Picsart landing-page assets.",
             "",
             "The sheet is a grid of numbered cells (#1, #2, ...) read left to right, top to bottom;",
             "the manifest yaml beside it lists what is already known about each cell.",
             "Answer only what the manifest's `fields` list asks for, and only from what you can see.",
             "A cell sitting on flat mid-grey is a transparent cutout: the page supplies its ground,",
             "so answer `ground` for what is baked into the picture, not for the grey.",
             "",
             "Fields:"]
    for name in SEMANTIC + measure.FIELDS:
        values, definition = attrs.FIELDS[name]
        shape = f"list, any of {', '.join(values)}" if name == "chrome" else \
            f"one of {', '.join(values)}" if isinstance(values, tuple) else values
        lines.append(f"- {name} ({shape}): {definition}")
    lines += ["", "Style families, for family_hint only:", styles.guide(),
              "", "Write <sheet>.answers.yaml beside the sheet, one block per cell:", "",
              "```yaml", "1:", "  chrome: [tile, chip]", "  text_in_image: labels-only",
              "  ui_mockup: none", "  subject: product", "  finish: photo",
              "  description: a product photo beside two tool tiles", "  family_hint: dark-composite",
              "  confidence: 0.8", "```", "",
              "Leave a cell out entirely if the thumbnail is too small to judge; do not guess."]
    return "\n".join(lines)


def write_index(sheets, out_dir=LABELS_DIR, stats=None):
    """README.md: the labelling prompt and one row per sheet."""
    out_dir = Path(out_dir)
    lines = [f"# Labelling sheets ({len(sheets)})", ""]
    if stats:
        lines += [f"{stats['pending']} assets pending in {stats['groups']} groups; "
                  f"{stats['answered']}/{len(sheets)} sheets answered.", ""]
    lines += ["| sheet | cells | type | ground | layout | answered |",
              "| --- | --- | --- | --- | --- | --- |"]
    for s in sheets:
        lines.append(f"| {s['name']}.png | {s['cells']} | " + " | ".join(s["group"])
                     + f" | {'yes' if s['answered'] else ''} |")
    lines += ["", "## Prompt", "", prompt(), ""]
    path = out_dir / "README.md"
    path.write_text("\n".join(lines))
    return path
