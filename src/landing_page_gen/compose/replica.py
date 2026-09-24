"""Replicas: each template drawn from its own original, then read beside it.

A template is understood when it can redraw the picture it was measured from.
The replica keeps the original's own pixels in the template's panels and the
original's own words in its blocks (the reading's OCR lines that fall in each
block's box), so every difference left is ours: the background, a card's
fill or radius, a block's type size, weight or position, an icon we do not
draw. Both pictures are read the same way (`corpus/readings`: OCR + layout)
and compared region by region and line by line.

    uv run lp-compose --replica [FAMILY[/LAYOUT]] --out research/replicas

The report ranks the layouts by how far their replica is from the original;
it is the work list for making the templates faithful."""

import json
import re
from pathlib import Path

import numpy as np
import yaml
from PIL import Image, ImageChops

from . import cli, plan
from .families import FAMILIES, REF

TEXT_KINDS = ("pill", "label", "statement", "text", "prompt-text", "tool-pill", "round-badge", "headline", "button")
PICK_KEYS = {"brackets": "label", "adjust-panel": "title"}


# ---------------------------------------------------------------- the original

def source_asset(tmpl):
    """The exemplar's corpus asset id (8 hex), or None for an unmeasured source."""
    src = str((tmpl.get("exemplar") or {}).get("source") or "")
    m = re.match(r"([0-9a-f]{8})\b", src)
    return m.group(1) if m else None


def reading_of(aid):
    from ..corpus import readings
    return readings.load(aid)


def lines_in(reading, rect, scale):
    """The OCR lines whose centre falls in a REF rect (scale: original px per REF)."""
    x0, y0, x1, y1 = (v * scale for v in rect)
    out = []
    for ln in reading["texts"]:
        bx0, by0, bx1, by1 = ln["box"]
        cx, cy = (bx0 + bx1) / 2, (by0 + by1) / 2
        if x0 <= cx <= x1 and y0 <= cy <= y1:
            out.append(ln)
    return sorted(out, key=lambda ln: (ln["box"][1], ln["box"][0]))


def rows_of(lines):
    """Lines grouped into rows: a line starting within one line height below the
    last one's bottom, and overlapping it across, continues its row (a wrap)."""
    rows = []
    for ln in lines:
        x0, y0, x1, y1 = ln["box"]
        if rows:
            px0, py0, px1, py1 = rows[-1]["box"]
            h = py1 - py0
            if 0 <= y0 - py1 <= 0.6 * h and x0 < px1 and px0 < x1 + h:
                rows[-1]["text"] += " " + ln["text"]
                rows[-1]["box"] = [min(px0, x0), py0, max(px1, x1), y1]
                continue
        rows.append({"text": ln["text"], "box": list(ln["box"])})
    return rows


def _unlogo(text):
    """A list row read with its logo as a letter ('G Google Ads', 'f Facebook Ads')."""
    parts = text.split(" ", 1)
    return parts[1] if len(parts) == 2 and len(parts[0]) == 1 and parts[1][:1].isupper() else text


