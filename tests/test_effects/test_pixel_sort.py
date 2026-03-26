"""Tests for pixel sorting effect."""

import numpy as np
import pytest
from PIL import Image

from sparagmos.effects import EffectContext, ConfigError, register_effect
from sparagmos.effects.pixel_sort import PixelSortEffect


@pytest.fixture
def effect():
    e = PixelSortEffect()
    register_effect(e)
    return e


@pytest.fixture
def context(tmp_path):
    return EffectContext(vision=None, temp_dir=tmp_path, seed=42, source_metadata={})


def test_apply_produces_valid_image(effect, test_image_rgb, context):
    params = {"mode": "brightness", "direction": "horizontal", "threshold_low": 0.1, "threshold_high": 0.9}
    result = effect.apply(test_image_rgb, params, context)
    assert result.image.size == test_image_rgb.size
    assert result.image.mode == "RGB"


def test_apply_modifies_image(effect, context):
    # Create an image with non-monotonic brightness to ensure sorting changes it
    img = Image.new("RGB", (64, 64))
    pixels = img.load()
    for x in range(64):
        for y in range(64):
            # Alternating bright/dark pattern so sorting will reorder pixels
            brightness = 200 if (x % 3 == 0) else 50
            pixels[x, y] = (brightness, brightness // 2, brightness // 3)
    params = {"mode": "brightness", "direction": "horizontal", "threshold_low": 0.0, "threshold_high": 1.0}
    result = effect.apply(img, params, context)
    orig = np.array(img)
    sorted_img = np.array(result.image)
    assert not np.array_equal(orig, sorted_img)


def test_vertical_sort(effect, test_image_rgb, context):
    params = {"mode": "brightness", "direction": "vertical", "threshold_low": 0.1, "threshold_high": 0.9}
    result = effect.apply(test_image_rgb, params, context)
    assert result.image.size == test_image_rgb.size


def test_hue_sort_mode(effect, test_image_rgb, context):
    params = {"mode": "hue", "direction": "horizontal", "threshold_low": 0.2, "threshold_high": 0.8}
    result = effect.apply(test_image_rgb, params, context)
    assert result.image.size == test_image_rgb.size


def test_validate_params_defaults(effect):
    params = effect.validate_params({})
    assert params["mode"] in ("brightness", "hue", "saturation")
    assert params["direction"] in ("horizontal", "vertical")


def test_validate_params_bad_mode(effect):
    with pytest.raises(ConfigError):
        effect.validate_params({"mode": "invalid"})


def test_works_with_tiny_image(effect, test_image_tiny, context):
    params = {"mode": "brightness", "direction": "horizontal", "threshold_low": 0.1, "threshold_high": 0.9}
    result = effect.apply(test_image_tiny, params, context)
    assert result.image.size == (4, 4)
