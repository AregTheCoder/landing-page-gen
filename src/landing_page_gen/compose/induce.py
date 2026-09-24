"""Templates induced from the corpus: a composite's reading (`lp-corpus read`:
OCR + layout) turned into a skeleton in the families.py format.

The hand-measured templates cover a few dozen originals, and a replica shows
several do not even redraw their own source. Induction measures every
composite the same way: the reading's pictures become panels, its cards
become slots (a statement, a list, a model list, a prompt, a row of chips, a
form, an icon tile) or plain surfaces, a plate over a picture becomes a pill
slot, and each slot keeps the look it was measured with (its fill, radius,
inset and type: the size and weight at which Manrope sets the original's
string to the same width and ink). The words themselves never enter the
template: its exemplar names each slot's block with placeholders, and a
replica reads the original's words back from `corpus/readings` when it draws.

    uv run lp-compose --induce [--limit N] [--page SLUG]   # -> compose/assets/layouts.yaml

Layouts that repeat (the same panels and cards, within a few per cent) are
kept once, with the originals they cover listed as members."""

import hashlib
import json
import re
from pathlib import Path

import numpy as np
import yaml
from PIL import Image, ImageDraw

from . import draw, models
from .families import REF, nearest_ratio

LAYOUTS = Path(__file__).parent / "assets" / "layouts.yaml"
OCR_W = 1.011          # an OCR line box is this much wider than Manrope's ink at the same size (calibrated)
SAME = 0.85            # IoU every panel and card must reach to count two layouts as one
UI_VERBS = re.compile(r"^(generate|download|upload( (video|photo|image|psd))?|try( it)?( now| for free| free)?|get started|"
                      r"buy( now)?|shop( now)?|create|edit|remove|add( to bag)?|start|continue|enrich|export|share|save|"
                      r"apply|next|done|open|browse|select)\b", re.I)
SPEC = re.compile(r"^(x\d+(\.\d+)?|\d+(\.\d+)?\s*[kK]|\d+\s*[x×]\s*\d+|\d+:\d+|\d+\s*(px|fps|s|sec|mb|gb|%)|"
                  r"(hd|4k|8k|2k|1080p|720p|full hd|svg|png|jpe?g|gif|pdf|mp4|webp|psd|eps)|"
                  r"\d+\s+(photos?|images?|videos?|clips?|pages?))$", re.I)
PRICE = re.compile(r"^[$€£]\s?\d|\d[.,]\d\d\s?[$€£]?$")
SOCIAL = re.compile(r"^@|\b(followers|likes|posted|views|comments)\b", re.I)
STATE = re.compile(r"^(before|after|original|enhanced|result)$", re.I)


# ---------------------------------------------------------------- what a string is

def text_category(text):
    """The bank category a string on an original belongs to."""
    t = " ".join(str(text).split())
    if STATE.match(t):
        return "state-label"
    if models.lookup(t):
        return "attribution"
    if re.fullmatch(r"#[0-9a-f]{6}", t, re.I):
        return "derived"
    if SPEC.match(t):
        return "spec"
    if UI_VERBS.match(t) and len(t.split()) <= 4:
        return "action"
    if PRICE.search(t) or SOCIAL.search(t):
        return "context"
    if len(t.split()) >= 6:
        return "action"  # a prompt, or a sentence of copy set as one
    return "statement"


# ---------------------------------------------------------------- measured type

def _ink(img, box, fg, bg):
    """Share of a box's pixels nearer the text colour than the background's."""
    x0, y0, x1, y1 = (int(round(v)) for v in box)
    px = np.asarray(img.crop((x0, y0, x1, y1)).convert("RGB"), np.float32)
    if not px.size:
        return 0.0
    d_fg = np.abs(px - np.asarray(fg, np.float32)).sum(-1)
    d_bg = np.abs(px - np.asarray(bg, np.float32)).sum(-1)
    return float((d_fg < d_bg).mean())


