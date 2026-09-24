"""A callout clip read as a storyboard: the states it holds still in, the
transitions between them, and what each state shows.

Picsart's product clips are compositions on a static camera: a UI state holds,
something changes (a cut, a crossfade, a wipe, a card sliding in, a prompt
typing), the next state holds. Sampling the clip densely (every STEP s, at a
small size, pixels read straight off a same-origin canvas in Chromium) and
differencing the frames finds the holds; a keyframe of each hold is grabbed at
full size and read like any corpus picture (OCR + layout). A region that never
stops changing (a clip playing inside the UI) is kept apart as the live region
so the states around it still resolve.

    uv run lp-corpus storyboard [--limit N] [--force] [--page SLUG]

One folder per clip in `corpus/storyboards/<id>/`: `storyboard.json`, the
keyframes `s<k>.png` and the dense samples `samples.npz` (uint8), which later
passes re-segment without decoding the clip. Rebuildable, so gitignored."""

import base64
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image

from . import attrs, layout, ocr
from .similar import _ranged_route

STORE = Path("corpus/storyboards")
STEP = 0.1          # seconds between samples
SMALL = 96          # px on the long side of a sample
NOISE = 0.06        # per-pixel change (0..1) under which a pixel holds (codec noise)
STILL = 0.004       # share of changed pixels under which a frame pair holds
MIN_HOLD = 3        # samples: a shorter hold is a pause inside a transition
LIVE = 0.5          # a pixel changing in this share of pairs belongs to a playing region

PAGE = "http://lp.local/index.html"
HTML = """<!doctype html><body style="margin:0;background:#000">
<video id="v" src="/v/clip" muted playsinline preload="auto"></video></body>"""

SAMPLE_JS = """async ({step, small}) => {
  const v = document.getElementById('v');
  if (v.readyState < 2) await new Promise((r, no) => { v.addEventListener('loadeddata', r, {once: true});
    v.addEventListener('error', () => no(new Error('the clip does not decode')), {once: true});
    setTimeout(() => no(new Error('the clip did not load in 30 s')), 30000); });
  const d = v.duration;
  const s = Math.min(1, small / Math.max(v.videoWidth, v.videoHeight));
  const c = document.createElement('canvas');
  c.width = Math.max(1, Math.round(v.videoWidth * s)); c.height = Math.max(1, Math.round(v.videoHeight * s));
  const g = c.getContext('2d', {willReadFrequently: true});
  const frames = [];
  for (let i = 0; i * step < d - 0.02; i++) {
    const t = i * step;
    if (Math.abs(v.currentTime - t) > 0.001) await new Promise(r => { v.addEventListener('seeked', r, {once: true}); v.currentTime = t; });
    g.drawImage(v, 0, 0, c.width, c.height);
    const px = g.getImageData(0, 0, c.width, c.height).data;
    const rgb = new Uint8Array(c.width * c.height * 3);
    for (let j = 0, k = 0; j < px.length; j += 4) { rgb[k++] = px[j]; rgb[k++] = px[j + 1]; rgb[k++] = px[j + 2]; }
    let bin = ''; for (let j = 0; j < rgb.length; j += 8192) bin += String.fromCharCode.apply(null, rgb.subarray(j, j + 8192));
    frames.push(btoa(bin));
  }
  return {duration: d, w: c.width, h: c.height, vw: v.videoWidth, vh: v.videoHeight, frames};
}"""

