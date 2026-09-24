"""Templated callout videos: lp-compose blocks animated on a timeline.

The ai-image-enhancer callouts (S07, S10, S11, S13, and their twins on
--unblur, --unpixelate, video-enhancer) are not generated motion. They are a
composition that changes state on a static camera:
1. a hero card;
2. a compare-handle sweep that reveals the fixed picture;
3. a settle into a bento (a column of tiles, tool tiles and one big card)
   while a checklist ticks, a prompt types or brand strings set.

A preset builds that as layers. Each layer is a panel (a generated still, or
a clip) or a chrome block with its role, with keyframes for rect, opacity,
wipe (the share shown from the left) and type (the share of the text set).
PIL draws every frame, reusing the compose kinds. Chromium encodes them to
VP9 with WebCodecs; Playwright is already here, and its bundled ffmpeg cannot
encode. The frames are muxed into WebM in Python with the real duration.
Free, deterministic, and every string is exact.

    uv run lp-compose --timeline motion-S10-m1.yaml --image photo=steps/S10-m1-2.png --out steps/S10-m1.webm
    uv run lp-compose --describe-timelines
"""

import base64
import math
import struct
import sys
import tempfile
from pathlib import Path

import yaml
from PIL import Image, ImageChops

from . import bank, degrade, draw, kinds, roles

REF = 1600
FPS = 30
BITRATE = 6_000_000
KEY_EVERY = 2.0  # seconds between keyframes (and clusters)
VIDEO_SUFFIXES = (".webm", ".mp4")
CLIP_FPS = 15    # a clip panel is sampled at this rate (each frame is a Chromium seek)
HOLD = 0.5       # seconds the last state holds before the clip ends

# the shared bento the S07 and S11 callouts settle into (REF px, 1:1, measured on
# their last frames): two photo tiles down the left, tool tiles top right, one card
TILE_A, TILE_B = (0, 0, 784, 784), (0, 816, 784, 1600)
TOOLS = ((816, 0, 1192, 376), (1224, 0, 1600, 376))
CARD = (816, 408, 1600, 1600)


def ease(x):
    """ease-in-out cubic on 0..1"""
    x = min(1.0, max(0.0, x))
    return 4 * x ** 3 if x < 0.5 else 1 - (-2 * x + 2) ** 3 / 2


def _lerp(a, b, f):
    if isinstance(a, (list, tuple)):
        return [x + (y - x) * f for x, y in zip(a, b)]
    return a + (b - a) * f


def value(keys, prop, t, default=None):
    """A layer property at time t: held before its first key and after its
    last, eased between keys (two keys at one time make a cut)."""
    pts = [(k["t"], k[prop]) for k in keys if prop in k]
    if not pts:
        return default
    if t < pts[0][0]:
        return pts[0][1]
    for (t0, v0), (t1, v1) in zip(pts, pts[1:]):
        if t < t1:
            return _lerp(v0, v1, ease((t - t0) / (t1 - t0)) if t1 > t0 else 1.0)
    return pts[-1][1]


# ---------------------------------------------------------------- presets

def _hero_to(layer_id, role, panel, hero, end, t_move, **extra):
    """A panel that starts on the hero card and moves into its bento cell."""
    return {"id": layer_id, "role": role, "panel": panel, **extra,
            "keys": [{"t": 0, "rect": list(hero), "opacity": 0}, {"t": 0.25, "opacity": 1},
                     {"t": t_move, "rect": list(hero)}, {"t": t_move + 0.7, "rect": list(end)}]}


def _sweep(hero, t0, t1, handle_id="handle"):
    """The compare-handle sweeping across the hero card, left to right."""
    x0, y0, x1, y1 = hero
    w = 150
    return {"id": handle_id, "role": "comparison", "kind": "compare-handle",
            "keys": [{"t": 0, "rect": [x0 - w / 2, y0, x0 + w / 2, y1], "opacity": 0},
                     {"t": t0, "opacity": 1, "rect": [x0 - w / 2, y0, x0 + w / 2, y1]},
                     {"t": t1, "rect": [x1 - w / 2, y0, x1 + w / 2, y1], "opacity": 1},
                     {"t": t1 + 0.2, "opacity": 0}]}


