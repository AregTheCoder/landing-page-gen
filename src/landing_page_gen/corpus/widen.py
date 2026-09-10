"""Widen a family's look-corpus by reverse image search.

The corpus is Picsart's own pages (layout, chrome) and `corpus/references/`
is licensed stock that matches their photography. Between the two sits what a
Google Lens search on a corpus image finds: the same photograph on its stock
page (provenance) and the visual neighbours the web already holds of that
look. `widen` runs that search for every tagged asset of a family, through a
Lens wrapper (SerpApi `google_lens`) or Google Cloud Vision web detection,
and writes `corpus/widened/<family>.yaml`; `pick` serves neighbours to
`similar --widen` as extra example images for a brief. Widened images are
look references only: never uploaded, never passed as `imageUrls`, never
injected — their licence is unknown until the page is a Pexels or Unsplash
page, at which point the reference-collector's format applies."""

import datetime as dt
import json
import os
import urllib.parse
import urllib.request
from pathlib import Path

import yaml

from .attrs import asset_id

WIDENED_DIR = Path("corpus/widened")
BACKENDS = ("serpapi-lens", "vision-web")
KEYS = {"serpapi-lens": "SERPAPI_KEY", "vision-web": "GOOGLE_VISION_API_KEY"}
OWN_HOSTS = ("picsart.com", "picsart.io")  # a neighbour on our own site is the corpus, not a widening


def fetch_json(url, data=None, timeout=60):
    req = urllib.request.Request(url, data=json.dumps(data).encode() if data is not None else None,
                                 headers={"Content-Type": "application/json"} if data is not None else {})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def lens_matches(image_url, key, exact=False, fetch=fetch_json):
    """SerpApi `google_lens`: visual_matches (or exact_matches) as
    {title, page, image, thumbnail, source}."""
    q = urllib.parse.urlencode({"engine": "google_lens", "url": image_url,
                                "type": "exact_matches" if exact else "visual_matches", "api_key": key})
    data = fetch(f"https://serpapi.com/search.json?{q}")
    out = []
    for m in data.get("exact_matches" if exact else "visual_matches") or []:
        out.append({"title": m.get("title", ""), "page": m.get("link", ""), "image": (m.get("image") or {}).get("link")
                    if isinstance(m.get("image"), dict) else m.get("image", ""),
                    "thumbnail": (m.get("thumbnail") or {}).get("link") if isinstance(m.get("thumbnail"), dict) else m.get("thumbnail", ""),
                    "source": m.get("source", "")})
    return out


def vision_matches(image_url, key, exact=False, fetch=fetch_json, max_results=20):
    """Google Cloud Vision WEB_DETECTION: visuallySimilarImages, or for exact
    the fullMatchingImages with their pagesWithMatchingImages."""
    body = {"requests": [{"image": {"source": {"imageUri": image_url}},
                          "features": [{"type": "WEB_DETECTION", "maxResults": max_results}]}]}
    data = fetch(f"https://vision.googleapis.com/v1/images:annotate?key={key}", body)
    web = ((data.get("responses") or [{}])[0].get("webDetection")) or {}
    out = []
    if exact:
        pages = web.get("pagesWithMatchingImages") or []
        for i, m in enumerate(web.get("fullMatchingImages") or []):
            page = pages[i] if i < len(pages) else {}
            out.append({"title": page.get("pageTitle", ""), "page": page.get("url", ""), "image": m.get("url", ""),
                        "thumbnail": "", "source": urllib.parse.urlsplit(page.get("url", "")).netloc})
    else:
        for m in web.get("visuallySimilarImages") or []:
            out.append({"title": "", "page": "", "image": m.get("url", ""), "thumbnail": "",
                        "source": urllib.parse.urlsplit(m.get("url", "")).netloc})
    return out


SEARCH = {"serpapi-lens": lens_matches, "vision-web": vision_matches}


def own(url):
    host = urllib.parse.urlsplit(url or "").netloc.lower()
    return any(host == h or host.endswith("." + h) for h in OWN_HOSTS)


