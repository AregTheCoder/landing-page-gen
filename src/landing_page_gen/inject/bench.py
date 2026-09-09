"""lp-bench: score a run's generated media against the originals they replaced.

For every `dist/media/gen/<slot>.png` that lp-inject wrote, pair it with the
original named in slots.json and measure both the same way the corpus does
(`corpus.measure`): ground colour, lightness and saturation from the border
ring, subject coverage and bounding box from the background mask, mean
picture saturation, and the style family the rule table derives. Writes
runs/<run>/benchmark.md: one row per slot, means per section and page, and a
flag list keyed to the review rubric (resemblance, geometry), so the report's
"Against the original" rests on numbers before anyone opens an original."""

import argparse
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image

from ..corpus import attrs, measure, sectionize, taxonomy

COVERAGE_DELTA = 0.25  # subject share of the picture; more than this and the crop or scale is off
LIGHT_DELTA = 0.3      # ground lightness; more than this and the ground convention changed
METRICS = ("coverage", "ground_l", "ground_sat", "pic_sat")


def stats(path):
    """Ground, subject and saturation statistics of one image, on the same
    256 px copy `measure` uses."""
    a, _ = measure.pixels(path)
    fields = measure.measure(path)
    bg = measure.flat_colour(a)
    if bg is None:
        bg = np.median(measure.ring(a), axis=0)
    fg = ~(np.abs(a - bg).max(axis=2) < measure.BG_TOL)
    ys, xs = np.nonzero(fg)
    h, w = fg.shape
    with Image.open(path) as im:
        im = im.convert("RGB")
        im.thumbnail((measure.MEASURE_PX, measure.MEASURE_PX))
        pic_sat = float(np.asarray(im.convert("HSV"))[..., 1].mean() / 255)
    return {**{k: fields.get(k) for k in measure.FIELDS},
            "ground_l": round(float(bg @ measure.LUMA), 2), "ground_sat": round(float(bg.max() - bg.min()), 2),
            "coverage": round(float(fg.mean()), 2),
            "bbox_h": round(float((ys.max() - ys.min() + 1) / h), 2) if len(ys) else 0.0,
            "bbox_w": round(float((xs.max() - xs.min() + 1) / w), 2) if len(xs) else 0.0,
            "pic_sat": round(pic_sat, 2)}


def family(fields, typ, aspect_class):
    return taxonomy.style_label(*taxonomy.family_of({**fields, "type": typ, "aspect_class": aspect_class})) or "unresolved"


def flags(row):
    o, g, out = row["orig"], row["gen"], []
    tag = f"{row['slot']} ({row['type']})"
    if row["orig_family"] != row["gen_family"]:
        out.append(f"{tag}: family {row['orig_family']} -> {row['gen_family']} [resemblance]")
    if abs(g["coverage"] - o["coverage"]) > COVERAGE_DELTA:
        out.append(f"{tag}: subject coverage {o['coverage']:.2f} -> {g['coverage']:.2f} [geometry]")
    if abs(g["ground_l"] - o["ground_l"]) > LIGHT_DELTA:
        out.append(f"{tag}: ground lightness {o['ground_l']:.2f} -> {g['ground_l']:.2f} [resemblance]")
    if o["ground_sat"] > measure.SAT and g["ground_sat"] < measure.SAT:
        out.append(f"{tag}: ground saturation {o['ground_sat']:.2f} -> {g['ground_sat']:.2f}, below SAT {measure.SAT} [resemblance]")
    return out


def means(rows):
    groups = {}
    for r in rows:
        groups.setdefault(r["section"], []).append(r)
    if rows:
        groups["page"] = list(rows)
    out = {}
    for key, rs in groups.items():
        out[key] = {"n": len(rs), "family_match": round(sum(r["orig_family"] == r["gen_family"] for r in rs) / len(rs), 2),
                    **{f"d_{m}": round(sum(r["gen"][m] - r["orig"][m] for r in rs) / len(rs), 2) for m in METRICS}}
    return out


