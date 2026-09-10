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
from pathlib import Path

import yaml

PRO_IMAGE = "gemini-3-pro-image"
BOARDS = ("blank", "template")
TEMPLATES_YAML = Path("corpus/flow-templates.yaml")

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
    "video": {"picsart_generate"},
    "motion": {"picsart_media_export", "picsart_media_apply_scene_template", "picsart_media_patch_scene",
               "picsart_media_validate_scene", "picsart_media_contact_sheet"},
    "compose": {"lp-compose"},
}
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


def check(doc):
    """Problems with one slot's board; empty when it wires."""
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
    seen = set()
    for s in steps:
        sid = f"{slot} node {s.get('id')}"
        kind = s["node"]
        if kind not in NODE_ENGINES:
            problems.append(f"{sid}: node kind {kind!r} (one of {', '.join(NODE_ENGINES)})")
        elif s.get("tool") and s["tool"] not in NODE_ENGINES[kind] and NODE_ENGINES[kind]:
            problems.append(f"{sid}: {kind} node on {s['tool']} (expects {' or '.join(sorted(NODE_ENGINES[kind]))})")
        elif not s.get("tool") and NODE_ENGINES[kind]:
            problems.append(f"{sid}: {kind} node without a tool")
        for up in s["in"]:
            if up != "start" and up not in seen:
                problems.append(f"{sid}: fed by node {up!r}, which is not an earlier node or start")
        if kind == "image" and s.get("model") != PRO_IMAGE and not (s.get("reason") or "").strip():
            problems.append(f"{sid}: image node on {s.get('model')} without a reason quoting the copy that names it")
        if s.get("id") is not None:
            seen.add(s["id"])
    if "final" not in doc:
        problems.append(f"{slot}: no END node (final:)")
    return problems


def check_file(path):
    docs = [d for d in yaml.safe_load_all(Path(path).read_text()) if d]
    return [p for d in docs for p in check(d)]


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
