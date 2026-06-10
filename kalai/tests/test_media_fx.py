"""media_fx — every effect is a (src, t, frame_idx) -> u8 frame transform."""
import numpy as np
import pytest

from kalai import media_fx

SRC = (np.random.default_rng(7).random((64, 36, 3)) * 255).astype(np.uint8)


@pytest.mark.parametrize("name", sorted(media_fx.EFFECTS))
def test_every_effect_returns_valid_frame(name):
    out = media_fx.apply(name, SRC, t=0.5, frame_idx=12)
    assert out.shape == SRC.shape and out.dtype == np.uint8


def test_twelve_effects_exist():
    assert len(media_fx.EFFECTS) == 12


def test_envelope_pulse_shape():
    assert media_fx.envelope(0.0) == pytest.approx(0.0, abs=1e-6)
    assert media_fx.envelope(0.5) == pytest.approx(1.0, abs=1e-3)
    assert media_fx.envelope(1.0) == pytest.approx(0.0, abs=1e-6)


def test_unknown_effect_raises():
    with pytest.raises(KeyError):
        media_fx.apply("nope", SRC, t=0.5, frame_idx=0)
