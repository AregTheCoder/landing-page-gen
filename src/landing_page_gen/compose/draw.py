"""Pillow primitives for lp-compose. Every function takes pixel coordinates
on the (supersampled) canvas; scaling from reference pixels is cli's job.
Shapes return the rect they covered so callers can report and test them."""

import math
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFont

from .families import CHECKER, MAGENTA

ASSETS = Path(__file__).parent / "assets"
WHITE = (255, 255, 255, 255)
STYLES = {  # pill fill, text colour
    "translucent": ((30, 30, 30, 150), WHITE),
    "solid-dark": ((28, 28, 28, 255), WHITE),
    "solid-light": ((255, 255, 255, 235), (20, 20, 20, 255)),
}
ANCHORS = {"center": (0.5, 0.5), "top": (0.5, 0), "bottom": (0.5, 1), "left": (0, 0.5), "right": (1, 0.5)}
# 24-unit grid; "lines" are polylines, "rounded" an outlined rounded square, "polygon" filled
ICONS = {
    "enlarge": {"rounded": (5, 5, 19, 19),
                "lines": [[(13.5, 10.5), (17.5, 6.5)], [(17.5, 10), (17.5, 6.5), (14, 6.5)],
                          [(10.5, 13.5), (6.5, 17.5)], [(6.5, 14), (6.5, 17.5), (10, 17.5)]]},
    "crop": {"lines": [[(7, 3), (7, 17), (21, 17)], [(3, 7), (17, 7), (17, 21)]]},
    "check": {"lines": [[(6, 12), (10.5, 16.5), (18.5, 8)]]},
    "sparkle": {"polygon": [(12, 2), (14.2, 9.8), (22, 12), (14.2, 14.2), (12, 22), (9.8, 14.2), (2, 12), (9.8, 9.8)]},
    "wheel": {"circles": [(9, 9.5, 5), (15, 9.5, 5), (12, 14.5, 5)]},  # three overlapping rings, the HSL mark
    "chevron": {"lines": [[(7, 14), (12, 9), (17, 14)]]},
    "close": {"lines": [[(7, 7), (17, 17)], [(17, 7), (7, 17)]]},  # selection-frame tool discs
    "rotate": {"arc": (5, 5, 19, 19, 40, 320), "lines": [[(19, 7), (19, 12), (14, 12)]]},
}
# the eight hue chips of the adjustment panel: red, orange, yellow, green, turquoise, blue, purple, pink
HUES = ((235, 64, 52), (245, 140, 30), (250, 215, 40), (70, 190, 90), (60, 205, 210), (70, 90, 235), (150, 70, 220), (235, 70, 170))
PANEL_FILL = (28, 28, 30, 238)


def font(px, weight=600):
    f = ImageFont.truetype(str(ASSETS / "Manrope.ttf"), max(1, round(px)))
    f.set_variation_by_axes([weight])
    return f


def ground(size, spec):
    """Solid, transparent (fill None) or two-colour gradient RGBA canvas."""
    w, h = size
    if "gradient" in spec:
        a, b = (tuple(c) + (255,) for c in spec["gradient"])
        ramp = Image.linear_gradient("L")  # black at the top, white at the bottom
        direction = spec.get("direction", "vertical")
        if direction == "horizontal":
            ramp = ramp.rotate(90)
        elif direction == "diagonal":
            ramp = ramp.resize((512, 512)).rotate(45).crop((128, 128, 384, 384))
        ramp = ramp.resize((w, h))
        return Image.composite(Image.new("RGBA", size, b), Image.new("RGBA", size, a), ramp)
    fill = spec.get("fill")
    return Image.new("RGBA", size, tuple(fill) + (255,) if fill else (0, 0, 0, 0))


def rounded_mask(size, radius):
    m = Image.new("L", size, 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, size[0] - 1, size[1] - 1), radius=radius, fill=255)
    return m


def parse_anchor(anchor):
    if anchor in ANCHORS:
        return ANCHORS[anchor]
    ax, ay = str(anchor).split(",")
    return float(ax), float(ay)


