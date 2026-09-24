"""lp-compose: assemble a composite-card image from a style family skeleton,
the worker's panel PNGs and the blocks the worker picked for its slots.

    uv run lp-compose --check-blocks composition-S07-m1.yaml blocks-S07-m1.yaml
    uv run lp-compose --spec-from-plan composition-S07-m1.yaml --blocks blocks-S07-m1.yaml \
        --image photo=steps/S07-m1-2-1.png --out compose-S07-m1.yaml
    uv run lp-compose compose-S07-m1.yaml --out steps/S07-m1-3-1.png
    uv run lp-compose --describe before-after

The spec names the family, the output size (the slot's natural size), an
optional `variant:` (a device of the family, e.g. `reference-thumbs`), one
image per panel and the chrome items to draw; the background and the geometry
come from `families.py`, and every chrome item from a block of the bank
(`bank.resolve`). A spec with no chrome draws the background and the panels
only. Costs nothing, runs offline."""

import argparse
import sys
from pathlib import Path

import yaml
from PIL import Image

from . import degrade, draw, kinds, layout, subject, verify
from .families import FAMILIES, PRESET_BY_SECTION, REF, aspect_label, nearest_ratio
from .kinds import CHECKER_CELL, FONT_PX  # noqa: F401  (single source; re-exported for back-compat)

SS = 2  # supersample: Pillow draws shapes without antialiasing


def parse_size(s):
    try:
        w, h = (int(v) for v in str(s).split("x"))
        return w, h
    except ValueError:
        sys.exit(f"lp-compose: size must be WxH, got {s!r}")


def template(fam, variant=None):
    """The family skeleton, or the family with one of its device variants laid
    over it: a key the variant omits is inherited, except that a variant keeps
    the family's ground but never its surfaces, slots or exemplar."""
    f = FAMILIES[fam]
    if not variant:
        return f
    variants = f.get("variants") or {}
    if variant not in variants:
        sys.exit(f"lp-compose: {fam} has no variant {variant!r}; one of {', '.join(variants) or 'none'}")
    v = variants[variant]
    bg = {"ground": (v.get("background") or {}).get("ground", f["background"]["ground"]),
          "surfaces": (v.get("background") or {}).get("surfaces", [])}
    return {**{k: x for k, x in f.items() if k not in ("variants", "slots", "exemplar")}, **v, "background": bg}


def _preset(spec):
    return spec.get("preset") or spec.get("variant")


def fits(tmpl, w, h):
    """Whether a WxH size has one of the template's aspects (2 % tolerance)."""
    return any(abs((w / h) / (fw / fh) - 1) <= 0.02 for fw, fh in tmpl.get("aspects") or (tmpl["aspect"],))


def preset_for_size(fam, size, preset=None, section=None):
    """The preset to render `fam` at a slot `size` (WxH): the one asked for,
    else the one its section type selects (the panel-overlay hero), else the
    default (None) when its aspect fits, else the first variant whose aspect
    does — a 1:1 before-after slot gets `stacked-square`. The brief's
    `> device:` picks a preset; this only fills in when the device does not."""
    if preset or fam not in FAMILIES:
        return preset
    if (PRESET_BY_SECTION.get(fam) or {}).get(section):
        return PRESET_BY_SECTION[fam][section]
    if not size:
        return None
    w, h = parse_size(size) if isinstance(size, str) else size
    if fits(FAMILIES[fam], w, h):
        return None
    return next((v for v in FAMILIES[fam].get("variants") or {} if fits(template(fam, v), w, h)), None)


_GROUND_WORDS = {"black": (0, 0, 0), "white": (255, 255, 255), "light": (242, 242, 244)}


def ground_renderable(word):
    """Whether a spec `ground:` is one `_ground` can draw. The corpus's other
    ground variants (colour, mixed, gradient, checker) name no colour, so they
    cannot be drawn from the word alone."""
    return word is None or isinstance(word, dict) or word in ("tilted", "transparent", "none") or word in _GROUND_WORDS


