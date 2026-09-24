"""The composition plan — the machine-readable contract between the manager,
the worker and lp-compose.

A plan is a template skeleton made concrete for one slot: the panels the
worker generates (their ratios, what they hold, the keep-clear regions chrome
over them would hide), and the template's slots, each with the bank blocks
that pass the category, shape and hard-context rules on this page
(`candidates`). It carries no chrome. The worker picks a block per slot, with
a reason, in blocks-<slot>.yaml; `check_blocks` refuses a pick that breaks a
rule, and `to_spec` turns the plan, the picks and the panel images into a
compose spec.

`keep_clear` is rendered once with the template's exemplar fills (the blocks
its measured original showed) and placeholder panels: the region of each panel
that chrome drawn over it would hide, so the brief can say "put no subject
here". Chrome under the panels and chrome that frames the subject is not a
no-go zone."""

import tempfile
from pathlib import Path

import yaml
from PIL import Image

from . import bank, cli, families, kinds, models

# an overlapping chrome rect only counts as keep-clear when it covers a
# meaningful share of the panel (a hairline pill on the edge is not a no-go zone)
MIN_OVERLAP = 0.02


def _rect_size(family, preset, size):
    tmpl = cli.template(family, preset)
    fw, fh = (tmpl.get("aspects") or (tmpl["aspect"],))[0]
    if size:
        return tmpl, size
    return tmpl, (families.REF, round(families.REF * fh / fw))


def exemplar_items(family, preset=None):
    """The chrome the template's measured original showed, as drawable items
    (its `exemplar` fills resolved without page facts). A record for the
    golden renders, the keep-clear footprint and --describe; never a default."""
    tmpl = cli.template(family, preset)
    ctx = {"panels": [{"panel": n} for n, p in tmpl["panels"].items() if not p.get("detail_of")]}
    return bank.resolve(ctx, tmpl, {"fills": (tmpl.get("exemplar") or {}).get("fills") or {}}, {})


def hides_subject(item):
    """Whether a chrome item can cover a panel's subject: only chrome drawn
    ABOVE the panels (a surface on the `card` layer sits under the photo), and
    not chrome that frames the subject (brackets, the crop grid, a selection
    box — the subject belongs inside those, so they are not no-subject zones)."""
    kind = kinds.KINDS[item["kind"]]
    layer = item.get("layer") or kind.layer
    return kinds.LAYERS[layer] > kinds.LAYERS["panel"] and not kind.frames


def keep_clear(family, preset=None, size=None):
    """{panel name: [{item, rect (output px), frac (of the panel)}]} — the
    chrome drawn over each panel that would hide a subject there (see
    `hides_subject`), with each slot holding its exemplar block. Panels with
    nothing over them are omitted."""
    tmpl, (w, h) = _rect_size(family, preset, size)
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        for name in tmpl["panels"]:
            Image.new("RGB", (400, 400), "white").save(d / f"{name}.png")
        spec = {"family": family, "size": f"{w}x{h}", "chrome": exemplar_items(family, preset),
                "panels": {name: {"image": f"{name}.png"} for name in tmpl["panels"]}}
        if preset:
            spec["preset"] = preset
        (d / "s.yaml").write_text(yaml.safe_dump(spec))
        layout = cli.resolve(cli.load_spec(d / "s.yaml"))
        _, drawn = cli.compose(layout)
    items = {it["id"]: it for it in layout["chrome"]}
    out = {}
    for name, p in layout["panels"].items():
        px0, py0, px1, py1 = (v / cli.SS for v in p["rect"])
        pw, ph = px1 - px0, py1 - py0
        regions = []
        for cid, (cx0, cy0, cx1, cy1) in drawn.items():
            if not hides_subject(items[cid]):
                continue
            ix0, iy0, ix1, iy1 = max(px0, cx0), max(py0, cy0), min(px1, cx1), min(py1, cy1)
            if ix1 > ix0 and iy1 > iy0 and (ix1 - ix0) * (iy1 - iy0) > MIN_OVERLAP * pw * ph:
                regions.append({"item": cid,
                                "rect": [round(ix0), round(iy0), round(ix1), round(iy1)],
                                "frac": [round((ix0 - px0) / pw, 3), round((iy0 - py0) / ph, 3),
                                         round((ix1 - px0) / pw, 3), round((iy1 - py0) / ph, 3)]})
        if regions:
            out[name] = regions
    return out


