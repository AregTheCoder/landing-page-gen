"""Emit runs/<run>/skeleton.md (and slots.json) for one indexed page.

skeleton.md is what the manager skill parses: YAML frontmatter, one
`## Sxx type` block per section with every text node as `- tN tag: text`,
one fenced `slot` block per media node, and `> annotation:` and `> style:` lines
per generated-role slot for the human to fill in. slots.json maps ids back to the snapshot stamps for
lp-inject."""

import json
from pathlib import Path

import yaml

from . import db

DEFAULTS = {"image_model": "gemini-3-pro-image", "video_model": "seedance-2.5", "video_draft": "seedance-2.0-mini"}
BUDGET = {"run_credits": 300, "image_slot": 20, "video_slot": 60}
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


def render_skeleton(page, sections):
    fm = {
        "page": page["slug"],
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
        for m in media:
            slot = {"id": m["slot_id"], "kind": m["kind"], "role": m["role"]}
            if m["width"] and m["height"]:
                slot["size"] = f"{m['width']}x{m['height']}"
            if m["aspect"]:
                slot["aspect"] = m["aspect"]
            if m["nat_width"] and m["nat_height"]:
                slot["natural"] = f"{m['nat_width']}x{m['nat_height']}"
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
                lines.append(f"> style: {m['style'] or 'TODO one of ' + ' | '.join(db.STYLES)}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def slots_json(page, sections):
    return {
        "page": page["slug"],
        "snapshot": page["html_path"],
        "sections": {s["sid"]: {"type": s["type"], "selector": s["selector"]} for s, _, _ in sections},
        "slots": {
            m["slot_id"]: {"kind": m["kind"], "role": m["role"], "selector": m["selector"], "src": m["src"],
                           "local": m["local_path"], "size": [m["width"], m["height"]], "aspect": m["aspect"]}
            for _, _, media in sections for m in media
        },
        "texts": {t["tid"]: {"tag": t["tag"], "selector": t["selector"]} for _, texts, _ in sections for t in texts},
    }


def write_skeleton(con, slug, out_path):
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    page, sections = load_page(con, slug)
    out_path.write_text(render_skeleton(page, sections))
    (out_path.parent / "slots.json").write_text(json.dumps(slots_json(page, sections), indent=1))
    n_gen = sum(1 for _, _, media in sections for m in media if m["role"] in db.GENERATED_ROLES)
    n_all = sum(len(media) for _, _, media in sections)
    return out_path, len(sections), n_gen, n_all