def _ground(base, word):
    """The family ground, or a spec override: a colour word (black/white/light),
    transparent/none, a mapping, or `tilted`/None which leaves the ground be."""
    if word in (None, "tilted"):
        return base
    if isinstance(word, dict):
        return word
    if word in ("transparent", "none"):
        return {"fill": None}
    if word in _GROUND_WORDS:
        return {"fill": _GROUND_WORDS[word]}
    sys.exit(f"lp-compose: ground {word!r} is not black/white/light/transparent/tilted or a mapping")


def _chrome_entries(spec):
    """Chrome spec as {id: item}: the list form (each item carries an id) and
    the mapping form (id -> item) unify."""
    ch = spec.get("chrome")
    if not ch:
        return {}
    if isinstance(ch, dict):
        return {k: {"id": k, **(v or {})} for k, v in ch.items()}
    entries = {}
    for e in ch:
        if not isinstance(e, dict) or "id" not in e:
            sys.exit("lp-compose: each chrome list entry needs an id (and a kind to add a new item)")
        entries[e["id"]] = e
    return entries


def _panel_required(o):
    """A family panel may be dropped only when the spec marks it optional and
    gives no image (a preset panel a slot does not need)."""
    return not (o.get("optional") and not o.get("image"))


def load_spec(path):
    path = Path(path)
    if not path.exists():
        sys.exit(f"lp-compose: {path} not found")
    spec = yaml.safe_load(path.read_text()) or {}
    fam = spec.get("family")
    if fam not in FAMILIES:
        sys.exit(f"lp-compose: unknown family {fam!r}; one of {', '.join(FAMILIES)}")
    family = template(fam, _preset(spec))
    w, h = parse_size(spec.get("size"))
    aspects = family.get("aspects") or (family["aspect"],)
    if not fits(family, w, h):
        sys.exit(f"lp-compose: size {w}x{h} is not {' or '.join(f'{a}:{b}' for a, b in aspects)} like {fam}")
    panels = spec.get("panels") or {}
    for name, fp in family["panels"].items():
        if fp.get("detail_of"):  # cropped from another panel at render, never supplied
            continue
        o = panels.get(name) or {}
        if not _panel_required(o):
            continue
        img = o.get("image")
        if not img:
            sys.exit(f"lp-compose: panel {name!r} has no image")
        if not (path.parent / img).exists():
            sys.exit(f"lp-compose: panel {name!r}: {img} not found")
    spec["_dir"], spec["_size"] = path.parent, (w, h)
    return spec


def derive(it, panels):
    """Fill an item's `{from: <panel>}` values from that panel's image, so chrome
    shows the slot's own content: `colours` its palette (`n` cells), `fill` its
    most saturated colour, `image` the image itself. An explicit value (a
    `> chrome:` hex list) is never a mapping, so it always wins."""
    for key in ("colours", "fill", "image"):
        v = it.get(key)
        if not (isinstance(v, dict) and "from" in v):
            continue
        if v["from"] not in panels:
            sys.exit(f"lp-compose: chrome {it['id']!r} takes its {key} from panel {v['from']!r}, which has no image")
        path = panels[v["from"]]["image"]
        if key == "image":
            it[key] = path
            continue
        with Image.open(path) as im:
            cols = draw.palette(im, v.get("n", 3) if key == "colours" else 6)
        it[key] = [list(c) for c in cols] if key == "colours" else \
            list(max(cols, key=lambda c: max(c) - min(c)))


