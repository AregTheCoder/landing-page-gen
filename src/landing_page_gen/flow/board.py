"""A slot's `workflow.yaml` read as a Picsart Flow board.

Picsart Flow (picsart.com/create/workflows) builds a creative as a graph of
nodes on a canvas: an input step (START, uploads, references, a prompt),
processing nodes (Image, Video, Text, Audio, Motion, each on one AI model),
and an output step (END). Workers author the same object headlessly: every
`steps:` entry is one Flow node with a `node:` kind and an `in:` list of the
nodes it takes its input from; `start:` is the START node and `final:` the
END node. The canvas itself has no API, so `sheet()` renders the board as the
exact node list a person would place and wire in the Flow editor, and
`check()` catches a board that would not wire (a node fed by a later node, a
kind that does not match its engine, an image node off the pro model with no
quoted copy, a template board without its source)."""

import re
from collections import Counter
from pathlib import Path

import yaml

from ..compose import kinds as _kinds
from ..compose.families import FAMILIES as _COMPOSE_FAMILIES

PRO_IMAGE = "gpt-image-2.5-sunburst"  # the default image model (was gemini-3-pro-image until 2026-09-23)
BOARDS = ("blank", "template")
# Absolute so `find_templates`/`load_templates` resolve the catalogue whatever
# the cwd (a hook or a Bash `cd` used to silently read `[]`).
TEMPLATES_YAML = Path(__file__).resolve().parents[3] / "corpus" / "flow-templates.yaml"


def composable(family):
    """Whether `lp-compose` can draw this family's chrome (it has a template).
    A family with a `compose` recipe step that is NOT composable yet finishes
    on an `enhance` upscale instead, until slice B registers its preset."""
    return family in _COMPOSE_FAMILIES

# Planned, mandatory recipe per family. A board is authored WHOLE from this
# recipe up front — every planned node is laid down and run, not grown
# reactively when a gate happens to find a flaw. Each recipe is an ordered list
# of planned steps; a step is the set of node kinds that can satisfy it. The
# first image is the base generate, the second the planned i2i refine (which
# used to be optional). `enhance` is the planned finishing upscale; `compose`,
# `cutout` and the `background`/`enhance`/`cutout` edit are the family's own
# chrome and derived-panel steps. `check()` enforces this whenever the board
# names its `family:`; a board that skips a planned step does not wire.
_IMG = frozenset({"image"})
RECIPES = {
    "full-bleed":          [_IMG, _IMG, frozenset({"enhance"})],
    "cinematic-still":     [_IMG, _IMG, frozenset({"enhance"})],
    "graphic-collage":     [_IMG, _IMG],
    "outcome-tile":        [_IMG, _IMG],
    "dark-composite":      [_IMG, _IMG, frozenset({"compose"})],
    "template-mockup":     [_IMG, _IMG, frozenset({"compose"})],
    "prompt-card":         [_IMG, _IMG, frozenset({"compose"})],
    "mockup-card":         [_IMG, _IMG, frozenset({"compose"})],
    "vs-two-up":           [_IMG, _IMG, frozenset({"compose"})],
    "panel-overlay":       [_IMG, _IMG, frozenset({"compose"})],
    "crop-frame":          [_IMG, _IMG, frozenset({"compose"})],
    "before-after":        [_IMG, frozenset({"enhance", "background", "cutout"}), frozenset({"compose"})],
    "cutout-checkerboard": [_IMG, frozenset({"cutout"}), frozenset({"compose"})],
}
# A `compose` step only stands for a family `lp-compose` can actually draw.
# prompt-card, mockup-card and vs-two-up carry a `compose` step here but have no
# template yet (`Template: none; brief as X`), so demanding one would make every
# such board un-wireable. Until slice B registers their presets they finish on an
# `enhance` upscale instead; `composable()` flips them back automatically.
_COMPOSE = frozenset({"compose"})
_ENHANCE = frozenset({"enhance"})
RECIPES = {
    fam: [(_ENHANCE if step == _COMPOSE and not composable(fam) else step) for step in recipe]
    for fam, recipe in RECIPES.items()
}