def fill(item, lines):
    """The item with its strings taken from the original's lines in its box."""
    if not lines:
        return item
    it, k = dict(item), item.get("kind")
    texts = [ln["text"] for ln in lines]
    if k in TEXT_KINDS:
        it["text"] = " ".join(texts)
    elif k in PICK_KEYS:
        it[PICK_KEYS[k]] = texts[0]
    elif k == "list-card":
        it["rows"] = [_unlogo(r["text"]) for r in rows_of(lines) if len(r["text"].strip()) > 1]  # a logo read as a letter
    elif k == "track-list":  # each row a title and the line under it
        ls = sorted(lines, key=lambda ln: ln["box"][1])
        n = max(1, len(it.get("rows") or []))
        y0, y1 = min(ln["box"][1] for ln in ls), max(ln["box"][3] for ln in ls)
        band = (y1 - y0) / n
        rows = [[] for _ in range(n)]
        for ln in ls:
            rows[min(n - 1, int((ln["box"][1] - y0) / max(1, band)))].append(ln["text"])
        it["rows"] = [r[:2] for r in rows if r]
    elif k == "list-panel":
        names = [_unlogo(r["text"]) for r in rows_of(lines)]
        it["active_text"], it["rows_text"], it["rows"] = names[0], names[1:], len(names)
    elif k == "form-card":
        xs = [(ln["box"][0] + ln["box"][2]) / 2 for ln in lines]
        mid = (min(ln["box"][0] for ln in lines) + max(ln["box"][2] for ln in lines)) / 2
        left = [ln["text"] for ln, x in zip(lines, xs) if x < mid]
        right = [ln["text"] for ln, x in zip(lines, xs) if x >= mid]
        if len(left) >= 2:
            it["fields"] = [left[i:i + 2] for i in range(0, len(left) - 1, 2)]
        if len(right) >= 2:
            it["result"] = right[:2]
    elif k == "chip-bar":
        texts = [ln["text"] for ln in sorted(lines, key=lambda ln: ln["box"][0])]
        items = [dict(x) if isinstance(x, dict) else {"text": str(x)} for x in it.get("items") or []]
        slots = [x for x in items if not x.get("mark")] or items
        for x, t in zip(slots, texts):
            x["text"] = t
        it["items"] = items
    return it


# ---------------------------------------------------------------- the replica

def _size(tmpl, reading):
    """The original's size when it has the template's aspect, else REF across."""
    w, h = reading["size"]
    if cli.fits(tmpl, w, h):
        return w, h
    fw, fh = (tmpl.get("aspects") or (tmpl["aspect"],))[0]
    return REF, round(REF * fh / fw)


def build(fam, variant, reading, work):
    """(spec path, size): the replica spec, the original cropped into each panel."""
    tmpl = cli.template(fam, variant)
    w, h = _size(tmpl, reading)
    work = Path(work)
    (work / "steps").mkdir(parents=True, exist_ok=True)
    orig = flat(reading["local"], (w, h))
    s = w / REF
    panels = {}
    for name, p in tmpl["panels"].items():
        if p.get("detail_of"):
            continue
        r = p.get("rect") or (0, 0, REF, round(REF * h / w))
        crop = orig.crop(tuple(round(v * s) for v in r))
        crop.save(work / "steps" / f"{name}.png")
        panels[name] = {"image": f"steps/{name}.png"}
    items = plan.exemplar_items(fam, variant)
    spec = {"slot": "replica", "family": fam, "size": f"{w}x{h}", "panels": panels, "chrome": items}
    if variant:
        spec["variant"] = variant
    path = work / "replica.yaml"
    path.write_text(yaml.safe_dump(spec, allow_unicode=True))
    # the boxes the blocks resolve to, back in REF, pick the original's words for each
    lay = cli.resolve(cli.load_spec(path))
    k = w / REF * cli.SS
    oscale = reading["size"][0] / REF
    placed = {}
    for x in lay["chrome"]:
        placed.setdefault(x.get("id"), x.get("rect"))
    filled = []
    for it in items:
        rect = [v / k for v in placed[it["id"]]] if placed.get(it.get("id")) else None
        filled.append(fill(it, lines_in(reading, rect, oscale)) if rect else it)
    spec["chrome"] = filled
    path.write_text(yaml.safe_dump(spec, allow_unicode=True))
    return path, (w, h)


def render(spec_path, out, ground=None):
    """The replica on the ground the original is seen on: its own colour, or
    white for a see-through file (the page's background, as the reading sees it)."""
    spec = cli.load_spec(spec_path)
    img, _ = cli.compose(cli.resolve(spec))
    under = tuple(ground) if isinstance(ground, (list, tuple)) else (255, 255, 255)
    flat = Image.new("RGBA", img.size, under + (255,))
    flat.alpha_composite(img.convert("RGBA"))
    flat.convert("RGB").save(out)
    return out


