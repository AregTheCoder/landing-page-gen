"""The model catalogue behind the model-picker list: which models Picsart
hosts, which kind each is, and the maker mark drawn beside its name
(`assets/models.yaml`, marks in `assets/logos/`)."""

import re
from functools import cache
from pathlib import Path

import yaml
from PIL import Image, ImageOps

ASSETS = Path(__file__).parent / "assets"
LOGOS = ASSETS / "logos"


@cache
def catalogue():
    return yaml.safe_load((ASSETS / "models.yaml").read_text())


def maker(m):
    return m.get("logo") or m.get("maker")


def lookup(name):
    """The catalogue entry a picker row's text names: an exact match, else the
    longest catalogue name the text starts with ("Recraft V4 Styles Pro" is
    Recraft V4's), else None."""
    key = str(name or "").casefold().strip()
    models = catalogue()["models"]
    exact = [m for m in models if m["name"].casefold() == key]
    if exact:
        return exact[0]
    prefix = [m for m in models if key.startswith(m["name"].casefold())]
    return max(prefix, key=lambda m: len(m["name"])) if prefix else None


def siblings(active, n, kind=None):
    """`n` names for a picker's other rows: models of the active one's kind
    (image when unknown) from other makers, one per maker, marked ones first,
    in catalogue order."""
    me = lookup(active)
    kind = kind or (me or {}).get("kind", "image")
    seen = {maker(me)} if me else set()
    pool = [m for m in catalogue()["models"] if m["kind"] == kind]
    out = []
    for m in sorted(pool, key=lambda m: not m.get("logo")):
        if maker(m) in seen or m["name"] == active:
            continue
        seen.add(maker(m))
        out.append(m["name"])
        if len(out) == n:
            break
    return out


def logo(name):
    """The maker mark (white on transparent RGBA) for a row's text, or None."""
    m = lookup(name)
    path = LOGOS / f"{m['logo']}.png" if m and m.get("logo") else None
    return Image.open(path).convert("RGBA") if path and path.exists() else None


def mark(name):
    """A maker mark by model name ("GPT Image 2.5 Sunburst") or by maker key
    ("openai"), or None."""
    path = LOGOS / f"{name}.png"
    return Image.open(path).convert("RGBA") if name and path.exists() else logo(name)


