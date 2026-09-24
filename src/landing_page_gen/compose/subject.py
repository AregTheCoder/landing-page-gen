"""Where a picture's subject is, so a cover crop keeps it: faces first, then
people, then the salient object (macOS Vision through `subject.swift`, compiled
on first use like the OCR helper). A centre crop cut two heads in random-2 that
the worker's own gate passed; `anchor: subject` crops around the subject, and
`cut()` names a face the crop still loses (a `verify:` fault)."""

import hashlib
import json
import subprocess
import sys
from functools import lru_cache
from pathlib import Path

SRC = Path(__file__).with_name("subject.swift")
BIN_DIR = Path.home() / ".cache" / "landing-page-gen"
HEAD = 0.25  # a face box grows this much of its height upward, for the hair and a hood
EYE_LINE = 0.38  # a face sits this far down its crop (a portrait's eyes near the upper third)


def binary():
    exe = BIN_DIR / f"lp-subject-{hashlib.sha1(SRC.read_bytes()).hexdigest()[:12]}"
    if not exe.exists():
        BIN_DIR.mkdir(parents=True, exist_ok=True)
        print(f"subject: compiling {SRC.name} (once, ~1 min)", file=sys.stderr)
        subprocess.run(["swiftc", "-O", str(SRC), "-o", str(exe)], check=True)
    return exe


@lru_cache(maxsize=256)
def locate(path):
    """{w, h, faces, people, salient} of one image file (pixels, origin top-left)."""
    proc = subprocess.run([str(binary())], input=str(path) + "\n", capture_output=True, text=True, check=True)
    return json.loads(proc.stdout.splitlines()[0])


def box(found):
    """The box a crop must keep: every face (grown for the head), else the
    people, else the salient object; None when Vision found nothing."""
    if found.get("faces"):
        bs = [[x0, y0 - HEAD * (y1 - y0), x1, y1] for x0, y0, x1, y1 in found["faces"]]
    elif found.get("people"):
        bs = found["people"]
    elif found.get("salient"):
        bs = [found["salient"]]
    else:
        return None
    return [min(b[0] for b in bs), max(0, min(b[1] for b in bs)), max(b[2] for b in bs), max(b[3] for b in bs)]


def anchor(size, frame, keep, y=0.5):
    """The cover-crop anchor (0..1, 0..1) that puts `keep`'s centre at the
    middle across and `y` down a `frame` (w, h) cut from an image of `size`,
    clamped to the image."""
    iw, ih = size
    w, h = frame
    s = max(w / iw, h / ih)
    cw, ch = w / s, h / s  # the crop's size in image pixels
    cx, cy = (keep[0] + keep[2]) / 2, (keep[1] + keep[3]) / 2
    ax = 0.5 if iw - cw < 1 else min(1, max(0, (cx - cw / 2) / (iw - cw)))
    ay = 0.5 if ih - ch < 1 else min(1, max(0, (cy - ch * y) / (ih - ch)))
    return ax, ay


def anchor_for(path, frame):
    """The anchor for a cover crop of the image at `path` into `frame`, and
    what Vision found; the centre when it found nothing."""
    found = locate(str(path))
    keep = box(found)
    if keep is None:
        return (0.5, 0.5), found
    return anchor((found["w"], found["h"]), frame, keep, EYE_LINE if found.get("faces") else 0.5), found


def crop_box(size, frame, at):
    """The part of the image (image pixels) a cover crop at anchor `at` keeps."""
    iw, ih = size
    w, h = frame
    s = max(w / iw, h / ih)
    cw, ch = w / s, h / s
    x, y = (iw - cw) * at[0], (ih - ch) * at[1]
    return [x, y, x + cw, y + ch]


def cut(found, crop, tol=0.02):
    """The faces (grown for the head) that the crop does not hold whole."""
    x0, y0, x1, y1 = crop
    t = tol * max(found["w"], found["h"])
    out = []
    for f in found.get("faces") or []:
        fx0, fy0, fx1, fy1 = f[0], f[1] - HEAD * (f[3] - f[1]), f[2], f[3]
        if fx0 < x0 - t or fy0 < y0 - t or fx1 > x1 + t or fy1 > y1 + t:
            out.append(f)
    return out