def _tool_tiles(facts, t, n=2):
    out = []
    for i, tool in enumerate([x for x in (facts or {}).get("tools") or [] if roles.tool(x)][:n]):
        out.append({"id": f"tool-{i + 1}", "role": "tool", "kind": "tile", "tool": tool, "icon": roles.tool(tool)["icon"],
                    "fill": [28, 28, 30], "keys": [{"t": 0, "opacity": 0, "rect": list(TOOLS[i])},
                                                    {"t": t + 0.2 * i, "opacity": 0}, {"t": t + 0.2 * i + 0.35, "opacity": 1}]})
    return out


def enhance_reveal(strings, facts):
    """S10 of ai-image-enhancer (4.0 s): the flawed picture on a card, a
    compare-handle sweeps the fix across it, then the pair splits (the Before
    small, top left; the After tall, right) and the checklist of what the tool
    did ticks in under the Before."""
    hero = (267, 117, 1333, 1483)
    mode = (facts or {}).get("degrade") or "lowlight"
    layers = [
        _hero_to("before", "before", "photo", hero, (0, 0, 784, 1184), 1.8, degrade=mode),
        {**_hero_to("after", "after", "photo", hero, (816, 0, 1600, 1600), 1.8),
         "keys": [{"t": 0, "rect": list(hero), "opacity": 1, "wipe": 0}, {"t": 0.6, "wipe": 0}, {"t": 1.6, "wipe": 1},
                  {"t": 1.8, "rect": list(hero)}, {"t": 2.5, "rect": [816, 0, 1600, 1600]}]},
        _sweep(hero, 0.6, 1.6),
    ]
    for i, row in enumerate(strings[:4]):
        y = 1250 + i * 110
        layers.append({"id": f"check-{i + 1}", "role": "spec", "kind": "check-row", "text": row, "font": "chip-lg",
                       "keys": [{"t": 0, "rect": [40, y + 40, 744, y + 130], "opacity": 0, "tick": 0},
                                {"t": 2.5 + 0.25 * i, "rect": [40, y + 40, 744, y + 130], "opacity": 0},
                                {"t": 2.8 + 0.25 * i, "rect": [40, y, 744, y + 90], "opacity": 1, "tick": 0},
                                {"t": 3.0 + 0.25 * i, "tick": 1}]})
    return {"duration": 4.0, "layers": layers}


def product_bento(strings, facts):
    """S11 (7.0 s): a soft product photo sharpens under the handle, becomes a
    shop card (name, price, the buy button from the copy) and settles into
    the bento: two photo tiles left, the page's tool tiles top right, the card
    bottom right."""
    name, price, button = (list(strings) + ["", "", ""])[:3]
    hero = (427, 320, 1173, 1280)
    card0 = (390, 300, 1210, 1300)
    layers = [
        {"id": "before", "role": "before", "panel": "photo", "degrade": (facts or {}).get("degrade") or "blur",
         "keys": [{"t": 0, "rect": list(hero), "opacity": 0}, {"t": 0.25, "opacity": 1}, {"t": 1.8, "opacity": 1},
                  {"t": 2.2, "opacity": 0}]},
        {"id": "after", "role": "after", "panel": "photo",
         "keys": [{"t": 0, "rect": list(hero), "opacity": 1, "wipe": 0}, {"t": 0.6, "wipe": 0}, {"t": 1.6, "wipe": 1},
                  {"t": 1.8, "opacity": 1}, {"t": 2.2, "opacity": 0}]},
        _sweep(hero, 0.6, 1.6),
        {"id": "tile-a", "role": "after", "panel": "photo",
         "keys": [{"t": 0, "rect": list(TILE_A), "opacity": 0}, {"t": 3.0, "opacity": 0}, {"t": 3.5, "opacity": 1}]},
        {"id": "tile-b", "role": "after", "panel": "photo-b",
         "keys": [{"t": 0, "rect": list(TILE_B), "opacity": 0}, {"t": 3.2, "opacity": 0}, {"t": 3.7, "opacity": 1}]},
        {"id": "card", "role": "context", "kind": "product-card", "name": name, "price": price,
         "button": button,
         "keys": [{"t": 0, "rect": list(card0), "opacity": 0}, {"t": 1.9, "opacity": 0}, {"t": 2.3, "opacity": 1},
                  {"t": 2.9, "rect": list(card0)}, {"t": 3.6, "rect": list(CARD)}]},
    ]
    return {"duration": 7.0, "layers": layers + _tool_tiles(facts, 3.9)}


