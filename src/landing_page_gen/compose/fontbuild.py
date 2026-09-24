"""Build the static Manrope weights lp-compose draws with.

`assets/Manrope.ttf` is a variable font (wght 200-800). A few composite
glyphs keep their 200-weight component offsets at every weight: the parts
grow and the offsets stay put, so from 600 the lower dot of ÷ runs into the
bar (it printed as +), and the marks of ť, Ţ and ΐ crowd their letters.
FreeType draws exactly what the font says, so the fix is the font: each
static weight is instanced, then every composite whose parts drift from
their 200-weight relationship has its parts re-seated: a part stacked on its
neighbour keeps its gap and its centring, a part beside it keeps its gap,
and the glyph keeps its place in the advance.

Run once when the font changes (fontTools is not a project dependency):

    uv run --with fonttools python -m landing_page_gen.compose.fontbuild
"""

from pathlib import Path

ASSETS = Path(__file__).parent / "assets"
WEIGHTS = (400, 500, 600, 700, 800)
TOLERANCE = 0.06  # a part further than this share of its neighbour's size from its seat has drifted


def _box(gs, name, dx=0, dy=0):
    from fontTools.pens.boundsPen import BoundsPen
    pen = BoundsPen(gs)
    gs[name].draw(pen)
    if pen.bounds is None:
        return None
    x0, y0, x1, y1 = pen.bounds
    return (x0 + dx, y0 + dy, x1 + dx, y1 + dy)


def _stacked(a, b):
    """True when two parts share most of their width (one above the other)."""
    ov = min(a[2], b[2]) - max(a[0], b[0])
    return ov >= 0.5 * min(a[2] - a[0], b[2] - b[0])


def _seat(ref0, part0, ref, part):
    """The (dx, dy) that puts `part` against `ref` as `part0` sat against `ref0`."""
    if _stacked(ref0, part0):
        rel = ((part0[0] + part0[2]) / 2 - (ref0[0] + ref0[2]) / 2) / max(1, ref0[2] - ref0[0])
        dx = (ref[0] + ref[2]) / 2 + rel * (ref[2] - ref[0]) - (part[0] + part[2]) / 2
        if part0[1] >= ref0[3] - 1:       # above: keep the gap over the ref's top
            dy = ref[3] + (part0[1] - ref0[3]) - part[1]
        elif part0[3] <= ref0[1] + 1:     # below: keep the gap under the ref's bottom
            dy = ref[1] - (ref0[1] - part0[3]) - part[3]
        else:
            dy = 0
        return dx, dy
    if part0[0] >= (ref0[0] + ref0[2]) / 2:   # to the right: keep the gap after the ref
        return ref[2] + (part0[0] - ref0[2]) - part[0], 0
    return ref[0] - (ref0[0] - part0[2]) - part[2], 0   # to the left: keep the gap before it


def _distance(a, b):
    """The gap between two boxes (0 when they touch)."""
    return max(0, a[0] - b[2], b[0] - a[2]) + max(0, a[1] - b[3], b[1] - a[3])


def _touch(a, b):
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def _nearest(boxes0, i):
    """The earlier part that part i sat against at 200."""
    return min(range(i), key=lambda k: _distance(boxes0[k], boxes0[i]))


def _vgap(ref, part):
    return part[1] - ref[3] if part[1] >= ref[3] - 1 else ref[1] - part[3]


