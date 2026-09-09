"""The manager's blindness check names every place a brief or example lets a
worker see the run page's own images, and the frontmatter lines that point at
the original."""
import importlib.util
import json
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / ".claude/skills/build-landing-page/blindcheck.py"
spec = importlib.util.spec_from_file_location("blindcheck", SCRIPT)
blindcheck = importlib.util.module_from_spec(spec)
spec.loader.exec_module(blindcheck)

UUID = "58eda88e-681b-4e7b-9f17-041c172bfe40"


def make_run(tmp_path, leak=True, pointer=True):
    run = tmp_path / "run"
    for sec in ("S03", "S09"):
        (run / "sections" / sec / "examples").mkdir(parents=True)
    slots = {"page": "p", "sections": {"S03": {"type": "gallery"}, "S09": {"type": "tutorial-grid"}}, "slots": {
        "S09-m1": {"src": f"https://cdn-cms-uploads.picsart.com/cms-uploads/{UUID}.avif",
                   "local": f"corpus/pages/p/media/{UUID}-582d4120.avif"},
        "S03-m1": {"src": "https://pcdn.picsart.com/cms-uploads/06daf4fe-aaaa-bbbb-cccc-1ac5cfcfb146.avif",
                   "local": "corpus/pages/p/media/06daf4fe-aaaa-bbbb-cccc-1ac5cfcfb146-deadbeef.avif"},
        "S15-m1": {"src": "https://static.x/openai.png", "local": "corpus/pages/p/media/openai-0badf00d.png"}}}
    (run / "slots.json").write_text(json.dumps(slots))
    head = "# Brief: S09\n\npage: p\n" + ("snapshot: corpus/pages/p/page.html\n" if pointer else "") + "brand: Picsart\n"
    (run / "sections/S09/brief.md").write_text(head)
    (run / "sections/S03/brief.md").write_text("# Brief: S03\n\npage: p\nbrand: Picsart\n")
    shown = UUID if leak else "11111111-2222-3333-4444-555555555555"
    (run / "sections/S09/examples/1-ai-art-generator-S15.md").write_text(
        f"---\nmedia:\n  - {{slot: S15-m1, src: https://cdn-cms-uploads.picsart.com/cms-uploads/{shown}.avif}}\n---\n")
    (run / "sections/S09/examples/2-other-S09.md").write_text(
        "---\nmedia: []\n---\n![x](media/foo-582d4120.avif)\n" if leak else "---\nmedia: []\n---\n")
    (run / "sections/S03/examples/1-other-S03.md").write_text(
        "---\nmedia:\n  - {slot: S03-m1, src: https://pcdn.picsart.com/cms-uploads/99999999-x.avif}\n---\n")
    return run


def test_leaks_and_pointers_are_named(tmp_path):
    problems = blindcheck.check(make_run(tmp_path))
    text = "\n".join(problems)
    assert "S09: sections/S09/examples/1-ai-art-generator-S15.md names 58eda88e (S09-m1)" in text, "the src uuid prefix is caught"
    assert "S09: sections/S09/examples/2-other-S09.md names 582d4120 (S09-m1)" in text, "the local file hash is caught too"
    assert "S09: brief.md carries snapshot:" in text
    assert not any(p.startswith("S03") for p in problems), "a clean section is not named"
    assert "openai" not in text and "0badf00d" in json.dumps(blindcheck.identifiers(
        json.loads((tmp_path / "run" / "slots.json").read_text())["slots"])), "non-hex stems are skipped, hex hashes kept"


def test_clean_run_and_exit_codes(tmp_path, capsys):
    assert blindcheck.check(make_run(tmp_path / "a", leak=False, pointer=False)) == []
    assert blindcheck.main([str(make_run(tmp_path / "b", leak=False, pointer=False))]) == 0
    assert "blind" in capsys.readouterr().out
    assert blindcheck.main([str(make_run(tmp_path / "c"))]) == 1
    assert blindcheck.check(tmp_path / "nowhere") == ["slots.json missing"]
