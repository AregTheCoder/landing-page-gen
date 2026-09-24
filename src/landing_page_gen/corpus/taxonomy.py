"""From attributes to families. `family_of` is the deterministic rule table
that names a style family (and its ground variant) from one asset's
attributes; `role_fix` corrects a guessed media role from what the model saw;
`write_report` cross-tabs the tagged corpus and lays out contact sheets so a
human can name, split or merge families with counts in hand."""

import json
import re
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


# Non-photographic grounds a designed card can sit on (photo-full-bleed,
# gradient and checkerboard are not "flat cards").
_FLAT = ("black", "white", "light-grey", "solid-colour", "mixed")


def _placed_labelled(rec, kind, placement):
    """True only when chrome_items is present and an entry matches — no fallback
    to bag membership, so a rule gated on this fires only on a real placement."""
    items = rec.get("chrome_items")
    return bool(items) and any(it.get("kind") == kind and it.get("placement") == placement for it in items)


def family_of(rec):
    """(family, variant) for one attribute record; (None, None) when no rule
    fits. Order matters: the most specific signature wins."""
    g = rec.get("ground")
    lay = rec.get("layout")
    ch = set(rec.get("chrome") or [])
    ui = rec.get("ui_mockup") or "none"
    art = rec.get("art_style")
    txt = rec.get("text_in_image") or "none"
    typ = rec.get("type")
    panels = rec.get("panel_count") or 0
    fam = None
    if rec.get("before_after"):
        fam = "before-after"
    elif "adjust-panel" in ch or ("adjust-slider" in ch and lay == "overlay") or (
            typ == "hero" and {"pill", "badge"} <= ch and g == "photo-full-bleed" and panels <= 1):
        fam = "panel-overlay"  # the tool panel over a photo; on heroes the tool badge + label pill stand in for it
    elif "compare-handle" in ch:
        fam = "before-after"  # a before/after divider handle, even when the flag was not measured
    elif ch & {"brackets", "size-label"}:
        fam = "crop-frame"
    elif g == "checkerboard" or ("badge" in ch and art == "photo"):
        fam = "cutout-checkerboard"
    elif "prompt-panel" in ch or ui == "prompt-ui":
        fam = "prompt-card"
    elif ch & {"vs-badge", "model-logo"} and (lay == "two-up" or (
            ch & {"pill", "vs-badge"} and lay in ("split", "stacked", "grid") and typ != "link-grid")):
        # the compare-page cards are two outputs side by side with a model mark and a pill;
        # the measurer often reads them as `split`, not `two-up`, so accept those grounds too
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
    elif (_placed_labelled(rec, "tile", "beside") and g in _FLAT and panels >= 1
          and lay in ("single", "stacked", "two-up", "grid") and txt not in ("headline", "body")):
        # a tool tile beside the photo on a flat card that the layout heuristics missed;
        # gated on a *labelled* beside placement so a bare `tile` in the bag cannot over-fire
        fam = "dark-composite"
    elif g == "photo-full-bleed" and rec.get("aspect_class") == "9:16" and typ in ("gallery", "hero"):
        fam = "cinematic-still"
    elif art == "collage":
        fam = "graphic-collage"
    elif typ == "gallery" and g in ("white", "checkerboard") and panels <= 1 and txt not in ("headline", "body"):
        fam = "outcome-tile"
    elif (txt in ("headline", "body") and g in _FLAT and ui == "none"
          and not ch & {"tile", "model-logo", "play-button", "prompt-panel", "adjust-slider", "compare-handle"}):
        # a designed card carrying a headline on a flat ground, no tool chrome: the
        # template-maker galleries the layout rules leave unresolved (206 assets)
        fam = "template-mockup"
    elif g == "photo-full-bleed" and panels <= 1:
        fam = "full-bleed"
    if fam is None:
        return None, None
    variant = VARIANT_NAME.get(g) if g and g != DEFAULT_GROUND[fam] and fam not in ("full-bleed", "cinematic-still") else None
    return fam, variant


# --- composition: how the chrome is laid out, computed on read ---------------
COMPOSITIONS = ("plain", "beside", "overlaid", "layered")


def _group_key(items):
    c = Counter()
    for it in items:
        c[it["kind"]] += it.get("count", 1)
    return "+".join(f"{k}*{c[k]}" if c[k] > 1 else k for k in sorted(c))


