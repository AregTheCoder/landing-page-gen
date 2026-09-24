"""A clip read as a storyboard (corpus/storyboard.py): the holds found in dense
samples, the transitions between them typed, an animated intro kept."""

import numpy as np

from landing_page_gen.corpus import storyboard as sb


def _frames():
    """40 samples at 32 px: A holds, crossfades to B, B holds, wipes left to right to C, C holds."""
    A = np.zeros((32, 32, 3), np.float32)
    A[8:24, 2:12] = 1.0
    B = np.zeros((32, 32, 3), np.float32)
    B[8:24, 20:30] = 1.0
    C = np.ones((32, 32, 3), np.float32) * 0.5
    out = [A] * 10
    out += [(1 - a) * A + a * B for a in np.linspace(0.2, 0.8, 5)]
    out += [B] * 10
    for k in range(1, 6):  # the boundary sweeps across
        f = B.copy()
        f[:, : round(32 * k / 6)] = C[:, : round(32 * k / 6)]
        out.append(f)
    out += [C] * 10
    return np.stack(out)


def test_holds_are_found_between_transitions():
    states, live, share = sb.segment(_frames())
    assert live is None
    assert [s for s in states] == [(0, 9), (15, 24), (30, 39)]


def test_transitions_are_typed_from_the_frames_between_holds():
    f = _frames()
    assert sb.transition(f, 9, 15)["type"] == "crossfade"
    assert sb.transition(f, 24, 30)["type"] == "wipe-lr"
    assert sb.transition(f, 9, 10)["type"] == "cut"


def test_an_intro_that_never_holds_is_still_a_state():
    rng = np.random.default_rng(0)
    intro = [rng.random((32, 32, 3)).astype(np.float32) for _ in range(6)]
    f = np.concatenate([np.stack(intro), _frames()])
    states, _, _ = sb.segment(f)
    assert states[0] == (0, 0)  # the opening frame stands for the intro
    assert states[1][0] >= 6
