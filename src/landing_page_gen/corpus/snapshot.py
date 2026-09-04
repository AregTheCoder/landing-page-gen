"""Fetch one Picsart landing page into corpus/pages/<slug>/.

The pages are React streaming SSR: the static HTML holds every section, but
out of order, as hidden `<div id="S:x">` segments that inline `$RC` scripts
swap into `<template id="P:x">` placeholders and Suspense `<template
id="B:x">` boundaries at load. `reassemble` does that swap in Python, which
was verified to give the same `<main>` as a Playwright render. Playwright is
still used, once per page, for the full-page screenshot and for the rendered
box of every image and video (the slot size a worker must fill)."""

import json
import re
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from bs4 import BeautifulSoup, Comment

from . import discover, media

HOST = "https://picsart.com"
UA_BROWSER = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/128.0 Safari/537.36")
VIEWPORT = {"width": 1440, "height": 900}
PAGES_DIR = Path("corpus/pages")

GEOMETRY_JS = """() => [...document.querySelectorAll('main img, main video, aside img, footer img')].map(e => {
  const r = e.getBoundingClientRect();
  const source = e.querySelector && e.querySelector('source');
  return {tag: e.tagName.toLowerCase(),
          src_attr: e.getAttribute('src') || (source ? source.getAttribute('src') : null),
          x: Math.round(r.x + window.scrollX), y: Math.round(r.y + window.scrollY),
          w: Math.round(r.width), h: Math.round(r.height),
          nat_w: e.naturalWidth || e.videoWidth || null, nat_h: e.naturalHeight || e.videoHeight || null,
          duration: (e.duration && isFinite(e.duration)) ? Math.round(e.duration * 100) / 100 : null};
})"""


def slug_for(url):
    path = discover.normalize(url) or urllib.parse.urlsplit(url).path
    parts = [p for p in path.split("/") if p]
    return "--".join(parts) if parts else "home"


def fetch_html(url, timeout=30):
    req = urllib.request.Request(url, headers={"User-Agent": UA_BROWSER})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", errors="ignore")


def reassemble(html):
    """Return a BeautifulSoup with every streamed segment moved into place."""
    soup = BeautifulSoup(html, "html.parser")
    segs = {d["id"]: d for d in soup.find_all("div", hidden=True, id=re.compile(r"^S:"))}
    # Placeholders: <template id="P:x"> becomes the children of <div id="S:x">.
    while (t := soup.find("template", id=re.compile(r"^P:"))) is not None:
        seg = segs.pop("S:" + t["id"][2:], None)
        if seg is None:
            t.decompose()
            continue
        t.replace_with(*list(seg.contents))
        seg.decompose()
    # Suspense boundaries: <!--$?--><template id="B:x"/>fallback...<!--/$--> ;
    # the fallback is replaced by the children of <div id="S:x">.
    for t in soup.find_all("template", id=re.compile(r"^B:")):
        seg = segs.pop("S:" + t["id"][2:], None)
        node = t.next_sibling
        while node is not None and not (isinstance(node, Comment) and node.strip() == "/$"):
            nxt = node.next_sibling
            node.extract()
            node = nxt
        if seg is None:
            t.decompose()
        else:
            t.replace_with(*list(seg.contents))
            seg.decompose()
    for seg in segs.values():
        seg.decompose()
    return soup


def snapshot_html(soup, base_url=HOST + "/"):
    """Make the reassembled soup a standalone snapshot: no scripts, absolute
    base, stylesheets kept. Mutates and returns the soup."""
    for tag in soup.find_all(["script", "template", "noscript"]):
        tag.decompose()
    for link in soup.find_all("link", rel=lambda r: r and "preload" in r):
        if link.get("as") == "script":
            link.decompose()
    for c in soup.find_all(string=lambda s: isinstance(s, Comment)):
        c.extract()
    head = soup.head or soup.new_tag("head")
    if not head.find("base"):
        base = soup.new_tag("base", href=base_url)
        head.insert(0, base)
    return soup


