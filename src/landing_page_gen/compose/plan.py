"""The composition plan — the machine-readable contract for what a composite
draws, and the geometry a worker needs before it generates.

`keep_clear` is the load-bearing piece: for a preset, it reports the region of
each panel that an overlay chrome item covers, so the brief can tell the worker
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


def keep_clear(family, preset=None, size=None):
    """{panel name: [{item, rect (output px), frac (of the panel)}]} — the
    overlay chrome covering each panel. Panels with nothing over them are
    omitted. Rendered with placeholder panels; the geometry is the real one."""
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
    out = {}
    for name, p in layout["panels"].items():
        px0, py0, px1, py1 = (v / cli.SS for v in p["rect"])
        pw, ph = px1 - px0, py1 - py0
        regions = []
        for cid, (cx0, cy0, cx1, cy1) in drawn.items():
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
    seen = set()
    for it in plan.get("items") or []:
        cid, kind = it.get("id"), it.get("kind")
        if not cid or cid in seen:
            problems.append(f"item id {cid!r} missing or repeated")
        seen.add(cid)
        if kind and kind not in kinds.KINDS:
            problems.append(f"item {cid!r}: kind {kind!r} is not drawable")
    return problems


def to_spec(plan, images):
    """A compose spec (dict) from a plan and a {panel: image path} map. The
    worker adds only the image paths; every item comes from the plan verbatim."""
    spec = {"slot": plan.get("slot"), "family": plan["family"], "size": plan["size"],
            "panels": {name: {"image": images[name]} for name in images}}
    for key in ("preset", "ground", "items", "omit"):
        if plan.get(key) is not None:
            spec["chrome" if key == "items" else key] = plan[key]
    return spec
