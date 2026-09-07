"""Pixel measurements of one corpus asset: the attribute fields that can be
read off the image itself, with no model in the loop.

`ground`, `layout`, `panel_count` and `before_after` are geometry and colour
statistics; the semantic fields (chrome, text, mockup, subject, finish) are
left blank for the labelling sheets to fill. Everything here works on a
256 px copy of the local file (a cached poster frame, for a video)."""

import re

import numpy as np
from PIL import Image

MEASURE_PX = 256
FIELDS = ("ground", "layout", "panel_count", "before_after")
# an alt text that says "before" is a before/after composite for free
BEFORE_RE = re.compile(r"\bbefore\b", re.I)

FLAT_GROUNDS = ("black", "white", "light-grey", "solid-colour", "gradient")
RING = 0.06        # border ring sampled for the ground colour, as a fraction of the short side
FLAT_SHARE = 0.85  # share of ring pixels near its median colour that still counts as one flat ground
ALPHA_RING = 0.5   # a ring this transparent means the ground comes from the page, not the file
PLANAR_RES = 0.03  # residual of the linear fit under which a non-flat ring is a gradient
PLANAR_RANGE = 0.06
TEXTURE = 0.008    # mean horizontal gradient above which a ring is photographic
RING_STD = 0.06    # ring luminance spread above which the picture fills the frame
SAT = 0.08         # channel spread above which a flat ground is a colour, not a grey
CHECKER_PERIODS = (6, 8, 10, 12, 16, 20, 24)
BG_TOL = 0.08      # chebyshev distance to the ground colour that still counts as background
GUTTER_FRAC = 0.97 # a row or column this much background is a gutter
MIN_GUTTER = 0.015 # gutters shorter than this fraction of the axis do not separate panels
SPLIT_BAND = (0.35, 0.65)
SEAM_STEP = 0.08   # per-row luminance step that counts as being on the divider
SEAM_HEIGHT = 0.8  # share of rows the divider has to cross to be a divider
SPLIT_CORR = 0.7   # row-profile correlation across a seam above which the halves are the same picture
CENTRED = (0.45, 0.55)  # a before/after divider sits in the middle; anything else is just two panels
LUMA = np.array([0.299, 0.587, 0.114], dtype=np.float32)


def pixels(path, max_px=MEASURE_PX):
    """(HxWx3 float array in 0..1 composited on white, HxW alpha or None).
    Cutouts are stored with transparency, so alpha has to be kept apart from
    the colour: a transparent border means the page supplies the ground."""
    with Image.open(path) as im:
        im = im.convert("RGBA")
        im.thumbnail((max_px, max_px))
        rgba = np.asarray(im, dtype=np.float32) / 255.0
    alpha = rgba[..., 3]
    rgb = rgba[..., :3] * alpha[..., None] + (1.0 - alpha[..., None])
    return rgb, (alpha if float(alpha.min()) < 1.0 else None)


def luma(a):
    return a @ LUMA


def ring(a, frac=RING):
    """The border pixels of an HxW or HxWx3 array, flattened: what the slot's
    ground looks like."""
    h, w = a.shape[:2]
    b = max(1, round(min(h, w) * frac))
    tail = a.shape[2:]
    sides = (a[:b], a[-b:], a[:, :b], a[:, -b:])
    return np.concatenate([side.reshape(-1, *tail) for side in sides])


def alternates(L):
    """True when a strip of luminance is two light greys alternating on one of
    the checkerboard periods."""
    h, w = L.shape
    for p in CHECKER_PERIODS:
        ny, nx = h // p, w // p
        if ny < 2 or nx < 3:
            continue
        blocks = L[:ny * p, :nx * p].reshape(ny, p, nx, p).mean(axis=(1, 3))
        yy, xx = np.mgrid[0:ny, 0:nx]
        even = (yy + xx) % 2 == 0
        hi, lo = blocks[even], blocks[~even]
        if (abs(hi.mean() - lo.mean()) > 0.015 and max(hi.std(), lo.std()) < 0.02
                and min(hi.mean(), lo.mean()) > 0.6):
            return True
    return False


def checkerboard(a):
    """A baked-in transparency checkerboard, tested on the top and left strips:
    whatever sits in the middle of the slot must not hide the pattern."""
    L = luma(a)
    h, w = L.shape
    strip = max(24, round(min(h, w) * 0.2))
    return alternates(L[:strip]) or alternates(L[:, :strip].T)


def planar(a):
    """True when the whole image is one smooth ramp (a gradient ground)."""
    L = luma(a)
    h, w = L.shape
    yy, xx = np.mgrid[0:h, 0:w]
    A = np.stack([np.ones(h * w, dtype=np.float32), xx.ravel() / w, yy.ravel() / h], axis=1)
    coef, *_ = np.linalg.lstsq(A, L.ravel(), rcond=None)
    fit = A @ coef
    return float(np.std(L.ravel() - fit)) < PLANAR_RES and abs(coef[1]) + abs(coef[2]) > PLANAR_RANGE


def flat_colour(a):
    """The ground colour when most of the ring is one colour (rounded corners
    and a pill or two do not stop it being flat), else None."""
    r = ring(a)
    med = np.median(r, axis=0)
    share = float((np.abs(r - med).max(axis=1) < BG_TOL).mean())
    return med if share >= FLAT_SHARE else None


