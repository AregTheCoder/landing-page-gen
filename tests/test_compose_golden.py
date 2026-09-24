"""Byte-identity guard: every case in golden_compose must render to the sha
recorded in fixtures/compose_golden.yaml. The registry/layer refactor must not
change these; a deliberate visual change re-records the fixture in its own
commit. Skips (not fails) under a different Pillow, since the raster depends on
it — CI drift stays visible without blocking."""

import yaml
import pytest

import golden_compose as g


_GOLDEN = yaml.safe_load(g.FIXTURE.read_text()) if g.FIXTURE.exists() else None


@pytest.mark.skipif(_GOLDEN is None, reason="no golden fixture recorded yet")
def test_pillow_matches_the_recorded_stamp():
    if _GOLDEN["stamp"]["pillow"] != g.stamp()["pillow"]:
        pytest.skip(f"golden recorded on Pillow {_GOLDEN['stamp']['pillow']}, running {g.stamp()['pillow']}")
    assert _GOLDEN["stamp"]["manrope_sha1"] == g.stamp()["manrope_sha1"], "the bundled Manrope font changed"


@pytest.mark.skipif(_GOLDEN is None, reason="no golden fixture recorded yet")
@pytest.mark.parametrize("case", list(g.cases()), ids=lambda c: c["name"])
def test_case_renders_byte_identical(tmp_path, case):
    if _GOLDEN["stamp"]["pillow"] != g.stamp()["pillow"]:
        pytest.skip("Pillow differs from the recorded baseline")
    assert case["name"] in _GOLDEN["hashes"], f"{case['name']} not in the fixture; re-record with --write"
    assert g.render_sha(tmp_path, case) == _GOLDEN["hashes"][case["name"]]