def contract(family, preset=None, size=None):
    """The worker's panel contract for a preset: each panel with the ratio to
    generate it at, its fit, what it holds (a scene, a design, a cut-out
    subject) and the keep-clear regions an overlay covers it with."""
    tmpl, (w, h) = _rect_size(family, preset, size)
    kc = keep_clear(family, preset, (w, h))
    out = []
    for name, p in tmpl["panels"].items():
        if p.get("detail_of"):  # cropped from another panel by lp-compose, never generated
            continue
        if p["rect"] is None:
            ratio = families.nearest_ratio(w, h)  # fills the slot
        else:
            x0, y0, x1, y1 = p["rect"]
            ratio = families.nearest_ratio(x1 - x0, y1 - y0)
        out.append({"panel": name, "ratio": ratio, "fit": p.get("fit", "cover"), "holds": p.get("holds", "scene"),
                    "keep_clear": kc.get(name, [])})
    return out


def degrade_panels(plan, facts, tmpl=None):
    """Make a before/after's Before from its After (compose/degrade.py) instead
    of generating it: the panel gets `degrade: <mode>` (the page's fault) and
    `from: <panel>`, and the worker supplies only the After. A pill slot in the
    After state sits bottom right and is the generated picture; its Before twin
    is `from: pair` (the After slot's image). A compare-slider always degrades
    its left half, and a measured compare card (an After panel with a `seam`
    over a twin of the same rect) takes its Before from that After."""
    if plan["family"] != "before-after":
        return
    mode, preset = (facts or {}).get("degrade"), plan.get("preset")
    by = {p["panel"]: p for p in plan["panels"]}
    if preset == "compare-slider":
        by["photo"]["degrade"] = mode or "blur"
    elif preset == "pill":
        if plan["state"] == "after":  # the keep-clear follows the pill, mirrored across the panel
            for kc in by["photo"]["keep_clear"]:
                x0, y0, x1, y1 = kc["frac"]
                kc["frac"] = [round(1 - x1, 3), y0, round(1 - x0, 3), y1]
                kc["rect"] = [families.REF - kc["rect"][2], kc["rect"][1], families.REF - kc["rect"][0], kc["rect"][3]]
        elif mode:
            by["photo"].update({"degrade": mode, "from": "pair"})
    elif mode and "before" in by:
        by["before"].update({"degrade": mode, "from": "after" if "after" in by else "result"})
    else:
        tp = (tmpl or {}).get("panels") or {}
        for name, t in tp.items():
            twin = next((n for n, o in tp.items() if n != name and o.get("seam") is not None
                         and list(o["rect"]) == list(t["rect"])), None)
            if t.get("seam") is None and twin and name in by:
                by[name].update({"degrade": mode or "blur", "from": twin})


def generated_panels(plan):
    """The panels a worker generates (not those lp-compose derives)."""
    return [p["panel"] for p in plan.get("panels") or [] if not p.get("from")]


def claimed_panels(plan):
    """The generated panels a page can present as a model's output. A prompt
    card's smaller panels are its inputs (the reference clip and photo a user
    brings), so only its largest panel, the result, is claimed (Areg,
    2026-09-24: an honest Sora thumbnail is a frame of a real Sora clip, and
    only the result is Sora's)."""
    panels = generated_panels(plan)
    if plan.get("family") != "prompt-card" or len(panels) < 2:
        return panels
    rects = cli.template(plan["family"], plan.get("preset"))["panels"]

    def area(name):
        r = rects.get(name, {}).get("rect")
        return (r[2] - r[0]) * (r[3] - r[1]) if r else float("inf")  # a panel with no rect fills the card
    return [max(panels, key=area)]


