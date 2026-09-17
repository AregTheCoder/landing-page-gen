"""Content index over the stock pool, so the manager can pull the *correct*
image for a slot instead of a family-filtered shuffle.

Each entry already carries its family (`best_family`), shape (`aspect_class`),
visual similarity to that family's Picsart corpus (`score`), state and licence.
This adds a plain-language `description` (written into the entry YAML by the
describe pass) and a derived SQLite + FTS5 index so a query like "product on a
pink seamless, hard shadow" ranks the pool by text match x visual score.

The YAML stays the committed source of truth; `_index.sqlite` is derived and
gitignored, rebuilt by `pool index` exactly as `corpus.db` is by `sectionize`.
"""
import json
import sqlite3
from pathlib import Path

from . import db as _db
from . import pool as _pool
from . import styles

INDEX_NAME = "_index.sqlite"

SCHEMA = """
CREATE TABLE IF NOT EXISTS images (
  id TEXT PRIMARY KEY,
  family TEXT, searched_family TEXT, state TEXT, composition TEXT,
  aspect_class TEXT, score REAL, licence TEXT, creator TEXT,
  url TEXT, image TEXT, thumb_local TEXT,
  description TEXT, subject TEXT
);
CREATE VIRTUAL TABLE IF NOT EXISTS images_fts
  USING fts5(description, subject, content='images', content_rowid='rowid');
CREATE TRIGGER IF NOT EXISTS images_ai AFTER INSERT ON images BEGIN
  INSERT INTO images_fts(rowid, description, subject) VALUES (new.rowid, new.description, new.subject);
END;
CREATE TRIGGER IF NOT EXISTS images_ad AFTER DELETE ON images BEGIN
  INSERT INTO images_fts(images_fts, rowid, description, subject) VALUES ('delete', old.rowid, old.description, old.subject);
END;
CREATE INDEX IF NOT EXISTS images_family ON images(family);
CREATE INDEX IF NOT EXISTS images_state ON images(state);
"""


def index_path(pool_dir=_pool.POOL_DIR):
    return Path(pool_dir) / INDEX_NAME


def _clean(text):
    if not text:
        return ""
    for tok in ("<pad>", "</s>", "<s>"):
        text = text.replace(tok, "")
    return " ".join(text.split()).strip()


def merge_descriptions(jsonl_path, pool_dir=_pool.POOL_DIR, log=print):
    """Write `description` from a {id, description} JSONL into the matching pool
    entry in each family YAML. The YAML is the source of truth; returns how many
    entries were set and how many ids had no home."""
    wanted = {}
    with open(jsonl_path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            desc = _clean(rec.get("description"))
            if rec.get("id") and desc:
                wanted[rec["id"]] = desc
    set_n = 0
    for path in sorted(Path(pool_dir).glob("*.yaml")):
        if path.name.startswith("_"):
            continue
        data = _pool.load(path.stem, pool_dir)
        touched = False
        for eid, entry in data["entries"].items():
            if eid in wanted and entry.get("description") != wanted[eid]:
                entry["description"] = wanted[eid]
                set_n += 1
                touched = True
        if touched:
            _pool.save(data, pool_dir)
            log(f"  {path.name}: descriptions merged")
    seen = set()
    for path in sorted(Path(pool_dir).glob("*.yaml")):
        if path.name.startswith("_"):
            continue
        seen |= set(_pool.load(path.stem, pool_dir)["entries"])
    orphan = [i for i in wanted if i not in seen]
    return {"set": set_n, "ids": len(wanted), "orphans": len(orphan)}


def build(pool_dir=_pool.POOL_DIR, log=print):
    """(Re)build `_index.sqlite` from every family YAML. Returns row counts."""
    path = index_path(pool_dir)
    if path.exists():
        path.unlink()
    con = sqlite3.connect(path)
    con.executescript(SCHEMA)
    rows = with_desc = 0
    for ypath in sorted(Path(pool_dir).glob("*.yaml")):
        if ypath.name.startswith("_"):
            continue
        data = _pool.load(ypath.stem, pool_dir)
        for eid, e in data["entries"].items():
            desc = _clean(e.get("description"))
            con.execute(
                "INSERT OR REPLACE INTO images(id,family,searched_family,state,composition,"
                "aspect_class,score,licence,creator,url,image,thumb_local,description,subject) "
                "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (eid, e.get("best_family") or ypath.stem, e.get("searched_family"),
                 e.get("state"), e.get("composition"), e.get("aspect_class"),
                 float(e.get("score") or 0.0), e.get("licence"), e.get("creator"),
                 e.get("url"), e.get("image"), f"thumbs/{eid}.png",
                 desc, e.get("subject")))
            rows += 1
            with_desc += bool(desc)
    con.commit()
    con.close()
    log(f"{path}: {rows} images indexed, {with_desc} with a description")
    return {"rows": rows, "with_description": with_desc}


def picks_for(need, family, k, aspect=None, exclude_asset=(), pool_dir=_pool.POOL_DIR):
    """Ranked *kept* pool entries for a slot, as full entries ready for
    `pool.write_examples`, using the content index to match the slot's `need`.
    Returns None when there is no index or no described-and-kept match, so the
    caller can fall back to the seeded shuffle (`pool.pick`)."""
    if not index_path(pool_dir).exists():
        return None
    rows = find(need=need, family=family, aspect=aspect, state=("kept",), k=k * 3, pool_dir=pool_dir)
    if not rows:
        return None
    data = _pool.load(family, pool_dir)
    excl = list(exclude_asset or [])
    out = []
    for r in rows:
        e = data["entries"].get(r["id"])
        if not e:
            continue
        blind = " ".join([e.get("url") or "", e.get("image") or "", *(e.get("nearest") or [])])
        if any(i in blind for i in excl):
            continue
        out.append(dict(e, id=r["id"]))
        if len(out) >= k:
            break
    return out or None


def _fts_query(need):
    """A safe FTS5 MATCH string: quote each word as a prefix term, OR-joined so
    a partial hit still ranks. Punctuation is dropped."""
    words = [w for w in "".join(c if c.isalnum() else " " for c in need).split() if len(w) > 1]
    return " OR ".join(f'"{w}"*' for w in words)


def find(need=None, family=None, aspect=None, state=("kept",), k=10, pool_dir=_pool.POOL_DIR):
    """Rank pool images for a slot. Hard filters: family, aspect_class, state.
    With `need`, order by text match (bm25) then visual score; without it, by
    score alone. Returns a list of dict rows."""
    con = sqlite3.connect(index_path(pool_dir))
    con.row_factory = sqlite3.Row
    where, args = [], []
    if family:
        where.append("i.family = ?"); args.append(family)
    if aspect:
        where.append("i.aspect_class = ?"); args.append(aspect)
    if state:
        state = (state,) if isinstance(state, str) else tuple(state)
        where.append(f"i.state IN ({','.join('?' * len(state))})"); args.extend(state)
    clause = (" AND " + " AND ".join(where)) if where else ""
    if need and _fts_query(need):
        sql = (f"SELECT i.*, bm25(images_fts) AS rank FROM images_fts "
               f"JOIN images i ON i.rowid = images_fts.rowid "
               f"WHERE images_fts MATCH ?{clause} "
               f"ORDER BY bm25(images_fts) ASC, i.score DESC LIMIT ?")
        args = [_fts_query(need), *args, k]
    else:
        sql = f"SELECT i.*, NULL AS rank FROM images i WHERE 1=1{clause} ORDER BY i.score DESC LIMIT ?"
        args = [*args, k]
    out = [dict(r) for r in con.execute(sql, args).fetchall()]
    con.close()
    return out
