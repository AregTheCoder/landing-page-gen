"""Split a page snapshot into typed sections, stamp every text node and media
node with a `data-lp*` id, and index the result in the corpus DB.

Section = one non-empty direct child of <main> (plus the body-level <aside>
link chips and the <footer>). Type = heuristics over headings, media, links
and buttons; roles = heuristics over alt text and rendered size. Both are
starting points for the hand-edited skeleton, not ground truth."""

import json
import math
import re
import urllib.parse
from collections import defaultdict, deque
from pathlib import Path

from bs4 import BeautifulSoup, Comment, NavigableString

from . import db

HEADINGS = ("h1", "h2", "h3", "h4", "h5", "h6")
TEXT_TAGS = set(HEADINGS) | {"p", "li", "button", "blockquote", "figcaption", "dt", "dd", "th", "td", "label"}
INLINE = {"a", "span", "strong", "em", "b", "i", "u", "br", "sup", "sub", "code", "mark", "small", "label", "time", "abbr"}
IGNORE = {"script", "style", "svg", "template", "noscript", "iframe", "source"}
RESPONSIVE_SHOW = re.compile(r"^(sm|md|lg|xl|2xl):(block|flex|grid|inline|inline-block|inline-flex|contents|table)$")
RESPONSIVE_HIDE = re.compile(r"^(sm|md|lg|xl|2xl):hidden$")
DECORATIVE = re.compile(r"\b(decorations?|badges?|logos?|icons?|avatars?|flags?)\b", re.I)
UI_WORDS = re.compile(r"inside picsart|built-in tools?|how .* works|interface|editor|screenshot|dashboard|\bui\b", re.I)
COMMON_ASPECTS = [(16, 9), (4, 3), (3, 2), (1, 1), (9, 16), (3, 4), (2, 3), (21, 9), (4, 5), (5, 4)]
MAX_TEXTS_IN_MD = 80
# The CMS components label their roots (data-testid, data-pulse-section-group);
# where a label is present it beats the structural heuristics below.
LABEL_TYPES = (
    (re.compile(r"faq"), "faq"),
    (re.compile(r"pricing"), "pricing"),
    (re.compile(r"testimonial"), "testimonial"),
    (re.compile(r"how-?it-?works|how-?to", re.I), "how-it-works"),
    (re.compile(r"tutorials"), "tutorial-grid"),
    (re.compile(r"blog"), "resource-links"),
    (re.compile(r"more-tools-to-explore|latest-ai-models|relevant-links"), "link-grid"),
    (re.compile(r"use-cases|content-creation"), "use-case-grid"),
    (re.compile(r"value-itemisation"), "feature-row"),
    (re.compile(r"feature-section|comparison-table"), "feature-list"),
    (re.compile(r"prompt-box"), "interactive-demo"),
    (re.compile(r"rating"), "cta-band"),
    (re.compile(r"promotional-component"), "gallery"),
    (re.compile(r"banner-block|create-your-way"), "feature-callout"),
    (re.compile(r"^footer"), "footer"),
)
GENERIC_LABELS = {"container", "heading-title", "horizontal-container", "cards-section-title"}


# ---------- helpers ----------

def cdn_url(src, base="https://picsart.com/"):
    """Resolve the Next.js image proxy (or a relative path) to the asset URL."""
    if not src:
        return ""
    url = urllib.parse.urljoin(base, src)
    parts = urllib.parse.urlsplit(url)
    if parts.path.rstrip("/").endswith("/_next/image"):
        inner = urllib.parse.parse_qs(parts.query).get("url")
        if inner:
            return inner[0]
    return url


def aspect_of(w, h):
    if not w or not h:
        return None
    for a, b in COMMON_ASPECTS:
        if abs(w / h - a / b) / (a / b) < 0.03:
            return f"{a}:{b}"
    g = math.gcd(int(w), int(h))
    return f"{int(w) // g}:{int(h) // g}"


def hidden_by_class(el):
    classes = el.get("class") or []
    if "sr-only" in classes:
        return True
    if any(RESPONSIVE_HIDE.match(c) for c in classes):
        return True
    return "hidden" in classes and not any(RESPONSIVE_SHOW.match(c) for c in classes)


def is_hidden(el):
    if el.has_attr("hidden") or el.get("aria-hidden") == "true":
        return True
    return hidden_by_class(el)


def own_text(el):
    return any(type(s) is NavigableString and s.strip() for s in el.contents)


def is_text_leaf(el):
    if el.name in TEXT_TAGS:
        return el.find(list(TEXT_TAGS)) is None and bool(el.get_text(strip=True))
    if own_text(el):
        return True
    kids = [k for k in el.find_all(recursive=False) if k.name not in IGNORE]
    return bool(kids) and all(k.name in INLINE for k in kids) and bool(el.get_text(strip=True))