def plan_slots(plan, tmpl, facts):
    """The template's slots for this plan: shape, categories, required, the
    panel state of a state-label slot, and (with page facts) the bank blocks
    that may fill each, with the ones excluded here and why."""
    ctx = bank.context(plan)
    out = []
    for sl in tmpl.get("slots") or []:
        entry = {"id": sl["id"], "shape": sl["shape"], "accepts": list(sl["accepts"]), "required": bool(sl.get("required"))}
        state = sl.get("state") or (plan.get("state") if sl["accepts"] == ["state-label"] else None)
        if state:
            entry["state"] = state
        if plan.get("preset") == "pill" and plan.get("state") == "after" and sl.get("corner"):
            entry["corner"] = "br"  # the After's pill sits bottom right
        if facts:
            cands, excluded = bank.candidates({**sl, **entry}, facts, ctx)
            entry["candidates"] = cands
            if excluded:
                entry["excluded"] = excluded
        out.append(entry)
    return out


def build(family, size, *, preset=None, ground=None, slot=None, derived_from=None, labels=None, section=None,
          facts=None, pair=None, state=None):
    """Assemble a composition plan: the panels (ratios + keep-clear) the worker
    generates and the template's slots with their candidate blocks on this
    page (`facts`, from `roles.facts_for`), tagged with what it was derived from
    (so a later edit to the skeleton can be caught as stale). `labels` are the
    skeleton's `> chrome:` strings: strings the chrome may say beyond the copy.
    A pill slot's `state` (before | after) comes from its pair."""
    # the panel ratios and keep-clear fractions do not depend on the render
    # size, so use the family's own frame; `size` is recorded for the compose step
    # and, when no preset is asked for, picks the variant whose aspect it has
    preset = cli.preset_for_size(family, size, preset, section)
    tmpl = cli.template(family, preset)
    plan = {"slot": slot, "family": family, "size": size, "panels": contract(family, preset)}
    if preset == "pill":
        state = state or ("after" if labels and str(labels[0]).casefold() in bank.AFTER_WORDS else "before")
    for key, val in (("preset", preset), ("ground", ground), ("labels", labels), ("derived_from", derived_from),
                     ("pair", pair), ("state", state)):
        if val:
            plan[key] = val
    if facts:
        plan["facts"] = {k: v for k, v in facts.items() if v not in (None, [], "")}
    degrade_panels(plan, facts, tmpl)
    plan["slots"] = plan_slots(plan, tmpl, facts)
    if ground and not cli.ground_renderable(ground):
        # a corpus variant with no colour to draw (colour, mixed, gradient, checker):
        # keep it on record and let lp-compose draw the family ground — the family
        # docs brief these as the default. The manager may set `ground: {fill: [r, g, b]}`.
        plan["ground_variant"] = plan.pop("ground")
    return plan


def fillable(family, size, facts, section=None):
    """The layouts of a family that fit a slot size and whose every required
    slot has a candidate on this page."""
    out = []
    for v in (None, *(families.FAMILIES[family].get("variants") or {})):
        t = cli.template(family, v)
        if size and not cli.fits(t, *(cli.parse_size(size) if isinstance(size, str) else size)):
            continue
        p = build(family, size, preset=v, facts=facts, section=section)
        if not [s for s in p["slots"] if s["required"] and not s.get("candidates")]:
            out.append(v or "the default")
    return out


def write_plan(path, plan):
    """Write a composition plan to YAML, slot/panel order preserved."""
    Path(path).write_text(yaml.safe_dump(plan, sort_keys=False, allow_unicode=True))