def drifted(boxes0, boxes):
    """Whether a composite's parts lost their 200-weight relationship: two parts
    that stood apart now touch, a stacked part left the centre of the part it
    sits on, the gap beside a part closed to under half, or a part's even gaps
    above and below (the dots of ÷) went uneven."""
    for i in range(len(boxes)):
        for j in range(i + 1, len(boxes)):
            if _touch(boxes[i], boxes[j]) and not _touch(boxes0[i], boxes0[j]):
                return True
    stacked_on = {}
    for i in range(1, len(boxes)):
        j = _nearest(boxes0, i)
        r0, p0, r, p = boxes0[j], boxes0[i], boxes[j], boxes[i]
        if _stacked(r0, p0):
            rel0 = ((p0[0] + p0[2]) - (r0[0] + r0[2])) / 2 / max(1, r0[2] - r0[0])
            rel = ((p[0] + p[2]) - (r[0] + r[2])) / 2 / max(1, r[2] - r[0])
            if abs(rel - rel0) > TOLERANCE:
                return True
            stacked_on.setdefault(j, []).append((_vgap(r0, p0), _vgap(r, p)))
        else:
            gap0 = max(p0[0] - r0[2], r0[0] - p0[2])
            gap = max(p[0] - r[2], r[0] - p[2])
            if gap0 > 0 and gap < 0.5 * gap0:
                return True
    for gaps in stacked_on.values():
        if len(gaps) == 2:
            (a0, a), (b0, b) = gaps
            if abs(a0 - b0) <= 0.05 * max(a0, b0) and abs(a - b) > 0.15 * max(a, b, 1):
                return True
    return False


def repair(inst, default):
    """Re-seat the drifting composites of a static instance in place, each part
    against the part it sat nearest at 200; returns the names changed."""
    glyf, glyf0 = inst["glyf"], default["glyf"]
    gs, gs0 = inst.getGlyphSet(), default.getGlyphSet()
    hmtx, hmtx0 = inst["hmtx"], default["hmtx"]
    changed = []
    for name in inst.getGlyphOrder():
        g = glyf[name]
        if not g.isComposite() or name not in glyf0.glyphs:
            continue
        comps, comps0 = g.components, glyf0[name].components
        boxes0 = [_box(gs0, c.glyphName, c.x, c.y) for c in comps0]
        boxes = [_box(gs, c.glyphName, c.x, c.y) for c in comps]
        if len(boxes) < 2 or None in boxes0 or None in boxes or not drifted(boxes0, boxes):
            continue
        moves = [(0, 0)]
        for i in range(1, len(comps)):
            j = _nearest(boxes0, i)
            dx, dy = _seat(boxes0[j], boxes0[i], boxes[j], boxes[i])
            moves.append((round(dx), round(dy)))
            x0, y0, x1, y1 = boxes[i]
            boxes[i] = (x0 + moves[-1][0], y0 + moves[-1][1], x1 + moves[-1][0], y1 + moves[-1][1])
        # a glyph of like parts (" … „) keeps its place in the advance; a letter
        # with a mark (ď Œ) keeps its letter where the plain letter sits
        lo, hi = min(b[0] for b in boxes), max(b[2] for b in boxes)
        shift = 0
        if boxes[0][2] - boxes[0][0] < 0.5 * (hi - lo):
            mid0 = (min(b[0] for b in boxes0) + max(b[2] for b in boxes0)) / 2
            shift = round(mid0 / max(1, hmtx0[name][0]) * hmtx[name][0] - (lo + hi) / 2)
        for c, (dx, dy) in zip(comps, moves):
            c.x += dx + shift
            c.y += dy
        g.recalcBounds(glyf)
        hmtx[name] = (hmtx[name][0], g.xMin)
        changed.append(name)
    return changed


def build():
    from fontTools.ttLib import TTFont
    from fontTools.varLib import instancer

    default = instancer.instantiateVariableFont(TTFont(ASSETS / "Manrope.ttf"), {"wght": 200})
    # what the font can set: a string with any other character would draw .notdef boxes
    chars = "".join(chr(u) for u in sorted(default.getBestCmap()) if u > 32)
    (ASSETS / "Manrope.chars.txt").write_text(chars + "\n", encoding="utf-8")
    for w in WEIGHTS:
        inst = instancer.instantiateVariableFont(TTFont(ASSETS / "Manrope.ttf"), {"wght": w}, updateFontNames=True)
        changed = repair(inst, default)
        out = ASSETS / f"Manrope-{w}.ttf"
        inst.save(out)
        print(f"{out.name}: {len(changed)} composites re-seated ({', '.join(changed)})")


if __name__ == "__main__":
    build()
