"""Pexels, Unsplash and Pixabay search clients for the reference pool.

All three licence their photos for reuse and name the creator on the photo
page, which is why they are the ones the pool stores (the same rule the
reference-collector follows). Results are normalised to one entry shape;
Unsplash+ premium photos are dropped (their licence is not the Unsplash
licence), and a kept Unsplash photo's download endpoint is pinged once at keep
time, as its guidelines ask.

The licence travels as a **key** from `LICENCES`, not as free text: the tier
routing in `pool.search` sends anything unknown to the widened tier, and
`attribution_required` is what `write_examples` renders into the credit line.

Requests cost the same at any page size, so `PER_PAGE` asks each platform for
its maximum and the caller caps *candidates* instead; `page` is what the pool's
breadth-first loop walks."""

import json
import os
import urllib.parse
import urllib.request

from .apiclient import RateLimited  # noqa: F401  (re-exported: callers catch stock.RateLimited)

PLATFORMS = ("pexels", "unsplash", "pixabay")
KEYS = {"pexels": "PEXELS_API_KEY", "unsplash": "UNSPLASH_ACCESS_KEY", "pixabay": "PIXABAY_API_KEY"}
ORIENTATIONS = ("landscape", "portrait", "square", "squarish")
PER_PAGE = {"pexels": 80, "unsplash": 30, "pixabay": 200}
THUMB_PX = 640  # long side of the rendition we ask for: >= the 256 px measure and the 320 px sheet cell

# The licence a pool entry may carry. `attribution_required` drives the credit
# line; `unknown` is the routing signal for the widened (look-only) tier.
LICENCES = {
    "pexels": {"label": "Pexels licence", "attribution_required": False,
               "url": "https://www.pexels.com/license/"},
    "unsplash": {"label": "Unsplash licence", "attribution_required": False,
                 "url": "https://unsplash.com/license"},
    "pixabay": {"label": "Pixabay content licence", "attribution_required": False,
                "url": "https://pixabay.com/service/license-summary/"},
    "cc0": {"label": "CC0", "attribution_required": False,
            "url": "https://creativecommons.org/publicdomain/zero/1.0/"},
    "cc-by": {"label": "CC BY", "attribution_required": True,
              "url": "https://creativecommons.org/licenses/by/4.0/"},
    "cc-by-sa": {"label": "CC BY-SA", "attribution_required": True,
                 "url": "https://creativecommons.org/licenses/by-sa/4.0/"},
    "unknown": {"label": "unknown", "attribution_required": None, "url": ""},
}
PLATFORM_LABELS = {"pexels": "Pexels", "unsplash": "Unsplash", "pixabay": "Pixabay"}
PLATFORM_HOSTS = {"Pexels": "pexels.com", "Unsplash": "unsplash.com", "Pixabay": "pixabay.com"}


def licence_key(value):
    """The controlled key for a licence written as a key or as a label; an
    unrecognised licence is `unknown`, which routes the entry out of the pool."""
    if not value:
        return "unknown"
    v = str(value).strip().lower()
    if v in LICENCES:
        return v
    for key, meta in LICENCES.items():
        if meta["label"].lower() == v:
            return key
    return "unknown"


def attribution_required(licence):
    return LICENCES.get(licence_key(licence), LICENCES["unknown"])["attribution_required"]