# A video slot's recipe is its poster family's still recipe followed by the two
# video nodes video-workflows.md plans: a draft on the mini tier, then the
# final. `recipe_for` keys on the board's `kind:` (inferred for old records).
_VIDEO = frozenset({"video"})
VIDEO_TAIL = [_VIDEO, _VIDEO]
VIDEO_DRAFT_HINT = "mini"   # seedance-2.0-mini (and its -video-extend) is the draft tier
VIDEO_MAX_SECONDS = 30      # Seedance's `duration` ceiling; a longer target goes through extend
DRAFTED_FAMILIES = ("seedance",)      # models with a mini draft tier; another model's clip has none to draft on
START_IN_IMAGE_URLS = ("sora-2",)     # models that take the start still in imageUrls, not extra.startFrame
REF_RE = re.compile(r"^<step (\d+) passed>$")

# Human label for a recipe step-set, so `recipe_row` can render a brief's
# recipe line from RECIPES itself instead of a hand-typed table that drifts.
_STEP_LABEL = {
    frozenset({"enhance"}): "enhance",
    frozenset({"compose"}): "compose",
    frozenset({"cutout"}): "cutout (remove_bg)",
    frozenset({"enhance", "background", "cutout"}): "edit (enhance/background/cutout)",
}


# A templated callout clip (`> motion: timeline <preset>`, compose/timeline.py)
# is the poster family's still steps, then one `motion` node on lp-compose that
# animates them: no Seedance draft or final unless a panel is a clip, and no
# separate compose step (the timeline is the composition).
_MOTION = frozenset({"motion"})
TIMELINE_TAIL = [_MOTION]


def recipe_for(family, kind="image"):
    recipe = RECIPES.get(family)
    if not recipe:
        return None
    if kind == "timeline":
        return [step for step in recipe if step != _COMPOSE] + TIMELINE_TAIL
    return recipe + VIDEO_TAIL if kind == "video" else recipe


def board_kind(doc):
    """`kind:` of the board; a record without one is a video board when it has a video node."""
    return doc.get("kind") or ("video" if any(s["node"] == "video" for s in nodes(doc)) else "image")


def recipe_row(family, kind="image"):
    """The family's planned recipe as one line ("generate -> i2i refine ->
    enhance"), rendered from RECIPES so it always matches what check() enforces.
    None for a family with no recipe."""
    recipe = recipe_for(family, kind)
    if not recipe:
        return None
    parts, imgs, vids = [], 0, 0
    for step in recipe:
        if step == _IMG:
            parts.append("generate" if imgs == 0 else "i2i refine")
            imgs += 1
        elif step == _VIDEO:
            parts.append("video draft (mini)" if vids == 0 else "video final")
            vids += 1
        elif step == _MOTION:
            parts.append("timeline (lp-compose --timeline)")
        else:
            parts.append(_STEP_LABEL.get(step, "/".join(sorted(step))))
    return " -> ".join(parts)


# Flow node kind -> the engine it runs on over MCP (or locally). `text` and
# `ref` nodes make no call: the worker writes the text; a ref is a URL.
NODE_ENGINES = {
    "text": set(),
    "ref": set(),
    "image": {"picsart_generate"},
    "edit": {"picsart_generate"},
    "cutout": {"picsart_remove_bg"},
    "background": {"picsart_change_bg"},
    "enhance": {"picsart_enhance"},
    "vectorize": {"picsart_vectorize"},
    "video": {"picsart_generate"},
    "motion": {"picsart_media_export", "picsart_media_apply_scene_template", "picsart_media_patch_scene",
               "picsart_media_validate_scene", "picsart_media_contact_sheet", "lp-compose"},
    "compose": {"lp-compose"},
}
# Upscale models an `enhance` node may run. `picsart_enhance` is the direct
# tool; when Picsart Drive is full it 403s (no saveToDrive override), so the
# same upscale engine is reached through `picsart_generate` on one of these
# models with saveToDrive:false. `lp-flow check` accepts that substitution.
ENHANCE_MODELS = {"picsart-enhance", "topaz-upscale-image"}
# The same for a `cutout`: picsart_remove_bg 403s on Drive auto-save too
# (blind-1-4), and picsart_generate runs its segmenter with saveToDrive:false.
CUTOUT_MODELS = {"picsart-sod-v8-2"}
DRIVE_WORKAROUND = {"enhance": ENHANCE_MODELS, "cutout": CUTOUT_MODELS}
EDIT_MODELS = {"picsart-qwen-image-edit"}
VIDEO_MODEL_HINT = ("seedance", "kling", "luma", "veo", "omni", "runway", "video")


