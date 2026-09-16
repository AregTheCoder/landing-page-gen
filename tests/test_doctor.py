"""lp-corpus doctor: a fully-processed corpus passes; an off-enum label, a
styles drift and an unindexed snapshot each raise an ERROR."""

from landing_page_gen.corpus import attrs, doctor, styles, taxonomy
from test_attrs import FakeGrabber, build


def _derive_and_apply(con, mapping, styles_yaml):
    tags = {src: {"style": taxonomy.family_of(rec)[0]}
            for src, rec in mapping.items() if taxonomy.family_of(rec)[0]}
    styles.save(tags, styles_yaml)
    styles.apply(con, tags)
    con.commit()
    return tags


def _run(tmp_path, pages, attrs_yaml, styles_yaml):
    return doctor.run(db_path=tmp_path / "c.db", pages_dir=pages, pool_dir=tmp_path / "nopool",
                      attrs_path=attrs_yaml, styles_path=styles_yaml)


def errors(findings):
    return [f for f in findings if f.level == doctor.ERROR]


def test_doctor_passes_on_a_fully_processed_corpus_and_catches_defects(tmp_path, monkeypatch):
    con, pages = build(tmp_path, ["comic-book-generator"], monkeypatch)
    attrs_yaml, styles_yaml, frames = tmp_path / "attributes.yaml", tmp_path / "styles.yaml", tmp_path / "frames"
    mapping, _ = attrs.run(con, path=attrs_yaml, frames_dir=frames, grabber=FakeGrabber())
    _derive_and_apply(con, mapping, styles_yaml)

    # clean: no ERROR findings
    assert errors(_run(tmp_path, pages, attrs_yaml, styles_yaml)) == []

    # an off-enum label the labels stage would have dropped
    src = next(iter(mapping))
    attrs.save({**mapping, src: {**mapping[src], "chrome": ["not-a-real-chrome"]}}, attrs_yaml)
    found = _run(tmp_path, pages, attrs_yaml, styles_yaml)
    assert any(f.code == "off-enum-label" for f in errors(found))

    # a styles.yaml that no longer derives from attributes
    attrs.save(mapping, attrs_yaml)  # restore
    tags = styles.load(styles_yaml)
    tags["https://cdn.example.com/ghost.avif"] = {"style": "full-bleed"}  # derives from nothing
    styles.save(tags, styles_yaml)
    found = _run(tmp_path, pages, attrs_yaml, styles_yaml)
    assert any(f.code == "styles-stale" for f in errors(found))


def test_doctor_flags_a_snapshot_that_was_never_indexed(tmp_path, monkeypatch):
    con, pages = build(tmp_path, ["comic-book-generator"], monkeypatch)
    attrs_yaml, styles_yaml, frames = tmp_path / "attributes.yaml", tmp_path / "styles.yaml", tmp_path / "frames"
    mapping, _ = attrs.run(con, path=attrs_yaml, frames_dir=frames, grabber=FakeGrabber())
    _derive_and_apply(con, mapping, styles_yaml)

    # a snapshot dir with sections.md but no DB page (a fetch that never sectionized)
    (pages / "orphan-page").mkdir()
    (pages / "orphan-page" / "sections.md").write_text("## S01 hero\n")
    found = _run(tmp_path, pages, attrs_yaml, styles_yaml)
    assert any(f.code == "snapshot-not-indexed" for f in errors(found))
