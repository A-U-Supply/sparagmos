"""Tests for channel shift effect."""

import numpy as np
import pytest
from PIL import Image

from sparagmos.effects import EffectContext, register_effect
from sparagmos.effects.channel_shift import ChannelShiftEffect


@pytest.fixture
def effect():
    e = ChannelShiftEffect()
    register_effect(e)
    return e


@pytest.fixture
def context(tmp_path):
    return EffectContext(vision=None, temp_dir=tmp_path, seed=42, source_metadata={})


def test_apply_produces_valid_image(effect, test_image_rgb, context):
    params = {"offset_r": 10, "offset_g": 0, "offset_b": -10}
    result = effect.apply(test_image_rgb, params, context)
    assert result.image.size == test_image_rgb.size
    assert result.image.mode == "RGB"


def test_apply_actually_shifts_channels(effect, test_image_rgb, context):
    params = {"offset_r": 20, "offset_g": 0, "offset_b": 0}
    result = effect.apply(test_image_rgb, params, context)
    orig = np.array(test_image_rgb)
    shifted = np.array(result.image)
    assert not np.array_equal(orig, shifted)


def test_zero_offsets_is_identity(effect, test_image_rgb, context):
    params = {"offset_r": 0, "offset_g": 0, "offset_b": 0}
    result = effect.apply(test_image_rgb, params, context)
    orig = np.array(test_image_rgb)
    out = np.array(result.image)
    np.testing.assert_array_equal(orig, out)


def test_validate_params_defaults(effect):
    params = effect.validate_params({})
    assert "offset_r" in params
    assert "offset_g" in params
    assert "offset_b" in params


def test_validate_params_clamps(effect):
    params = effect.validate_params({"offset_r": 9999})
    assert params["offset_r"] <= 500


def test_works_with_tiny_image(effect, test_image_tiny, context):
    params = {"offset_r": 2, "offset_g": 0, "offset_b": -1}
    result = effect.apply(test_image_tiny, params, context)
    assert result.image.size == test_image_tiny.size
