"""Style families for corpus media: which composite-card family of
`.claude/skills/picsart-workflows/style-families.md` an existing Picsart
image belongs to. Tags live in corpus/styles.yaml keyed by CDN src (stable
across re-fetch and re-index) and are mirrored into media.style, which is
what `similar --style` prefers and `skeleton` pre-fills. `lp-corpus styles`
classifies untagged creatives with Claude vision; `apply` re-mirrors the
yaml after any re-index."""

import base64
import io
import json
import re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import yaml

from . import db

STYLES_YAML = Path("corpus/styles.yaml")
DOC = Path(__file__).resolve().parents[3] / ".claude" / "skills" / "picsart-workflows" / "style-families.md"
CANDIDATE_TYPES = ("hero", "feature-callout", "use-case-grid", "how-it-works")
MODEL = "claude-opus-5"
BEFORE_RE = re.compile(r"\bbefore\b", re.I)
SCHEMA = {
    "type": "object",
    "properties": {"style": {"type": "string", "enum": list(db.STYLES)}, "confidence": {"type": "number"}},
    "required": ["style", "confidence"],
    "additionalProperties": False,
}


def load(path=STYLES_YAML):
    path = Path(path)
    return (yaml.safe_load(path.read_text()) or {}) if path.exists() else {}


def save(mapping, path=STYLES_YAML):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(dict(sorted(mapping.items())), sort_keys=False, allow_unicode=True, width=1000))


def apply(con, mapping):
    """Mirror the yaml into media.style; returns the number of rows set."""
    before = con.total_changes
    con.executemany("UPDATE media SET style = ? WHERE src = ?", [(v["style"], src) for src, v in mapping.items()])
    con.commit()
    return con.total_changes - before


def candidates(con, mapping, force=False):
    """Creative images of the section types that carry a house style, with a
    local copy to look at; already tagged ones are skipped unless force."""
    marks = ",".join("?" * len(CANDIDATE_TYPES))
    rows = con.execute(
        f"""SELECT m.src, m.alt, m.local_path, m.slot_id, p.slug FROM media m
            JOIN sections s ON s.id = m.section_id JOIN pages p ON p.id = s.page_id
            WHERE m.kind = 'image' AND m.role = 'creative' AND m.local_path IS NOT NULL AND s.type IN ({marks})
            ORDER BY p.slug, m.slot_id""", CANDIDATE_TYPES).fetchall()
    return [r for r in rows if force or r["src"] not in mapping]


def guide():
    """The classifier's system prompt: the doc's preamble plus every family's
    Use, Ground and Chrome lines, read at run time so the doc stays the one
    source of truth."""
    lines = DOC.read_text().splitlines()
    out, in_block = [], False
    for line in lines:
        if line.startswith("## "):
            in_block = True
            out.append(line)
        elif not in_block or line.startswith(("**Use:**", "**Ground:**", "**Chrome")):
            out.append(line)
    return "\n".join(out) + "\n\nClassify the image into exactly one family id."


def encode(path, max_px=512):
    from PIL import Image
    with Image.open(path) as im:
        im = im.convert("RGB")
        im.thumbnail((max_px, max_px))
        buf = io.BytesIO()
        im.save(buf, format="PNG")
    return base64.standard_b64encode(buf.getvalue()).decode()


def classify(client, path, system, model=MODEL):
    """One image -> (style, confidence), or None when the model declines."""
    response = client.messages.create(
        model=model, max_tokens=256, system=system,
        output_config={"effort": "low", "format": {"type": "json_schema", "schema": SCHEMA}},
        messages=[{"role": "user", "content": [
            {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": encode(path)}},
            {"type": "text", "text": "Which style family is this Picsart landing-page image? "
                                     "Give the family id and a confidence between 0 and 1."},
        ]}],
    )
    if response.stop_reason == "refusal":
        return None
    data = json.loads(next(b.text for b in response.content if b.type == "text"))
    return data["style"], float(data["confidence"])


def run(con, model=MODEL, limit=None, force=False, workers=8, log=print, path=STYLES_YAML, client=None):
    """Tag the untagged candidates: alt text saying "before" is before-after
    for free, everything else goes to the model. Saves the yaml every 50
    results and mirrors it into the DB. Returns (mapping, n_by_alt, n_by_model, rows_set)."""
    mapping = load(path)
    todo = candidates(con, mapping, force)[:limit]
    pre = [r for r in todo if r["alt"] and BEFORE_RE.search(r["alt"])]
    for r in pre:
        mapping[r["src"]] = {"style": "before-after", "confidence": 1.0, "page": r["slug"], "slot": r["slot_id"]}
    todo = [r for r in todo if not (r["alt"] and BEFORE_RE.search(r["alt"]))]
    if todo:
        if client is None:
            import anthropic
            client = anthropic.Anthropic()
        system = guide()

        def one(r):
            try:
                return r, classify(client, r["local_path"], system, model)
            except Exception as exc:  # one bad image or request must not stop the pass
                log(f"  {r['slug']} {r['slot_id']}: {exc!r}")
                return r, None
        with ThreadPoolExecutor(workers) as ex:
            for i, (r, res) in enumerate(ex.map(one, todo), 1):
                if res:
                    mapping[r["src"]] = {"style": res[0], "confidence": round(res[1], 2), "page": r["slug"], "slot": r["slot_id"]}
                if i % 50 == 0:
                    log(f"  {i}/{len(todo)}")
                    save(mapping, path)
    save(mapping, path)
    return mapping, len(pre), len(todo), apply(con, mapping)
