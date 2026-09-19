"""Motion measurements of one corpus video: what five sampled frames settle
with no model in the loop — how much the picture changes, how fast, whether
the clip returns to its first frame, whether the camera holds — plus the
3-frame strip a person or an agent reads instead of the clip.

Frames come from Chromium through `similar.FrameGrabber` (the machine has no
ffmpeg and the corpus is VP9 webm); the maths is numpy on 128 px grey copies.
`camera` is written only when it settles as `static`; every other camera move
and the `motion_kind` are labelled on the sheets, like chrome."""

from pathlib import Path

import numpy as np
from PIL import Image

FRAMES = 5
EDGE = 0.2           # seconds kept off both ends: a fade-in and the poster hold
MOTION_PX = 128
PACE = (("still", 0.01), ("slow", 0.04), ("medium", 0.10))  # upper bound per bucket; above the last is fast
LOOP_SIM = 0.90      # first-vs-last similarity that reads as a seamless loop
CUT = 0.25           # one frame-pair changing this much is a cut, not motion
STATIC_SHIFT = 1.0   # px of global translation (at MOTION_PX) under which the frame holds
STATIC_RING = 0.02   # mean change on the border ring under which the camera holds (a push-in moves the edges)
RING = 0.08
FIELDS = ("motion", "pace", "loop", "loop_seam", "camera")


def times(duration, n=FRAMES, edge=EDGE):
    """The instants to sample: `edge` in, then evenly to `edge` before the end.
    A clip shorter than two edges collapses onto its middle."""
    if not duration or duration <= 2 * edge:
        mid = (duration or 2 * edge) / 2
        return [round(mid, 2)] * n
    lo, hi = edge, duration - edge
    return [round(lo + (hi - lo) * i / (n - 1), 2) for i in range(n)]


def frame_paths(frames_dir, stem, n=FRAMES):
    return [Path(frames_dir) / f"{stem}-f{i}.png" for i in range(n)]


def probe(src, grabber, frames_dir, stem, duration=None):
    """(duration, frame paths): the clip's sampled frames, grabbed once and
    cached beside the poster frame. `duration` is the DB's when known, else
    what Chromium reads off the file."""
    paths = frame_paths(frames_dir, stem)
    if all(p.exists() for p in paths):
        return duration, paths
    Path(frames_dir).mkdir(parents=True, exist_ok=True)
    seen, _ = grabber.grab_many(src, lambda d: list(zip(times(duration or d), paths)))
    return duration or seen, paths


def grey(path, max_px=MOTION_PX):
    with Image.open(path) as im:
        im = im.convert("L")
        im.thumbnail((max_px, max_px))
        return np.asarray(im, dtype=np.float32) / 255.0


def shift(a, b):
    """Global translation between two frames in px, by phase correlation."""
    fa, fb = np.fft.fft2(a - a.mean()), np.fft.fft2(b - b.mean())
    r = fa * np.conj(fb)
    r = np.fft.ifft2(r / (np.abs(r) + 1e-9)).real
    y, x = np.unravel_index(int(np.argmax(r)), r.shape)
    h, w = r.shape
    dy = y - h if y > h / 2 else y
    dx = x - w if x > w / 2 else x
    return float(np.hypot(dy, dx))


def ring_change(a, b, frac=RING):
    h, w = a.shape
    k = max(1, int(round(min(h, w) * frac)))
    d = np.abs(a - b)
    return float(np.concatenate([d[:k].ravel(), d[-k:].ravel(), d[:, :k].ravel(), d[:, -k:].ravel()]).mean())


def pace_of(motion):
    for name, bound in PACE:
        if motion < bound:
            return name
    return "fast"


def measure(frames):
    """The measured motion fields from the sampled frames (paths or arrays)."""
    g = [f if isinstance(f, np.ndarray) else grey(f) for f in frames]
    if len(g) < 2:
        return {}
    pairs = list(zip(g, g[1:]))
    diffs = [float(np.abs(a - b).mean()) for a, b in pairs]
    motion = float(np.mean(diffs))
    seam = 1.0 - float(np.abs(g[0] - g[-1]).mean())
    out = {"motion": round(motion, 4), "pace": pace_of(motion),
           "loop": bool(seam >= LOOP_SIM), "loop_seam": round(seam, 3)}
    cut = max(diffs) >= CUT
    holds = all(shift(a, b) < STATIC_SHIFT and ring_change(a, b) < STATIC_RING for a, b in pairs)
    if not cut and holds:
        out["camera"] = "static"
    return out


