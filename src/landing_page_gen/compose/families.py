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
MAGENTA = (225, 30, 224)  # Picsart accent #e01ee0 (was (181,23,170), an off measurement)
CHECKER = ((58, 58, 60), (42, 42, 44))

# panels: name -> rect (x0, y0, x1, y1), optional fit ("cover" | "contain") and
# under ("checkerboard"). chrome: drawn after the panels except kind "card";
# a spec overrides an item by id and drops one with `omit`.
FAMILIES = {
    "before-after": {
        # Ground is transparent on every corpus composite (alpha-0 gutters); the
        # page section supplies the surround. The 1:1 stacked pair is the rare
        # form (1/20) but is what a callout-1:1 slot needs, so it stays the
        # default; the modal WIDE card (14/20, e.g. 08385997 ai-image-enhancer
        # S09, c5715e9b image-upscale S07) is the `wide` variant for 2:1 slots.
        "aspect": (1, 1),
        "ground": {"fill": None},
        "radius": 40,
        "panels": {
            "before": {"rect": (0, 0, 604, 632)},
            "after": {"rect": (0, 664, 604, 1296)},
            "result": {"rect": (636, 0, 1600, 1600)},
        },
        "chrome": [
            {"id": "before-pill", "kind": "pill", "at": "before", "corner": "bl", "text": "Before", "style": "translucent"},
            {"id": "after-pill", "kind": "pill", "at": "after", "corner": "bl", "text": "After", "style": "translucent"},
            {"id": "tile", "kind": "tile", "rect": (0, 1328, 604, 1600), "icon": "enlarge"},
        ],
        "variants": {
            # modal wide card, 1060x504 native scaled to 1600 wide (08385997,
            # c5715e9b): before + icon tile left, result right, solid-dark pills,
            # "After" on the RESULT. For 21:10 (callout-2:1) slots.
            "wide": {
                "aspect": (21, 10),
                "panels": {
                    "before": {"rect": (24, 24, 610, 519)},
                    "result": {"rect": (622, 24, 1576, 737)},
                },
                "chrome": [
                    {"id": "before-pill", "kind": "pill", "at": "before", "corner": "bl", "text": "Before", "style": "solid-dark"},
                    {"id": "after-pill", "kind": "pill", "at": "result", "corner": "bl", "text": "After", "style": "solid-dark"},
                    {"id": "tile", "kind": "tile", "rect": (24, 531, 610, 737), "icon": "enlarge"},
                ],
            },
        },
    },
    "crop-frame": {
        # Ground is BLACK (10/13 in-family assets, all crop-image pages;
        # 5f91c6aa resize-image S07 is the geometry model). The source panel is
        # dimmed under white brackets, and the top-left mark is a bare white
        # outline icon on the ground, not a filled tile.
        "aspect": (1, 1),
        "ground": {"fill": BLACK},
        "radius": 40,
        "panels": {
            "source": {"rect": (0, 392, 784, 1600), "dim": 0.35},
            "result": {"rect": (816, 0, 1600, 1600)},
        },
        "chrome": [
            {"id": "icon", "kind": "icon", "rect": (232, 100, 552, 264), "icon": "enlarge"},
            {"id": "brackets", "kind": "brackets", "at": "source", "frac": (0.30, 0.22, 0.70, 0.66), "label": "x2"},
        ],
    },
    "cutout-checkerboard": {
        # Ground is transparent (alpha-0 gutters on every 1:1 asset; the page
        # supplies black/white). Skeleton is real (4604e99a batch-photo-editor
        # S06): two checker panels left, magenta badges, big light result, dark
        # button. `checker_tone` is dark by default (batch/sticker pages); set
        # it light on background-remover/-changer pages. (The corpus's
        # partial-fill checker — photo backdrop kept on part of the panel — needs
        # the pre-remove_bg frame as a second input; deferred, see STANDARD.md.)
        "aspect": (1, 1),
        "ground": {"fill": None},
        "radius": 40,
        "panels": {
            "cutout-a": {"rect": (0, 0, 513, 784), "under": "checkerboard", "fit": "contain"},
            "cutout-b": {"rect": (0, 816, 513, 1600), "under": "checkerboard", "fit": "contain"},
            "result": {"rect": (545, 0, 1600, 1360)},
        },
        "chrome": [
            {"id": "badge-a", "kind": "badge", "at": "cutout-a", "corner": "tr"},
            {"id": "badge-b", "kind": "badge", "at": "cutout-b", "corner": "tr"},
            {"id": "button", "kind": "pill", "rect": (545, 1390, 1600, 1600), "text": "Add to bag", "style": "solid-dark"},
        ],
    },
    "template-mockup": {
        # Ground is transparent (12/14 corpus assets; the page supplies
        # white/black). The `photo` panel IS the finished card design filling the
        # card interior — the model renders the poster/headline typography inside
        # it (never blank bars, which appear in 0/14). Left column is 3 MIXED
        # tiles (one magenta accent, not 4 uniform black): geometry from
        # c3461329, b2749949. /black is the same artwork exported on a dark page
        # (a fill override, not a separate drawing). The selection-frame chrome,
        # swatch-stripe tile and /editor exploded view are deferred (new
        # primitives; see STANDARD.md).
        "aspect": (1, 1),
        "ground": {"fill": None},
        "radius": 40,
        "panels": {
            "photo": {"rect": (600, 200, 1400, 1400)},
        },
        "chrome": [
            {"id": "card", "kind": "card", "rect": (556, 152, 1444, 1448), "fill": (43, 20, 90)},
            {"id": "tile-1", "kind": "tile", "rect": (152, 152, 532, 532), "icon": "sparkle", "fill": MAGENTA},
            {"id": "tile-2", "kind": "tile", "rect": (152, 560, 532, 940), "icon": "crop", "fill": (0, 0, 0)},
            {"id": "swatch", "kind": "tile", "rect": (152, 968, 532, 1348), "fill": (90, 90, 96)},
        ],
    },
    "dark-composite": {
        "aspect": (1, 1),
        "ground": {"fill": BLACK},
        "radius": 40,
        "panels": {
            "photo": {"rect": (570, 150, 1450, 1450)},
        },
        "chrome": [
            # Column on the LEFT (x150-530, 380 wide), three boxes; the main
            # card sits right, inset 150. Evidence: 21cdafd9, 8031c225, d5d56eb0,
            # f57c774f, bd014004. tile-1 = a tool glyph (#1c1c1e); tile-2 = the
            # page's ACTIVE tool, a MAGENTA accent (8/13 assets carry one); tile-3
            # = a flat colour-swatch tile. No "4K" chip — a resolution/format chip
            # is in 0/13 of the current population (opt-in via `chrome: {chip}`).
            {"id": "tile-1", "kind": "tile", "rect": (150, 150, 530, 530), "icon": "sparkle", "fill": (28, 28, 30)},
            {"id": "tile-2", "kind": "tile", "rect": (150, 570, 530, 950), "icon": "crop", "fill": MAGENTA},
            {"id": "tile-3", "kind": "tile", "rect": (150, 990, 530, 1450), "fill": (90, 90, 96)},
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
    # "type a prompt, get this": a dark prompt column with a Generate button on
    # the left, the result photo on the right (22f9b181 ai-models--kling-v2-1,
    # 802fe719 ai-models--qwen-image). The prompt sentence is chrome text the
    # manager fills; the result carries none.
    "prompt-card": {
        "aspect": (1, 1),
        "ground": {"fill": BLACK},
        "radius": 40,
        "panels": {
            "result": {"rect": (700, 100, 1500, 1500)},
        },
        "chrome": [
            {"id": "prompt", "kind": "card", "rect": (100, 100, 620, 1500), "fill": (30, 30, 32)},
            {"id": "prompt-text", "kind": "text", "rect": (160, 200, 560, 640), "text": ""},
            {"id": "generate", "kind": "pill", "rect": (160, 1320, 560, 1440), "text": "Generate", "style": "solid-light"},
        ],
    },
    # two outputs of one prompt, side by side, a round VS mark on the seam
    # (compare-models cards). Model pills and size chips are a later variant.
    "vs-two-up": {
        "aspect": (1, 1),
        "ground": {"fill": (242, 242, 244)},
        "radius": 40,
        "panels": {
            "left": {"rect": (40, 40, 780, 1440)},
            "right": {"rect": (820, 40, 1560, 1440)},
        },
        "chrome": [
            {"id": "vs", "kind": "round-badge", "rect": (712, 712, 888, 888), "text": "VS"},
        ],
    },
    # the result shown "in use": the source photo on the left, a mock profile /
    # social card built from it on the right (7a980105 background-remover S08).
    # The card is placeholder chrome — never a real network's layout or names.
    "mockup-card": {
        "aspect": (1, 1),
        "ground": {"fill": BLACK},
        "radius": 40,
        "panels": {
            "photo": {"rect": (80, 120, 760, 1480)},
        },
        "chrome": [
            {"id": "post", "kind": "profile-card", "rect": (820, 120, 1520, 1480), "fill": (30, 30, 32)},
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