def prompt_to_result(strings, facts):
    """S13 (10.0 s): the result full bleed (a clip, or a still drifting in),
    a cut to black where the prompt types itself, then the prompt settles in
    a column with the tool mark (and the voice line and mic when the copy
    offers audio), the result right with a play mark."""
    prompt = (list(strings) + [""])[0]
    tool = (facts or {}).get("tool") or "generate"
    layers = [
        {"id": "result", "role": "after", "panel": "result",
         "keys": [{"t": 0, "rect": [0, 0, 1600, 1600], "opacity": 1}, {"t": 3.4, "rect": [-48, -48, 1648, 1648]},
                  {"t": 3.5, "opacity": 0, "rect": [880, 0, 1600, 1600]}, {"t": 6.0, "opacity": 0},
                  {"t": 6.6, "opacity": 1}]},
        {"id": "prompt", "role": "action", "kind": "prompt-text", "text": prompt, "font": "prompt-sm", "pad": 48,
         "keys": [{"t": 0, "rect": [320, 630, 1280, 980], "opacity": 0, "type": 0}, {"t": 3.5, "opacity": 0},
                  {"t": 3.6, "opacity": 1, "type": 0}, {"t": 5.6, "type": 1, "rect": [320, 630, 1280, 980]},
                  {"t": 6.4, "rect": [30, 30, 850, 560]}]},
        {"id": "tool", "role": "tool", "kind": "icon", "icon": roles.tool(tool)["icon"], "tool": tool,
         "keys": [{"t": 0, "rect": [340, 960, 540, 1160], "opacity": 0}, {"t": 6.7, "opacity": 0}, {"t": 7.0, "opacity": 1}]},
        {"id": "play", "role": "spec", "kind": "play-button",
         "keys": [{"t": 0, "rect": [1140, 700, 1340, 900], "opacity": 0}, {"t": 7.0, "opacity": 0}, {"t": 7.4, "opacity": 1}]},
    ]
    if "voice" in ((facts or {}).get("tools") or []):  # the voice line only where the page offers audio
        layers[2:2] = [
            {"id": "wave", "role": "spec", "kind": "waveform",
             "keys": [{"t": 0, "rect": [60, 640, 820, 760], "opacity": 0}, {"t": 6.4, "opacity": 0}, {"t": 6.8, "opacity": 1}]},
            {"id": "voice", "role": "tool", "kind": "icon", "icon": "mic", "tool": "voice",
             "keys": [{"t": 0, "rect": [370, 1300, 510, 1440], "opacity": 0}, {"t": 6.9, "opacity": 0}, {"t": 7.2, "opacity": 1}]},
        ]
    return {"duration": 10.0, "layers": layers}