def resolve(spec):
    """Scale the family to the spec size (supersampled): the skeleton's panels
    and background surfaces, and the chrome items the spec carries (the
    resolved blocks); `place:` anchors and `repeat:` expands before scaling."""
    family = template(spec["family"], _preset(spec))
    w, h = spec["_size"]
    s = w / REF * SS
    rect = lambda r: tuple(round(v * s) for v in r)  # noqa: E731
    panels = {}
    for name, p in family["panels"].items():
        o = (spec.get("panels") or {}).get(name) or {}
        crop = None
        if p.get("detail_of"):
            # a detail crop of another panel (the S03 lips of the portrait): the
            # same picture, so no generation and no authorship of its own
            src = (spec.get("panels") or {}).get(p["detail_of"]) or {}
            if not src.get("image"):
                continue
            o, crop = {**src, **o}, o.get("frac", p["frac"])
        elif not _panel_required(o):
            continue
        panels[name] = {"rect": rect(p["rect"]) if p["rect"] else (0, 0, w * SS, h * SS), "fit": o.get("fit", p.get("fit", "cover")),
                        "anchor": o.get("anchor", p.get("anchor", "center")), "under": p.get("under"), "dim": o.get("dim", p.get("dim")),
                        "trim": p.get("trim"), "crop": crop, "image": spec["_dir"] / o["image"],
                        "degrade": _degrade(p.get("degrade"), o.get("degrade")), "radius": p.get("radius"),
                        "seam": p.get("seam")}
    # REF-frame boxes a `place:` can anchor to: the canvas and every family panel
    ref_h = round(REF * h / w)
    boxes = {"canvas": (0, 0, REF, ref_h)}
    for name, p in family["panels"].items():
        boxes[name] = tuple(p["rect"]) if p["rect"] else (0, 0, REF, ref_h)

    def finish(it):
        it = dict(it)
        if "place" in it and "rect" not in it:
            it["rect"] = layout.to_rect(it.pop("place"), boxes)
        out = layout.expand_repeat(it)
        for x in out:
            if "rect" in x:
                x["rect"] = rect(x["rect"])
        return out

    omit = set(spec.get("omit") or [])
    chrome = []
    # the template's background surfaces, then the blocks the spec carries
    for item in [*family["background"]["surfaces"], *_chrome_entries(spec).values()]:
        if item["id"] in omit:
            continue
        if "kind" not in item:
            print(f"lp-compose: chrome {item['id']!r} has no kind; a spec's chrome comes from bank blocks "
                  "(`--spec-from-plan --blocks`)", file=sys.stderr)
            continue
        chrome += finish(item)
    for it in chrome:
        derive(it, panels)
    tilt = spec.get("tilt") or (10 if spec.get("ground") == "tilted" else 0)
    return {"size": (w * SS, h * SS), "out": (w, h), "scale": s,
            "ground": _ground(family["background"]["ground"], spec.get("ground")),
            "radius": round(family["radius"] * s), "panels": panels, "chrome": chrome, "tilt": tilt}


def _degrade(family, spec):
    """A panel's degrade as {mode, until, amount}, or None: the family says
    where (a compare-slider degrades the left half), the spec which fault
    (`degrade: blur`, or a mapping)."""
    if not family and not spec:
        return None
    norm = lambda d: d if isinstance(d, dict) else ({"mode": d} if d else {})  # noqa: E731
    d = {"mode": "blur", "until": 1.0, "amount": 1.0, **norm(family), **norm(spec)}
    if d["mode"] not in degrade.MODES:
        sys.exit(f"lp-compose: degrade {d['mode']!r} is not one of {', '.join(degrade.MODES)}")
    return d


def _subject_anchor(p):
    """`anchor: subject`: the cover-crop anchor that keeps the picture's subject
    (compose/subject.py), printing a `verify:` fault for a face it still cuts."""
    x0, y0, x1, y1 = p["rect"]
    at, found = subject.anchor_for(p["image"], (x1 - x0, y1 - y0))
    if subject.cut(found, subject.crop_box((found["w"], found["h"]), (x1 - x0, y1 - y0), at)):
        print(f"verify: {Path(p['image']).name}: a face is cut by the panel's frame")
    return f"{at[0]:.3f},{at[1]:.3f}"


