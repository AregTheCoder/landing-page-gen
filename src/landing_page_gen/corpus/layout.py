"""A composite read off its pixels: the ground, the cards and pictures laid on
it, and what sits inside each card (text lines, fields, icons) or over each
picture (pills).

Picsart's composites are grids: cards and pictures separated by strips of the
ground. A recursive XY-cut on the ground mask finds them; inside a flat card,
the card's own fill is the ground of the next level. The OCR reading
(`ocr.py`) places the words. Everything is measured on a copy at most WORK px
across and returned in the original's pixels and in REF units (1600 across,
the frame lp-compose templates use)."""

import numpy as np
from PIL import Image, ImageFilter

WORK = 800
REF = 1600
TOL = 0.07          # chebyshev distance (0..1) to a colour that still counts as that colour
MIN_GUTTER = 3      # WORK px: a thinner strip of ground does not separate two regions
MIN_LEAF = 5        # WORK px: a smaller region is noise
FLAT_SHARE = 0.55   # share of a region's pixels at its fill above which it is a card, not a picture
FLAT_STD = 0.02     # luma spread of those pixels under which the fill is flat (paint, not a backdrop)
RING_FLAT = 0.9     # share of a text box's surround at one colour that makes it a pill over a picture
STROKE_SURVIVE = 0.3  # share of a transparent-ground figure left after a 4 px erosion below which it is strokes, not a picture
SEAM_RUN = 0.85    # share of a picture's rows a compare divider runs down...
SEAM_W = 0.03       # ...within this share of its width, between two halves that are not white


def load(path, work=WORK):
    """(rgb HxWx3 in 0..1 on white, alpha HxW or None, scale to original px)."""
    with Image.open(path) as im:
        w0 = im.size[0]
        im = im.convert("RGBA")
        im.thumbnail((work, work))
        a = np.asarray(im, dtype=np.float32) / 255.0
    alpha = a[..., 3]
    rgb = a[..., :3] * alpha[..., None] + (1 - alpha[..., None])
    return rgb, (alpha if alpha.min() < 0.99 else None), w0 / a.shape[1]


def near(rgb, colour, tol=TOL):
    return np.abs(rgb - np.asarray(colour, dtype=np.float32)).max(axis=-1) < tol


def _gutter_colours(rgb, top=3):
    """Candidate colours of the strips between panels: the commonest colours of
    the rows and columns that are one flat colour end to end."""
    meds = []
    for lines in (rgb, rgb.transpose(1, 0, 2)):
        med = np.median(lines, axis=1)
        flat = (np.abs(lines - med[:, None, :]).max(axis=-1) < TOL).mean(axis=1) >= 0.97
        meds += list(med[flat])
    if len(meds) < MIN_GUTTER:
        return []
    meds = np.array(meds)
    codes = np.round(meds * 15).astype(int) @ np.array([256, 16, 1])
    vals, counts = np.unique(codes, return_counts=True)
    return [np.median(meds[codes == v], axis=0) for v in vals[np.argsort(-counts)][:top]]


def _cut_quality(bg, w, h):
    """How well a background mask cuts the image into panels: the leaves, if at
    least two cover at least half the image."""
    leaves = xycut(bg, (0, 0, w, h))
    area = sum((x1 - x0) * (y1 - y0) for x0, y0, x1, y1 in leaves)
    return leaves if len(leaves) >= 2 and area >= 0.5 * w * h else None


def ground_of(rgb, alpha):
    """The ground: 'transparent' when the file is see-through around or between
    its panels, the border's colour when it is one flat colour, else the colour
    of the strips between panels (pictures that run to the edge still sit on
    it); None for one picture."""
    h, w = rgb.shape[:2]
    k = max(2, round(min(h, w) * 0.02))
    if alpha is not None:
        ring_a = np.concatenate([alpha[:k].ravel(), alpha[-k:].ravel(), alpha[:, :k].ravel(), alpha[:, -k:].ravel()])
        if (ring_a < 0.5).mean() > 0.5 or _cut_quality(alpha < 0.5, w, h):
            return "transparent"
    ring = np.concatenate([rgb[:k].reshape(-1, 3), rgb[-k:].reshape(-1, 3), rgb[:, :k].reshape(-1, 3), rgb[:, -k:].reshape(-1, 3)])
    med = np.median(ring, axis=0)
    if near(ring, med).mean() >= 0.8:
        return med
    best = None
    for g in _gutter_colours(rgb):
        if float(g.max() - g.min()) / max(1e-3, float(g.max())) > 0.25:
            continue  # a saturated flat band (a photo's clear sky) is not the strip between panels
        leaves = _cut_quality(near(rgb, g), w, h)
        if leaves and (best is None or len(leaves) > best[0]):
            best = (len(leaves), g)
    return best[1] if best else None


