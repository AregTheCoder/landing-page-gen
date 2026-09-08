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


def split_style(style):
    """'dark-composite/light' -> ('dark-composite', 'light'); validates the family."""
    if not style:
        return None, None
    fam, _, variant = style.partition("/")
    if fam not in db.STYLES:
        raise ValueError(f"unknown style family {fam!r}; one of {', '.join(db.STYLES)}")
    return fam, variant or None


def _media_clause(need_media, style=None, attrs=None, exclude_asset=None):
    """The EXISTS filter on a section's media: a generated-role slot, optionally
    of one family[/variant] and with given attribute values; plus a NOT EXISTS
    for sections that show the excluded source asset (sibling pages reuse it)."""
    fam, variant = split_style(style)
    conds, params = ["m.role IN ('creative','thumbnail')"], []
    if fam:
        conds.append("m.style = ?")
        params.append(fam)
    if variant:
        conds.append("json_extract(m.attrs, '$.variant') = ?")
        params.append(variant)
    for key, value in (attrs or {}).items():
        conds.append(f"json_extract(m.attrs, '$.{key}') = ?")
        params.append(value)
    sql = ""
    if need_media or fam or attrs:
        sql = f"AND EXISTS (SELECT 1 FROM media m WHERE m.section_id = s.id AND {' AND '.join(conds)})"
    if exclude_asset:
        sql += " AND NOT EXISTS (SELECT 1 FROM media x WHERE x.section_id = s.id AND x.src LIKE ?)"
        params.append(f"%{exclude_asset}%")
    return sql, tuple(params)


def find_similar(con, type_, query, k=3, exclude=None, need_media=True, style=None, attrs=None, exclude_asset=None):
    """Top-k sections of `type_` by BM25, at most one per page, from pages
    other than `exclude` and never showing `exclude_asset` (an 8-hex asset id
    or any substring of the src); with need_media only sections that have a
    creative/thumbnail slot. With `style` (family[/variant]) or `attrs`
    ({attribute: value}), matching sections come first; the untagged passes
    only fill what is left."""
    match = fts_query(query)
    rows = []

    def enough():
        return len({r["slug"] for r in rows if r["slug"] != exclude}) >= k
    passes = ([(style, attrs)] if style or attrs else []) + [(None, None)]
    for st, at in passes:
        clause, params = _media_clause(need_media or st or at, st, at, exclude_asset)
        if match and not enough():
            rows += con.execute(
                f"""SELECT s.*, p.slug, p.url, bm25(sections_fts) AS rank
                    FROM sections_fts f JOIN sections s ON s.id = f.rowid JOIN pages p ON p.id = s.page_id
                    WHERE sections_fts MATCH ? AND s.type = ? {clause}
                    ORDER BY rank LIMIT ?""", (match, type_, *params, k * 8)).fetchall()
    for st, at in passes:
        clause, params = _media_clause(need_media or st or at, st, at, exclude_asset)
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


EXAMPLE_MAX_PX = 480  # long side of an example image: the look reads at this size, tokens do not


def to_png(path, max_px=EXAMPLE_MAX_PX):
    """Images arrive as AVIF/WebP (sometimes behind a .png name), which agents
    cannot view; re-encode as PNG by content, not by suffix, no larger than
    max_px on the long side."""
    from PIL import Image
    png = path.with_suffix(".png")
    with Image.open(path) as im:
        rgb = im.convert("RGB")
    if max_px and max(rgb.size) > max_px:
        rgb.thumbnail((max_px, max_px), Image.LANCZOS)
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


MAX_EXAMPLE_MEDIA = 1  # per example section; a brief shows the look, not the whole grid


def write_examples(con, rows, out_dir, log=print, grabber=None, max_media=MAX_EXAMPLE_MEDIA):
    """One <n>-<slug>-<sid>.md per hit plus up to max_media of its
    generated-role media as PNG (images converted and downscaled, videos as a
    still), taken from the snapshot's local copy when there is one."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for n, r in enumerate(rows, 1):
        media = con.execute("SELECT * FROM media WHERE section_id = ? ORDER BY id", (r["id"],)).fetchall()
        gen = sorted((m for m in media if m["role"] in db.GENERATED_ROLES), key=lambda m: m["style"] is None)  # tagged first
        stem = f"{n}-{r['slug']}-{r['sid']}"
        files = []
        for m in gen[:max_media]:
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
