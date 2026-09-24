"""What an icon on a corpus original is: its shape matched against the icons
lp-compose draws (draw.ICONS) and the makers' marks it knows (assets/logos).

A reading finds an icon as a small shape of one colour in a card; to template
the slot honestly the icon must be named: an upload arrow is the reader's step
(action), a crop glyph is a tool, the OpenAI knot is attribution. The icon's
pixels are binarised against the card's fill and compared by overlap (IoU)
with each known shape rendered at the same size; the best above MATCH wins."""

from functools import cache
from pathlib import Path

import numpy as np
from PIL import Image

from . import draw

SIZE = 48
MATCH = 0.55
LOGOS = Path(__file__).parent / "assets" / "logos"


def _mask(img, back):
    """Where an RGB(A) crop differs from its background colour, squared and centred."""
    a = np.asarray(img.convert("RGB"), np.float32)
    m = np.abs(a - np.asarray(back, np.float32)).max(-1) > 60
    ys, xs = np.nonzero(m)
    if len(ys) < 6:
        return None
    m = m[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    h, w = m.shape
    side = max(h, w)
    sq = np.zeros((side, side), bool)
    sq[(side - h) // 2:(side - h) // 2 + h, (side - w) // 2:(side - w) // 2 + w] = m
    return np.asarray(Image.fromarray(sq.astype(np.uint8) * 255).resize((SIZE, SIZE), Image.BILINEAR)) > 127


@cache
def _known():
    """{name: mask} of every drawable icon and every maker mark."""
    out = {}
    for name in draw.ICONS:
        im = Image.new("RGBA", (SIZE * 2, SIZE * 2), (0, 0, 0, 255))
        draw.icon(im, (0, 0, SIZE * 2, SIZE * 2), name)
        m = _mask(im, (0, 0, 0))
        if m is not None:
            out[name] = m
    for p in sorted(LOGOS.glob("*.png")):
        im = Image.open(p).convert("RGBA")
        base = Image.new("RGBA", im.size, (0, 0, 0, 255))
        base.alpha_composite(im)
        m = _mask(base, (0, 0, 0))
        if m is not None:
            out[f"logo:{p.stem}"] = m
    return out


def classify(crop, back):
    """(name, score) of the known shape an icon crop is, or (None, best score).
    A learned glyph names only what no drawn icon or maker's mark matches: it
    was mined from those leftovers, and a mark it outscored would lose its
    attribution (48 generator marks became blank tiles)."""
    m = _mask(crop, back)
    if m is None:
        return None, 0.0
    best = (None, 0.0)
    for learned in (False, True):
        for name, k in _known().items():
            if ("glyph" in draw.ICONS.get(name, {})) != learned:
                continue
            iou = float((m & k).sum() / max(1, (m | k).sum()))
            if iou > best[1]:
                best = (name, iou)
        if best[1] >= MATCH:
            return best[0], round(best[1], 3)
    return None, round(best[1], 3)


# ---------------------------------------------------------------- learning new icons

LEARNED = Path(__file__).parent / "assets" / "icons"
CLUSTER = 0.62   # IoU at which two unknown shapes are one icon


def _unknowns(readings_iter, limit=None):
    """(mask, crop, where) of every card icon no known shape matches."""
    out = []
    for rd in readings_iter:
        try:
            img = Image.open(rd["local"]).convert("RGBA")
        except OSError:
            continue
        base = Image.new("RGBA", img.size, (255, 255, 255, 255))
        base.alpha_composite(img)
        img = base.convert("RGB")
        for reg in rd["regions"]:
            if reg["kind"] != "card":
                continue
            for c in reg.get("children") or []:
                if c["kind"] != "icon" or c.get("text"):
                    continue
                w, h = c["box"][2] - c["box"][0], c["box"][3] - c["box"][1]
                if min(w, h) < 12 or max(w, h) > 5 * min(w, h):
                    continue
                crop = img.crop(tuple(c["box"]))
                name, _ = classify(crop, reg.get("fill") or [0, 0, 0])
                m = _mask(crop, reg.get("fill") or [0, 0, 0])
                if name or m is None or m.mean() < 0.04:
                    continue
                out.append((m, crop, f"{rd['id']}"))
                if limit and len(out) >= limit:
                    return out
    return out


def mine(readings_iter, limit=None):
    """Clusters of unknown icons, biggest first: [{size, medoid crop, where}]."""
    items = _unknowns(readings_iter, limit)
    clusters = []
    for m, crop, where in items:
        for cl in clusters:
            k = cl["mask"]
            if float((m & k).sum() / max(1, (m | k).sum())) >= CLUSTER:
                cl["n"] += 1
                cl["where"].append(where)
                break
        else:
            clusters.append({"mask": m, "crop": crop, "n": 1, "where": [where]})
    return sorted(clusters, key=lambda c: -c["n"])


def sheet(clusters, out, top=48):
    from PIL import ImageDraw
    cell = 110
    cols = 8
    rows = (min(top, len(clusters)) + cols - 1) // cols
    im = Image.new("RGB", (cols * cell, rows * (cell + 16)), (240, 240, 244))
    d = ImageDraw.Draw(im)
    for i, cl in enumerate(clusters[:top]):
        x, y = (i % cols) * cell, (i // cols) * (cell + 16)
        c = cl["crop"].copy()
        c.thumbnail((cell - 10, cell - 10))
        im.paste(c, (x + 5, y + 5))
        d.text((x + 4, y + cell), f"#{i} n={cl['n']}", fill=(0, 0, 0))
    im.save(out)
    return out
