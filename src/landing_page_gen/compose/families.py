"""Composite-card templates, one dict per style family of
`.claude/skills/picsart-workflows/style-families.md` that has chrome.
Geometry is in reference pixels at REF (the corpus originals are 1600 px
square) and is scaled to the spec's size at render time. The worker supplies
the panel images; the family supplies the layout and the chrome."""

import math

REF = 1600
RATIOS = ("1:1", "3:2", "2:3", "16:9", "9:16", "4:3", "3:4")  # gpt-image-2.5-sunburst (no 21:9: wide panels generate at 16:9 and crop)

BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
MAGENTA = (225, 30, 224)  # Picsart accent #e01ee0 (was (181,23,170), an off measurement)
CHECKER = ((58, 58, 60), (42, 42, 44))
# the finer checker of the template-mockup /editor tile, measured: light (5/8, a
# translucent grey/white pair, c491d842, a591037a, d4507d92) and dark (219070b9)
EDITOR_CHECKER = {"light": ((167, 167, 171, 64), (255, 255, 255, 64)), "dark": ((65, 64, 66), (35, 31, 32))}

# panels: name -> rect (x0, y0, x1, y1), optional fit ("cover" | "contain") and
# under ("checkerboard"). chrome: drawn after the panels except kind "card";
# a spec overrides an item by id and drops one with `omit`.
FAMILIES = {
    "before-after": {
        # Ground is transparent on every corpus composite (alpha-0 gutters and
        # margin, measured 15/15; the page section supplies the surround). The
        # MODAL card is the WIDE ~2.1:1 layout — 11 of 15 genuine before+result+
        # tile composites, 16 of 21 by aspect (e.g. 08385997 ai-image-enhancer
        # S09, c5715e9b image-upscale S07, f223c881 video-enhancer S10). Native
        # 1060x504 scaled x1.5094 to REF width: margin 16->24, gutter 8->12.
        # before + icon tile left, result right, solid-dark pills, "After" on the
        # RESULT. The rare 1:1 stacked pair (1/21 for this exact geometry;
        # 69ed3f5c image-enlarger S08) is `variant: stacked-square`.
        "aspect": (21, 10),                         # 1060x504 = 2.103:1
        "ground": {"fill": None},                   # transparent — all composites
        "radius": 40,
        "panels": {
            "before": {"rect": (24, 24, 610, 519)},   # 388x328 native
            "result": {"rect": (622, 24, 1576, 737)}, # 632x472 native
        },
        "chrome": [
            {"id": "before-pill", "kind": "pill", "at": "before", "corner": "bl", "text": "Before", "style": "solid-dark"},
            {"id": "after-pill", "kind": "pill", "at": "result", "corner": "bl", "text": "After", "style": "solid-dark"},
            {"id": "tile", "kind": "tile", "rect": (24, 531, 610, 737), "icon": "enlarge"},
        ],
        "variants": {
            # the 1:1 stacked pair, measured from 69ed3f5c (image-enlarger S08):
            # before + after stacked left with a tile below, result (often an
            # applied mockup of the after image) right. The former default; for
            # callout-1:1 slots. Translucent pills (69ed3f5c, bcc56313).
            "stacked-square": {
                "aspect": (1, 1),
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
        "variants": {
            # The crop-image namesake signature (4c0b8b9b S01 hero, c78690a2 S05,
            # d93605b1 S06, 24e4540f S09): two overlapping rounded photo cards on a
            # TRANSPARENT ground (measured from alpha: 0.23-0.41 alpha-0 gutters, not
            # black), the back card under a rule-of-thirds crop grid, the front card
            # the clean result, a black circular crop badge on the seam, and a dark
            # rounded ratio/size label. Fills STANDARD.md's deferred `crop-grid`.
            "crop-grid": {
                "ground": {"fill": None},
                "panels": {
                    "source": {"rect": (600, 110, 1510, 1120)},   # back, gridded
                    "result": {"rect": (90, 560, 850, 1470)},     # front, clean, overlaps the corner
                },
                "chrome": [
                    # the existing brackets PLUS interior thirds lines (grid: True); inset
                    # to the back card's outer ~65% so the front card does not cross it
                    # (639e11c1 interior lines at 1/3, 2/3; c78690a2 frame 613-1463 x 233-1075)
                    {"id": "grid", "kind": "brackets", "at": "source",
                     "frac": (0.30, 0.09, 0.95, 0.90), "grid": True},
                    # black disc + white crop glyph, d~260 on the seam
                    # (4c0b8b9b d278 @ (230,508); c78690a2 d256 left edge)
                    {"id": "crop-badge", "kind": "crop-badge",
                     "rect": (470, 430, 730, 690), "icon": "crop"},
                    # dark rounded ratio/size label bottom-right (c78690a2 card 496x404 @ (1100,884))
                    {"id": "ratio", "kind": "label", "rect": (1090, 900, 1560, 1300), "text": "1:1"},
                ],
            },
        },
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
        "variants": {
            # the editor transform box over the first cutout (17a18112 meme-generator
            # S10, 361c2368 ai-image-extender S05, 16410f3b whatsapp-sticker-maker S05,
            # 1fa729f4 background-tools S13): white square-cornered frame, disc
            # handles at the edge midpoints, X / rotate / resize tool discs outside
            # the corners. Frame 6 px, handles d40 at REF (972da313, native 1600).
            # frac is inset from the proposal's 0.16-0.84 so the tool discs (100 px
            # past each corner) stay on the 513-wide panel and clear of badge-a.
            "selection-frame": {
                "chrome": [
                    {"id": "badge-a", "kind": "badge", "at": "cutout-a", "corner": "tr"},
                    {"id": "badge-b", "kind": "badge", "at": "cutout-b", "corner": "tr"},
                    {"id": "button", "kind": "pill", "rect": (545, 1390, 1600, 1600), "text": "Add to bag", "style": "solid-dark"},
                    {"id": "select", "kind": "selection-frame", "at": "cutout-a",
                     "frac": (0.24, 0.30, 0.76, 0.70), "colour": [255, 255, 255],
                     "tools": [["tl", "close"], ["tr", "rotate"], ["br", "enlarge"]]},
                ],
            },
        },
    },
    "template-mockup": {
        # Ground is transparent (12/14 corpus assets; the page supplies
        # white/black). The `photo` panel IS the finished card design filling the
        # card interior — the model renders the poster/headline typography inside
        # it (never blank bars, which appear in 0/14). Left column is 3 MIXED
        # tiles (one magenta accent, not 4 uniform black): geometry from
        # c3461329, b2749949. /black is the same artwork exported on a dark page
        # (a fill override, not a separate drawing). The swatch stripe is the
        # `palette-card` variant, the selection box the `selection-frame`
        # variant and the exploded editor canvas the `editor` variant.
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
            {"id": "swatch", "kind": "swatch", "rect": (152, 968, 532, 1348), "colours": {"from": "photo", "n": 3}},
        ],
        "variants": {
            # measured small-tile modal (8 S08 cards; 6 byte-identical): swatch stripe
            # on top, magenta accent + black tool tile below, beside the finished card.
            # Evidence: 861c2971, 8031c225, f57cb379, 56f038cf, 517b85da, 80694dc4,
            # d5d56eb0, ba57eaf9. Colours come from the section copy (spec override).
            "palette-card": {
                "panels": {
                    "photo": {"rect": (532, 300, 1307, 1299)},   # the card interior
                },
                "chrome": [
                    {"id": "card", "kind": "card", "rect": (532, 300, 1307, 1299), "fill": (43, 20, 90)},
                    {"id": "swatch", "kind": "swatch", "rect": (290, 292, 481, 843),
                     "colours": {"from": "photo", "n": 3}},  # the card's palette; `> chrome:` hex colours override
                    {"id": "tile-accent", "kind": "tile", "rect": (290, 884, 481, 1075), "icon": "sparkle", "fill": MAGENTA},
                    {"id": "tile-tool", "kind": "tile", "rect": (290, 1114, 481, 1305), "icon": "crop", "fill": (16, 16, 16)},
                ],
            },
            # the editor selection box over the card's focal graphic (972da313
            # card-maker S01: a 391 px square frame, 6 px stroke, d40 midpoint
            # handles; 87194d0d, 168e63a1). The graphic moves per generated card,
            # so the manager moves `select.rect` in the slot's plan (an explicit rect wins); this rect
            # is the measured upper-right default.
            "selection-frame": {
                "chrome": [
                    {"id": "card", "kind": "card", "rect": (556, 152, 1444, 1448), "fill": (43, 20, 90)},
                    {"id": "tile-1", "kind": "tile", "rect": (152, 152, 532, 532), "icon": "sparkle", "fill": MAGENTA},
                    {"id": "tile-2", "kind": "tile", "rect": (152, 560, 532, 940), "icon": "crop", "fill": (0, 0, 0)},
                    {"id": "swatch", "kind": "swatch", "rect": (152, 968, 532, 1348), "colours": {"from": "photo", "n": 3}},
                    {"id": "select", "kind": "selection-frame", "rect": (980, 250, 1370, 640),
                     "colour": [255, 255, 255], "handles": ["top", "bottom", "left", "right"]},
                ],
            },
            # the exploded editor canvas of the card/poster/menu maker callouts (8
            # S06-m1 slots: 219070b9 calendar, c491d842 christmas-card, a591037a
            # coupon, d4507d92 birthday-card, 6aac8086 facebook-post, cf38e144
            # quote-poster, fc4bbe40 menu, 0a059f15 gift-certificate). The finished
            # card is `photo`; one of its motifs, background removed, is the square
            # `cutout` panel (trimmed to its pixels) on a checker tile, framed by a
            # 3 px selection box with 4 midpoint handles; a type tile sits under it
            # and a swatch bar spans the foot. Light checker + black frame is the
            # modal (5/8); dark is `checker.tone: dark` with a white frame (3/8).
            "editor": {
                "panels": {
                    "photo": {"rect": (720, 264, 1336, 1072)},   # the finished card design
                    "cutout": {"rect": (300, 310, 652, 662), "fit": "contain", "trim": True},
                },
                "chrome": [
                    {"id": "card", "kind": "card", "rect": (720, 264, 1336, 1072), "fill": (43, 20, 90)},
                    {"id": "checker", "kind": "checker", "rect": (264, 264, 688, 856)},
                    {"id": "select", "kind": "selection-frame", "at": "cutout", "frac": (-0.04, -0.04, 1.04, 1.04),
                     "colour": [0, 0, 0], "stroke": 3, "handle": 6},
                    {"id": "type", "kind": "type-tile", "rect": (264, 888, 688, 1072)},
                    {"id": "swatch", "kind": "swatch", "rect": (264, 1100, 1336, 1336), "direction": "row",
                     "colours": {"from": "photo", "n": 4}},  # the card's palette; `> chrome:` hex colours override
                ],
            },
        },
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
            # = a colour-swatch tile in the photo's own palette. No "4K" chip — a resolution/format chip
            # is in 0/13 of the current population (opt-in via `chrome: {chip}`).
            {"id": "tile-1", "kind": "tile", "rect": (150, 150, 530, 530), "icon": "sparkle", "fill": (28, 28, 30)},
            {"id": "tile-2", "kind": "tile", "rect": (150, 570, 530, 950), "icon": "crop", "fill": MAGENTA},
            {"id": "tile-3", "kind": "swatch", "rect": (150, 990, 530, 1450), "colours": {"from": "photo", "n": 3}},
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
            # chosen over other models: a dark list card (the page's model highlighted among
            # same-kind siblings, each with its maker mark) above two thumbnails, the output right
            "model-picker": {
                "panels": {
                    "photo": {"rect": (700, 0, 1600, 1600)},
                    "thumb-a": {"rect": (0, 667, 667, 1120)},
                    "thumb-b": {"rect": (0, 1147, 667, 1600)},
                },
                "chrome": [
                    {"id": "list", "kind": "list-panel", "rect": (0, 72, 667, 576), "rows": 4, "active": 1, "active_text": "",
                     "rows_text": []},  # `> chrome:` names the page's model; plan.build fills the siblings
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
    # its lower right (hsl-color S03); the hero is `variant: hero`, a round tool
    # badge with a label pill top right instead (hsl-color S01). No slot draws
    # both: they overlap. Panel rect `None` means the whole canvas at whichever
    # of `aspects` the spec's size has; `ground: tilted` stacks the card over a
    # plain one on the page's white (S03-m2, S03-m4).
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
        ],
        "variants": {
            "hero": {  # chosen by the section type (PRESET_BY_SECTION), never by `> device:`
                "chrome": [
                    {"id": "tool-pill", "kind": "tool-pill", "rect": (1080, 120, 1520, 620), "text": "HSL", "icon": "wheel"},
                ],
            },
        },
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
            {"id": "prompt-text", "kind": "text", "rect": (160, 200, 560, 1260), "text": "", "wrap": True, "font": "pill"},
            {"id": "generate", "kind": "pill", "rect": (160, 1320, 560, 1440), "text": "Generate", "style": "solid-light"},
        ],
        # The model-page language (measured on ai-models--gpt-image-2-5-sunburst,
        # 2026-09-23): the prompt that made the picture in a dark card fading to an
        # ellipsis, the model's mark in a tile, the output dominant, black ground,
        # 32 px corners. One variant per original; `> chrome:` gives the prompt
        # (the real generation prompt's opening) and the model.
        "variants": {
            # S03 04-2a8d68c7: mark tile, prompt card and a detail crop of the output
            # stacked left, the output right
            "column": {
                "radius": 32,
                "panels": {
                    "photo": {"rect": (584, 0, 1600, 1600)},
                    "detail": {"rect": (0, 1166, 550, 1600), "detail_of": "photo", "frac": (0.30, 0.52, 0.78, 0.74)},
                },
                "chrome": [
                    {"id": "mark", "kind": "mark-tile", "rect": (0, 0, 550, 430), "model": ""},
                    {"id": "prompt", "kind": "prompt-text", "rect": (0, 470, 550, 1130), "text": "", "pad": 44, "font": "prompt-md"},
                ],
            },
            # S01 04aabc52 (hero): the output between two cropped neighbours, the mark
            # tile and a wide prompt card beneath
            "strip": {
                "radius": 32,
                "panels": {
                    "peek-a": {"rect": (0, 0, 316, 1248), "anchor": "right"},
                    "photo": {"rect": (350, 0, 1250, 1248)},
                    "peek-b": {"rect": (1282, 0, 1600, 1248), "anchor": "left"},
                },
                "chrome": [
                    {"id": "mark", "kind": "mark-tile", "rect": (0, 1282, 316, 1600), "model": "", "scale": 0.56},
                    {"id": "prompt", "kind": "prompt-text", "rect": (350, 1282, 1600, 1600), "text": "", "pad": 60, "font": "prompt-md"},
                ],
            },
            # S04 9a903c68: the design left, the design applied right, the prompt as
            # its caption
            "caption": {
                "radius": 32,
                "panels": {
                    "photo": {"rect": (0, 0, 665, 1600)},
                    "applied": {"rect": (700, 0, 1600, 1250)},
                },
                "chrome": [
                    {"id": "prompt", "kind": "prompt-text", "rect": (700, 1282, 1600, 1600), "text": "", "pad": 60, "font": "prompt-md"},
                ],
            },
            # S05 bd1f5ad3: the output above a prompt card that carries the
            # generator's settings chips (model, ratio, count, quality, Enrich)
            "toolbar": {
                "radius": 32,
                "panels": {
                    "photo": {"rect": (0, 0, 1600, 1120)},
                },
                "chrome": [
                    {"id": "prompt", "kind": "prompt-text", "rect": (0, 1080, 1600, 1600), "text": "", "pad": 56, "max_lines": 3, "font": "prompt-md"},
                    {"id": "toolbar", "kind": "chip-bar", "rect": (56, 1456, 1544, 1544), "group": False, "items": [
                        {"text": "", "mark": True, "caret": True}, {"text": "4:3", "caret": True},
                        {"text": "1 image", "caret": True}, {"text": "high", "caret": True}, {"text": "Enrich", "accent": True}]},
                ],
            },
            # S06 a6439ac4: the output above the generator's quality and ratio bars,
            # the settings it was made with lifted (the chips are the model's own
            # options, so the bar never shows a setting it does not have)
            "settings": {
                "radius": 32,
                "panels": {
                    "photo": {"rect": (0, 0, 1600, 1360)},
                },
                "chrome": [
                    {"id": "quality", "kind": "chip-bar", "rect": (0, 1400, 665, 1600), "font": "chip-lg",
                     "items": [{"text": "high", "active": True}, {"text": "max"}]},
                    {"id": "ratios", "kind": "chip-bar", "rect": (700, 1400, 1600, 1600), "font": "chip-lg",
                     "items": [{"text": "1:1"}, {"text": "4:3", "active": True}, {"text": "3:4"}, {"text": "16:9"}, {"text": "2:3"}]},
                ],
            },
            # S07 298b8931 (use-case, 1060x504): prompt card over the mark tile left,
            # the output right
            "wide": {
                "aspect": (21, 10),
                "radius": 32,
                "panels": {
                    "photo": {"rect": (728, 24, 1576, 737)},
                },
                "chrome": [
                    {"id": "prompt", "kind": "prompt-text", "rect": (24, 24, 710, 516), "text": "", "font": "prompt-sm", "pad": 48},
                    {"id": "mark", "kind": "mark-tile", "rect": (24, 532, 710, 737), "model": "", "scale": 0.62},
                ],
            },
        },
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
    # The card is generic chrome — never a real network's layout — carrying the
    # photo, and the account name and caption the page's `> chrome:` gives.
    "mockup-card": {
        "aspect": (1, 1),
        "ground": {"fill": BLACK},
        "radius": 40,
        "panels": {
            "photo": {"rect": (80, 120, 760, 1480)},
        },
        "chrome": [
            {"id": "post", "kind": "profile-card", "rect": (820, 120, 1520, 1480), "fill": (30, 30, 32), "image": {"from": "photo"},
             "name": "", "caption": ""},
        ],
    },
}

# The preset a section type selects when `> device:` names none: the
# panel-overlay hero carries the tool pill, never the adjust panel (runs/layered-1:
# the hero omitted the panel by hand, its 9 cards the pill).
PRESET_BY_SECTION = {"panel-overlay": {"hero": "hero"}}

_BEFORE_AFTER = [("before label", ("before-pill.text",)), ("after label", ("after-pill.text",))]

# The strings a preset draws that the page decides, in the skeleton's `> chrome:`
# order: (slot, the item fields its string fills). `sliders.N` is slider N's name;
# `colours` takes every remaining string. A slot the line leaves out keeps the
# template's string. test_plan pins every text field a preset draws to a slot here.
LABELS = {
    ("before-after", None): _BEFORE_AFTER,
    ("before-after", "stacked-square"): _BEFORE_AFTER,
    ("crop-frame", None): [("frame label", ("brackets.label",))],
    ("crop-frame", "crop-grid"): [("ratio", ("ratio.text",))],
    ("cutout-checkerboard", None): [("button", ("button.text",))],
    ("cutout-checkerboard", "selection-frame"): [("button", ("button.text",))],
    ("dark-composite", "reference-thumbs"): [("chip", ("chip.text",))],
    ("dark-composite", "model-picker"): [("active row", ("list.active_text",)), ("other rows", ("list.rows_text",))],
    ("panel-overlay", None): [("tool name", ("panel.title",)), ("slider 1", ("panel.sliders.0",)),
                              ("slider 2", ("panel.sliders.1",)), ("slider 3", ("panel.sliders.2",))],
    ("panel-overlay", "hero"): [("tool name", ("tool-pill.text",))],
    ("prompt-card", None): [("prompt", ("prompt-text.text",)), ("button", ("generate.text",))],
    ("prompt-card", "column"): [("prompt", ("prompt.text",)), ("model", ("mark.model",))],
    ("prompt-card", "strip"): [("prompt", ("prompt.text",)), ("model", ("mark.model",))],
    ("prompt-card", "caption"): [("prompt", ("prompt.text",))],
    ("prompt-card", "toolbar"): [("prompt", ("prompt.text",)), ("model", ("toolbar.items.0",))],
    ("prompt-card", "settings"): [],
    ("prompt-card", "wide"): [("prompt", ("prompt.text",)), ("model", ("mark.model",))],
    ("template-mockup", "palette-card"): [("colours (hex, any number)", ("swatch.colours",))],
    ("template-mockup", "editor"): [("colours (hex, any number)", ("swatch.colours",))],
    ("vs-two-up", None): [("badge", ("vs.text",))],
    ("mockup-card", None): [("account name", ("post.name",)), ("caption", ("post.caption",))],
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
