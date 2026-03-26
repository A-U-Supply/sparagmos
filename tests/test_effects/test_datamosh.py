"""Tests for the datamosh effect."""

from __future__ import annotations

import numpy as np
import pytest
from PIL import Image

from sparagmos.effects import EffectContext, register_effect
from sparagmos.effects.datamosh import DatamoshEffect


@pytest.fixture
def effect():
    e = DatamoshEffect()
    register_effect(e)
    return e


@pytest.fixture
def context(tmp_path):
    return EffectContext(vision=None, temp_dir=tmp_path, seed=42, source_metadata={})


@pytest.fixture
def test_image_16x16():
    """16x16 image suitable for datamosh block tests."""
    img = Image.new("RGB", (16, 16))
    pixels = img.load()
    for x in range(16):
        for y in range(16):
            pixels[x, y] = ((x * 16) % 256, (y * 16) % 256, ((x + y) * 8) % 256)
    return img


def test_apply_produces_valid_image(effect, test_image_rgb, context):
    result = effect.apply(test_image_rgb, {"mode": "iframe_remove", "corruption_amount": 0.3}, context)
    assert isinstance(result.image, Image.Image)
    assert result.image.size == test_image_rgb.size
    assert result.image.mode == "RGB"


def test_apply_modifies_image(effect, test_image_rgb, context):
    result = effect.apply(test_image_rgb, {"mode": "mv_swap", "corruption_amount": 0.8}, context)
    orig = np.array(test_image_rgb)
    out = np.array(result.image)
    assert not np.array_equal(orig, out)


def test_validate_params_defaults(effect):
    params = effect.validate_params({})
    assert params["mode"] == "iframe_remove"
    assert params["corruption_amount"] == 0.3
    assert params["block_size"] == 16


def test_works_with_tiny_image(effect, test_image_16x16, context):
    """Use 16x16 image to accommodate default block_size=16."""
    result = effect.apply(test_image_16x16, {}, context)
    assert isinstance(result.image, Image.Image)
    assert result.image.size == test_image_16x16.size


def test_both_modes_produce_valid_output(effect, test_image_rgb, context):
    for mode in ("iframe_remove", "mv_swap"):
        result = effect.apply(test_image_rgb, {"mode": mode, "corruption_amount": 0.5}, context)
        assert result.image.size == test_image_rgb.size
        assert result.image.mode == "RGB"
        arr = np.array(result.image)
        assert arr.min() >= 0
        assert arr.max() <= 255


def test_validate_params_clamps_corruption_amount(effect):
    params = effect.validate_params({"corruption_amount": 2.0})
    assert params["corruption_amount"] == 1.0
    params = effect.validate_params({"corruption_amount": -0.5})
    assert params["corruption_amount"] == 0.0


def test_validate_params_invalid_mode(effect):
    from sparagmos.effects import ConfigError
    with pytest.raises(ConfigError):
        effect.validate_params({"mode": "glitch"})


def test_seeded_rng_is_deterministic(effect, test_image_rgb, context):
    result1 = effect.apply(test_image_rgb, {"mode": "iframe_remove", "corruption_amount": 0.5}, context)
    result2 = effect.apply(test_image_rgb, {"mode": "iframe_remove", "corruption_amount": 0.5}, context)
    arr1 = np.array(result1.image)
    arr2 = np.array(result2.image)
    np.testing.assert_array_equal(arr1, arr2)
