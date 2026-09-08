"""From attributes to families. `family_of` is the deterministic rule table
that names a style family (and its ground variant) from one asset's
attributes; `role_fix` corrects a guessed media role from what the model saw;
`write_report` cross-tabs the tagged corpus and lays out contact sheets so a
human can name, split or merge families with counts in hand."""

import json
from collections import Counter, defaultdict
from pathlib import Path

from . import db

DEFAULT_GROUND = {
    "dark-composite": "black", "before-after": "black", "crop-frame": "white", "cutout-checkerboard": "black",
    "template-mockup": "white", "prompt-card": "black", "full-bleed": "photo-full-bleed",
    "vs-two-up": "light-grey", "mockup-card": "black", "cinematic-still": "photo-full-bleed",
    "graphic-collage": "solid-colour", "outcome-tile": "white", "editor-canvas": "white", "model-card": "light-grey",
    "panel-overlay": "photo-full-bleed",
}
VARIANT_NAME = {"light-grey": "light", "white": "white", "black": "black", "gradient": "gradient",
                "solid-colour": "colour", "checkerboard": "checker", "mixed": "mixed"}


def family_of(rec):
    """(family, variant) for one attribute record; (None, None) when no rule
    fits. Order matters: the most specific signature wins."""
    g = rec.get("ground")
    lay = rec.get("layout")
    ch = set(rec.get("chrome") or [])
    ui = rec.get("ui_mockup") or "none"
    fin = rec.get("finish")
    txt = rec.get("text_in_image") or "none"
    typ = rec.get("type")
    panels = rec.get("panel_count") or 0
    fam = None
    if rec.get("before_after"):
        fam = "before-after"
    elif "adjust-panel" in ch or ("slider" in ch and lay == "overlay") or (
            typ == "hero" and {"pill", "badge"} <= ch and g == "photo-full-bleed" and panels <= 1):
        fam = "panel-overlay"  # the tool panel over a photo; on heroes the tool badge + label pill stand in for it
    elif ch & {"brackets", "size-label"}:
        fam = "crop-frame"
    elif g == "checkerboard" or ("badge" in ch and fin == "photo"):
        fam = "cutout-checkerboard"
    elif "prompt-panel" in ch or ui == "prompt-ui":
        fam = "prompt-card"
    elif lay == "two-up" and ch & {"vs-badge", "model-logo"}:
        fam = "vs-two-up"
    elif ui in ("app-card", "product-card"):
        fam = "mockup-card"
    elif "mockup-card" in ch and txt in ("headline", "body"):
        fam = "template-mockup"
    elif ui == "editor-canvas":
        fam = "editor-canvas"
    elif typ == "link-grid" and "chip" in ch:
        fam = "model-card"
    elif lay in ("column-main", "split") and ch & {"tile", "chip"} and g in ("black", "light-grey", "white"):
        fam = "dark-composite"
    elif g == "photo-full-bleed" and rec.get("aspect_class") == "9:16" and typ in ("gallery", "hero"):
        fam = "cinematic-still"
    elif fin == "collage":
        fam = "graphic-collage"
    elif typ == "gallery" and g in ("white", "checkerboard") and panels <= 1:
        fam = "outcome-tile"
    elif g == "photo-full-bleed" and panels <= 1:
        fam = "full-bleed"
    if fam is None:
        return None, None
    variant = VARIANT_NAME.get(g) if g and g != DEFAULT_GROUND[fam] and fam not in ("full-bleed", "cinematic-still") else None
    return fam, variant


def role_fix(rec):
    """A corrected role, or None to keep the guess. Mockup-card composites
    stay creative: they are generated assets of their own family."""
    role, fin, ui = rec.get("role"), rec.get("finish"), rec.get("ui_mockup") or "none"
    if role == "creative" and (fin == "screenshot" or ui in ("editor-canvas", "browser-window")):
        return "ui-screenshot"
    if role == "ui-screenshot" and fin == "photo" and ui == "none":
        return "creative"
    return None


def style_label(style, variant):
    return f"{style}/{variant}" if style and variant else style


def key_of(rec, keys):
    vals = []
    for k in keys:
        v = rec.get(k)
        if k == "chrome":
            v = "+".join(sorted(v or [])) or "none"
        vals.append(str(v))
    return tuple(vals)


def groups(mapping, keys):
    """{key tuple: [(src, rec), ...]} over the yaml."""
    out = defaultdict(list)
    for src, rec in mapping.items():
        out[key_of(rec, keys)].append((src, rec))
    return out


