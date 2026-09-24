"""Readings: what each corpus picture says and where. One JSON per distinct
asset in `corpus/readings/<id>.json`: the OCR lines (macOS Vision, on-device)
and the layout read off the pixels (`layout.py`): the ground, the cards and
pictures on it, and what sits in each. Rebuildable, so gitignored.

    uv run lp-corpus read [--limit N] [--force] [--page SLUG]

A reading is the evidence templates are learned from and replicas are scored
against: the strings exactly as set, the boxes they fill, the cards' fills and
radii."""

import json
import sys
from pathlib import Path

from . import attrs, layout, ocr

STORE = Path("corpus/readings")
ROLES = ("creative", "thumbnail", "ui-screenshot")
CHUNK = 100


def path_of(aid, store=STORE):
    return Path(store) / f"{aid}.json"


def load(aid, store=STORE):
    p = path_of(aid, store)
    return json.loads(p.read_text()) if p.exists() else None


def every(store=STORE):
    for p in sorted(Path(store).glob("*.json")):
        yield json.loads(p.read_text())


def targets(con, pages=None, roles=ROLES):
    """Distinct local images of the generated and screenshot roles."""
    recs = attrs.candidates(con, {}, roles=roles, kinds=("image",), force=True)
    out = []
    for r in recs:
        if pages and r["page"] not in pages:
            continue
        if r["local_path"] and Path(r["local_path"]).exists():
            out.append(r)
    return out


def read_one(rec, reading):
    lay = layout.read(rec["local_path"], reading)
    return {"id": attrs.asset_id(rec["src"]), "src": rec["src"], "local": rec["local_path"], "page": rec["page"],
            "slot": rec["slot"], "type": rec["type"], "role": rec["role"], **lay}


def run(con, limit=None, force=False, pages=None, store=STORE):
    store = Path(store)
    store.mkdir(parents=True, exist_ok=True)
    recs = targets(con, pages)
    todo = [r for r in recs if force or not path_of(attrs.asset_id(r["src"]), store).exists()]
    if limit:
        todo = todo[:limit]
    done = 0
    for i in range(0, len(todo), CHUNK):
        chunk = todo[i:i + CHUNK]
        reads = ocr.read([r["local_path"] for r in chunk])
        for r in chunk:
            try:
                rd = read_one(r, reads.get(str(r["local_path"])))
            except Exception as e:  # an unreadable file is reported, never fatal to the pass
                print(f"read: {r['local_path']}: {e}", file=sys.stderr)
                continue
            path_of(rd["id"], store).write_text(json.dumps(rd))
            done += 1
        print(f"read: {min(i + CHUNK, len(todo))}/{len(todo)}", file=sys.stderr)
    return {"targets": len(recs), "read": done, "kept": len(recs) - len(todo)}
