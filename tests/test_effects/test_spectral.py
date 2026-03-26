"""Tests for the spectral effect."""

from __future__ import annotations

import numpy as np
import pytest
from PIL import Image

from sparagmos.effects import EffectContext, register_effect
from sparagmos.effects.spectral import SpectralEffect


@pytest.fixture
def effect():
    e = SpectralEffect()
    register_effect(e)
    return e


@pytest.fixture
def context(tmp_path):
    return EffectContext(vision=None, temp_dir=tmp_path, seed=42, source_metadata={})


def test_apply_produces_valid_image(effect, test_image_rgb, context):
    result = effect.apply(test_image_rgb, {"operation": "shift", "amount": 0.3}, context)
    assert isinstance(result.image, Image.Image)
    assert result.image.size == test_image_rgb.size
    assert result.image.mode == "RGB"


def test_apply_modifies_image(effect, test_image_rgb, context):
    result = effect.apply(test_image_rgb, {"operation": "blur", "amount": 0.7}, context)
    orig = np.array(test_image_rgb)
    out = np.array(result.image)
    assert not np.array_equal(orig, out)


def test_validate_params_defaults(effect):
    params = effect.validate_params({})
    assert params["operation"] == "shift"
    assert params["amount"] == 0.3


def test_works_with_tiny_image(effect, test_image_tiny, context):
    result = effect.apply(test_image_tiny, {}, context)
    assert isinstance(result.image, Image.Image)
    assert result.image.size == test_image_tiny.size


def test_all_operations_produce_valid_output(effect, test_image_rgb, context):
    for op in ("shift", "bandpass", "blur"):
        result = effect.apply(test_image_rgb, {"operation": op, "amount": 0.5}, context)
        assert result.image.size == test_image_rgb.size
        assert result.image.mode == "RGB"
        arr = np.array(result.image)
        assert arr.min() >= 0
        assert arr.max() <= 255


def test_validate_params_clamps_amount(effect):
    params = effect.validate_params({"amount": 5.0})
    assert params["amount"] == 1.0
    params = effect.validate_params({"amount": -0.5})
    assert params["amount"] == 0.0


def test_validate_params_invalid_operation(effect):
    from sparagmos.effects import ConfigError
    with pytest.raises(ConfigError):
        effect.validate_params({"operation": "explode"})