def contact_sheet(items, out_png, per_cell=12, thumb=200, columns=6, caption=None):
    """A grid of thumbnails with a caption strip, from each record's `local`.
    caption(i, src, rec) overrides the page/slot line (the labelling sheets
    number their cells)."""
    from PIL import Image, ImageDraw
    from ..compose import draw as cdraw
    items = items[:per_cell]
    cap = 28
    rows = max(1, -(-len(items) // columns))
    sheet = Image.new("RGB", (columns * thumb, rows * (thumb + cap)), "#f4f4f4")
    d = ImageDraw.Draw(sheet)
    font = cdraw.font(13)
    for i, (src, rec) in enumerate(items):
        x, y = (i % columns) * thumb, (i // columns) * (thumb + cap)
        local = rec.get("local")
        try:
            with Image.open(local) as im:
                im = im.convert("RGBA")
                im.thumbnail((thumb - 8, thumb - 8))
                # cutouts are transparent: mid-grey keeps both dark and light art readable
                cell = Image.new("RGBA", im.size, "#808080")
                cell.alpha_composite(im)
                sheet.paste(cell.convert("RGB"), (x + (thumb - im.width) // 2, y + (thumb - im.height) // 2))
        except Exception:
            d.rectangle((x + 4, y + 4, x + thumb - 4, y + thumb - 4), outline="#999")
        text = caption(i, src, rec) if caption else f"{rec.get('page', '') or ''}"[:22] + f" {rec.get('slot', '') or ''}"
        d.text((x + 4, y + thumb + 6), text, fill="#111", font=font)
    sheet.save(out_png)
    return out_png


def write_report(mapping, out_dir, keys=("type", "aspect_class", "ground", "layout"), min_n=5, per_cell=12):
    """report.md (one table per section type, a rules-vs-hint matrix, the
    unresolved list), groups.json and one contact sheet per group with at
    least min_n assets (smaller groups pooled per type in <type>_rest.png)."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    keys = tuple(keys)
    if keys[0] != "type":
        keys = ("type",) + keys
    grp = groups(mapping, keys)
    by_type = defaultdict(list)
    for key, items in grp.items():
        by_type[key[0]].append((key, items))
    lines = [f"# Taxonomy report ({len(mapping)} distinct assets)", "",
             f"Grouping keys: {', '.join(keys)}. Counts are distinct assets / media rows / pages.", ""]
    json_groups = []
    for typ in sorted(by_type, key=lambda t: -sum(len(i) for _, i in by_type[t])):
        cells = sorted(by_type[typ], key=lambda ki: -len(ki[1]))
        total = sum(len(i) for _, i in cells)
        lines += [f"## {typ} ({total} assets)", "",
                  "| " + " | ".join(keys[1:]) + " | assets | rows | pages | % | family (rules) | hints | examples | sheet |",
                  "|" + "---|" * (len(keys) + 8)]
        rest = []
        for key, items in cells:
            n_rows = sum(r.get("n_rows", 1) for _, r in items)
            n_pages = len({r.get("page") for _, r in items})
            fams = Counter(style_label(*family_of(r)) or "unresolved" for _, r in items)
            hints = Counter(r.get("family_hint", "?") for _, r in items)
            examples = ", ".join(f"{r.get('page')} {r.get('slot')}" for _, r in items[:3])
            sheet = ""
            if len(items) >= min_n:
                sheet = "_".join(key).replace("/", "-").replace(":", "x") + ".png"
                contact_sheet(items, out_dir / sheet, per_cell)
            else:
                rest += items
            lines.append("| " + " | ".join(key[1:]) + f" | {len(items)} | {n_rows} | {n_pages} | {100 * len(items) // total} | "
                         + ", ".join(f"{f} {n}" for f, n in fams.most_common(3)) + " | "
                         + ", ".join(f"{f} {n}" for f, n in hints.most_common(3)) + f" | {examples} | {sheet} |")
            json_groups.append({"key": dict(zip(keys, key)), "assets": len(items), "rows": n_rows, "pages": n_pages,
                                "families": dict(fams), "hints": dict(hints), "srcs": [s for s, _ in items]})
        if rest:
            contact_sheet(rest, out_dir / f"{typ}_rest.png", per_cell)
            lines.append(f"\nGroups under {min_n} assets are pooled in `{typ}_rest.png` ({len(rest)} assets).")
        lines.append("")
    # rules vs hints
    matrix = defaultdict(Counter)
    for _, r in mapping.items():
        matrix[style_label(*family_of(r)) or "unresolved"][r.get("family_hint", "?")] += 1
    lines += ["## Rules vs model hint", "", "| family (rules) | assets | agree | top hints |", "|---|---|---|---|"]
    for fam, hints in sorted(matrix.items(), key=lambda kv: -sum(kv[1].values())):
        n = sum(hints.values())
        agree = hints.get(fam.split("/")[0], 0)
        lines.append(f"| {fam} | {n} | {100 * agree // n} % | " + ", ".join(f"{h} {c}" for h, c in hints.most_common(3)) + " |")
    unresolved = [(s, r) for s, r in mapping.items() if family_of(r)[0] is None]
    lines += ["", f"## Unresolved ({len(unresolved)})", ""]
    for s, r in unresolved[:200]:
        lines.append(f"- {r.get('page')} {r.get('slot')} ({r.get('type')}, {r.get('aspect_class')}): ground {r.get('ground')}, "
                     f"layout {r.get('layout')}, chrome {'+'.join(r.get('chrome') or []) or 'none'}, ui {r.get('ui_mockup')}, "
                     f"finish {r.get('finish')}; hint {r.get('family_hint')}; {r.get('description', '')}")
    (out_dir / "report.md").write_text("\n".join(lines) + "\n")
    (out_dir / "groups.json").write_text(json.dumps(json_groups, indent=1))
    return out_dir / "report.md", len(grp), len(unresolved)


def resolved_share(mapping):
    if not mapping:
        return 0.0
    return sum(1 for r in mapping.values() if family_of(r)[0]) / len(mapping)


assert set(DEFAULT_GROUND) == set(db.STYLES), "every style has a default ground"
