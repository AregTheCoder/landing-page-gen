"""Relative placement for compose specs.

Absolute `rect:` (in the REF frame) stays the primary form — it is what makes
the six shipped families byte-identical. `place:` is the addition: it anchors a
chrome item to the canvas or a named panel so a spec (or a preset) need not
hand-compute pixels. It resolves to a REF-frame rect, which `resolve()` then
scales exactly like any other rect, so nothing downstream changes.

    place:
      of: canvas | <panel id>     # the box to anchor to (default canvas)
      anchor: tl t tr l c r bl b br | top bottom left right centre
      w: 380 | "25%" | 0.25       # px in the REF frame, or a fraction of `of`
      h: 380 | "25%" | 0.25
      inset: 40                   # gap from the anchored edge(s); negative overhangs
      dx: 0                       # extra REF-px nudge
      dy: 0
"""

import sys

# fraction of the reference box each anchor sits at, in x and y
_AX = {"tl": 0, "l": 0, "bl": 0, "left": 0, "t": .5, "c": .5, "b": .5,
       "top": .5, "bottom": .5, "centre": .5, "center": .5, "tr": 1, "r": 1, "br": 1, "right": 1}
_AY = {"tl": 0, "t": 0, "tr": 0, "top": 0, "l": .5, "c": .5, "r": .5,
       "left": .5, "right": .5, "centre": .5, "center": .5, "bl": 1, "b": 1, "br": 1, "bottom": 1}


def _dim(v, full):
    if isinstance(v, str) and v.endswith("%"):
        return full * float(v[:-1]) / 100
    if isinstance(v, float) and 0 < v <= 1:
        return full * v
    return float(v)


def to_rect(place, boxes):
    """A REF-frame rect from a `place` block, given the REF rects of the
    anchor boxes (`canvas` plus every panel and earlier item by id)."""
    of = place.get("of", "canvas")
    if of not in boxes:
        sys.exit(f"lp-compose: place.of {of!r} is not canvas, a panel, or an earlier item")
    bx0, by0, bx1, by1 = boxes[of]
    bw, bh = bx1 - bx0, by1 - by0
    w, h = _dim(place.get("w", bw), bw), _dim(place.get("h", bh), bh)
    ax, ay = _AX[place.get("anchor", "tl")], _AY[place.get("anchor", "tl")]
    inset = place.get("inset", 0)
    x0 = bx0 + ax * bw - ax * w + (inset if ax == 0 else -inset if ax == 1 else 0) + place.get("dx", 0)
    y0 = by0 + ay * bh - ay * h + (inset if ay == 0 else -inset if ay == 1 else 0) + place.get("dy", 0)
    return (round(x0), round(y0), round(x0 + w), round(y0 + h))


def expand_repeat(item):
    """A chrome item with `repeat: N` becomes N items id-1..id-N, stacked along
    `dir` (column|row) with `gap` between them inside the item's own rect. An
    item without `repeat` is returned unchanged as a one-element list."""
    n = item.get("repeat")
    if not n or n < 1:
        return [item]
    x0, y0, x1, y1 = item["rect"]
    gap = item.get("gap", 0)
    horizontal = item.get("dir") == "row"
    span = (x1 - x0) if horizontal else (y1 - y0)
    step = (span - gap * (n - 1)) / n
    out = []
    for i in range(n):
        it = {k: v for k, v in item.items() if k not in ("repeat", "dir", "gap")}
        it["id"] = f"{item['id']}-{i + 1}"
        off = round(i * (step + gap))
        it["rect"] = ((x0 + off, y0, round(x0 + off + step), y1) if horizontal
                      else (x0, y0 + off, x1, round(y0 + off + step)))
        out.append(it)
    return out