def _runs(flags, min_len):
    """(start, end) of the runs of True at least min_len long."""
    out, start = [], None
    for i, f in enumerate(list(flags) + [False]):
        if f and start is None:
            start = i
        elif not f and start is not None:
            if i - start >= min_len:
                out.append((start, i))
            start = None
    return out


def xycut(bg, box):
    """Leaves of a recursive XY-cut of `box` along strips of background (whole
    rows or columns of `bg`), each trimmed to what it holds."""
    x0, y0, x1, y1 = box
    sub = bg[y0:y1, x0:x1]
    rows, cols = ~sub.all(axis=1), ~sub.all(axis=0)
    if not rows.any():
        return []
    ys, xs = np.nonzero(rows)[0], np.nonzero(cols)[0]
    x0, x1, y0, y1 = x0 + xs[0], x0 + xs[-1] + 1, y0 + ys[0], y0 + ys[-1] + 1
    if x1 - x0 < MIN_LEAF or y1 - y0 < MIN_LEAF:
        return []
    sub = bg[y0:y1, x0:x1]
    best = None
    for axis in (0, 1):
        prof = sub.all(axis=1) if axis == 0 else sub.all(axis=0)
        runs = _runs(prof, MIN_GUTTER)
        if runs and (best is None or max(e - s for s, e in runs) > best[2]):
            best = (axis, runs, max(e - s for s, e in runs))
    if not best:
        return [(int(x0), int(y0), int(x1), int(y1))]
    axis, runs, _ = best
    cuts, prev, out = [], 0, []
    n = (y1 - y0) if axis == 0 else (x1 - x0)
    for s, e in runs:
        cuts.append((prev, s))
        prev = e
    cuts.append((prev, n))
    for a, b in cuts:
        if b - a <= 0:
            continue
        piece = (x0, y0 + a, x1, y0 + b) if axis == 0 else (x0 + a, y0, x0 + b, y1)
        out += xycut(bg, piece)
    return out


def _fill(px):
    """The dominant colour of an Nx3 pixel list and the share of pixels at it."""
    q = np.round(px * 15).astype(np.int32)
    codes = q[:, 0] * 256 + q[:, 1] * 16 + q[:, 2]
    vals, counts = np.unique(codes, return_counts=True)
    top = vals[counts.argmax()]
    sel = codes == top
    colour = np.median(px[sel], axis=0)
    share = near(px, colour).mean()
    return colour, float(share), px[near(px, colour)]


