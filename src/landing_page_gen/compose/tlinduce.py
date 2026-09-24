"""Timelines induced from the corpus's clips: a storyboard (`lp-corpus
storyboard`: the states a clip holds, their keyframes read as layouts, the
transitions between) turned into a motion spec the timeline renderer plays.

Each state's regions are its elements. An element is followed from one state
to the next by what it looks like (a small grey signature and its colour, the
words it holds), wherever it moved and however it was scaled; a followed
element is one layer whose rect is keyed at every hold and eased across each
transition, an element that arrives fades in over the transition, one that
leaves fades out. The replica cuts each layer's picture from the keyframe it
first appears in, so what it tests is the choreography alone: where things
go and when. Played against the clip's own dense samples it scores every
moment; the worst moments are what is not yet understood.

    uv run lp-compose --learn-clips [--limit N] --out research/clips"""

import json
from pathlib import Path

import numpy as np
from PIL import Image

from .families import REF

SIG = 24          # px of an element's grey signature
MATCH = 0.72      # signature correlation that follows an element to the next state
FADE = 0.25       # s: an element arriving without a transition window fades this long


def _sig(img):
    g = np.asarray(img.convert("L").resize((SIG, SIG), Image.BILINEAR), np.float32)
    g = g - g.mean()
    n = float(np.linalg.norm(g))
    col = np.asarray(img.convert("RGB").resize((4, 4)), np.float32).reshape(-1, 3).mean(0)
    return (g / n if n > 1e-3 else g).ravel(), col, n


def elements(state, key_img):
    """A state's elements: its reading's regions, in REF, with their pictures."""
    rd = state["reading"]
    s = REF / rd["size"][0]
    out = []
    for i, reg in enumerate(rd["regions"]):
        x0, y0, x1, y1 = reg["box"]
        if x1 - x0 < 8 or y1 - y0 < 8:
            continue
        crop = key_img.crop((x0, y0, x1, y1))
        sig, col, energy = _sig(crop)
        out.append({"kind": reg["kind"], "ref": [v * s for v in reg["box"]], "img": crop, "sig": sig, "col": col,
                    "flat": energy < 1.0, "texts": [t["text"] for t in rd["texts"] if t.get("region") == i]})
    return out


def _same_words(a, b):
    """Whether two elements say the same thing (OCR may slip a letter): an
    element whose words change between states is a new element in the same
    place, not the old one moved (a list that scrolls, a chip that is picked)."""
    from difflib import SequenceMatcher
    ta, tb = " ".join(sorted(a["texts"])).casefold(), " ".join(sorted(b["texts"])).casefold()
    return SequenceMatcher(None, ta, tb).ratio() >= 0.85


def _score(a, b):
    if a["kind"] != b["kind"] and not (a["flat"] or b["flat"]):
        return 0.0
    if a["texts"] and b["texts"] and not _same_words(a, b):
        return 0.0
    colour = 1 - min(1.0, float(np.abs(a["col"] - b["col"]).mean()) / 60)
    if a["flat"] or b["flat"]:  # a plain card: its colour and its words
        words = len(set(a["texts"]) & set(b["texts"])) / max(1, len(set(a["texts"]) | set(b["texts"])))
        return 0.5 * colour + 0.5 * words if (a["texts"] or b["texts"]) else colour * 0.8
    corr = float(a["sig"] @ b["sig"])
    return 0.75 * corr + 0.25 * colour


def link(prev, nxt):
    """One-to-one matches {i: j} between two states' elements, best first."""
    pairs = sorted(((_score(a, b), i, j) for i, a in enumerate(prev) for j, b in enumerate(nxt)), reverse=True)
    out, used = {}, set()
    for sc, i, j in pairs:
        if sc < MATCH:
            break
        if i in out or j in used:
            continue
        out[i] = j
        used.add(j)
    return out


