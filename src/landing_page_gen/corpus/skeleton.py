"""Emit runs/<run>/skeleton.md (and slots.json) for one indexed page.

skeleton.md is what the manager skill parses: YAML frontmatter, one
`## Sxx type` block per section with every text node as `- tN tag: text`,
one fenced `slot` block per media node, and `> annotation:`, `> style:`, `> attrs:`, `> prior:`, `> text:`,
`> device:` and `> chrome:` lines per generated-role slot for the human to fill in (`> attrs:` says what the style rests on:
the measured fields, whether chrome was ever answered, confidence and source; `> prior:` is what the page grammar,
corpus/grammar/grammar.yaml, expects of a slot in this context: advice, never an override). slots.json maps ids
back to the snapshot stamps for lp-inject and carries style and attrs per slot."""

import json
from pathlib import Path

import yaml
from PIL import Image

from . import db, grammar, sectionize

DEFAULTS = {"image_model": "gpt-image-2.5-sunburst", "video_model": "seedance-2.5", "video_draft": "seedance-2.0-mini"}
BUDGET = {"run_credits": 600, "image_slot": 40,
          "video_slot": 120,     # still ~15 + draft 10 + 7 cr/s final: a faithful 10 s clip is ~95
          "video_seconds": 30}   # the longest final a video slot ships; Seedance's `duration` ceiling
MAX_TEXTS = 40


def load_page(con, slug):
    page = con.execute("SELECT * FROM pages WHERE slug = ?", (slug,)).fetchone()
    if page is None:
        raise SystemExit(f"skeleton: page {slug!r} is not in the corpus; run `lp-corpus sectionize {slug}` first")
    sections = con.execute("SELECT * FROM sections WHERE page_id = ? ORDER BY idx", (page["id"],)).fetchall()
    out = []
    for s in sections:
        texts = con.execute("SELECT * FROM texts WHERE section_id = ? ORDER BY id", (s["id"],)).fetchall()
        media = con.execute("SELECT * FROM media WHERE section_id = ? ORDER BY id", (s["id"],)).fetchall()
        out.append((s, texts, media))
    return page, out


def _source_size(m):
    """The source's real resolution: the larger of the DOM's natural size (which
    srcset variant the fetch happened to load) and the local file's pixels (the
    CDN original). roas-calculator S04 recorded 720x720 while its file is
    1600x1600, and a composite rendered at 720 lost the dots of its ÷."""
    best = (m["nat_width"], m["nat_height"]) if m["nat_width"] and m["nat_height"] else None
    local = m["local_path"]
    if m["kind"] == "image" and local and Path(local).exists():
        try:
            with Image.open(local) as im:
                w, h = im.size
            if not best or w * h > best[0] * best[1]:
                best = (w, h)
        except OSError:
            pass
    return best


def _own_layout(m):
    """(family, layout) induced from this slot's original (`lp-compose --induce`), if any."""
    from ..compose import families
    from .attrs import asset_id
    return families.induced_for(asset_id(m["src"])) if m["src"] else None