def brand_to_mockup(strings, facts):
    """S07 (6.0 s): the photo on a card, the caption typing onto it inside an
    editor selection box, the brand name setting on top, then the bento: the
    photo twice down the left, the tool tile top right, the design applied as
    a mockup bottom right (a generated still)."""
    title, caption = (list(strings) + ["", ""])[:2]
    hero = (250, 120, 1350, 1480)
    cap = (330, 1150, 1270, 1400)
    layers = [
        {**_hero_to("card", "subject", "photo", hero, TILE_A, 3.0)},
        {"id": "tile-b", "role": "subject", "panel": "photo",
         "keys": [{"t": 0, "rect": list(TILE_B), "opacity": 0}, {"t": 3.3, "opacity": 0}, {"t": 3.8, "opacity": 1}]},
        {"id": "caption", "role": "action", "kind": "text", "text": caption, "font": "prompt-md", "wrap": True,
         "keys": [{"t": 0, "rect": list(cap), "opacity": 0, "type": 0}, {"t": 0.8, "opacity": 1, "type": 0},
                  {"t": 2.0, "type": 1}, {"t": 2.9, "opacity": 1}, {"t": 3.1, "opacity": 0}]},
        {"id": "select", "role": "editor", "kind": "selection-frame", "colour": [255, 255, 255], "stroke": 4, "handle": 12,
         "keys": [{"t": 0, "rect": [cap[0] - 20, cap[1] - 20, cap[2] + 20, cap[3] + 20], "opacity": 0},
                  {"t": 0.8, "opacity": 1}, {"t": 2.2, "opacity": 1}, {"t": 2.5, "opacity": 0}]},
        {"id": "title", "role": "action", "kind": "text", "text": title, "font": "headline",
         "keys": [{"t": 0, "rect": [330, 200, 1270, 400], "opacity": 0}, {"t": 2.2, "opacity": 0}, {"t": 2.6, "opacity": 1},
                  {"t": 2.9, "opacity": 1}, {"t": 3.1, "opacity": 0}]},
        {"id": "mockup", "role": "context", "panel": "mockup",
         "keys": [{"t": 0, "rect": list(CARD), "opacity": 0}, {"t": 3.4, "opacity": 0}, {"t": 4.0, "opacity": 1}]},
    ]
    return {"duration": 6.0, "layers": layers + _tool_tiles(facts, 4.1, n=1)}


# preset -> (builder, panels {name: what the worker supplies}, the `> chrome:` strings in order)
PRESETS = {
    "enhance-reveal": (enhance_reveal, {"photo": "the fixed picture (generated); the Before is it degraded"},
                       ["checklist rows (1-4): what the tool fixed"]),
    "product-bento": (product_bento, {"photo": "the product in its scene (generated)",
                                      "photo-b": "optional: a second view (else the photo again)",
                                      "cutout": "optional: the product cut out (remove_bg, 0 cr; else the photo)"},
                      ["product name", "price", "button"]),
    "prompt-to-result": (prompt_to_result, {"result": "the output: a still, or the seedance clip (.webm/.mp4)"},
                         ["the prompt that made it"]),
    "brand-to-mockup": (brand_to_mockup, {"photo": "the photo the design is set on (generated)",
                                          "mockup": "the design applied (a poster on a wall), generated with the "
                                                    "title and caption as its `> text:`"},
                        ["title", "caption"]),
}
OPTIONAL_PANELS = {"photo-b": "photo", "cutout": "photo"}


def build(preset, size, strings=(), facts=None, slot=None):
    """The motion spec a brief writes (`motion-<slot>.yaml`): the preset's
    layers with the page's strings and tools; the worker adds only images."""
    if preset not in PRESETS:
        raise ValueError(f"timeline preset {preset!r}: one of {', '.join(PRESETS)}")
    fn, panels, _ = PRESETS[preset]
    body = fn(list(strings or []), facts)
    # the originals keep moving to their last half second (lp-corpus frames reads them fast):
    # stretch the cues so the last one lands there instead of holding still
    last = max(k["t"] for ly in body["layers"] for k in ly["keys"])
    stretch = (body["duration"] - HOLD) / last if last < body["duration"] - HOLD else 1.0
    for ly in body["layers"]:
        for k in ly["keys"]:
            k["t"] = round(k["t"] * stretch, 3)
    spec = {"slot": slot, "preset": preset, "size": size, "fps": FPS, "ground": [0, 0, 0], "radius": 40,
            **body, "panels": dict(panels)}
    if facts:
        spec["facts"] = {k: v for k, v in facts.items() if v not in (None, [], "")}
    return spec


