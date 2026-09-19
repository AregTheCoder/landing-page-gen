"""lp-inject: write a run's chosen media and changed text back into the page
snapshot and emit runs/<run>/dist/index.html.

Input is runs/<run>/skeleton.md plus each sections/*/result.md (whose
frontmatter names the `chosen` asset per slot) and slots.json from `lp-corpus
skeleton`; lp-inject assembles page.md itself. Every element
is addressed by the data-lp / data-lp-t stamps sectionize wrote into the
snapshot. Images are centre-cropped to the slot's aspect and downscaled to
the slot size; videos are copied as they are, given the result's `poster`
(the accepted still, fitted like an image) and the autoplay-muted-loop
attributes a landing page expects. A slot whose `chosen` is null (dry run)
gets a labelled placeholder image."""

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


def _result_slots(run):
    """{slot_id: {chosen, workflow}} from every sections/*/result.md frontmatter,
    so the manager no longer hand-writes page.md (a 47 KB restatement of the
    skeleton plus each worker's chosen line)."""
    out = {}
    sections = run / "sections"
    for res in sorted(sections.glob("S*/result.md")) if sections.is_dir() else []:
        m = re.match(r"^---\n(.*?)\n---", res.read_text(), re.S)
        if not m:
            continue
        fm = yaml.safe_load(m.group(1)) or {}
        workflow = f"sections/{res.parent.name}/workflow.yaml"
        for sid, s in (fm.get("slots") or {}).items():
            if isinstance(s, dict) and "chosen" in s:
                out[sid] = {"chosen": s.get("chosen"), "workflow": workflow}
                out[sid].update({k: s[k] for k in ("poster", "duration_s") if s.get(k) is not None})  # video slots
    return out


def assemble_page_md(run):
    """The skeleton with each produced slot's `chosen`/`workflow` appended to its
    slot block, kept-from-source slots untouched — what the manager used to write."""
    run = Path(run)
    skeleton = (run / "skeleton.md").read_text()
    results = _result_slots(run)

    def add(m):
        block = m.group(1)
        slot = yaml.safe_load(block) or {}
        r = results.get(slot.get("id"))
        if r is None or "chosen" in slot:
            return m.group(0)
        lines = yaml.safe_dump(r, sort_keys=False, allow_unicode=True, width=10000).rstrip()
        return f"```slot\n{block}\n{lines}\n```"

    return SLOT_RE.sub(add, skeleton)


def fetch_to(src, dest):
    if src.startswith(("http://", "https://")):
        req = urllib.request.Request(src, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=120) as r, open(dest, "wb") as f:
            shutil.copyfileobj(r, f)
    else:
        shutil.copyfile(src, dest)
    return dest


def looks_like_html(text):
    """A stylesheet URL that has gone stale (the origin redeployed and the
    content-hashed chunk no longer exists) serves the SPA/app-shell HTML with a
    200, not a 404. Saving that as `.css` silently breaks the page. Detect it."""
    head = text.lstrip()[:200].lower()
    return head.startswith(("<!doctype", "<html")) or "<head" in head


def absolutise_css_urls(css, css_url):
    """Rewrite relative url(...) refs in a chunk to absolute, so fonts and
    background images still resolve after the chunk is moved to <run>/dist/css/."""
    origin = "https://" + urllib.parse.urlsplit(css_url).netloc

    def repl(m):
        q = m.group(1).strip().strip("\"'")
        if q.startswith(("http://", "https://", "data:")):
            return m.group(0)
        if q.startswith("/"):
            return f'url("{origin}{q}")'
        base = css_url.rsplit("/", 1)[0] + "/"
        return f'url("{base}{q}")'

    return re.sub(r"url\(([^)]+)\)", repl, css)


