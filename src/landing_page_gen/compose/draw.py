"""Pillow primitives for lp-compose. Every function takes pixel coordinates
on the (supersampled) canvas; scaling from reference pixels is cli's job.
Shapes return the rect they covered so callers can report and test them."""

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


def checkerboard(size, cell):
    im = Image.new("RGBA", size, CHECKER[0] + (255,))
    d = ImageDraw.Draw(im)
    for y in range(0, size[1], cell):
        for x in range(0, size[0], cell):
            if ((x // cell) + (y // cell)) % 2:
                d.rectangle((x, y, x + cell - 1, y + cell - 1), fill=CHECKER[1] + (255,))
    return im


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
    s = round(min(x1 - x0, y1 - y0) * 0.4)
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    icon(canvas, (cx - s / 2, cy - s / 2, cx + s / 2, cy + s / 2), name)
    return rect


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


def label(canvas, rect, text, radius, fnt, fill=(28, 28, 28, 255)):
    return box_text(canvas, rect, text, fill, WHITE, radius, fnt)


def brackets(canvas, rect, text, fnt, stroke, colour=WHITE):
    """Four L corners plus a tick at each edge midpoint, the label centred
    below; the crop-selection mark of the crop-frame family."""
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
    return rect


def badge(canvas, rect, radius):
    d = ImageDraw.Draw(canvas)
    d.rounded_rectangle(rect, radius=radius, fill=MAGENTA + (255,))
    x0, y0, x1, y1 = rect
    inset = (x1 - x0) * 0.22
    icon(canvas, (x0 + inset, y0 + inset, x1 - inset, y1 - inset), "check")
    return rect


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
    bw, bh = mark * 0.55, mark * 0.4
    d.rounded_rectangle((tx + tw + mark * 0.4, y0 + pad + (mark - bh) / 2, tx + tw + mark * 0.4 + bw, y0 + pad + (mark + bh) / 2),
                        radius=bh * 0.25, fill=(60, 200, 180, 255))
    icon(layer, (x1 - pad - mark, y0 + pad, x1 - pad, y0 + pad + mark), "chevron", (200, 200, 200, 255))
    # chips
    top = y0 + pad + hh
    if chips:
        step = (w - 2 * pad - dia) / max(1, chips - 1)
        for i in range(chips):
            cx = x0 + pad + i * step
            d.ellipse((cx, top, cx + dia, top + dia), fill=HUES[i % len(HUES)] + (255,))
            if i == active:
                ring = dia * 0.12
                d.ellipse((cx - ring, top - ring, cx + dia + ring, top + dia + ring), outline=(250, 215, 40, 255), width=max(1, round(ring * 0.6)))
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
    dia = min(w * 0.42, h * 0.45)
    bx = x0 + (w - dia) / 2
    d.ellipse((bx, y0, bx + dia, y0 + dia), fill=WHITE)
    inset = dia * 0.28
    icon(layer, (bx + inset, y0 + inset, bx + dia - inset, y0 + dia - inset), icon_name, (20, 20, 20, 255))
    ph = h * 0.28
    py0 = y1 - ph
    d.rounded_rectangle((x0, py0, x1, y1), radius=ph * 0.3, fill=WHITE)
    tip = ph * 0.3
    mx = (x0 + x1) / 2
    d.polygon([(mx - tip, py0 + 1), (mx + tip, py0 + 1), (mx, py0 - tip)], fill=WHITE)
    d.text((mx, py0 + ph / 2), text, font=fnt, fill=(20, 20, 20, 255), anchor="mm")
    canvas.alpha_composite(layer)
    return (x0, y0, x1, y1)


def list_panel(canvas, rect, rows, active, text, fnt, radius):
    """The model-picker list card: a dark card with one row per entry, each a
    neutral disc and a blank grey bar; the active row is lighter and carries
    a white check and, when `text` is given, the page's own model name. No
    other row ever carries a word: competitor names and marks stay out."""
    x0, y0, x1, y1 = (round(v) for v in rect)
    w, h = x1 - x0, y1 - y0
    layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    d.rounded_rectangle((x0, y0, x1, y1), radius=radius, fill=(30, 30, 32, 255))
    rh = h / max(1, rows)
    pad = w * 0.07
    for i in range(rows):
        ry0, ry1 = y0 + rh * i, y0 + rh * (i + 1)
        cy = (ry0 + ry1) / 2
        is_active = i == active
        if is_active:
            d.rounded_rectangle((x0 + pad * 0.4, ry0 + rh * 0.08, x1 - pad * 0.4, ry1 - rh * 0.08), radius=radius * 0.5, fill=(54, 54, 58, 255))
        dia = rh * 0.38
        d.ellipse((x0 + pad, cy - dia / 2, x0 + pad + dia, cy + dia / 2), fill=WHITE if is_active else (120, 120, 126, 255))
        bx0 = x0 + pad + dia * 1.6
        if is_active and text:
            d.text((bx0, cy), text, font=fnt, fill=WHITE, anchor="lm")
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
