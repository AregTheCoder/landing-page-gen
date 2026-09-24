"""Find the k closest sections of one type across the corpus and write them as
example excerpts (Markdown plus downloaded media) for a worker's brief."""

import json
import re
import shutil
import urllib.parse
from pathlib import Path

from . import db, taxonomy
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


def _media_clause(need_media, style=None, attrs=None, exclude_asset=None, kind=None):
    """The EXISTS filter on a section's media: a generated-role slot, optionally
    of one kind (image | video), of one family[/variant] and with given attribute
    values; plus a NOT EXISTS for sections that show the excluded source asset
    (sibling pages reuse it)."""
    fam, variant = split_style(style)
    conds, params = ["m.role IN ('creative','thumbnail')"], []
    if kind:
        conds.append("m.kind = ?")
        params.append(kind)
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
    if need_media or fam or attrs or kind:
        sql = f"AND EXISTS (SELECT 1 FROM media m WHERE m.section_id = s.id AND {' AND '.join(conds)})"
    ids = [exclude_asset] if isinstance(exclude_asset, str) else list(exclude_asset or [])
    if ids:
        # one id is enough to drop the section; the uuid prefix lives in src, the sha1 suffix in the local name
        hit = " OR ".join("x.src LIKE ? OR x.local_path LIKE ?" for _ in ids)
        sql += f" AND NOT EXISTS (SELECT 1 FROM media x WHERE x.section_id = s.id AND ({hit}))"
        for i in ids:
            params += [f"%{i}%", f"%{i}%"]
    return sql, tuple(params)


def _row_score(con, section_id, fam, attrs, kind=None):
    """How well a candidate section's example media match the target slot, for
    re-ranking on look/construction rather than section copy alone. A same-family
    example scores; a chrome-ANSWERED (verified) one scores more than a
    pixel-only provisional guess (the measurer mislabels composites as
    full-bleed until chrome is answered); each matching target attribute adds a
    little; an example of the slot's own kind (a clip for a video slot) adds
    more, since only a clip shows motion. 0 when the section has no usable
    example media."""
    rows = con.execute("SELECT style, attrs, kind FROM media WHERE section_id = ? "
                       "AND role IN ('creative','thumbnail')", (section_id,)).fetchall()
    best = 0.0
    for m in rows:
        a = json.loads(m["attrs"]) if m["attrs"] else {}
        s = 0.0
        if kind and m["kind"] == kind:
            s += 1.5
        if fam and m["style"] == fam:
            s += 2.0
            s += 1.0 if a.get("chrome") is not None else 0.0   # verified beats provisional
        for key, val in (attrs or {}).items():
            if a.get(key) == val:
                s += 0.5
        best = max(best, s)
    return best


def find_similar(con, type_, query, k=3, exclude=None, need_media=True, style=None, attrs=None, exclude_asset=None,
                 kind=None):
    """Top-k sections of `type_` by BM25, at most one per page, from pages
    other than `exclude` and never showing any of `exclude_asset` (an 8-hex
    asset id, the uuid prefix of the src or the hash suffix of the local file
    name, or a list of them); with need_media only sections that have a
    creative/thumbnail slot. With `style` (family[/variant]), `attrs`
    ({attribute: value}) or `kind` (image | video: the slot's own kind),
    matching sections come first; the looser passes only fill what is left."""
    match = fts_query(query)
    rows = []

    def enough():
        return len({r["slug"] for r in rows if r["slug"] != exclude}) >= k
    passes = []
    for st, at, kd in ((style, attrs, kind), (None, None, kind), (style, attrs, None), (None, None, None)):
        if (st or at or kd or (st, at, kd) == (None, None, None)) and (st, at, kd) not in passes:
            passes.append((st, at, kd))
    for st, at, kd in passes:
        clause, params = _media_clause(need_media or st or at, st, at, exclude_asset, kd)
        if match and not enough():
            rows += con.execute(
                f"""SELECT s.*, p.slug, p.url, bm25(sections_fts) AS rank
                    FROM sections_fts f JOIN sections s ON s.id = f.rowid JOIN pages p ON p.id = s.page_id
                    WHERE sections_fts MATCH ? AND s.type = ? {clause}
                    ORDER BY rank LIMIT ?""", (match, type_, *params, k * 8)).fetchall()
    for st, at, kd in passes:
        clause, params = _media_clause(need_media or st or at, st, at, exclude_asset, kd)
        if not enough():
            rows += con.execute(
                f"""SELECT s.*, p.slug, p.url, 0 AS rank FROM sections s JOIN pages p ON p.id = s.page_id
                    WHERE s.type = ? {clause} ORDER BY s.media_count DESC, s.text_len DESC LIMIT ?""",
                (type_, *params, k * 8)).fetchall()
    # Re-rank on look/construction: a verified same-family, structurally-matching
    # example of the slot's kind outranks a text-only BM25 hit. Stable, so BM25
    # order breaks ties.
    fam, _ = split_style(style)
    if fam or attrs or kind:
        scored = sorted(enumerate(rows), key=lambda t: (-_row_score(con, t[1]["id"], fam, attrs, kind), t[0]))
        rows = [r for _, r in scored]
    out, seen, shown = [], set(), set()
    for r in rows:
        if r["slug"] == exclude or r["slug"] in seen:
            continue
        lead = _lead_src(con, r["id"])
        if lead and lead in shown:
            continue  # sibling pages share one CMS asset: the same picture twice is one example, not two
        seen.add(r["slug"])
        shown.add(lead)
        out.append(r)
        if len(out) == k:
            break
    return out


