"""lp-inject: write a run's chosen media and changed text back into the page
snapshot and emit runs/<run>/dist/index.html.

Input is runs/<run>/page.md (the skeleton with a `chosen:` key added to each
filled slot block) plus slots.json from `lp-corpus skeleton`. Every element
is addressed by the data-lp / data-lp-t stamps sectionize wrote into the
snapshot. Images are centre-cropped to the slot's aspect and downscaled to
the slot size; videos are copied as they are. A slot whose `chosen` is null
(dry run) gets a labelled placeholder image."""

import argparse
import json
import re
import shutil
import sys
import urllib.parse
import urllib.request
from pathlib import Path

import yaml
from bs4 import BeautifulSoup

SLOT_RE = re.compile(r"^```slot\n(.*?)\n```", re.M | re.S)
TEXT_RE = re.compile(r"^- (t\d+) (\w+): (.*?)(?: -> \S+)?$", re.M)
SECTION_RE = re.compile(r"^## (S\d+) ", re.M)
UA = "Mozilla/5.0 (Macintosh) lp-inject/0.1"


def parse_page_md(text):
    """Return (slots by id, texts by tid) from page.md / skeleton.md."""
    slots = {}
    for block in SLOT_RE.findall(text):
        slot = yaml.safe_load(block)
        slots[slot["id"]] = slot
    texts = {}
    parts = re.split(SECTION_RE, text)
    for sid, body in zip(parts[1::2], parts[2::2]):
        for tid, tag, value in TEXT_RE.findall(body):
            texts[f"{sid}-{tid}"] = value.strip()
    return slots, texts


def fetch_to(src, dest):
    if src.startswith(("http://", "https://")):
        req = urllib.request.Request(src, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=120) as r, open(dest, "wb") as f:
            shutil.copyfileobj(r, f)
    else:
        shutil.copyfile(src, dest)
    return dest


def fit_image(path, size):
    """Centre-crop to the slot aspect and downscale to the slot size; never
    upscale. Re-encodes as PNG (AVIF/WebP inputs included)."""
    from PIL import Image
    w, h = size
    with Image.open(path) as im:
        im = im.convert("RGBA" if im.mode in ("RGBA", "LA", "P") else "RGB")
        iw, ih = im.size
        target = w / h
        if iw / ih > target:
            cw = round(ih * target); box = ((iw - cw) // 2, 0, (iw - cw) // 2 + cw, ih)
        else:
            ch = round(iw / target); box = (0, (ih - ch) // 2, iw, (ih - ch) // 2 + ch)
        im = im.crop(box)
        if im.width > w:
            im = im.resize((w, h), Image.LANCZOS)
        out = path.with_suffix(".png")
        im.save(out)
    if out != path:
        path.unlink()
    return out


def placeholder(dest, slot):
    """Grey box labelled with the slot id and size, at the slot size."""
    from PIL import Image, ImageDraw
    w, h = slot_size(slot) or (1200, 675)
    im = Image.new("RGB", (w, h), (90, 90, 96))
    d = ImageDraw.Draw(im)
    label = f"{slot['id']}  {slot.get('kind', '')}  {w}x{h}"
    d.rectangle((0, 0, w - 1, h - 1), outline=(200, 200, 205), width=max(2, w // 200))
    d.text((w // 20, h // 2 - 8), label, fill=(235, 235, 240))
    im.save(dest)
    return dest


def slot_size(slot):
    size = slot.get("size")
    if not size:
        return None
    w, h = size.split("x")
    return int(w), int(h)


def inject(run, out=None, log=print):
    run = Path(run)
    out = Path(out) if out else run / "dist"
    page_md = (run / "page.md") if (run / "page.md").exists() else run / "skeleton.md"
    slots_meta = json.loads((run / "slots.json").read_text())
    snapshot = Path(slots_meta["snapshot"])
    slots, texts = parse_page_md(page_md.read_text())
    soup = BeautifulSoup(snapshot.read_text(), "html.parser")

    out.mkdir(parents=True, exist_ok=True)
    media_src_dir = snapshot.parent / "media"
    if media_src_dir.is_dir():
        shutil.copytree(media_src_dir, out / "media", dirs_exist_ok=True)
    gen_dir = out / "media" / "gen"
    gen_dir.mkdir(parents=True, exist_ok=True)

    report = {"filled": [], "placeholders": [], "kept": [], "texts_changed": 0, "missing": []}
    for slot_id, slot in slots.items():
        el = soup.select_one(f'[data-lp="{slot_id}"]')
        if el is None:
            report["missing"].append(slot_id)
            continue
        if "chosen" not in slot:
            report["kept"].append(slot_id)
            continue
        chosen = slot["chosen"]
        if chosen:
            src = str(chosen)
            if not src.startswith(("http://", "https://")) and not Path(src).is_absolute():
                src = str(run / src)  # a composite's result.md names its file relative to the run
            ext = Path(urllib.parse.urlsplit(src).path).suffix or ".bin"
            dest = fetch_to(src, gen_dir / f"{slot_id}{ext}")
            if slot.get("kind") == "image" and slot_size(slot):
                dest = fit_image(dest, slot_size(slot))
            report["filled"].append(slot_id)
        else:
            dest = placeholder(gen_dir / f"{slot_id}-placeholder.png", slot)
            report["placeholders"].append(slot_id)
        rel = f"media/gen/{dest.name}"
        if el.name == "video" and dest.suffix == ".png":
            img = soup.new_tag("img", src=rel, alt=f"placeholder {slot_id}")
            for attr in ("class", "style", "data-lp"):
                if el.get(attr):
                    img[attr] = el[attr]
            el.replace_with(img)
        else:
            el["src"] = rel
            el.attrs.pop("srcset", None)
            if el.name == "video":
                el.attrs.pop("poster", None)
        el = soup.select_one(f'[data-lp="{slot_id}"]')
        el["data-lp-chosen"] = str(chosen) if chosen else "placeholder"

    for tid, value in texts.items():
        el = soup.select_one(f'[data-lp-t="{tid}"]')
        if el is None:
            continue
        current = re.sub(r"\s+", " ", el.get_text(" ")).strip()
        if value and value != current:
            el.clear()
            el.string = value
            report["texts_changed"] += 1

    (out / "index.html").write_text(str(soup))
    log(f"{out / 'index.html'}: {len(report['filled'])} filled, {len(report['placeholders'])} placeholders, "
        f"{len(report['kept'])} kept from source, {report['texts_changed']} text nodes changed"
        + (f", missing stamps: {report['missing']}" if report["missing"] else ""))
    return report


def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        prog="lp-inject",
        description="Inject a run's chosen media and text into the source HTML snapshot.",
    )
    p.add_argument("run", type=Path, help="run folder containing page.md (or skeleton.md) and slots.json")
    p.add_argument("--out", type=Path, help="output folder (default <run>/dist)")
    a = p.parse_args(argv)
    try:
        report = inject(a.run, a.out)
    except FileNotFoundError as exc:
        sys.exit(f"lp-inject: {exc}")
    return 1 if report["missing"] else 0


if __name__ == "__main__":
    sys.exit(main())
