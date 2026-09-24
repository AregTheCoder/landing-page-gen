"""The chrome block bank (`assets/blocks.yaml`) and the rules that put a block
in a template slot.

A template is a skeleton (families.py): background, picture panels, and slots
that each take one block of the categories they accept, in one shape. Nothing
in a template says anything about a page. A block fills a slot only when its
category is accepted, it can draw in the slot's shape, and its hard context
(`requires`) holds on the page's facts (`roles.facts_for`): `candidates` lists
the blocks that pass for a slot. Whether a candidate's soft context (`when`)
is this section's is the worker's call, recorded with a `because:` in
blocks-<slot>.yaml; `check` refuses a pick that breaks a rule, and `resolve`
turns the picks into the items lp-compose draws."""

import re
from functools import cache
from pathlib import Path

import yaml

from . import draw, models, roles

ASSETS = Path(__file__).parent / "assets"

# slot keys that describe the slot, not the item drawn in it
SLOT_META = ("id", "shape", "accepts", "required", "state", "n", "note")
# the category an item carries when it names none (a timeline layer, an
# item written by hand): its kind's commonest reading
DEFAULT_CATEGORY = {
    "tile": "tool", "crop-badge": "tool", "tool-pill": "tool", "icon": "tool", "adjust-panel": "tool",
    "form-card": "tool", "mark-tile": "attribution", "list-panel": "attribution",
    "chip-bar": "spec", "label": "spec", "check-row": "spec", "waveform": "spec", "play-button": "spec",
    "pill": "action", "text": "action", "prompt-text": "action", "headline": "action",
    "statement": "statement", "round-badge": "comparison", "compare-handle": "comparison",
    "swatch": "derived", "type-tile": "derived", "profile-card": "context", "list-card": "context",
    "checker": "editor", "brackets": "editor", "selection-frame": "editor", "badge": "editor",
}
# the interface verbs a Picsart tool's own button carries; an action string
# that is neither one of these nor page copy is invented
UI_VERBS = {"generate", "download", "upload", "upload a photo", "enhance", "try now", "remove background",
            "add to bag", "buy", "edit", "create", "start creating"}
# what a generator's settings chips may say (options, never claims)
OPTION_WORDS = {"low", "medium", "high", "max", "auto", "hd", "enrich"}
COUNT = re.compile(r"^\d+ (image|images|video|videos)$")
BEFORE_WORDS = {"before", "original", "old", "input"}
AFTER_WORDS = {"after", "enhanced", "new", "output", "result", "restored", "upscaled"}


@cache
def vocab():
    return yaml.safe_load((ASSETS / "blocks.yaml").read_text())


def block(name):
    return vocab()["blocks"].get(name)


def category_of(item):
    """An item's category: its own, its block's, else its kind's commonest."""
    return item.get("category") or (block(item.get("block") or "") or {}).get("category") \
        or DEFAULT_CATEGORY.get(item.get("kind"))


def glyph_of(maker):
    """The glyph a maker draws as its own symbol (gemini: the sparkle), or None."""
    return next((g for g, m in (roles.vocab().get("marks") or {}).items() if m == maker), None)


def mark_maker(item):
    """The maker whose symbol an item draws (a sparkle tile is Gemini's; a mark
    tile its model's maker), or None."""
    if item.get("kind") == "mark-tile":
        return models.maker_of(item.get("model"))
    return (roles.vocab().get("marks") or {}).get(item.get("icon"))


def item_tool(item):
    """The Picsart tool a block shows: its `tool:`, else the one its glyph
    draws (a maker's glyph is never a tool)."""
    if item.get("icon") in (roles.vocab().get("marks") or {}):
        return None
    return item.get("tool") or roles.icon_tool(item.get("icon"))


def item_strings(item):
    """Every page-visible string an item draws that the copy must supply
    (a calculator's values and an adjust panel's slider values are examples,
    not claims)."""
    kind = item.get("kind")
    if kind == "adjust-panel":
        out = [item.get("title"), *(s[0] for s in item.get("sliders") or [])]
    elif kind == "form-card":
        out = [f[0] for f in item.get("fields") or []] + [(item.get("result") or [None])[0]]
    elif kind == "list-card":
        out = list(item.get("rows") or [])
    elif kind == "chip-bar":
        out = [x.get("text") for x in item.get("items") or [] if x.get("mark") is not True]
    elif kind == "list-panel":
        out = []  # model names: the attribution check holds them
    else:
        out = [item.get(k) for k in ("text", "label", "title", "name", "caption")]
    return [str(s) for s in out if s not in (None, "")]