# The clip played once at PLAY_RATE, each frame grabbed as it is presented (requestVideoFrameCallback):
# every frame is decoded once, where a seek per sample decodes back from the last keyframe each time
# (2.6x faster at 2x on add-music-to-video S07, samples within 0.001 of the seeked ones).
PLAY_RATE = 2
PLAY_JS = """async ({step, small, rate}) => {
  const v = document.getElementById('v');
  if (v.readyState < 2) await new Promise((r, no) => { v.addEventListener('loadeddata', r, {once: true});
    v.addEventListener('error', () => no(new Error('the clip does not decode')), {once: true});
    setTimeout(() => no(new Error('the clip did not load in 30 s')), 30000); });
  const d = v.duration;
  const s = Math.min(1, small / Math.max(v.videoWidth, v.videoHeight));
  const c = document.createElement('canvas');
  c.width = Math.max(1, Math.round(v.videoWidth * s)); c.height = Math.max(1, Math.round(v.videoHeight * s));
  const g = c.getContext('2d', {willReadFrequently: true});
  const n = Math.max(1, Math.floor((d - 0.02) / step) + 1);
  const frames = new Array(n).fill(null);
  let next = 0;
  await new Promise((resolve) => {
    const grab = (now, meta) => {
      while (next < n && next * step <= meta.mediaTime + 0.5 / 30) {
        g.drawImage(v, 0, 0, c.width, c.height);
        const px = g.getImageData(0, 0, c.width, c.height).data;
        const rgb = new Uint8Array(c.width * c.height * 3);
        for (let j = 0, k = 0; j < px.length; j += 4) { rgb[k++] = px[j]; rgb[k++] = px[j + 1]; rgb[k++] = px[j + 2]; }
        let bin = ''; for (let j = 0; j < rgb.length; j += 8192) bin += String.fromCharCode.apply(null, rgb.subarray(j, j + 8192));
        frames[next++] = btoa(bin);
      }
      if (next < n && !v.ended) v.requestVideoFrameCallback(grab); else resolve();
    };
    v.addEventListener('ended', () => resolve(), {once: true});
    setTimeout(resolve, (d / rate + 15) * 1000);
    v.requestVideoFrameCallback(grab);
    v.playbackRate = rate; v.play().catch(() => resolve());
  });
  v.pause();
  return {duration: d, w: c.width, h: c.height, vw: v.videoWidth, vh: v.videoHeight, frames};
}"""

GRAB_JS = """async (t) => {
  const v = document.getElementById('v');
  if (Math.abs(v.currentTime - t) > 0.001) await new Promise(r => { v.addEventListener('seeked', r, {once: true}); v.currentTime = t; });
  const c = document.createElement('canvas');
  c.width = v.videoWidth; c.height = v.videoHeight;
  c.getContext('2d').drawImage(v, 0, 0);
  return c.toDataURL('image/png');
}"""


class Sampler:
    """One Chromium for many clips; each clip is served same-origin so its
    frames can be read off a canvas (a cross-origin clip taints it)."""

    def __enter__(self):
        from playwright.sync_api import sync_playwright
        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch()
        return self

    def __exit__(self, *exc):
        self._browser.close()
        self._pw.stop()

    def open(self, path):
        if not self._browser.is_connected():  # a clip that crashed Chromium does not stop the pass
            self._browser = self._pw.chromium.launch()
        page = self._browser.new_page()
        page.route(PAGE, lambda route: route.fulfill(status=200, body=HTML, headers={"Content-Type": "text/html"}))
        page.route("http://lp.local/v/clip", _ranged_route(path))
        page.goto(PAGE)
        return page


def sample(page, step=STEP, small=SMALL):
    """(duration, frames NxHxWx3 float 0..1, video size): played through once,
    or seeked sample by sample when the playback missed frames."""
    got = page.evaluate(PLAY_JS, {"step": step, "small": small, "rate": PLAY_RATE})
    missing = sum(1 for f in got["frames"] if f is None)
    if missing > 0.05 * len(got["frames"]):
        page.evaluate("() => { const v = document.getElementById('v'); v.pause(); v.currentTime = 0; }")
        got = page.evaluate(SAMPLE_JS, {"step": step, "small": small})
    w, h = got["w"], got["h"]
    last, rows = None, []
    for f in got["frames"]:  # a frame the playback skipped at the very end repeats the one before it
        last = np.frombuffer(base64.b64decode(f), np.uint8).reshape(h, w, 3) if f else last
        if last is not None:
            rows.append(last)
    frames = np.stack(rows)
    return got["duration"], frames.astype(np.float32) / 255.0, (got["vw"], got["vh"])


def grab(page, t, png):
    url = page.evaluate(GRAB_JS, float(t))
    Path(png).write_bytes(base64.b64decode(url.split(",", 1)[1]))
    return png


def segment(frames, step=STEP):
    """States and transitions from dense samples: (states [(i0, i1)], live mask
    or None, per-pair changed share). A state is a run of holding pairs at
    least MIN_HOLD long; pixels that change in most pairs are the live region
    and do not stop a hold."""
    delta = np.abs(np.diff(frames, axis=0)).max(axis=-1) > NOISE   # (N-1)xHxW
    live = delta.mean(axis=0) > LIVE if len(delta) >= 4 else np.zeros(frames.shape[1:3], bool)
    live = live if live.mean() > 0.002 else None
    moving = delta & ~live if live is not None else delta
    share = moving.reshape(len(moving), -1).mean(axis=1)
    holds = share < STILL
    states, i = [], 0
    while i < len(holds):
        if holds[i]:
            j = i
            while j < len(holds) and holds[j]:
                j += 1
            if j - i >= MIN_HOLD - 1:
                states.append((i, j))          # samples i..j hold still
            i = j
        else:
            i += 1
    if not states:  # a clip that never holds: its first and last frames stand for it
        states = [(0, 0), (len(frames) - 1, len(frames) - 1)] if len(frames) > 1 else [(0, 0)]
    # an intro or an outro that never holds still (a tile pulsing in, a last zoom) is still a state:
    # its first (last) frame, so the clip's opening and close are not the next hold stretched over them
    if states[0][0] > 2:
        states.insert(0, (0, 0))
    if states[-1][1] < len(frames) - 3:
        states.append((len(frames) - 1, len(frames) - 1))
    return states, live, share


