"""The Before of a before/after, made from the generated After.

An enhancer page shows what its tool fixes, so the Before is the After with
that fault put back in: blurred for unblur/sharpen, pixelated for unpixelate
and upscale, grainy for denoise, dark for lighting and video enhance, faded
and scratched for restoration. Local, deterministic and free, and the pair is
aligned pixel for pixel (roles.yaml `pages:` picks the mode per page).
Strength is relative to the picture's short side, so it reads the same at any
render size."""

import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageOps

MODES = ("blur", "pixelate", "noise", "lowlight", "scratches", "desaturate")


def _resample(im, k, down=Image.BILINEAR, up=Image.BILINEAR):
    w, h = im.size
    small = im.resize((max(1, round(w / k)), max(1, round(h / k))), down)
    return small.resize((w, h), up)


def degrade(im, mode, amount=1.0, seed=7):
    """`im` with the fault `mode` applied (RGBA in, RGBA out, alpha kept)."""
    if mode not in MODES:
        raise ValueError(f"degrade mode {mode!r}: one of {', '.join(MODES)}")
    im = im.convert("RGBA")
    alpha = im.getchannel("A")
    rgb = im.convert("RGB")
    side = min(im.size)
    if mode == "blur":  # soft focus: detail lost, shapes kept (the corpus Before shots)
        rgb = _resample(rgb, 1 + 5 * amount).filter(ImageFilter.GaussianBlur(side * 0.006 * amount))
    elif mode == "pixelate":  # blocky low resolution
        rgb = _resample(rgb, max(2, side / (44 / max(amount, 0.05))), Image.BOX, Image.NEAREST)
    elif mode == "noise":  # high-ISO grain with a colour cast
        a = np.asarray(rgb, dtype=np.float32)
        grain = np.random.default_rng(seed).normal(0, 34 * amount, a.shape[:2])[..., None]
        chroma = np.random.default_rng(seed + 1).normal(0, 12 * amount, a.shape)
        rgb = Image.fromarray(np.clip(a + grain + chroma, 0, 255).astype(np.uint8))
        rgb = ImageEnhance.Color(rgb).enhance(1 - 0.3 * amount)
    elif mode == "lowlight":  # under-exposed, flat, muddy
        rgb = ImageEnhance.Brightness(rgb).enhance(1 - 0.55 * amount)
        rgb = ImageEnhance.Contrast(rgb).enhance(1 - 0.35 * amount)
        rgb = ImageEnhance.Color(rgb).enhance(1 - 0.45 * amount)
    elif mode == "scratches":  # an old print: faded sepia, soft, scratched
        grey = ImageOps.grayscale(_resample(rgb, 1 + 2 * amount))
        rgb = ImageOps.colorize(grey, (52, 38, 26), (236, 222, 196))
        rgb = ImageEnhance.Contrast(rgb).enhance(1 - 0.3 * amount)
        rng = np.random.default_rng(seed)
        d = ImageDraw.Draw(rgb)
        w, h = rgb.size
        for _ in range(round(14 * amount)):
            x = rng.uniform(0, w)
            d.line([(x, rng.uniform(0, h * 0.3)), (x + rng.uniform(-w * 0.04, w * 0.04), rng.uniform(h * 0.6, h))],
                   fill=(245, 238, 224), width=max(1, round(side * 0.002)))
    elif mode == "desaturate":
        rgb = ImageOps.grayscale(rgb).convert("RGB")
    out = rgb.convert("RGBA")
    out.putalpha(alpha)
    return out


def split(im, mode, until=0.5, amount=1.0):
    """`im` with its left `until` share degraded: the compare-slider card, the
    handle drawn at the seam."""
    out = im.convert("RGBA").copy()
    cut = round(out.width * until)
    if cut > 0:
        out.paste(degrade(out, mode, amount).crop((0, 0, cut, out.height)), (0, 0))
    return out
