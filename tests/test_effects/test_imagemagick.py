"""Tests for the ImageMagick effect."""

from __future__ import annotations

import shutil

import pytest
from PIL import Image

from sparagmos.effects import ConfigError, EffectContext, register_effect
from sparagmos.effects.imagemagick import ImageMagickEffect

HAS_IMAGEMAGICK = (
    shutil.which("convert") is not None or shutil.which("magick") is not None
)
pytestmark = pytest.mark.skipif(
    not HAS_IMAGEMAGICK, reason="ImageMagick not installed"
)


@pytest.fixture
def effect():
    e = ImageMagickEffect()
    register_effect(e)
    return e


@pytest.fixture
def context(tmp_path):
    return EffectContext(vision=None, temp_dir=tmp_path, seed=42, source_metadata={})


def test_apply_produces_valid_image(effect, test_image_rgb, context):
    params = {"preset": "swirl", "degrees": 45}
    result = effect.apply(test_image_rgb, params, context)
    assert result.image.size == test_image_rgb.size
    assert result.image.mode == "RGB"


def test_validate_params_defaults(effect):
    params = effect.validate_params({})
    assert params["preset"] == "swirl"
    assert "degrees" in params


def test_validate_params_implode(effect):
    params = effect.validate_params({"preset": "implode", "amount": 0.8})
    assert params["preset"] == "implode"
    assert params["amount"] == pytest.approx(0.8)


def test_validate_params_wave(effect):
    params = effect.validate_params({"preset": "wave", "amplitude": 15, "wavelength": 60})
    assert params["amplitude"] == 15
    assert params["wavelength"] == 60


def test_validate_params_invalid_preset_raises(effect):
    with pytest.raises(ConfigError):
        effect.validate_params({"preset": "nonexistent"})


def test_works_with_tiny_image(effect, test_image_tiny, context):
    params = {"preset": "swirl", "degrees": 30}
    result = effect.apply(test_image_tiny, params, context)
    assert result.image.mode == "RGB"


def test_preset_implode(effect, test_image_rgb, context):
    params = {"preset": "implode", "amount": 0.5}
    result = effect.apply(test_image_rgb, params, context)
    assert result.image.size == test_image_rgb.size


def test_preset_wave(effect, test_image_rgb, context):
    params = {"preset": "wave", "amplitude": 5, "wavelength": 30}
    result = effect.apply(test_image_rgb, params, context)
    assert result.image.mode == "RGB"


def test_preset_fx_noise(effect, test_image_rgb, context):
    params = {"preset": "fx_noise"}
    result = effect.apply(test_image_rgb, params, context)
    assert result.image.mode == "RGB"


def test_preset_plasma_overlay(effect, test_image_rgb, context):
    params = {"preset": "plasma_overlay"}
    result = effect.apply(test_image_rgb, params, context)
    assert result.image.mode == "RGB"


def test_metadata_contains_preset(effect, test_image_rgb, context):
    params = {"preset": "swirl"}
    result = effect.apply(test_image_rgb, params, context)
    assert result.metadata["preset"] == "swirl"