def chains(board, store):
    """Layers: each a list of (state index, element) the element was followed through."""
    folder = Path(store) / board["id"]
    per_state = []
    for st in board["states"]:
        with Image.open(folder / st["key"]) as im:
            per_state.append(elements(st, im.convert("RGB")))
    open_chains, done = {}, []
    for k, elems in enumerate(per_state):
        if k == 0:
            open_chains = {j: [(0, e)] for j, e in enumerate(elems)}
            continue
        m = link(per_state[k - 1], elems)
        nxt = {}
        for i, ch in open_chains.items():
            if i in m:
                ch.append((k, elems[m[i]]))
                nxt[m[i]] = ch
            else:
                done.append(ch)
        for j, e in enumerate(elems):
            if j not in nxt:
                nxt[j] = [(k, e)]
        open_chains = nxt
    return done + list(open_chains.values())


def _ground(board, store):
    """The colour the clip plays on: the median of its first sample's border (a
    see-through clip reads black, as its samples and a dark section show it)."""
    with np.load(Path(store) / board["id"] / "samples.npz") as z:
        f = z["frames"][0].astype(np.float32)
    ring = np.concatenate([f[0], f[-1], f[:, 0], f[:, -1]])
    return [int(v) for v in np.median(ring, axis=0)]


def spec(board, layers, work, store):
    """The motion spec that replays a storyboard's choreography with its own pictures."""
    work = Path(work)
    (work / "sprites").mkdir(parents=True, exist_ok=True)
    w, h = board["size"]
    states, trans = board["states"], {t["to"]: t for t in board["transitions"]}
    ground = _ground(board, store)
    out_layers, images = [], {}
    for n, ch in enumerate(layers):
        name = f"el-{n}"
        ch[0][1]["img"].save(work / "sprites" / f"{name}.png")
        images[name] = str(work / "sprites" / f"{name}.png")
        keys = []
        first, last = ch[0][0], ch[-1][0]
        layer = {"id": name, "role": "subject", "panel": name}
        if first > 0:  # it arrives the way the transition into its first state arrives
            t = trans.get(first) or {}
            t0 = t.get("t0", max(0.0, states[first]["t0"] - FADE))
            t1 = states[first]["t0"]
            kind = t.get("type", "crossfade")
            if kind == "cut":
                keys.append({"t": round(t1, 3), "rect": ch[0][1]["ref"], "opacity": 0})
                keys.append({"t": round(t1, 3), "opacity": 1})
            elif kind.startswith("wipe-"):
                layer["wipe_from"] = {"lr": "left", "rl": "right", "tb": "top", "bt": "bottom"}[kind[5:]]
                keys.append({"t": round(t0, 3), "rect": ch[0][1]["ref"], "opacity": 1, "wipe": 0})
                keys.append({"t": round(t1, 3), "wipe": 1})
            else:
                keys.append({"t": round(t0, 3), "rect": ch[0][1]["ref"], "opacity": 0})
                keys.append({"t": round(t1, 3), "opacity": 1})
        else:
            keys.append({"t": 0, "rect": ch[0][1]["ref"], "opacity": 1})
        for k, e in ch:
            keys.append({"t": round(states[k]["t0"], 3), "rect": e["ref"]})
            keys.append({"t": round(states[k]["t1"], 3), "rect": e["ref"]})
        if last < len(states) - 1:  # it leaves the way the next transition goes: at once on a cut, else fading
            t = trans.get(last + 1) or {}
            t0 = states[last]["t1"]
            t1 = t.get("t1", t0 + FADE)
            if t.get("type") == "cut":
                keys.append({"t": round(t1, 3), "opacity": 1})
                keys.append({"t": round(t1, 3), "opacity": 0})
            else:
                keys.append({"t": round(t0, 3), "opacity": 1})
                keys.append({"t": round(t1, 3), "opacity": 0})
        keys.sort(key=lambda k: k["t"])
        out_layers.append({**layer, "keys": keys})
    hi = round(REF * h / w)
    body = {"slot": board["id"], "preset": "learned", "size": f"{w - w % 2}x{h - h % 2}", "fps": 30,
            "ground": ground,
            "radius": 0, "duration": board["duration"], "layers": out_layers, "panels": {k: "" for k in images},
            "ref_height": hi}
    return body, images