def infer_node(step):
    """The Flow kind of a step that predates `node:` (live-1 to live-4 records)."""
    tool, model = step.get("tool") or "", step.get("model") or ""
    if tool == "lp-compose":
        return "compose"
    if tool == "picsart_remove_bg":
        return "cutout"
    if tool == "picsart_change_bg":
        return "background"
    if tool == "picsart_enhance":
        return "enhance"
    if tool.startswith("picsart_media"):
        return "motion"
    if tool == "picsart_generate":
        if any(h in model for h in VIDEO_MODEL_HINT):
            return "video"
        if model in EDIT_MODELS:
            return "edit"
        return "image"
    return "text" if step.get("params", {}).get("text") is not None else "ref"


def infer_in(step, steps):
    """Upstream nodes of a step without `in:`: the `<step N passed>` placeholders
    in its params, else the step before it, else START."""
    ids = sorted({int(n) for n in re.findall(r"<step (\d+) passed>", yaml.safe_dump(step.get("params") or {}))})
    if ids:
        return ids
    earlier = [s["id"] for s in steps if s.get("id") is not None and s["id"] < step.get("id", 0)]
    return [max(earlier)] if earlier else ["start"]


def nodes(doc):
    """The board's steps with `node` and `in` filled (inferred when absent)."""
    steps = doc.get("steps") or []
    out = []
    for st in steps:
        s = dict(st)
        s["node"] = s.get("node") or infer_node(s)
        s["in"] = s.get("in") or infer_in(s, steps)
        out.append(s)
    return out


def recipe_problems(doc):
    """A board that skips a node its family's planned recipe requires. The
    recipe is authored up front, so this catches a shallow board (a lone
    generate where the plan calls for generate -> i2i refine -> finish) before
    it runs — enforced only when the board names a `family:` in RECIPES."""
    family = doc.get("family")
    recipe = recipe_for(family, board_kind(doc))
    if not recipe:
        return []
    slot = doc.get("slot", "?")
    kinds = [s["node"] for s in nodes(doc)]
    problems = []
    need_img = sum(1 for step in recipe if step == _IMG)
    have_img = kinds.count("image")
    if have_img < need_img:
        problems.append(
            f"{slot}: {family} recipe plans {need_img} image nodes (a base generate and "
            f"the planned i2i refine); board has {have_img}. Author the refine up front, "
            f"do not wait for a gate to fail.")
    avail = Counter(k for k in kinds if k != "image")
    for step in recipe:
        if step == _IMG:
            continue
        if not any(avail.get(k, 0) > 0 for k in step):
            label = " or ".join(sorted(step))
            hint = " (a mini draft and a final, video-workflows.md)" if step == _VIDEO else ""
            problems.append(f"{slot}: {family} recipe plans a {label} node{hint}; board has "
                            f"{'too few' if step == _VIDEO else 'none'}")
        else:
            for k in step:
                if avail.get(k, 0) > 0:
                    avail[k] -= 1
                    break
    return problems