def validate(plan):
    """Problems that would stop a plan from rendering; empty when it is sound."""
    problems = []
    fam = plan.get("family")
    if fam not in families.FAMILIES:
        problems.append(f"family {fam!r} is not a compose family")
        return problems
    preset = plan.get("preset")
    known = not preset or preset in (families.FAMILIES[fam].get("variants") or {})
    if not known:
        problems.append(f"{fam} has no preset {preset!r}")
    elif plan.get("size"):
        # the aspect check lp-compose makes at render, made before the panels are paid for
        size = plan["size"]
        w, h = cli.parse_size(size) if isinstance(size, str) else size
        tmpl = cli.template(fam, preset)
        if not cli.fits(tmpl, w, h):
            aspects = " or ".join(f"{a}:{b}" for a, b in tmpl.get("aspects") or (tmpl["aspect"],))
            variants = families.FAMILIES[fam].get("variants") or {}
            fits = [v for v in (None, *variants) if cli.fits(cli.template(fam, v), w, h)]
            named = [v or "the default" for v in fits if not (v and variants[v].get("induced"))]
            induced = [v for v in fits if v and variants[v].get("induced")]
            more = f" (and {len(induced)} induced layout{'s' * (len(induced) != 1)}, e.g. {induced[0]})" if induced else ""
            if named:
                tail = f": {' or '.join(named)} fits it{more}"
            elif induced:
                tail = f": {len(induced)} induced layout{'s' * (len(induced) != 1)} fit it, e.g. {induced[0]}"
            else:
                tail = f": no {fam} layout fits it"
            problems.append(f"size {w}x{h} is not {aspects} like {fam}" + (f" preset {preset!r}" if preset else "") + tail)
    if not cli.ground_renderable(plan.get("ground")):
        problems.append(f"ground {plan['ground']!r} cannot be drawn: use black, white, light, transparent, "
                        f"tilted or a mapping such as {{fill: [r, g, b]}}")
    if not known:
        return problems
    tmpl = cli.template(fam, preset)
    names = {s["id"] for s in tmpl.get("slots") or []}
    for s in plan.get("slots") or []:
        if s.get("id") not in names:
            problems.append(f"slot {s.get('id')!r} is not a slot of {fam}" + (f" {preset}" if preset else ""))
        elif s.get("required") and "candidates" in s and not s["candidates"]:
            why = "; ".join(f"{e['block']}: {e['why']}" for e in s.get("excluded") or []) or "no block of the bank fits it"
            problems.append(f"slot {s['id']} ({' | '.join(s['accepts'])}, {s['shape']}) is required and no block can "
                            f"honestly fill it on this page ({why})"
                            + _other_layouts(plan))
    problems += hybrid_problems(plan, tmpl)
    return problems


def _other_layouts(plan):
    facts = plan.get("facts")
    if not facts:
        return ""
    ok = [v for v in fillable(plan["family"], plan.get("size"), facts) if v != (plan.get("preset") or "the default")]
    return f"; layouts of {plan['family']} this page can fill: {', '.join(ok)}" if ok else \
        f"; no {plan['family']} layout can be filled here: pick another family"


def hybrid_problems(plan, tmpl):
    """A plan's `items` are only hybrid chrome (kinds.MODEL_KINDS) a worker's
    node paints, `rendered_by: model` with a reason and no string; everything
    lp-compose draws comes from a bank block in a slot."""
    out = []
    panel_names = tmpl["panels"]
    seen = set()
    for it in plan.get("items") or []:
        cid, kind = it.get("id"), it.get("kind")
        if not cid or cid in seen:
            out.append(f"item id {cid!r} missing or repeated")
        seen.add(cid)
        if it.get("rendered_by") != "model":
            out.append(f"item {cid!r}: a plan item is hybrid chrome (`rendered_by: model`); compose chrome comes "
                       "from a bank block in a slot (blocks-<slot>.yaml)")
            continue
        if kind not in kinds.MODEL_KINDS:
            out.append(f"item {cid!r}: kind {kind!r} cannot be rendered_by: model "
                       f"(compose draws it; only {', '.join(sorted(kinds.MODEL_KINDS))} are hybrid)")
        if not (it.get("reason") or "").strip():
            out.append(f"item {cid!r}: rendered_by: model needs a reason")
        if it.get("text"):
            out.append(f"item {cid!r}: a model-rendered item carries no text (strings are never model-rendered)")
        for key in ("image",):
            v = it.get(key)
            if isinstance(v, dict) and v.get("from") not in panel_names:
                out.append(f"item {cid!r}: {key} from panel {v.get('from')!r}, which {plan['family']} does not have")
    return out


# the string fields each text kind draws, all of which must be filled
_TEXT_FIELDS = {"pill": ("text",), "label": ("text",), "text": ("text",), "round-badge": ("text",),
                "tool-pill": ("text",), "headline": ("text",), "adjust-panel": ("title",),
                "list-panel": ("active_text",), "profile-card": ("name", "caption"), "prompt-text": ("text",),
                "check-row": ("text",), "statement": ("text",)}


