"""SQLite store for scraped landing pages: pages, typed sections as Markdown,
media slots with their CSS selectors, and an FTS5 index for `similar`."""

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

SCHEMA = """
CREATE TABLE IF NOT EXISTS pages (
  id INTEGER PRIMARY KEY,
  slug TEXT UNIQUE NOT NULL,
  url TEXT NOT NULL,
  title TEXT,
  fetched_at TEXT NOT NULL,
  html_path TEXT NOT NULL
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
  local_path TEXT,
  selector TEXT NOT NULL
);
CREATE VIRTUAL TABLE IF NOT EXISTS sections_fts
  USING fts5(md, headline, content='sections', content_rowid='id');
CREATE TRIGGER IF NOT EXISTS sections_ai AFTER INSERT ON sections BEGIN
  INSERT INTO sections_fts(rowid, md, headline) VALUES (new.id, new.md, new.headline);
END;
"""


def connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path)
    con.executescript(SCHEMA)
    return con