def score(board, spec_body, images, store):
    """Per-sample error between the replay and the clip's own samples (0..1,
    mean absolute difference at the sample size), and its mean."""
    from .timeline import Renderer
    with np.load(Path(store) / board["id"] / "samples.npz") as z:
        samples = z["frames"].astype(np.float32) / 255
        step = float(z["step"])
    r = Renderer(spec_body, images)
    errs = []
    hs, ws = samples.shape[1:3]
    for i in range(len(samples)):
        f = r.frame(i * step).convert("RGB").resize((ws, hs), Image.BILINEAR)
        errs.append(float(np.abs(np.asarray(f, np.float32) / 255 - samples[i]).max(-1).mean()))
    return errs


def learn(board, store, work):
    ch = chains(board, store)
    body, images = spec(board, ch, work, store)
    errs = score(board, body, images, store)
    Path(work, "motion.json").write_text(json.dumps(body))
    return {"id": board["id"], "page": board["page"], "slot": board["slot"], "states": len(board["states"]),
            "layers": len(ch), "followed": sum(1 for c in ch if len(c) > 1), "error": round(float(np.mean(errs)), 4),
            "worst": [round(i * board["step"], 1) for i in np.argsort(errs)[-3:][::-1]], "errors": errs}


TIMELINES = Path(__file__).parent / "assets" / "timelines.yaml"


def run(out_dir, limit=None, store=None, write_to=TIMELINES):
    """Learn every storyboard: its choreography replayed from its own
    keyframes, then its learned template redrawn with our blocks; both scored
    against the clip. Every learned template is written to `write_to` with
    its two errors (the gap between them is what our blocks still draw
    differently)."""
    import yaml
    from ..corpus import storyboard as sb
    store = store or sb.STORE
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    results, learned = [], {}
    for i, b in enumerate(sb.every(store)):
        if limit and i >= limit:
            break
        try:
            r = learn(b, store, out_dir / b["id"] / "choreography")
            tmpl, _, _, errs = replay(b, store, out_dir / b["id"] / "full")
        except Exception as e:  # a board the replay cannot play is reported, never fatal
            results.append({"id": b["id"], "page": b["page"], "slot": b["slot"], "failed": str(e)[:200]})
            continue
        r.pop("errors", None)
        r["full_error"] = round(float(np.mean(errs)), 4)
        results.append(r)
        learned[f"t-{b['id']}"] = {**tmpl, "error": {"choreography": r["error"], "full": r["full_error"]}}
    (out_dir / "clips.json").write_text(json.dumps(results, indent=1))
    if write_to:
        header = ("# Timelines learned from the corpus's clips (`lp-compose --learn-clips`); rebuilt, never hand-edited.\n"
                  "# Each: panels and slots with a track (rect per state), holds, typed transitions, and the replay errors.\n")
        Path(write_to).write_text(header + yaml.safe_dump(json.loads(json.dumps(learned)), sort_keys=False, width=140))
    return results


def report(results):
    ok = sorted((r for r in results if "failed" not in r), key=lambda r: -r["error"])
    errs = [r["error"] for r in ok]
    lines = ["# Clip choreography replays", "",
             "Each storyboard replayed from its own keyframes (elements followed state to state, arriving by the "
             "measured transition) and scored against the clip's dense samples: mean absolute difference, 0 = identical.",
             "", f"{len(ok)} clips replayed, {len(results) - len(ok)} failed. Median error {np.median(errs):.3f}, "
             f"quartiles {np.percentile(errs, 25):.3f} / {np.percentile(errs, 75):.3f}." if errs else "", "",
             "| clip | states | layers | followed | choreography | full | worst moments (s) |", "|---|---|---|---|---|---|---|"]
    for r in ok:
        lines.append(f"| {r['page']} {r['slot']} ({r['id']}) | {r['states']} | {r['layers']} | {r['followed']} | "
                     f"{r['error']:.3f} | {r.get('full_error', float('nan')):.3f} | {', '.join(str(x) for x in r['worst'])} |")
    fails = [r for r in results if "failed" in r]
    if fails:
        lines += ["", "## Failed", ""] + [f"- {r['page']} {r['slot']} ({r['id']}): {r['failed']}" for r in fails]
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------- learned timeline templates