def _lead_src(con, section_id):
    """The src of a section's first generated-role picture (what its example shows), or None."""
    row = con.execute(f"SELECT src FROM media WHERE section_id = ? AND role IN ({','.join('?' * len(db.GENERATED_ROLES))}) "
                      "ORDER BY id LIMIT 1", (section_id, *db.GENERATED_ROLES)).fetchone()
    return row["src"] if row else None


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


RANGE_CHUNK = 8 << 20  # bytes per answer to an open-ended range request


def _ranged_route(path):
    """Serve a local clip to Chromium with byte ranges. `route.fulfill(path=)`
    answers every request with the whole file and no Accept-Ranges, which makes
    the clip unseekable (`seekable` is [0, 0]): every seek snapped to 0 and the
    "t=1 s" poster frames were frame 0."""
    data = Path(path).read_bytes()
    mime = "video/webm" if Path(path).suffix.lower() == ".webm" else "video/mp4"

    def handle(route):
        m = re.match(r"bytes=(\d+)-(\d*)", route.request.headers.get("range", ""))
        if m:
            a = int(m.group(1))
            # an open range is answered in chunks: one 188 MB body (ad-maker's clip) closed the page
            b = int(m.group(2)) if m.group(2) else min(len(data), a + RANGE_CHUNK) - 1
            route.fulfill(status=206, body=data[a:b + 1], headers={
                "Content-Type": mime, "Accept-Ranges": "bytes",
                "Content-Range": f"bytes {a}-{b}/{len(data)}", "Content-Length": str(b - a + 1)})
        else:
            route.fulfill(status=200, body=data, headers={
                "Content-Type": mime, "Accept-Ranges": "bytes", "Content-Length": str(len(data))})
    return handle


class FrameGrabber:
    """A still from each example video, taken with Chromium (Playwright's
    ffmpeg has no VP9 decoder, and agents cannot open .webm anyway)."""

    def __enter__(self):
        # Launch nothing yet: most `similar` runs have no video example, and
        # Chromium startup is ~0.9s per call inside the build loop.
        self._pw = self._browser = None
        return self

    def __exit__(self, *exc):
        if self._browser is not None:
            self._browser.close()
            self._pw.stop()

    def _ensure(self):
        if self._browser is None:
            from playwright.sync_api import sync_playwright
            self._pw = sync_playwright().start()
            self._browser = self._pw.chromium.launch()

    def grab(self, src, png, at=1.0):
        """One still at `at` seconds."""
        return self.grab_many(src, [(at, png)])[1][0]

    def grab_many(self, src, plan):
        """Several stills of one clip from a single load. `plan` is a list of
        (seconds, png) or a callable taking the clip's duration and returning
        one, for a caller that spaces its frames by the length Chromium reads.
        Returns (duration, pngs). src: a CDN URL or a local Path (served to
        Chromium through a route, since a set_content page may not load
        file:// media)."""
        self._ensure()
        page = self._browser.new_page(viewport={"width": 1280, "height": 720})
        try:
            url = str(src)
            if isinstance(src, Path):
                url = "http://lp.local/" + src.name
                page.route(url, _ranged_route(src))
            page.set_content(f'<body style="margin:0;background:#000"><video id="v" src="{url}" muted playsinline '
                             f'style="position:absolute;left:-9999px"></video><canvas id="c" style="display:block"></canvas>')
            page.wait_for_function("document.getElementById('v').readyState >= 2", timeout=30_000)
            duration = page.evaluate("() => { const v = document.getElementById('v'); return isFinite(v.duration) ? v.duration : null; }")
            targets = plan(duration) if callable(plan) else plan
            pngs = []
            for at, png in targets:
                # Seek, wait for the `seeked` event, then draw the presented frame
                # onto a canvas and screenshot THAT: an element screenshot of the
                # video after a seek repaints the frame Chromium showed before, so
                # five seeks gave five copies of it. The canvas is screenshotted,
                # not exported, because a routed or CDN clip taints it.
                page.evaluate("""async (at) => {
                    const v = document.getElementById('v');
                    const t = Math.min(at, isFinite(v.duration) ? Math.max(0, v.duration - 0.05) : at);
                    if (Math.abs(v.currentTime - t) > 0.01) {
                        await new Promise(res => { v.addEventListener('seeked', res, {once: true}); v.currentTime = t; });
                    }
                    const c = document.getElementById('c');
                    const scale = Math.min(1, 1280 / v.videoWidth);
                    c.width = Math.round(v.videoWidth * scale); c.height = Math.round(v.videoHeight * scale);
                    c.getContext('2d').drawImage(v, 0, 0, c.width, c.height);
                }""", float(at))
                page.locator("#c").screenshot(path=str(png))
                pngs.append(png)
            return duration, pngs
        finally:
            page.close()


