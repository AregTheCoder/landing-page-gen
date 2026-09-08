"""board.png: one row per hsl-color slot; columns original | live-1 generated | web reference | trial-4 composite."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

R = Path(__file__).parent
ROWS = [
    ("S01-m1 hero", "originals/S01-m1-85708ef3.png", "generated/S01-m1.png", "refs/pexels-2180474-rfera-smiling-man.jpg", "trial/T3-composed.png"),
    ("S03-m1", "originals/S03-m1-da31e929.png", "generated/S03-m1.png", "refs/pexels-850391-godisable-jacob-striped-wall.jpg", "trial/T1-composed.png"),
    ("S03-m2", "originals/S03-m2-9caa06ad.png", "generated/S03-m2.png", "refs/pexels-850393-godisable-jacob-striped-wall.jpg", "trial/T2-tilted-composed.png"),
    ("S03-m3", "originals/S03-m3-0c9be8c4.png", "generated/S03-m3.png", "refs/pexels-12928824-weezy-mie-lilac-on-yellow.jpg", "trial/T2-composed.png"),
    ("S03-m4", "originals/S03-m4-e9c17dd8.png", "generated/S03-m4.png", None, None),
]
COLS = ["original (picsart.com/hsl-color)", "live-1 generated (full-bleed brief)", "web reference (Pexels)", "trial-4: stock look + panel-overlay"]
CW, CH, GAP, HEAD, LABEL = 400, 300, 16, 40, 22
font = ImageFont.truetype(str(R.parent.parent / "src/landing_page_gen/compose/assets/Manrope.ttf"), 15)
W = GAP + len(COLS) * (CW + GAP)
H = HEAD + len(ROWS) * (CH + LABEL + GAP) + GAP
board = Image.new("RGB", (W, H), (245, 245, 247))
d = ImageDraw.Draw(board)
for c, name in enumerate(COLS):
    d.text((GAP + c * (CW + GAP), 12), name, font=font, fill=(40, 40, 40))
for r, (label, *cells) in enumerate(ROWS):
    y = HEAD + r * (CH + LABEL + GAP)
    d.text((GAP, y), label, font=font, fill=(90, 90, 90))
    for c, cell in enumerate(cells):
        x = GAP + c * (CW + GAP)
        box = (x, y + LABEL, x + CW, y + LABEL + CH)
        if not cell:
            d.rectangle(box, outline=(200, 200, 200))
            d.text((x + 12, y + LABEL + 12), "no reference found", font=font, fill=(160, 160, 160))
            continue
        im = Image.open(R / cell).convert("RGBA")
        im.thumbnail((CW, CH), Image.LANCZOS)
        bg = Image.new("RGBA", (CW, CH), (255, 255, 255, 255))
        bg.alpha_composite(im, ((CW - im.width) // 2, (CH - im.height) // 2))
        board.paste(bg.convert("RGB"), (x, y + LABEL))
board.save(R / "board.png")
print(R / "board.png", board.size)
