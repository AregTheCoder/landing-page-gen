"""Find the k closest sections of one type across the corpus and write them as
example excerpts (Markdown plus downloaded media) for a worker's brief."""

import re
import shutil
import urllib.parse
import urllib.request
from pathlib import Path

from . import db

STOP = {"the", "and", "for", "with", "your", "you", "from", "that", "this", "are", "can", "any", "all",
        "into", "one", "our", "how", "what", "use", "get", "more", "make", "made", "new", "just", "every"}
UA = "Mozilla/5.0 (Macintosh) lp-corpus/0.1"


def fts_query(query, limit=40):
    tokens = []
    for t in re.findall(r"[A-Za-z0-9]+", query):
        tl = t.lower()
        if len(tl) > 2 and tl not in STOP and tl not in tokens:
            tokens.append(tl)
    return " OR ".join(f'"{t}"' for t in tokens[:limit])


def find_similar(con, type_, query, k=3, exclude=None, need_media=True):
    """Top-k sections of `type_` by BM25, at most one per page, from pages
    other than `exclude`; with need_media only sections that have a
    creative/thumbnail slot."""
    match = fts_query(query)
    media_clause = ("AND EXISTS (SELECT 1 FROM media m WHERE m.section_id = s.id AND m.role IN ('creative','thumbnail'))"
                    if need_media else "")
    if match:
        rows = con.execute(
            f"""SELECT s.*, p.slug, p.url, bm25(sections_fts) AS rank
                FROM sections_fts f JOIN sections s ON s.id = f.rowid JOIN pages p ON p.id = s.page_id
                WHERE sections_fts MATCH ? AND s.type = ? {media_clause}
                ORDER BY rank LIMIT ?""", (match, type_, k * 8)).fetchall()
    else:
        rows = []
    if len({r["slug"] for r in rows if r["slug"] != exclude}) < k:
        rows += con.execute(
            f"""SELECT s.*, p.slug, p.url, 0 AS rank FROM sections s JOIN pages p ON p.id = s.page_id
                WHERE s.type = ? {media_clause} ORDER BY s.media_count DESC, s.text_len DESC LIMIT ?""",
            (type_, k * 8)).fetchall()
    out, seen = [], set()
    for r in rows:
        if r["slug"] == exclude or r["slug"] in seen:
            continue
        seen.add(r["slug"])
        out.append(r)
        if len(out) == k:
            break
    return out


def download(url, dest, timeout=60):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r, open(dest, "wb") as f:
        shutil.copyfileobj(r, f)
    return dest


def to_png(path):
    """Images arrive as AVIF/WebP, which agents cannot view; convert to PNG."""
    from PIL import Image
    png = path.with_suffix(".png")
    with Image.open(path) as im:
        im.convert("RGB").save(png)
    path.unlink()
    return png


class FrameGrabber:
    """A still from each example video, taken with Chromium (Playwright's
    ffmpeg has no VP9 decoder, and agents cannot open .webm anyway)."""

    def __enter__(self):
        from playwright.sync_api import sync_playwright
        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch()
        return self

    def __exit__(self, *exc):
        self._browser.close()
        self._pw.stop()

    def grab(self, url, png, at=1.0):
        page = self._browser.new_page(viewport={"width": 1280, "height": 720})
        try:
            page.set_content(f'<body style="margin:0;background:#000"><video id="v" src="{url}" muted playsinline></video>')
            page.wait_for_function("document.getElementById('v').readyState >= 2", timeout=30_000)
            page.evaluate(f"""() => {{ const v = document.getElementById('v');
                v.style.width = Math.min(v.videoWidth, 1280) + 'px'; v.style.height = 'auto'; v.currentTime = {at}; }}""")
            page.wait_for_function("(() => { const v = document.getElementById('v'); return !v.seeking && v.readyState >= 2; })()", timeout=30_000)
            page.locator("#v").screenshot(path=str(png))
            return png
        finally:
            page.close()


MAX_EXAMPLE_MEDIA = 4


def write_examples(con, rows, out_dir, log=print, grabber=None):
    """One <n>-<slug>-<sid>.md per hit plus up to MAX_EXAMPLE_MEDIA of its
    generated-role media as PNG (images converted, videos as a still)."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for n, r in enumerate(rows, 1):
        media = con.execute("SELECT * FROM media WHERE section_id = ? ORDER BY id", (r["id"],)).fetchall()
        gen = [m for m in media if m["role"] in db.GENERATED_ROLES]
        stem = f"{n}-{r['slug']}-{r['sid']}"
        files = []
        for m in gen[:MAX_EXAMPLE_MEDIA]:
            dest = out_dir / f"{stem}-{m['slot_id'].split('-')[-1]}.png"
            try:
                if m["kind"] == "video":
                    if grabber is None:
                        continue
                    grabber.grab(m["src"], dest)
                else:
                    ext = Path(urllib.parse.urlsplit(m["src"]).path).suffix or ".bin"
                    tmp = dest.with_suffix(ext) if ext.lower() != ".png" else dest
                    download(m["src"], tmp)
                    if tmp != dest:
                        to_png(tmp)
            except Exception as exc:  # a missing example asset is not fatal
                log(f"  could not fetch {m['src']}: {exc}")
                continue
            files.append((m, dest))
        lines = ["---", f"page: {r['slug']}", f"url: {r['url']}", f"section: {r['sid']}", f"type: {r['type']}",
                 f"headline: {r['headline']!r}", f"media_total: {len(gen)}", "media:"]
        for m, f in files:
            size = f"{m['width']}x{m['height']}" if m["width"] and m["height"] else "?"
            lines.append(f"  - {{slot: {m['slot_id']}, kind: {m['kind']}, role: {m['role']}, size: {size}, "
                         f"aspect: '{m['aspect']}', local: {f.name}, src: {m['src']}}}")
        lines += ["---", "", r["md"]]
        path = out_dir / f"{stem}.md"
        path.write_text("\n".join(lines))
        written.append(path)
        log(f"  {path.name}: {r['type']} from {r['slug']}, {len(files)}/{len(gen)} media file(s)")
    return written
