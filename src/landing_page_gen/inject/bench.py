"""lp-bench: score a run's generated media against the originals they replaced.

For every `dist/media/gen/<slot>.<png|mp4|webm>` that lp-inject wrote, pair it
with the original named in slots.json and measure both the same way the corpus
does (`corpus.measure`): ground colour, lightness and saturation from the
border ring, subject coverage and bounding box from the background mask, mean
picture saturation, the style family the rule table derives, and for
composites the number of picture panels (a proxy for the device). A clip is
measured on its first frame, plus its length and loop seam against the
original's (`corpus.motion`). Writes runs/<run>/benchmark.md: one row per
slot, means per section and page, and a flag list keyed to the review rubric
(resemblance, geometry, fit, duration, loop), so the report's "Against the
original" rests on numbers before anyone opens an original."""

import argparse
import json
import sys
import tempfile
from pathlib import Path

import numpy as np
import yaml
from PIL import Image

from ..compose import cli as compose_cli
from ..compose.families import FAMILIES
from ..corpus import attrs, measure, motion, sectionize, taxonomy
from ..corpus.similar import FrameGrabber

COVERAGE_DELTA = 0.25  # subject share of the picture; more than this and the crop or scale is off
LIGHT_DELTA = 0.3      # ground lightness; more than this and the ground convention changed
METRICS = ("coverage", "ground_l", "ground_sat", "pic_sat")
VIDEO_SUFFIXES = (".mp4", ".webm")
DURATION_BAND = (0.9, 1.1)  # generated / original length outside this is a [duration] flag
PICTURE_DARK = 0.12    # lightness below which a pixel is the card, a gutter or a #1c1c1e tile
PICTURE_LIGHT = 0.9    # lightness above which a low-spread pixel is white chrome or the page
PICTURE_MIN_AREA = 0.02  # share of the picture a region needs to count as a panel
PICTURE_MIN_SAT = 0.15   # mean saturation a region needs to count as a picture, not a chip

# A compose chrome kind is a rendering primitive; the corpus labels the same
# element under one of `attrs.CHROME_KINDS`. This maps each drawable kind to the
# corpus kind bench compares against; text-only chrome (manager strings drawn on
# a transparent fill) has no corpus kind and maps to nothing.
COMPOSE_KIND = {
    "tile": "tile", "swatch": "swatch", "icon": "tile", "label": "chip", "pill": "pill", "tool-pill": "pill",
    "brackets": "brackets", "crop-badge": "tile", "badge": "badge", "card": "mockup-card", "profile-card": "mockup-card",
    "list-panel": "option-list", "adjust-panel": "adjust-panel", "round-badge": "vs-badge",
    "text": None, "headline": None, "divider": None,
}


def drawn_kinds(spec_path):
    """The set of corpus chrome kinds a compose spec draws: the family/preset
    template chrome minus omitted ids plus list-form additions, each compose
    kind mapped through COMPOSE_KIND (text/headline/divider draw no corpus
    chrome). Reads the spec only — no panel images needed."""
    spec = yaml.safe_load(Path(spec_path).read_text()) or {}
    if spec.get("family") not in FAMILIES:
        return set()
    template = compose_cli.template(spec["family"], compose_cli._preset(spec))
    entries = compose_cli._chrome_entries(spec)
    omit = set(spec.get("omit") or [])
    fam_ids = {item["id"] for item in template["chrome"]}
    kinds = {entries.get(item["id"], {}).get("kind", item["kind"])
             for item in template["chrome"] if item["id"] not in omit}
    kinds |= {e["kind"] for eid, e in entries.items() if eid not in fam_ids and "kind" in e}
    return {COMPOSE_KIND.get(k) for k in kinds} - {None}


def pictures(path):
    """How many picture panels a card shows: connected regions of the 256 px
    copy that are neither the near-black card, gutters and tiles nor near-white
    chrome, large enough to be a panel and coloured enough to be a picture.
    Thumbnails and second panels count; tiles, chips and list cards do not.
    A proxy for the device, tuned on runs/live-3; never a gate."""
    a, _ = measure.pixels(path)
    lum = a @ measure.LUMA
    spread = a.max(axis=2) - a.min(axis=2)
    mask = ~((lum < PICTURE_DARK) | ((lum > PICTURE_LIGHT) & (spread < 0.1)))
    sat = spread / np.maximum(a.max(axis=2), 1e-6)
    h, w = mask.shape
    seen = np.zeros_like(mask)
    count = 0
    for sy, sx in zip(*np.nonzero(mask)):
        if seen[sy, sx]:
            continue
        seen[sy, sx] = True
        stack, region = [(sy, sx)], []
        while stack:
            y, x = stack.pop()
            region.append((y, x))
            for ny, nx in ((y - 1, x), (y + 1, x), (y, x - 1), (y, x + 1)):
                if 0 <= ny < h and 0 <= nx < w and mask[ny, nx] and not seen[ny, nx]:
                    seen[ny, nx] = True
                    stack.append((ny, nx))
        if len(region) >= PICTURE_MIN_AREA * h * w:
            ys, xs = zip(*region)
            if float(sat[list(ys), list(xs)].mean()) >= PICTURE_MIN_SAT:
                count += 1
    return count


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
            "pic_sat": round(pic_sat, 2), "pictures": pictures(path)}