def fit_type(img, line, bg, ref_scale):
    """{px, weight} in REF units at which Manrope sets the line's string to the
    width OCR measured, with the ink share nearest the original's."""
    text = line["text"]
    x0, y0, x1, y1 = line["box"]
    fg = line.get("colour") or ([255, 255, 255] if sum(bg) < 384 else [0, 0, 0])
    target = _ink(img, line["box"], fg, bg)
    best = None
    for w in draw.WEIGHTS:
        f100 = draw.font(100, w)
        unit = f100.getlength(text) / 100
        if unit <= 0:
            continue
        px = (x1 - x0) / OCR_W / unit
        if px < 4:
            continue
        f = draw.font(px, w)
        bb = f.getbbox(text)
        im = Image.new("L", (bb[2] + 4, bb[3] + 4), 0)
        ImageDraw.Draw(im).text((2, 2), text, font=f, fill=255)
        ink = float((np.asarray(im) > 127).mean() * (im.size[0] * im.size[1]) / max(1, (bb[2] - bb[0]) * (y1 - y0)))
        score = abs(ink - target)
        if best is None or score < best[0]:
            best = (score, round(px * ref_scale, 1), w)
    return {"px": best[1], "weight": best[2]} if best else None


# ---------------------------------------------------------------- UI or design

NEUTRAL_SAT = 0.2       # a UI surface is black, a grey or white...
ACCENTS = ((225, 30, 224), (181, 23, 170))  # ...or Picsart's magenta
PILL_PX = 18            # REF px: a plate's words smaller than this are part of the picture (a product's label)
DESIGN_TEXT = 0.7       # share of an original's lines inside its pictures above which the words are the picture's
DESIGN_LINES = 12       # this many lines...
DESIGN_LINE_H = 0.02    # ...with a median height under this share of the image: a document (résumé, menu, flyer)


def _sat(c):
    c = [float(v) for v in c]
    return (max(c) - min(c)) / max(1.0, max(c))


def ui_fill(c):
    """Whether a fill is an interface's (neutral or the accent) rather than a design's."""
    if c is None:
        return False
    return _sat(c) < NEUTRAL_SAT or any(max(abs(a - b) for a, b in zip(c, acc)) < 40 for acc in ACCENTS)


def is_design(reading):
    """An original whose words are set in its pictures (a menu, a card, a poster
    laid out as a grid): its text is the picture's, not chrome to template."""
    lines = reading["texts"]
    if len(lines) < 3:
        return False
    if len(lines) >= DESIGN_LINES and \
            np.median([(t["box"][3] - t["box"][1]) / reading["size"][1] for t in lines]) < DESIGN_LINE_H:
        return True  # a document's many small lines, wherever the reader cut its regions (the résumé thumbnails)
    inside = [t for t in lines if t.get("region") is not None
              and reading["regions"][t["region"]]["kind"] == "picture"]
    return len(inside) / len(lines) >= DESIGN_TEXT


# ---------------------------------------------------------------- slots

def rows_of(lines):
    """OCR lines grouped into rows (a wrap continues its row)."""
    rows = []
    for ln in sorted(lines, key=lambda ln: (ln["box"][1], ln["box"][0])):
        x0, y0, x1, y1 = ln["box"]
        if rows:
            px0, py0, px1, py1 = rows[-1]["box"]
            h = py1 - py0
            if 0 <= y0 - py1 <= 0.6 * h and x0 < px1 and px0 < x1 + h:
                rows[-1]["text"] += " " + ln["text"]
                rows[-1]["box"] = [min(px0, x0), py0, max(px1, x1), y1]
                rows[-1]["lines"].append(ln)
                continue
        rows.append({"text": ln["text"], "box": list(ln["box"]), "lines": [ln]})
    return rows


def _logo_rows(rows):
    """(rows, logos): a row that is one character is a logo read as a letter."""
    keep = [r for r in rows if len(r["text"].strip()) > 1]
    return keep, len(rows) - len(keep)


def _uncaret(text):
    """A chip's string without the dropdown caret OCR reads as a letter ('4:3 v', 'highv')."""
    return re.sub(r"\s*[v∨˅⌄]$", "", str(text).strip()).lstrip("•· ").strip()


