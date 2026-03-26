"""Tests for DeepDream effect."""

import pytest

try:
    import torch

    HAS_TORCH = True
except ImportError:
    HAS_TORCH = False

pytestmark = pytest.mark.skipif(not HAS_TORCH, reason="PyTorch not installed")

from PIL import Image

from sparagmos.effects import EffectContext, register_effect
from sparagmos.effects.deepdream import DeepDreamEffect


@pytest.fixture
def effect():
    e = DeepDreamEffect()
    register_effect(e)
    return e


@pytest.fixture
def context(tmp_path):
    return EffectContext(vision=None, temp_dir=tmp_path, seed=42, source_metadata={})


@pytest.mark.slow
def test_apply_produces_valid_image(effect, test_image_rgb, context):
    params = {"iterations": 2, "octave_scale": 1.4, "jitter": 8, "learning_rate": 0.01}
    result = effect.apply(test_image_rgb, params, context)
    assert isinstance(result.image, Image.Image)
    assert result.image.mode == "RGB"
    assert result.image.size == test_image_rgb.size


def test_validate_params_defaults(effect):
    params = effect.validate_params({})
    assert params["iterations"] == 10
    assert params["octave_scale"] == 1.4
    assert params["jitter"] == 32
    assert params["learning_rate"] == 0.01


@pytest.mark.slow
def test_works_with_tiny_image(effect, context):
    tiny = Image.new("RGB", (32, 32), color=(100, 150, 200))
    params = {"iterations": 1, "octave_scale": 1.4, "jitter": 4, "learning_rate": 0.01}
    result = effect.apply(tiny, params, context)
    assert isinstance(result.image, Image.Image)
    assert result.image.size == tiny.size


def test_validate_params_rejects_bad_iterations(effect):
    with pytest.raises(Exception):
        effect.validate_params({"iterations": 0})

    with pytest.raises(Exception):
        effect.validate_params({"iterations": 51})


def test_validate_params_rejects_bad_octave_scale(effect):
    with pytest.raises(Exception):
        effect.validate_params({"octave_scale": 0.5})
