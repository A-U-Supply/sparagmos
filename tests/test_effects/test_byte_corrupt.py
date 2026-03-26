"""Tests for byte_corrupt effect."""

import numpy as np
import pytest
from PIL import Image

from sparagmos.effects import ConfigError, EffectContext, register_effect
from sparagmos.effects.byte_corrupt import ByteCorruptEffect


@pytest.fixture
def effect():
    e = ByteCorruptEffect()
    register_effect(e)
    return e


@pytest.fixture
def context(tmp_path):
    return EffectContext(vision=None, temp_dir=tmp_path, seed=42, source_metadata={})


def test_apply_produces_valid_image(effect, test_image_rgb, context):
    params = {"num_flips": 50, "mode": "flip"}
    result = effect.apply(test_image_rgb, params, context)
    assert result.image.size == test_image_rgb.size
    assert result.image.mode == "RGB"


def test_apply_modifies_image(effect, test_image_rgb, context):
    params = {"num_flips": 500, "mode": "flip"}
    result = effect.apply(test_image_rgb, params, context)
    orig = np.array(test_image_rgb)
    out = np.array(result.image)
    assert not np.array_equal(orig, out)


def test_apply_inject_mode(effect, test_image_rgb, context):
    params = {"num_flips": 100, "mode": "inject"}
    result = effect.apply(test_image_rgb, params, context)
    assert result.image.size == test_image_rgb.size
    assert result.image.mode == "RGB"


def test_apply_replace_mode(effect, test_image_rgb, context):
    params = {"num_flips": 100, "mode": "replace"}
    result = effect.apply(test_image_rgb, params, context)
    assert result.image.size == test_image_rgb.size
    assert result.image.mode == "RGB"


def test_validate_params_defaults(effect):
    params = effect.validate_params({})
    assert params["num_flips"] == 100
    assert params["skip_header"] == 0
    assert params["mode"] == "flip"


def test_validate_params_clamps_num_flips(effect):
    params = effect.validate_params({"num_flips": 99999})
    assert params["num_flips"] <= 10000

    params = effect.validate_params({"num_flips": -5})
    assert params["num_flips"] == 0


def test_validate_params_rejects_bad_mode(effect):
    with pytest.raises(ConfigError):
        effect.validate_params({"mode": "explode"})


def test_works_with_tiny_image(effect, test_image_tiny, context):
    params = {"num_flips": 5, "mode": "flip"}
    result = effect.apply(test_image_tiny, params, context)
    assert result.image.size == test_image_tiny.size


def test_zero_flips_is_near_identity(effect, test_image_rgb, context):
    params = {"num_flips": 0, "mode": "flip"}
    result = effect.apply(test_image_rgb, params, context)
    orig = np.array(test_image_rgb.convert("RGB"))
    out = np.array(result.image)
    np.testing.assert_array_equal(orig, out)


def test_skip_header_beyond_data(effect, test_image_rgb, context):
    """skip_header larger than image data should return image unchanged."""
    params = {"num_flips": 100, "skip_header": 10_000_000, "mode": "flip"}
    result = effect.apply(test_image_rgb, params, context)
    assert result.image.size == test_image_rgb.size