def _bbox(mask):
    ys, xs = np.nonzero(mask)
    if not len(ys):
        return None
    return [int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1]


def transition(frames, a, b, live=None):
    """What happens between the last hold sample `a` and the next hold's first
    sample `b`: {type, region} with type one of cut, crossfade, fade-in,
    fade-out, wipe-lr / wipe-rl / wipe-tb / wipe-bt, slide, appear, vanish,
    change."""
    A, B = frames[a], frames[b]
    diff = np.abs(B - A).max(axis=-1) > NOISE
    if live is not None:
        diff &= ~live
    region = _bbox(diff)
    out = {"frames": b - a, "region": region, "share": round(float(diff.mean()), 4)}
    if region is None:
        out["type"] = "none"
        return out
    if b - a <= 1:
        out["type"] = "cut"
        return out
    x0, y0, x1, y1 = region
    mids = frames[a + 1:b]
    RA, RB, RM = A[y0:y1, x0:x1], B[y0:y1, x0:x1], mids[:, y0:y1, x0:x1]
    d = (RB - RA).reshape(-1)
    # crossfade: each middle frame is (1 - alpha) A + alpha B for one alpha
    alphas, resid = [], []
    for m in RM:
        e = (m - RA).reshape(-1)
        al = float(e @ d / max(1e-6, d @ d))
        alphas.append(al)
        resid.append(float(np.abs(e - al * d).mean() / max(1e-6, np.abs(d).mean())))
    if max(resid) < 0.35 and all(q >= p - 0.08 for p, q in zip(alphas, alphas[1:])):
        dark = lambda f: float(f.mean()) < 0.06  # noqa: E731
        out["type"] = "fade-in" if dark(RA) else "fade-out" if dark(RB) else "crossfade"
        return out
    # wipe: a boundary sweeps the region; each column (row) flips from A to B in order
    near_b = np.abs(RM - RB[None]).max(axis=-1) < NOISE * 2
    near_a = np.abs(RM - RA[None]).max(axis=-1) < NOISE * 2
    changed = np.abs(RB - RA).max(axis=-1) > NOISE
    for axis, names in ((1, ("wipe-lr", "wipe-rl")), (0, ("wipe-tb", "wipe-bt"))):
        flip = []
        for k in range(len(RM)):
            done = (near_b[k] & changed).sum(axis=1 - axis) / np.maximum(1, changed.sum(axis=1 - axis))
            flip.append(done)
        flip = np.array(flip)  # frames x positions: share flipped to B
        if flip.shape[1] < 4:
            continue
        cols = np.arange(flip.shape[1])
        firsts = np.array([np.argmax(flip[:, c] > 0.5) if (flip[:, c] > 0.5).any() else len(RM) for c in cols])
        valid = changed.sum(axis=1 - axis) > 0
        if valid.sum() >= 4:
            corr = np.corrcoef(cols[valid], firsts[valid])[0, 1] if np.std(firsts[valid]) > 0 else 0.0
            if corr > 0.8:
                out["type"] = names[0]
                return out
            if corr < -0.8:
                out["type"] = names[1]
                return out
    area = (x1 - x0) * (y1 - y0) / (A.shape[0] * A.shape[1])
    if area < 0.5:
        flat = lambda R: float(np.abs(R - np.median(R.reshape(-1, 3), axis=0)).max(axis=-1).mean()) < 0.05  # noqa: E731
        if flat(RA) and not flat(RB):
            out["type"] = "appear"
            return out
        if flat(RB) and not flat(RA):
            out["type"] = "vanish"
            return out
    # slide: the middle frames are A shifted (phase correlation on grey)
    out["type"] = "slide" if _shifts(RA, RM) else "change"
    return out