def _hay(facts):
    return " ".join([str(facts.get("copy") or ""), str(facts.get("page_copy") or ""),
                     *map(str, facts.get("labels") or [])]).casefold()


def in_copy(s, facts):
    return str(s).casefold() in _hay(facts)


def context(plan):
    """What a plan offers its blocks: its panels, whether it shows two states of
    one picture, and which panel holds what."""
    panels = [p["panel"] if isinstance(p, dict) else p for p in plan.get("panels") or []]
    names = set(panels)
    two_states = bool(({"before"} & names and names & {"after", "result"}) or plan.get("pair")
                      or any(isinstance(p, dict) and p.get("degrade") for p in plan.get("panels") or []))
    return {"panels": panels, "two_states": two_states,
            "first": next((p["panel"] for p in plan.get("panels") or [] if isinstance(p, dict) and not p.get("from")),
                          panels[0] if panels else None)}


def _requires(item):
    b = block(item.get("block") or "")
    if b and "requires" in b:
        return b["requires"]
    return (vocab()["categories"].get(category_of(item)) or {}).get("requires") or []


def _allowed_models(facts):
    named = [n for n in facts.get("labels") or [] if models.lookup(n)]
    return [m for m in [facts.get("generator"), *(facts.get("models") or []), *named] if m]


def claim_problems(item, facts, ctx, slot=None):
    """What an item claims that this page does not support: its category's (or
    block's) hard context. Empty when the item is honest, or when there are no
    facts to judge it by. A string the font cannot set is refused either way."""
    cid = item.get("id")
    miss = draw.missing_glyphs(item)
    out = [f"{cid}: {miss!r} is not in the font (it would print as boxes); write it with characters the font has"] if miss else []
    if not facts:
        return out
    for req in _requires(item):
        if req == "two-states" and not ctx["two_states"]:
            out.append(f"{cid}: needs two states of one picture (before + after panels, a degraded panel, or a pair)")
        elif req == "state" and slot and slot.get("state"):
            word = str(item.get("text") or "").casefold()
            wrong = AFTER_WORDS if slot["state"] == "before" else BEFORE_WORDS
            if word in wrong:
                out.append(f"{cid}: says {item.get('text')!r} on the {slot['state']} panel")
        elif req == "two-pictures" and len(ctx["panels"]) < 2:
            out.append(f"{cid}: needs two pictures side by side (two states of one picture take a compare handle)")
        elif req == "page-tool":
            t = item_tool(item)
            if t and t not in (facts.get("tools") or []):
                about = " / ".join(facts.get("tools") or []) or "no Picsart tool"
                out.append(f"{cid}: shows the {t} tool, but {facts.get('page') or 'the page'} names {about}")
        elif req == "generator":
            maker, gen = mark_maker(item), facts.get("generator")
            want = models.maker_of(gen) if gen else None
            if maker and want and maker != want:
                out.append(f"{cid}: shows the {maker} mark, but the picture is made on {gen} ({want}); "
                           "an attribution names the generating model")
            named = models.attributed_model(item)
            if named and not any(models.lookup(named) == models.lookup(m) for m in _allowed_models(facts)):
                out.append(f"{cid}: names {named!r}, which neither makes the picture nor is a model the page presents")
        elif req in ("spec", "copy", "verb", "options"):
            honest = set((roles.tool(facts.get("tool")) or {}).get("specs") or []) if req == "spec" else set()
            for s in item_strings(item):
                fold = s.casefold()
                if req == "verb" and fold in UI_VERBS or req == "options" and (
                        fold in OPTION_WORDS or s in _ratios() or COUNT.match(fold)):
                    continue
                if s not in honest and not in_copy(s, facts):
                    what = {"spec": "a claim about the output", "verb": "button text",
                            "options": "a setting the generator does not have"}.get(req, "a string")
                    out.append(f"{cid}: {s!r} is {what} the page copy never makes")
            if req == "copy" and item.get("kind") == "form-card" and not _computed(item):
                out.append(f"{cid}: the result {(item.get('result') or [None, None])[1]!r} is not computed from "
                           "the fields; work your own example through")
        elif req == "prompt" and not str(item.get("text") or "").strip():
            out.append(f"{cid}: the prompt is empty; it is the opening of the prompt that made the picture")
        elif req == "panel":
            for key in ("colours", "image", "fill"):
                v = item.get(key)
                if isinstance(v, dict) and v.get("from") not in ctx["panels"]:
                    out.append(f"{cid}: {key} from panel {v.get('from')!r}, which this composition does not have")
    return out


def _number(v):
    m = re.search(r"-?\d[\d,]*(\.\d+)?", str(v or ""))
    return float(m.group(0).replace(",", "")) if m else None