def _get_text(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read().decode("utf-8", "replace")


def current_css_urls(source_url):
    """The stylesheet chunk URLs the source page references RIGHT NOW — used to
    recover a snapshot whose hashed chunks have gone stale."""
    try:
        html = _get_text(source_url)
    except Exception:
        return []
    urls, seen = [], set()
    for m in re.finditer(r'href="(https?://[^"]+\.css)"', html):
        u = m.group(1)
        if u not in seen:
            seen.add(u); urls.append(u)
    return urls


def localise_css(soup, out, source_url=None, log=print):
    """Download every remote stylesheet the page links, verify each is real CSS
    (never HTML), save under dist/css/ and point the <link>s at the local copy,
    so the page formats without the origin's (perishable) hashed chunks. If a
    chunk has gone stale, recover the origin's current chunk set. Returns a
    report; `stale` non-empty means the page would not format and is a hard
    failure the caller must surface."""
    links = [l for l in soup.find_all("link", rel="stylesheet")
             if str(l.get("href", "")).startswith(("http://", "https://"))
             and ".css" in str(l.get("href", ""))]
    if not links:
        return {"localised": 0, "stale": [], "recovered": False}

    css_dir = out / "css"
    css_dir.mkdir(parents=True, exist_ok=True)

    def download_valid(url):
        try:
            body = _get_text(url)
        except Exception as exc:
            return None, f"fetch failed: {exc}"
        if looks_like_html(body):
            return None, "stale (served HTML, not CSS)"
        return body, None

    localised, stale = 0, []
    for link in links:
        url = link["href"]
        body, err = download_valid(url)
        if err:
            stale.append((url, err)); continue
        name = url.rsplit("/", 1)[-1]
        (css_dir / name).write_text(absolutise_css_urls(body, url))
        link["href"] = f"css/{name}"
        localised += 1

    recovered = False
    if stale and source_url:
        log(f"lp-inject: {len(stale)} stylesheet chunk(s) are stale; recovering current chunks from {source_url}")
        cur = current_css_urls(source_url)
        good = []
        for url in cur:
            body, err = download_valid(url)
            if err:
                continue
            name = url.rsplit("/", 1)[-1]
            (css_dir / name).write_text(absolutise_css_urls(body, url))
            good.append(name)
        if good:
            # Replace the whole stylesheet set with the recovered current one,
            # in document order, in <head>.
            for link in list(soup.find_all("link", rel="stylesheet")):
                link.decompose()
            head = soup.find("head") or soup
            for name in good:
                head.append(soup.new_tag("link", rel="stylesheet", href=f"css/{name}"))
            localised, stale, recovered = len(good), [], True

    return {"localised": localised, "stale": stale, "recovered": recovered}


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


def _frontmatter_source(text):
    m = re.match(r"^---\n(.*?)\n---", text, re.S)
    if not m:
        return None
    try:
        return (yaml.safe_load(m.group(1)) or {}).get("source")
    except yaml.YAMLError:
        return None


def inject(run, out=None, log=print, localise_css_assets=True):
    run = Path(run)
    out = Path(out) if out else run / "dist"
    if (run / "sections").is_dir() and any((run / "sections").glob("S*/result.md")):
        page_text = assemble_page_md(run)  # lp-inject owns page.md now
        (run / "page.md").write_text(page_text)
    else:  # older runs, or a hand-assembled page.md
        page_md = (run / "page.md") if (run / "page.md").exists() else run / "skeleton.md"
        page_text = page_md.read_text()
    slots_meta = json.loads((run / "slots.json").read_text())
    snapshot = Path(slots_meta["snapshot"])
    source_url = slots_meta.get("source") or _frontmatter_source(page_text)
    slots, texts = parse_page_md(page_text)
    soup = BeautifulSoup(snapshot.read_text(), "html.parser")

    out.mkdir(parents=True, exist_ok=True)
    media_src_dir = snapshot.parent / "media"
    if media_src_dir.is_dir():
        shutil.copytree(media_src_dir, out / "media", dirs_exist_ok=True)
    gen_dir = out / "media" / "gen"
    gen_dir.mkdir(parents=True, exist_ok=True)

    def bring(value, stem, fit):
        """Copy a result asset (URL, absolute path, or a path relative to the run —
        how a composite's result.md names its file) into dist/media/gen/."""
        src = str(value)
        if not src.startswith(("http://", "https://")) and not Path(src).is_absolute():
            src = str(run / src)
        ext = Path(urllib.parse.urlsplit(src).path).suffix or ".bin"
        dest = fetch_to(src, gen_dir / f"{stem}{ext}")
        return fit_image(dest, slot_size(slot)) if fit and slot_size(slot) else dest

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
            dest = bring(chosen, slot_id, fit=slot.get("kind") == "image")
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
                el.attrs.pop("poster", None)  # the snapshot's poster belongs to the old clip
                if slot.get("poster"):
                    poster = bring(slot["poster"], f"{slot_id}-poster", fit=True)
                    el["poster"] = f"media/gen/{poster.name}"
                for attr in ("muted", "autoplay", "loop", "playsinline"):
                    el[attr] = ""
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

    report["css_stale"] = []
    if localise_css_assets:
        css = localise_css(soup, out, source_url=source_url, log=log)
        report["css_localised"] = css["localised"]
        report["css_stale"] = [u for u, _ in css["stale"]]
        if css["stale"]:
            log("lp-inject: WARNING the page will NOT format — these stylesheet "
                "chunks are stale and could not be recovered:")
            for u, why in css["stale"]:
                log(f"  - {u} ({why})")
            if not source_url:
                log("  no `source:` URL to recover current chunks from; re-fetch "
                    "the snapshot or pass one.")
        elif css["recovered"]:
            log(f"lp-inject: recovered {css['localised']} current stylesheet chunks "
                f"(snapshot's were stale); page is self-contained.")
        elif css["localised"]:
            log(f"lp-inject: localised {css['localised']} stylesheet chunks; page is self-contained.")

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
    p.add_argument("--no-localise-css", dest="localise_css", action="store_false",
                   help="keep remote stylesheet links instead of downloading and validating them "
                        "(the page then depends on the origin's perishable hashed CSS chunks)")
    a = p.parse_args(argv)
    try:
        report = inject(a.run, a.out, localise_css_assets=a.localise_css)
    except FileNotFoundError as exc:
        sys.exit(f"lp-inject: {exc}")
    # Stale CSS means the page will not format: fail loudly rather than ship it.
    return 1 if (report["missing"] or report.get("css_stale")) else 0


if __name__ == "__main__":
    sys.exit(main())