def _inside(inner, outer, pad=4):
    return inner[0] >= outer[0] - pad and inner[1] >= outer[1] - pad and inner[2] <= outer[2] + pad and inner[3] <= outer[3] + pad


def _carry(rect, frm, to):
    """A part's rect moved and scaled with its element (frm -> to)."""
    sx = (to[2] - to[0]) / max(1e-6, frm[2] - frm[0])
    sy = (to[3] - to[1]) / max(1e-6, frm[3] - frm[1])
    return [round(to[0] + (rect[0] - frm[0]) * sx, 1), round(to[1] + (rect[1] - frm[1]) * sy, 1),
            round(to[0] + (rect[2] - frm[0]) * sx, 1), round(to[1] + (rect[3] - frm[1]) * sy, 1)]


def skeleton(board, store):
    """A learned timeline template: the clip's pictures as panels and its blocks
    as slots, each with a track (its rect in every state it shows in), the
    states' holds and the typed transitions between them. Every part comes
    from the induced layout of the state it first shows in; parts inside a
    followed card move with the card."""
    from . import induce
    folder = Path(store) / board["id"]
    lays = []
    for st in board["states"]:
        rd = {"id": board["id"], "page": board["page"], "slot": board["slot"], "local": str(folder / st["key"]),
              **st["reading"]}
        lays.append(induce.induce(rd, merge=False))
    out = {"source": f"{board['id']} {board['page']} {board['slot']}", "duration": board["duration"],
           "size": board["size"], "ground": _ground(board, store),
           "states": [{"t0": st["t0"], "t1": st["t1"]} for st in board["states"]],
           "transitions": [{k: t[k] for k in ("from", "to", "t0", "t1", "type")} for t in board["transitions"]],
           "panels": {}, "slots": [], "surfaces": [], "exemplar": {"fills": {}}}
    n = {"p": 0, "s": 0}
    for ch in chains(board, store):
        k0, e0 = ch[0]
        lay = lays[k0]
        track = [{"state": k, "rect": [round(v, 1) for v in e["ref"]]} for k, e in ch]
        if e0["kind"] == "picture":
            n["p"] += 1
            name = f"p{n['p']}"
            best = next((p for p in lay["panels"].values() if _inside(p["rect"], e0["ref"], 8)), None)
            out["panels"][name] = {"holds": (best or {}).get("holds", "scene"), "ratio": (best or {}).get("ratio"),
                                   "track": track}
            continue
        parts = [s for s in lay["slots"] if _inside(s["rect"], e0["ref"])]
        surf = [s for s in lay["background"]["surfaces"] if _inside(s["rect"], e0["ref"])]
        for sf in surf:
            out["surfaces"].append({"fill": sf["fill"], "track": [{"state": k, "rect": _carry(sf["rect"], e0["ref"], e["ref"])}
                                                                  for k, e in ch]})
        for sl in parts:
            n["s"] += 1
            sid = f"s{n['s']}"
            out["slots"].append({**{k: v for k, v in sl.items() if k not in ("id", "rect")}, "id": sid,
                                 "track": [{"state": k, "rect": _carry(sl["rect"], e0["ref"], e["ref"])} for k, e in ch]})
            out["exemplar"]["fills"][sid] = lay["exemplar"]["fills"].get(sl["id"], {})
    return out


