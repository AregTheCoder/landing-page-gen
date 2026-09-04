from landing_page_gen.corpus import db


def test_schema_and_fts_roundtrip(tmp_path):
    con = db.connect(tmp_path / "corpus.db")
    con.execute(
        "INSERT INTO pages(slug, url, fetched_at, html_path) VALUES (?,?,?,?)",
        ("ai-image-generator", "https://picsart.com/ai-image-generator/", "2026-09-04", "page.html"),
    )
    con.execute(
        "INSERT INTO sections(page_id, sid, idx, type, headline, md, text_len, media_count) "
        "VALUES (1, 'S01', 1, 'hero', 'AI Image Generator', '# AI Image Generator\\nTurn ideas into visuals.', 44, 1)",
    )
    con.commit()
    hits = con.execute(
        "SELECT s.sid, s.type FROM sections_fts f JOIN sections s ON s.id = f.rowid "
        "WHERE sections_fts MATCH 'visuals'"
    ).fetchall()
    assert [tuple(h) for h in hits] == [("S01", "hero")]
    assert "hero" in db.SECTION_TYPES
    assert set(db.GENERATED_ROLES) < set(db.MEDIA_ROLES)