def composition_of(rec):
    """(composition | None, key | None, source) from chrome_items: plain (no
    chrome), beside (all beside the picture), overlaid (all on it), layered
    (both). key canonicalises the kinds by placement, e.g.
    'beside:option-list+tile*2/overlay:chip'. source is 'labelled' when the
    items were answered, 'derived' when only inferred, None when absent."""
    items = rec.get("chrome_items")
    source = ("labelled" if "chrome_items" in (rec.get("labelled") or [])
              else "derived" if items is not None else None)
    if items is None:
        return None, None, source
    if not items:
        return "plain", "plain", source
    beside = [it for it in items if it["placement"] == "beside"]
    overlay = [it for it in items if it["placement"] == "overlay"]
    comp = "layered" if beside and overlay else "overlaid" if overlay else "beside"
    segs = ([f"beside:{_group_key(beside)}"] if beside else []) + ([f"overlay:{_group_key(overlay)}"] if overlay else [])
    return comp, "/".join(segs), source


def device_of(rec):
    """The device a composite demonstrates, derived from chrome_items (total,
    never stored): a model/option picker, reference thumbnails, two outputs, an
    applied mockup, an icon set, or none."""
    items = rec.get("chrome_items") or []
    kinds = {it["kind"] for it in items}
    handle = "compare-handle" in kinds
    for it in items:
        if it["kind"] == "option-list" and it["placement"] == "beside" and (it.get("state") or {}).get("active") is not None:
            return "model-picker"
    panels = rec.get("panel_count") or 0
    if panels >= 3 and any(it["kind"] in ("tile", "chip") and it["placement"] == "beside" for it in items) and not handle:
        return "reference-thumbs"
    if panels == 2 and not handle and "vs-badge" not in kinds:
        return "two-up"
    if "mockup-card" in kinds and (rec.get("ui_mockup") or "none") == "none" and rec.get("art_style") == "photo":
        return "applied-mockup"
    if any(it["kind"] == "tile" and (it.get("count") or 1) >= 4 for it in items) or (
            rec.get("art_style") == "flat-vector" and rec.get("layout") == "grid"):
        return "icon-set"
    return "none"


def role_fix(rec):
    """A corrected role, or None to keep the guess. Mockup-card composites
    stay creative: they are generated assets of their own family."""
    role, art, ui = rec.get("role"), rec.get("art_style"), rec.get("ui_mockup") or "none"
    if role == "creative" and (art == "ui-screenshot" or ui in ("editor-canvas", "browser-window")):
        return "ui-screenshot"
    if role == "ui-screenshot" and art == "photo" and ui == "none":
        return "creative"
    return None


def style_label(style, variant):
    return f"{style}/{variant}" if style and variant else style


# --- structure: the coarse shape of a picture, computed on read ---------------
STRUCTURES = ("single-picture", "before-after", "side-by-side", "grid-set", "column-main",
              "panel-overlay", "card", "cutout-checkerboard", "crop-frame")


def structure_of(rec):
    """(structure | None, source) for one attribute record. Computed on read
    (no stored field): pixel facts (before/after, checkerboard) outrank labelled
    chrome; labelled chrome outranks measured layout. source is 'labelled' when
    chrome was answered (it is on every sheet, so an answered chrome means a
    person saw the picture), else 'measured'."""
    g = rec.get("ground")
    lay = rec.get("layout")
    ch = set(rec.get("chrome") or [])
    ui = rec.get("ui_mockup") or "none"
    panels = rec.get("panel_count") or 0
    source = "labelled" if rec.get("chrome") is not None else "measured"
    if rec.get("before_after"):
        st = "before-after"
    elif g == "checkerboard":
        st = "cutout-checkerboard"
    elif ch & {"brackets", "size-label"}:
        st = "crop-frame"
    elif "adjust-panel" in ch or lay == "overlay":
        st = "panel-overlay"
    elif "vs-badge" in ch:
        st = "side-by-side"
    elif ui != "none" or ch & {"mockup-card", "prompt-panel"}:
        st = "card"
    elif lay == "column-main":
        st = "column-main"
    elif lay in ("two-up", "split") or (lay in ("grid", "stacked") and panels <= 2):
        st = "side-by-side"
    elif lay in ("grid", "stacked"):
        st = "grid-set"
    elif lay == "single" or g == "photo-full-bleed":
        st = "single-picture"
    else:
        return None, None
    return st, source


