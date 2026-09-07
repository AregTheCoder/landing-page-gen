"""Find the k closest sections of one type across the corpus and write them as
example excerpts (Markdown plus downloaded media) for a worker's brief."""

import re
import shutil
import urllib.parse
from pathlib import Path

from . import db
from .media import download  # noqa: F401  (tests monkeypatch similar.download)

STOP = {"the", "and", "for", "with", "your", "you", "from", "that", "this", "are", "can", "any", "all",
        "into", "one", "our", "how", "what", "use", "get", "more", "make", "made", "new", "just", "every"}
def fts_query(query, limit=40):
    tokens = []
    for t in re.findall(r"[A-Za-z0-9]+", query):
        tl = t.lower()
        if len(tl) > 2 and tl not in STOP and tl not in tokens:
            tokens.append(tl)
    return " OR ".join(f'"{t}"' for t in tokens[:limit])


def _media_clause(need_media, style=None):
    if not need_media and not style:
        return "", ()
    cond = "m.role IN ('creative','thumbnail')" + (" AND m.style = ?" if style else "")
    return f"AND EXISTS (SELECT 1 FROM media m WHERE m.section_id = s.id AND {cond})", ((style,) if style else ())


def find_similar(con, type_, query, k=3, exclude=None, need_media=True, style=None):
    """Top-k sections of `type_` by BM25, at most one per page, from pages
    other than `exclude`; with need_media only sections that have a
    creative/thumbnail slot. With `style`, sections whose media carry that
    style family come first; the untagged passes only fill what is left."""
    match = fts_query(query)
    rows = []

    def enough():
        return len({r["slug"] for r in rows if r["slug"] != exclude}) >= k
    passes = ([style] if style else []) + [None]
    for st in passes:
        clause, params = _media_clause(need_media or st, st)
        if match and not enough():
            rows += con.execute(
                f"""SELECT s.*, p.slug, p.url, bm25(sections_fts) AS rank
                    FROM sections_fts f JOIN sections s ON s.id = f.rowid JOIN pages p ON p.id = s.page_id
                    WHERE sections_fts MATCH ? AND s.type = ? {clause}
                    ORDER BY rank LIMIT ?""", (match, type_, *params, k * 8)).fetchall()
    for st in passes:
        clause, params = _media_clause(need_media or st, st)
        if not enough():
            rows += con.execute(
                f"""SELECT s.*, p.slug, p.url, 0 AS rank FROM sections s JOIN pages p ON p.id = s.page_id
                    WHERE s.type = ? {clause} ORDER BY s.media_count DESC, s.text_len DESC LIMIT ?""",
                (type_, *params, k * 8)).fetchall()
    out, seen = [], set()
    for r in rows:
        if r["slug"] == exclude or r["slug"] in seen:
            continue
        seen.add(r["slug"])
        out.append(r)
        if len(out) == k:
            break
    return out


def to_png(path):
    """Images arrive as AVIF/WebP (sometimes behind a .png name), which agents
    cannot view; re-encode as PNG by content, not by suffix."""
    from PIL import Image
    png = path.with_suffix(".png")
    with Image.open(path) as im:
        rgb = im.convert("RGB")
    rgb.save(png)
    if path != png:
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

    def grab(self, src, png, at=1.0):
        """src: a CDN URL or a local Path (served to Chromium through a route,
        since a set_content page may not load file:// media)."""
        page = self._browser.new_page(viewport={"width": 1280, "height": 720})
        try:
            url = str(src)
            if isinstance(src, Path):
                url = "http://lp.local/" + src.name
                page.route(url, lambda route: route.fulfill(path=str(src)))
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
    generated-role media as PNG (images converted, videos as a still), taken
    from the snapshot's local copy when there is one."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for n, r in enumerate(rows, 1):
        media = con.execute("SELECT * FROM media WHERE section_id = ? ORDER BY id", (r["id"],)).fetchall()
        gen = sorted((m for m in media if m["role"] in db.GENERATED_ROLES), key=lambda m: m["style"] is None)  # tagged first
        stem = f"{n}-{r['slug']}-{r['sid']}"
        files = []
        for m in gen[:MAX_EXAMPLE_MEDIA]:
            dest = out_dir / f"{stem}-{m['slot_id'].split('-')[-1]}.png"
            local = Path(m["local_path"]) if m["local_path"] and Path(m["local_path"]).exists() else None
            try:
                if m["kind"] == "video":
                    if grabber is None:
                        continue
                    grabber.grab(local or m["src"], dest)
                else:
                    ext = Path(urllib.parse.urlsplit(m["src"]).path).suffix or ".bin"
                    tmp = dest.with_suffix(ext)
                    if local:
                        shutil.copyfile(local, tmp)
                    else:
                        download(m["src"], tmp)
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
                         f"aspect: '{m['aspect']}', style: {m['style'] or 'untagged'}, local: {f.name}, src: {m['src']}}}")
        lines += ["---", "", r["md"]]
        path = out_dir / f"{stem}.md"
        path.write_text("\n".join(lines))
        written.append(path)
        log(f"  {path.name}: {r['type']} from {r['slug']}, {len(files)}/{len(gen)} media file(s)")
    return written