def _keys(track, states, trans):
    """Renderer keys for a part shown through `track`: arriving and leaving by
    the measured transitions, its rect held at each state and eased between."""
    first, last = track[0]["state"], track[-1]["state"]
    r0 = track[0]["rect"]
    keys, extra = [], {}
    if first > 0:
        t = trans.get(first) or {}
        t0, t1 = t.get("t0", max(0.0, states[first]["t0"] - FADE)), states[first]["t0"]
        kind = t.get("type", "crossfade")
        if kind == "cut":
            keys += [{"t": t1, "rect": r0, "opacity": 0}, {"t": t1, "opacity": 1}]
        elif kind.startswith("wipe-"):
            extra["wipe_from"] = {"lr": "left", "rl": "right", "tb": "top", "bt": "bottom"}[kind[5:]]
            keys += [{"t": t0, "rect": r0, "opacity": 1, "wipe": 0}, {"t": t1, "wipe": 1}]
        else:
            keys += [{"t": t0, "rect": r0, "opacity": 0}, {"t": t1, "opacity": 1}]
    else:
        keys.append({"t": 0, "rect": r0, "opacity": 1})
    for tr in track:
        st = states[tr["state"]]
        keys += [{"t": st["t0"], "rect": tr["rect"]}, {"t": st["t1"], "rect": tr["rect"]}]
    if last < len(states) - 1:
        t = trans.get(last + 1) or {}
        t0, t1 = states[last]["t1"], t.get("t1", states[last]["t1"] + FADE)
        keys += ([{"t": t1, "opacity": 1}, {"t": t1, "opacity": 0}] if t.get("type") == "cut"
                 else [{"t": t0, "opacity": 1}, {"t": t1, "opacity": 0}])
    for k in keys:
        k["t"] = round(float(k["t"]), 3)
    return sorted(keys, key=lambda k: k["t"]), extra


def compile_spec(tmpl, items, images_by_panel):
    """The renderer spec for a learned template: `items` {slot id: resolved block
    item}, `images_by_panel` {panel name: image path}; surfaces are drawn as cards."""
    states, trans = tmpl["states"], {t["to"]: t for t in tmpl["transitions"]}
    w, h = tmpl["size"]
    layers, panels = [], {}
    for i, sf in enumerate(tmpl["surfaces"]):
        keys, extra = _keys(sf["track"], states, trans)
        layers.append({"id": f"surface-{i}", "role": "background", "kind": "card", "fill": sf["fill"], **extra, "keys": keys})
    for name, p in tmpl["panels"].items():
        keys, extra = _keys(p["track"], states, trans)
        layers.append({"id": name, "role": "subject", "panel": name, **extra, "keys": keys})
        panels[name] = p.get("holds", "scene")
    for sl in tmpl["slots"]:
        it = items.get(sl["id"])
        if not it:
            continue
        keys, extra = _keys(sl["track"], states, trans)
        layers.append({**{k: v for k, v in it.items() if k not in ("rect", "id")}, "id": sl["id"], **extra, "keys": keys})
    return {"slot": tmpl["source"].split()[0], "preset": "learned", "size": f"{w - w % 2}x{h - h % 2}", "fps": 30,
            "ground": tmpl["ground"], "radius": 0, "duration": tmpl["duration"], "layers": layers, "panels": panels}


def replay(board, store, work):
    """The learned template redrawn from its own clip: panels cut from their
    first keyframe, each slot's block given the words read there. Returns the
    template, the spec and the per-sample error against the clip."""
    from . import bank, replica
    work = Path(work)
    work.mkdir(parents=True, exist_ok=True)
    tmpl = skeleton(board, store)
    folder = Path(store) / board["id"]
    images = {}
    for name, p in tmpl["panels"].items():
        st = board["states"][p["track"][0]["state"]]
        with Image.open(folder / st["key"]) as im:
            s = im.size[0] / REF
            im.convert("RGBA").crop(tuple(round(v * s) for v in p["track"][0]["rect"])).save(work / f"{name}.png")
        images[name] = str(work / f"{name}.png")
    items = {}
    ctx = {"panels": [], "two_states": False, "first": None}
    for sl in tmpl["slots"]:
        pick = tmpl["exemplar"]["fills"].get(sl["id"]) or {}
        if not pick.get("block"):
            continue
        slot = {**{k: v for k, v in sl.items() if k != "track"}, "rect": sl["track"][0]["rect"]}
        item = bank.resolve_one(slot, pick, {}, ctx)
        rd = board["states"][sl["track"][0]["state"]]["reading"]
        items[sl["id"]] = replica.fill(item, replica.lines_in(rd, slot["rect"], rd["size"][0] / REF))
    body = compile_spec(tmpl, items, images)
    errs = score(board, body, images, store)
    return tmpl, body, images, errs