def fit(im, size, mode="cover", anchor="center"):
    """cover: scale to fill and crop, the anchor picks the part that survives
    (0,0 top-left .. 1,1 bottom-right); contain: scale to fit inside, centred
    on transparency (for cutouts, so nothing of the subject is lost)."""
    w, h = size
    im = im.convert("RGBA")
    iw, ih = im.size
    if mode == "contain":
        s = min(w / iw, h / ih)
        r = im.resize((max(1, round(iw * s)), max(1, round(ih * s))), Image.LANCZOS)
        out = Image.new("RGBA", size, (0, 0, 0, 0))
        out.paste(r, ((w - r.width) // 2, (h - r.height) // 2))
        return out
    s = max(w / iw, h / ih)
    r = im.resize((max(w, round(iw * s)), max(h, round(ih * s))), Image.LANCZOS)
    ax, ay = parse_anchor(anchor)
    x, y = round((r.width - w) * ax), round((r.height - h) * ay)
    return r.crop((x, y, x + w, y + h))


def palette(im, n):
    """The `n` colours a swatch should show for an image: its opaque pixels
    quantised, each colour scored by its share times its saturation (a small
    vivid accent beats a large dull wall), near-duplicates dropped, returned
    dark to light like the corpus swatch stripes. Fewer than `n` when the image
    has fewer distinct colours."""
    im = im.convert("RGBA")
    im.thumbnail((160, 160))
    data = im.get_flattened_data() if hasattr(im, "get_flattened_data") else im.getdata()
    px = [p[:3] for p in data if p[3] >= 128] or [(128, 128, 128)]
    strip = Image.new("RGB", (len(px), 1))
    strip.putdata(px)
    q = strip.quantize(16, method=Image.Quantize.MEDIANCUT)
    pal = q.getpalette()[:48]
    counts = sorted(q.getcolors(), reverse=True)

    def sat(c):
        return (max(c) - min(c)) / 255

    scored = sorted(((cnt * (0.25 + sat(c)), c) for cnt, i in counts for c in [tuple(pal[3 * i:3 * i + 3])]),
                    reverse=True)
    picked = []
    for _, c in scored:
        if all(sum((a - b) ** 2 for a, b in zip(c, p)) > 45 ** 2 for p in picked):
            picked.append(c)
        if len(picked) == n:
            break
    return sorted(picked, key=lambda c: 0.299 * c[0] + 0.587 * c[1] + 0.114 * c[2])


def checkerboard(size, cell, tones=CHECKER):
    a, b = (tuple(t) + (255,) * (4 - len(t)) for t in tones)  # RGB or RGBA; the light editor pair is translucent
    im = Image.new("RGBA", size, a)
    d = ImageDraw.Draw(im)
    for y in range(0, size[1], cell):
        for x in range(0, size[0], cell):
            if ((x // cell) + (y // cell)) % 2:
                d.rectangle((x, y, x + cell - 1, y + cell - 1), fill=b)
    return im


def checker_tile(canvas, rect, radius, tones, cell):
    """A rounded checkerboard tile: the transparency an editor shows behind a
    cut-out element."""
    x0, y0, x1, y1 = (round(v) for v in rect)
    layer = checkerboard((x1 - x0, y1 - y0), cell, tones)
    layer.putalpha(ImageChops.multiply(layer.getchannel("A"), rounded_mask(layer.size, radius)))
    canvas.alpha_composite(layer, (x0, y0))
    return (x0, y0, x1, y1)


def panel(canvas, im, rect, radius, mode="cover", anchor="center", under=None, cell=100):
    x0, y0, x1, y1 = rect
    size = (x1 - x0, y1 - y0)
    layer = Image.new("RGBA", size, (0, 0, 0, 0))
    if under == "checkerboard":
        layer.alpha_composite(checkerboard(size, cell))
    layer.alpha_composite(fit(im, size, mode, anchor))
    layer.putalpha(ImageChops.multiply(layer.getchannel("A"), rounded_mask(size, radius)))
    canvas.alpha_composite(layer, (x0, y0))
    return rect


def card(canvas, rect, fill, radius):
    ImageDraw.Draw(canvas).rounded_rectangle(rect, radius=radius, fill=tuple(fill) + (255,))
    return rect


def dim(canvas, rect, radius, amount):
    """Darken a panel region (crop-frame dims the source under the brackets)."""
    x0, y0, x1, y1 = (round(v) for v in rect)
    layer = Image.new("RGBA", (x1 - x0, y1 - y0), (0, 0, 0, 0))
    ImageDraw.Draw(layer).rounded_rectangle((0, 0, x1 - x0 - 1, y1 - y0 - 1), radius=radius,
                                            fill=(0, 0, 0, round(255 * amount)))
    canvas.alpha_composite(layer, (x0, y0))
    return rect


def icon(canvas, rect, name, colour=WHITE):
    """A line icon from the 24-unit grid, centred in rect, sized to its
    shorter side; strokes are 2 units with round caps and joints."""
    spec = ICONS[name]
    x0, y0, x1, y1 = rect
    s = min(x1 - x0, y1 - y0)
    u = s / 24
    ox, oy = x0 + (x1 - x0 - s) / 2, y0 + (y1 - y0 - s) / 2
    pt = lambda p: (ox + p[0] * u, oy + p[1] * u)  # noqa: E731
    d = ImageDraw.Draw(canvas)
    stroke = max(1, round(2 * u))
    if "rounded" in spec:
        a, b, c, e = spec["rounded"]
        d.rounded_rectangle((*pt((a, b)), *pt((c, e))), radius=3 * u, outline=colour, width=stroke)
    if "arc" in spec:
        a, b, c, e, start, end = spec["arc"]
        d.arc((*pt((a, b)), *pt((c, e))), start, end, fill=colour, width=stroke)
    for line in spec.get("lines", []):
        pts = [pt(p) for p in line]
        d.line(pts, fill=colour, width=stroke, joint="curve")
        for x, y in (pts[0], pts[-1]):
            d.ellipse((x - stroke / 2, y - stroke / 2, x + stroke / 2, y + stroke / 2), fill=colour)
    if "polygon" in spec:
        d.polygon([pt(p) for p in spec["polygon"]], fill=colour)
    for cx, cy, r in spec.get("circles", []):
        d.ellipse((*pt((cx - r, cy - r)), *pt((cx + r, cy + r))), outline=colour, width=stroke)
    return rect


def tile(canvas, rect, name, radius, fill=(0, 0, 0, 255)):
    x0, y0, x1, y1 = rect
    ImageDraw.Draw(canvas).rounded_rectangle(rect, radius=radius, fill=fill)
    if name:  # a colour-swatch tile (no glyph) when name is falsy
        s = round(min(x1 - x0, y1 - y0) * 0.4)
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        icon(canvas, (cx - s / 2, cy - s / 2, cx + s / 2, cy + s / 2), name)
    return rect


def swatch_stripe(canvas, rect, colours, radius, direction="column", gap=0):
    """A rounded tile split into len(colours) equal cells of solid colour; only
    the OUTER corners are rounded, interior edges butt flush. `direction`
    stacks the cells down a column (modal) or along a row; `gap` (px) inserts
    transparent gutters, else cells touch. Generalises tile(name=None), the
    single flat swatch, to N palette cells."""
    x0, y0, x1, y1 = (round(v) for v in rect)
    n = max(1, len(colours))
    W, H = x1 - x0, y1 - y0
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    horizontal = direction == "row"
    span = W if horizontal else H
    step = (span - gap * (n - 1)) / n
    for i, c in enumerate(colours):
        off = i * (step + gap)
        cell = (off, 0, off + step, H) if horizontal else (0, off, W, off + step)
        d.rectangle([round(v) for v in cell], fill=tuple(c) + (255,))
    layer.putalpha(ImageChops.multiply(layer.getchannel("A"), rounded_mask((W, H), radius)))
    canvas.alpha_composite(layer, (x0, y0))
    return (x0, y0, x1, y1)


def box_text(canvas, rect, text, fill, colour, radius, fnt):
    """Rounded box filling rect with the text centred; the base of pills,
    labels and buttons. Alpha-composited so translucent fills work."""
    x0, y0, x1, y1 = (round(v) for v in rect)
    layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    d.rounded_rectangle((x0, y0, x1, y1), radius=radius, fill=fill)
    if text:
        d.text(((x0 + x1) / 2, (y0 + y1) / 2), text, font=fnt, fill=colour, anchor="mm")
    canvas.alpha_composite(layer)
    return (x0, y0, x1, y1)


def wrapped_text(canvas, rect, text, colour, fnt, leading=1.3):
    """Text set left-aligned from the top of rect, wrapped on words to its
    width; a last line that would overflow the height ends in an ellipsis."""
    x0, y0, x1, y1 = (round(v) for v in rect)
    d = ImageDraw.Draw(canvas)
    lines, line = [], ""
    for word in str(text).split():
        trial = f"{line} {word}".strip()
        if line and d.textlength(trial, font=fnt) > x1 - x0:
            lines.append(line)
            line = word
        else:
            line = trial
    if line:
        lines.append(line)
    step = fnt.size * leading
    fit = max(1, int((y1 - y0) // step))
    if len(lines) > fit:
        lines = lines[:fit]
        while lines[-1] and d.textlength(lines[-1] + "…", font=fnt) > x1 - x0:
            lines[-1] = lines[-1].rsplit(" ", 1)[0] if " " in lines[-1] else lines[-1][:-1]
        lines[-1] += "…"
    for i, ln in enumerate(lines):
        d.text((x0, y0 + i * step), ln, font=fnt, fill=colour)
    return (x0, y0, x1, y1)


def prompt_card(canvas, rect, text, fnt, radius, pad, fill=(30, 30, 32, 255), leading=1.28, max_lines=None):
    """The prompt card of the model pages (ai-models--gpt-image-2-5-sunburst
    S01, S03, S04, S07): a dark rounded card, the prompt wrapped from its top
    left, the first third of the lines white and the rest fading to grey, the
    last line cut with an ellipsis when the prompt runs past the card."""
    x0, y0, x1, y1 = (round(v) for v in rect)
    card(canvas, (x0, y0, x1, y1), fill[:3], radius)
    d = ImageDraw.Draw(canvas)
    width, height = x1 - x0 - 2 * pad, y1 - y0 - 2 * pad
    lines, line = [], ""
    for word in str(text).split():
        trial = f"{line} {word}".strip()
        if line and d.textlength(trial, font=fnt) > width:
            lines.append(line)
            line = word
        else:
            line = trial
    if line:
        lines.append(line)
    step = fnt.size * leading
    fit = max(1, int((height + step - fnt.size) // step))
    fit = min(fit, max_lines) if max_lines else fit
    if len(lines) > fit:
        lines = lines[:fit]
        while lines[-1] and d.textlength(lines[-1] + "...", font=fnt) > width:
            lines[-1] = lines[-1].rsplit(" ", 1)[0] if " " in lines[-1] else lines[-1][:-1]
        lines[-1] += "..."
    bright = max(1, -(-len(lines) // 3))
    for i, ln in enumerate(lines):
        k = 0 if i < bright else (i - bright + 1) / max(1, len(lines) - bright)
        v = round(250 - 135 * k)
        d.text((x0 + pad, y0 + pad + i * step), ln, font=fnt, fill=(v, v, v + 2, 255))
    return (x0, y0, x1, y1)


def mark_tile(canvas, rect, mark, radius, fill=(30, 30, 32, 255), scale=0.46):
    """A dark tile carrying a maker's mark (white on transparent), centred and
    sized to `scale` of the tile's shorter side; a lettered disc when the mark
    is unknown is the caller's job (it passes None and gets an empty tile)."""
    x0, y0, x1, y1 = (round(v) for v in rect)
    card(canvas, (x0, y0, x1, y1), fill[:3], radius)
    if mark is not None:
        side = round(min(x1 - x0, y1 - y0) * scale)
        m = mark.resize((side, side), Image.LANCZOS)
        canvas.alpha_composite(m, ((x0 + x1 - side) // 2, (y0 + y1 - side) // 2))
    return (x0, y0, x1, y1)


def chip_bar(canvas, rect, items, fnt, radius, group=True, marks=None):
    """A row of settings chips (the generator toolbar of S05, the resolution and
    ratio bar of S06): `items` are {text, active, accent, caret, mark}; with
    `group` the row sits on one dark rounded bar and only the active chip is
    lifted, else every chip is its own rounded pill. Chip widths follow their
    text; the row is spread across the rect."""
    x0, y0, x1, y1 = (round(v) for v in rect)
    h = y1 - y0
    d = ImageDraw.Draw(canvas)
    if group:
        card(canvas, (x0, y0, x1, y1), (30, 30, 32), radius)
    marks = marks or {}
    padx, gap = round(h * (0.2 if group else 0.34)), round(h * (0.08 if group else 0.22))
    widths = []
    for it in items:
        w = d.textlength(it.get("text", ""), font=fnt) + 2 * padx
        if it.get("caret"):
            w += h * 0.42
        if it.get("mark"):
            w += h * 0.58
        widths.append(w)
    spare = (x1 - x0) - sum(widths) - gap * (len(items) + 1)
    extra = spare / len(items) if group and spare > 0 else 0
    cx = x0 + gap if group else x0
    ih = h * (0.66 if group else 1.0)
    iy0 = y0 + (h - ih) / 2
    for it, base in zip(items, widths):
        w = base + extra
        fill = None
        if it.get("accent"):
            fill = (62, 32, 96, 255)
        elif it.get("active"):
            fill = (62, 62, 66, 255)
        elif not group:
            fill = (40, 40, 44, 255)
        if fill:
            d.rounded_rectangle((cx, iy0, cx + w, iy0 + ih), radius=radius * 0.7, fill=fill)
        ink = (205, 170, 255, 255) if it.get("accent") else ((245, 245, 247, 255) if it.get("active") else (190, 190, 196, 255))
        tx = cx + (w - (base - 2 * padx)) / 2 if group else cx + padx
        cy = iy0 + ih / 2
        key = it.get("text") if it.get("mark") is True else it.get("mark")
        mark = marks.get(key) if it.get("mark") else None
        if it.get("mark"):
            ms = round(ih * 0.5)
            d.rounded_rectangle((tx, cy - ms / 2, tx + ms, cy + ms / 2), radius=ms * 0.25, fill=(58, 170, 120, 255))
            if mark is not None:
                g = mark.resize((round(ms * 0.7), round(ms * 0.7)), Image.LANCZOS)
                canvas.alpha_composite(g, (round(tx + ms * 0.15), round(cy - ms * 0.35)))
                d = ImageDraw.Draw(canvas)
            tx += h * 0.58
        d.text((tx, cy), it.get("text", ""), font=fnt, fill=ink, anchor="lm")
        if it.get("caret"):
            cw = h * 0.16
            ex = tx + d.textlength(it.get("text", ""), font=fnt) + h * 0.2
            d.line([(ex, cy - cw * 0.35), (ex + cw / 2, cy + cw * 0.35), (ex + cw, cy - cw * 0.35)], fill=ink, width=max(1, round(h * 0.03)))
        cx += w + gap
    return (x0, y0, x1, y1)


def pill_in(canvas, rect, text, style, fnt):
    fill, colour = STYLES[style]
    return box_text(canvas, rect, text, fill, colour, (rect[3] - rect[1]) / 2, fnt)


def pill_at(canvas, panel_rect, corner, text, style, fnt, pad, inset):
    """A pill sized to its text, `inset` from the named corner of a panel
    (tl, tr, bl, br)."""
    l, t, r, b = fnt.getbbox(text)
    w, h = r - l + 2 * pad[0], (b - t) + 2 * pad[1]
    px0, py0, px1, py1 = panel_rect
    x0 = px0 + inset if corner[1] == "l" else px1 - inset - w
    y0 = py0 + inset if corner[0] == "t" else py1 - inset - h
    fill, colour = STYLES[style]
    return box_text(canvas, (x0, y0, x0 + w, y0 + h), text, fill, colour, h / 2, fnt)


def type_tile(canvas, rect, radius, fill, colour, fonts, text="Aa"):
    """A rounded tile with two type specimens side by side (the left in
    fonts[0], the right in fonts[1]): an editor's font pairing."""
    x0, y0, x1, y1 = (round(v) for v in rect)
    d = ImageDraw.Draw(canvas)
    d.rounded_rectangle((x0, y0, x1, y1), radius=radius, fill=fill)
    for fx, fnt in zip((0.31, 0.71), fonts):  # the specimens' centres, measured on the corpus tiles
        d.text((x0 + (x1 - x0) * fx, (y0 + y1) / 2), text, font=fnt, fill=colour, anchor="mm")
    return (x0, y0, x1, y1)


def label(canvas, rect, text, radius, fnt, fill=(28, 28, 28, 255)):
    return box_text(canvas, rect, text, fill, WHITE, radius, fnt)


def brackets(canvas, rect, text, fnt, stroke, colour=WHITE, grid=False):
    """Four L corners plus a tick at each edge midpoint, the label centred
    below; the crop-selection mark of the crop-frame family. `grid` adds the
    interior rule-of-thirds lines (the crop-grid variant)."""
    x0, y0, x1, y1 = rect
    arm = min(x1 - x0, y1 - y0) * 0.14
    d = ImageDraw.Draw(canvas)
    for cx, sx in ((x0, 1), (x1, -1)):
        for cy, sy in ((y0, 1), (y1, -1)):
            d.line([(cx, cy + sy * arm), (cx, cy), (cx + sx * arm, cy)], fill=colour, width=stroke, joint="curve")
    mx, my, half = (x0 + x1) / 2, (y0 + y1) / 2, arm * 0.4
    for a, b in (((mx - half, y0), (mx + half, y0)), ((mx - half, y1), (mx + half, y1)),
                 ((x0, my - half), (x0, my + half)), ((x1, my - half), (x1, my + half))):
        d.line([a, b], fill=colour, width=stroke)
    if text:
        d.text((mx, y1 + arm * 1.2), text, font=fnt, fill=colour, anchor="ma")
    if grid:
        thin = max(1, round(stroke * 0.6))
        for f in (1 / 3, 2 / 3):
            gx, gy = x0 + (x1 - x0) * f, y0 + (y1 - y0) * f
            d.line([(gx, y0), (gx, y1)], fill=colour, width=thin)
            d.line([(x0, gy), (x1, gy)], fill=colour, width=thin)
    return rect


def selection_frame(canvas, rect, colour=WHITE, stroke=6, handle=20, dashed=False,
                    grid=False, handles=("top", "bottom", "left", "right"), tools=()):
    """The editor transform/selection box: a thin, square-cornered rectangle over
    a subject with filled disc handles at the named positions (edge midpoints
    top/bottom/left/right and/or corners tl/tr/bl/br), an optional 3x3
    rule-of-thirds grid inside, and optional round tool discs (an icon in a
    filled disc of the opposite tone) floating just outside named corners.
    Solid by default; `dashed` gives the extend/crop guide. `colour` is white
    over dark/photographic grounds, dark over light ones. Editor furniture: it
    marks a selection and carries no text."""
    x0, y0, x1, y1 = (round(v) for v in rect)
    layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    edges = [((x0, y0), (x1, y0)), ((x1, y0), (x1, y1)), ((x1, y1), (x0, y1)), ((x0, y1), (x0, y0))]
    if dashed:
        dash = max(2, stroke * 3)
        for (ax, ay), (bx, by) in edges:
            n = max(1, round(math.hypot(bx - ax, by - ay) / (dash * 2)))
            for i in range(n):
                t0, t1 = i / n, (i + 0.5) / n
                d.line([(ax + (bx - ax) * t0, ay + (by - ay) * t0),
                        (ax + (bx - ax) * t1, ay + (by - ay) * t1)], fill=colour, width=stroke)
    else:
        for a, b in edges:
            d.line([a, b], fill=colour, width=stroke)
    if grid:
        gw = max(1, round(stroke * 0.6))
        for k in (1 / 3, 2 / 3):
            d.line([(x0 + (x1 - x0) * k, y0), (x0 + (x1 - x0) * k, y1)], fill=colour, width=gw)
            d.line([(x0, y0 + (y1 - y0) * k), (x1, y0 + (y1 - y0) * k)], fill=colour, width=gw)
    pos = {"top": ((x0 + x1) / 2, y0), "bottom": ((x0 + x1) / 2, y1),
           "left": (x0, (y0 + y1) / 2), "right": (x1, (y0 + y1) / 2),
           "tl": (x0, y0), "tr": (x1, y0), "bl": (x0, y1), "br": (x1, y1)}
    for name in handles:
        cx, cy = pos[name]
        d.ellipse((cx - handle, cy - handle, cx + handle, cy + handle), fill=colour)
    canvas.alpha_composite(layer)
    if tools:  # tool discs, opposite tone, just outside the corner
        tdia = handle * 4
        opp = (24, 24, 26, 255) if tuple(colour) == WHITE else WHITE
        for corner, name in tools:
            cx, cy = pos[corner]
            off = tdia * 0.75
            cx += -off if corner[1] == "l" else off
            cy += -off if corner[0] == "t" else off
            disc = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
            ImageDraw.Draw(disc).ellipse((cx - tdia / 2, cy - tdia / 2, cx + tdia / 2, cy + tdia / 2), fill=colour)
            ins = tdia * 0.28
            icon(disc, (cx - tdia / 2 + ins, cy - tdia / 2 + ins, cx + tdia / 2 - ins, cy + tdia / 2 - ins), name, opp)
            canvas.alpha_composite(disc)
    return (x0, y0, x1, y1)


def disc_icon(canvas, rect, name, fill=(0, 0, 0)):
    """A filled circle carrying a white line icon (the crop-tool badge)."""
    x0, y0, x1, y1 = (round(v) for v in rect)
    layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    ImageDraw.Draw(layer).ellipse((x0, y0, x1, y1), fill=tuple(fill) + (255,))
    inset = (x1 - x0) * 0.30
    icon(layer, (x0 + inset, y0 + inset, x1 - inset, y1 - inset), name)
    canvas.alpha_composite(layer)
    return (x0, y0, x1, y1)


def badge(canvas, rect, radius):
    d = ImageDraw.Draw(canvas)
    d.rounded_rectangle(rect, radius=radius, fill=MAGENTA + (255,))
    x0, y0, x1, y1 = rect
    inset = (x1 - x0) * 0.22
    icon(canvas, (x0 + inset, y0 + inset, x1 - inset, y1 - inset), "check")
    return rect


def round_badge(canvas, rect, text, fill, colour, fnt):
    """A filled circle with centred text — a VS mark on a seam, or the disc a
    play button sits in. Alpha-composited so it reads over either panel."""
    x0, y0, x1, y1 = (round(v) for v in rect)
    layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    d.ellipse((x0, y0, x1, y1), fill=fill)
    if text:
        d.text(((x0 + x1) / 2, (y0 + y1) / 2), text, font=fnt, fill=colour, anchor="mm")
    canvas.alpha_composite(layer)
    return (x0, y0, x1, y1)


def profile_card(canvas, rect, fill, radius, image=None, name="", caption="", fonts=None):
    """A mock social/profile card: a rounded card with a round avatar and a
    name beside it, an image well, and blank caption bars — all placeholder
    chrome (never a real network's layout, name or logo). With `image` (the
    photo the card is built from) the well shows it and the avatar is its
    centre crop, so the card reads as that photo in use."""
    x0, y0, x1, y1 = (round(v) for v in rect)
    card(canvas, rect, fill, radius)
    layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    w, h = x1 - x0, y1 - y0
    pad = round(w * 0.10)
    av = round(w * 0.26)
    disc, bar, lite = (74, 74, 80, 255), (60, 60, 66, 255), (96, 96, 104, 255)
    d.ellipse((x0 + pad, y0 + pad, x0 + pad + av, y0 + pad + av), fill=disc)  # avatar
    nx = x0 + pad + av + round(w * 0.06)
    if name and fonts:
        d.text((nx, y0 + pad + av / 2), name, font=fonts[0], fill=WHITE, anchor="lm")
    else:
        d.rounded_rectangle((nx, y0 + pad + round(av * 0.22), x1 - pad, y0 + pad + round(av * 0.42)), radius=12, fill=lite)  # name
        d.rounded_rectangle((nx, y0 + pad + round(av * 0.55), x0 + pad + av + round(w * 0.30), y0 + pad + round(av * 0.72)), radius=12, fill=bar)  # handle
    well_top, well_bot = y0 + pad + av + round(h * 0.05), y0 + round(h * 0.62)
    d.rounded_rectangle((x0 + pad, well_top, x1 - pad, well_bot), radius=round(w * 0.04), fill=bar)  # image well
    cy, bh, gap = well_bot + round(h * 0.05), round(h * 0.04), round(h * 0.03)
    if not (caption and fonts):
        for i, frac in enumerate((1.0, 0.85, 0.5)):  # caption bars
            yy = cy + i * (bh + gap)
            d.rounded_rectangle((x0 + pad, yy, x0 + pad + round((w - 2 * pad) * frac), yy + bh), radius=round(bh * 0.5), fill=lite if i == 0 else bar)
    canvas.alpha_composite(layer)
    if caption and fonts:
        wrapped_text(canvas, (x0 + pad, cy, x1 - pad, y1 - pad), caption, (225, 225, 230, 255), fonts[1])
    if image is not None:
        panel(canvas, image, (x0 + pad, well_top, x1 - pad, well_bot), round(w * 0.04))
        face = fit(image, (av, av)).convert("RGBA")
        mask = Image.new("L", (av, av), 0)
        ImageDraw.Draw(mask).ellipse((0, 0, av - 1, av - 1), fill=255)
        face.putalpha(ImageChops.multiply(face.getchannel("A"), mask))
        canvas.alpha_composite(face, (x0 + pad, y0 + pad))
    return (x0, y0, x1, y1)


def headline(canvas, rect, text, px, stroke, radius, colour=WHITE):
    """The template card's headline area: a thin rounded outline with the
    text in caps sized to fit, or two blank bars when there is no text."""
    x0, y0, x1, y1 = rect
    w, h = (x1 - x0), (y1 - y0)
    d = ImageDraw.Draw(canvas)
    d.rounded_rectangle(rect, radius=radius, outline=colour, width=stroke)
    if text:
        words = text.upper().split()
        lines = [" ".join(words)] if len(words) < 3 else [" ".join(words[: len(words) // 2]), " ".join(words[len(words) // 2:])]
        body = "\n".join(lines)
        fnt = font(px, 800)
        while px > 8 and (d.multiline_textbbox((0, 0), body, font=fnt)[2] > w * 0.86
                          or d.multiline_textbbox((0, 0), body, font=fnt)[3] > h * 0.8):
            px *= 0.92
            fnt = font(px, 800)
        d.multiline_text(((x0 + x1) / 2, (y0 + y1) / 2), body, font=fnt, fill=colour, anchor="mm", align="center")
    else:
        for k in (0.34, 0.56):
            d.rounded_rectangle((x0 + w * 0.2, y0 + h * k, x1 - w * 0.2, y0 + h * (k + 0.12)), radius=stroke, fill=colour)
    return rect


def adjust_panel(canvas, rect, title, chips, active, sliders, fnt_title, fnt_label, radius):
    """The tool's dark adjustment panel laid over a photo: a header row (tool
    mark, title, a small teal badge, a chevron), a row of hue chips with the
    active one ringed, then one row per slider (label, track, knob, value chip).
    `sliders` is a list of [label, value] with value in -100..100."""
    x0, y0, x1, y1 = (round(v) for v in rect)
    w = x1 - x0
    pad = w * 0.05
    hh = w * 0.1  # header row; rows are sized from the width so the panel can grow to its content
    dia = min((w - 2 * pad) / (chips * 1.25), w * 0.07) if chips else 0
    need = 2 * pad + hh + (dia + pad if chips else 0) + len(sliders) * w * 0.085
    y1 = max(y1, round(y0 + need))
    h = y1 - y0
    layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    d.rounded_rectangle((x0, y0, x1, y1), radius=radius, fill=PANEL_FILL)
    # header
    mark = hh * 0.7
    icon(layer, (x0 + pad, y0 + pad, x0 + pad + mark, y0 + pad + mark), "wheel")
    tx = x0 + pad + mark * 1.4
    d.text((tx, y0 + pad + mark / 2), title, font=fnt_title, fill=WHITE, anchor="lm")
    tw = d.textlength(title, font=fnt_title) if title else 0
    # teal badge: a small circle with a white inner mark (hsl-color zoom), not a bar
    bd = mark * 0.5
    bcx, bcy = tx + tw + mark * 0.55, y0 + pad + mark / 2
    d.ellipse((bcx - bd / 2, bcy - bd / 2, bcx + bd / 2, bcy + bd / 2), fill=(60, 200, 180, 255))
    d.ellipse((bcx - bd * 0.12, bcy - bd * 0.12, bcx + bd * 0.12, bcy + bd * 0.12), fill=WHITE)
    icon(layer, (x1 - pad - mark, y0 + pad, x1 - pad, y0 + pad + mark), "chevron", (200, 200, 200, 255))
    # hairline separator under the header
    sep_y = y0 + pad + hh - pad * 0.35
    d.line([(x0 + pad, sep_y), (x1 - pad, sep_y)], fill=(60, 60, 64, 255), width=max(1, round(h * 0.004)))
    # chips: rounded squares (squircles) with a WHITE ring on the active one
    top = y0 + pad + hh
    if chips:
        step = (w - 2 * pad - dia) / max(1, chips - 1)
        for i in range(chips):
            cx = x0 + pad + i * step
            d.rounded_rectangle((cx, top, cx + dia, top + dia), radius=dia * 0.3, fill=HUES[i % len(HUES)] + (255,))
            if i == active:
                ring = dia * 0.14
                d.rounded_rectangle((cx - ring, top - ring, cx + dia + ring, top + dia + ring),
                                    radius=dia * 0.42, outline=WHITE, width=max(1, round(ring * 0.6)))
        top += dia + pad
    # sliders
    if sliders:
        rh = (y1 - pad - top) / len(sliders)
        for i, (label, value) in enumerate(sliders):
            cy = top + rh * (i + 0.5)
            d.text((x0 + pad, cy), str(label), font=fnt_label, fill=(170, 170, 175, 255), anchor="lm")
            tx0, tx1 = x0 + w * 0.36, x0 + w * 0.76
            d.line([(tx0, cy), (tx1, cy)], fill=(95, 95, 100, 255), width=max(1, round(h * 0.012)))
            knob = rh * 0.22
            kx = tx0 + (tx1 - tx0) * (0.5 + max(-100, min(100, float(value))) / 200)
            d.ellipse((kx - knob, cy - knob, kx + knob, cy + knob), fill=WHITE)
            vw, vh = w * 0.13, rh * 0.62
            d.rounded_rectangle((x1 - pad - vw, cy - vh / 2, x1 - pad, cy + vh / 2), radius=vh * 0.25, fill=(48, 48, 52, 255))
            d.text((x1 - pad - vw / 2, cy), str(value), font=fnt_label, fill=WHITE, anchor="mm")
    canvas.alpha_composite(layer)
    return (x0, y0, x1, y1)


def tool_pill(canvas, rect, text, icon_name, fnt):
    """A white round badge carrying the tool mark, with a white label pill and
    a small pointer under it: the hero's tool call-out (hsl-color S01)."""
    x0, y0, x1, y1 = (round(v) for v in rect)
    w, h = x1 - x0, y1 - y0
    layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    dia = min(w * 0.59, h * 0.55)   # badge ~0.59 of the block width (85708ef3)
    bx = x0 + (w - dia) / 2
    d.ellipse((bx, y0, bx + dia, y0 + dia), fill=WHITE)
    inset = dia * 0.28
    icon(layer, (bx + inset, y0 + inset, bx + dia - inset, y0 + dia - inset), icon_name, (20, 20, 20, 255))
    ph = h * 0.28
    py0 = max(y1 - ph, y0 + dia + h * 0.09)   # pill sits just below the badge, ~0.09h gap
    d.rounded_rectangle((x0, py0, x1, y1), radius=ph * 0.3, fill=WHITE)
    tip = ph * 0.3
    mx = (x0 + x1) / 2
    d.polygon([(mx - tip, py0 + 1), (mx + tip, py0 + 1), (mx, py0 - tip)], fill=WHITE)
    d.text((mx, py0 + ph / 2), text, font=fnt, fill=(20, 20, 20, 255), anchor="mm")
    canvas.alpha_composite(layer)
    return (x0, y0, x1, y1)


def list_panel(canvas, rect, rows, active, text, fnt, radius, others=(), marks=None):
    """The model-picker list card: a dark card with one row per model, each a
    maker mark (or a disc with the name's initial) and the model's name; the
    active row, the page's own model, is lighter and carries a white check.
    `others` names the other rows in order (the picker's same-kind siblings);
    `marks` maps a name to its white mark. A row with no name draws a blank
    grey bar, which `plan.blank_chrome` refuses before a run."""
    x0, y0, x1, y1 = (round(v) for v in rect)
    w, h = x1 - x0, y1 - y0
    layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    d.rounded_rectangle((x0, y0, x1, y1), radius=radius, fill=(30, 30, 32, 255))
    rh = h / max(1, rows)
    pad = w * 0.07
    names = iter(others or ())
    marks = marks or {}
    for i in range(rows):
        ry0, ry1 = y0 + rh * i, y0 + rh * (i + 1)
        cy = (ry0 + ry1) / 2
        is_active = i == active
        name = text if is_active else next(names, "")
        ink = WHITE if is_active else (205, 205, 210, 255)
        if is_active:
            d.rounded_rectangle((x0 + pad * 0.4, ry0 + rh * 0.08, x1 - pad * 0.4, ry1 - rh * 0.08), radius=radius * 0.5, fill=(54, 54, 58, 255))
        dia = rh * 0.38
        mx0 = round(x0 + pad)
        mark = marks.get(name) if name else None
        if mark is not None:
            m = mark.resize((round(dia * 1.15), round(dia * 1.15)), Image.LANCZOS)
            if not is_active:
                m.putalpha(m.getchannel("A").point(lambda a: round(a * 0.8)))
            layer.alpha_composite(m, (mx0, round(cy - m.height / 2)))
        else:
            d.ellipse((mx0, cy - dia / 2, mx0 + dia, cy + dia / 2), fill=WHITE if is_active else (120, 120, 126, 255))
            if name:
                d.text((mx0 + dia / 2, cy), name[0].upper(), font=font(dia * 0.62, 800), fill=(30, 30, 32, 255), anchor="mm")
        bx0 = x0 + pad + dia * 1.6
        if name:
            d.text((bx0, cy), name, font=fnt, fill=ink, anchor="lm")
        else:
            bh = rh * 0.18
            bw = (w - pad * 2 - dia * 1.6) * (0.55 if not is_active else 0.5)
            d.rounded_rectangle((bx0, cy - bh / 2, bx0 + bw, cy + bh / 2), radius=bh / 2,
                                fill=WHITE if is_active else (96, 96, 102, 255))
        if is_active:
            ck = rh * 0.42
            icon(layer, (x1 - pad - ck, cy - ck / 2, x1 - pad, cy + ck / 2), "check")
    canvas.alpha_composite(layer)
    return (x0, y0, x1, y1)


def tilted_stack(im, angle, scale=0.8, back=(236, 236, 238, 255)):
    """The composed card scaled down and rotated over a plain card rotated the
    other way, on a transparent ground the page shows through."""
    w, h = im.size
    card = im.resize((round(w * scale), round(h * scale)), Image.LANCZOS)
    plain = Image.new("RGBA", card.size, (0, 0, 0, 0))
    ImageDraw.Draw(plain).rounded_rectangle((0, 0, card.width - 1, card.height - 1), radius=round(min(card.size) * 0.07), fill=back)
    out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    for layer, a in ((plain, -angle * 0.6), (card, angle)):
        rot = layer.rotate(a, resample=Image.BICUBIC, expand=True)
        out.paste(rot, ((w - rot.width) // 2, (h - rot.height) // 2), rot)
    return out
