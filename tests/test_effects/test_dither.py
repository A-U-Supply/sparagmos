"""Tests for dither effect."""

import numpy as np
import pytest
from PIL import Image

from sparagmos.effects import ConfigError, EffectContext, register_effect
from sparagmos.effects.dither import DitherEffect


@pytest.fixture
def effect():
    e = DitherEffect()
    register_effect(e)
    return e


@pytest.fixture
def context(tmp_path):
    return EffectContext(vision=None, temp_dir=tmp_path, seed=42, source_metadata={})


def test_apply_produces_valid_image(effect, test_image_rgb, context):
    params = {"palette": "cga"}
    result = effect.apply(test_image_rgb, params, context)
    assert result.image.size == test_image_rgb.size
    assert result.image.mode == "RGB"


def test_apply_modifies_image(effect, test_image_rgb, context):
    params = {"palette": "cga"}
    result = effect.apply(test_image_rgb, params, context)
    orig = np.array(test_image_rgb)
    out = np.array(result.image)
    assert not np.array_equal(orig, out)


def test_apply_ega_palette(effect, test_image_rgb, context):
    result = effect.apply(test_image_rgb, {"palette": "ega"}, context)
    assert result.image.size == test_image_rgb.size
    assert result.metadata["palette"] == "ega"
    assert result.metadata["num_colors"] == 16


def test_apply_gameboy_palette(effect, test_image_rgb, context):
    result = effect.apply(test_image_rgb, {"palette": "gameboy"}, context)
    assert result.image.size == test_image_rgb.size
    assert result.metadata["num_colors"] == 4


def test_apply_thermal_palette(effect, test_image_rgb, context):
    result = effect.apply(test_image_rgb, {"palette": "thermal"}, context)
    assert result.image.size == test_image_rgb.size
    assert result.metadata["num_colors"] == 8


def test_validate_params_defaults(effect):
    params = effect.validate_params({})
    assert params["palette"] == "cga"
    assert params["num_colors"] is None


def test_validate_params_rejects_unknown_palette(effect):
    with pytest.raises(ConfigError):
        effect.validate_params({"palette": "atari"})


def test_validate_params_clamps_num_colors(effect):
    # CGA only has 4 colors — requesting 100 should clamp to 4
    params = effect.validate_params({"palette": "cga", "num_colors": 100})
    assert params["num_colors"] <= 4

    # Must be at least 1
    params = effect.validate_params({"palette": "cga", "num_colors": 0})
    assert params["num_colors"] >= 1


def test_works_with_tiny_image(effect, test_image_tiny, context):
    params = {"palette": "gameboy"}
    result = effect.apply(test_image_tiny, params, context)
    assert result.image.size == test_image_tiny.size