def _built(attrs_json, duration=None):
    """A compact `built: {...}` of an example's construction (ground, layout,
    panels, chrome, art_style, structure; for a clip also its length, pace, loop,
    camera and motion kind) so a worker anchors on how the picture is made, not
    a 480px thumbnail alone. Empty when the asset is unlabelled."""
    a = json.loads(attrs_json) if attrs_json else {}
    if duration and "duration" not in a:
        a["duration"] = duration
    if not a:
        return ""
    parts = []
    if a.get("ground"):
        parts.append(f"ground: {a['ground']}")
    if a.get("layout"):
        parts.append(f"layout: {a['layout']}")
    if a.get("panel_count") is not None:
        parts.append(f"panels: {a['panel_count']}")
    if a.get("chrome"):
        parts.append(f"chrome: [{', '.join(a['chrome'])}]")
    if a.get("art_style"):
        parts.append(f"art_style: {a['art_style']}")
    struct = taxonomy.structure_of(a)[0]
    if struct:
        parts.append(f"structure: {struct}")
    if a.get("duration"):
        parts.append(f"duration: {a['duration']}s")
    for key in ("pace", "loop", "camera", "motion_kind"):
        if a.get(key) is not None:
            parts.append(f"{key}: {str(a[key]).lower()}")
    return f", built: {{{', '.join(parts)}}}" if parts else ""


MAX_EXAMPLE_MEDIA = 1  # per example section; a brief shows the look, not the whole grid
STRIP_MAX_PX = 3 * EXAMPLE_MAX_PX  # a clip's 3-frame strip: each frame at the example size


def video_strip(src, dest, grabber, duration=None):
    """A clip's first/middle/last frames side by side, at example size: the
    motion arc in one image a worker can Read. The sampled frames live in a
    temporary folder; only the strip is kept."""
    import tempfile
    from . import motion
    with tempfile.TemporaryDirectory() as tmp:
        _, frames = motion.probe(src, grabber, tmp, dest.stem, duration)
        motion.strip(frames, dest)
    return to_png(dest, max_px=STRIP_MAX_PX)


def write_examples(con, rows, out_dir, log=print, grabber=None, max_media=MAX_EXAMPLE_MEDIA, kind=None):
    """One <n>-<slug>-<sid>.md per hit plus up to max_media of its
    generated-role media as PNG (images converted and downscaled, videos as a
    3-frame strip), taken from the snapshot's local copy when there is one.
    `kind` puts media of the slot's own kind first."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for n, r in enumerate(rows, 1):
        media = con.execute("SELECT * FROM media WHERE section_id = ? ORDER BY id", (r["id"],)).fetchall()
        gen = sorted((m for m in media if m["role"] in db.GENERATED_ROLES),
                     key=lambda m: (kind is not None and m["kind"] != kind, m["style"] is None))  # own kind, then tagged
        stem = f"{n}-{r['slug']}-{r['sid']}"
        files = []
        for m in gen[:max_media]:
            dest = out_dir / f"{stem}-{m['slot_id'].split('-')[-1]}.png"
            local = Path(m["local_path"]) if m["local_path"] and Path(m["local_path"]).exists() else None
            try:
                if m["kind"] == "video":
                    if grabber is None:
                        continue
                    video_strip(local or m["src"], dest, grabber, m["duration"])
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
                         f"aspect: '{m['aspect']}', style: {m['style'] or 'untagged'}, local: {f.name}, "
                         f"src: {m['src']}{_built(m['attrs'], m['duration'])}}}")
        lines += ["---", "", r["md"]]
        path = out_dir / f"{stem}.md"
        path.write_text("\n".join(lines))
        written.append(path)
        log(f"  {path.name}: {r['type']} from {r['slug']}, {len(files)}/{len(gen)} media file(s)")
    return written
