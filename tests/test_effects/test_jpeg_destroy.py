"""Tests for JPEG destruction effect."""

import numpy as np
import pytest
from PIL import Image

from sparagmos.effects import EffectContext, register_effect
from sparagmos.effects.jpeg_destroy import JpegDestroyEffect


@pytest.fixture
def effect():
    e = JpegDestroyEffect()
    register_effect(e)
    return e


@pytest.fixture
def context(tmp_path):
    return EffectContext(vision=None, temp_dir=tmp_path, seed=42, source_metadata={})


def test_apply_produces_valid_image(effect, test_image_rgb, context):
    params = {"quality": 5, "iterations": 3}
    result = effect.apply(test_image_rgb, params, context)
    assert result.image.size == test_image_rgb.size
    assert result.image.mode == "RGB"


def test_low_quality_degrades_image(effect, test_image_rgb, context):
    params = {"quality": 1, "iterations": 10}
    result = effect.apply(test_image_rgb, params, context)
    orig = np.array(test_image_rgb)
    destroyed = np.array(result.image)
    diff = np.abs(orig.astype(float) - destroyed.astype(float)).mean()
    assert diff > 5


def test_metadata_records_params(effect, test_image_rgb, context):
    params = {"quality": 3, "iterations": 5}
    result = effect.apply(test_image_rgb, params, context)
    assert result.metadata["quality"] == 3
    assert result.metadata["iterations"] == 5


def test_validate_params_defaults(effect):
    params = effect.validate_params({})
    assert 1 <= params["quality"] <= 95
    assert params["iterations"] >= 1


def test_validate_params_clamps_quality(effect):
    params = effect.validate_params({"quality": 0})
    assert params["quality"] >= 1
    params = effect.validate_params({"quality": 100})
    assert params["quality"] <= 95