def validate(spec):
    """What would make the clip false or unrenderable: an unknown preset or
    kind, an empty string, a block whose role the page cannot claim."""
    probs = []
    if spec.get("preset") not in PRESETS:
        probs.append(f"preset {spec.get('preset')!r} is not one of {', '.join(PRESETS)}")
    w, h = _size(spec)
    if w != h:
        probs.append(f"size {w}x{h}: the callout timelines are 1:1 (the originals are 480x480)")
    if w % 2 or h % 2:
        probs.append("size must be even for VP9")
    items = []
    for ly in spec.get("layers") or []:
        if "kind" in ly:
            if ly["kind"] not in kinds.KINDS and ly["kind"] != "product-card":
                probs.append(f"layer {ly['id']!r}: kind {ly['kind']!r} is not drawable")
            for f in ("text", "name", "price", "button"):
                if f in ly and not str(ly[f]).strip():
                    probs.append(f"layer {ly['id']!r}: {f} is empty: give it with the skeleton's `> chrome:` line")
            if draw.missing_glyphs(ly):
                probs.append(f"layer {ly['id']!r}: {draw.missing_glyphs(ly)!r} is not in the font (it would print as boxes)")
            if ly["kind"] != "product-card":
                items.append({k: v for k, v in ly.items() if k != "keys"})
    before = any(ly.get("degrade") for ly in spec.get("layers") or [])
    ctx = bank.context({"panels": ["before", "after"] if before else ["result"]})
    for it in items:  # a chrome layer's role is its block category (compose/assets/blocks.yaml)
        if it.get("role") in bank.vocab()["categories"]:
            probs += bank.claim_problems({**it, "category": it["role"]}, spec.get("facts") or {}, ctx)
    return probs


# ---------------------------------------------------------------- render

def _size(spec):
    s = spec["size"]
    w, h = (int(v) for v in s.split("x")) if isinstance(s, str) else s
    return w, h


