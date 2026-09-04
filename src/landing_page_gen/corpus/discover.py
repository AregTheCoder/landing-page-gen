"""Discover Picsart landing pages by crawling internal links from hub pages.

The pages are server-rendered, so plain HTTP is enough here. Only landing-page
families are expanded (hubs, ai-models, compare-models, tool pages); anything
else is recorded once and not followed."""

import re
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor

from bs4 import BeautifulSoup

HOST = "https://picsart.com"
UA = "Mozilla/5.0 (Macintosh) lp-corpus/0.1"
SEEDS = ("/", "/ai-models/", "/compare-models/", "/ai-image-generator/",
         "/ai-video-generator/", "/comic-book-generator/", "/persona/")
SKIP_PREFIXES = ("/blog", "/create", "/hashtag", "/u/", "/i/", "/webmobile",
                 "/ai-playground", "/subscribe", "/login", "/reset", "/survey",
                 "/legal", "/privacy", "/terms", "/careers", "/press", "/help",
                 "/templates", "/stickers", "/fonts", "/backgrounds", "/tags",
                 "/pricing", "/discover", "/gold", "/about", "/sitemap", "/api",
                 "/status", "/download", "/apps", "/enterprise", "/business",
                 "/company", "/team", "/cookie", "/contact", "/newsroom", "/accessibility-statement",
                 "/community-guidelines", "/copyright-dispute-policy", "/security-policy",
                 "/colors", "/challenges", "/earn", "/images", "/library", "/stock-videos",
                 "/tutorials", "/workflows", "/print", "/industries", "/gen-ai/")
LOCALE_RE = re.compile(r"^/[a-z]{2}(_[a-z]{2})?/")
FAMILIES = (
    ("hub", re.compile(r"^/(ai-models|compare-models|image-models|video-models|audio-models|"
                        r"ai-tools|ai-design-tools|design-tools|video-tools|video-toolkit|image-tools|"
                        r"background-tools)/$")),
    ("ai-models", re.compile(r"^/ai-models/[a-z0-9-]+/$")),
    ("compare-models", re.compile(r"^/compare-models/[a-z0-9-]+/$")),
    ("tool", re.compile(r"^/[a-z0-9-]+-(generator|editor|remover|enhancer|maker|changer|"
                        r"upscaler|eraser|converter|creator|resizer|cropper|filters?|effects?|"
                        r"studio|swap|blur|cutout|cleanup|restoration|colorizer|animator)/$")),
    ("ai-tool", re.compile(r"^/ai-[a-z0-9-]+/$")),
    ("other", re.compile(r"^/[a-z0-9-]+/$")),
)
EXPAND = {"hub", "ai-models", "compare-models", "tool", "ai-tool"}


def normalize(href, base=HOST):
    """Absolute picsart.com path with trailing slash and no query, or None."""
    if not href or href.startswith(("mailto:", "tel:", "javascript:", "#")):
        return None
    url = urllib.parse.urljoin(base, href)
    parts = urllib.parse.urlsplit(url)
    if parts.netloc not in ("picsart.com", "www.picsart.com") or parts.query:
        return None
    path = parts.path or "/"
    if not path.endswith("/"):
        path += "/"
    if path != "/" and (LOCALE_RE.match(path) or path.startswith(SKIP_PREFIXES)):
        return None
    return path


def classify(path):
    for family, rx in FAMILIES:
        if rx.match(path):
            return family
    return None


def fetch(path, timeout=25):
    req = urllib.request.Request(HOST + path, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", errors="ignore")


def parse(html):
    soup = BeautifulSoup(html, "html.parser")
    title = soup.title.get_text(strip=True) if soup.title else ""
    links = {normalize(a.get("href")) for a in soup.find_all("a", href=True)}
    return title, {l for l in links if l}


def crawl(seeds=SEEDS, depth=2, limit=300, workers=4, delay=0.2, log=print):
    """BFS over landing-page links. Returns {path: {family, title, from}}."""
    pages = {}
    frontier = {s: "seed" for s in seeds}
    for level in range(depth + 1):
        todo = [p for p in frontier if p not in pages][: max(0, limit - len(pages))]
        if not todo:
            break
        log(f"level {level}: fetching {len(todo)} pages")
        with ThreadPoolExecutor(workers) as pool:
            results = list(pool.map(_safe_fetch_parse, todo))
        next_frontier = {}
        for path, (title, links) in zip(todo, results):
            family = classify(path) or ("hub" if path == "/" else None)
            pages[path] = {"family": family, "title": title, "from": frontier[path]}
            if family in EXPAND or path == "/":
                for l in links:
                    if l not in pages and l not in frontier and classify(l):
                        next_frontier[l] = path
            time.sleep(delay)
        frontier = next_frontier
    return pages


def _safe_fetch_parse(path):
    try:
        return parse(fetch(path))
    except Exception as exc:  # network errors are data here, not crashes
        return f"ERROR {exc}", set()