def _shifts(RA, RM):
    """True when the middle frames are mostly translations of the first."""
    g0 = RA.mean(axis=-1)
    if min(g0.shape) < 8:
        return False
    F0 = np.fft.fft2(g0 - g0.mean())
    moves = 0
    for m in RM:
        g = m.mean(axis=-1)
        F = np.fft.fft2(g - g.mean())
        R = F0 * np.conj(F)
        r = np.abs(np.fft.ifft2(R / np.maximum(1e-9, np.abs(R))))
        dy, dx = np.unravel_index(r.argmax(), r.shape)
        if r.max() > 0.2 and (dx or dy):
            moves += 1
    return moves >= max(1, len(RM) // 2)


def build(rec, sampler, out_dir, step=STEP):
    """The storyboard of one clip, its keyframes written beside it."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    page = sampler.open(rec["local_path"])
    try:
        duration, frames, (vw, vh) = sample(page, step)
        # the dense samples are kept, so a later pass re-reads the clip without decoding it again
        np.savez_compressed(out_dir / "samples.npz", frames=(frames * 255).round().astype(np.uint8), step=step)
        states, live, share = segment(frames, step)
        board = {"id": attrs.asset_id(rec["src"]), "src": rec["src"], "local": rec["local_path"], "page": rec["page"],
                 "slot": rec["slot"], "type": rec["type"], "role": rec["role"], "duration": round(duration, 3),
                 "size": [vw, vh], "step": step, "samples": len(frames),
                 "live": _scale_box(_bbox(live), frames.shape, vw) if live is not None else None,
                 "motion": [round(float(x), 4) for x in share], "states": [], "transitions": []}
        for k, (i0, i1) in enumerate(states):
            t = (i0 + i1) / 2 * step
            png = grab(page, t, out_dir / f"s{k}.png")
            board["states"].append({"k": k, "t0": round(i0 * step, 2), "t1": round(min(duration, (i1 + 1) * step), 2),
                                    "key": png.name, "t": round(t, 2)})
            if k:
                tr = transition(frames, states[k - 1][1], i0, live)
                tr["region"] = _scale_box(tr["region"], frames.shape, vw)
                t0, t1 = states[k - 1][1] * step, i0 * step
                entry = {"from": k - 1, "to": k, "t0": round(t0, 2), "t1": round(t1, 2), **tr}
                if t1 - t0 >= 3 * step:  # the middle of a long transition, full size: a prompt half typed, a reveal half done
                    entry["mid"] = grab(page, (t0 + t1) / 2, out_dir / f"t{k}.png").name
                board["transitions"].append(entry)
    finally:
        page.close()
    reads = ocr.read([out_dir / s["key"] for s in board["states"]])
    for s in board["states"]:
        p = str(out_dir / s["key"])
        s["reading"] = layout.read(p, reads.get(p))
    (out_dir / "storyboard.json").write_text(json.dumps(board))
    return board


def _scale_box(box, shape, vw):
    if box is None:
        return None
    f = vw / shape[2]
    return [round(v * f) for v in box]


def targets(con, pages=None):
    recs = attrs.candidates(con, {}, roles=("creative", "thumbnail", "ui-screenshot"), kinds=("video",), force=True)
    return [r for r in recs if r["local_path"] and Path(r["local_path"]).exists() and (not pages or r["page"] in pages)
            and Path(r["local_path"]).suffix.lower() in (".webm", ".mp4", ".mov", ".m4v")]  # a .psd filed as video is not a clip


def load(aid, store=STORE):
    p = Path(store) / aid / "storyboard.json"
    return json.loads(p.read_text()) if p.exists() else None


def every(store=STORE):
    for p in sorted(Path(store).glob("*/storyboard.json")):
        yield json.loads(p.read_text())


def run(con, limit=None, force=False, pages=None, store=STORE):
    recs = targets(con, pages)
    todo = [r for r in recs if force or not (Path(store) / attrs.asset_id(r["src"]) / "storyboard.json").exists()]
    kept = len(recs) - len(todo)
    if limit:
        todo = todo[:limit]
    done = 0
    with Sampler() as s:
        for i, r in enumerate(todo, 1):
            try:
                build(r, s, Path(store) / attrs.asset_id(r["src"]))
                done += 1
            except Exception as e:  # an undecodable clip is reported, never fatal to the pass
                print(f"storyboard: {r['local_path']}: {e}", file=sys.stderr)
            if i % 10 == 0:
                print(f"storyboard: {i}/{len(todo)}", file=sys.stderr)
    return {"targets": len(recs), "built": done, "kept": kept}