class Renderer:
    """Draws the frames of one motion spec at its output size."""

    def __init__(self, spec, images):
        self.spec = spec
        self.w, self.h = _size(spec)
        self.s = self.w / REF
        self.images = {}
        for name in spec.get("panels") or {}:
            src = images.get(name) or images.get(OPTIONAL_PANELS.get(name, ""))
            if src:
                self.images[name] = Path(src)
        self._cache = {}
        self._clips = {}

    def _px(self, rect):
        return tuple(round(v * self.s) for v in rect)

    def _still(self, name, t):
        path = self.images[name]
        if path.suffix in VIDEO_SUFFIXES:
            return self._clip_frame(path, t)
        key = ("img", name)
        if key not in self._cache:
            with Image.open(path) as im:
                self._cache[key] = im.convert("RGBA")
        return self._cache[key]

    def _clip_frame(self, path, t):
        """The clip's frame at t (looped), sampled at CLIP_FPS and only while a
        layer showing it is visible, grabbed with Chromium (the frames tool's
        grabber: each frame is a seek, so fewer frames is most of the time)."""
        frames = self._clips.get(path)
        if frames is None:
            from ..corpus.similar import FrameGrabber
            tmp = Path(tempfile.mkdtemp(prefix="lp-timeline-"))
            users = [ly for ly in self.spec["layers"] if "kind" not in ly and self.images.get(ly.get("panel")) == path]
            n = math.ceil(self.spec["duration"] * CLIP_FPS) + 1
            need = [i for i in range(n) if any(value(ly["keys"], "opacity", i / CLIP_FPS, 1.0) > 0.003 for ly in users)]
            with FrameGrabber() as g:
                _, pngs = g.grab_many(path, lambda d: [((i / CLIP_FPS) % max(d or 1, 0.1), tmp / f"{i}.png") for i in need])
            frames = self._clips[path] = {i: Image.open(p).convert("RGBA") for i, p in zip(need, pngs)}
        i = round(t * CLIP_FPS)
        return frames.get(i) or frames[min(frames, key=lambda k: abs(k - i))]

    def _panel_sprite(self, ly, size, t):
        name = ly["panel"]
        if name not in self.images:
            return None
        clip = self.images[name].suffix in VIDEO_SUFFIXES
        key = ("panel", ly["id"], size, ly.get("degrade"))
        if not clip and key in self._cache:
            return self._cache[key]
        im = draw.fit(self._still(name, t), size)
        if ly.get("degrade"):
            im = degrade.degrade(im, ly["degrade"])
        im.putalpha(draw.rounded_mask(size, round(self.spec.get("radius", 40) * self.s)))
        if not clip:
            self._cache[key] = im
        return im

    def _chrome_sprite(self, ly, size, t):
        """A chrome block drawn at the sprite's size on a supersampled canvas."""
        item = {k: v for k, v in ly.items() if k != "keys"}
        typed = value(ly["keys"], "type", t, 1.0)
        if "text" in item and typed < 1:
            n = round(len(item["text"]) * typed)
            item["text"] = item["text"][:n] + ("|" if 0 < typed else "")
        tick = value(ly["keys"], "tick", t, None)
        if tick is not None:
            item["tick"] = tick
        key = ("chrome", ly["id"], size, item.get("text"), item.get("tick"))
        if key in self._cache:
            return self._cache[key]
        ss = 2
        cw, ch = max(1, size[0] * ss), max(1, size[1] * ss)
        canvas = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
        item["rect"] = (0, 0, cw, ch)
        radius = self.spec.get("radius", 40) if item.get("radius") is None else item["radius"]  # a measured item's own corner
        ctx = kinds.Ctx(s=self.s * ss, r=round(radius * self.s * ss), panels={}, type=item.get("type"))
        if item["kind"] == "product-card":
            self._product_card(canvas, item, ctx, t)
        elif item.get("text") == "" and kinds.KINDS[item["kind"]].text:
            pass  # nothing typed yet
        else:
            kinds.KINDS[item["kind"]].draw(canvas, item, ctx)
        out = canvas.resize(size, Image.LANCZOS)
        if len(self._cache) > 4000:
            self._cache = {k: v for k, v in self._cache.items() if k[0] in ("img", "panel")}
        self._cache[key] = out
        return out

    def _product_card(self, canvas, it, ctx, t):
        """The shop card of S11: an off-white card, the product (its cutout, or
        the photo) on top, name and price, the buy button. The strings come
        from the page copy."""
        w, h = canvas.size
        r = ctx.r
        draw.card(canvas, (0, 0, w, h), (255, 255, 255), r)
        well = (round(w * 0.05), round(h * 0.04), round(w * 0.95), round(h * 0.70))
        draw.card(canvas, well, (250, 244, 240), round(r * 0.7))
        if self.images.get("cutout") or self.images.get("photo"):
            ww, wh = well[2] - well[0], well[3] - well[1]
            im = draw.fit(self._still("cutout" if "cutout" in self.images else "photo", t), (ww, wh),
                          "contain" if "cutout" in self.images else "cover")
            im.putalpha(ImageChops.darker(im.getchannel("A"), draw.rounded_mask((ww, wh), round(r * 0.7))))
            canvas.alpha_composite(im, well[:2])
        fnt = draw.font(w * 0.062, 700)  # by width: the card grows taller than wide as it settles
        small = draw.font(w * 0.05, 500)
        dark = (20, 20, 20, 255)
        draw.wrapped_text(canvas, (round(w * 0.06), round(h * 0.74), round(w * 0.62), round(h * 0.90)), it.get("name", ""), dark, fnt, 1.15)
        draw.box_text(canvas, (round(w * 0.06), round(h * 0.89), round(w * 0.5), round(h * 0.97)), it.get("price", ""),
                      (0, 0, 0, 0), (110, 110, 110, 255), 0, small)
        bw = round(w * 0.30)
        draw.box_text(canvas, (w - bw - round(w * 0.05), round(h * 0.84), w - round(w * 0.05), round(h * 0.95)),
                      it.get("button", ""), (20, 20, 20, 255), (255, 255, 255, 255), round(h * 0.055), small)

    def frame(self, t):
        g = self.spec.get("ground") or [0, 0, 0]
        out = Image.new("RGBA", (self.w, self.h), tuple(g) + (255,))
        for ly in self.spec["layers"]:
            op = value(ly["keys"], "opacity", t, 1.0)
            rect = value(ly["keys"], "rect", t)
            if op <= 0.003 or rect is None:
                continue
            x0, y0, x1, y1 = self._px(rect)
            size = (max(1, x1 - x0), max(1, y1 - y0))
            sprite = self._chrome_sprite(ly, size, t) if "kind" in ly else self._panel_sprite(ly, size, t)
            if sprite is None:
                continue
            wipe = value(ly["keys"], "wipe", t, 1.0)
            if wipe < 1:  # the share shown, from the side the layer's wipe starts at
                way = ly.get("wipe_from", "left")
                span = sprite.width if way in ("left", "right") else sprite.height
                cut = round(span * wipe)
                if cut <= 0:
                    continue
                box = {"left": (0, 0, cut, sprite.height), "right": (sprite.width - cut, 0, sprite.width, sprite.height),
                       "top": (0, 0, sprite.width, cut), "bottom": (0, sprite.height - cut, sprite.width, sprite.height)}[way]
                shown = Image.new("RGBA", sprite.size, (0, 0, 0, 0))
                shown.paste(sprite.crop(box), box[:2])
                sprite = shown
            if op < 1:
                sprite = sprite.copy()
                sprite.putalpha(sprite.getchannel("A").point(lambda a: round(a * op)))
            layer = Image.new("RGBA", out.size, (0, 0, 0, 0))
            layer.paste(sprite, (x0, y0))
            out.alpha_composite(layer)
        return out

    def frames(self):
        fps = self.spec.get("fps", FPS)
        n = round(self.spec["duration"] * fps)
        for i in range(n):
            yield i, self.frame(i / fps)