def _bounded(img, box, colour, pad=6):
    """Whether a plate ends at its box on every side: the strip just outside
    each edge is not its colour (a word on a poster's dark ground is not a pill,
    even where the poster ends)."""
    x0, y0, x1, y1 = (int(round(v)) for v in box)
    W, H = img.size
    sides = [(x0, max(0, y0 - pad), x1, y0), (x0, y1, x1, min(H, y1 + pad)),
             (max(0, x0 - pad), y0, x0, y1), (x1, y0, min(W, x1 + pad), y1)]
    seen = 0
    for bx in sides:
        if bx[2] <= bx[0] or bx[3] <= bx[1]:
            continue  # the plate touches the edge of the picture there
        px = np.asarray(img.crop(bx).convert("RGB"), np.float32).reshape(-1, 3)
        if float((np.abs(px - np.asarray(colour, np.float32)).max(-1) < 18).mean()) >= 0.6:
            return False
        seen += 1
    return seen >= 3


def _same_line(rows):
    """True when the rows sit side by side on one baseline (a row of chips)."""
    if len(rows) < 2:
        return False
    ys = [(r["box"][1] + r["box"][3]) / 2 for r in rows]
    h = np.median([r["box"][3] - r["box"][1] for r in rows])
    return max(ys) - min(ys) < 0.6 * h


def _words(rows):
    return sum(len(r["text"].split()) for r in rows)


