"""Labelling contact sheets: how the semantic attribute fields get filled in
without a vision API.

`lp-corpus sheets` lays every asset that still lacks a field on 12-cell PNG
sheets, grouped by what `measure` already read off the pixels, and writes a
yaml manifest beside each sheet. A labeller — an agent given the sheet with
`Read`, or a person — answers one sheet in `<sheet>.answers.yaml` keyed by
cell number; `lp-corpus labels` merges the answers into attributes.yaml."""

import hashlib
from collections import Counter
from pathlib import Path

import yaml

from . import attrs, measure, styles, taxonomy

LABELS_DIR = Path("corpus/labels")
PER_SHEET = 12
THUMB = 320
COLUMNS = 4
# what a sheet always asks for: the fields no pixel statistic can settle
SEMANTIC = ("chrome", "text_in_image", "ui_mockup", "subject", "art_style", "description",
            "family_hint", "confidence")
# asked only on a composition sheet (the layered-chrome campaign), never on a
# first-pass sheet; kept apart so `fields_for` stays a first-pass question.
COMPOSITION = ("chrome_items",)


def semantic_for(rec):
    """What a labeller answers for this asset: the semantic fields, and for a
    video its motion kind and — when the frames did not settle it — its camera."""
    if rec.get("kind") != "video":
        return list(SEMANTIC)
    return list(SEMANTIC) + [f for f in attrs.VIDEO_SEMANTIC if rec.get(f) is None or f == "motion_kind"]


def fields_for(rec):
    """The fields this asset's cell has to answer: the semantic ones, plus any
    measurable field the pixel pass left empty — and `before_after` whenever a
    divider was found but not centred enough to call it, since that answer
    decides the first rule in the table."""
    out = semantic_for(rec) + [f for f in measure.FIELDS if rec.get(f) is None]
    if rec.get("seam") and not rec.get("before_after") and "before_after" not in out:
        out.append("before_after")
    return out


def pending(mapping, skip_resolved=False, priority=None):
    """[(src, rec)] for every asset with an unanswered field, hardest first:
    a run flagged its family as suspect (`priority`) comes first, then assets the
    measured fields alone cannot place into a family, then the ones that already
    have a fallback answer."""
    priority = priority or set()
    out = [(src, rec) for src, rec in mapping.items()
           if any(rec.get(f) is None for f in semantic_for(rec)) and rec.get("local")]
    if skip_resolved:
        out = [(src, rec) for src, rec in out if taxonomy.family_of(rec)[0] is None]
    out.sort(key=lambda kv: (kv[0] not in priority, taxonomy.family_of(kv[1])[0] is not None, group_key(kv[1]), kv[0]))
    return out


def group_key(rec):
    """(type, ground, layout) with a name for the fields the pixels left open:
    an asset whose ground the file cannot say is a cutout the page grounds.
    Videos sheet apart, by (type, aspect, video): their cells are 3-frame strips."""
    if rec.get("kind") == "video":
        return (str(rec.get("type") or "unknown"), str(rec.get("aspect_class") or "unknown"), "video")
    return tuple(str(rec.get(k) or "unknown") for k in ("type", "ground", "layout"))


def composition_key(rec):
    """(type, chrome-combo) — a composition sheet holds one chrome combo, so a
    labeller places the same shape twelve times over."""
    return (str(rec.get("type") or "unknown"), "+".join(sorted(rec.get("chrome") or [])))


def composition_pending(mapping):
    """[(src, rec)] for the layered-chrome campaign: every asset whose chrome
    bag is answered and non-empty but whose chrome_items are not yet
    human-labelled (a coarse derived one does not count). Ordered most-common
    combo first, so the highest-value sheets come first."""
    out = [(src, rec) for src, rec in mapping.items()
           if rec.get("chrome") and "chrome_items" not in (rec.get("labelled") or []) and rec.get("local")]
    freq = Counter(composition_key(rec) for _, rec in out)
    out.sort(key=lambda kv: (-freq[composition_key(kv[1])], composition_key(kv[1]), kv[0]))
    return out


def strip_for(rec, frames_dir=attrs.FRAMES_DIR):
    """A video's 3-frame strip beside its cached frames, built from them when
    missing; the poster frame when the samples were never grabbed."""
    from . import motion
    frames = motion.frame_paths(frames_dir, attrs.frame_stem(rec))
    if not all(p.exists() for p in frames):
        return rec.get("local")
    out = Path(frames_dir) / f"{attrs.frame_stem(rec)}-strip.png"
    if not out.exists():
        motion.strip(frames, out)
    return str(out)