def fetch_json(url, headers=None, timeout=60):
    """The unmetered fallback, kept for one-off calls and for tests; a pool run
    passes `apiclient.Client.fetch_for(platform)` instead."""
    req = urllib.request.Request(url, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as exc:
        if exc.code == 429:
            raise RateLimited(url) from exc
        raise


def key_for(platform, key=None):
    key = key or os.environ.get(KEYS[platform])
    if not key:
        raise ValueError(f"no API key: set {KEYS[platform]} in the environment")
    return key


def keys_available(platforms, keys=None, environ=None):
    """({platform: key} for those that have one, [those that do not]). A
    missing key skips its platform with a warning rather than blocking the
    whole run, which is what the eager lookup used to do."""
    environ = os.environ if environ is None else environ
    found, missing = {}, []
    for pf in platforms:
        key = (keys or {}).get(pf) or environ.get(KEYS[pf])
        if key:
            found[pf] = key
        else:
            missing.append(pf)
    return found, missing


def pexels_search(term, key, per_page=30, orientation=None, page=1, min_width=0, fetch=fetch_json):
    """https://api.pexels.com/v1/search, normalised. `src.large` is the
    smallest documented rendition at least THUMB_PX on the long side in both
    orientations (`medium` is 350 tall, so 233 wide for a portrait)."""
    q = {"query": term, "per_page": min(per_page, PER_PAGE["pexels"]), "page": max(1, int(page))}
    if orientation:
        q["orientation"] = "square" if orientation == "squarish" else orientation
    data = fetch(f"https://api.pexels.com/v1/search?{urllib.parse.urlencode(q)}", headers={"Authorization": key})
    out = []
    for ph in data.get("photos") or []:
        src = ph.get("src") or {}
        out.append({"id": f"pexels-{ph['id']}", "url": ph.get("url", ""), "image": src.get("original", ""),
                    "thumb": src.get("large", "") or src.get("medium", ""),
                    "creator": ph.get("photographer", ""), "creator_url": ph.get("photographer_url", ""),
                    "platform": "Pexels", "licence": "pexels", "attribution_required": False,
                    "width": ph.get("width"), "height": ph.get("height")})
    return out


def unsplash_thumb(urls):
    """Unsplash serves through imgix, so the eval copy is a resize of `raw`
    with the ixid kept (their guideline) rather than the 1080 px `regular`."""
    raw = urls.get("raw") or ""
    if raw:
        sep = "&" if "?" in raw else "?"
        return f"{raw}{sep}w={THUMB_PX}&h={THUMB_PX}&fit=max&q=75&fm=jpg"
    return urls.get("small", "") or urls.get("regular", "")


def unsplash_search(term, key, per_page=15, orientation=None, page=1, min_width=0, fetch=fetch_json):
    """https://api.unsplash.com/search/photos, normalised; Unsplash+ hosts
    (plus.unsplash.com) are premium, not the Unsplash licence, and dropped."""
    q = {"query": term, "per_page": min(per_page, PER_PAGE["unsplash"]), "page": max(1, int(page))}
    if orientation:
        q["orientation"] = "squarish" if orientation == "square" else orientation
    data = fetch(f"https://api.unsplash.com/search/photos?{urllib.parse.urlencode(q)}",
                 headers={"Authorization": f"Client-ID {key}", "Accept-Version": "v1"})
    out = []
    for ph in data.get("results") or []:
        urls = ph.get("urls") or {}
        if "plus.unsplash.com" in (urls.get("raw") or urls.get("full") or ""):
            continue
        user, links = ph.get("user") or {}, ph.get("links") or {}
        out.append({"id": f"unsplash-{ph['id']}", "url": links.get("html", ""), "image": urls.get("full", ""),
                    "thumb": unsplash_thumb(urls),
                    "creator": user.get("name", ""), "creator_url": (user.get("links") or {}).get("html", ""),
                    "platform": "Unsplash", "licence": "unsplash", "attribution_required": False,
                    "width": ph.get("width"), "height": ph.get("height"),
                    "download_location": links.get("download_location", "")})
    return out


def pixabay_search(term, key, per_page=200, orientation=None, page=1, min_width=0, fetch=fetch_json):
    """https://pixabay.com/api/, normalised. The key travels in the query, so
    the ledger strips it from every cache key and log line. `webformatURL` is
    the 640 px rendition: `previewURL` is 150 px and `largeImageURL` is closer
    to the systematic downloading their terms forbid."""
    q = {"key": key, "q": term[:100], "image_type": "photo", "safesearch": "true",
         "per_page": min(max(per_page, 3), PER_PAGE["pixabay"]), "page": max(1, int(page))}
    if min_width:
        q["min_width"] = int(min_width)
    if orientation in ("landscape", "portrait"):
        q["orientation"] = "horizontal" if orientation == "landscape" else "vertical"
    data = fetch(f"https://pixabay.com/api/?{urllib.parse.urlencode(q)}")
    out = []
    for h in data.get("hits") or []:
        user, uid = h.get("user", ""), h.get("user_id", "")
        out.append({"id": f"pixabay-{h['id']}", "url": h.get("pageURL", ""),
                    "image": h.get("largeImageURL", "") or h.get("webformatURL", ""),
                    "thumb": h.get("webformatURL", ""),
                    "creator": user, "creator_url": f"https://pixabay.com/users/{user}-{uid}/" if uid else "",
                    "platform": "Pixabay", "licence": "pixabay", "attribution_required": False,
                    "width": h.get("imageWidth"), "height": h.get("imageHeight")})
    return out


def unsplash_track_download(download_location, key, fetch=fetch_json):
    """Ping a kept photo's download endpoint once (the Unsplash guideline)."""
    fetch(download_location, headers={"Authorization": f"Client-ID {key}", "Accept-Version": "v1"})


VIDEO_MIN_PX = 720  # the rendition a pool clip is read at: a 3-frame strip needs no more


def _rendition(files, min_px=VIDEO_MIN_PX):
    """The smallest rendition at least min_px wide, else the largest there is."""
    wide = sorted((f for f in files if (f.get("width") or 0) >= min_px), key=lambda f: f.get("width") or 0)
    if wide:
        return wide[0]
    return max(files, key=lambda f: f.get("width") or 0) if files else {}


def pexels_video_search(term, key, per_page=30, orientation=None, page=1, min_width=0, fetch=fetch_json):
    """https://api.pexels.com/videos/search, normalised to the pool shape plus
    `kind: video`, `video` (the mp4 rendition) and `duration`; `image`/`thumb`
    is the platform's poster, which stands in for the still downstream."""
    q = {"query": term, "per_page": min(per_page, PER_PAGE["pexels"]), "page": max(1, int(page))}
    if orientation:
        q["orientation"] = "square" if orientation == "squarish" else orientation
    data = fetch(f"https://api.pexels.com/videos/search?{urllib.parse.urlencode(q)}", headers={"Authorization": key})
    out = []
    for v in data.get("videos") or []:
        user = v.get("user") or {}
        files = [f for f in v.get("video_files") or [] if (f.get("file_type") or "").endswith("mp4")]
        r = _rendition(files)
        out.append({"id": f"pexels-v{v['id']}", "url": v.get("url", ""), "image": v.get("image", ""),
                    "thumb": v.get("image", ""), "video": r.get("link", ""), "duration": v.get("duration"),
                    "kind": "video", "creator": user.get("name", ""), "creator_url": user.get("url", ""),
                    "platform": "Pexels", "licence": "pexels", "attribution_required": False,
                    "width": v.get("width"), "height": v.get("height")})
    return out


def pixabay_video_search(term, key, per_page=200, orientation=None, page=1, min_width=0, fetch=fetch_json):
    """https://pixabay.com/api/videos/, normalised like `pexels_video_search`.
    Pixabay's video API has no orientation filter; the pool's aspect prefilter
    does that work after."""
    q = {"key": key, "q": term[:100], "safesearch": "true",
         "per_page": min(max(per_page, 3), PER_PAGE["pixabay"]), "page": max(1, int(page))}
    if min_width:
        q["min_width"] = int(min_width)
    data = fetch(f"https://pixabay.com/api/videos/?{urllib.parse.urlencode(q)}")
    out = []
    for h in data.get("hits") or []:
        vids = h.get("videos") or {}
        r = _rendition([dict(v, link=v.get("url")) for v in vids.values() if v.get("url")])
        big = vids.get("large") or vids.get("medium") or {}
        user, uid = h.get("user", ""), h.get("user_id", "")
        out.append({"id": f"pixabay-v{h['id']}", "url": h.get("pageURL", ""), "image": r.get("thumbnail", ""),
                    "thumb": r.get("thumbnail", ""), "video": r.get("link", ""), "duration": h.get("duration"),
                    "kind": "video", "creator": user,
                    "creator_url": f"https://pixabay.com/users/{user}-{uid}/" if uid else "",
                    "platform": "Pixabay", "licence": "pixabay", "attribution_required": False,
                    "width": big.get("width"), "height": big.get("height")})
    return out


SEARCH = {"pexels": pexels_search, "unsplash": unsplash_search, "pixabay": pixabay_search}
# `pool search --kind video`: Unsplash has no video API, so it is skipped there.
SEARCH_VIDEO = {"pexels": pexels_video_search, "pixabay": pixabay_video_search}