def blank_chrome(it):
    """What an item would draw with nothing in it: an empty string, a tile with
    no glyph, a swatch with no colours, a list row with no model, a mockup card
    with no picture. Blank placeholder chrome reads as an unfinished mockup, so
    every piece must be tied to a source: the page copy, a panel
    (`{from: <panel>}`), the tool, or the generating model."""
    kind = it.get("kind")
    out = [f"{f} is empty" for f in _TEXT_FIELDS.get(kind, ()) if not str(it.get(f) or "").strip()]
    if kind in ("tile", "icon", "crop-badge") and not it.get("icon"):
        out.append("a tile with no glyph")
    if kind == "swatch" and not it.get("colours"):
        out.append("a swatch with no colours: `colours: {from: <panel>}` or hex colours from `> chrome:`")
    if kind == "list-panel":
        others = it.get("rows_text") or []
        if len(others) < it.get("rows", 4) - 1 or not all(str(r).strip() for r in others):
            out.append(f"{it.get('rows', 4) - 1} other rows need model names (the catalogue fills them once the "
                       "ticked model is named)")
    if kind == "mark-tile" and not it.get("model"):
        out.append("a mark tile with no model: it names the model that makes the picture")
    if kind == "chip-bar" and not all(str(x.get("text") or "").strip() for x in it.get("items") or [{}]):
        out.append("a chip with no text")
    if kind == "profile-card" and not it.get("image"):
        out.append("a mockup card with an empty image well: `image: {from: <panel>}`")
    if kind == "list-card" and not [r for r in it.get("rows") or [] if str(r).strip()]:
        out.append("a list with no rows")
    if kind == "form-card" and not (it.get("fields") and it.get("result")):
        out.append("a calculator with no fields or no result")
    return out


def check_blocks(plan, doc):
    """Problems with a worker's picks (blocks-<slot>.yaml) for this plan: the
    bank rules (bank.check), then anything a picked block would draw blank."""
    tmpl = cli.template(plan["family"], plan.get("preset"))
    problems = bank.check(plan, tmpl, doc, plan.get("facts") or {})
    if not problems:
        for it in bank.resolve(plan, tmpl, doc):
            problems += [f"{it['id']}: {p}" for p in blank_chrome(it)]
    return problems


def picked_items(plan, doc):
    return bank.resolve(plan, cli.template(plan["family"], plan.get("preset")), doc)


def made_by(plan, doc):
    """{panel: {model, because}} the picks bind: an attribution block makes its
    panels that model's output (compose.models.made_by)."""
    items = picked_items(plan, doc)
    page = (plan.get("facts") or {}).get("page")
    return models.made_by(page, plan["family"], plan.get("preset"), items, claimed_panels(plan))


def to_spec(plan, images, doc=None):
    """A compose spec (dict) from a plan, the worker's picks and a {panel:
    image path} map. The chrome is exactly the picked blocks, resolved; a plan
    item `rendered_by: model` is painted by a worker's node and never drawn."""
    spec = {"slot": plan.get("slot"), "family": plan["family"], "size": plan["size"],
            "panels": {name: {"image": images[name]} for name in images}}
    for p in plan.get("panels") or []:  # a derived Before: the After's image, degraded at render
        src = p.get("from")
        if src and src != "pair" and p["panel"] not in images and src in images:
            spec["panels"][p["panel"]] = {"image": images[src]}
        if p.get("degrade") and p["panel"] in spec["panels"]:
            spec["panels"][p["panel"]]["degrade"] = p["degrade"]
        if p.get("holds") == "scene" and p.get("fit", "cover") == "cover" and p["panel"] in spec["panels"]:
            spec["panels"][p["panel"]]["anchor"] = "subject"  # a cover crop keeps the face (compose/subject.py)
    for key in ("preset", "ground"):
        if plan.get(key) is not None:
            spec[key] = plan[key]
    spec["chrome"] = picked_items(plan, doc) if doc else []
    return spec