def family_assets(styles, family, limit=None):
    """(asset id, CDN src) of every corpus asset tagged with the family."""
    rows = [(asset_id(src), src) for src, rec in sorted(styles.items()) if (rec or {}).get("style") == family]
    return rows[:limit] if limit else rows


def load(path):
    path = Path(path)
    return (yaml.safe_load(path.read_text()) or {}) if path.exists() else {}


def widen(family, styles, backend="serpapi-lens", key=None, limit=None, exact=False, out_dir=WIDENED_DIR,
          fetch=fetch_json, log=print):
    """Search every asset of the family once (assets already in the yaml are
    kept, not re-searched) and merge the neighbours into
    `<out_dir>/<family>.yaml`. Returns (path, assets searched, matches added)."""
    if backend not in BACKENDS:
        raise ValueError(f"backend {backend!r}; one of {', '.join(BACKENDS)}")
    key = key or os.environ.get(KEYS[backend])
    if not key:
        raise ValueError(f"no API key: set {KEYS[backend]} in the environment")
    path = Path(out_dir) / f"{family}.yaml"
    data = load(path) or {"family": family, "assets": {}}
    section = "exact" if exact else "visual"
    searched = added = 0
    for aid, src in family_assets(styles, family, limit):
        rec = data["assets"].setdefault(aid, {"src": src})
        if section in rec:
            continue
        matches = [m for m in SEARCH[backend](src, key, exact=exact, fetch=fetch) if m.get("image") or m.get("page")]
        matches = [m for m in matches if not own(m.get("page")) and not own(m.get("image"))]
        seen, kept = set(), []
        for m in matches:
            k = m.get("image") or m.get("page")
            if k not in seen:
                seen.add(k)
                kept.append(m)
        rec[section] = {"backend": backend, "at": dt.date.today().isoformat(), "matches": kept}
        searched += 1
        added += len(kept)
        log(f"  {aid}: {len(kept)} {section} match(es)")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True, width=1000))
    return path, searched, added


def pick(family, k, exclude_asset=(), path=None):
    """Up to k visual neighbours for a brief, round-robin over the family's
    source assets so one asset does not fill the set; never one whose page or
    image names an excluded asset id (the page's own pictures on other sites)."""
    data = load(path or WIDENED_DIR / f"{family}.yaml")
    ids = [i for i in (exclude_asset or [])]
    queues = []
    for aid, rec in (data.get("assets") or {}).items():
        ms = [dict(m, from_asset=aid) for m in (rec.get("visual") or {}).get("matches") or []
              if not any(i in (m.get("page") or "") or i in (m.get("image") or "") for i in ids)]
        if ms:
            queues.append(ms)
    out, seen = [], set()
    while queues and len(out) < k:
        for q in list(queues):
            m = q.pop(0)
            if m["image"] not in seen:
                seen.add(m["image"])
                out.append(m)
                if len(out) == k:
                    break
            if not q:
                queues.remove(q)
    return out


def write_examples(matches, out_dir, download, to_png, log=print, start=1):
    """One `w<n>-widened.md` plus PNG per neighbour, beside the corpus
    excerpts; the md says where it came from and that it is a look reference."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for n, m in enumerate(matches, start):
        stem = f"w{n}-widened"
        dest = out_dir / f"{stem}.png"
        try:
            tmp = dest.with_suffix(".bin")
            download(m["image"], tmp)
            to_png(tmp)
        except Exception as exc:  # a dead neighbour is not fatal
            log(f"  could not fetch {m['image']}: {exc}")
            continue
        md = out_dir / f"{stem}.md"
        md.write_text("\n".join([
            "---", "origin: widened", f"from_asset: {m.get('from_asset', '')}", f"source: {m.get('source', '')}",
            f"page: {m.get('page', '')}", f"title: {m.get('title', '')!r}", f"local: {dest.name}", "---", "",
            "A visual neighbour of a corpus asset of this family, found by reverse image search. Look reference",
            "only: read it for finish, light, subject genre and framing. Its licence is unknown, so it is never",
            "uploaded, passed as `imageUrls`, or injected; Picsart's chrome and ground still come from the family block.", ""]))
        written.append(md)
        log(f"  {md.name}: from {m.get('source') or m.get('page') or m['image']}")
    return written