def card_block(card, rows):
    """(shape, accepts, block, kind key(s) for type) of a card by what it holds."""
    fields = [c for c in card.get("children") or [] if c["kind"] == "field"]
    icons = [c for c in card.get("children") or [] if c["kind"] == "icon"]
    if not rows:
        if icons or fields:  # a card with no words around one shape: a logo or a tool glyph
            return "tile", ["tool", "attribution", "derived"], "tool-tile", ()
        return None
    if (icons or fields) and 1 <= len(rows) <= 2 and all(len(r["text"].split()) <= 8 for r in rows) and \
            min(c["box"][0] for c in icons + fields) < min(r["box"][0] for r in rows):
        return "card", ["tool", "context"], "track-list", ("list-row", "chip")  # one row: a glyph, a title, a line
    if fields and len(rows) >= 3 and not _same_line(rows) and any(re.search(r"\d", r["text"]) for r in rows):
        return "card", ["tool", "context"], "calculator", ("form-label", "form-value", "form-head", "form-result")
    if _same_line(rows) and all(len(r["text"].split()) <= 3 for r in rows):
        return "bar", ["spec", "attribution", "action"], "options-bar", ("chip",)
    if len(rows) >= 2 and all(len(r["text"].split()) <= 4 for r in rows):
        if sum(1 for r in rows if models.lookup(_unlogo(r["text"]))) >= max(2, len(rows) // 2):
            return "card", ["attribution"], "model-picker", ("list-row",)
        return "card", ["context", "attribution", "spec"], "channel-list", ("list-card",)
    if _words(rows) >= 6:
        return "card", ["action"], "prompt-card", ("prompt", "prompt-md", "prompt-sm")
    cat = text_category(rows[0]["text"])
    return "card", sorted({cat, "statement"}), "statement", ("statement",)


def _unlogo(text):
    parts = str(text).split(" ", 1)
    return parts[1] if len(parts) == 2 and len(parts[0]) == 1 and parts[1][:1].isupper() else text


def _rgb(c):
    return [int(v) for v in c] if c is not None else None


def line_ink(img, line, back):
    """The colour a line is set in: the median of the quarter of its box's
    pixels furthest from the background (the glyphs' cores, not their
    anti-aliased edges, which read grey)."""
    x0, y0, x1, y1 = (int(round(v)) for v in line["box"])
    px = np.asarray(img.crop((x0, y0, x1, y1)).convert("RGB"), np.float32).reshape(-1, 3)
    if back is None or len(px) < 4:
        return line.get("colour")
    d = np.abs(px - np.asarray(back, np.float32)).max(-1)
    far = px[d >= np.quantile(d, 0.9)]
    return [int(v) for v in np.median(far, axis=0)] if len(far) and d.max() > 40 else line.get("colour")


def _ink_of(rows):
    """The colour a slot's words are set in: the median of its lines' ink."""
    cols = [ln["ink"] for r in rows for ln in r["lines"] if ln.get("ink")] or \
        [ln["colour"] for r in rows for ln in r["lines"] if ln.get("colour")]
    return [int(v) for v in np.median(np.array(cols), axis=0)] if cols else None


def _palette(region, chips, bar):
    """A chip row's measured look: its bar, its usual chip and ink, and the chip
    picked out (a fill unlike the rest) with its ink."""
    fields = [c for c in region.get("children") or [] if c["kind"] == "field"]
    def plate(r):
        cx, cy = (r["box"][0] + r["box"][2]) / 2, (r["box"][1] + r["box"][3]) / 2
        f = next((f for f in fields if f["box"][0] <= cx <= f["box"][2] and f["box"][1] <= cy <= f["box"][3]), None)
        return tuple(f["fill"]) if f else None
    plates = [plate(r) for r in chips]
    known = [p for p in plates if p]
    pal = {"bar": _rgb(bar)}
    if known:
        common = max(set(known), key=known.count)
        pal["chip"] = list(common)
        odd = [(p, r) for p, r in zip(plates, chips) if p and p != common]
        if odd:
            pal["active"] = list(odd[0][0])
            pal["active_ink"] = _ink_of([odd[0][1]])
    ink = _ink_of([r for p, r in zip(plates, chips) if not pal.get("active") or list(p or ()) != pal.get("active")])
    if ink:
        pal["ink"] = ink
    return pal


def _type(img, row, fill, s):
    return fit_type(img, max(row["lines"], key=lambda ln: ln["box"][3] - ln["box"][1]), fill or [0, 0, 0], s)


def _chips(region, rows):
    """The rows that sit in the card's fields on one line (a row of chips), and the rest."""
    fields = [c for c in region.get("children") or [] if c["kind"] == "field"]
    inside = lambda r, f: f["box"][0] - 4 <= (r["box"][0] + r["box"][2]) / 2 <= f["box"][2] + 4 and \
        f["box"][1] - 4 <= (r["box"][1] + r["box"][3]) / 2 <= f["box"][3] + 4  # noqa: E731
    boxed = [r for r in rows if any(inside(r, f) for f in fields) and len(_uncaret(r["text"]).split()) <= 3]
    if not boxed:
        return [], rows
    # every short row on the boxed chips' line is a chip, boxed or not (a model chip, an accent button)
    y = np.median([(r["box"][1] + r["box"][3]) / 2 for r in boxed])
    h = np.median([r["box"][3] - r["box"][1] for r in boxed])
    chips = [r for r in rows if len(_uncaret(r["text"]).split()) <= 3 and abs((r["box"][1] + r["box"][3]) / 2 - y) < 0.6 * h]
    if len(chips) < 2:
        return [], rows
    return chips, [r for r in rows if r not in chips]


def induce(reading, family=None, merge=True):
    """A layout skeleton (families.py format) measured from one reading; with
    `merge`, stacked like cards become one list slot (a still's list; a clip
    keeps its rows apart, each moves on its own)."""
    w0, h0 = reading["size"]
    s = REF / w0  # original px -> REF
    ref = lambda box: tuple(round(v * s) for v in box)  # noqa: E731
    img = Image.open(reading["local"]).convert("RGBA")
    base = Image.new("RGBA", img.size, (255, 255, 255, 255))
    base.alpha_composite(img)
    img = base.convert("RGB")
    ground = reading["ground"]
    layout = {"aspect": _aspect(w0, h0), "radius": 0,
              "background": {"ground": {"fill": None if ground in ("transparent", "picture") else _rgb(ground)},
                             "surfaces": []},
              "panels": {}, "slots": [], "exemplar": {"source": f"{reading['id']} {reading['page']} {reading['slot']}",
                                                      "fills": {}}}
    radii, pics, n = [], [], {"photo": 0, "slot": 0}

    def panel(rect, holds="scene", radius=0.0):
        n["photo"] += 1
        pics.append(radius)
        name = "photo" if n["photo"] == 1 else f"photo-{n['photo']}"
        layout["panels"][name] = {"rect": rect, "holds": holds, "ratio": nearest_ratio(rect[2] - rect[0], rect[3] - rect[1])}

    def slot(shape, accepts, rect, blk, params, look):
        n["slot"] += 1
        sid = f"{shape}-{n['slot']}"
        layout["slots"].append({"id": sid, "shape": shape, "accepts": accepts, "required": shape != "pill",
                                "rect": rect, **{k: v for k, v in look.items() if v is not None}})
        layout["exemplar"]["fills"][sid] = {"block": blk, **params}

    for i, region in enumerate(reading["regions"]):
        rect = ref(region["box"])
        if region.get("radius"):
            radii.append(region["radius"] * s)
        raw = (region.get("radius") or 0) * s
        rr = round(raw)  # a card keeps its own corner: a flat fill measures true
        lines = [t for t in reading["texts"] if t.get("region") == i]
        fill = region.get("fill")
        plates = [c for c in region.get("children") or [] if c["kind"] == "field"]
        for ln in lines:  # against what the words sit on: a field's plate, else the card
            cx, cy = (ln["box"][0] + ln["box"][2]) / 2, (ln["box"][1] + ln["box"][3]) / 2
            on = next((f["fill"] for f in plates if f["box"][0] <= cx <= f["box"][2] and f["box"][1] <= cy <= f["box"][3]), fill)
            ln["ink"] = line_ink(img, ln, on)
        if region["kind"] == "picture":
            panel(rect, radius=raw)
            if region.get("split") is not None:  # a compare card: its After right of the divider, and the divider
                panel(rect, radius=raw)
                layout["panels"][f"photo-{n['photo']}"]["seam"] = region["split"]
                slot("seam", ["comparison"], rect, "compare-handle", {}, {"split": region["split"]})
            plates = [c for c in region.get("children") or [] if c["kind"] == "pill"]
            for ln in lines:
                cat = text_category(ln["text"])
                if cat not in ("state-label", "spec", "attribution", "action") or \
                        (cat == "action" and not (UI_VERBS.match(ln["text"].strip()) and len(ln["text"].split()) <= 4)):
                    continue  # a poster's words, a label on a product, a tagline: the picture's own
                plate = next((c for c in plates if c.get("text") == ln["text"]), None)
                solid = plate is not None and ui_fill(plate.get("fill")) and _bounded(img, plate["box"], plate["fill"])
                back = plate["fill"] if solid else [30, 30, 30]
                ty = fit_type(img, ln, back, s)
                if not ty or ty["px"] < PILL_PX:
                    continue
                x0, y0, x1, y1 = ln["box"]
                th = y1 - y0
                box = plate["box"] if solid else [x0 - 0.7 * th, y0 - 0.45 * th, x1 + 0.7 * th, y1 + 0.45 * th]
                lum = sum(plate["fill"][:3]) / 3 if solid else 0
                blk = {"state-label": "state-pill", "attribution": "model-pill", "action": "cta-button"}.get(cat, "spec-pill")
                slot("pill", [cat], ref(box), blk, {"text": _placeholder(blk)},
                     {"fill": _rgb(plate["fill"]) if solid else None,
                      "style": ("solid-light" if lum > 150 else "solid-dark") if solid else "translucent",
                      "type": {"pill": ty, "button": ty}})
            continue
        rows, logos = _logo_rows(rows_of(lines))
        icons = [c for c in region.get("children") or [] if c["kind"] in ("icon", "field") and not c.get("text")]
        if not ui_fill(fill) and not icons and (not rows or len(rows) >= 2 or
                                                (rows and (_type(img, rows[0], fill, s) or {}).get("px", 0) > 90)):
            panel(rect, "design" if rows else "scene", raw)  # a design card or an illustration, not interface
            continue
        chips, rest = _chips(region, rows)
        if chips and rest:  # one card holding a prompt and its options: the card is a surface, each group a slot
            layout["background"]["surfaces"].append({"kind": "card", "rect": rect, "fill": _rgb(fill), "radius": rr})
            box = ref([min(r["box"][0] for r in rest), min(r["box"][1] for r in rest),
                       max(r["box"][2] for r in rest), max(r["box"][3] for r in rest)])
            long_ = _words(rest) >= 6
            ty = _type(img, rest[0], fill, s)
            slot("text", ["action"] if long_ else ["statement"], box, "prompt-line" if long_ else "statement",
                 {"text": "The prompt that made the picture" if long_ else "A line of the copy"},
                 {"type": {"prompt": ty, "prompt-md": ty, "prompt-sm": ty, "statement": ty, "panel-label": ty},
                  "colour": _ink_of(rest)})
            cb = ref([min(r["box"][0] for r in chips) - 12, min(r["box"][1] for r in chips) - 8,
                      max(r["box"][2] for r in chips) + 12, max(r["box"][3] for r in chips) + 8])
            slot("bar", ["spec", "attribution", "action"], cb, "options-bar",
                 {"items": [{"text": f"Option {k + 1}"} for k in range(len(chips))]},
                 {"type": {"chip": _type(img, chips[0], fill, s)}, "palette": {**_palette(region, chips, None), "bar": None}})
            continue
        got = card_block(region, rows)
        if got is None:  # a plain card: part of the background
            layout["background"]["surfaces"].append({"kind": "card", "rect": rect, "fill": _rgb(fill), "radius": rr})
            continue
        shape, accepts, blk, keys = got
        look = {"fill": _rgb(fill), "radius": rr}
        params = _placeholders(blk, rows)
        if shape == "tile":  # name the icon: a maker's mark, a tool's glyph, the upload step
            named = _icon_block(img, region, fill)
            if named:
                accepts, blk, extra = named
                params = {**params, **extra}
        if rows and blk == "calculator":
            look["type"] = _form_type(img, region, rows, fill, s)
        elif rows and keys:
            ty = _type(img, max(rows, key=lambda r: r["box"][3] - r["box"][1]), fill, s)
            if ty:
                look["type"] = {k: ty for k in keys}
            look["pad"] = max(0, round((min(r["box"][0] for r in rows) - region["box"][0]) * s))
        if logos:
            look["logos"] = logos
        if rows:
            look["colour"] = _ink_of(rows)
        if blk == "options-bar":
            look["palette"] = _palette(region, rows, fill)
        slot(shape, accepts, rect, blk, params, look)
    for k, sf in enumerate(layout["background"]["surfaces"], 1):  # surfaces are drawn like chrome: each needs an id
        sf["id"] = f"surface-{k}"
    layout["radius"] = round(float(np.median(radii))) if radii else 0
    for p in layout["panels"].values():  # a photo's corner is read against its own pixels (a dark corner merges
        p["radius"] = round(float(np.median(pics)))  # with a dark ground: 9 and 196 on m-f473d4), so panels share one
    layout["family"] = family
    layout["size"] = [w0, h0]
    return merge_lists(layout, reading) if merge else layout


def _form_type(img, region, rows, fill, s):
    """A form's measured type by part: the labels over its fields, the values
    in them, and the result's head and figure (the right-hand lines)."""
    fields = [c for c in region.get("children") or [] if c["kind"] == "field"]
    mid = (region["box"][0] + region["box"][2]) / 2
    inside = lambda r: any(f["box"][0] <= (r["box"][0] + r["box"][2]) / 2 <= f["box"][2] and  # noqa: E731
                           f["box"][1] <= (r["box"][1] + r["box"][3]) / 2 <= f["box"][3] for f in fields)
    left = [r for r in rows if (r["box"][0] + r["box"][2]) / 2 < mid]
    right = sorted((r for r in rows if (r["box"][0] + r["box"][2]) / 2 >= mid), key=lambda r: r["box"][1])
    parts = {"form-label": [r for r in left if not inside(r)], "form-value": [r for r in left if inside(r)],
             "form-head": right[:1], "form-result": right[1:2]}
    out = {}
    for key, rs in parts.items():
        if rs:
            ty = _type(img, rs[0], fill, s)
            if ty:
                out[key] = ty
    return out


def _icon_block(img, region, fill):
    """(accepts, block, params) for a tile whose one icon is recognised, else None."""
    from . import icons, roles
    kids = [c for c in region.get("children") or [] if c["kind"] in ("icon", "field") and not c.get("text")]
    if not kids:
        return None
    c = max(kids, key=lambda c: (c["box"][2] - c["box"][0]) * (c["box"][3] - c["box"][1]))
    name, _ = icons.classify(img.crop(tuple(c["box"])), fill or [0, 0, 0])
    if not name:
        return None
    if name.startswith("logo:"):
        maker = name[5:]
        model = next((m["name"] for m in models.catalogue()["models"] if m.get("logo") == maker), None)
        return ["attribution"], "generator-mark", ({"model": model} if model else {})
    if name in ("upload", "add-image"):  # the reader's step: add a picture
        return ["action"], "upload-tile", {}
    if name == "spinner":
        return ["process"], "progress-ring", {}
    if name == "cursor":
        return ["editor"], "pointer", {}
    tool = roles.icon_tool(name)
    if tool:
        return ["tool"], "tool-tile", {"tool": tool}
    return None


def merge_lists(layout, reading):
    """Runs of three or more like cards stacked at one x and a regular pitch
    (the rows of a picker, the models of a list) become one list slot: a
    track list when the rows carry a glyph, a plain list otherwise."""
    cards = [s for s in layout["slots"] if s["shape"] == "card" and s.get("rect")]
    cards.sort(key=lambda s: (s["rect"][0], s["rect"][1]))
    used, runs = set(), []
    for i, a in enumerate(cards):
        if a["id"] in used:
            continue
        run = [a]
        for b in cards[i + 1:]:
            p = run[-1]["rect"]
            q = b["rect"]
            wa, ha, wb, hb = p[2] - p[0], p[3] - p[1], q[2] - q[0], q[3] - q[1]
            if abs(q[0] - p[0]) <= 8 and abs(wb - wa) <= 0.03 * wa and abs(hb - ha) <= 0.1 * ha and 0 <= q[1] - p[3] <= 0.8 * ha:
                run.append(b)
        if len(run) >= 3:
            runs.append(run)
            used |= {x["id"] for x in run}
    for run in runs:
        ids = {x["id"] for x in run}
        glyphs = sum(1 for x in run if layout["exemplar"]["fills"].get(x["id"], {}).get("block") in ("tool-tile",)
                     or x.get("logos"))
        first = run[0]
        rect = (run[0]["rect"][0], run[0]["rect"][1], run[-1]["rect"][2], run[-1]["rect"][3])
        block = "track-list"
        sid = f"list-{first['id'].split('-')[-1]}"
        slot = {k: v for k, v in first.items() if k not in ("id", "rect")}
        slot.update({"id": sid, "shape": "card", "rect": rect, "accepts": ["tool", "context"], "required": True})
        layout["slots"] = [s for s in layout["slots"] if s["id"] not in ids] + [slot]
        for x in ids:
            layout["exemplar"]["fills"].pop(x, None)
        layout["exemplar"]["fills"][sid] = {"block": block, "rows": [[f"Choice {k + 1}", "A line under it"]
                                                                      for k in range(len(run))]}
    return layout


def _aspect(w, h):
    """A small ratio within 1 % of the original's (inside `cli.fits`' 2 %): the
    generation ratio when one is that close, else the nearest small fraction.
    Snapping 1.445 to 3:2 stretched its replica 4 % (184 layouts)."""
    from fractions import Fraction
    from math import gcd
    g = gcd(w, h)
    a, b = w // g, h // g
    if max(a, b) > 50:  # an odd pixel size: the nearest generation ratio names it, when it is close
        a, b = (int(x) for x in nearest_ratio(w, h).split(":"))
        if abs((w / h) / (a / b) - 1) > 0.01:
            f = Fraction(w, h).limit_denominator(50)
            a, b = f.numerator, f.denominator
    return (a, b)


def _placeholder(blk):
    return {"state-pill": "Before", "cta-button": "Action", "model-pill": "Model"}.get(blk, "Label")


def _placeholders(blk, rows):
    """The block's parameters with placeholder words, shaped like the original's."""
    n = max(1, len(rows))
    if blk == "statement":
        return {"text": "A line of the copy"}
    if blk == "channel-list":
        return {"rows": [f"Row {i + 1}" for i in range(n)]}
    if blk == "model-picker":
        return {"rows": n}
    if blk == "prompt-card":
        return {"text": "The prompt that made the picture"}
    if blk == "track-list":
        return {"rows": [["A choice", "A line under it"]]}
    if blk == "options-bar":
        return {"items": [{"text": f"Option {i + 1}"} for i in range(n)]}
    if blk == "calculator":
        k = max(1, (n - 2) // 2)
        return {"fields": [[f"Input {i + 1}", "0"] for i in range(k)], "result": ["Result:", "0"]}
    return {}


# ---------------------------------------------------------------- the catalogue

def _rects(layout):
    return [p["rect"] for p in layout["panels"].values()] + [s["rect"] for s in layout["slots"] if s.get("rect")]


def _iou(a, b):
    ix = max(0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = ix * iy
    u = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / u if u else 0.0


def same_layout(a, b):
    """Two layouts are one when their aspects match and every panel and slot of
    each has a partner of the same shape in the other at IoU >= SAME."""
    if tuple(a["aspect"]) != tuple(b["aspect"]) or len(a["panels"]) != len(b["panels"]) or len(a["slots"]) != len(b["slots"]):
        return False
    shapes = lambda L: sorted(s["shape"] for s in L["slots"])  # noqa: E731
    if shapes(a) != shapes(b):
        return False
    ra, rb = _rects(a), _rects(b)
    return all(max((_iou(x, y) for y in rb), default=0) >= SAME for x in ra)


def catalogue(readings_iter, families_of, min_parts=2):
    """{family: {name: layout}} from every composite reading: repeats kept once
    (the first seen, with the others as members)."""
    out = {}
    kept = []
    for rd in readings_iter:
        regions = rd["regions"]
        if len(regions) < min_parts and not any(c["kind"] == "pill" for r in regions for c in r.get("children") or []) \
                and not any(r.get("split") is not None for r in regions):  # a compare card is Before, After and a divider
            continue
        if is_design(rd):
            continue
        try:
            lay = induce(rd, families_of(rd))
        except (OSError, ValueError) as e:
            print(f"induce: {rd['id']}: {e}")
            continue
        if not lay["slots"] and len(lay["panels"]) < 2:
            continue
        twin = next((k for k in kept if k["family"] == lay["family"] and same_layout(k, lay)), None)
        if twin:
            twin.setdefault("members", []).append(rd["id"])
            continue
        kept.append(lay)
    for lay in kept:
        fam = lay.pop("family") or "dark-composite"
        out.setdefault(fam, {})[layout_name(lay["exemplar"]["source"].split()[0])] = lay
    return out


def layout_name(asset_id):
    """An induced layout's name: opaque, so a brief that names the layout never
    names the original it was measured from (blindcheck refuses a page's own
    asset ids); `families.induced_for` finds it by its source."""
    return "m-" + hashlib.sha1(asset_id.encode()).hexdigest()[:6]


COMPOSE = ("before-after", "crop-frame", "cutout-checkerboard", "dark-composite", "mockup-card", "panel-overlay",
           "prompt-card", "template-mockup", "vs-two-up")


def families_by_src():
    """{src: compose family} from the labelled attributes (the family hint, else the style)."""
    import yaml as _y
    from ..corpus import attrs
    data = _y.safe_load(Path(attrs.ATTRIBUTES_YAML).read_text()) or {}
    out = {}
    for src, a in data.items():
        fam = a.get("family_hint") or a.get("style")
        out[src] = fam if fam in COMPOSE else "dark-composite"
    return out


def run(path=LAYOUTS):
    from ..corpus import readings
    fams = families_by_src()
    cat = catalogue(readings.every(), lambda rd: fams.get(rd["src"], "dark-composite"))
    write(cat, path)
    return cat


def write(cat, path=LAYOUTS):
    def plain(x):
        if isinstance(x, dict):
            return {k: plain(v) for k, v in x.items()}
        if isinstance(x, (list, tuple)):
            return [plain(v) for v in x]
        return x
    header = ("# Layouts induced from corpus readings (`lp-compose --induce`); rebuilt, never hand-edited.\n"
              "# Each is a skeleton in the families.py format; the exemplar carries placeholders, never page words.\n")
    Path(path).write_text(header + yaml.safe_dump(plain(cat), sort_keys=False, allow_unicode=True, width=120))
    return path

