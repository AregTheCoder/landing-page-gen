"""Read a composite back: every string a block sets must be legible where the
block sits, as the words it was given.

The check that would have caught the ROAS formula: its 600-weight ÷ printed
as +, and OCR (macOS Vision, on-device, `corpus/ocr.py`) reads the render as
"Revenue + Ad Spend". Words may differ by one OCR slip when long; symbols and
numbers must read exactly (÷ is not +, 7.14 is not 7.1). A string OCR cannot
find at all is either too small to read at the output size or not drawn."""

import re
import shutil
import sys

from . import draw

REF = 1600
PAD = 0.04  # share of the canvas a block's box is widened by when collecting what reads inside it
SWAP = {"‘": "'", "’": "'", "“": '"', "”": '"', "–": "-", "—": "-", "…": "...", " ": " ", "•": " ", "·": " "}


def available():
    return sys.platform == "darwin" and shutil.which("swiftc") is not None


def _norm(s):
    s = str(s).casefold()
    for a, b in SWAP.items():
        s = s.replace(a, b)
    return re.findall(r"[^\W_]+|[^\w\s]", s)


def _close(a, b):
    """Two tokens match: equal, or a long word one edit apart."""
    if a == b:
        return True
    if not (a.isalpha() and b.isalpha()) or min(len(a), len(b)) < 5 or abs(len(a) - len(b)) > 1:
        return False
    if len(a) == len(b):
        return sum(x != y for x, y in zip(a, b)) <= 1
    short, long_ = sorted((a, b), key=len)
    return any(long_[:i] + long_[i + 1:] == short for i in range(len(long_)))


def found(expected, read):
    """Whether the tokens of `expected` appear in order in `read`."""
    want, got = _norm(expected), _norm(read)
    if not want:
        return True
    i = 0
    for tok in got:
        if _close(want[i], tok):
            i += 1
            if i == len(want):
                return True
    return False


def _inside(line, rect, pad):
    x0, y0, x1, y1 = line["box"]
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    return rect[0] - pad <= cx <= rect[2] + pad and rect[1] - pad <= cy <= rect[3] + pad


def problems(png, items, reading=None):
    """What the render does not say: one line per string of an item that does
    not read back inside the item's box."""
    if reading is None:
        from ..corpus import ocr
        reading = ocr.read([png])[str(png)]
    s = reading["w"] / REF
    pad = PAD * reading["w"]
    out = []
    for it in items:
        want = [x for x in draw.strings_of(it) if str(x).strip()]
        if not want:
            continue
        rect = [v * s for v in it["rect"]] if it.get("rect") else None
        lines = [ln for ln in reading["lines"] if rect is None or _inside(ln, rect, pad)]
        read = " ".join(ln["text"] for ln in lines)
        for w in want:
            if not found(w, read):
                seen = f"it reads {read!r}" if read else "nothing reads there (too small at this size, or not drawn)"
                out.append(f"{it.get('id')}: sets {w!r}; {seen}")
    return out
