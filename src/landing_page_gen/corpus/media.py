"""Localise a snapshot's media: download every image, video and poster into
corpus/pages/<slug>/media/ and point page.html at the copies. The attribute
as served stays on the element as data-lp-src / data-lp-poster, which is what
`sectionize` reads for the CDN URL and the render.json geometry key. Used by
`fetch` (on by default) and by `lp-corpus media` for snapshots fetched
earlier. Stylesheets, fonts and CSS background images stay remote."""

import hashlib
import json
import os
import shutil
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from bs4 import BeautifulSoup

from .sectionize import cdn_url

UA = "Mozilla/5.0 (Macintosh) lp-corpus/0.1"


def local_name(url):
    """<stem>-<8 hex of the full URL><ext>: readable, unique across hosts and
    query-string renditions, and the same on every run."""
    path = Path(urllib.parse.urlsplit(url).path)
    digest = hashlib.sha1(url.encode()).hexdigest()[:8]
    return f"{path.stem[:40] or 'asset'}-{digest}{path.suffix.lower() or '.bin'}"


def download(url, dest, timeout=60):
    """Fetch to dest through a .part file, so an interrupted run never leaves
    a truncated file that the next run would treat as done."""
    part = dest.with_suffix(dest.suffix + ".part")
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r, open(part, "wb") as f:
        shutil.copyfileobj(r, f)
    os.replace(part, dest)
    return dest


def media_refs(soup):
    """(element, attribute) pairs to localise: img src, video src and poster."""
    refs = []
    for el in soup.find_all(["img", "video"]):
        refs.append((el, "src"))
        if el.name == "video" and (el.get("poster") or el.get("data-lp-poster")):
            refs.append((el, "poster"))
    return refs


def localise_html(soup, media_dir, log=print, workers=8):
    """Download the assets, rewrite the attributes, drop what only made sense
    online (srcset, image preloads, <picture> sources, <base>).
    Returns {"ok": n, "failed": n}."""
    media_dir = Path(media_dir)
    media_dir.mkdir(parents=True, exist_ok=True)
    for link in soup.find_all("link", rel=lambda r: r and "preload" in r):
        if link.get("as") == "image":
            link.decompose()
    for source in soup.find_all("source"):
        if source.parent is not None and source.parent.name == "picture":
            source.decompose()

    jobs = []
    for el, attr in media_refs(soup):
        orig = el.get(f"data-lp-{attr}") or el.get(attr) or ""
        if not orig or orig.startswith("data:"):
            continue
        url = cdn_url(orig)
        jobs.append((el, attr, orig, url, media_dir / local_name(url)))
    todo = {dest: url for _, _, _, url, dest in jobs if not dest.exists()}

    def fetch(item):
        dest, url = item
        try:
            download(url, dest)
        except Exception as exc:  # one bad asset must not fail the page
            log(f"  could not download {url}: {exc}")

    with ThreadPoolExecutor(workers) as pool:
        list(pool.map(fetch, todo.items()))

    ok = 0
    for el, attr, orig, url, dest in jobs:
        el[f"data-lp-{attr}"] = orig
        if dest.exists():
            el[attr] = f"media/{dest.name}"
            ok += 1
        else:
            el[attr] = url
        if attr == "src":
            el.attrs.pop("srcset", None)
            el.attrs.pop("sizes", None)

    # Relative local paths and <base href="https://picsart.com/"> cannot
    # coexist; make the remaining relative links absolute and drop the base.
    base = soup.find("base")
    if base is not None:
        root = base.get("href") or "https://picsart.com/"
        for el in soup.find_all(href=True):
            el["href"] = urllib.parse.urljoin(root, el["href"])
        for el in soup.find_all(src=True):
            if not el["src"].startswith("media/"):
                el["src"] = urllib.parse.urljoin(root, el["src"])
        base.decompose()
    return {"ok": ok, "failed": len(jobs) - ok}


def localise_page(page_dir, log=print):
    """Localise corpus/pages/<slug>/page.html in place; record counts in meta.json."""
    page_dir = Path(page_dir)
    html_path = page_dir / "page.html"
    soup = BeautifulSoup(html_path.read_text(), "html.parser")
    counts = localise_html(soup, page_dir / "media", log=log)
    html_path.write_text(str(soup))
    meta_path = page_dir / "meta.json"
    meta = json.loads(meta_path.read_text()) if meta_path.exists() else {}
    meta["media"] = counts
    meta_path.write_text(json.dumps(meta, indent=1))
    log(f"{page_dir.name}: {counts['ok']} media files" + (f", {counts['failed']} failed" if counts["failed"] else ""))
    return counts
