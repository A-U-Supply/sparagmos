"""Tests for fractal blend effect."""

import numpy as np
import pytest
from PIL import Image

from sparagmos.effects import ConfigError, EffectContext, register_effect
from sparagmos.effects.fractal_blend import FractalBlendEffect


@pytest.fixture
def effect():
    e = FractalBlendEffect()
    register_effect(e)
    return e


@pytest.fixture
def context(tmp_path):
    return EffectContext(vision=None, temp_dir=tmp_path, seed=42, source_metadata={})


def test_apply_produces_valid_image(effect, test_image_rgb, context):
    params = {"opacity": 0.5, "iterations": 20, "colormap": "hot"}
    result = effect.apply(test_image_rgb, params, context)
    assert result.image.size == test_image_rgb.size
    assert result.image.mode == "RGB"


def test_apply_modifies_image(effect, test_image_rgb, context):
    params = {"opacity": 0.8, "iterations": 20, "colormap": "hot"}
    result = effect.apply(test_image_rgb, params, context)
    orig = np.array(test_image_rgb.convert("RGB"))
    out = np.array(result.image)
    assert not np.array_equal(orig, out)


def test_validate_params_defaults(effect):
    params = effect.validate_params({})
    assert params["opacity"] == 0.5
    assert params["iterations"] == 100
    assert params["colormap"] == "hot"


def test_validate_params_clamps_opacity(effect):
    params = effect.validate_params({"opacity": 5.0})
    assert params["opacity"] == 1.0

    params = effect.validate_params({"opacity": -1.0})
    assert params["opacity"] == 0.0


def test_validate_params_clamps_iterations(effect):
    params = effect.validate_params({"iterations": 9999})
    assert params["iterations"] == 500

    params = effect.validate_params({"iterations": 0})
    assert params["iterations"] == 1


def test_validate_params_rejects_bad_colormap(effect):
    with pytest.raises(ConfigError):
        effect.validate_params({"colormap": "rainbow_blast"})


def test_works_with_tiny_image(effect, test_image_tiny, context):
    params = {"opacity": 0.5, "iterations": 5, "colormap": "hot"}
    result = effect.apply(test_image_tiny, params, context)
    assert result.image.size == test_image_tiny.size


def test_cool_colormap(effect, test_image_rgb, context):
    params = {"opacity": 0.5, "iterations": 10, "colormap": "cool"}
    result = effect.apply(test_image_rgb, params, context)
    assert result.image.size == test_image_rgb.size
    assert result.image.mode == "RGB"


def test_grayscale_colormap(effect, test_image_rgb, context):
    params = {"opacity": 0.5, "iterations": 10, "colormap": "grayscale"}
    result = effect.apply(test_image_rgb, params, context)
    assert result.image.size == test_image_rgb.size
    assert result.image.mode == "RGB"


def test_zero_opacity_is_original(effect, test_image_rgb, context):
    """opacity=0 should return the original image unchanged."""
    params = {"opacity": 0.0, "iterations": 20, "colormap": "hot"}
    result = effect.apply(test_image_rgb, params, context)
    orig = np.array(test_image_rgb.convert("RGB"))
    out = np.array(result.image)
    np.testing.assert_array_equal(orig, out)


def test_metadata_contains_params(effect, test_image_rgb, context):
    params = {"opacity": 0.3, "iterations": 50, "colormap": "cool"}
    result = effect.apply(test_image_rgb, params, context)
    assert result.metadata["opacity"] == 0.3
    assert result.metadata["iterations"] == 50
    assert result.metadata["colormap"] == "cool"
    assert "center_real" in result.metadata
    assert "zoom" in result.metadata
