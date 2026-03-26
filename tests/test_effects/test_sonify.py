"""Tests for the sonify effect."""

from __future__ import annotations

import numpy as np
import pytest
from PIL import Image

from sparagmos.effects import EffectContext, register_effect
from sparagmos.effects.sonify import SonifyEffect


@pytest.fixture
def effect():
    e = SonifyEffect()
    register_effect(e)
    return e


@pytest.fixture
def context(tmp_path):
    return EffectContext(vision=None, temp_dir=tmp_path, seed=42, source_metadata={})


def test_apply_produces_valid_image(effect, test_image_rgb, context):
    result = effect.apply(test_image_rgb, {"effect": "reverb", "intensity": 0.5}, context)
    assert isinstance(result.image, Image.Image)
    assert result.image.size == test_image_rgb.size
    assert result.image.mode == "RGB"


def test_apply_modifies_image(effect, test_image_rgb, context):
    result = effect.apply(test_image_rgb, {"effect": "distortion", "intensity": 0.8}, context)
    orig = np.array(test_image_rgb)
    out = np.array(result.image)
    assert not np.array_equal(orig, out)


def test_validate_params_defaults(effect):
    params = effect.validate_params({})
    assert params["effect"] == "reverb"
    assert params["intensity"] == 0.5


def test_works_with_tiny_image(effect, test_image_tiny, context):
    result = effect.apply(test_image_tiny, {}, context)
    assert isinstance(result.image, Image.Image)
    assert result.image.size == test_image_tiny.size


def test_all_effects_produce_valid_output(effect, test_image_rgb, context):
    for dsp in ("reverb", "echo", "distortion", "phaser"):
        result = effect.apply(test_image_rgb, {"effect": dsp, "intensity": 0.6}, context)
        assert result.image.size == test_image_rgb.size
        assert result.image.mode == "RGB"
        arr = np.array(result.image)
        assert arr.min() >= 0
        assert arr.max() <= 255


def test_validate_params_clamps_intensity(effect):
    params = effect.validate_params({"intensity": 5.0})
    assert params["intensity"] == 1.0
    params = effect.validate_params({"intensity": -1.0})
    assert params["intensity"] == 0.0


def test_validate_params_invalid_effect(effect):
    from sparagmos.effects import ConfigError
    with pytest.raises(ConfigError):
        effect.validate_params({"effect": "invalid"})