def radius(fg):
    """Corner radius of the shape in a boolean box: the circle whose profile
    (how far in each top row starts) best fits each corner, median of four."""
    h, w = fg.shape
    lim = max(2, min(h, w) // 2)
    rs = []
    for corner in (fg, fg[:, ::-1], fg[::-1], fg[::-1, ::-1]):
        prof = []
        for dy in range(lim):
            row = np.nonzero(corner[dy])[0]
            prof.append(row[0] if row.size else lim)
        prof = np.array(prof, np.float32)
        if prof[0] <= 1:  # square corner
            rs.append(0.0)
            continue
        dys = np.arange(lim, dtype=np.float32) + 0.5
        best = (1e9, 0.0)
        for r in range(1, lim):
            model = np.where(dys < r, r - np.sqrt(np.maximum(0, r * r - (r - dys) ** 2)), 0)
            n = min(lim, r + 2)
            err = float(np.abs(model[:n] - prof[:n]).mean())
            if err < best[0]:
                best = (err, float(r))
        rs.append(best[1])
    return float(np.median(rs))


def _rounded(size, r, inset=0):
    """Boolean mask of a rounded rectangle filling `size`, shrunk by `inset` px."""
    from PIL import ImageDraw as _D
    m = Image.new("L", size, 0)
    w, h = size
    if w - 2 * inset > 0 and h - 2 * inset > 0:
        _D.Draw(m).rounded_rectangle((inset, inset, w - 1 - inset, h - 1 - inset), radius=max(0, r - inset), fill=255)
    return np.asarray(m) > 127


def _to_orig(box, scale):
    return [round(v * scale) for v in box]


def _ref(box_px, w0):
    return [round(v * REF / w0) for v in box_px]


def _texts_in(texts, box, scale):
    x0, y0, x1, y1 = (v * scale for v in box)
    out = []
    for t in texts:
        tx0, ty0, tx1, ty1 = t["box"]
        cx, cy = (tx0 + tx1) / 2, (ty0 + ty1) / 2
        if x0 <= cx <= x1 and y0 <= cy <= y1:
            out.append(t)
    return out


def _text_colour(rgb, box, back, scale):
    x0, y0, x1, y1 = (int(round(v / scale)) for v in box)
    px = rgb[max(0, y0):y1, max(0, x0):x1].reshape(-1, 3)
    if not px.size:
        return None
    far = px[np.abs(px - back).max(axis=1) > 0.25]
    return (np.median(far, axis=0) * 255).round().astype(int).tolist() if len(far) else None


def _pill(rgb, tbox, scale, limit=0.2):
    """The flat plate a string sits on over a picture, grown out from the text
    box while its edge stays one colour; None when the surround is picture."""
    h, w = rgb.shape[:2]
    x0, y0, x1, y1 = (int(round(v / scale)) for v in tbox)
    x0, y0, x1, y1 = max(0, x0 - 2), max(0, y0 - 2), min(w, x1 + 2), min(h, y1 + 2)
    ring = np.concatenate([rgb[max(0, y0 - 3):y0, x0:x1].reshape(-1, 3), rgb[y1:y1 + 3, x0:x1].reshape(-1, 3),
                           rgb[y0:y1, max(0, x0 - 3):x0].reshape(-1, 3), rgb[y0:y1, x1:x1 + 3].reshape(-1, 3)])
    if len(ring) < 8:
        return None
    colour = np.median(ring, axis=0)
    if near(ring, colour).mean() < RING_FLAT:
        return None
    th = y1 - y0  # a plate is at most a text height beyond its words on each side
    grow = max(4, min(int(limit * min(h, w)), th))
    for _ in range(grow):
        moved = False
        if y0 > 0 and near(rgb[y0 - 1, x0:x1], colour).mean() > 0.6:
            y0, moved = y0 - 1, True
        if y1 < h and near(rgb[y1, x0:x1], colour).mean() > 0.6:
            y1, moved = y1 + 1, True
        if x0 > 0 and near(rgb[y0:y1, x0 - 1], colour).mean() > 0.6:
            x0, moved = x0 - 1, True
        if x1 < w and near(rgb[y0:y1, x1], colour).mean() > 0.6:
            x1, moved = x1 + 1, True
        if not moved:
            break
    return (x0, y0, x1, y1), colour


def _survives(fg):
    """Share of a mask left after a 4 px erosion: ~1 for a photo, ~0 for strokes."""
    er = np.asarray(Image.fromarray(fg.astype(np.uint8) * 255).filter(ImageFilter.MinFilter(9))) > 127
    return er.sum() / max(1, fg.sum())


def _seam(rgb, box):
    """Where a compare card's divider runs (0..1 across the picture), or None:
    a white line straight down the picture's middle half, with a picture, not
    white, either side of it (add-shadow-to-image S11, ai-image-enhancer S14)."""
    x0, y0, x1, y1 = box
    w = x1 - x0
    if w < 40 or y1 - y0 < 40:
        return None
    white = (rgb[y0:y1, x0:x1].min(-1) >= 0.92).mean(0)  # share of each column's rows that is white
    lo = w // 4
    run = np.nonzero(white[lo:w - lo] >= SEAM_RUN)[0] + lo
    if not len(run) or run.max() - run.min() + 1 > max(3, SEAM_W * w):
        return None
    beside = np.r_[white[max(0, run.min() - 10):max(0, run.min() - 3)], white[run.max() + 4:run.max() + 11]]
    if not len(beside) or beside.max() >= 0.6:
        return None
    return round(float((run.min() + run.max() + 1) / 2 / w), 3)


def _text_mask(texts, box, scale, shape):
    """The OCR boxes that fall in `box`, as a mask over the working image."""
    m = np.zeros(shape, bool)
    for t in _texts_in(texts, box, scale):
        x0, y0, x1, y1 = (int(round(v / scale)) for v in t["box"])
        m[max(0, y0):y1, max(0, x0):x1] = True
    return m


def _rgb255(c):
    return (np.asarray(c) * 255).round().astype(int).tolist()


def read(path, reading=None, work=WORK):
    """The layout of one image. `reading` is its OCR reading (ocr.read), whose
    lines are placed in the region they sit in."""
    rgb, alpha, scale = load(path, work)
    h, w = rgb.shape[:2]
    w0 = round(w * scale)
    texts = [dict(t) for t in (reading or {}).get("lines") or []]
    ground = ground_of(rgb, alpha)
    out = {"size": [w0, round(h * scale)], "ground": None, "regions": [], "texts": texts}
    if isinstance(ground, str):
        out["ground"] = ground
        bg = alpha < 0.5
    elif ground is None:
        out["ground"] = "picture"
        bg = np.zeros((h, w), bool)
    else:
        out["ground"] = _rgb255(ground)
        bg = near(rgb, ground)
    leaves = xycut(bg, (0, 0, w, h)) if out["ground"] != "picture" else [(0, 0, w, h)]
    for box in leaves:
        x0, y0, x1, y1 = box
        fg = ~bg[y0:y1, x0:x1]
        tm = _text_mask(texts, box, scale, (h, w))[y0:y1, x0:x1]
        px = rgb[y0:y1, x0:x1][fg & ~tm]
        if len(px) < MIN_LEAF * MIN_LEAF:
            px = rgb[y0:y1, x0:x1][fg]
            if len(px) < MIN_LEAF * MIN_LEAF:
                continue
        colour, share, at = _fill(px)
        flat = share >= FLAT_SHARE and float((at @ np.array([0.299, 0.587, 0.114])).std()) < FLAT_STD
        if flat:  # a flat ground under a big figure is an illustration, not a card
            other = fg & ~near(rgb[y0:y1, x0:x1], colour) & ~tm
            flat = other.mean() < 0.25
        if not flat and out["ground"] == "transparent" and _survives(fg) < STROKE_SURVIVE:
            continue  # lettering or a line sticker on a transparent sheet: thin strokes, no panel
        orig = _to_orig(box, scale)
        region = {"kind": "card" if flat else "picture", "box": orig, "ref": _ref(orig, w0),
                  "radius": round(radius(fg) * scale), "children": []}
        inner = _texts_in(texts, box, scale)
        if flat:
            region["fill"] = _rgb255(colour)
            region_tm = tm
            # inside the card only: its anti-aliased rim crosses every row and column,
            # which would leave no gutter to cut on and hide what the card holds
            rim = np.ones((h, w), bool)
            rim[y0:y1, x0:x1] = ~_rounded((x1 - x0, y1 - y0), radius(fg), inset=2)
            sub_bg = near(rgb, colour) | bg | rim
            for cb in xycut(sub_bg, box):
                if (cb[2] - cb[0]) * (cb[3] - cb[1]) > 0.9 * (x1 - x0) * (y1 - y0):
                    continue
                ctm = region_tm[cb[1] - y0:cb[3] - y0, cb[0] - x0:cb[2] - x0]
                cpx = rgb[cb[1]:cb[3], cb[0]:cb[2]]
                plate = cpx[~ctm]
                corig = _to_orig(cb, scale)
                hit = _texts_in(texts, cb, scale)
                if ctm.mean() > 0.5 or (hit and (len(plate) < 0.3 * ctm.size or _fill(plate)[1] < 0.8)):
                    continue  # words (or a fragment of them): placed from the reading below
                ccol, cshare, _ = _fill(plate if len(plate) else cpx.reshape(-1, 3))
                big = max(cb[2] - cb[0], cb[3] - cb[1]) > 20
                solid = near(cpx, ccol).mean() > 0.85  # a field fills its box; a logo's shape does not
                r = max(3, radius(fg))
                if not big and min(abs(cb[0] - x0), abs(x1 - cb[2])) < r and min(abs(cb[1] - y0), abs(y1 - cb[3])) < r:
                    continue  # the anti-aliased rim of a rounded corner, not an icon
                kind = "field" if cshare > 0.8 and big and (solid or hit) else "icon"
                child = {"kind": kind, "box": corig, "ref": _ref(corig, w0), "fill": _rgb255(ccol)}
                if hit:
                    child["text"] = " ".join(t["text"] for t in hit)
                region["children"].append(child)
            for t in inner:
                t["colour"] = _text_colour(rgb, t["box"], colour, scale)
        else:
            split = _seam(rgb, box)
            if split is not None:  # a compare card: one picture's Before and After either side of a divider
                region["split"] = split
            for t in inner:
                got = _pill(rgb, t["box"], scale)
                if got:
                    pb, pcol = got
                    porig = _to_orig(pb, scale)
                    region["children"].append({"kind": "pill", "box": porig, "ref": _ref(porig, w0),
                                               "fill": _rgb255(pcol), "text": t["text"]})
                    t["colour"] = _text_colour(rgb, t["box"], pcol, scale)
        for t in inner:
            t["region"] = len(out["regions"])
        out["regions"].append(region)
    for t in texts:
        t["ref"] = _ref(t["box"], w0)
    return out