def video_problems(s, sid, seen, drafted):
    """The video non-negotiables (video-workflows.md), checked on the yaml: audio
    off, async, the still (or an earlier clip) wired by `<step N passed>` and
    named in `in:`, nothing from outside the board, a mini draft before any
    final, `duration` within Seedance's ceiling. `seen` maps earlier node ids
    to their kinds; `drafted` says whether a mini video node came before."""
    p = s.get("params") or {}
    extra = p.get("extra") or {}
    out = []
    if p.get("generateAudio") is not False:
        out.append(f"{sid}: video node without generateAudio: false")
    if p.get("async") is not True:
        out.append(f"{sid}: video node without async: true")
    model = s.get("model") or ""
    start_in_urls = model.startswith(START_IN_IMAGE_URLS)
    if p.get("imageUrls") and not start_in_urls:
        out.append(f"{sid}: video node wires imageUrls; references are read for the look, never wired, "
                   f"and the still enters through extra.startFrame")
    if (p.get("duration") or 0) > VIDEO_MAX_SECONDS:
        out.append(f"{sid}: duration {p['duration']} above Seedance's {VIDEO_MAX_SECONDS} s; "
                   f"reach a longer target through an extend node")
    if model.startswith(DRAFTED_FAMILIES) and VIDEO_DRAFT_HINT not in model and not drafted:
        out.append(f"{sid}: {model} before a {VIDEO_DRAFT_HINT} draft node; always draft first")
    refs = {"extra.startFrame": extra.get("startFrame"), "extra.endFrame": extra.get("endFrame"),
            "params.videoUrl": p.get("videoUrl")}
    if start_in_urls:
        for i, u in enumerate(p.get("imageUrls") or []):
            refs[f"params.imageUrls[{i}]"] = u  # this model's start still, wired like extra.startFrame
    for i, u in enumerate(p.get("videoUrls") or []):
        refs[f"params.videoUrls[{i}]"] = u
    fed = False
    for key, val in refs.items():
        if not val:
            continue
        m = REF_RE.match(str(val))
        if not m:
            out.append(f"{sid}: {key} is a literal URL; write `<step N passed>` for the node that made it "
                       f"(nothing from outside the board enters a video node)")
            continue
        n = int(m.group(1))
        want_video = key.startswith("params.video")
        if n not in seen or (seen[n] == "video") != want_video:
            out.append(f"{sid}: {key} names node {n}, which is not an earlier {'video' if want_video else 'still'} node")
        elif n not in s["in"]:
            out.append(f"{sid}: {key} names node {n} but in: does not")
        fed = True
    if not fed:
        out.append(f"{sid}: video node with no still (extra.startFrame) or clip (videoUrls) from an earlier node; "
                   f"text-to-motion is not a recipe")
    return out


def hybrid_node_problems(s, sid, kind):
    """The hybrid model-step gate (image-workflows.md, prd.md). A node that
    renders a plan's hybrid chrome item carries `chrome_item: <id>` and must be a
    generate/edit node with a reason; a generate/edit node that names interface
    furniture in its prompt (kinds.UI_WORDS) but claims no chrome_item is
    smuggling chrome the model must not draw — lp-compose draws chrome."""
    out = []
    item = s.get("chrome_item")
    if item:
        if kind not in ("image", "edit"):
            out.append(f"{sid}: chrome_item {item!r} on a {kind} node; a model-rendered item is painted in an image or edit node")
        if not (s.get("reason") or "").strip():
            out.append(f"{sid}: chrome_item {item!r} without a reason (why this chrome must be model-rendered, not composed)")
    elif kind in ("image", "edit"):
        prompt = (s.get("params") or {}).get("prompt") or ""
        hit = sorted(w for w in _kinds.UI_WORDS if re.search(rf"\b{re.escape(w)}\b", prompt, re.I))
        if hit:
            out.append(f"{sid}: prompt names UI ({', '.join(hit)}) but the node has no chrome_item; chrome is drawn by "
                       f"lp-compose. For a hybrid item, mark the plan item rendered_by: model and set chrome_item here")
    return out


# nodes whose output is a model's picture (a cutout, an upscale, a frame grab or
# the compose step keep the picture's authorship; these make a new one)
GENERATIVE = ("image", "edit", "background", "video")


