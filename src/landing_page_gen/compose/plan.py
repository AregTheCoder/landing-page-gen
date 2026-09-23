"""The composition plan — the machine-readable contract for what a composite
draws, and the geometry a worker needs before it generates.

`keep_clear` is the load-bearing piece: for a preset, it reports the region of
each panel that chrome drawn over it would hide (not chrome under the panel,
not chrome that frames the subject), so the brief can tell the worker
"put no subject here" and the panel-node gate can enforce it. It is computed by
rendering the preset once with placeholder panels and reading the drawn rects
`compose()` already returns — no real image, no new geometry. `to_spec` turns a
plan plus panel image paths into a compose spec; `validate` checks a plan is
renderable before anything runs.
"""

import tempfile
from pathlib import Path

import yaml
from PIL import Image

from . import cli, families, kinds

# an overlapping chrome rect only counts as keep-clear when it covers a
# meaningful share of the panel (a hairline pill on the edge is not a no-go zone)
MIN_OVERLAP = 0.02


def _rect_size(family, preset, size):
    tmpl = cli.template(family, preset)
    fw, fh = (tmpl.get("aspects") or (tmpl["aspect"],))[0]
    if size:
        return tmpl, size
    return tmpl, (families.REF, round(families.REF * fh / fw))


def hides_subject(item):
    """Whether a chrome item can cover a panel's subject: only chrome drawn
    ABOVE the panels (a card on the `card` layer sits under the photo), and not
    chrome that frames the subject (brackets, the crop grid, a selection box —
    the subject belongs inside those, so they are not no-subject zones)."""
    kind = kinds.KINDS[item["kind"]]
    layer = item.get("layer") or kind.layer
    return kinds.LAYERS[layer] > kinds.LAYERS["panel"] and not kind.frames


def keep_clear(family, preset=None, size=None):
    """{panel name: [{item, rect (output px), frac (of the panel)}]} — the
    chrome drawn over each panel that would hide a subject there (see
    `hides_subject`). Panels with nothing over them are omitted. Rendered with
    placeholder panels; the geometry is the real one."""
    tmpl, (w, h) = _rect_size(family, preset, size)
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        for name in tmpl["panels"]:
            Image.new("RGB", (400, 400), "white").save(d / f"{name}.png")
        spec = {"family": family, "size": f"{w}x{h}",
                "panels": {name: {"image": f"{name}.png"} for name in tmpl["panels"]}}
        if preset:
            spec["preset"] = preset
        (d / "s.yaml").write_text(yaml.safe_dump(spec))
        layout = cli.resolve(cli.load_spec(d / "s.yaml"))
        _, drawn = cli.compose(layout)
    items = {it["id"]: it for it in layout["chrome"]}
    out = {}
    for name, p in layout["panels"].items():
        px0, py0, px1, py1 = (v / cli.SS for v in p["rect"])
        pw, ph = px1 - px0, py1 - py0
        regions = []
        for cid, (cx0, cy0, cx1, cy1) in drawn.items():
            if not hides_subject(items[cid]):
                continue
            ix0, iy0, ix1, iy1 = max(px0, cx0), max(py0, cy0), min(px1, cx1), min(py1, cy1)
            if ix1 > ix0 and iy1 > iy0 and (ix1 - ix0) * (iy1 - iy0) > MIN_OVERLAP * pw * ph:
                regions.append({"item": cid,
                                "rect": [round(ix0), round(iy0), round(ix1), round(iy1)],
                                "frac": [round((ix0 - px0) / pw, 3), round((iy0 - py0) / ph, 3),
                                         round((ix1 - px0) / pw, 3), round((iy1 - py0) / ph, 3)]})
        if regions:
            out[name] = regions
    return out


def contract(family, preset=None, size=None):
    """The worker's panel contract for a preset: each panel with the ratio to
    generate it at, its fit, whether it is optional, and the keep-clear regions
    an overlay covers it with. What the brief hands the worker so it stops
    guessing '1 panel'."""
    tmpl, (w, h) = _rect_size(family, preset, size)
    kc = keep_clear(family, preset, (w, h))
    out = []
    for name, p in tmpl["panels"].items():
        if p["rect"] is None:
            ratio = families.nearest_ratio(w, h)  # fills the slot
        else:
            x0, y0, x1, y1 = p["rect"]
            ratio = families.nearest_ratio(x1 - x0, y1 - y0)
        out.append({"panel": name, "ratio": ratio, "fit": p.get("fit", "cover"),
                    "keep_clear": kc.get(name, [])})
    return out


def apply_labels(items, family, preset, labels):
    """Write the manager's `> chrome:` strings into the fields each slot of
    `families.LABELS` fills, in order. Copies what it changes, so the family
    template is never touched."""
    by_id = {it["id"]: it for it in items}
    for i, (_, targets) in enumerate(families.LABELS.get((family, preset), [])[:len(labels)]):
        for target in targets:
            cid, field, *n = target.split(".")
            it = by_id[cid]
            if field == "colours":
                it["colours"] = list(labels[i:])
            elif field == "sliders":
                it["sliders"] = [list(s) for s in it["sliders"]]
                it["sliders"][int(n[0])][0] = labels[i]
            else:
                it[field] = labels[i]


