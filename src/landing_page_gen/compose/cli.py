"""lp-compose: assemble a composite-card image from a style family template
and the worker's panel PNGs.

    uv run lp-compose compose-S07-m1.yaml --out steps/S07-m1-3-1.png
    uv run lp-compose --describe before-after

The spec names the family, the output size (the slot's natural size), an
optional `variant:` (a device of the family, e.g. `reference-thumbs`) and one
image per panel; geometry and chrome come from `families.py`. Costs nothing,
runs offline."""

import argparse
import sys
from pathlib import Path

import yaml
from PIL import Image

from . import draw, kinds
from .families import FAMILIES, REF, aspect_label, nearest_ratio
from .kinds import CHECKER_CELL, FONT_PX  # noqa: F401  (single source; re-exported for back-compat)

SS = 2  # supersample: Pillow draws shapes without antialiasing


def parse_size(s):
    try:
        w, h = (int(v) for v in str(s).split("x"))
        return w, h
    except ValueError:
        sys.exit(f"lp-compose: size must be WxH, got {s!r}")


def template(fam, variant=None):
    """The family dict, or the family with one of its device variants laid
    over it (a key the variant omits is inherited)."""
    f = FAMILIES[fam]
    if not variant:
        return f
    variants = f.get("variants") or {}
    if variant not in variants:
        sys.exit(f"lp-compose: {fam} has no variant {variant!r}; one of {', '.join(variants) or 'none'}")
    return {**{k: v for k, v in f.items() if k != "variants"}, **variants[variant]}


def load_spec(path):
    path = Path(path)
    if not path.exists():
        sys.exit(f"lp-compose: {path} not found")
    spec = yaml.safe_load(path.read_text()) or {}
    fam = spec.get("family")
    if fam not in FAMILIES:
        sys.exit(f"lp-compose: unknown family {fam!r}; one of {', '.join(FAMILIES)}")
    family = template(fam, spec.get("variant"))
    w, h = parse_size(spec.get("size"))
    aspects = family.get("aspects") or (family["aspect"],)
    if not any(abs((w / h) / (fw / fh) - 1) <= 0.02 for fw, fh in aspects):
        sys.exit(f"lp-compose: size {w}x{h} is not {' or '.join(f'{a}:{b}' for a, b in aspects)} like {fam}")
    panels = spec.get("panels") or {}
    for name in family["panels"]:
        img = (panels.get(name) or {}).get("image")
        if not img:
            sys.exit(f"lp-compose: panel {name!r} has no image")
        if not (path.parent / img).exists():
            sys.exit(f"lp-compose: panel {name!r}: {img} not found")
    spec["_dir"], spec["_size"] = path.parent, (w, h)
    return spec


def resolve(spec):
    """Scale the family to the spec size (supersampled), merge chrome
    overrides by id, drop omitted items."""
    family = template(spec["family"], spec.get("variant"))
    w, h = spec["_size"]
    s = w / REF * SS
    rect = lambda r: tuple(round(v * s) for v in r)  # noqa: E731
    panels = {}
    for name, p in family["panels"].items():
        o = (spec.get("panels") or {}).get(name) or {}
        panels[name] = {"rect": rect(p["rect"]) if p["rect"] else (0, 0, w * SS, h * SS), "fit": o.get("fit", p.get("fit", "cover")),
                        "anchor": o.get("anchor", "center"), "under": p.get("under"), "dim": o.get("dim", p.get("dim")),
                        "image": spec["_dir"] / o["image"]}
    overrides, omit = spec.get("chrome") or {}, set(spec.get("omit") or [])
    chrome = []
    for item in family["chrome"]:
        if item["id"] in omit:
            continue
        it = {**item, **(overrides.get(item["id"]) or {})}
        if "rect" in it:
            it["rect"] = rect(it["rect"])
        chrome.append(it)
    tilt = spec.get("tilt") or (10 if spec.get("ground") == "tilted" else 0)
    return {"size": (w * SS, h * SS), "out": (w, h), "scale": s, "ground": family["ground"],
            "radius": round(family["radius"] * s), "panels": panels, "chrome": chrome, "tilt": tilt}


def _draw_panel(canvas, p, ctx):
    with Image.open(p["image"]) as im:
        draw.panel(canvas, im, p["rect"], ctx.r, p["fit"], p["anchor"], p["under"], round(kinds.CHECKER_CELL * ctx.s))
    if p.get("dim"):
        draw.dim(canvas, p["rect"], ctx.r, p["dim"])