def attribution_problems(doc, required):
    """An image a page presents as a model's output must be that model's
    (`models.made_by`, written to the section's made-by.yaml). For each
    attributed panel, the node that makes it (`panel: <name>`) and every
    generative node upstream of it must run the required model; for a slot with
    no composite ('*'), every generative node must. A required model of "no: ..."
    is a slot that cannot be generated truthfully at all."""
    slot = doc.get("slot", "?")
    steps = nodes(doc)
    by_id = {s.get("id"): s for s in steps}
    out = []

    def lineage(s, model, seen=None):
        seen = seen if seen is not None else set()
        if s.get("id") in seen:
            return []
        seen.add(s.get("id"))
        if s["node"] == "video" and s.get("model") == model:
            return [s]  # the model's own clip is its output; the still it starts from is its input
        return [s] + [x for up in s["in"] if up in by_id for x in lineage(by_id[up], model, seen)]

    for panel, req in (required or {}).items():
        model, because = req.get("model") or "", req.get("because", "")
        if model.startswith("no:"):
            out.append(f"{slot}: {panel} cannot be generated truthfully ({model[3:].strip()}); {because}")
            continue
        if panel == "*":
            chain = steps
        else:
            makers = [s for s in steps if s.get("panel") == panel]
            if not makers:
                out.append(f"{slot}: no node marks `panel: {panel}`, which must be {model}'s output ({because})")
                continue
            chain = [x for m in makers for x in lineage(m, model)]
        for s in chain:
            if s["node"] in GENERATIVE and s.get("model") != model:
                out.append(f"{slot} node {s.get('id')}: {s['node']} on {s.get('model')}, but {panel if panel != '*' else 'the slot'} "
                           f"must be {model}'s output ({because})")
    return out


def check(doc, required=None):
    """Problems with one slot's board; empty when it wires. `required` is the
    slot's entry of made-by.yaml (see `attribution_problems`)."""
    slot = doc.get("slot", "?")
    problems = []
    board = doc.get("board", "blank")
    if board not in BOARDS:
        problems.append(f"{slot}: board {board!r} (blank or template)")
    if board == "template":
        t = doc.get("template") or {}
        for key in ("title", "url", "adapted"):
            if not t.get(key):
                problems.append(f"{slot}: template board without template.{key}")
    steps = nodes(doc)
    if not steps:
        problems.append(f"{slot}: no nodes between START and END")
    seen, drafted = {}, False
    for s in steps:
        sid = f"{slot} node {s.get('id')}"
        kind = s["node"]
        # An enhance node run through picsart_generate on an upscale model is the
        # accepted Drive-403 workaround (see ENHANCE_MODELS), not a wrong engine.
        enhance_workaround = (
            kind in DRIVE_WORKAROUND and s.get("tool") == "picsart_generate"
            and s.get("model") in DRIVE_WORKAROUND[kind]
        )
        if kind not in NODE_ENGINES:
            problems.append(f"{sid}: node kind {kind!r} (one of {', '.join(NODE_ENGINES)})")
        elif kind == "enhance" and s.get("tool") == "picsart_generate" and not enhance_workaround:
            problems.append(
                f"{sid}: enhance node on picsart_generate needs model in "
                f"{{{', '.join(sorted(ENHANCE_MODELS))}}} (the Drive-403 workaround: "
                f"picsart_generate + topaz-upscale-image, saveToDrive:false); else use picsart_enhance")
        elif s.get("tool") and s["tool"] not in NODE_ENGINES[kind] and NODE_ENGINES[kind] \
                and not enhance_workaround:
            problems.append(f"{sid}: {kind} node on {s['tool']} (expects {' or '.join(sorted(NODE_ENGINES[kind]))})")
        elif not s.get("tool") and NODE_ENGINES[kind]:
            problems.append(f"{sid}: {kind} node without a tool")
        for up in s["in"]:
            if up != "start" and up not in seen:
                problems.append(f"{sid}: fed by node {up!r}, which is not an earlier node or start")
        attributed = s.get("model") in {r.get("model") for r in (required or {}).values()}
        if kind == "image" and s.get("model") != PRO_IMAGE and not attributed and not (s.get("reason") or "").strip():
            problems.append(f"{sid}: image node on {s.get('model')} without a reason quoting the copy that names it")
        if kind == "motion" and s.get("tool") == "lp-compose" and not str(s.get("timeline") or "").endswith(".yaml"):
            problems.append(f"{sid}: a timeline node names its motion spec (`timeline: motion-<slot>.yaml`, the brief wrote it)")
        if kind == "video":
            problems += video_problems(s, sid, seen, drafted)
            drafted = drafted or VIDEO_DRAFT_HINT in (s.get("model") or "")
        problems += hybrid_node_problems(s, sid, kind)
        if s.get("id") is not None:
            seen[s["id"]] = kind
    if "final" not in doc:
        problems.append(f"{slot}: no END node (final:)")
    problems += recipe_problems(doc)
    problems += attribution_problems(doc, required)
    return problems