def _draw_panel(canvas, p, ctx):
    if p["anchor"] == "subject":
        p = {**p, "anchor": _subject_anchor(p) if not (p.get("crop") or p.get("trim")) and p["fit"] == "cover" else "center"}
    with Image.open(p["image"]) as im:
        if p.get("crop"):
            fx0, fy0, fx1, fy1 = p["crop"]
            im = im.crop((round(im.width * fx0), round(im.height * fy0), round(im.width * fx1), round(im.height * fy1)))
        if p.get("trim"):  # a cut-out fitted by its visible pixels, so a frame around the panel hugs it
            im = im.convert("RGBA")
            im = im.crop(im.getchannel("A").getbbox() or (0, 0, *im.size))
        if p.get("degrade"):  # the Before made from the After (compose/degrade.py)
            d = p["degrade"]
            if d["until"] >= 1:
                im = degrade.degrade(im, d["mode"], d["amount"])
            else:  # fitted first, so the seam sits at the panel's `until`, not the source's
                x0, y0, x1, y1 = p["rect"]
                im = degrade.split(draw.fit(im, (x1 - x0, y1 - y0), p["fit"], p["anchor"]), d["mode"], d["until"], d["amount"])
        r = ctx.r if p.get("radius") is None else round(p["radius"] * ctx.s)  # a measured panel's own corner
        if p.get("seam") is None:
            draw.panel(canvas, im, p["rect"], r, p["fit"], p["anchor"], p["under"], round(kinds.CHECKER_CELL * ctx.s))
        else:  # a compare card's After: the same card as its Before, shown right of the divider only
            layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
            draw.panel(layer, im, p["rect"], r, p["fit"], p["anchor"], p["under"], round(kinds.CHECKER_CELL * ctx.s))
            x0, _, x1, _ = p["rect"]
            a = layer.getchannel("A")
            a.paste(0, (0, 0, round(x0 + (x1 - x0) * p["seam"]), canvas.size[1]))
            layer.putalpha(a)
            canvas.alpha_composite(layer)
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
        if draw.missing_glyphs(it):
            sys.exit(f"lp-compose: chrome {it.get('id')!r} sets {draw.missing_glyphs(it)!r}, which the font cannot draw "
                     f"(it would print boxes); write it with characters the font has")
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
            ctx.type = obj.get("type")  # a slot's measured type (induced layouts), else the kind's own sizes
            ctx.r = r if obj.get("radius") is None else round(obj["radius"] * s)  # and its measured corner
            drawn[obj["id"]] = tuple(v / SS for v in kinds.KINDS[k].draw(target, obj, ctx))
            ctx.type, ctx.r = None, r

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


def _ground_word(g):
    return "transparent" if g.get("fill") is None and "gradient" not in g else ("gradient" if "gradient" in g else f"rgb{g['fill']}")


def _slot_line(sl):
    where = f"on {sl['at']}" + (f" {sl['corner']}" if sl.get("corner") else "") if sl.get("at") else \
        f"at {tuple(sl['rect'])}" if sl.get("rect") else ""
    state = f", the {sl['state']} panel" if sl.get("state") else ""
    return (f"slot {sl['id']}: {sl['shape']} {where}, takes {' | '.join(sl['accepts'])}"
            f"{', required' if sl.get('required') else ', optional'}{state}")