def compose(layout):
    """Render the layout; returns (image at the output size, {chrome id:
    rect in output pixels}). Items and panels draw in layer order (ground <
    card < panel < chrome < overlay), stable within a layer, so the legacy
    card-first / panels / chrome order is reproduced exactly; a `top` item is
    drawn after the tilt on its own canvas and composited over."""
    s, r = layout["scale"], layout["radius"]
    canvas = draw.ground(layout["size"], layout["ground"])
    ctx = kinds.Ctx(s=s, r=r, panels=layout["panels"])
    drawn = {}
    ops = []  # (layer value, (phase, index)) -> a chrome item or a panel
    for i, it in enumerate(layout["chrome"]):
        k = it["kind"]
        if k not in kinds.KINDS:
            sys.exit(f"lp-compose: unknown chrome kind {k!r}; one of {', '.join(kinds.KINDS)}")
        layer = it.get("layer") or kinds.KINDS[k].layer
        ops.append((kinds.LAYERS[layer], ("chrome", i), it, k))
    for i, p in enumerate(layout["panels"].values()):
        ops.append((kinds.LAYERS["panel"], ("panel", i), p, None))
    ops.sort(key=lambda o: (o[0], o[1]))

    def render(op, target):
        _, _, obj, k = op
        if k is None:
            _draw_panel(target, obj, ctx)
        else:
            drawn[obj["id"]] = tuple(v / SS for v in kinds.KINDS[k].draw(target, obj, ctx))

    for op in ops:
        if op[0] < kinds.LAYERS["top"]:
            render(op, canvas)
    out = canvas.resize(layout["out"], Image.LANCZOS)
    if layout.get("tilt"):
        out = draw.tilted_stack(out, layout["tilt"])
    top = [op for op in ops if op[0] >= kinds.LAYERS["top"]]
    if top:
        over = draw.ground(layout["size"], {"fill": None})
        for op in top:
            render(op, over)
        out = out.convert("RGBA")
        out.alpha_composite(over.resize(layout["out"], Image.LANCZOS))
    if layout["ground"].get("fill") is not None or "gradient" in layout["ground"]:
        out = out.convert("RGB")
    return out, drawn


def describe(fam):
    if fam not in FAMILIES:
        sys.exit(f"lp-compose: unknown family {fam!r}; one of {', '.join(FAMILIES)}")
    f = FAMILIES[fam]
    g = f["ground"]
    ground = "transparent" if g.get("fill") is None and "gradient" not in g else ("gradient" if "gradient" in g else f"rgb{g['fill']}")
    aspects = " or ".join(f"{a}:{b}" for a, b in (f.get("aspects") or (f["aspect"],)))
    text_kinds = {k for k, v in kinds.KINDS.items() if v.text}

    def geometry(t, indent="  "):
        out = []
        for name, p in t["panels"].items():
            if p["rect"] is None:
                out.append(f"{indent}panel {name}: fills the slot, generate at the slot's ratio ({aspects}), fit {p.get('fit', 'cover')}")
                continue
            x0, y0, x1, y1 = p["rect"]
            w, h = x1 - x0, y1 - y0
            extra = f", under {p['under']}" if p.get("under") else ""
            out.append(f"{indent}panel {name}: {w}x{h} at ({x0},{y0}), aspect {aspect_label(w, h)}, "
                       f"generate at {nearest_ratio(w, h)}, fit {p.get('fit', 'cover')}{extra}")
        out.append(f"{indent}chrome: " + ", ".join(
            f"{c['id']} ({c['kind']}{', text' if c['kind'] in text_kinds or c.get('label') or c.get('active_text') else ''})"
            for c in t["chrome"]))
        return out

    lines = [f"{fam}: aspect {aspects}, ground {ground}, geometry at {REF} px"] + geometry(f)
    lines.append("  chrome marked text carries a label; omit an item (`omit: [id]`) when the model renders its string")
    if f.get("aspects"):
        lines.append("  `ground: tilted` in the spec stacks the card over a plain one at 10 degrees; `tilt: <deg>` sets the angle")
    for name in f.get("variants") or {}:
        lines.append(f"  variant {name} (`variant: {name}` in the spec; the brief's `> device:`):")
        lines += geometry(template(fam, name), indent="    ")
    return "\n".join(lines)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="lp-compose", description="Compose a style-family card from generated panels.")
    p.add_argument("spec", nargs="?", type=Path, help="compose-<slot>.yaml")
    p.add_argument("--out", type=Path, help="output PNG (required with a spec)")
    p.add_argument("--describe", metavar="FAMILY", help="print a family's panels and the ratio to generate each at")
    a = p.parse_args(argv)
    if a.describe:
        print(describe(a.describe))
        return 0
    if not a.spec or not a.out:
        p.error("a spec and --out are required unless --describe is given")
    spec = load_spec(a.spec)
    out, _ = compose(resolve(spec))
    a.out.parent.mkdir(parents=True, exist_ok=True)
    out.save(a.out)
    print(f"{a.out}: {spec['family']} {out.width}x{out.height}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
