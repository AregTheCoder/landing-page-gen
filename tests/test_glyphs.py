"""Type is drawn right: every weight is a static instance, every composite
glyph keeps its parts where the font's designer put them, and a string the
font cannot set is refused before it prints boxes.

The variable Manrope keeps its composites' parts at their 200-weight offsets,
so a 600-weight ÷ printed as a +: the dots ran into the bar (runs/random-1
S04, the ROAS formula). fontbuild.py instances the weights and re-seats them."""

import numpy as np
import pytest
from PIL import Image, ImageDraw, ImageFont

from landing_page_gen.compose import bank, draw

PX = 96
# Manrope's composite glyphs (fontTools: glyf[name].isComposite()), soft hyphen and ligatures included
COMPOSITES = ('":;_\xadµËÕëï÷ďĐĽľŒœŢťŨũŲʹ͵;΄Ά·ΈΉΊΌΎΏΐΑΒΓΕΖΗΙΚΜΝΟΠΡΤΥΦΧήΰγηκνοφχόЀЅІЇЈЉАВЕКМНОРСТХЫаеорсухѐѕ'
              'іјћҮỹ‑’‚”„†…‹₀₁₂₃₄₅₆₇₈№ﬁ')


def _mask(font, ch):
    im = Image.new("L", (PX * 2, PX * 2), 0)
    ImageDraw.Draw(im).text((PX // 2, PX // 4), ch, font=font, fill=255)
    return np.array(im) > 127


def _parts(mask):
    """8-connected blobs of a bitmap, largest first, as (area, cx, cy, box)."""
    seen = np.zeros_like(mask)
    out = []
    for y, x in zip(*np.nonzero(mask)):
        if seen[y, x]:
            continue
        stack, pts = [(y, x)], []
        seen[y, x] = True
        while stack:
            cy, cx = stack.pop()
            pts.append((cy, cx))
            for ny in (cy - 1, cy, cy + 1):
                for nx in (cx - 1, cx, cx + 1):
                    if 0 <= ny < mask.shape[0] and 0 <= nx < mask.shape[1] and mask[ny, nx] and not seen[ny, nx]:
                        seen[ny, nx] = True
                        stack.append((ny, nx))
        ys, xs = zip(*pts)
        out.append((len(pts), sum(xs) / len(xs), sum(ys) / len(ys), (min(xs), min(ys), max(xs), max(ys))))
    return sorted(out, reverse=True)


def test_every_weight_is_a_static_instance():
    for w in draw.WEIGHTS:
        with pytest.raises(OSError):  # a static instance has no variation axes to set
            draw.font(20, w).get_variation_axes()
    with pytest.raises(ValueError):
        draw.font(20, 300)


@pytest.mark.parametrize("weight", draw.WEIGHTS)
def test_divide_sign_has_two_dots_centred_on_its_bar(weight):
    parts = _parts(_mask(draw.font(PX, weight), "÷"))
    assert len(parts) == 3, f"÷ at {weight} draws {len(parts)} parts (the dots ran into the bar)"
    bar, dots = parts[0], parts[1:]
    for d in dots:
        assert abs(d[1] - bar[1]) <= 1.0, f"÷ at {weight}: a dot sits {d[1] - bar[1]:+.1f}px off the bar's centre"
    above, below = sorted(dots, key=lambda d: d[2])
    gap_up, gap_down = bar[3][1] - above[3][3], below[3][1] - bar[3][3]
    assert gap_up > 1 and gap_down > 1 and abs(gap_up - gap_down) <= 2, (weight, gap_up, gap_down)


@pytest.mark.parametrize("weight", draw.WEIGHTS)
def test_composite_glyphs_keep_their_parts_apart(weight):
    """A composite has as many separate parts at every weight as the designer
    drew at the default one (200, where the offsets were set)."""
    default = ImageFont.truetype(str(draw.ASSETS / "Manrope.ttf"), PX)
    fnt = draw.font(PX, weight)
    merged = [ch for ch in COMPOSITES if len(_parts(_mask(fnt, ch))) < len(_parts(_mask(default, ch)))]
    assert not merged, f"at {weight} these composites' parts run together: {''.join(merged)}"


def test_a_string_the_font_cannot_set_is_refused():
    item = {"id": "check-1", "kind": "check-row", "text": "✓ Sharper"}
    assert draw.missing_glyphs(item) == "✓"
    assert any("not in the font" in p for p in bank.claim_problems(item, {}, {"panels": [], "two_states": False}))
    assert draw.missing_glyphs({"kind": "form-card", "fields": [["Ad Spend", "150"]], "result": ["ROAS ÷ x", "5"]}) == ""
    assert draw.missing_glyphs({"kind": "chip-bar", "items": [{"text": "4K ★"}]}) == "★"