def name_of(colour):
    """A flat ground colour -> its `ground` enum name."""
    lum = float(colour @ LUMA)
    if float(colour.max() - colour.min()) > SAT:
        return "solid-colour"
    return "black" if lum < 0.12 else "white" if lum >= 0.93 else "light-grey" if lum >= 0.78 else "solid-colour"


def ground_of(a, alpha=None):
    """One of the `ground` enum values, or None when the file cannot say
    (a cutout whose ground is the section behind it)."""
    if checkerboard(a):
        return "checkerboard"
    if alpha is not None and float(ring(alpha).mean()) < ALPHA_RING:
        return None
    colour = flat_colour(a)
    if colour is not None:
        return name_of(colour)
    if planar(a):
        return "gradient"
    L = luma(a)
    b = max(1, round(min(L.shape) * RING))
    edge = np.concatenate([np.abs(np.diff(L[:b], axis=1)).ravel(), np.abs(np.diff(L[-b:], axis=1)).ravel()])
    fills = float(edge.mean()) > TEXTURE or float(luma(ring(a)).std()) > RING_STD
    return "photo-full-bleed" if fills else "mixed"


def bands(profile, min_gutter=MIN_GUTTER):
    """Content runs along one axis, merging any separated by a gutter shorter
    than min_gutter of the axis: [(start, end), ...]."""
    n = len(profile)
    min_run = max(2, round(n * min_gutter))
    content = profile < GUTTER_FRAC
    out, i = [], 0
    while i < n:
        if not content[i]:
            i += 1
            continue
        j = i
        while j < n and content[j]:
            j += 1
        if out and i - out[-1][1] < min_run:
            out[-1] = (out[-1][0], j)
        else:
            out.append((i, j))
        i = j
    return out


def structure(a, bg):
    """(column bands, row bands, occupancy grid) of the panels sitting on a
    flat ground colour."""
    is_bg = np.abs(a - bg).max(axis=2) < BG_TOL
    cb, rb = bands(is_bg.mean(axis=0)), bands(is_bg.mean(axis=1))
    occ = np.array([[bool(is_bg[r0:r1, c0:c1].mean() < 0.9) for c0, c1 in cb] for r0, r1 in rb],
                   dtype=bool).reshape(len(rb), len(cb))
    return cb, rb, occ


def layout_of(cb, rb, occ):
    """(layout, panel_count), or (None, count) when the grid is not one of the
    named shapes and the sheet should ask."""
    n = int(occ.sum())
    nr, nc = occ.shape
    if n == 0:
        return None, 0
    if n == 1:
        return "single", 1
    widths = [c1 - c0 for c0, c1 in cb]
    even = max(widths) <= 1.25 * min(widths)
    if nr == 1 and nc == 2:
        return ("two-up" if even else "column-main"), n
    if nc == 1 and nr == 2:
        return "stacked", n
    if nc == 1 and nr >= 3:
        return "stacked", n
    if nr == 1 and nc >= 3:
        return "grid", n
    if nr >= 2 and nc >= 2:
        return ("grid" if even else "column-main"), n
    return None, n


def seam_of(a):
    """(x fraction, row-profile correlation) of a hard vertical divider near
    the middle, or None: a split panel, and with a high correlation the same
    picture twice. The divider has to run the full height, or every photo
    with a strong edge in the middle would read as a split."""
    L = luma(a)
    h, w = L.shape
    if w < 24:
        return None
    step = np.abs(np.diff(L, axis=1))
    dx = step.mean(axis=0)
    lo, hi = round(w * SPLIT_BAND[0]), round(w * SPLIT_BAND[1])
    if hi - lo < 3:
        return None
    k = lo + int(np.argmax(dx[lo:hi]))
    if dx[k] < max(0.05, 4 * float(np.median(dx))):
        return None
    if float((step[:, k] > SEAM_STEP).mean()) < SEAM_HEIGHT:
        return None
    left, right = L[:, :k], L[:, k + 1:]
    m = min(left.shape[1], right.shape[1])
    if m < 8:
        return None
    p, q = left[:, -m:].mean(axis=1), right[:, :m].mean(axis=1)
    corr = float(np.corrcoef(p, q)[0, 1]) if p.std() > 1e-4 and q.std() > 1e-4 else 0.0
    return round(k / w, 3), round(corr, 3)


def measure(path, alt=None):
    """The measurable attribute fields of one asset, plus a `seam` diagnostic.
    Fields the pixels do not settle are left out, not guessed."""
    a, alpha = pixels(path)
    g = ground_of(a, alpha)
    out = {"ground": g} if g else {}
    layout, panels = None, None
    if g in FLAT_GROUNDS:
        colour = flat_colour(a)
        bg = colour if colour is not None else ring(a).mean(axis=0)
        layout, panels = layout_of(*structure(a, bg))
    if g == "photo-full-bleed":
        layout, panels = "single", 1  # one picture filling the slot, by definition
    seam = seam_of(a)
    if seam and layout in (None, "single"):
        layout, panels = "split", 2
    if layout:
        out["layout"] = layout
    if panels is not None:
        out["panel_count"] = max(0, min(8, int(panels)))
    centred = bool(seam and CENTRED[0] <= seam[0] <= CENTRED[1] and seam[1] > SPLIT_CORR)
    before = bool(alt and BEFORE_RE.search(alt)) or centred
    out["before_after"] = before
    if seam:
        out["seam"] = list(seam)
    return out