def describe(fam):
    """A family's skeleton: background, panels (and the ratio to generate each
    at), slots (shape, categories, required) and what the measured original
    showed in each slot."""
    if fam not in FAMILIES:
        sys.exit(f"lp-compose: unknown family {fam!r}; one of {', '.join(FAMILIES)}")
    f = FAMILIES[fam]
    aspects = " or ".join(f"{a}:{b}" for a, b in (f.get("aspects") or (f["aspect"],)))

    def skeleton(t, indent="  "):
        out = [f"{indent}background: ground {_ground_word(t['background']['ground'])}"
               + "".join(f", surface {s['id']} ({s['kind']})" for s in t["background"]["surfaces"])]
        for name, p in t["panels"].items():
            holds = f", holds a {p.get('holds', 'scene')}"
            if p.get("detail_of"):
                out.append(f"{indent}panel {name}: a crop of {p['detail_of']} (lp-compose, never generated)")
            elif p["rect"] is None:
                out.append(f"{indent}panel {name}: fills the slot, generate at the slot's ratio ({aspects}), "
                           f"fit {p.get('fit', 'cover')}{holds}")
            else:
                x0, y0, x1, y1 = p["rect"]
                w, h = x1 - x0, y1 - y0
                extra = f", under {p['under']}" if p.get("under") else ""
                out.append(f"{indent}panel {name}: {w}x{h} at ({x0},{y0}), aspect {aspect_label(w, h)}, "
                           f"generate at {nearest_ratio(w, h)}, fit {p.get('fit', 'cover')}{extra}{holds}")
        out += [indent + _slot_line(sl) for sl in t["slots"]]
        ex = t.get("exemplar") or {}
        if ex.get("fills"):
            out.append(f"{indent}the original ({ex.get('source')}) showed: "
                       + ", ".join(f"{k} {v['block']}" for k, v in ex["fills"].items()))
        return out

    lines = [f"{fam}: aspect {aspects}, geometry at {REF} px"] + skeleton(f)
    lines.append("  slots are filled only from bank blocks the worker picks (blocks-<slot>.yaml); an empty optional slot draws nothing")
    if f.get("aspects"):
        lines.append("  `ground: tilted` in the spec stacks the card over a plain one at 10 degrees; `tilt: <deg>` sets the angle")
    for name in f.get("variants") or {}:
        lines.append(f"  variant {name} (`variant: {name}` in the spec; the brief's `> device:`):")
        lines += skeleton(template(fam, name), indent="    ")
    return "\n".join(lines)


def check_blocks(plan_path, picks_path):
    """Check a worker's picks against its plan; when they hold, bind every
    attribution pick into made-by.yaml beside the plan (the page's own
    attribution, written by the brief, wins) and print what each slot shows.
    Returns the exit code."""
    from . import plan  # lazy: plan imports cli
    plan_path, picks_path = Path(plan_path), Path(picks_path)
    cp = yaml.safe_load(plan_path.read_text()) or {}
    if not picks_path.exists():
        print(f"lp-compose: {picks_path} not found", file=sys.stderr)
        return 1
    doc = yaml.safe_load(picks_path.read_text()) or {}
    problems = plan.check_blocks(cp, doc)
    made = {} if problems else plan.made_by(cp, doc)
    mb_path = plan_path.parent / "made-by.yaml"
    have = (yaml.safe_load(mb_path.read_text()) or {}) if mb_path.exists() else {}
    slot = cp.get("slot") or "*"
    for panel, req in made.items():
        was = (have.get(slot) or {}).get(panel)
        if req["model"].startswith("no:"):
            problems.append(f"panel {panel}: {req['model'][3:].strip()}")
        elif was and was["model"] != req["model"]:
            problems.append(f"panel {panel}: an attribution pick names {req['model']}, but the page makes it on "
                            f"{was['model']} ({was['because']})")
    if problems:
        print(f"{picks_path.name}: {len(problems)} problem(s)")
        for pr in problems:
            print(f"  - {pr}")
        return 1
    if made:
        have.setdefault(slot, {})
        for panel, req in made.items():
            have[slot].setdefault(panel, req)
        mb_path.write_text(yaml.safe_dump(have, sort_keys=False))
    items = plan.picked_items(cp, doc)
    print(f"{picks_path.name}: ok, {len(items)} block(s)" + (f"; made-by.yaml binds {', '.join(made)}" if made else ""))
    for it in items:
        shows = it.get("tool") or it.get("model") or it.get("text") or it.get("active_text") or it.get("rows") \
            or it.get("title") or it.get("block")
        print(f"  {it['id']}: {it['block']} ({it['category']}) {shows}")
    return 0