def sheet_name(key, srcs):
    """Named after its group and the assets on it: a rebuilt sheet of the same
    cells keeps its name, and a sheet of different cells never inherits an
    answers file written for other pictures."""
    digest = hashlib.sha1("\n".join(sorted(srcs)).encode()).hexdigest()[:6]
    return "_".join(k.replace("/", "-").replace(":", "x") for k in key) + f"-{digest}"


def cell(src, rec, composition=False):
    keep = ("page", "slot", "type", "size", "aspect_class", "kind", "n_rows", "n_pages")
    out = {"src": src, "asset": attrs.asset_id(src)}
    out.update({k: rec.get(k) for k in keep})
    out.update({f: rec.get(f) for f in measure.FIELDS if rec.get(f) is not None})
    if rec.get("kind") == "video":
        out.update({f: rec.get(f) for f in attrs.VIDEO_MEASURED if rec.get(f) is not None})
    if composition:  # the kinds are known; the labeller only places them
        out["chrome"] = list(rec.get("chrome") or [])
    return out


def build(mapping, out_dir=LABELS_DIR, per_sheet=PER_SHEET, thumb=THUMB, columns=COLUMNS,
          limit=None, skip_resolved=False, priority=None, composition=False):
    """Write the sheets and their manifests. Returns (sheets, stats). When
    `priority` is None the persistent re-label queue (run feedback) is used, so
    a run's suspect originals are laid out first. When `composition` the sheets
    are the layered-chrome campaign: one sheet per chrome combo (most common
    first), each cell's chrome bag pre-filled, and the only field asked is
    chrome_items — the labeller places the known kinds."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    if composition:
        todo = composition_pending(mapping)
        keyer, group_names = composition_key, ("type", "chrome")
    else:
        from . import feedback
        if priority is None:
            priority = feedback.load_queue()
        todo = pending(mapping, skip_resolved, priority)
        keyer, group_names = group_key, ("type", "ground", "layout")
    groups, order = {}, []
    for src, rec in todo:
        key = keyer(rec)
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
            shown = [(src, {**rec, "local": strip_for(rec)} if rec.get("kind") == "video" else rec) for src, rec in chunk]
            taxonomy.contact_sheet(shown, png, per_cell=per_sheet, thumb=thumb, columns=columns,
                                   caption=lambda n, src, rec: f"#{n + 1} {attrs.asset_id(src)} {rec.get('size') or ''}")
            fields = list(COMPOSITION) if composition else sorted({f for _, rec in chunk for f in fields_for(rec)})
            manifest = {"sheet": name, "group": dict(zip(group_names, key)),
                        "fields": fields, "answers": f"{name}.answers.yaml",
                        "cells": {n + 1: cell(src, rec, composition) for n, (src, rec) in enumerate(chunk)}}
            (out_dir / f"{name}.yaml").write_text(styles.dump_yaml(manifest, sort_keys=False, allow_unicode=True, width=1000))
            sheets.append({"name": name, "png": png, "cells": len(chunk), "group": key, "fields": fields,
                           "answered": (out_dir / f"{name}.answers.yaml").exists()})
    stats = {"pending": len(todo), "groups": len(groups), "sheets": len(sheets),
             "answered": sum(1 for s in sheets if s["answered"])}
    return sheets, stats


def prompt(composition=False):
    """What a labeller is told: the field definitions, the families behind
    family_hint, and the answer format. `composition` swaps in the
    layered-chrome campaign prompt (place a known chrome bag)."""
    if composition:
        return _composition_prompt()
    lines = ["Label one contact sheet of Picsart landing-page assets.",
             "",
             "The sheet is a grid of numbered cells (#1, #2, ...) read left to right, top to bottom;",
             "the manifest yaml beside it lists what is already known about each cell.",
             "Answer only what the manifest's `fields` list asks for, and only from what you can see.",
             "A cell sitting on flat mid-grey is a transparent cutout: the page supplies its ground,",
             "so answer `ground` for what is baked into the picture, not for the grey.",
             "A cell that is three frames side by side is a video (first, middle, last frame): answer",
             "the picture fields for the first frame and `motion_kind`/`camera` for what changes across them.",
             "",
             "Fields:"]
    for name in SEMANTIC + measure.FIELDS + attrs.VIDEO_SEMANTIC:
        values, definition = attrs.FIELDS[name]
        shape = f"list, any of {', '.join(values)}" if name == "chrome" else \
            f"one of {', '.join(values)}" if isinstance(values, tuple) else values
        lines.append(f"- {name} ({shape}): {definition}")
    lines += ["", "Style families, for family_hint only:", styles.guide(),
              "", "Write <sheet>.answers.yaml beside the sheet, one block per cell:", "",
              "```yaml", "1:", "  chrome: [tile, chip]", "  text_in_image: labels-only",
              "  ui_mockup: none", "  subject: product", "  art_style: photo",
              "  description: a product photo beside two tool tiles", "  family_hint: dark-composite",
              "  confidence: 0.8", "```", "",
              "Leave a cell out entirely if the thumbnail is too small to judge; do not guess."]
    return "\n".join(lines)


def _composition_prompt():
    """The layered-chrome campaign prompt: each cell's chrome kinds are already
    known (the manifest's `chrome:` bag), so the labeller only says WHERE each
    element sits and what it shows. The answer format is exactly what
    `label.check` accepts, so a placed sheet ingests cleanly."""
    lines = ["Place the chrome of one contact sheet of Picsart landing-page assets.",
             "",
             "The sheet is a grid of numbered cells (#1, #2, ...) read left to right, top to bottom;",
             "all twelve share the same chrome combo, so you place the same shape each time.",
             "Every cell's manifest already has its `chrome:` bag (the kinds present); you add a",
             "`chrome_items:` list that places each element. A cell that is three frames side by side",
             "is a video (first, middle, last frame): place the chrome on the first (poster) frame.",
             "",
             "For each cell, one entry per element:",
             "- kind: one of the kinds in that cell's `chrome:` bag.",
             "- placement (required): overlay = drawn on a picture; beside = on the ground next to it.",
             f"- anchor (optional): where it sits, one of {', '.join(attrs.CHROME_ANCHORS)}.",
             "- count (optional, default 1): how many identical copies (three tiles = one entry, count 3).",
             "- state (optional): a map, any of {active: <the row/index the page is about>, on: true|false, value: <number>}.",
             "- text (optional, <=40 chars): the exact label the element shows; `|`-join the strings when count>1.",
             f"- tool (optional, tiles and icons): the Picsart tool the glyph shows, one of {', '.join(attrs.CHROME_TOOLS)}.",
             "",
             "The set of kinds you place must equal the cell's `chrome:` bag exactly: every bag kind appears",
             "at least once and you name no other kind, or the whole cell is dropped. Repeats go in `count`,",
             "not extra entries.",
             "",
             f"Chrome kinds: {', '.join(attrs.CHROME_KINDS)}.",
             "",
             "Write <sheet>.answers.yaml beside the sheet, one block per cell:", "",
             "```yaml", "1:", "  chrome_items:",
             "    - {kind: option-list, placement: beside, anchor: left, state: {active: 2}, text: Recraft V4}",
             "    - {kind: tile, placement: beside, anchor: left, count: 2}",
             "    - {kind: chip, placement: overlay, anchor: tr, text: 4K}", "```", "",
             "Leave a cell out entirely if the thumbnail is too small to judge; do not guess."]
    return "\n".join(lines)


def write_index(sheets, out_dir=LABELS_DIR, stats=None, composition=False):
    """README.md: the labelling prompt and stats, what a label subagent reads.
    The per-sheet table (one row per sheet, hundreds of them) goes to its own
    index.md so a subagent is not handed ~45 KB of rows it does not need.
    `composition` renders the chrome-combo table and the campaign prompt."""
    out_dir = Path(out_dir)
    head = [f"# Labelling sheets ({len(sheets)})", ""]
    if stats:
        head += [f"{stats['pending']} assets pending in {stats['groups']} groups; "
                 f"{stats['answered']}/{len(sheets)} sheets answered.", ""]

    cols = ("type", "chrome") if composition else ("type", "ground", "layout")
    table = ["| sheet | cells | " + " | ".join(cols) + " | answered |",
             "| " + " | ".join(["---"] * (3 + len(cols))) + " |"]
    for s in sheets:
        table.append(f"| {s['name']}.png | {s['cells']} | " + " | ".join(s["group"])
                     + f" | {'yes' if s['answered'] else ''} |")
    (out_dir / "index.md").write_text("\n".join([*head, *table, ""]))

    path = out_dir / "README.md"
    path.write_text("\n".join([*head, "The per-sheet table is in `index.md`.", "",
                               "## Prompt", "", prompt(composition), ""]))
    return path