def made_by_file(folder):
    """The section's made-by.yaml ({slot: {panel: {model, because}}}), or {}."""
    path = Path(folder) / "made-by.yaml"
    return (yaml.safe_load(path.read_text()) or {}) if path.exists() else {}


def check_file(path):
    docs = [d for d in yaml.safe_load_all(Path(path).read_text()) if d]
    required = made_by_file(Path(path).parent)
    return [p for d in docs for p in check(d, required.get(d.get("slot")))]


def _short(text, n=90):
    text = " ".join(str(text).split())
    return text if len(text) <= n else text[: n - 1] + "…"


def sheet(docs):
    """The board as a canvas sheet: a Mermaid graph and one row per node, in
    wiring order, with the Flow node type, engine, model, prompt and gate. A
    person rebuilds it on the Flow canvas node by node; a reviewer reads it."""
    lines = ["# Flow board", ""]
    for doc in docs:
        slot = doc.get("slot", "?")
        board = doc.get("board", "blank")
        t = doc.get("template") or {}
        head = f"## {slot} — {board} board"
        if board == "template" and t.get("title"):
            head += f" from “{t['title']}” ({t.get('url', '')})"
        lines += [head, ""]
        if t.get("adapted"):
            lines += [f"Adapted: {t['adapted']}", ""]
        steps = nodes(doc)
        lines += ["```mermaid", "flowchart LR", "  start([START])"]
        for s in steps:
            label = f"{s['id']} {s['node']}" + (f"<br/>{s['model']}" if s.get("model") else "")
            lines.append(f"  n{s['id']}[\"{label}\"]")
        lines.append("  end_([END])")
        for s in steps:
            for up in s["in"]:
                lines.append(f"  {'start' if up == 'start' else 'n' + str(up)} --> n{s['id']}")
        if steps:
            lines.append(f"  n{steps[-1]['id']} --> end_")
        lines += ["```", ""]
        lines += ["| node | Flow type | engine | model | in | prompt / params | gate | credits | status |",
                  "|---|---|---|---|---|---|---|---|---|"]
        for s in steps:
            params = s.get("params") or {}
            prompt = params.get("prompt") or params.get("text") or params.get("spec") or ""
            lines.append(
                f"| {s['id']} | {s['node']} | {s.get('tool') or '—'} | {s.get('model') or '—'} | "
                f"{', '.join(str(i) for i in s['in'])} | {_short(prompt)} | {_short(s.get('gate') or '')} | "
                f"{s.get('quoted_credits') if s.get('quoted_credits') is not None else '—'} | {s.get('status') or '—'} |")
        final = doc.get("final") or {}
        lines += ["", f"END: {final.get('url') or final.get('local') or 'not produced'}", ""]
    return "\n".join(lines)


def sheet_file(path):
    return sheet([d for d in yaml.safe_load_all(Path(path).read_text()) if d])


def load_templates(path=TEMPLATES_YAML):
    path = Path(path)
    return (yaml.safe_load(path.read_text()) or {}).get("templates", []) if path.exists() else []


def find_templates(family=None, device=None, query="", path=TEMPLATES_YAML):
    """Gallery templates whose `fits` names the family (and device when given),
    or whose title, tags or description carry a query word; best first."""
    words = {w.lower() for w in re.findall(r"[A-Za-z0-9]+", query) if len(w) > 2}
    scored = []
    for t in load_templates(path):
        fits = t.get("fits") or {}
        score = 0
        if family and family in (fits.get("families") or []):
            score += 4
        if device and device in (fits.get("devices") or []):
            score += 2
        hay = " ".join([t.get("title", ""), t.get("description", ""), " ".join(t.get("tags") or []), t.get("category", "")]).lower()
        score += sum(1 for w in words if w in hay)
        if score:
            scored.append((score, t))
    scored.sort(key=lambda x: -x[0])
    return [t for _, t in scored]
