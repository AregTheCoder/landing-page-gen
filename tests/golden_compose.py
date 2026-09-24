"""Byte-identity baseline for lp-compose.

Records a sha256 per (family, variant, aspect) render — plus a few
override/omit/tilt spec variations — so the component-library refactor
(the chrome-kind registry and the layer model) can be proven to change
nothing about the pixels the six existing families produce.

`cases()` is the single source of truth, shared by the writer and the test.
Run `uv run python -m tests.golden_compose --write` to (re)record the fixture
against the CURRENT renderer; do that once on HEAD before the refactor, and
again only when a change is meant to alter output (e.g. the MAGENTA commit).
"""

import hashlib
from pathlib import Path

import yaml
from PIL import Image

from landing_page_gen.compose import cli, plan
from landing_page_gen.compose.cli import template
from landing_page_gen.compose.families import FAMILIES

FIXTURE = Path(__file__).parent / "fixtures" / "compose_golden.yaml"
# the static weights the renderer sets type with (built from Manrope.ttf by fontbuild.py)
FONTS = sorted((Path(cli.draw.__file__).parent / "assets").glob("Manrope-*.ttf"))
BASE_W = 720  # render width; height follows the aspect


def _size(fw, fh):
    return f"{BASE_W}x{round(BASE_W * fh / fw)}"


def cases():
    """Yield {name, family, variant, size, extra} for every family × variant ×
    aspect, then the spec variations the existing tests exercise."""
    for fam in sorted(FAMILIES):
        variants = FAMILIES[fam].get("variants") or {}
        for variant in [None, *(v for v in variants if not variants[v].get("induced"))]:  # induced: scored by replicas
            tmpl = template(fam, variant)
            for fw, fh in tmpl.get("aspects") or (tmpl["aspect"],):
                asp = "" if (tmpl.get("aspects") is None) else f"-{fw}x{fh}"
                name = f"{fam}{('/' + variant) if variant else ''}{asp}"
                yield {"name": name, "family": fam, "variant": variant,
                       "size": _size(fw, fh), "extra": {}}
    # override / omit / tilt paths, mirroring real run specs
    yield {"name": "dark-composite/model-picker+active_text", "family": "dark-composite",
           "variant": "model-picker", "size": _size(1, 1),
           "extra": {"chrome": {"list": {"active_text": "Recraft V4"}}}}
    yield {"name": "panel-overlay+omit+tilted", "family": "panel-overlay", "variant": None,
           "size": _size(4, 3), "extra": {"omit": ["tool-pill"], "ground": "tilted"}}
    yield {"name": "before-after+omit", "family": "before-after", "variant": None,
           "size": _size(21, 10), "extra": {"omit": ["tile"]}}


def render_sha(tmp_path, case):
    """Render one case with solid fixture panels and return its pixel sha256.
    Templates are skeletons, so the chrome is the template's exemplar fill
    (the blocks its measured original showed, resolved from the bank), with the
    case's overrides merged by id: the fixture proves the skeleton + bank draw
    exactly what the filled templates drew."""
    steps = tmp_path / "steps"
    steps.mkdir(exist_ok=True)
    tmpl = template(case["family"], case["variant"])
    panels = {}
    for i, name in enumerate(tmpl["panels"]):
        img = steps / f"{name}.png"
        Image.new("RGB", (800, 800), ("red", "blue", "green", "yellow")[i % 4]).save(img)
        panels[name] = {"image": f"steps/{name}.png"}
    over = case["extra"].get("chrome") or {}
    chrome = [{**it, **over.get(it["id"], {})} for it in plan.exemplar_items(case["family"], case["variant"])]
    spec = {"slot": "S01-m1", "family": case["family"], "size": case["size"],
            "panels": panels, **{k: v for k, v in case["extra"].items() if k != "chrome"}, "chrome": chrome}
    if case["variant"]:
        spec["variant"] = case["variant"]
    spec_path = tmp_path / "compose.yaml"
    spec_path.write_text(yaml.safe_dump(spec))
    out = steps / "out.png"
    assert cli.main([str(spec_path), "--out", str(out)]) == 0, case["name"]
    with Image.open(out) as im:
        payload = f"{im.mode}:{im.size}:".encode() + im.tobytes()
    return hashlib.sha256(payload).hexdigest()


def stamp():
    return {"pillow": __import__("PIL").__version__,
            "manrope_sha1": hashlib.sha1(b"".join(f.read_bytes() for f in FONTS)).hexdigest()}


def write(tmp_path):
    data = {"stamp": stamp(), "hashes": {c["name"]: render_sha(tmp_path, c) for c in cases()}}
    FIXTURE.parent.mkdir(parents=True, exist_ok=True)
    FIXTURE.write_text(yaml.safe_dump(data, sort_keys=True))
    return data


if __name__ == "__main__":
    import argparse
    import tempfile

    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true", help="record the fixture against the current renderer")
    args = ap.parse_args()
    if not args.write:
        ap.error("nothing to do; pass --write to record the baseline")
    with tempfile.TemporaryDirectory() as d:
        data = write(Path(d))
    print(f"wrote {FIXTURE} ({len(data['hashes'])} cases) at Pillow {data['stamp']['pillow']}")