def _computed(item):
    """Whether a calculator's result is its fields worked through: with two
    numeric inputs, their ratio, product, sum or difference (to the shown
    precision). Anything else passes (the check is for a worked example)."""
    vals = [_number(f[1]) for f in item.get("fields") or [] if len(f) > 1]
    res = _number((item.get("result") or [None, None])[1]) if len(item.get("result") or []) > 1 else None
    if len(vals) != 2 or None in vals or res is None:
        return True
    a, b = vals
    shown = str((item.get("result") or [None, ""])[1])
    places = len(shown.split(".")[1]) if "." in shown else 0
    tol = 0.5 * 10 ** -places + 1e-9
    options = [a + b, a - b, b - a, a * b] + ([b / a] if a else []) + ([a / b] if b else [])
    return any(abs(res - o) <= tol for o in options)


@cache
def _ratios():
    from .families import RATIOS
    return set(RATIOS) | {"21:9", "4:5", "5:4"}


def _sub(value, params):
    """Put a pick's parameters into a block's draw fields ($tool.icon,
    $model.glyph, $name)."""
    if isinstance(value, dict):
        return {k: v for k, v in ((k, _sub(v, params)) for k, v in value.items()) if v is not None}
    if isinstance(value, list):
        return [_sub(v, params) for v in value]
    if not (isinstance(value, str) and value.startswith("$")):
        return value
    name, _, attr = value[1:].partition(".")
    v = params.get(name)
    if attr == "icon":
        return (roles.tool(v) or {}).get("icon")
    if attr == "glyph":
        return glyph_of(models.maker_of(v))
    return v


def _default(param, spec, slot, facts, ctx):
    src = spec.get("from")
    if "default" in spec:
        return spec["default"]
    if src == "generator":
        return (facts or {}).get("generator")
    if src == "state" and slot.get("state"):
        return {"before": "Before", "after": "After"}[slot["state"]]
    if src == "panel":
        return {"from": ctx["first"], "n": slot.get("n", 3)} if param == "colours" else {"from": ctx["first"]}
    if src == "catalogue":
        return []
    return None


def resolve_one(slot, pick, facts, ctx):
    """The item a pick draws in a slot: the block's kind and fields for the
    slot's shape, the pick's parameters (or their bound defaults), then the
    slot's geometry and look."""
    b = block(pick["block"])
    params = {}
    for name, spec in (b.get("params") or {}).items():
        params[name] = pick[name] if name in pick else _default(name, spec, slot, facts, ctx)
    fields = _sub(b["draw"][slot["shape"]], params)
    item = {"id": slot["id"], **fields, **{k: v for k, v in slot.items() if k not in SLOT_META},
            "category": b["category"], "block": pick["block"]}
    if item.get("kind") == "list-panel" and str(item.get("active_text") or "").strip():
        rows = list(item.get("rows_text") or [])
        need = item.get("rows", 4) - 1 - len(rows)
        if need > 0:
            extra = [n for n in models.siblings(item["active_text"], need + len(rows)) if n not in rows]
            item["rows_text"] = rows + extra[:need]
    return item


def picks_of(doc):
    """{slot id: pick} from a blocks-<slot>.yaml (`fills:` a list of {slot,
    block, ...} or a mapping slot -> {block, ...})."""
    fills = (doc or {}).get("fills") or {}
    if isinstance(fills, list):
        return {f.get("slot"): {k: v for k, v in f.items() if k != "slot"} for f in fills if isinstance(f, dict)}
    return {k: dict(v or {}) for k, v in fills.items()}


def slots_of(plan, template):
    """The plan's slots with the template's geometry and look (a plan entry may
    move a slot: an explicit `rect` wins)."""
    over = {s["id"]: s for s in plan.get("slots") or []}
    return [{**s, **{k: v for k, v in (over.get(s["id"]) or {}).items() if k not in ("candidates", "excluded")}}
            for s in template.get("slots") or []]