def render_skeleton(page, sections, g=None, page_family=None):
    """`g` is the loaded page grammar (None: no `> prior:` lines)."""
    rows, srows = {}, {}
    if g and page_family:
        r, sr = grammar.page_rows(page["slug"], page_family, sections, dedupe=False)
        rows = {x["slot"]: x for x in r}
        srows = {x["sid"]: x for x in sr}
    fm = {
        "page": page["slug"],
        **({"page_family": page_family} if page_family else {}),
        "source": page["url"],
        "snapshot": page["html_path"],
        "brand": "Picsart",
        "audience": "",
        "defaults": DEFAULTS,
        "budget": BUDGET,
        "notes": "",
    }
    lines = ["---", yaml.safe_dump(fm, sort_keys=False, allow_unicode=True).rstrip(), "---", ""]
    lines.append(f"# {page['title'] or page['slug']}")
    lines.append("")
    for s, texts, media in sections:
        lines.append(f"## {s['sid']} {s['type']}")
        lines.append("")
        for i, t in enumerate(texts):
            if i == MAX_TEXTS:
                lines.append(f"- ... {len(texts) - MAX_TEXTS} more text nodes (see corpus)")
                break
            tid = t["tid"].split("-", 1)[1]
            link = f" -> {t['href']}" if t["href"] else ""
            lines.append(f"- {tid} {t['tag']}: {t['text']}{link}")
        if g and s["sid"] in srows and not srows[s["sid"]]["media"]:
            note = grammar.section_prior_line(g, srows[s["sid"]])
            if note:
                lines.append("")
                lines.append(f"> prior: {note}")
        for m in media:
            slot = {"id": m["slot_id"], "kind": m["kind"], "role": m["role"]}
            if m["width"] and m["height"]:
                slot["size"] = f"{m['width']}x{m['height']}"
                slot["size_class"] = sectionize.size_class(m["width"], m["height"])
            if m["aspect"]:
                slot["aspect"] = m["aspect"]
                cls = sectionize.aspect_class(m["width"], m["height"])
                if cls and cls != m["aspect"]:
                    slot["aspect_class"] = cls
            natural = _source_size(m)
            if natural:
                slot["natural"] = f"{natural[0]}x{natural[1]}"
            if m["duration"]:
                slot["duration_s"] = m["duration"]
            slot["src"] = m["src"]
            if m["local_path"]:
                slot["local"] = m["local_path"]
            if m["alt"]:
                slot["alt"] = m["alt"]
            lines.append("")
            lines.append("```slot")
            lines.append(yaml.safe_dump(slot, sort_keys=False, allow_unicode=True, width=1000).rstrip())
            lines.append("```")
            if m["role"] in db.GENERATED_ROLES:
                hint = f' (source alt: "{m["alt"]}")' if m["alt"] else ""
                lines.append(f"> annotation: TODO what this {m['kind']} should show{hint}")
                at = json.loads(m["attrs"]) if m["attrs"] else None
                variant = at.get("variant") if at else None
                style = f"{m['style']}/{variant}" if m["style"] and variant else m["style"]
                lines.append(f"> style: {style or 'TODO one of ' + ' | '.join(db.STYLES)}")
                lines.append(f"> attrs: {attrs_line(at)}")
                pl = grammar.prior_line(g, rows[m["slot_id"]]) if g and m["slot_id"] in rows else None
                if pl:
                    lines.append(f"> prior: {pl}")
                lines.append('> text: TODO exact strings the model renders, e.g. "50% OFF" | "Buy now", or none')
                own = _own_layout(m)
                lines.append("> device: TODO " + (f"{own[1]} (this slot's own measured layout, style {own[0]}) | " if own else "")
                             + "none | reference-thumbs | icon-set | two-up | model-picker | bento | "
                             "applied-mockup | crop-grid | palette-card | selection-frame | editor | pill | compare-slider, "
                             "then a colon and the claim this picture demonstrates")
                lines.append('> chrome: TODO strings the chrome may say beyond the page copy (the Before | After of a '
                             'pill pair, a model a picker may tick, hex colours), or none')
                if m["kind"] == "video":  # the target length: faithful to the original, capped by budget.video_seconds
                    lines.append(f"> duration: {round(m['duration'])}  # original {m['duration']} s" if m["duration"]
                                 else "> duration: TODO seconds (the original's length is unknown)")
                    lines.append(f"> motion: {motion_line(at, m['width'], m['height'])}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


# a templated callout (a composition changing state on a static camera) is
# rendered by `lp-compose --timeline`; anything with real camera or subject
# motion is generated (Seedance). The preset follows the original's chrome.
TIMELINE_KINDS = ("ui-demo", "transition")


def motion_line(at, w=None, h=None):
    """The skeleton's `> motion:` value for a video slot: `timeline <preset>`
    when the original is a ui-demo or transition on a static camera at 1:1,
    else `generative`; a TODO when the clip is not measured."""
    at = at or {}
    kind, camera = at.get("motion_kind"), at.get("camera")
    if not kind:
        return "TODO timeline <enhance-reveal | product-bento | prompt-to-result | brand-to-mockup> | generative"
    square = bool(w and h and abs(w / h - 1) <= 0.02)
    if kind not in TIMELINE_KINDS or camera not in (None, "static") or not square:
        return f"generative  # {kind}, camera {camera or 'unmeasured'}" + ("" if square else ", not 1:1")
    # a clip's chrome is labelled on its poster (first) frame, and a callout's
    # chrome arrives later, so an empty bag says nothing: the manager picks from the strip
    chrome = set(at.get("chrome") or [])
    if chrome & {"prompt-panel", "waveform"}:
        preset = "prompt-to-result"
    elif "button" in chrome or at.get("ui_mockup") == "product-card":
        preset = "product-bento"
    elif chrome & {"mockup-card", "selection-handles"}:
        preset = "brand-to-mockup"
    elif chrome & {"compare-handle", "slider"}:
        preset = "enhance-reveal"
    else:
        return (f"timeline TODO enhance-reveal | product-bento | prompt-to-result | brand-to-mockup  # {kind}, "
                "static camera; pick the one the original's strip shows (lp-compose --describe-timelines)")
    return f"timeline {preset}  # {kind}, static camera (lp-compose --describe-timelines)"


def attrs_line(at):
    """What the slot's style rests on. `chrome=unanswered` means the family
    came from the pixels alone and a chrome family is still possible."""
    if not at:
        return "none (asset not measured; run lp-corpus attrs)"
    chrome = "+".join(sorted(at["chrome"] or [])) or "none" if "chrome" in at else "unanswered"
    conf = at.get("confidence")
    return (f"ground={at.get('ground')} layout={at.get('layout')} panels={at.get('panel_count')} chrome={chrome} "
            f"confidence={'none' if conf is None else conf} source={at.get('source') or 'unknown'}")


def slots_json(page, sections):
    return {
        "page": page["slug"],
        "snapshot": page["html_path"],
        "sections": {s["sid"]: {"type": s["type"], "selector": s["selector"]} for s, _, _ in sections},
        "slots": {
            m["slot_id"]: {"kind": m["kind"], "role": m["role"], "selector": m["selector"], "src": m["src"],
                           "local": m["local_path"], "size": [m["width"], m["height"]], "aspect": m["aspect"],
                           "style": m["style"], "attrs": json.loads(m["attrs"]) if m["attrs"] else None}
            for _, _, media in sections for m in media
        },
        "texts": {t["tid"]: {"tag": t["tag"], "selector": t["selector"]} for _, texts, _ in sections for t in texts},
    }


def write_skeleton(con, slug, out_path, g=None):
    """`g`: the loaded page grammar for the `> prior:` lines (the CLI passes
    corpus/grammar/grammar.yaml; None writes none)."""
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    page, sections = load_page(con, slug)
    out_path.write_text(render_skeleton(page, sections, g, grammar.page_families(con).get(slug)))
    (out_path.parent / "slots.json").write_text(json.dumps(slots_json(page, sections), indent=1))
    n_gen = sum(1 for _, _, media in sections for m in media if m["role"] in db.GENERATED_ROLES)
    n_all = sum(len(media) for _, _, media in sections)
    return out_path, len(sections), n_gen, n_all