# --- model: who generated an asset, from where it is placed -------------------
# Thumbnails of these types depict other pages; the DB holds no href, so they
# are never evidence of who made the asset.
CROSS_LINK_TYPES = ("link-grid", "tutorial-grid", "resource-links")
HEADLINE_RE = re.compile(r"\b(?:created|made) with (.+?)(?:\s+AI model)?\s*$", re.I)


def slugify(name):
    """'Flux 2 Max' -> 'flux-2-max'."""
    return re.sub(r"[^a-z0-9]+", "-", (name or "").strip().lower()).strip("-")


def model_slug(slug):
    """The model part of an 'ai-models--<model>' page slug, else None."""
    prefix = "ai-models--"
    return slug[len(prefix):] if slug and slug.startswith(prefix) else None


def model_slugs(con):
    """Every 'ai-models--<model>' page's model slug (the known-models set)."""
    return {model_slug(r["slug"]) for r in con.execute(
        "SELECT slug FROM pages WHERE slug LIKE 'ai-models--%'")}


def display_name(title):
    """A readable model name from a page title, for the sidecar only (the
    folder is always the slug). Cuts the title at its first product-category
    or separator word."""
    if not title:
        return None
    head = re.split(r"\s+(?:AI|—|-|\||:)\s", title, maxsplit=1)[0]
    head = re.sub(r"\s+AI$", "", head).strip()
    return head or title.strip()


def placements(con, roles=db.GENERATED_ROLES):
    """{src: [{slug, family, type, headline, role, kind, slot}, ...]} for every
    generated-role media row, one join over media x sections x pages."""
    out = defaultdict(list)
    q = ("SELECT m.src AS src, m.role AS role, m.kind AS kind, m.slot_id AS slot, "
         "s.type AS type, s.headline AS headline, p.slug AS slug, p.family AS family "
         "FROM media m JOIN sections s ON m.section_id = s.id JOIN pages p ON s.page_id = p.id "
         "WHERE m.role IN (%s)" % ",".join("?" * len(roles)))
    for r in con.execute(q, tuple(roles)):
        out[r["src"]].append({k: r[k] for k in ("slug", "family", "type", "headline", "role", "kind", "slot")})
    return dict(out)


def model_of(asset_placements, known):
    """(model | None, evidence, models) for one asset. `known` = model_slugs(con).
    Evidence order: a 'made with X' headline naming one known model is a strict
    upgrade of the page set; two headlines conflict (general); one own ai-models
    page names the model; two or more are shared (general); a lone compare page
    yields the pair (general, in the sidecar); anything else is general."""
    own = [p for p in asset_placements if p.get("type") not in CROSS_LINK_TYPES]
    heads = sorted({slugify(m.group(1)) for p in own
                    for m in [HEADLINE_RE.search(p.get("headline") or "")] if m
                    and slugify(m.group(1)) in known})
    if len(heads) == 1:
        return heads[0], "headline", []
    if len(heads) >= 2:
        return None, "conflict", heads
    ai = sorted({model_slug(p["slug"]) for p in own if model_slug(p["slug"]) in known})
    if len(ai) == 1:
        return ai[0], "page", []
    if len(ai) >= 2:
        return None, "shared", ai
    slugs = {p["slug"] for p in own}
    if len(slugs) == 1:
        only = next(iter(slugs))
        body = only[len("compare-models--"):] if only.startswith("compare-models--") else None
        if body and "-vs-" in body:
            a, b = body.split("-vs-", 1)
            return None, "compare", [a, b]
    return None, None, []


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
                     f"art_style {r.get('art_style')}; hint {r.get('family_hint')}; {r.get('description', '')}")
    (out_dir / "report.md").write_text("\n".join(lines) + "\n")
    (out_dir / "groups.json").write_text(json.dumps(json_groups, indent=1))
    return out_dir / "report.md", len(grp), len(unresolved)


def resolved_share(mapping):
    if not mapping:
        return 0.0
    return sum(1 for r in mapping.values() if family_of(r)[0]) / len(mapping)


assert set(DEFAULT_GROUND) == set(db.STYLES), "every style has a default ground"