def clean_text(s):
    return re.sub(r"\s+", " ", s).strip()


def strip_stamps(soup):
    for el in soup.find_all(attrs={"data-lp": True}):
        del el["data-lp"]
    for el in soup.find_all(attrs={"data-lp-t": True}):
        del el["data-lp-t"]
    for el in soup.find_all(attrs={"data-lp-section": True}):
        del el["data-lp-section"]


# ---------- splitting ----------

def content_children(el):
    out = []
    for ch in el.find_all(recursive=False):
        if ch.name in IGNORE or ch.name in ("hr", "br"):
            continue
        if ch.name == "nav" and "breadcrumb" in (ch.get("aria-label") or "").lower():
            continue
        if not ch.get_text(strip=True) and ch.find(["img", "video"]) is None:
            continue
        out.append(ch)
    return out


def split_sections(soup):
    """Section roots in page order."""
    main = soup.find("main") or soup.body
    roots = content_children(main)
    while len(roots) == 1 and roots[0].name in ("div", "section") and len(content_children(roots[0])) >= 3:
        roots = content_children(roots[0])
    for tag in ("aside", "footer"):
        for el in soup.find_all(tag):
            if el.find_parent("main") is None and el.find_parent(("header", "footer", "aside")) is None:
                roots.append(el)
    return roots


# ---------- walking one section ----------

def walk(root):
    """Yield ('text', el) and ('media', el) items in document order, skipping
    hidden branches, icons drawn as SVG, and nested text once a leaf is found."""
    def rec(el):
        for ch in el.children:
            if isinstance(ch, NavigableString):
                continue
            if ch.name in IGNORE or is_hidden(ch):
                continue
            if ch.name in ("img", "video"):
                yield "media", ch
                continue
            if is_text_leaf(ch):
                if ch.find(["img", "video"]) is not None:
                    yield from (("media", m) for m in ch.find_all(["img", "video"]))
                yield "text", ch
                continue
            yield from rec(ch)
    yield from rec(root)


def media_src(el):
    if el.name == "video":
        src = el.get("src") or next((s.get("src") for s in el.find_all("source") if s.get("src")), "")
    else:
        src = el.get("src") or el.get("data-src") or ""
    return src


def source_attr(el):
    """The src as the site served it: kept in data-lp-src once media.py has
    pointed src at a local copy. Keys render.json geometry and the CDN URL."""
    return el.get("data-lp-src") or media_src(el)


def local_src(el):
    src = media_src(el)
    return src if src.startswith("media/") else None


def media_role(el, kind, alt, w, h, section_type, root):
    """Roles are a first guess for the hand-edited skeleton. Order matters:
    size before words (a 40px "logo" is an icon), thumbnail sections before
    words (a tutorial card about logos is still a thumbnail)."""
    if root.name in ("footer", "header"):
        return "icon"
    if w and h and max(w, h) <= 120:
        return "icon"
    if section_type in ("resource-links", "tutorial-grid", "link-grid"):
        return "thumbnail"
    if DECORATIVE.search(alt or ""):
        return "decorative"
    headline = (root.find(HEADINGS).get_text(" ", strip=True) if root.find(HEADINGS) else "")
    if UI_WORDS.search(alt or "") or (kind == "video" and (UI_WORDS.search(headline) or section_type == "how-it-works")):
        return "ui-screenshot"
    return "creative"


def section_labels(root):
    """Component labels on the root or just below it, data-testid first."""
    els = [root] + root.find_all(True, limit=8)
    out = []
    for attr in ("data-testid", "data-pulse-section-group"):
        for el in els:
            v = (el.get(attr) or "").lower()
            if v and v not in GENERIC_LABELS and v not in out:
                out.append(v)
    return out


def type_from_labels(labels):
    for label in labels:
        for rx, stype in LABEL_TYPES:
            if rx.search(label):
                return stype
    return None