class Renderer:
    """One Chromium for many pages. Use as a context manager."""

    def __init__(self):
        self._pw = None
        self._browser = None

    def __enter__(self):
        from playwright.sync_api import sync_playwright
        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch()
        return self

    def __exit__(self, *exc):
        self._browser.close()
        self._pw.stop()

    def render(self, url, png_path):
        """Full-page screenshot plus the rendered geometry of every media node."""
        ctx = self._browser.new_context(viewport=VIEWPORT, reduced_motion="reduce", user_agent=UA_BROWSER)
        try:
            page = ctx.new_page()
            page.goto(url, wait_until="load", timeout=90_000)
            page.wait_for_timeout(1500)
            try:
                return self._capture(page, png_path)
            except Exception as exc:
                # A client-side redirect right after load destroys the context;
                # let the new document settle and capture once more.
                if "Execution context was destroyed" not in str(exc):
                    raise
                page.wait_for_load_state("load")
                page.wait_for_timeout(1500)
                return self._capture(page, png_path)
        finally:
            ctx.close()

    @staticmethod
    def _capture(page, png_path):
        # Sections use content-visibility:auto, which leaves them unpainted
        # in a full-page capture; force them visible, then scroll once so
        # lazy media loads.
        page.add_style_tag(content="*{content-visibility:visible!important;contain:none!important}")
        y, height = 0, page.evaluate("document.body.scrollHeight")
        while y < height:
            page.evaluate(f"window.scrollTo(0,{y})")
            page.wait_for_timeout(200)
            y += 700
            height = page.evaluate("document.body.scrollHeight")
        page.wait_for_timeout(800)
        geometry = page.evaluate(GEOMETRY_JS)
        page.evaluate("window.scrollTo(0,0)")
        page.wait_for_timeout(500)
        page.screenshot(path=str(png_path), full_page=True)
        return geometry


def save_page(url, pages_dir=PAGES_DIR, renderer=None, family=None, log=print, localise=True):
    """Fetch, reassemble and store one page. Returns its folder.

    Writes raw.html (as served), page.html (reassembled, script-free snapshot;
    with localise its media downloaded into media/ and linked locally, else
    with <base>), meta.json, and with a renderer also page.png and render.json."""
    url = HOST + discover.normalize(url) if not url.startswith("http") else url
    slug = slug_for(url)
    out = Path(pages_dir) / slug
    out.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    raw = fetch_html(url)
    (out / "raw.html").write_text(raw)
    soup = reassemble(raw)
    title = soup.title.get_text(strip=True) if soup.title else ""
    meta = {
        "slug": slug, "url": url, "title": title,
        "family": family or discover.classify(urllib.parse.urlsplit(url).path),
        "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    if soup.body is None or len(soup.body.get_text(strip=True)) < 200:
        # Some paths serve the client-side app shell (title "Picsart", a few
        # KB, no server-rendered text). Record it so fetch does not retry;
        # no snapshot. Pages without <main> but with content are sectionized
        # from <body>.
        meta["shell"] = True
        (out / "meta.json").write_text(json.dumps(meta, indent=1))
        log(f"skipped {slug}: app shell without <main> ({len(raw) // 1024} KB)")
        return out
    snapshot_html(soup)
    if localise:
        meta["media"] = media.localise_html(soup, out / "media", log=log)
    (out / "page.html").write_text(str(soup))
    if renderer is not None:
        geometry = renderer.render(url, out / "page.png")
        (out / "render.json").write_text(json.dumps(geometry, indent=1))
        meta["rendered"] = True
    (out / "meta.json").write_text(json.dumps(meta, indent=1))
    files = f", {meta['media']['ok']} media files" if localise else ""
    log(f"fetched {slug} in {time.time() - t0:.1f}s ({len(raw) // 1024} KB{files}{', rendered' if renderer else ''})")
    return out