def candidates(slot, facts, ctx):
    """([candidate], [excluded]): the blocks whose category the slot accepts
    and that can draw in its shape, with the parameters the page fixes bound
    (the tool, the generator) and the ones the worker must give named; the
    excluded are those whose hard context fails here, with why."""
    out, excluded = [], []
    for name, b in vocab()["blocks"].items():
        if b["category"] not in slot["accepts"] or slot["shape"] not in b["draw"]:
            continue
        params = b.get("params") or {}
        options = [{}]
        if "tool" in params:
            tools = [t for t in (facts or {}).get("tools") or [] if roles.tool(t)]
            if not tools:
                excluded.append({"block": name, "why": "the page names no Picsart tool"})
                continue
            options = [{"tool": t} for t in tools]
        give = [p for p, spec in params.items() if spec.get("from") in ("copy", "prompt") and not spec.get("optional")]
        for opt in options:
            item = resolve_one(slot, {"block": name, **opt, **{p: "x" for p in give}}, facts, ctx)
            if "$" in str(item) or ("icon" in b["draw"][slot["shape"]] and not item.get("icon")):
                excluded.append({"block": name, "why": _unbound_why(name, facts)})
                continue
            probs = [p for p in claim_problems(item, facts, ctx, slot) if "'x'" not in p]
            if probs:
                excluded.append({"block": name, **opt, "why": probs[0].split(": ", 1)[1]})
                continue
            out.append({"block": name, **opt, **({"give": give} if give else {})})
    return out, excluded


def _unbound_why(name, facts):
    if name == "maker-glyph":
        return f"only a Gemini picture carries the sparkle; this one is made on {(facts or {}).get('generator')}"
    return "a parameter it needs is not known"


def check(plan, template, doc, facts):
    """Problems with a worker's picks (blocks-<slot>.yaml) against a plan:
    each slot filled by an accepted category in its shape, every hard context
    held, every string given, a reason for each choice, no block twice, and
    every required slot filled. Empty when the picks can be drawn."""
    picks, slots, ctx = picks_of(doc), slots_of(plan, template), context(plan)
    by_id = {s["id"]: s for s in slots}
    out = [f"{sid}: not a slot of this layout ({', '.join(by_id)})" for sid in picks if sid not in by_id]
    seen = {}
    for s in slots:
        pick = picks.get(s["id"])
        if not pick or pick.get("block") in (None, "none"):
            if s.get("required"):
                out.append(f"{s['id']}: a required slot ({' | '.join(s['accepts'])}, {s['shape']}) is empty")
            elif pick is not None and not str(pick.get("because") or "").strip():
                out.append(f"{s['id']}: say why the slot stays empty (`because:`)")
            continue
        b = block(pick["block"])
        if not b:
            out.append(f"{s['id']}: {pick['block']!r} is not a block of the bank")
            continue
        if b["category"] not in s["accepts"]:
            art = "an" if b["category"][0] in "aeio" else "a"
            out.append(f"{s['id']}: {pick['block']} is {art} {b['category']} block; the slot takes {' | '.join(s['accepts'])}")
            continue
        if s["shape"] not in b["draw"]:
            out.append(f"{s['id']}: {pick['block']} cannot draw in a {s['shape']} ({', '.join(b['draw'])})")
            continue
        if not str(pick.get("because") or "").strip():
            out.append(f"{s['id']}: `because:` is missing; name the copy or page fact that makes {pick['block']} fit")
        for p, spec in (b.get("params") or {}).items():
            if spec.get("from") in ("copy", "prompt") and not spec.get("optional") and p not in pick:
                out.append(f"{s['id']}: {pick['block']} needs `{p}:` ({spec.get('note') or 'from the ' + spec['from']})")
        item = resolve_one(s, pick, facts, ctx)
        if "icon" in b["draw"][s["shape"]] and not item.get("icon"):
            out.append(f"{s['id']}: {_unbound_why(pick['block'], facts)}")
        out += claim_problems(item, facts, ctx, s)
        # what the block says, wherever it sits: two palettes of one panel repeat, a Before and an After do not
        key = (str(sorted((k, str(v)) for k, v in item.items() if k not in s and k != "id")), s.get("at"))
        if key in seen:
            out.append(f"{s['id']}: the same block as {seen[key]}; a composition says each thing once")
        seen[key] = s["id"]
    return out


def resolve(plan, template, doc, facts=None):
    """The items the picks draw, in slot order (an empty slot draws nothing)."""
    picks, ctx = picks_of(doc), context(plan)
    return [resolve_one(s, picks[s["id"]], facts or plan.get("facts") or {}, ctx)
            for s in slots_of(plan, template) if (picks.get(s["id"]) or {}).get("block") not in (None, "none")]


def evidence_matches(item, role_of):
    """The bank blocks a corpus chrome item {kind, text} is evidence for."""
    text = str(item.get("text") or "")
    out = []
    for name, b in vocab()["blocks"].items():
        ev = b.get("evidence") or {}
        if item.get("kind") not in ev.get("kinds", ()):
            continue
        if ev.get("role") and role_of(item) != ev["role"]:
            continue
        if ev.get("text") and not re.search(ev["text"], text, re.I):
            continue
        out.append(name)
    return out
