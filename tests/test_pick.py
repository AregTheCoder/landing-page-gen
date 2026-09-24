"""pick.py draws only slots the procedure lets us generate."""
import importlib.util
import sqlite3
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parents[1] / ".claude" / "skills" / "build-landing-page"


def load():
    sys.path.insert(0, str(HERE))
    spec = importlib.util.spec_from_file_location("pick_mod", HERE / "pick.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_kept_from_source_classes_come_from_the_slot_class_table():
    pick = load()
    assert ("link-grid", "thumbnail", "5:4") in pick.kept_classes()
    assert {"editor-canvas", "model-card"} <= pick.never_families()


def test_no_kept_or_never_generated_slot_is_a_candidate():
    db = Path(__file__).resolve().parents[1] / "corpus" / "corpus.db"
    if not db.exists():
        pytest.skip("no corpus.db")
    pick = load()
    with sqlite3.connect(db) as con:
        pool = pick.candidates(con)
    assert pool and not [c for c in pool if c[3] == "link-grid-5:4"], "blind-1 drew three link-grid 5:4 thumbnails"