def extract_logos(repo):
    """Re-key every mark from its corpus source: the crop's luminance above the
    tile's own (its border median) becomes the alpha of a white glyph, trimmed
    and centred on a square. Returns the files written."""
    written = []
    LOGOS.mkdir(exist_ok=True)
    for key, src in catalogue()["logos"].items():
        with Image.open(Path(repo) / src["src"]) as im:
            grey = ImageOps.grayscale(im.convert("RGB").crop(tuple(src["box"])))
        w, h = grey.size
        border = sorted([grey.getpixel((x, y)) for x in range(w) for y in (0, h - 1)]
                        + [grey.getpixel((x, y)) for y in range(h) for x in (0, w - 1)])
        bg = border[len(border) // 2]
        alpha = grey.point(lambda v: max(0, min(255, round((v - bg) * 255 / max(1, 255 - bg) * 1.15))))
        box = alpha.point(lambda v: 255 if v > 24 else 0).getbbox()
        alpha = alpha.crop(box)
        side = max(alpha.size)
        mark = Image.new("RGBA", (side, side), (255, 255, 255, 0))
        glyph = Image.new("RGBA", alpha.size, (255, 255, 255, 255))
        glyph.putalpha(alpha)
        mark.alpha_composite(glyph, ((side - alpha.width) // 2, (side - alpha.height) // 2))
        if side < 192:
            mark = mark.resize((192, 192), Image.LANCZOS)
        out = LOGOS / f"{key}.png"
        mark.save(out)
        written.append(out)
    return written


def _norm(s):
    return re.sub(r"[^a-z0-9]", "", str(s).lower())


def connector_ids():
    c = catalogue()["connector"]
    return {*c["image"], *c["video"]}


def model_id(slug):
    """The connector model a model-page slug part names ("recraft-v4-styles-pro-vector"
    -> recraftv4_styles_pro_vector), or a reason string starting with "no:" when
    it cannot be generated or is not mapped."""
    cat = catalogue()
    if slug in cat["slugs"]:
        return cat["slugs"][slug]
    by_norm = {_norm(i): i for i in connector_ids()}
    if _norm(slug) in by_norm:
        return by_norm[_norm(slug)]
    if slug in cat["unavailable"]:
        return f"no: {slug} is advertised on Picsart but not on the connector, so its images cannot be generated truthfully"
    return f"no: {slug} is not mapped to a connector model; add it to compose/assets/models.yaml (slugs or unavailable)"


def model_name(slug):
    """The catalogue name of the model a page slug names ("nano-banana-pro" ->
    "Nano Banana Pro"), or None when it has none (unmapped, unavailable)."""
    return name_for_id(model_id(slug))


def name_for_id(mid):
    """The catalogue name of a connector model id ("gpt-image-2.5-sunburst" ->
    "GPT Image 2.5 Sunburst"), or None."""
    return next((m["name"] for m in catalogue()["models"] if m.get("id") == mid), None)


def maker_of(name):
    """The maker key of a model name or a maker key ("Nano Banana Pro" -> gemini)."""
    m = lookup(name)
    return maker(m) if m else (name if name and (LOGOS / f"{name}.png").exists() else None)


def page_models(page):
    """The models a page presents its pictures as the output of: [x] for
    ai-models--x, [a, b] for compare-models--a-vs-b, [] otherwise (and for the
    audio models, whose pages are illustrated, not demonstrated)."""
    page = str(page or "")
    audio = set(catalogue()["audio"])
    if page.startswith("ai-models--"):
        slug = page[len("ai-models--"):]
        return [] if slug in audio else [slug]
    if page.startswith("compare-models--"):
        sides = page[len("compare-models--"):].split("-vs-")
        return [] if len(sides) != 2 or set(sides) & audio else sides
    return []


def made_by(page, family=None, preset=None, items=(), panels=("*",)):
    """{panel: {model, because}} — the model each generated panel must come from
    because the page or the chrome presents it as that model's output ('*' is a
    slot with no composite). A `model` starting "no:" is a slot that cannot be
    generated truthfully. Empty when nothing is attributed.

    - ai-models--x: every panel is x's output.
    - compare-models--a-vs-b: a vs-two-up's left is a's, its right b's.
    - elsewhere, a model picker's panels are its highlighted model's, and any
      other attribution block (a mark tile, a model chip) makes the panels it
      names (`for:`, else every panel) that model's output."""
    sides = page_models(page)
    if str(page).startswith("ai-models--") and sides:
        mid = model_id(sides[0])
        return {p: {"model": mid, "because": f"the page {page} presents its pictures as {sides[0]}'s output"}
                for p in panels}
    if len(sides) == 2 and family == "vs-two-up":
        return {p: {"model": model_id(s), "because": f"the {p} side of {page} is {s}'s output"}
                for p, s in zip(("left", "right"), sides) if p in panels}
    if preset == "model-picker" and any(it.get("kind") == "list-panel" for it in items):
        active = next((it.get("active_text") for it in items if it.get("kind") == "list-panel"), "")
        m = lookup(active) if active else None
        mid = (m or {}).get("id") or f"no: the picker highlights {active!r}, which has no connector id in models.yaml"
        return {p: {"model": mid, "because": f"the model picker ticks {active!r}"} for p in panels if p != "*"}
    for it in items:
        name = attributed_model(it)
        if not name:
            continue
        m = lookup(name)
        mid = (m or {}).get("id") or f"no: the {it.get('kind')} {it.get('id')!r} names {name!r}, which is no model in models.yaml"
        return {p: {"model": mid, "because": f"the {it.get('kind')} {it.get('id')!r} marks it as {name}'s output"}
                for p in (it.get("for") or panels) if p != "*"}
    return {}


def attributed_model(item):
    """The model name an attribution block shows, or None (a maker key alone,
    "gemini", names no model and so attributes nothing)."""
    from . import bank  # bank reads models; lazy to keep the import graph flat
    if bank.category_of(item) != "attribution":
        return None
    kind = item.get("kind")
    if kind == "mark-tile":
        name = item.get("model")
    elif kind == "chip-bar":
        name = next((x.get("text") for x in item.get("items") or [] if x.get("mark") is True), None)
    elif kind == "pill":
        name = item.get("text")
    elif kind == "list-panel":
        name = item.get("active_text")
    else:
        return None
    if not name or (LOGOS / f"{name}.png").exists() and not lookup(name):
        return None  # empty, or a maker key: a mark with no model claims no model
    return name