# ---------------------------------------------------------------- encode

_ENCODE_JS = """async ({n, fps, w, h, bitrate, keyEvery}) => {
  const chunks = []; let failure = null;
  const enc = new VideoEncoder({
    output: (c) => {
      const b = new Uint8Array(c.byteLength); c.copyTo(b);
      let s = ''; for (let i = 0; i < b.length; i += 0x8000) s += String.fromCharCode.apply(null, b.subarray(i, i + 0x8000));
      chunks.push([c.timestamp, c.type === 'key', btoa(s)]);
    },
    error: (e) => { failure = String(e); },
  });
  enc.configure({codec: 'vp09.00.10.08', width: w, height: h, bitrate, framerate: fps, latencyMode: 'quality'});
  for (let i = 0; i < n; i++) {
    const bmp = await createImageBitmap(await (await fetch(`/f/${i}.png`)).blob());
    const vf = new VideoFrame(bmp, {timestamp: Math.round(i * 1e6 / fps), duration: Math.round(1e6 / fps)});
    enc.encode(vf, {keyFrame: i % keyEvery === 0}); vf.close(); bmp.close();
    while (enc.encodeQueueSize > 6) await new Promise(r => setTimeout(r, 1));
  }
  await enc.flush();
  if (failure) throw new Error(failure);
  return chunks;
}"""


def encode(frames_dir, n, fps, size):
    """VP9 chunks [(timestamp µs, is key, bytes)] of frames_dir/<i>.png via
    Chromium's WebCodecs (a secure-context page served through a route)."""
    from playwright.sync_api import sync_playwright
    frames_dir = Path(frames_dir)

    def handle(route):
        path = route.request.url.split("lp.local", 1)[1]
        if path.startswith("/f/"):
            route.fulfill(status=200, body=(frames_dir / path[3:]).read_bytes(), headers={"Content-Type": "image/png"})
        else:
            route.fulfill(status=200, body="<!doctype html><body></body>", headers={"Content-Type": "text/html"})

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        try:
            page = browser.new_page()
            page.route("https://lp.local/**", handle)
            page.goto("https://lp.local/")
            raw = page.evaluate(_ENCODE_JS, {"n": n, "fps": fps, "w": size[0], "h": size[1], "bitrate": BITRATE,
                                             "keyEvery": round(KEY_EVERY * fps)})
        finally:
            browser.close()
    return [(ts, key, base64.b64decode(data)) for ts, key, data in raw]


def _vint(n):
    for length in range(1, 9):
        if n < (1 << (7 * length)) - 1:
            return ((1 << (7 * length)) | n).to_bytes(length, "big")
    raise ValueError("EBML size too large")