def classify(root, idx, texts, media, links, buttons):
    """Section type: hero by position, then component labels, then
    structural heuristics. `media` are the visible non-icon nodes."""
    if root.name == "footer":
        return "footer"
    if root.name == "aside":
        return "link-grid"
    if idx == 0 or root.find("h1") is not None:
        return "hero"
    labelled = type_from_labels(section_labels(root))
    if labelled:
        return labelled
    heads = [{"tag": h.name, "text": clean_text(h.get_text(" "))} for h in root.find_all(HEADINGS)]
    heads = [h for h in heads if h["text"]]
    headline = heads[0]["text"].lower() if heads else ""
    hl = " ".join(h["text"].lower() for h in heads)
    text_len = sum(len(t["text"]) for t in texts)
    n_media = len(media)
    if "faq" in hl or "frequently asked" in hl:
        return "faq"
    h2s = {h["text"].lower() for h in heads if h["tag"] == "h2"}
    if {"pro", "ultra"} <= h2s or "/month" in " ".join(t["text"].lower() for t in texts):
        return "pricing"
    if re.search(r"testimonial|review", hl) or root.find(class_=re.compile("testimonial", re.I)) is not None:
        return "testimonial"
    if not heads and len(buttons) >= 6 and text_len < 300:
        return "interactive-demo"
    blog = sum(1 for h in links if "/blog/" in h)
    tuts = sum(1 for h in links if "/tutorials/" in h)
    if tuts >= 2:
        return "tutorial-grid"
    if blog >= 2:
        return "resource-links"
    tablist = root.find(attrs={"role": "tablist"})
    step_buttons = [b for b in buttons if re.match(r"step \d", (b.get("aria-label") or "").lower())]
    if step_buttons or headline.startswith("how to") or (tablist is not None and "step" in (tablist.get("aria-label") or "").lower()):
        return "how-it-works"
    if tablist is not None or len([b for b in buttons if len(clean_text(b.get_text())) > 1]) >= 4 and n_media:
        return "use-case-grid" if n_media else "feature-row"
    if len(links) >= 12 and not n_media:
        return "link-grid"
    # cards: a link wrapping an image and a title, to distinct destinations
    cards = [a for a in root.find_all("a", href=True)
             if a.find(["img", "video"]) is not None and a.find(("h3", "h4")) is not None]
    if n_media >= 3 and len({a["href"] for a in cards}) >= 3:
        return "link-grid"
    if n_media >= 4 and text_len / n_media < 150:
        return "gallery"
    if n_media >= 3:
        return "use-case-grid"
    if n_media:
        return "feature-callout"
    if text_len < 250 and (links or buttons):
        return "cta-band"
    if len(heads) >= 3 and text_len <= 600:
        return "feature-row"
    return "feature-list"


def geometry_index(render):
    """(tag, src attribute) -> deque of geometry rows, in document order."""
    idx = defaultdict(deque)
    for g in render or []:
        idx[(g["tag"], g.get("src_attr") or "")].append(g)
    return idx


def build_section(root, idx, sid, geo):
    items = list(walk(root))
    texts, media_nodes = [], []
    seen_src = set()
    for kind, el in items:
        if kind == "text":
            text = clean_text(el.get_text(" "))
            if not text:
                continue
            href = el.get("href") if el.name == "a" else None
            texts.append({"el": el, "tag": el.name, "text": text, "href": href})
        else:
            src_attr = source_attr(el)
            src = cdn_url(src_attr)
            if not src or src in seen_src:
                continue
            g = geo[(el.name, src_attr)].popleft() if geo.get((el.name, src_attr)) else None
            if g is not None and (g["w"] == 0 or g["h"] == 0):
                continue  # not displayed at desktop width
            w = g["w"] if g else _int(el.get("width"))
            h = g["h"] if g else _int(el.get("height"))
            seen_src.add(src)
            media_nodes.append({
                "el": el, "kind": "video" if el.name == "video" else "image", "src": src,
                "alt": clean_text(el.get("alt") or ""), "width": w, "height": h,
                "nat_width": g["nat_w"] if g else _int(el.get("width")),
                "nat_height": g["nat_h"] if g else _int(el.get("height")),
                "duration": g["duration"] if g else None,
                "local": local_src(el),
            })
    links = [a.get("href") or "" for a in root.find_all("a", href=True)]
    buttons = [b for b in root.find_all("button") if not is_hidden(b)]
    # icons don't count as media for typing
    sized = [m for m in media_nodes if not (m["width"] and m["height"] and max(m["width"], m["height"]) <= 120)]
    stype = classify(root, idx, texts, sized, links, buttons)
    for m in media_nodes:
        m["role"] = media_role(m["el"], m["kind"], m["alt"], m["width"], m["height"], stype, root)
        m["aspect"] = aspect_of(m["width"], m["height"])
    # stamp
    root["data-lp-section"] = sid
    for n, t in enumerate(texts, 1):
        t["tid"] = f"{sid}-t{n}"
        t["el"]["data-lp-t"] = t["tid"]
    for n, m in enumerate(media_nodes, 1):
        m["slot_id"] = f"{sid}-m{n}"
        m["el"]["data-lp"] = m["slot_id"]
    heads = [t for t in texts if t["tag"] in HEADINGS]
    headline = heads[0]["text"] if heads else (texts[0]["text"] if texts else "")
    md = to_markdown(sid, stype, headline, items, texts, media_nodes)
    return {
        "sid": sid, "idx": idx, "type": stype, "headline": headline, "md": md,
        "text_len": sum(len(t["text"]) for t in texts), "media_count": len(media_nodes),
        "selector": f'[data-lp-section="{sid}"]', "texts": texts, "media": media_nodes,
    }


