"""Composite-card templates, one dict per style family of
`.claude/skills/picsart-workflows/style-families.md` that has chrome.
Geometry is in reference pixels at REF (the corpus originals are 1600 px
square) and is scaled to the spec's size at render time. The worker supplies
the panel images; the family supplies the layout and the chrome."""

import math

REF = 1600
RATIOS = ("1:1", "16:9", "9:16", "3:4", "4:3", "2:3", "21:9")  # gemini-3-pro-image

BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
MAGENTA = (181, 23, 170)
CHECKER = ((58, 58, 60), (42, 42, 44))

# panels: name -> rect (x0, y0, x1, y1), optional fit ("cover" | "contain") and
# under ("checkerboard"). chrome: drawn after the panels except kind "card";
# a spec overrides an item by id and drops one with `omit`.
FAMILIES = {
    "before-after": {
        "aspect": (1, 1),
        "ground": {"fill": BLACK},
        "radius": 40,
        "panels": {
            "before": {"rect": (0, 0, 600, 630)},
            "after": {"rect": (0, 660, 600, 1290)},
            "result": {"rect": (630, 0, 1600, 1600)},
        },
        "chrome": [
            {"id": "before-pill", "kind": "pill", "at": "before", "corner": "bl", "text": "Before", "style": "translucent"},
            {"id": "after-pill", "kind": "pill", "at": "after", "corner": "bl", "text": "After", "style": "translucent"},
            {"id": "tile", "kind": "tile", "rect": (0, 1320, 600, 1600), "icon": "enlarge"},
        ],
    },
    "crop-frame": {
        "aspect": (1, 1),
        "ground": {"fill": None},
        "radius": 40,
        "panels": {
            "source": {"rect": (0, 400, 780, 1600)},
            "result": {"rect": (820, 0, 1600, 1600)},
        },
        "chrome": [
            {"id": "tile", "kind": "tile", "rect": (0, 0, 780, 360), "icon": "enlarge"},
            {"id": "brackets", "kind": "brackets", "at": "source", "frac": (0.3, 0.22, 0.7, 0.66), "label": "x2"},
        ],
    },
    "cutout-checkerboard": {
        "aspect": (1, 1),
        "ground": {"fill": BLACK},
        "radius": 40,
        "panels": {
            "cutout-a": {"rect": (0, 0, 510, 780), "under": "checkerboard", "fit": "contain"},
            "cutout-b": {"rect": (0, 820, 510, 1600), "under": "checkerboard", "fit": "contain"},
            "result": {"rect": (560, 40, 1600, 1330)},
        },
        "chrome": [
            {"id": "badge-a", "kind": "badge", "at": "cutout-a", "corner": "tr"},
            {"id": "badge-b", "kind": "badge", "at": "cutout-b", "corner": "tr"},
            {"id": "button", "kind": "pill", "rect": (590, 1370, 1600, 1560), "text": "Add to bag", "style": "solid-dark"},
        ],
    },
    "template-mockup": {
        "aspect": (1, 1),
        "ground": {"fill": WHITE},
        "radius": 40,
        "panels": {
            "photo": {"rect": (580, 660, 1320, 1320)},
        },
        "chrome": [
            {"id": "card", "kind": "card", "rect": (520, 240, 1380, 1380), "fill": (43, 20, 90)},
            {"id": "headline", "kind": "headline", "rect": (580, 300, 1320, 600), "text": ""},
            {"id": "tile-1", "kind": "tile", "rect": (240, 240, 500, 500), "icon": "sparkle"},
            {"id": "tile-2", "kind": "tile", "rect": (240, 520, 500, 780), "icon": "crop"},
            {"id": "tile-3", "kind": "tile", "rect": (240, 800, 500, 1060), "icon": "enlarge"},
            {"id": "tile-4", "kind": "tile", "rect": (240, 1080, 500, 1340), "icon": "check"},
        ],
    },
    "dark-composite": {
        "aspect": (1, 1),
        "ground": {"fill": BLACK},
        "radius": 40,
        "panels": {
            "photo": {"rect": (0, 0, 1180, 1600)},
        },
        "chrome": [
            # tiles a step lighter than the black card, else only the glyphs show (live-3 review of S01/S04/S05)
            {"id": "tile-1", "kind": "tile", "rect": (1220, 0, 1600, 380), "icon": "sparkle", "fill": (28, 28, 30)},
            {"id": "tile-2", "kind": "tile", "rect": (1220, 420, 1600, 800), "icon": "crop", "fill": (28, 28, 30)},
            {"id": "chip", "kind": "label", "rect": (1220, 1220, 1600, 1600), "text": "4K"},
        ],
        # Devices (`variant:` in the spec; `> device:` in the skeleton): the panel
        # arrangement that tells the section's story. A key a variant omits is
        # inherited from the family. Geometry measured on the Recraft originals
        # (ai-models--recraft-v4-styles-pro-vector S01 86f73fc9, S06 3d65a628,
        # S07 a3502ec3), column on the left as on every Recraft card.
        "variants": {
            # references in, style-locked output out: mark tile, chip, two same-style thumbnails left, the output right
            "reference-thumbs": {
                "panels": {
                    "photo": {"rect": (410, 0, 1600, 1600)},
                    "thumb-a": {"rect": (0, 816, 375, 1192)},
                    "thumb-b": {"rect": (0, 1224, 375, 1600)},
                },
                "chrome": [
                    {"id": "tile-1", "kind": "tile", "rect": (0, 0, 375, 375), "icon": "sparkle", "fill": (28, 28, 30)},
                    {"id": "chip", "kind": "label", "rect": (0, 420, 375, 560), "text": "4K"},
                ],
            },
            # chosen over other models: a dark list card (blank rows, one highlighted) above two thumbnails, the output right
            "model-picker": {
                "panels": {
                    "photo": {"rect": (700, 0, 1600, 1600)},
                    "thumb-a": {"rect": (0, 667, 667, 1120)},
                    "thumb-b": {"rect": (0, 1147, 667, 1600)},
                },
                "chrome": [
                    {"id": "list", "kind": "list-panel", "rect": (0, 72, 667, 576), "rows": 4, "active": 1, "active_text": ""},
                ],
            },
            # two outputs of one style side by side: panel-a top left with the mark tile under it, panel-b right
            "two-up": {
                "panels": {
                    "photo": {"rect": (0, 0, 667, 933)},
                    "photo-b": {"rect": (720, 0, 1600, 1600)},
                },
                "chrome": [
                    {"id": "tile-1", "kind": "tile", "rect": (0, 966, 667, 1600), "icon": "sparkle", "fill": (28, 28, 30)},
                ],
            },
        },
    },
    # A photo filling the slot with the tool's dark adjustment panel laid over
    # its lower right (hsl-color S03) and, on heroes, a round tool badge with a
    # label pill top right (hsl-color S01). Panel rect `None` means the whole
    # canvas at whichever of `aspects` the spec's size has; the spec omits
    # `tool-pill` on cards and `panel` on the hero, and `ground: tilted` stacks
    # the card over a plain one on the page's white (S03-m2, S03-m4).
    "panel-overlay": {
        "aspect": (4, 3),
        "aspects": ((4, 3), (5, 4)),
        "ground": {"fill": None},
        "radius": 40,
        "panels": {
            "photo": {"rect": None},
        },
        "chrome": [
            {"id": "panel", "kind": "adjust-panel", "rect": (680, 300, 1490, 900), "title": "HSL", "chips": 8, "active": 1,
             "sliders": [["Hue", 28], ["Saturation", -26], ["Lightness", 30]]},
            {"id": "tool-pill", "kind": "tool-pill", "rect": (1080, 120, 1520, 620), "text": "HSL", "icon": "wheel"},
        ],
    },
}


def ratio_value(r):
    a, b = r.split(":")
    return int(a) / int(b)


def nearest_ratio(w, h):
    """The generate `aspectRatio` closest to a panel's shape."""
    t = math.log(w / h)
    return min(RATIOS, key=lambda r: abs(math.log(ratio_value(r)) - t))


def aspect_label(w, h):
    g = math.gcd(w, h)
    return f"{w // g}:{h // g}"