def skeleton_image(fam, preset=None, size=None):
    """The layout as a wireframe: the background drawn as it will be, each
    panel a grey card naming what the model makes there, each slot an outline
    naming its shape and the categories it takes (the footprint is its
    exemplar block's). Nothing in it says anything about a page."""
    from . import plan  # lazy
    from PIL import ImageDraw
    tmpl = template(fam, preset)
    fw, fh = (tmpl.get("aspects") or (tmpl["aspect"],))[0]
    w, h = size or (1200, round(1200 * fh / fw))
    kc_spec = {"family": fam, "size": f"{w}x{h}", "chrome": plan.exemplar_items(fam, preset), "panels": {}}
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        for name in tmpl["panels"]:
            Image.new("RGB", (64, 64), "white").save(Path(d) / f"{name}.png")
            kc_spec["panels"][name] = {"image": f"{name}.png"}
        if preset:
            kc_spec["preset"] = preset
        (Path(d) / "s.yaml").write_text(yaml.safe_dump(kc_spec))
        lay = resolve(load_spec(Path(d) / "s.yaml"))
        _, drawn = compose(lay)
    ground = lay["ground"] if lay["ground"].get("fill") is not None else {"fill": (246, 246, 248)}
    im = draw.ground((w, h), ground).convert("RGBA")
    s = w / REF
    for sf in tmpl["background"]["surfaces"]:
        x0, y0, x1, y1 = (v * s for v in sf["rect"])
        ImageDraw.Draw(im).rounded_rectangle((x0, y0, x1, y1), radius=round(tmpl["radius"] * s),
                                             fill=tuple((sf.get("fill") or (200, 200, 204)))[:3] + (255,))
    d = ImageDraw.Draw(im)
    dark = sum((ground.get("fill") or (0, 0, 0))[:3]) < 300
    ink = (235, 235, 240, 255) if dark else (40, 40, 44, 255)
    small = draw.font(max(10, round(34 * s)), 600)
    for name, p in lay["panels"].items():
        x0, y0, x1, y1 = (v / SS for v in p["rect"])
        d.rounded_rectangle((x0, y0, x1, y1), radius=round(tmpl["radius"] * s), fill=(150, 150, 158, 255))
        holds = tmpl["panels"][name].get("holds", "scene") if not tmpl["panels"][name].get("detail_of") else "crop"
        d.text(((x0 + x1) / 2, (y0 + y1) / 2), f"{name}\n{holds}", font=small, fill=(255, 255, 255, 255),
               anchor="mm", align="center")
    for sl in tmpl["slots"]:
        box = drawn.get(sl["id"])
        if not box:
            continue
        x0, y0, x1, y1 = box
        d.rounded_rectangle((x0, y0, x1, y1), radius=min(round(tmpl["radius"] * s), (y1 - y0) / 2),
                            outline=(225, 30, 224, 255), width=max(2, round(6 * s)))
        label = f"{sl['id']} [{sl['shape']}]\n" + "\n".join(sl["accepts"]) + ("" if sl.get("required") else "\n(optional)")
        d.multiline_text(((x0 + x1) / 2, (y0 + y1) / 2), label, font=small, fill=ink, anchor="mm", align="center")
    return im


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="lp-compose", description="Compose a style-family card from generated panels.")
    p.add_argument("spec", nargs="?", type=Path, help="compose-<slot>.yaml")
    p.add_argument("--out", type=Path, help="output PNG (required with a spec)")
    p.add_argument("--replica", nargs="?", const="", metavar="FAMILY[/LAYOUT]",
                   help="redraw each layout from its own original (its pixels, its words), read both, report the gap -> --out DIR")
    p.add_argument("--probe", action="store_true",
                   help="redraw the probe set (assets/probe.yaml) against the last probe in --out DIR: regressions, one sheet")
    p.add_argument("--learn-clips", action="store_true",
                   help="replay every clip storyboard's choreography from its own keyframes, score it against the clip -> --out DIR")
    p.add_argument("--limit", type=int, help="with --learn-clips: at most this many clips")
    p.add_argument("--induce", action="store_true",
                   help="induce a layout from every composite reading (corpus/readings) -> assets/layouts.yaml")
    p.add_argument("--strict", action="store_true", help="fail when the render does not read back as its blocks' strings (OCR)")
    p.add_argument("--no-verify", action="store_true", help="skip reading the render back (OCR) after drawing it")
    p.add_argument("--describe", metavar="FAMILY", help="print a family's panels and the ratio to generate each at")
    p.add_argument("--keepclear", metavar="FAMILY", help="print the region each panel must keep clear of its subject")
    p.add_argument("--preset", help="a preset/variant of the family, for --keepclear")
    p.add_argument("--spec-from-plan", metavar="PLAN", type=Path, help="build a compose spec from a composition plan")
    p.add_argument("--blocks", metavar="PICKS", type=Path, help="blocks-<slot>.yaml, the worker's picks, for --spec-from-plan")
    p.add_argument("--check-blocks", nargs=2, metavar=("PLAN", "PICKS"), type=Path,
                   help="check the worker's picks against the plan and bind made-by.yaml")
    p.add_argument("--skeleton", metavar="FAMILY", help="draw a layout's skeleton (background, panels, slots) to --out")
    p.add_argument("--image", action="append", default=[], metavar="PANEL=PATH", help="a panel image, for --spec-from-plan")
    p.add_argument("--extract-logos", action="store_true", help="re-key the model-picker maker marks from their corpus crops")
    p.add_argument("--timeline", metavar="MOTION", type=Path, help="render a motion-<slot>.yaml to a WebM (--out), panels via --image")
    p.add_argument("--poster", type=Path, help="with --timeline: also write the last frame here")
    p.add_argument("--describe-timelines", action="store_true", help="print the timeline presets, their panels and strings")
    a = p.parse_args(argv)
    if a.describe_timelines:
        from . import timeline
        print(timeline.describe())
        return 0
    if a.timeline:
        from . import timeline
        if not a.out:
            p.error("--timeline needs --out")
        spec = timeline.load(a.timeline)
        images = {k: (a.timeline.parent / v) if not Path(v).is_absolute() else Path(v)
                  for k, v in (kv.split("=", 1) for kv in a.image)}
        n, secs = timeline.render(spec, images, a.out, a.poster)
        print(f"{a.out}: {spec['preset']} {spec['size']} {n} frames, {secs:.2f} s")
        return 0
    if a.extract_logos:
        from . import models
        for f in models.extract_logos(Path.cwd()):
            print(f)
        return 0
    if a.describe:
        print(describe(a.describe))
        return 0
    if a.keepclear:
        from . import plan  # lazy: plan imports cli
        size = parse_size(a.spec) if a.spec else None  # optional WxH passed positionally
        preset = preset_for_size(a.keepclear, size, a.preset)  # a 1:1 before-after size -> stacked-square
        print(yaml.safe_dump(plan.keep_clear(a.keepclear, preset, size), sort_keys=True).rstrip())
        return 0
    if a.check_blocks:
        return check_blocks(*a.check_blocks)
    if a.skeleton:
        if not a.out:
            p.error("--skeleton needs --out")
        size = parse_size(a.spec) if a.spec else None
        skeleton_image(a.skeleton, a.preset, size).save(a.out)
        print(f"{a.out}: {a.skeleton}{'/' + a.preset if a.preset else ''} skeleton")
        return 0
    if a.spec_from_plan:
        from . import plan  # lazy
        if not a.out:
            p.error("--spec-from-plan needs --out")
        images = dict(kv.split("=", 1) for kv in a.image)
        cp = yaml.safe_load(a.spec_from_plan.read_text()) or {}
        doc = yaml.safe_load(a.blocks.read_text()) if a.blocks else None
        if [s for s in cp.get("slots") or [] if s.get("required")] and not doc:
            sys.exit(f"lp-compose: {a.spec_from_plan.name} has required slots: pick their blocks in "
                     f"blocks-{cp.get('slot')}.yaml and pass --blocks")
        if doc is not None:
            if check_blocks(a.spec_from_plan, a.blocks):
                return 1
        spec = plan.to_spec(cp, images, doc)
        spec["plan"] = a.spec_from_plan.name  # so precheck can pair the spec with its plan
        if a.blocks:
            spec["blocks"] = a.blocks.name
        a.out.parent.mkdir(parents=True, exist_ok=True)
        a.out.write_text(yaml.safe_dump(spec, sort_keys=False, allow_unicode=True))
        print(f"{a.out}: spec from {a.spec_from_plan.name} ({len(images)} panel image(s))")
        return 0
    if a.learn_clips:
        from . import tlinduce
        out_dir = a.out or Path("research/clips")
        results = tlinduce.run(out_dir, a.limit)
        (out_dir / "report.md").write_text(tlinduce.report(results))
        ok = [r["error"] for r in results if "failed" not in r]
        print(f"{out_dir / 'report.md'}: {len(ok)} clips replayed, median error "
              f"{sorted(ok)[len(ok) // 2] if ok else float('nan'):.3f}, {len(results) - len(ok)} failed")
        return 0
    if a.induce:
        from . import induce
        cat = induce.run()
        n = sum(len(v) for v in cat.values())
        members = sum(len(lay.get("members") or []) for v in cat.values() for lay in v.values())
        print(f"{induce.LAYOUTS}: {n} layouts ({members} more originals share one) in "
              f"{', '.join(f'{k} {len(v)}' for k, v in sorted(cat.items()))}")
        return 0
    if a.probe:
        from . import replica
        lines = replica.probe(a.out or Path("research/probe"))
        print("\n".join(lines))
        return 1 if any(x.startswith("WORSE") for x in lines) else 0
    if a.replica is not None:
        from . import replica
        out_dir = a.out or Path("research/replicas")
        results = replica.run(out_dir, a.replica or None)
        (out_dir / "report.md").write_text(replica.report(results))
        for r in sorted((r for r in results if "skipped" not in r), key=lambda r: -r["severity"]):
            print(f"{r['layout']:<34} chrome {r['chrome_error']:.3f}  severity {r['severity']:>3}  findings {len(r['findings'])}")
        for r in results:
            if "skipped" in r:
                print(f"{r['layout']:<34} skipped: {r['skipped']}")
        print(f"{out_dir / 'report.md'}")
        return 0
    if not a.spec or not a.out:
        p.error("a spec and --out are required unless --describe is given")
    spec = load_spec(a.spec)
    lay = resolve(spec)
    out, _ = compose(lay)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    out.save(a.out)
    print(f"{a.out}: {spec['family']} {out.width}x{out.height}")
    if not a.no_verify:
        for name, p in lay["panels"].items():  # a subject-anchored panel checked itself while it drew
            if p["anchor"] != "subject" and p["fit"] == "cover" and not (p.get("crop") or p.get("trim")) and p.get("image"):
                x0, y0, x1, y1 = p["rect"]
                found = subject.locate(str(p["image"]))
                at = draw.parse_anchor(p["anchor"])
                if subject.cut(found, subject.crop_box((found["w"], found["h"]), (x1 - x0, y1 - y0), at)):
                    print(f"verify: {name}: a face is cut by the panel's frame (try `anchor: subject`)")
    if verify.available() and not a.no_verify:
        # read the render back: every string a block sets must say what it was given
        probs = verify.problems(a.out, spec.get("chrome") or [])
        for pr in probs:
            print(f"verify: {pr}")
        if probs and a.strict:
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
