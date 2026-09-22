"""The chrome-kind registry: one adapter per drawable kind, so `cli.compose`
is a layer-ordered dispatch instead of a closed if/elif. Each adapter turns a
resolved spec item into the exact `draw.*` call the old branch made, so the six
families render byte-identically (guarded by tests/test_compose_golden.py); the
registry is what lets later waves ADD kinds and place them by layer.

An item draws on the layer named by its kind (or an explicit `layer:`), and
layers stack ground < card < panel < chrome < overlay < top. Everything up to
`overlay` is drawn on the supersampled canvas before the downsample and tilt;
a `top` item is drawn after the tilt, on its own canvas composited over — that
is how an adjustment panel can stay level over a tilted card."""

from dataclasses import dataclass
from typing import Callable

from . import draw

LAYERS = {"ground": 0, "card": 10, "panel": 20, "chrome": 30, "overlay": 40, "top": 50}
CHECKER_CELL = 100
FONT_PX = {"pill": 52, "button": 56, "label": 110, "brackets": 110, "headline": 96,
           "panel-title": 44, "panel-label": 34, "tool-pill": 64, "list-row": 48}  # at REF


@dataclass
class Ctx:
    """What every adapter may read: the supersample scale, the corner radius and
    the resolved panels (chrome anchored to a panel reads its rect)."""
    s: float
    r: int
    panels: dict

    def font(self, key, weight=600):
        return draw.font(FONT_PX[key] * self.s, weight)


@dataclass(frozen=True)
class Kind:
    draw: Callable          # (canvas, item, ctx) -> box (rect at SS pixels)
    layer: str = "chrome"
    text: bool = False      # carries a manager-decided string (for --describe)


def _card(canvas, it, ctx):
    return draw.card(canvas, it["rect"], it["fill"], ctx.r)


def _tile(canvas, it, ctx):
    fill = tuple(it["fill"]) + (255,) if it.get("fill") else (0, 0, 0, 255)
    return draw.tile(canvas, it["rect"], it.get("icon"), ctx.r, fill=fill)


def _icon(canvas, it, ctx):
    return draw.icon(canvas, it["rect"], it["icon"])


def _pill(canvas, it, ctx):
    if "rect" in it:
        return draw.pill_in(canvas, it["rect"], it["text"], it["style"], ctx.font("button"))
    return draw.pill_at(canvas, ctx.panels[it["at"]]["rect"], it["corner"], it["text"], it["style"],
                        ctx.font("pill"), pad=(round(40 * ctx.s), round(22 * ctx.s)), inset=round(40 * ctx.s))


def _label(canvas, it, ctx):
    return draw.label(canvas, it["rect"], it["text"], ctx.r, ctx.font("label"))


def _brackets(canvas, it, ctx):
    x0, y0, x1, y1 = ctx.panels[it["at"]]["rect"]
    fx0, fy0, fx1, fy1 = it["frac"]
    w, h = x1 - x0, y1 - y0
    return draw.brackets(canvas, (x0 + w * fx0, y0 + h * fy0, x0 + w * fx1, y0 + h * fy1), it.get("label", ""),
                         ctx.font("brackets"), max(1, round(10 * ctx.s)))


def _badge(canvas, it, ctx):
    px0, py0, px1, py1 = ctx.panels[it["at"]]["rect"]
    size, inset = round(90 * ctx.s), round(24 * ctx.s)
    x0 = px0 + inset if it["corner"][1] == "l" else px1 - inset - size
    y0 = py0 + inset if it["corner"][0] == "t" else py1 - inset - size
    return draw.badge(canvas, (x0, y0, x0 + size, y0 + size), round(22 * ctx.s))


def _headline(canvas, it, ctx):
    return draw.headline(canvas, it["rect"], it.get("text", ""), FONT_PX["headline"] * ctx.s,
                         max(1, round(6 * ctx.s)), round(12 * ctx.s))


def _adjust_panel(canvas, it, ctx):
    return draw.adjust_panel(canvas, it["rect"], it.get("title", ""), it.get("chips", 0), it.get("active", 0),
                             it.get("sliders") or [], ctx.font("panel-title", 700),
                             ctx.font("panel-label"), round(36 * ctx.s))


def _tool_pill(canvas, it, ctx):
    return draw.tool_pill(canvas, it["rect"], it.get("text", ""), it.get("icon", "wheel"),
                          ctx.font("tool-pill", 700))


def _list_panel(canvas, it, ctx):
    return draw.list_panel(canvas, it["rect"], it.get("rows", 4), it.get("active", 0), it.get("active_text", ""),
                           ctx.font("list-row", 700), ctx.r)


def _text(canvas, it, ctx):
    """Free text on a transparent fill — a label bound to no chrome box, e.g. a
    prompt sentence or a compare-label. Centred in its rect at the given font."""
    colour = tuple(it.get("colour") or (255, 255, 255))
    if len(colour) == 3:
        colour += (255,)
    return draw.box_text(canvas, it["rect"], it.get("text", ""), (0, 0, 0, 0), colour, 0, ctx.font(it.get("font", "panel-label")))


def _round_badge(canvas, it, ctx):
    """A filled circle with centred text — the VS mark on a two-up seam."""
    fill = tuple(it.get("fill") or (255, 255, 255))
    if len(fill) == 3:
        fill += (255,)
    colour = tuple(it.get("colour") or (28, 28, 28))
    if len(colour) == 3:
        colour += (255,)
    return draw.round_badge(canvas, it["rect"], it.get("text", ""), fill, colour, ctx.font(it.get("font", "tool-pill"), 700))


def _profile_card(canvas, it, ctx):
    """A mock profile/social card (avatar, name, image well, caption bars).
    `fill` is an RGB triple; `draw.card` adds the alpha."""
    return draw.profile_card(canvas, it["rect"], tuple(it.get("fill") or (30, 30, 32)), ctx.r)


KINDS = {
    "card": Kind(_card, layer="card"),
    "tile": Kind(_tile),
    "icon": Kind(_icon),
    "pill": Kind(_pill, text=True),
    "label": Kind(_label, text=True),
    "brackets": Kind(_brackets),
    "badge": Kind(_badge),
    "headline": Kind(_headline, text=True),
    "adjust-panel": Kind(_adjust_panel, text=True),
    "tool-pill": Kind(_tool_pill, text=True),
    "list-panel": Kind(_list_panel, text=True),
    "text": Kind(_text, text=True),
    "round-badge": Kind(_round_badge, text=True),
    "profile-card": Kind(_profile_card),
}
