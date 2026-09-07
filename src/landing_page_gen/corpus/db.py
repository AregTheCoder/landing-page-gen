"""SQLite store for scraped landing pages: pages, typed sections as Markdown,
their text nodes and media slots (addressed by `data-lp*` stamps in the page
snapshot), and an FTS5 index over section Markdown for `similar`."""

import sqlite3
from pathlib import Path

SECTION_TYPES = (
    "hero", "feature-callout", "feature-row", "how-it-works", "use-case-grid",
    "gallery", "feature-list", "testimonial", "resource-links", "faq",
    "cta-band", "pricing", "tutorial-grid", "interactive-demo", "link-grid",
    "footer",
)
MEDIA_ROLES = ("creative", "thumbnail", "ui-screenshot", "icon", "decorative")
GENERATED_ROLES = ("creative", "thumbnail")
# style families of .claude/skills/picsart-workflows/style-families.md (media.style)
STYLES = ("dark-composite", "before-after", "crop-frame", "cutout-checkerboard",
          "template-mockup", "prompt-card", "full-bleed",
          "vs-two-up", "mockup-card", "cinematic-still", "graphic-collage", "outcome-tile",
          "editor-canvas", "model-card")

SCHEMA = """
CREATE TABLE IF NOT EXISTS pages (
  id INTEGER PRIMARY KEY,
  slug TEXT UNIQUE NOT NULL,
  url TEXT NOT NULL,
  family TEXT,
  title TEXT,
  fetched_at TEXT NOT NULL,
  html_path TEXT NOT NULL,
  screenshot_path TEXT
);
CREATE TABLE IF NOT EXISTS sections (
  id INTEGER PRIMARY KEY,
  page_id INTEGER NOT NULL REFERENCES pages(id),
  sid TEXT NOT NULL,
  idx INTEGER NOT NULL,
  type TEXT NOT NULL,
  headline TEXT,
  md TEXT NOT NULL,
  text_len INTEGER NOT NULL,
  media_count INTEGER NOT NULL,
  selector TEXT,
  UNIQUE(page_id, sid)
);
CREATE TABLE IF NOT EXISTS texts (
  id INTEGER PRIMARY KEY,
  section_id INTEGER NOT NULL REFERENCES sections(id),
  tid TEXT NOT NULL,
  tag TEXT NOT NULL,
  text TEXT NOT NULL,
  href TEXT,
  selector TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS media (
  id INTEGER PRIMARY KEY,
  section_id INTEGER NOT NULL REFERENCES sections(id),
  slot_id TEXT NOT NULL,
  kind TEXT NOT NULL,
  role TEXT NOT NULL,
  src TEXT NOT NULL,
  alt TEXT,
  width INTEGER,
  height INTEGER,
  aspect TEXT,
  nat_width INTEGER,
  nat_height INTEGER,
  duration REAL,
  local_path TEXT,
  style TEXT,
  attrs TEXT,
  selector TEXT NOT NULL
);
CREATE VIRTUAL TABLE IF NOT EXISTS sections_fts
  USING fts5(md, headline, content='sections', content_rowid='id');
CREATE TRIGGER IF NOT EXISTS sections_ai AFTER INSERT ON sections BEGIN
  INSERT INTO sections_fts(rowid, md, headline) VALUES (new.id, new.md, new.headline);
END;
CREATE TRIGGER IF NOT EXISTS sections_ad AFTER DELETE ON sections BEGIN
  INSERT INTO sections_fts(sections_fts, rowid, md, headline) VALUES ('delete', old.id, old.md, old.headline);
END;
"""


def connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    con.executescript(SCHEMA)
    cols = {r["name"] for r in con.execute("PRAGMA table_info(media)")}
    for col in ("style", "attrs"):  # corpora indexed before styles / attributes existed
        if col not in cols:
            con.execute(f"ALTER TABLE media ADD COLUMN {col} TEXT")
    return con


def delete_page(con, slug):
    """Remove a page and everything under it, so it can be re-indexed."""
    row = con.execute("SELECT id FROM pages WHERE slug = ?", (slug,)).fetchone()
    if row is None:
        return
    con.execute("DELETE FROM media WHERE section_id IN (SELECT id FROM sections WHERE page_id = ?)", (row["id"],))
    con.execute("DELETE FROM texts WHERE section_id IN (SELECT id FROM sections WHERE page_id = ?)", (row["id"],))
    con.execute("DELETE FROM sections WHERE page_id = ?", (row["id"],))
    con.execute("DELETE FROM pages WHERE id = ?", (row["id"],))