def bench(run, attrs_path=attrs.ATTRIBUTES_YAML):
    run = Path(run)
    meta = json.loads((run / "slots.json").read_text())
    known = attrs.load(attrs_path) if Path(attrs_path).exists() else {}
    rows, skipped = [], []
    for gen in sorted((run / "dist" / "media" / "gen").glob("*.png")):
        slot = gen.stem
        if slot.endswith("-placeholder") or slot not in meta["slots"]:
            continue
        s = meta["slots"][slot]
        typ = meta["sections"][slot.split("-")[0]]["type"]
        cls = sectionize.aspect_class(*(s.get("size") or (None, None)))
        orig = Path(s["local"]) if s.get("local") else None
        if orig is None or not orig.exists() or orig.suffix == ".svg":
            skipped.append(f"{slot}: original {'is svg' if orig and orig.suffix == '.svg' else 'missing'}")
            continue
        o, g = stats(orig), stats(gen)
        rec = known.get(s.get("src")) or s.get("attrs")  # the corpus record may carry sheet answers the pixels cannot
        rows.append({"slot": slot, "section": slot.split("-")[0], "type": typ, "orig": o, "gen": g,
                     "orig_family": family(rec or o, typ, cls), "gen_family": family(g, typ, cls)})
    return {"rows": rows, "means": means(rows), "flags": [f for r in rows for f in flags(r)], "skipped": skipped}


def write_md(result, path):
    pair = lambda r, k: f"{r['orig'][k]:.2f} / {r['gen'][k]:.2f}"  # noqa: E731
    lines = ["# Benchmark: generated vs original", "",
             f"Measured on {measure.MEASURE_PX} px copies. Ground = border-ring median colour (on a picture that fills "
             "the frame this is the border's colour, not a judgement of the whole); coverage = share of pixels farther "
             f"than BG_TOL from that ground; L = ground lightness; sat = ground channel spread (SAT {measure.SAT}); "
             "pic sat = mean HSV saturation. Values are original / generated.", "",
             "| slot | section | family orig -> gen | match | ground L | ground sat | coverage | bbox h | pic sat |",
             "|---|---|---|---|---|---|---|---|---|"]
    for r in result["rows"]:
        lines.append(f"| {r['slot']} | {r['section']} {r['type']} | {r['orig_family']} -> {r['gen_family']} | "
                     f"{'yes' if r['orig_family'] == r['gen_family'] else 'no'} | {pair(r, 'ground_l')} | {pair(r, 'ground_sat')} | "
                     f"{pair(r, 'coverage')} | {pair(r, 'bbox_h')} | {pair(r, 'pic_sat')} |")
    lines += ["", "## Means (generated minus original)", "",
              "| group | n | family match | d coverage | d ground L | d ground sat | d pic sat |", "|---|---|---|---|---|---|---|"]
    for key, m in result["means"].items():
        lines.append(f"| {key} | {m['n']} | {m['family_match']:.2f} | {m['d_coverage']:+.2f} | {m['d_ground_l']:+.2f} | "
                     f"{m['d_ground_sat']:+.2f} | {m['d_pic_sat']:+.2f} |")
    lines += ["", "## Flags", ""] + ([f"- {f}" for f in result["flags"]] or ["- none"])
    if result["skipped"]:
        lines += ["", "## Skipped", ""] + [f"- {s}" for s in result["skipped"]]
    path.write_text("\n".join(lines) + "\n")


def main(argv=None):
    ap = argparse.ArgumentParser(prog="lp-bench", description="Score a run's generated media against the originals.")
    ap.add_argument("run", help="run folder with slots.json and dist/media/gen/")
    ap.add_argument("--attrs", default=str(attrs.ATTRIBUTES_YAML), help="corpus attributes.yaml for the originals' labels")
    a = ap.parse_args(argv)
    result = bench(a.run, Path(a.attrs))
    out = Path(a.run) / "benchmark.md"
    write_md(result, out)
    print(f"{out}: {len(result['rows'])} slots, {len(result['flags'])} flags, {len(result['skipped'])} skipped")
    return 0


if __name__ == "__main__":
    sys.exit(main())