def strip(frames, out, height=None, gap=4):
    """First, middle and last frame side by side: the clip's arc in one image."""
    picks = [frames[0], frames[len(frames) // 2], frames[-1]] if len(frames) >= 3 else list(frames)
    ims = [Image.open(p).convert("RGB") for p in picks]
    h = height or min(im.height for im in ims)
    ims = [im.resize((max(1, round(im.width * h / im.height)), h), Image.LANCZOS) for im in ims]
    sheet = Image.new("RGB", (sum(im.width for im in ims) + gap * (len(ims) - 1), h), "#222")
    x = 0
    for im in ims:
        sheet.paste(im, (x, 0))
        x += im.width + gap
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out)
    return out


def summary(mapping, min_n=5):
    """Per family, what its labelled videos do: {family: {n, motion_kind,
    camera, pace, loop_share, median_s}} over records with a family and the
    measured fields; modal values, `None` where fewer than min_n answered."""
    from collections import Counter
    from statistics import median
    from . import taxonomy
    by_fam = {}
    for rec in mapping.values():
        if rec.get("kind") != "video" or rec.get("pace") is None:
            continue
        fam = taxonomy.family_of(rec)[0]
        if fam:
            by_fam.setdefault(fam, []).append(rec)

    def mode(recs, key):
        c = Counter(r[key] for r in recs if r.get(key) is not None)
        return c.most_common(1)[0][0] if sum(c.values()) >= min_n else None

    out = {}
    for fam, recs in sorted(by_fam.items()):
        durs = [r["duration"] for r in recs if r.get("duration")]
        out[fam] = {"n": len(recs), "motion_kind": mode(recs, "motion_kind"), "camera": mode(recs, "camera"),
                    "pace": mode(recs, "pace"), "loop_share": round(sum(1 for r in recs if r.get("loop")) / len(recs), 2),
                    "median_s": round(median(durs), 1) if durs else None}
    return out


def motion_line(fam, s):
    """The family block's **Motion:** line from one `summary` entry."""
    parts = [f"{s['n']} corpus clips"]
    if s["motion_kind"]:
        parts.append(s["motion_kind"])
    if s["camera"]:
        parts.append(f"camera {s['camera']}")
    if s["pace"]:
        parts.append(f"pace {s['pace']}")
    parts.append(f"{round(s['loop_share'] * 100)} % loop")
    if s["median_s"]:
        parts.append(f"median {s['median_s']} s")
    return f"**Motion:** {'; '.join(parts)}."


def write_doc(summaries, doc_path, min_n=5):
    """Set each family block's **Motion:** line after its **References:** line
    (or at the block's end), replacing an earlier one; a family with fewer than
    min_n measured clips gets no line (one clip is an anecdote, not a
    convention). Returns families written."""
    import re
    doc = Path(doc_path)
    text = doc.read_text()
    written = []
    for fam, s in summaries.items():
        m = re.search(rf"^## {re.escape(fam)}\n(.*?)(?=^## |\Z)", text, re.M | re.S)
        if not m or s["n"] < min_n:
            continue
        block = re.sub(r"^\*\*Motion:\*\* .*\n", "", m.group(1), flags=re.M)
        line = motion_line(fam, s)
        if re.search(r"^\*\*References:\*\* .*\n", block, re.M):
            block = re.sub(r"(^\*\*References:\*\* .*\n)", lambda mm: mm.group(1) + line + "\n", block, count=1, flags=re.M)
        else:
            body = block.rstrip("\n")
            block = body + "\n" + line + block[len(body):]  # keep the block's own trailing blank lines
        text = text[:m.start(1)] + block + text[m.end(1):]
        written.append(fam)
    doc.write_text(text)
    return written