def video_stats(path, grabber, tmp):
    """(duration, first frame path, motion fields) of a clip, its five sample
    frames grabbed into `tmp`."""
    duration, frames = motion.probe(path, grabber, tmp, Path(path).stem)
    return duration, frames[0], motion.measure(frames)


def family(fields, typ, aspect_class):
    return taxonomy.style_label(*taxonomy.family_of({**fields, "type": typ, "aspect_class": aspect_class})) or "unresolved"


def flags(row):
    o, g, out = row["orig"], row["gen"], []
    tag = f"{row['slot']} ({row['type']})"
    if row.get("video"):
        v = row["video"]
        if v["orig_s"] and v["gen_s"] and not DURATION_BAND[0] <= v["gen_s"] / v["orig_s"] <= DURATION_BAND[1]:
            out.append(f"{tag}: duration {v['orig_s']:.1f} s -> {v['gen_s']:.1f} s [duration]")
        if v["orig_loop"] and not v["gen_loop"]:
            out.append(f"{tag}: loop seam {v['orig_seam']:.2f} -> {v['gen_seam']:.2f}, the original loops and this does not [loop]")
    if row["orig_family"] != row["gen_family"]:
        out.append(f"{tag}: family {row['orig_family']} -> {row['gen_family']} [resemblance]")
    if abs(g["coverage"] - o["coverage"]) > COVERAGE_DELTA:
        out.append(f"{tag}: subject coverage {o['coverage']:.2f} -> {g['coverage']:.2f} [geometry]")
    if abs(g["ground_l"] - o["ground_l"]) > LIGHT_DELTA:
        out.append(f"{tag}: ground lightness {o['ground_l']:.2f} -> {g['ground_l']:.2f} [resemblance]")
    if o["ground_sat"] > measure.SAT and g["ground_sat"] < measure.SAT:
        out.append(f"{tag}: ground saturation {o['ground_sat']:.2f} -> {g['ground_sat']:.2f}, below SAT {measure.SAT} [resemblance]")
    if row.get("composition"):
        c = row["composition"]
        if c["missing"]:
            out.append(f"{tag}: chrome {'+'.join(c['orig'])} -> {'+'.join(c['gen']) or 'none'}, "
                       f"missing {'+'.join(c['missing'])} [composition]")
    elif row.get("composite") and o["pictures"] >= 2 and g["pictures"] < o["pictures"]:
        out.append(f"{tag}: pictures {o['pictures']} -> {g['pictures']}, the original's device has more panels [fit]")
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
    files = sorted(p for p in (run / "dist" / "media" / "gen").iterdir() if p.suffix in (".png",) + VIDEO_SUFFIXES)
    with FrameGrabber() as grabber, tempfile.TemporaryDirectory() as tmp:
        for gen in files:
            slot = gen.stem
            if slot.endswith(("-placeholder", "-poster")) or slot not in meta["slots"]:
                continue
            s = meta["slots"][slot]
            typ = meta["sections"][slot.split("-")[0]]["type"]
            cls = sectionize.aspect_class(*(s.get("size") or (None, None)))
            orig = Path(s["local"]) if s.get("local") else None
            if orig is None or not orig.exists() or orig.suffix == ".svg":
                skipped.append(f"{slot}: original {'is svg' if orig and orig.suffix == '.svg' else 'missing'}")
                continue
            video = None
            if gen.suffix in VIDEO_SUFFIXES or orig.suffix in VIDEO_SUFFIXES:
                # a clip is scored on its first frame, plus length and seam against the original's
                o_s, o_first, o_m = video_stats(orig, grabber, Path(tmp) / "orig") if orig.suffix in VIDEO_SUFFIXES else (None, orig, {})
                g_s, g_first, g_m = video_stats(gen, grabber, Path(tmp) / "gen") if gen.suffix in VIDEO_SUFFIXES else (None, gen, {})
                video = {"orig_s": o_s, "gen_s": g_s, "orig_loop": o_m.get("loop"), "gen_loop": g_m.get("loop"),
                         "orig_seam": o_m.get("loop_seam", 0.0), "gen_seam": g_m.get("loop_seam", 0.0),
                         "orig_pace": o_m.get("pace"), "gen_pace": g_m.get("pace")}
                orig, gen = o_first, g_first
            o, g = stats(orig), stats(gen)
            rec = known.get(s.get("src")) or s.get("attrs")  # the corpus record may carry sheet answers the pixels cannot
            sec = slot.split("-")[0]
            spec_path = run / "sections" / sec / f"compose-{slot}.yaml"
            row = {"slot": slot, "section": sec, "type": typ, "orig": o, "gen": g, "video": video,
                   "composite": spec_path.exists(),
                   "orig_family": family(rec or o, typ, cls), "gen_family": family(g, typ, cls)}
            if row["composite"] and rec and "chrome_items" in (rec.get("labelled") or []):
                # ground truth of what the modal drew (labelled corpus items) vs
                # what the spec draws; kinds only in this batch (placement/count
                # /state/text follow), so the pixel `pictures` proxy stands down
                orig_kinds = {it["kind"] for it in (rec.get("chrome_items") or [])}
                gen_kinds = drawn_kinds(spec_path)
                row["composition"] = {"orig": sorted(orig_kinds), "gen": sorted(gen_kinds),
                                      "missing": sorted(orig_kinds - gen_kinds), "extra": sorted(gen_kinds - orig_kinds)}
            rows.append(row)
    return {"rows": rows, "means": means(rows), "flags": [f for r in rows for f in flags(r)], "skipped": skipped}


