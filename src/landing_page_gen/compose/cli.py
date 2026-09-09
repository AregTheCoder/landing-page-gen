"""lp-compose: assemble a composite-card image from a style family template
and the worker's panel PNGs.

    uv run lp-compose compose-S07-m1.yaml --out steps/S07-m1-3-1.png
    uv run lp-compose --describe before-after

The spec names the family, the output size (the slot's natural size) and one
image per panel; geometry and chrome come from `families.py`. Costs nothing,
runs offline."""

import argparse
import sys
from pathlib import Path

import yaml
from PIL import Image

from . import draw
from .families import FAMILIES, REF, aspect_label, nearest_ratio

SS = 2  # supersample: Pillow draws shapes without antialiasing
CHECKER_CELL = 100
FONT_PX = {"pill": 52, "button": 56, "label": 110, "brackets": 110, "headline": 96,
           "panel-title": 44, "panel-label": 34, "tool-pill": 64}  # at REF


def parse_size(s):
    try:
        w, h = (int(v) for v in str(s).split("x"))
        return w, h
    except ValueError:
        sys.exit(f"lp-compose: size must be WxH, got {s!r}")


def load_spec(path):
    path = Path(path)
    if not path.exists():
        sys.exit(f"lp-compose: {path} not found")
    spec = yaml.safe_load(path.read_text()) or {}
    fam = spec.get("family")
    if fam not in FAMILIES:
        sys.exit(f"lp-compose: unknown family {fam!r}; one of {', '.join(FAMILIES)}")
    w, h = parse_size(spec.get("size"))
    aspects = FAMILIES[fam].get("aspects") or (FAMILIES[fam]["aspect"],)
    if not any(abs((w / h) / (fw / fh) - 1) <= 0.02 for fw, fh in aspects):
        sys.exit(f"lp-compose: size {w}x{h} is not {' or '.join(f'{a}:{b}' for a, b in aspects)} like {fam}")
    panels = spec.get("panels") or {}
    for name in FAMILIES[fam]["panels"]:
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
    family = FAMILIES[spec["family"]]
    w, h = spec["_size"]
    s = w / REF * SS
    rect = lambda r: tuple(round(v * s) for v in r)  # noqa: E731
    panels = {}
    for name, p in family["panels"].items():
        o = (spec.get("panels") or {}).get(name) or {}
        panels[name] = {"rect": rect(p["rect"]) if p["rect"] else (0, 0, w * SS, h * SS), "fit": o.get("fit", p.get("fit", "cover")),
                        "anchor": o.get("anchor", "center"), "under": p.get("under"), "image": spec["_dir"] / o["image"]}
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


def compose(layout):
    """Render the layout; returns (image at the output size, {chrome id:
    rect in output pixels})."""
    s, r = layout["scale"], layout["radius"]
    canvas = draw.ground(layout["size"], layout["ground"])
    drawn = {}
    for it in layout["chrome"]:
        if it["kind"] == "card":
            drawn[it["id"]] = tuple(v / SS for v in draw.card(canvas, it["rect"], it["fill"], r))
    for p in layout["panels"].values():
        with Image.open(p["image"]) as im:
            draw.panel(canvas, im, p["rect"], r, p["fit"], p["anchor"], p["under"], round(CHECKER_CELL * s))
    for it in layout["chrome"]:
        k = it["kind"]
        if k == "card":
            continue
        if k == "tile":
            fill = tuple(it["fill"]) + (255,) if it.get("fill") else (0, 0, 0, 255)
            box = draw.tile(canvas, it["rect"], it["icon"], r, fill=fill)
        elif k == "pill" and "rect" in it:
            box = draw.pill_in(canvas, it["rect"], it["text"], it["style"], draw.font(FONT_PX["button"] * s))
        elif k == "pill":
            box = draw.pill_at(canvas, layout["panels"][it["at"]]["rect"], it["corner"], it["text"], it["style"],
                               draw.font(FONT_PX["pill"] * s), pad=(round(40 * s), round(22 * s)), inset=round(40 * s))
        elif k == "label":
            box = draw.label(canvas, it["rect"], it["text"], r, draw.font(FONT_PX["label"] * s))
        elif k == "brackets":
            x0, y0, x1, y1 = layout["panels"][it["at"]]["rect"]
            fx0, fy0, fx1, fy1 = it["frac"]
            w, h = x1 - x0, y1 - y0
            box = draw.brackets(canvas, (x0 + w * fx0, y0 + h * fy0, x0 + w * fx1, y0 + h * fy1), it.get("label", ""),
                                draw.font(FONT_PX["brackets"] * s), max(1, round(10 * s)))
        elif k == "badge":
            px0, py0, px1, py1 = layout["panels"][it["at"]]["rect"]
            size, inset = round(90 * s), round(24 * s)
            x0 = px0 + inset if it["corner"][1] == "l" else px1 - inset - size
            y0 = py0 + inset if it["corner"][0] == "t" else py1 - inset - size
            box = draw.badge(canvas, (x0, y0, x0 + size, y0 + size), round(22 * s))
        elif k == "headline":
            box = draw.headline(canvas, it["rect"], it.get("text", ""), FONT_PX["headline"] * s,
                                max(1, round(6 * s)), round(12 * s))
        elif k == "adjust-panel":
            box = draw.adjust_panel(canvas, it["rect"], it.get("title", ""), it.get("chips", 0), it.get("active", 0),
                                    it.get("sliders") or [], draw.font(FONT_PX["panel-title"] * s, 700),
                                    draw.font(FONT_PX["panel-label"] * s), round(36 * s))
        elif k == "tool-pill":
            box = draw.tool_pill(canvas, it["rect"], it.get("text", ""), it.get("icon", "wheel"),
                                 draw.font(FONT_PX["tool-pill"] * s, 700))
        else:
            sys.exit(f"lp-compose: unknown chrome kind {k!r}")
        drawn[it["id"]] = tuple(v / SS for v in box)
    out = canvas.resize(layout["out"], Image.LANCZOS)
    if layout.get("tilt"):
        out = draw.tilted_stack(out, layout["tilt"])
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
    lines = [f"{fam}: aspect {aspects}, ground {ground}, geometry at {REF} px"]
    for name, p in f["panels"].items():
        if p["rect"] is None:
            lines.append(f"  panel {name}: fills the slot, generate at the slot's ratio ({aspects}), fit {p.get('fit', 'cover')}")
            continue
        x0, y0, x1, y1 = p["rect"]
        w, h = x1 - x0, y1 - y0
        extra = f", under {p['under']}" if p.get("under") else ""
        lines.append(f"  panel {name}: {w}x{h} at ({x0},{y0}), aspect {aspect_label(w, h)}, "
                     f"generate at {nearest_ratio(w, h)}, fit {p.get('fit', 'cover')}{extra}")
    text_kinds = {"pill", "label", "headline", "adjust-panel", "tool-pill"}
    lines.append("  chrome: " + ", ".join(
        f"{c['id']} ({c['kind']}{', text' if c['kind'] in text_kinds or c.get('label') else ''})" for c in f["chrome"]))
    lines.append("  chrome marked text carries a label; omit an item (`omit: [id]`) when the model renders its string")
    if f.get("aspects"):
        lines.append("  `ground: tilted` in the spec stacks the card over a plain one at 10 degrees; `tilt: <deg>` sets the angle")
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
