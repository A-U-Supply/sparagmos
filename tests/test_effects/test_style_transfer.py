"""Tests for neural style transfer effect."""

import pytest

try:
    import torch

    HAS_TORCH = True
except ImportError:
    HAS_TORCH = False

pytestmark = pytest.mark.skipif(not HAS_TORCH, reason="PyTorch not installed")

from PIL import Image

from sparagmos.effects import EffectContext, register_effect
from sparagmos.effects.style_transfer import StyleTransferEffect


@pytest.fixture
def effect():
    e = StyleTransferEffect()
    register_effect(e)
    return e


@pytest.fixture
def context(tmp_path):
    return EffectContext(vision=None, temp_dir=tmp_path, seed=42, source_metadata={})


@pytest.mark.slow
def test_apply_produces_valid_image(effect, test_image_rgb, context):
    params = {"style_weight": 1e4, "content_weight": 1.0, "iterations": 2}
    result = effect.apply(test_image_rgb, params, context)
    assert isinstance(result.image, Image.Image)
    assert result.image.mode == "RGB"
    assert result.image.size == test_image_rgb.size


def test_validate_params_defaults(effect):
    params = effect.validate_params({})
    assert params["style_weight"] == 1e6
    assert params["content_weight"] == 1.0
    assert params["iterations"] == 50


@pytest.mark.slow
def test_works_with_tiny_image(effect, context):
    tiny = Image.new("RGB", (32, 32), color=(80, 120, 200))
    params = {"style_weight": 1e4, "content_weight": 1.0, "iterations": 1}
    result = effect.apply(tiny, params, context)
    assert isinstance(result.image, Image.Image)
    assert result.image.size == tiny.size


def test_validate_params_rejects_bad_iterations(effect):
    with pytest.raises(Exception):
        effect.validate_params({"iterations": 0})

    with pytest.raises(Exception):
        effect.validate_params({"iterations": 201})


def test_validate_params_rejects_negative_weights(effect):
    with pytest.raises(Exception):
        effect.validate_params({"style_weight": -1.0})

    with pytest.raises(Exception):
        effect.validate_params({"content_weight": -1.0})
