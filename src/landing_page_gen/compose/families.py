"""Composite-card templates, one skeleton per style family of
`.claude/skills/picsart-workflows/style-families.md` that has chrome.
Geometry is in reference pixels at REF (the corpus originals are 1600 px
square) and is scaled to the spec's size at render time. A skeleton says where
things go: its background, the panels the worker generates, and the slots the
worker fills with blocks from the bank (assets/blocks.yaml, compose/bank.py)."""

import math
from pathlib import Path

import yaml

REF = 1600
RATIOS = ("1:1", "3:2", "2:3", "16:9", "9:16", "4:3", "3:4")  # gpt-image-2.5-sunburst (no 21:9: wide panels generate at 16:9 and crop)

BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
MAGENTA = (225, 30, 224)  # Picsart accent #e01ee0 (was (181,23,170), an off measurement)
CHECKER = ((58, 58, 60), (42, 42, 44))
# the finer checker of the template-mockup /editor tile, measured: light (5/8, a
# translucent grey/white pair, c491d842, a591037a, d4507d92) and dark (219070b9)
EDITOR_CHECKER = {"light": ((167, 167, 171, 64), (255, 255, 255, 64)), "dark": ((65, 64, 66), (35, 31, 32))}

# A template is a SKELETON: where things go, never what they say.
#
# - `background`: what lp-compose draws under everything, never generated and
#   never a block: the `ground` (the canvas: transparent lets the page section
#   show) and fixed `surfaces` (the rounded card a design is printed on, the
#   dark card a prompt sits on, a checker behind a cut-out). A variant inherits
#   its family's ground, never its surfaces.
# - `panels`: the only place a model's pixels go. name -> rect (x0, y0, x1, y1;
#   None fills the slot), fit ("cover" | "contain"), `under` ("checkerboard"),
#   and `holds`: `scene` (a whole picture with its own backdrop), `design` (a
#   finished card or poster, typography per `> text:`) or `subject` (a cut-out
#   on transparency: the template's background shows around it). A panel with
#   `detail_of` is cropped from another by lp-compose.
# - `slots`: where chrome goes. Each takes at most one block of the bank
#   (assets/blocks.yaml) whose category it `accepts` and that can draw in its
#   `shape`; `required` slots must be filled, an empty optional slot draws
#   nothing. The slot's geometry (`rect`, `at` + `corner`, `at` + `frac`, `at` +
#   `split`) and look (`fill`, `style`, `font`, ...) are the template's; the
#   block brings the content. `state` marks a state-label slot's panel.
# - `exemplar`: the blocks the measured corpus original showed in each slot.
#   It is a record, NEVER a default: lp-compose draws a slot only from a pick
#   (the worker's blocks-<slot>.yaml). It feeds the golden renders
#   (tests/golden_compose.py), the keep-clear footprint and `--describe`. It
#   carries no page's words or numbers (generic interface labels at most):
#   a new picture's blocks are written for that picture, never copied.
FAMILIES = {
    "before-after": {
        # Ground is transparent on every corpus composite (alpha-0 gutters and
        # margin, measured 15/15; the page section supplies the surround). The
        # MODAL card is the WIDE ~2.1:1 layout — 11 of 15 genuine before+result+
        # tile composites, 16 of 21 by aspect (e.g. 08385997 ai-image-enhancer
        # S09, c5715e9b image-upscale S07, f223c881 video-enhancer S10). Native
        # 1060x504 scaled x1.5094 to REF width: margin 16->24, gutter 8->12.
        # before + a box left, result right, solid-dark pills, "After" on the
        # RESULT. The rare 1:1 stacked pair (69ed3f5c image-enlarger S08) is
        # `variant: stacked-square`.
        "aspect": (21, 10),                         # 1060x504 = 2.103:1
        "radius": 40,
        "background": {"ground": {"fill": None}, "surfaces": []},
        "panels": {
            "before": {"rect": (24, 24, 610, 519), "holds": "scene"},    # 388x328 native
            "result": {"rect": (622, 24, 1576, 737), "holds": "scene"},  # 632x472 native
        },
        "slots": [
            {"id": "before-pill", "shape": "pill", "accepts": ["state-label"], "state": "before", "required": True,
             "at": "before", "corner": "bl", "style": "solid-dark"},
            {"id": "after-pill", "shape": "pill", "accepts": ["state-label"], "state": "after", "required": True,
             "at": "result", "corner": "bl", "style": "solid-dark"},
            # the box under the Before: the tool, the model or a spec (corpus: attribution 34, tool 22, spec 15)
            {"id": "tile", "shape": "tile", "accepts": ["tool", "attribution", "spec"], "rect": (24, 531, 610, 737)},
        ],
        "exemplar": {"source": "08385997 ai-image-enhancer S09", "fills": {
            "before-pill": {"block": "state-pill"}, "after-pill": {"block": "state-pill"},
            "tile": {"block": "tool-tile", "tool": "upscale"}}},
        "variants": {
            # the 1:1 stacked pair, measured from 69ed3f5c (image-enlarger S08):
            # before + after stacked left with a box below, result (often an
            # applied mockup of the after image) right. For callout-1:1 slots.
            # Translucent pills (69ed3f5c, bcc56313).
            "stacked-square": {
                "aspect": (1, 1),
                "panels": {
                    "before": {"rect": (0, 0, 604, 632), "holds": "scene"},
                    "after": {"rect": (0, 664, 604, 1296), "holds": "scene"},
                    "result": {"rect": (636, 0, 1600, 1600), "holds": "scene"},
                },
                "slots": [
                    {"id": "before-pill", "shape": "pill", "accepts": ["state-label"], "state": "before", "required": True,
                     "at": "before", "corner": "bl", "style": "translucent"},
                    {"id": "after-pill", "shape": "pill", "accepts": ["state-label"], "state": "after", "required": True,
                     "at": "after", "corner": "bl", "style": "translucent"},
                    {"id": "tile", "shape": "tile", "accepts": ["tool", "attribution", "spec"], "rect": (0, 1328, 604, 1600)},
                ],
                "exemplar": {"source": "69ed3f5c image-enlarger S08", "fills": {
                    "before-pill": {"block": "state-pill"}, "after-pill": {"block": "state-pill"},
                    "tile": {"block": "tool-tile", "tool": "upscale"}}},
            },
            # one picture per slot, the pair split over two slots of a section
            # (ai-image-enhancer S01/S08/S12, the --unblur/--denoise/--sharpen/
            # --unpixelate/--photo-restoration heroes, hd-photo-converter: 480x480
            # each): the Before slot is the After degraded (`degrade:`, the page's
            # fault) with a dark pill bottom left; the After slot is the generated
            # picture with its pill bottom right. The plan sets the slot's state.
            "pill": {
                "aspect": (1, 1),
                "panels": {"photo": {"rect": (0, 0, 1600, 1600), "holds": "scene"}},
                "slots": [
                    {"id": "state", "shape": "pill", "accepts": ["state-label"], "required": True, "at": "photo",
                     "corner": "bl", "style": "solid-dark", "font": "pill-lg", "pad": (80, 34), "inset": 75},  # 15c37bff: 440x150 @ 75
                ],
                "exemplar": {"source": "15c37bff ai-image-enhancer S01", "fills": {
                    "state": {"block": "state-pill", "text": "Before"}}},
            },
            # the gallery compare card (ai-image-enhancer S14, six 360x226 cards;
            # hd-photo-converter, image-upscale): one picture, degraded left of a
            # centred divider, clean right of it, a round two-arrow knob on the seam
            "compare-slider": {
                "aspect": (16, 10),
                "panels": {"photo": {"rect": (0, 0, 1600, 1000), "degrade": {"until": 0.5}, "holds": "scene"}},
                "slots": [
                    {"id": "handle", "shape": "seam", "accepts": ["comparison"], "required": True, "at": "photo", "split": 0.5},
                ],
                "exemplar": {"source": "ai-image-enhancer S14", "fills": {"handle": {"block": "compare-handle"}}},
            },
        },
    },
    "crop-frame": {
        # Ground is BLACK (10/13 in-family assets, all crop-image pages;
        # 5f91c6aa resize-image S07 is the geometry model). The source panel is
        # dimmed under white brackets, and the top-left mark is a bare white
        # outline glyph on the ground, not a filled tile.
        "aspect": (1, 1),
        "radius": 40,
        "background": {"ground": {"fill": BLACK}, "surfaces": []},
        "panels": {
            "source": {"rect": (0, 392, 784, 1600), "dim": 0.35, "holds": "scene"},
            "result": {"rect": (816, 0, 1600, 1600), "holds": "scene"},
        },
        "slots": [
            {"id": "icon", "shape": "tile", "accepts": ["tool", "spec", "attribution"], "rect": (232, 100, 552, 264)},
            {"id": "brackets", "shape": "frame", "accepts": ["editor"], "required": True, "at": "source",
             "frac": (0.30, 0.22, 0.70, 0.66)},
        ],
        "exemplar": {"source": "5f91c6aa resize-image S07", "fills": {
            "icon": {"block": "tool-icon", "tool": "upscale"}, "brackets": {"block": "crop-brackets", "label": "x2"}}},
        "variants": {
            # The crop-image namesake signature (4c0b8b9b S01 hero, c78690a2 S05,
            # d93605b1 S06, 24e4540f S09): two overlapping rounded photo cards on a
            # TRANSPARENT ground (measured from alpha: 0.23-0.41 alpha-0 gutters, not
            # black), the back card under a rule-of-thirds crop grid, the front card
            # the clean result, a round badge on the seam, and a dark ratio/size box.
            "crop-grid": {
                "background": {"ground": {"fill": None}},
                "panels": {
                    "source": {"rect": (600, 110, 1510, 1120), "holds": "scene"},   # back, gridded
                    "result": {"rect": (90, 560, 850, 1470), "holds": "scene"},     # front, clean, overlaps the corner
                },
                "slots": [
                    # interior thirds lines (grid: True) inset to the back card's outer ~65% so
                    # the front card does not cross it (639e11c1 lines at 1/3, 2/3; c78690a2 613-1463 x 233-1075)
                    {"id": "grid", "shape": "frame", "accepts": ["editor"], "required": True, "at": "source",
                     "frac": (0.30, 0.09, 0.95, 0.90), "grid": True},
                    # a disc d~260 on the seam (4c0b8b9b d278 @ (230,508); c78690a2 d256 left edge)
                    {"id": "crop-badge", "shape": "seam", "accepts": ["tool"], "rect": (470, 430, 730, 690)},
                    # the dark ratio/size box bottom-right (c78690a2 card 496x404 @ (1100,884))
                    {"id": "ratio", "shape": "tile", "accepts": ["spec"], "rect": (1090, 900, 1560, 1300)},
                ],
                "exemplar": {"source": "4c0b8b9b crop-image S01", "fills": {
                    "grid": {"block": "crop-brackets"}, "crop-badge": {"block": "tool-disc", "tool": "crop"},
                    "ratio": {"block": "spec-label", "text": "1:1"}}},
            },
            # the image stretcher (6cdb5d19 resize-image--stretcher S05, 1600 px,
            # transparent): top row, the narrow source on a checker board beside
            # the same scene stretched wide, 32 px gutter; below, the stretched
            # picture in use full width. No chrome of its own (the original's
            # side arrows are left out until the bank has them).
            "stretch": {
                "background": {"ground": {"fill": None},
                               "surfaces": [{"id": "checker", "kind": "checker", "tone": "dark", "rect": (0, 0, 784, 572)}]},
                "panels": {
                    "source": {"rect": (232, 0, 552, 572), "holds": "scene"},
                    "result": {"rect": (816, 0, 1600, 572), "holds": "scene"},
                    "applied": {"rect": (0, 602, 1600, 1600), "holds": "scene"},
                },
                "slots": [],
                "exemplar": {"source": "6cdb5d19 resize-image--stretcher S05", "fills": {}},
            },
        },
    },
    "cutout-checkerboard": {
        # Ground is transparent (alpha-0 gutters on every 1:1 asset; the page
        # supplies black/white). Skeleton is real (4604e99a batch-photo-editor
        # S06): two cut-outs on checker panels left, badges on them, the big
        # light result, a dark button. (The partial-fill checker — the photo
        # backdrop kept on part of the panel — is deferred, see STANDARD.md.)
        "aspect": (1, 1),
        "radius": 40,
        "background": {"ground": {"fill": None}, "surfaces": []},
        "panels": {
            "cutout-a": {"rect": (0, 0, 513, 784), "under": "checkerboard", "fit": "contain", "holds": "subject"},
            "cutout-b": {"rect": (0, 816, 513, 1600), "under": "checkerboard", "fit": "contain", "holds": "subject"},
            "result": {"rect": (545, 0, 1600, 1360), "holds": "scene"},
        },
        "slots": [
            {"id": "badge-a", "shape": "badge", "accepts": ["editor", "tool"], "at": "cutout-a", "corner": "tr"},
            {"id": "badge-b", "shape": "badge", "accepts": ["editor", "tool"], "at": "cutout-b", "corner": "tr"},
            {"id": "button", "shape": "pill", "accepts": ["action"], "rect": (545, 1390, 1600, 1600), "style": "solid-dark"},
        ],
        "exemplar": {"source": "4604e99a batch-photo-editor S06", "fills": {
            "badge-a": {"block": "batch-check"}, "badge-b": {"block": "batch-check"},
            "button": {"block": "cta-button", "text": "Add to bag"}}},
        "variants": {
            # the editor transform box over the first cutout (17a18112 meme-generator
            # S10, 361c2368 ai-image-extender S05, 16410f3b whatsapp-sticker-maker S05,
            # 1fa729f4 background-tools S13): white square-cornered frame, disc
            # handles at the edge midpoints, X / rotate / resize discs outside the
            # corners. Frame 6 px, handles d40 at REF (972da313). frac is inset from
            # 0.16-0.84 so the discs stay on the 513-wide panel and clear of badge-a.
            "selection-frame": {
                "slots": [
                    {"id": "badge-a", "shape": "badge", "accepts": ["editor", "tool"], "at": "cutout-a", "corner": "tr"},
                    {"id": "badge-b", "shape": "badge", "accepts": ["editor", "tool"], "at": "cutout-b", "corner": "tr"},
                    {"id": "button", "shape": "pill", "accepts": ["action"], "rect": (545, 1390, 1600, 1600), "style": "solid-dark"},
                    {"id": "select", "shape": "frame", "accepts": ["editor"], "required": True, "at": "cutout-a",
                     "frac": (0.24, 0.30, 0.76, 0.70), "colour": [255, 255, 255],
                     "tools": [["tl", "close"], ["tr", "rotate"], ["br", "enlarge"]]},
                ],
                "exemplar": {"source": "17a18112 meme-generator S10", "fills": {
                    "badge-a": {"block": "batch-check"}, "badge-b": {"block": "batch-check"},
                    "button": {"block": "cta-button", "text": "Add to bag"}, "select": {"block": "transform-box"}}},
            },
        },
    },
    "template-mockup": {
        # Ground is transparent (12/14 corpus assets; the page supplies
        # white/black). The `photo` panel IS the finished card design filling the
        # card interior — the model renders the poster/headline typography inside
        # it (never blank bars, which appear in 0/14), on a fixed dark card
        # surface. A column of three boxes left: geometry from c3461329, b2749949;
        # one is the magenta accent. The swatch stripe is the `palette-card`
        # variant, the selection box `selection-frame`, the exploded editor
        # canvas `editor`.
        "aspect": (1, 1),
        "radius": 40,
        "background": {"ground": {"fill": None},
                       "surfaces": [{"id": "card", "kind": "card", "rect": (556, 152, 1444, 1448), "fill": (43, 20, 90)}]},
        "panels": {
            "photo": {"rect": (600, 200, 1400, 1400), "holds": "design"},
        },
        "slots": [
            {"id": "tile-1", "shape": "tile", "accepts": ["attribution", "tool", "derived"], "required": True,
             "rect": (152, 152, 532, 532), "fill": MAGENTA},
            {"id": "tile-2", "shape": "tile", "accepts": ["tool", "attribution", "derived"], "required": True,
             "rect": (152, 560, 532, 940), "fill": (0, 0, 0)},
            {"id": "swatch", "shape": "tile", "accepts": ["derived", "tool", "attribution"], "required": True,
             "rect": (152, 968, 532, 1348), "n": 3},
        ],
        "exemplar": {"source": "c3461329 (a Gemini-made card)", "fills": {
            "tile-1": {"block": "maker-glyph", "model": "Nano Banana Pro"}, "tile-2": {"block": "tool-tile", "tool": "crop"},
            "swatch": {"block": "palette"}}},
        "variants": {
            # measured small-tile modal (8 S08 cards; 6 byte-identical): swatch stripe
            # on top, magenta accent + black box below, beside the finished card.
            # Evidence: 861c2971, 8031c225, f57cb379, 56f038cf, 517b85da, 80694dc4,
            # d5d56eb0, ba57eaf9.
            "palette-card": {
                "background": {"surfaces": [{"id": "card", "kind": "card", "rect": (532, 300, 1307, 1299), "fill": (43, 20, 90)}]},
                "panels": {
                    "photo": {"rect": (532, 300, 1307, 1299), "holds": "design"},   # the card interior
                },
                "slots": [
                    {"id": "swatch", "shape": "tile", "accepts": ["derived"], "required": True, "rect": (290, 292, 481, 843), "n": 3},
                    {"id": "tile-accent", "shape": "tile", "accepts": ["attribution", "tool"], "required": True,
                     "rect": (290, 884, 481, 1075), "fill": MAGENTA},
                    {"id": "tile-tool", "shape": "tile", "accepts": ["tool", "attribution"], "required": True,
                     "rect": (290, 1114, 481, 1305), "fill": (16, 16, 16)},
                ],
                "exemplar": {"source": "861c2971", "fills": {
                    "swatch": {"block": "palette"}, "tile-accent": {"block": "maker-glyph", "model": "Nano Banana Pro"},
                    "tile-tool": {"block": "tool-tile", "tool": "crop"}}},
            },
            # the editor selection box over the card's focal graphic (972da313
            # card-maker S01: a 391 px square frame, 6 px stroke, d40 midpoint
            # handles; 87194d0d, 168e63a1). The graphic moves per generated card, so
            # the manager moves the `select` slot's rect in the plan; this rect is
            # the measured upper-right default.
            "selection-frame": {
                "background": {"surfaces": [{"id": "card", "kind": "card", "rect": (556, 152, 1444, 1448), "fill": (43, 20, 90)}]},
                "slots": [
                    {"id": "tile-1", "shape": "tile", "accepts": ["attribution", "tool", "derived"], "required": True,
                     "rect": (152, 152, 532, 532), "fill": MAGENTA},
                    {"id": "tile-2", "shape": "tile", "accepts": ["tool", "attribution", "derived"], "required": True,
                     "rect": (152, 560, 532, 940), "fill": (0, 0, 0)},
                    {"id": "swatch", "shape": "tile", "accepts": ["derived", "tool", "attribution"], "required": True,
                     "rect": (152, 968, 532, 1348), "n": 3},
                    {"id": "select", "shape": "frame", "accepts": ["editor"], "required": True, "rect": (980, 250, 1370, 640),
                     "colour": [255, 255, 255], "handles": ["top", "bottom", "left", "right"]},
                ],
                "exemplar": {"source": "972da313 card-maker S01", "fills": {
                    "tile-1": {"block": "maker-glyph", "model": "Nano Banana Pro"}, "tile-2": {"block": "tool-tile", "tool": "crop"},
                    "swatch": {"block": "palette"}, "select": {"block": "transform-box"}}},
            },
            # the exploded editor canvas of the card/poster/menu maker callouts (8
            # S06-m1 slots: 219070b9 calendar, c491d842 christmas-card, a591037a
            # coupon, d4507d92 birthday-card, 6aac8086 facebook-post, cf38e144
            # quote-poster, fc4bbe40 menu, 0a059f15 gift-certificate). The finished
            # card is `photo`; one of its motifs, background removed, is the square
            # `cutout` panel (trimmed to its pixels) on a checker surface, framed by a
            # 3 px selection box with 4 midpoint handles; a box under it and a bar
            # along the foot. Light checker + black frame is the modal (5/8).
            "editor": {
                "background": {"surfaces": [
                    {"id": "card", "kind": "card", "rect": (720, 264, 1336, 1072), "fill": (43, 20, 90)},
                    {"id": "checker", "kind": "checker", "rect": (264, 264, 688, 856)}]},
                "panels": {
                    "photo": {"rect": (720, 264, 1336, 1072), "holds": "design"},   # the finished card design
                    "cutout": {"rect": (300, 310, 652, 662), "fit": "contain", "trim": True, "holds": "subject"},
                },
                "slots": [
                    {"id": "select", "shape": "frame", "accepts": ["editor"], "required": True, "at": "cutout",
                     "frac": (-0.04, -0.04, 1.04, 1.04), "colour": [0, 0, 0], "stroke": 3, "handle": 6},
                    {"id": "type", "shape": "tile", "accepts": ["derived", "tool"], "required": True, "rect": (264, 888, 688, 1072)},
                    {"id": "swatch", "shape": "bar", "accepts": ["derived"], "required": True, "rect": (264, 1100, 1336, 1336),
                     "direction": "row", "n": 4},
                ],
                "exemplar": {"source": "219070b9 calendar-maker S06", "fills": {
                    "select": {"block": "transform-box"}, "type": {"block": "font-pair"}, "swatch": {"block": "palette"}}},
            },
        },
    },
    "dark-composite": {
        # Column on the LEFT (x150-530, 380 wide), three boxes; the main card
        # sits right, inset 150. Evidence: 21cdafd9, 8031c225, d5d56eb0, f57c774f,
        # bd014004: the maker's mark, the page's ACTIVE tool on a MAGENTA accent
        # (8/13 assets carry one), and a palette in the photo's own colours. No
        # "4K" chip — a resolution/format chip is in 0/13 of the population.
        "aspect": (1, 1),
        "radius": 40,
        "background": {"ground": {"fill": BLACK}, "surfaces": []},
        "panels": {
            "photo": {"rect": (570, 150, 1450, 1450), "holds": "scene"},
        },
        "slots": [
            {"id": "tile-1", "shape": "tile", "accepts": ["attribution", "tool", "derived", "spec"], "required": True,
             "rect": (150, 150, 530, 530), "fill": (28, 28, 30)},
            {"id": "tile-2", "shape": "tile", "accepts": ["tool", "attribution", "derived", "spec"], "required": True,
             "rect": (150, 570, 530, 950), "fill": MAGENTA},
            {"id": "tile-3", "shape": "tile", "accepts": ["derived", "tool", "attribution", "spec"], "required": True,
             "rect": (150, 990, 530, 1450), "n": 3},
        ],
        "exemplar": {"source": "21cdafd9 (a Gemini-made card)", "fills": {
            "tile-1": {"block": "maker-glyph", "model": "Nano Banana Pro"}, "tile-2": {"block": "tool-tile", "tool": "crop"},
            "tile-3": {"block": "palette"}}},
        # Devices (`variant:` in the spec; `> device:` in the skeleton): the panel
        # arrangement that tells the section's story. Geometry measured on the
        # Recraft originals (ai-models--recraft-v4-styles-pro-vector S01 86f73fc9,
        # S06 3d65a628, S07 a3502ec3), column on the left as on every Recraft card.
        "variants": {
            # references in, style-locked output out: the mark, a spec box, two same-style thumbnails left, the output right
            "reference-thumbs": {
                "panels": {
                    "photo": {"rect": (410, 0, 1600, 1600), "holds": "scene"},
                    "thumb-a": {"rect": (0, 816, 375, 1192), "holds": "scene"},
                    "thumb-b": {"rect": (0, 1224, 375, 1600), "holds": "scene"},
                },
                "slots": [
                    {"id": "tile-1", "shape": "tile", "accepts": ["attribution", "tool"], "required": True,
                     "rect": (0, 0, 375, 375), "fill": (28, 28, 30)},
                    {"id": "chip", "shape": "tile", "accepts": ["spec"], "rect": (0, 420, 375, 560)},
                ],
                "exemplar": {"source": "86f73fc9 ai-models--recraft-v4-styles-pro-vector S01", "fills": {
                    "tile-1": {"block": "maker-glyph", "model": "Nano Banana Pro"}, "chip": {"block": "spec-label", "text": "4K"}}},
            },
            # chosen over other models: a list card (the ticked model among same-kind
            # peers, each with its maker mark) above two thumbnails, the output right
            "model-picker": {
                "panels": {
                    "photo": {"rect": (700, 0, 1600, 1600), "holds": "scene"},
                    "thumb-a": {"rect": (0, 667, 667, 1120), "holds": "scene"},
                    "thumb-b": {"rect": (0, 1147, 667, 1600), "holds": "scene"},
                },
                "slots": [
                    {"id": "list", "shape": "card", "accepts": ["attribution"], "required": True, "rect": (0, 72, 667, 576)},
                ],
                "exemplar": {"source": "3d65a628 ai-models--recraft-v4-styles-pro-vector S06", "fills": {
                    "list": {"block": "model-picker", "active": "", "rows": []}}},
            },
            # two outputs of one style side by side: panel-a top left with the mark under it, panel-b right
            "two-up": {
                "panels": {
                    "photo": {"rect": (0, 0, 667, 933), "holds": "scene"},
                    "photo-b": {"rect": (720, 0, 1600, 1600), "holds": "scene"},
                },
                "slots": [
                    {"id": "tile-1", "shape": "tile", "accepts": ["attribution", "tool"], "required": True,
                     "rect": (0, 966, 667, 1600), "fill": (28, 28, 30)},
                ],
                "exemplar": {"source": "a3502ec3 ai-models--recraft-v4-styles-pro-vector S07", "fills": {
                    "tile-1": {"block": "maker-glyph", "model": "Nano Banana Pro"}}},
            },
            # three dark cards around the picture on the page's own ground: a line of
            # the copy top left, a list under it, the page's tool across the foot
            # (e08c5490 roas-calculator S04: a formula line, the platforms its copy
            # names, the page's calculator on a worked example). Cards 16 px apart,
            # the grid inset 232 px on the 1600 original.
            "bento": {
                "background": {"ground": {"fill": None}},
                "panels": {
                    "photo": {"rect": (808, 232, 1368, 983), "holds": "scene"},
                },
                "slots": [
                    {"id": "card-a", "shape": "card", "accepts": ["statement", "spec"], "required": True,
                     "rect": (232, 232, 792, 503)},
                    {"id": "card-b", "shape": "card", "accepts": ["context", "attribution", "action"], "required": True,
                     "rect": (232, 520, 792, 983)},
                    {"id": "foot", "shape": "card", "accepts": ["tool", "action", "context"], "required": True,
                     "rect": (232, 1000, 1368, 1367)},
                ],
                # the original's blocks, with placeholders for its words: a record of
                # what went where, never a string for a new picture to reuse
                "exemplar": {"source": "e08c5490 roas-calculator S04", "fills": {
                    "card-a": {"block": "statement", "text": "A line of the copy"},
                    "card-b": {"block": "channel-list", "rows": ["Channel one", "Channel two", "Channel three"]},
                    "foot": {"block": "calculator", "fields": [["Input one", "0"], ["Input two", "0"]],
                             "result": ["Result:", "0"]}}},
            },
        },
    },
    # A photo filling the slot with the tool's dark adjustment panel laid over
    # its lower right (hsl-color S03); the hero is `variant: hero`, a round tool
    # badge with a label top right instead (hsl-color S01). No slot draws both:
    # they overlap. Panel rect `None` means the whole canvas at whichever of
    # `aspects` the spec's size has; `ground: tilted` stacks the card over a
    # plain one on the page's white (S03-m2, S03-m4).
    "panel-overlay": {
        "aspect": (4, 3),
        "aspects": ((4, 3), (5, 4)),
        "radius": 40,
        "background": {"ground": {"fill": None}, "surfaces": []},
        "panels": {
            "photo": {"rect": None, "holds": "scene"},
        },
        "slots": [
            {"id": "panel", "shape": "panel", "accepts": ["tool"], "required": True, "rect": (680, 300, 1490, 900)},
        ],
        "exemplar": {"source": "hsl-color S03", "fills": {
            "panel": {"block": "adjust-panel", "title": "HSL",
                      "sliders": [["Hue", 28], ["Saturation", -26], ["Lightness", 30]]}}},
        "variants": {
            "hero": {  # chosen by the section type (PRESET_BY_SECTION), never by `> device:`
                "slots": [
                    {"id": "tool-pill", "shape": "tile", "accepts": ["tool"], "required": True, "rect": (1080, 120, 1520, 620)},
                ],
                "exemplar": {"source": "hsl-color S01", "fills": {
                    "tool-pill": {"block": "tool-pill", "tool": "adjust", "text": "HSL"}}},
            },
        },
    },
    # "type a prompt, get this": a dark prompt surface with the prompt and a
    # button on it left, the result right (22f9b181 ai-models--kling-v2-1,
    # 802fe719 ai-models--qwen-image).
    "prompt-card": {
        "aspect": (1, 1),
        "radius": 40,
        "background": {"ground": {"fill": BLACK},
                       "surfaces": [{"id": "prompt", "kind": "card", "rect": (100, 100, 620, 1500), "fill": (30, 30, 32)}]},
        "panels": {
            "result": {"rect": (700, 100, 1500, 1500), "holds": "scene"},
        },
        "slots": [
            {"id": "prompt-text", "shape": "text", "accepts": ["action", "statement"], "required": True,
             "rect": (160, 200, 560, 1260), "font": "pill"},
            {"id": "generate", "shape": "pill", "accepts": ["action"], "rect": (160, 1320, 560, 1440), "style": "solid-light"},
        ],
        "exemplar": {"source": "22f9b181 ai-models--kling-v2-1", "fills": {
            "prompt-text": {"block": "prompt-line", "text": ""}, "generate": {"block": "cta-button", "text": "Generate"}}},
        # The model-page language (measured on ai-models--gpt-image-2-5-sunburst,
        # 2026-09-23): the prompt in a dark card fading to an ellipsis, the model's
        # mark in a tile, the output dominant, black ground, 32 px corners. One
        # variant per original.
        "variants": {
            # S03 04-2a8d68c7: mark, prompt card and a detail crop of the output stacked left, the output right
            "column": {
                "radius": 32,
                "panels": {
                    "photo": {"rect": (584, 0, 1600, 1600), "holds": "scene"},
                    "detail": {"rect": (0, 1166, 550, 1600), "detail_of": "photo", "frac": (0.30, 0.52, 0.78, 0.74)},
                },
                "slots": [
                    {"id": "mark", "shape": "tile", "accepts": ["attribution"], "required": True, "rect": (0, 0, 550, 430)},
                    {"id": "prompt", "shape": "card", "accepts": ["action"], "required": True, "rect": (0, 470, 550, 1130),
                     "pad": 44, "font": "prompt-md"},
                ],
                "exemplar": {"source": "2a8d68c7 ai-models--gpt-image-2-5-sunburst S03", "fills": {
                    "mark": {"block": "generator-mark", "model": ""}, "prompt": {"block": "prompt-card", "text": ""}}},
            },
            # S01 04aabc52 (hero): the output between two cropped neighbours, the mark and a wide prompt card beneath
            "strip": {
                "radius": 32,
                "panels": {
                    "peek-a": {"rect": (0, 0, 316, 1248), "anchor": "right", "holds": "scene"},
                    "photo": {"rect": (350, 0, 1250, 1248), "holds": "scene"},
                    "peek-b": {"rect": (1282, 0, 1600, 1248), "anchor": "left", "holds": "scene"},
                },
                "slots": [
                    {"id": "mark", "shape": "tile", "accepts": ["attribution"], "required": True,
                     "rect": (0, 1282, 316, 1600), "scale": 0.56},
                    {"id": "prompt", "shape": "card", "accepts": ["action"], "required": True, "rect": (350, 1282, 1600, 1600),
                     "pad": 60, "font": "prompt-md"},
                ],
                "exemplar": {"source": "04aabc52 ai-models--gpt-image-2-5-sunburst S01", "fills": {
                    "mark": {"block": "generator-mark", "model": ""}, "prompt": {"block": "prompt-card", "text": ""}}},
            },
            # S04 9a903c68: the design left, the design applied right, the prompt as its caption
            "caption": {
                "radius": 32,
                "panels": {
                    "photo": {"rect": (0, 0, 665, 1600), "holds": "design"},
                    "applied": {"rect": (700, 0, 1600, 1250), "holds": "scene"},
                },
                "slots": [
                    {"id": "prompt", "shape": "card", "accepts": ["action"], "required": True, "rect": (700, 1282, 1600, 1600),
                     "pad": 60, "font": "prompt-md"},
                ],
                "exemplar": {"source": "9a903c68 ai-models--gpt-image-2-5-sunburst S04", "fills": {
                    "prompt": {"block": "prompt-card", "text": ""}}},
            },
            # S05 bd1f5ad3: the output above a prompt card that carries the
            # generator's settings chips (model, ratio, count, quality, Enrich)
            "toolbar": {
                "radius": 32,
                "panels": {
                    "photo": {"rect": (0, 0, 1600, 1120), "holds": "scene"},
                },
                "slots": [
                    {"id": "prompt", "shape": "card", "accepts": ["action"], "required": True, "rect": (0, 1080, 1600, 1600),
                     "pad": 56, "max_lines": 3, "font": "prompt-md"},
                    {"id": "toolbar", "shape": "bar", "accepts": ["attribution", "spec"], "rect": (56, 1456, 1544, 1544)},
                ],
                "exemplar": {"source": "bd1f5ad3 ai-models--gpt-image-2-5-sunburst S05", "fills": {
                    "prompt": {"block": "prompt-card", "text": ""}, "toolbar": {"block": "generator-toolbar", "model": ""}}},
            },
            # S06 a6439ac4: the output above the generator's quality and ratio bars
            # (the model's own options, so a bar never shows a setting it lacks)
            "settings": {
                "radius": 32,
                "panels": {
                    "photo": {"rect": (0, 0, 1600, 1360), "holds": "scene"},
                },
                "slots": [
                    {"id": "quality", "shape": "bar", "accepts": ["spec"], "required": True, "rect": (0, 1400, 665, 1600),
                     "font": "chip-lg"},
                    {"id": "ratios", "shape": "bar", "accepts": ["spec"], "required": True, "rect": (700, 1400, 1600, 1600),
                     "font": "chip-lg"},
                ],
                "exemplar": {"source": "a6439ac4 ai-models--gpt-image-2-5-sunburst S06", "fills": {
                    "quality": {"block": "options-bar", "items": [{"text": "high", "active": True}, {"text": "max"}]},
                    "ratios": {"block": "options-bar", "items": [{"text": "1:1"}, {"text": "4:3", "active": True},
                                                                 {"text": "3:4"}, {"text": "16:9"}, {"text": "2:3"}]}}},
            },
            # S07 298b8931 (use-case, 1060x504): prompt card over the mark left, the output right
            "wide": {
                "aspect": (21, 10),
                "radius": 32,
                "panels": {
                    "photo": {"rect": (728, 24, 1576, 737), "holds": "scene"},
                },
                "slots": [
                    {"id": "prompt", "shape": "card", "accepts": ["action"], "required": True, "rect": (24, 24, 710, 516),
                     "font": "prompt-sm", "pad": 48},
                    {"id": "mark", "shape": "tile", "accepts": ["attribution"], "required": True,
                     "rect": (24, 532, 710, 737), "scale": 0.62},
                ],
                "exemplar": {"source": "298b8931 ai-models--gpt-image-2-5-sunburst S07", "fills": {
                    "prompt": {"block": "prompt-card", "text": ""}, "mark": {"block": "generator-mark", "model": ""}}},
            },
        },
    },
    # two outputs of one prompt, side by side, a round mark on the seam
    # (compare-models cards).
    "vs-two-up": {
        "aspect": (1, 1),
        "radius": 40,
        "background": {"ground": {"fill": (242, 242, 244)}, "surfaces": []},
        "panels": {
            "left": {"rect": (40, 40, 780, 1440), "holds": "scene"},
            "right": {"rect": (820, 40, 1560, 1440), "holds": "scene"},
        },
        "slots": [
            {"id": "vs", "shape": "seam", "accepts": ["comparison"], "required": True, "rect": (712, 712, 888, 888)},
        ],
        "exemplar": {"source": "compare-models", "fills": {"vs": {"block": "vs-badge"}}},
    },
    # the result shown "in use": the source photo on the left, a card showing it
    # posted on the right (7a980105 background-remover S08). The card is generic
    # chrome — never a real network's layout.
    "mockup-card": {
        "aspect": (1, 1),
        "radius": 40,
        "background": {"ground": {"fill": BLACK}, "surfaces": []},
        "panels": {
            "photo": {"rect": (80, 120, 760, 1480), "holds": "scene"},
        },
        "slots": [
            {"id": "post", "shape": "card", "accepts": ["context"], "required": True, "rect": (820, 120, 1520, 1480),
             "fill": (30, 30, 32)},
        ],
        "exemplar": {"source": "7a980105 background-remover S08", "fills": {
            "post": {"block": "profile-card", "name": "", "caption": ""}}},
    },
}