def _int(v):
    try:
        return int(float(v)) if v not in (None, "") else None
    except ValueError:
        return None


def to_markdown(sid, stype, headline, items, texts, media):
    by_el = {id(t["el"]): t for t in texts}
    by_el.update({id(m["el"]): m for m in media})
    lines = [f"## {sid} {stype}", ""]
    n = 0
    for kind, el in items:
        rec = by_el.get(id(el))
        if rec is None:
            continue
        if kind == "media":
            label = "video" if rec["kind"] == "video" else "image"
            size = f" {rec['width']}x{rec['height']}" if rec.get("width") and rec.get("height") else ""
            lines.append(f"![{label} {rec['role']}{size}: {rec['alt']}]({rec['src']})")
            continue
        n += 1
        if n > MAX_TEXTS_IN_MD:
            continue
        tag, text = rec["tag"], rec["text"]
        if tag in HEADINGS:
            lines.append("#" * min(int(tag[1]) + 1, 6) + " " + text)
        elif tag == "li":
            lines.append(f"- {text}")
        elif tag == "button":
            lines.append(f"[button: {text}]")
        elif tag == "a" or rec.get("href"):
            lines.append(f"[{text}]({rec.get('href') or ''})")
        else:
            lines.append(text)
    if n > MAX_TEXTS_IN_MD:
        lines.append(f"... ({n - MAX_TEXTS_IN_MD} more text nodes)")
    return "\n".join(lines).strip() + "\n"


# ---------- page level ----------

def sectionize_html(html, render=None):
    """Return (soup with stamps, [section dicts])."""
    soup = BeautifulSoup(html, "html.parser")
    strip_stamps(soup)
    geo = geometry_index(render)
    sections = []
    for i, root in enumerate(split_sections(soup)):
        sections.append(build_section(root, i, f"S{i + 1:02d}", geo))
    return soup, sections


def sectionize_page(page_dir, con, log=print):
    """Index corpus/pages/<slug>/ into the DB and rewrite page.html with stamps."""
    page_dir = Path(page_dir)
    meta = json.loads((page_dir / "meta.json").read_text())
    render_path = page_dir / "render.json"
    render = json.loads(render_path.read_text()) if render_path.exists() else None
    soup, sections = sectionize_html((page_dir / "page.html").read_text(), render)
    (page_dir / "page.html").write_text(str(soup))
    (page_dir / "sections.md").write_text(
        f"# {meta['title']}\n\n<{meta['url']}>\n\n" + "\n".join(s["md"] for s in sections))
    slug = meta["slug"]
    db.delete_page(con, slug)
    cur = con.execute(
        "INSERT INTO pages(slug, url, family, title, fetched_at, html_path, screenshot_path) VALUES (?,?,?,?,?,?,?)",
        (slug, meta["url"], meta.get("family"), meta.get("title"), meta["fetched_at"],
         str(page_dir / "page.html"), str(page_dir / "page.png") if (page_dir / "page.png").exists() else None))
    page_id = cur.lastrowid
    for s in sections:
        cur = con.execute(
            "INSERT INTO sections(page_id, sid, idx, type, headline, md, text_len, media_count, selector) VALUES (?,?,?,?,?,?,?,?,?)",
            (page_id, s["sid"], s["idx"], s["type"], s["headline"], s["md"], s["text_len"], s["media_count"], s["selector"]))
        section_id = cur.lastrowid
        con.executemany(
            "INSERT INTO texts(section_id, tid, tag, text, href, selector) VALUES (?,?,?,?,?,?)",
            [(section_id, t["tid"], t["tag"], t["text"], t["href"], f'[data-lp-t="{t["tid"]}"]') for t in s["texts"]])
        con.executemany(
            "INSERT INTO media(section_id, slot_id, kind, role, src, alt, width, height, aspect, nat_width, nat_height, duration, local_path, selector) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            [(section_id, m["slot_id"], m["kind"], m["role"], m["src"], m["alt"], m["width"], m["height"], m["aspect"],
              m["nat_width"], m["nat_height"], m["duration"], str(page_dir / m["local"]) if m["local"] else None,
              f'[data-lp="{m["slot_id"]}"]') for m in s["media"]])
    con.commit()
    log(f"{slug}: {len(sections)} sections, {sum(s['media_count'] for s in sections)} media")
    for s in sections:
        roles = ",".join(sorted({m["role"] for m in s["media"]})) or "-"
        log(f"  {s['sid']} {s['type']:<16} media={s['media_count']:<2} [{roles}] {s['headline'][:60]}")
    return sections