def write_md(result, path):
    pair = lambda r, k: f"{r['orig'][k]:.2f} / {r['gen'][k]:.2f}"  # noqa: E731
    lines = ["# Benchmark: generated vs original", "",
             f"Measured on {measure.MEASURE_PX} px copies. Ground = border-ring median colour (on a picture that fills "
             "the frame this is the border's colour, not a judgement of the whole); coverage = share of pixels farther "
             f"than BG_TOL from that ground; L = ground lightness; sat = ground channel spread (SAT {measure.SAT}); "
             "pic sat = mean HSV saturation; pictures = coloured regions large enough to be a panel (a device "
             "proxy, flagged on composites only); chrome = the corpus kinds the original's labelled composition "
             "carried vs the kinds the compose spec draws (dash when the original has no labelled chrome_items, "
             "where the pictures proxy stands in). Values are original / generated.", "",
             "| slot | section | family orig -> gen | match | ground L | ground sat | coverage | bbox h | pic sat | pictures | chrome orig -> gen |",
             "|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in result["rows"]:
        c = r.get("composition")
        chrome = f"{'+'.join(c['orig']) or 'none'} -> {'+'.join(c['gen']) or 'none'}" if c else "—"
        lines.append(f"| {r['slot']} | {r['section']} {r['type']} | {r['orig_family']} -> {r['gen_family']} | "
                     f"{'yes' if r['orig_family'] == r['gen_family'] else 'no'} | {pair(r, 'ground_l')} | {pair(r, 'ground_sat')} | "
                     f"{pair(r, 'coverage')} | {pair(r, 'bbox_h')} | {pair(r, 'pic_sat')} | "
                     f"{r['orig']['pictures']} / {r['gen']['pictures']} | {chrome} |")
    lines += ["", "## Means (generated minus original)", "",
              "| group | n | family match | d coverage | d ground L | d ground sat | d pic sat |", "|---|---|---|---|---|---|---|"]
    for key, m in result["means"].items():
        lines.append(f"| {key} | {m['n']} | {m['family_match']:.2f} | {m['d_coverage']:+.2f} | {m['d_ground_l']:+.2f} | "
                     f"{m['d_ground_sat']:+.2f} | {m['d_pic_sat']:+.2f} |")
    videos = [r for r in result["rows"] if r.get("video")]
    if videos:
        fmt = lambda x, spec: (format(x, spec) if isinstance(x, (int, float)) else "?")  # noqa: E731
        lines += ["", "## Video (first frame scored above; length and seam here)", "",
                  "| slot | duration orig / gen | ratio | loop seam orig / gen | pace orig / gen |", "|---|---|---|---|---|"]
        for r in videos:
            v = r["video"]
            ratio = v["gen_s"] / v["orig_s"] if v["orig_s"] and v["gen_s"] else None
            lines.append(f"| {r['slot']} | {fmt(v['orig_s'], '.1f')} s / {fmt(v['gen_s'], '.1f')} s | {fmt(ratio, '.2f')} | "
                         f"{fmt(v['orig_seam'], '.2f')} / {fmt(v['gen_seam'], '.2f')} | {v['orig_pace'] or '?'} / {v['gen_pace'] or '?'} |")
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