# ---------------------------------------------------------------- the comparison

def _iou(a, b):
    ix = max(0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = ix * iy
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / union if union else 0.0


def compare(orig, rep, tmpl):
    """Findings between two readings (both in REF units): regions matched by
    overlap, lines by text; what the original has that the replica lacks."""
    from . import verify
    f = []
    used = set()
    for r in orig["regions"]:
        best = max(((i, _iou(r["ref"], q["ref"])) for i, q in enumerate(rep["regions"]) if i not in used),
                   key=lambda x: x[1], default=(None, 0))
        if best[1] < 0.5:
            f.append({"what": "region", "severity": 3, "note": f"{r['kind']} at {r['ref']} has no counterpart"})
            continue
        used.add(best[0])
        q = rep["regions"][best[0]]
        if best[1] < 0.92:
            f.append({"what": "region", "severity": 2, "note": f"{r['kind']} at {r['ref']} drawn at {q['ref']} (IoU {best[1]:.2f})"})
        if r["kind"] != q["kind"]:
            f.append({"what": "region", "severity": 2, "note": f"{r['kind']} at {r['ref']} reads as a {q['kind']}"})
        if r.get("fill") and q.get("fill") and max(abs(a - b) for a, b in zip(r["fill"], q["fill"])) > 12:
            f.append({"what": "fill", "severity": 1, "note": f"card at {r['ref']}: fill {r['fill']} drawn {q['fill']}"})
        ro, qo = r.get("radius", 0) * REF / orig["size"][0], q.get("radius", 0) * REF / rep["size"][0]
        if abs(ro - qo) > max(6, 0.25 * ro):
            f.append({"what": "radius", "severity": 1, "note": f"{r['kind']} at {r['ref']}: radius {ro:.0f} drawn {qo:.0f} (REF)"})
        icons = [c for c in r.get("children") or [] if c["kind"] == "icon"]
        qicons = [c for c in q.get("children") or [] if c["kind"] == "icon"]
        if len(icons) > len(qicons):
            f.append({"what": "icon", "severity": 2,
                      "note": f"{r['kind']} at {r['ref']}: {len(icons)} icon(s) in the original, {len(qicons)} drawn"})
    for ln in orig["texts"]:
        cands = [q for q in rep["texts"] if verify.found(ln["text"], q["text"]) or verify.found(q["text"], ln["text"])]
        if not cands:
            continue
        q = min(cands, key=lambda q: abs(q["ref"][1] - ln["ref"][1]) + abs(q["ref"][0] - ln["ref"][0]))
        oh, qh = ln["ref"][3] - ln["ref"][1], q["ref"][3] - q["ref"][1]
        dx, dy = q["ref"][0] - ln["ref"][0], q["ref"][1] - ln["ref"][1]
        if oh and abs(qh / oh - 1) > 0.12:
            f.append({"what": "type-size", "severity": 2, "note": f"{ln['text']!r}: {oh} tall drawn {qh} (x{qh / oh:.2f})"})
        if abs(dx) > 16 or abs(dy) > 16:
            f.append({"what": "type-place", "severity": 1, "note": f"{ln['text']!r}: moved {dx:+d},{dy:+d} (REF)"})
        oc, qc = ln.get("colour"), q.get("colour")
        if oc and qc and max(abs(a - b) for a, b in zip(oc, qc)) > 40:
            f.append({"what": "type-colour", "severity": 1, "note": f"{ln['text']!r}: colour {oc} drawn {qc}"})
    return f


def flat(path, size=None):
    """A picture as seen on the page: see-through pixels over white."""
    with Image.open(path) as im:
        im = im.convert("RGBA")
        if size:
            im = im.resize(size, Image.LANCZOS)
        base = Image.new("RGBA", im.size, (255, 255, 255, 255))
        base.alpha_composite(im)
        return base.convert("RGB")


def chrome_error(orig_png, rep_png, tmpl, size):
    """Mean absolute difference (0..1) outside the panels: what the template draws."""
    w, h = size
    a = np.asarray(flat(orig_png, (w, h)), np.float32) / 255
    b = np.asarray(flat(rep_png, (w, h)), np.float32) / 255
    mask = np.ones((h, w), bool)
    s = w / REF
    for p in tmpl["panels"].values():
        if p.get("rect"):
            x0, y0, x1, y1 = (round(v * s) for v in p["rect"])
            mask[y0:y1, x0:x1] = False
    if not mask.any():
        return 0.0
    return float(np.abs(a - b).max(axis=-1)[mask].mean())


def sheet(orig_png, rep_png, out, width=560):
    a = flat(orig_png)
    b = flat(rep_png, a.size)
    diff = ImageChops.difference(a, b).convert("L").point(lambda v: min(255, v * 3))
    tiles = [x.resize((width, round(width * a.size[1] / a.size[0]))) for x in (a, b, diff.convert("RGB"))]
    im = Image.new("RGB", (width * 3 + 20, tiles[0].size[1]), (255, 255, 255))
    for i, t in enumerate(tiles):
        im.paste(t, (i * (width + 10), 0))
    im.save(out)
    return out


def layouts(which=None):
    """(family, variant, name) of every layout, of one family or layout (a
    string), or of exactly the names listed (the probe set)."""
    for fam in sorted(FAMILIES):
        for v in [None, *(FAMILIES[fam].get("variants") or {})]:
            name = f"{fam}/{v}" if v else fam
            if isinstance(which, str) and which and which not in (fam, name):
                continue
            if isinstance(which, (list, tuple, set)) and name not in which:
                continue
            yield fam, v, name


def run(out_dir, which=None):
    """Replicate every layout with a measured source; write the sheets and report."""
    from ..corpus import layout as corpus_layout, ocr
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    results = []
    for fam, v, name in layouts(which):
        tmpl = cli.template(fam, v)
        aid = source_asset(tmpl)
        reading = reading_of(aid) if aid else None
        if not reading:
            results.append({"layout": name, "skipped": f"no reading for source {(tmpl.get('exemplar') or {}).get('source')!r}"})
            continue
        work = out_dir / name.replace("/", "__")
        try:
            spec_path, size = build(fam, v, reading, work)
            rep_png = render(spec_path, work / "replica.png", reading["ground"])
        except (Exception, SystemExit) as e:  # a layout that cannot be drawn is a finding, not the end of the pass
            results.append({"layout": name, "source": aid, "chrome_error": 1.0, "severity": 99,
                            "findings": [{"what": "draw", "severity": 99, "note": f"cannot draw: {str(e)[:200]}"}],
                            "sheet": ""})
            continue
        try:
            rr = ocr.read([rep_png])[str(rep_png)]
            rep = corpus_layout.read(rep_png, rr)
            # both readings in REF units of their own size
            for rd in (reading, rep):
                f = REF / rd["size"][0]
                for r in rd["regions"]:
                    r["ref"] = [round(x * f) for x in r["box"]]
                for t in rd["texts"]:
                    t["ref"] = [round(x * f) for x in t["box"]]
            findings = compare(reading, rep, tmpl)
            err = chrome_error(reading["local"], rep_png, tmpl, size)
            sheet(reading["local"], rep_png, work / "sheet.png")
        except Exception as e:
            results.append({"layout": name, "source": aid, "chrome_error": 1.0, "severity": 99,
                            "findings": [{"what": "read", "severity": 99, "note": f"cannot compare: {str(e)[:200]}"}],
                            "sheet": ""})
            continue
        results.append({"layout": name, "source": aid, "chrome_error": round(err, 4),
                        "severity": sum(x["severity"] for x in findings), "findings": findings,
                        "sheet": str((work / "sheet.png").relative_to(out_dir))})
    (out_dir / "replicas.json").write_text(json.dumps(results, indent=1))
    return results


PROBE = Path(__file__).parent / "assets" / "probe.yaml"
WORSE = 0.01  # a chrome error this much above the last probe's is a regression


def probe(out_dir):
    """Redraw the probe set (assets/probe.yaml) and set it against the last
    probe in `out_dir`: the lines to print (regressions first) and one contact
    sheet (probe.png), so every template or reader change is looked at."""
    import yaml
    out_dir = Path(out_dir)
    last = out_dir / "probe.json"
    before = {r["layout"]: r for r in json.loads(last.read_text())} if last.exists() else {}
    names = yaml.safe_load(PROBE.read_text())
    results = [r for r in run(out_dir, names) if "skipped" not in r]
    lines = []
    for r in results:
        b = before.get(r["layout"])
        if b and (r["chrome_error"] > b["chrome_error"] + WORSE or r["severity"] > b["severity"]):
            lines.append(f"WORSE {r['layout']}: chrome {b['chrome_error']} -> {r['chrome_error']}, "
                         f"severity {b['severity']} -> {r['severity']}")
    for r in results:
        b = before.get(r["layout"])
        if b and r["chrome_error"] < b["chrome_error"] - WORSE:
            lines.append(f"better {r['layout']}: chrome {b['chrome_error']} -> {r['chrome_error']}")
    if last.exists():
        last.replace(out_dir / "probe-prev.json")
    last.write_text(json.dumps(results, indent=1))
    sheets = [Image.open(out_dir / r["sheet"]).convert("RGB") for r in results if r.get("sheet")]
    if sheets:
        w = max(s.width for s in sheets)
        rows = [s.resize((w // 2, round(s.height * w / 2 / s.width))) for s in sheets]
        im = Image.new("RGB", (w, sum(r.height for r in rows[::2]) + 8 * len(rows)), (255, 255, 255))
        y = 0
        for i in range(0, len(rows), 2):
            for j, r in enumerate(rows[i:i + 2]):
                im.paste(r, (j * (w // 2), y))
            y += max(r.height for r in rows[i:i + 2]) + 8
        im.save(out_dir / "probe.png")
    errs = sorted(r["chrome_error"] for r in results)
    lines.append(f"probe: {len(results)} of {len(names)} layouts, median chrome error "
                 f"{errs[len(errs) // 2] if errs else 'n/a'}, {sum(r['severity'] >= 99 for r in results)} cannot draw"
                 f"{'' if before else ' (first probe: the baseline)'} -> {out_dir / 'probe.png'}")
    return lines


def report(results):
    done = sorted((r for r in results if "skipped" not in r), key=lambda r: -(r["severity"] + 100 * r["chrome_error"]))
    lines = ["# Template replicas", "",
             "Each layout redrawn from its own original (its pixels in the panels, its words in the blocks) and read "
             "beside it. `chrome error` is the mean difference outside the panels (0 = identical); findings are what "
             "the reading of the original has that the replica does not match.", "",
             "| layout | source | chrome error | severity | findings |", "|---|---|---|---|---|"]
    for r in done:
        lines.append(f"| {r['layout']} | {r['source']} | {r['chrome_error']:.3f} | {r['severity']} | {len(r['findings'])} |")
    for r in done:
        lines += ["", f"## {r['layout']} ({r['source']})", "", f"![sheet]({r['sheet']})", ""]
        lines += [f"- [{x['what']}] {x['note']}" for x in sorted(r["findings"], key=lambda x: -x["severity"])] or ["- no findings"]
    skipped = [r for r in results if "skipped" in r]
    if skipped:
        lines += ["", "## Not replicated", ""] + [f"- {r['layout']}: {r['skipped']}" for r in skipped]
    return "\n".join(lines) + "\n"