def _el(eid, payload):
    return eid.to_bytes((eid.bit_length() + 7) // 8, "big") + _vint(len(payload)) + payload


def _uint(eid, v):
    return _el(eid, v.to_bytes(max(1, (v.bit_length() + 7) // 8), "big"))


def mux(chunks, size, duration_s):
    """A WebM (one VP9 track) from encoded chunks: EBML header, Info with the
    real Duration, Tracks, one Cluster per keyframe, and Cues, so a browser
    reads the length and seeks (the frames tool and lp-bench do both)."""
    ebml = _el(0x1A45DFA3, _uint(0x4286, 1) + _uint(0x42F7, 1) + _uint(0x42F2, 4) + _uint(0x42F3, 8)
               + _el(0x4282, b"webm") + _uint(0x4287, 4) + _uint(0x4285, 2))
    info = _el(0x1549A966, _uint(0x2AD7B1, 1_000_000) + _el(0x4489, struct.pack(">d", duration_s * 1000))
               + _el(0x4D80, b"lp-compose") + _el(0x5741, b"lp-compose timeline"))
    video = _el(0xE0, _uint(0xB0, size[0]) + _uint(0xBA, size[1]))
    tracks = _el(0x1654AE6B, _el(0xAE, _uint(0xD7, 1) + _uint(0x73C5, 1) + _uint(0x83, 1) + _el(0x86, b"V_VP9")
                                  + _uint(0x9C, 0) + video))
    body = info + tracks
    clusters, cues, cluster, base = b"", [], b"", None
    for ts, key, data in chunks:
        ms = round(ts / 1000)
        if key or base is None or ms - base > 30000:
            if base is not None:
                clusters += _el(0x1F43B675, cluster)
            base, cluster = ms, _uint(0xE7, ms)
            if key:
                cues.append((ms, len(body) + len(clusters)))
        cluster += _el(0xA3, b"\x81" + struct.pack(">h", ms - base) + bytes([0x80 if key else 0]) + data)
    if base is not None:
        clusters += _el(0x1F43B675, cluster)
    cue_el = _el(0x1C53BB6B, b"".join(_el(0xBB, _uint(0xB3, ms) + _el(0xB7, _uint(0xF7, 1) + _uint(0xF1, pos)))
                                      for ms, pos in cues))
    return ebml + _el(0x18538067, body + clusters + cue_el)


def render(spec, images, out, poster=None, keep_frames=None):
    """Render a motion spec to a WebM at `out` (and its last frame to
    `poster`). `images` maps panel names to files (a clip for a video panel).
    Returns (frame count, duration s)."""
    probs = [p for p in validate(spec) if "is empty" in p or "not drawable" in p or "preset" in p or "size" in p]
    if probs:
        sys.exit("lp-compose: " + "; ".join(probs))
    r = Renderer(spec, images)
    missing = [n for n in spec.get("panels") or {} if n not in r.images and n not in OPTIONAL_PANELS]
    if missing:
        sys.exit(f"lp-compose: timeline panel(s) {', '.join(missing)} have no image (--image <panel>=<path>)")
    fps = spec.get("fps", FPS)
    with tempfile.TemporaryDirectory() as d:
        d = Path(keep_frames) if keep_frames else Path(d)
        d.mkdir(parents=True, exist_ok=True)
        last = None
        n = 0
        for i, fr in r.frames():
            fr.convert("RGB").save(d / f"{i}.png", compress_level=1)
            last, n = fr, i + 1
        chunks = encode(d, n, fps, (r.w, r.h))
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    Path(out).write_bytes(mux(chunks, (r.w, r.h), n / fps))
    if poster and last is not None:
        last.convert("RGB").save(poster)
    return n, n / fps


def describe():
    lines = ["Timeline presets (1:1 callout videos, rendered locally, 0 credits):"]
    for name, (fn, panels, strings) in PRESETS.items():
        doc = " ".join((fn.__doc__ or "").split())
        spec = fn([f"<{s}>" for s in strings], {"tools": ["enhance"], "tool": "enhance"})
        lines.append(f"  {name} ({spec['duration']:.1f} s): {doc}")
        lines += [f"    panel {p}: {what}" for p, what in panels.items()]
        lines.append(f"    page strings, in `> chrome:` order: {', '.join(strings)}")
        roles_used = sorted({ly['role'] for ly in spec['layers']})
        lines.append(f"    blocks by role: {', '.join(roles_used)}")
    return "\n".join(lines)


def load(path):
    return yaml.safe_load(Path(path).read_text()) or {}