def build(family, size, *, preset=None, ground=None, slot=None, derived_from=None, labels=None, section=None):
    """Assemble a composition plan: the panels (ratios + keep-clear) the worker
    generates and the chrome items the preset draws, carrying the manager's
    `labels` (the skeleton's `> chrome:` strings), tagged with what it was
    derived from (so a later edit to the skeleton can be caught as stale). The
    manager may hand-edit the result; `to_spec` turns it into a compose spec."""
    # the panel ratios and keep-clear fractions do not depend on the render
    # size, so use the family's own frame; `size` is recorded for the compose step
    # and, when no preset is asked for, picks the variant whose aspect it has
    preset = cli.preset_for_size(family, size, preset, section)
    plan = {"slot": slot, "family": family, "size": size,
            "panels": contract(family, preset),
            "items": [dict(it) for it in cli.template(family, preset)["chrome"]]}
    for key, val in (("preset", preset), ("ground", ground), ("labels", labels), ("derived_from", derived_from)):
        if val:
            plan[key] = val
    if labels:
        apply_labels(plan["items"], family, preset, labels)
    if ground and not cli.ground_renderable(ground):
        # a corpus variant with no colour to draw (colour, mixed, gradient, checker):
        # keep it on record and let lp-compose draw the family ground — the family
        # docs brief these as the default. The manager may set `ground: {fill: [r, g, b]}`.
        plan["ground_variant"] = plan.pop("ground")
    return plan


def write_plan(path, plan):
    """Write a composition plan to YAML, item/panel order preserved."""
    Path(path).write_text(yaml.safe_dump(plan, sort_keys=False, allow_unicode=True))


def validate(plan):
    """Problems that would stop a plan from rendering; empty when it is sound."""
    problems = []
    fam = plan.get("family")
    if fam not in families.FAMILIES:
        problems.append(f"family {fam!r} is not a compose family")
        return problems
    preset = plan.get("preset")
    if preset and preset not in (families.FAMILIES[fam].get("variants") or {}):
        problems.append(f"{fam} has no preset {preset!r}")
    elif plan.get("size"):
        # the aspect check lp-compose makes at render, made before the panels are paid for
        size = plan["size"]
        w, h = cli.parse_size(size) if isinstance(size, str) else size
        tmpl = cli.template(fam, preset)
        if not cli.fits(tmpl, w, h):
            aspects = " or ".join(f"{a}:{b}" for a, b in tmpl.get("aspects") or (tmpl["aspect"],))
            fitting = [v or "the default" for v in (None, *(families.FAMILIES[fam].get("variants") or {}))
                       if cli.fits(cli.template(fam, v), w, h)]
            problems.append(f"size {w}x{h} is not {aspects} like {fam}" + (f" preset {preset!r}" if preset else "")
                            + (f": {' or '.join(fitting)} fits it" if fitting else f": no {fam} layout fits it"))
    labels = plan.get("labels") or []
    if labels and (not preset or preset in (families.FAMILIES[fam].get("variants") or {})):
        slots = families.LABELS.get((fam, preset), [])
        name = fam + (f" preset {preset!r}" if preset else "")
        if not slots:
            problems.append(f"{name} draws no page strings: its `> chrome:` line must be none")
        elif len(labels) > len(slots) and not any(t.endswith(".colours") for t in slots[-1][1]):
            problems.append(f"{name} draws {len(slots)} page string(s) ({', '.join(n for n, _ in slots)}); "
                            f"`> chrome:` gives {len(labels)}")
    if not cli.ground_renderable(plan.get("ground")):
        problems.append(f"ground {plan['ground']!r} cannot be drawn: use black, white, light, transparent, "
                        f"tilted or a mapping such as {{fill: [r, g, b]}}")
    seen = set()
    for it in plan.get("items") or []:
        cid, kind = it.get("id"), it.get("kind")
        if not cid or cid in seen:
            problems.append(f"item id {cid!r} missing or repeated")
        seen.add(cid)
        rendered_by = it.get("rendered_by", "compose")
        if rendered_by not in ("compose", "model"):
            problems.append(f"item {cid!r}: rendered_by {rendered_by!r} (compose or model)")
        elif rendered_by == "model":
            # the hybrid exception (kinds.MODEL_KINDS): a model-rendered item must
            # be a hybrid kind, carry a reason, and never a string
            if kind not in kinds.MODEL_KINDS:
                problems.append(f"item {cid!r}: kind {kind!r} cannot be rendered_by: model "
                                f"(compose draws it; only {', '.join(sorted(kinds.MODEL_KINDS))} are hybrid)")
            if not (it.get("reason") or "").strip():
                problems.append(f"item {cid!r}: rendered_by: model needs a reason")
            if it.get("text"):
                problems.append(f"item {cid!r}: a model-rendered item carries no text (strings are never model-rendered)")
        elif kind in kinds.MODEL_KINDS:
            problems.append(f"item {cid!r}: kind {kind!r} is hybrid-only; set rendered_by: model with a reason")
        elif kind and kind not in kinds.KINDS:
            problems.append(f"item {cid!r}: kind {kind!r} is not drawable")
        for c in it.get("colours") or []:  # hex/CSS names are fine; anything else would crash the render
            try:
                kinds.rgb(c)
            except ValueError:
                problems.append(f"item {cid!r}: colour {c!r} is not '#rrggbb', a colour name or an RGB list")
    return problems


def to_spec(plan, images):
    """A compose spec (dict) from a plan and a {panel: image path} map. The
    worker adds only the image paths; every item comes from the plan verbatim,
    except that `rendered_by: model` items are dropped — a worker's generate/edit
    node paints those, lp-compose never draws them (and could not: their kinds
    are not in the registry)."""
    spec = {"slot": plan.get("slot"), "family": plan["family"], "size": plan["size"],
            "panels": {name: {"image": images[name]} for name in images}}
    for key in ("preset", "ground", "items", "omit"):
        val = plan.get(key)
        if val is None:
            continue
        if key == "items":
            spec["chrome"] = [it for it in val if it.get("rendered_by") != "model"]
        else:
            spec[key] = val
    return spec
