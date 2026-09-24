"""Before a worker spends: does the layout a slot is briefed on look like the
slot's own original? Three measurements against the original's reading
(`corpus/readings`), each a warning the manager resolves before the brief goes
out, plus a sheet with the original beside the layout's skeleton.

The live checks found both of their layout faults only after a worker had paid
for panels: a layout induced from a lettering sticker (its pictures a thin band
at 16 % of the canvas where the original's filled 95 %) and a crop layout whose
result was narrower than its source."""

from PIL import Image

from .families import REF

AREA = 0.5     # the layout's pictures cover less than this share of the original's: a different device
ASPECT = 0.15  # relative difference of canvas aspects above which the layout is another shape
FULL = 0.9     # one picture over this share of its canvas is a full-bleed original


def _pictures(reading):
    """(pictures, boxes): the original's pictures (a compare card's Before and
    After are two in one box) and each box's share of its canvas."""
    w, h = reading["size"]
    n, boxes = 0, []
    for r in reading.get("regions") or []:
        if r["kind"] != "picture":
            continue
        x0, y0, x1, y1 = r["box"]
        n += 2 if r.get("split") is not None else 1
        boxes.append(((x1 - x0) * (y1 - y0)) / (w * h))
    return n, boxes


def _panels(tmpl):
    """(panels, boxes) of the layout: panels sharing one rect (a seam) are one box."""
    aw, ah = tmpl["aspect"]
    w, h = REF, REF * ah / aw
    rects = [tuple(p["rect"] or (0, 0, w, h)) for p in (tmpl.get("panels") or {}).values()
             if not p.get("detail_of")]  # a detail is cropped from another panel, not a picture of its own
    return len(rects), [((x1 - x0) * (y1 - y0)) / (w * h) for x0, y0, x1, y1 in dict.fromkeys(rects)]


def check(tmpl, reading):
    """Warnings, one line each; empty when the layout fits its original."""
    if not reading:
        return ["no reading of this slot's original: the layout cannot be checked against it"]
    warn = []
    (n, pics), (m, pans) = _pictures(reading), _panels(tmpl)
    if n and m != n:
        warn.append(f"panels: the layout has {m}, the original shows {n} pictures"
                    + (f" (one picture over {pics[0]:.0%} of it: full-bleed, or a ground the reader cannot see,"
                       " e.g. a gradient)" if n == 1 and pics[0] > FULL else ""))
    elif n and len(pans) != len(pics):
        warn.append(f"boxes: the layout lays its {m} pictures in {len(pans)} boxes, the original in {len(pics)}"
                    " (a compare card is one box)")
    if pics and sum(pans) < AREA * sum(pics):
        warn.append(f"scale: the layout's pictures fill {sum(pans):.0%} of the canvas, the original's {sum(pics):.0%}")
    ow, oh = reading["size"]
    aw, ah = tmpl["aspect"]
    if abs((aw / ah) / (ow / oh) - 1) > ASPECT:
        warn.append(f"aspect: the layout is {aw}:{ah}, the original {ow}x{oh}")
    return warn


def sheet(original, skeleton, out, height=360):
    """The original beside the layout's skeleton, one height, on grey."""
    ims = []
    for im in (Image.open(original).convert("RGBA"), skeleton.convert("RGBA")):
        g = Image.new("RGBA", im.size, (200, 200, 200, 255))
        g.alpha_composite(im)
        ims.append(g.convert("RGB").resize((round(im.width * height / im.height), height)))
    s = Image.new("RGB", (ims[0].width + ims[1].width + 16, height), (255, 255, 255))
    s.paste(ims[0], (0, 0))
    s.paste(ims[1], (ims[0].width + 16, 0))
    s.save(out)
    return out
