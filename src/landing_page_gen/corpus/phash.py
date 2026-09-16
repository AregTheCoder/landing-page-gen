"""Perceptual hashes: the corpus's first content-level identity.

Every other id in the repo is derived from a URL (the CDN uuid prefix, the
sha1 of the served address), so the same photograph under two URLs counts
twice. `dhash` reads the picture itself — a 64-bit difference hash that
survives resizing and re-encoding (not crops) — and `hamming` compares two
of them. Used by the pool to keep external stock unique against itself and
against the corpus."""

from PIL import Image

SIZE = (9, 8)  # 8x8 horizontal comparisons -> 64 bits


def _rgb(source):
    """An RGB copy of a path or a PIL Image (a caller's Image stays open)."""
    if isinstance(source, Image.Image):
        return source.convert("RGB")
    with Image.open(source) as im:
        return im.convert("RGB")


def dhash(source):
    """16-hex dHash: greyscale, 9x8, one bit per horizontal neighbour pair."""
    px = _rgb(source).convert("L").resize(SIZE, Image.LANCZOS).tobytes()
    bits = 0
    for row in range(SIZE[1]):
        for col in range(SIZE[1]):
            bits = (bits << 1) | (px[row * SIZE[0] + col] > px[row * SIZE[0] + col + 1])
    return f"{bits:016x}"


def dhash_pair(source):
    """(hash, hash of the mirror): Picsart flips stock now and then, and a
    mirrored duplicate is still a duplicate."""
    rgb = _rgb(source)
    return dhash(rgb), dhash(rgb.transpose(Image.FLIP_LEFT_RIGHT))


def hamming(a, b):
    """Bit distance between two 16-hex hashes."""
    return (int(a, 16) ^ int(b, 16)).bit_count()