# The preset a section type selects when `> device:` names none: the
# panel-overlay hero carries the tool pill, never the adjust panel (runs/layered-1:
# the hero omitted the panel by hand, its 9 cards the pill).
PRESET_BY_SECTION = {"panel-overlay": {"hero": "hero"}}


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


# Layouts induced from corpus readings (`lp-compose --induce` -> assets/layouts.yaml):
# each is a variant of its family measured from one original (its panels, cards
# and pills, their fills, radii and type), with the originals it also covers as
# `members`. They are `induced`: replicas score them (`lp-compose --replica`),
# the golden fixture does not hash them.
LAYOUTS = Path(__file__).parent / "assets" / "layouts.yaml"


def _tuples(x, key=None):
    if isinstance(x, dict):
        return {k: _tuples(v, k) for k, v in x.items()}
    if isinstance(x, list):
        return tuple(x) if key in ("rect", "aspect") else [_tuples(v) for v in x]
    return x


def load_induced(path=LAYOUTS):
    if not Path(path).exists():
        return 0
    n = 0
    loader = getattr(yaml, "CSafeLoader", yaml.SafeLoader)  # the catalogue is ~2 MB: the C parser reads it ~10x faster
    for fam, lays in (yaml.load(Path(path).read_text(), Loader=loader) or {}).items():
        if fam not in FAMILIES:
            continue
        vs = FAMILIES[fam].setdefault("variants", {})
        for name, lay in (lays or {}).items():
            if name not in vs:
                vs[name] = {**_tuples(lay), "aspects": None, "induced": True}
                n += 1
    return n


load_induced()


def induced_for(asset_id):
    """(family, layout name) of the induced layout measured from an original,
    or covering it as a member; None when the original was not induced."""
    for fam, f in FAMILIES.items():
        for name, v in (f.get("variants") or {}).items():
            if not v.get("induced"):
                continue
            src = str((v.get("exemplar") or {}).get("source") or "").split()[:1]
            if src == [asset_id] or asset_id in (v.get("members") or []):
                return fam, name
    return None


def layout_names(fam, induced=3):
    """A family's layouts, default first: its own variants, then the first
    `induced` induced ones (None: all of them; a sweep over every induced
    layout is the replica pass's job, not a test's)."""
    vs = FAMILIES[fam].get("variants") or {}
    own = [v for v in vs if not vs[v].get("induced")]
    ind = [v for v in vs if vs[v].get("induced")]
    return [None, *own, *(ind if induced is None else ind[:induced])]
