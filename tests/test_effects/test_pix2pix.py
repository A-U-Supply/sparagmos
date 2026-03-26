"""Tests for the pix2pix effect."""

from __future__ import annotations

import numpy as np
import pytest
from PIL import Image

from sparagmos.effects import ConfigError, EffectContext
from sparagmos.effects.pix2pix import Pix2PixEffect


@pytest.fixture
def effect():
    return Pix2PixEffect()


@pytest.fixture
def context(tmp_path):
    return EffectContext(vision=None, temp_dir=tmp_path, seed=42, source_metadata={})


def test_apply_produces_valid_image(effect, test_image_rgb, context):
    result = effect.apply(test_image_rgb, {}, context)
    assert isinstance(result.image, Image.Image)
    assert result.image.mode == "RGB"
    assert result.image.size == test_image_rgb.size


def test_apply_modifies_image(effect, test_image_rgb, context):
    result = effect.apply(test_image_rgb, {}, context)
    orig = np.array(test_image_rgb)
    out = np.array(result.image)
    assert not np.array_equal(orig, out)


def test_validate_params_defaults(effect):
    params = effect.validate_params({})
    assert params["model"] == "zebra"
    assert params["direction"] == "AtoB"
    assert params["intensity"] == pytest.approx(0.7)


def test_validate_params_clamps_intensity(effect):
    params = effect.validate_params({"intensity": 5.0})
    assert params["intensity"] == pytest.approx(1.0)

    params = effect.validate_params({"intensity": -1.0})
    assert params["intensity"] == pytest.approx(0.0)


def test_validate_params_invalid_model(effect):
    with pytest.raises(ConfigError):
        effect.validate_params({"model": "doesnotexist"})


def test_validate_params_invalid_direction(effect):
    with pytest.raises(ConfigError):
        effect.validate_params({"direction": "sideways"})


@pytest.mark.parametrize("model", ["zebra", "monet", "vangogh", "ukiyoe"])
def test_all_models_produce_valid_images(effect, test_image_rgb, context, model):
    result = effect.apply(test_image_rgb, {"model": model}, context)
    assert result.image.mode == "RGB"
    assert result.image.size == test_image_rgb.size


@pytest.mark.parametrize("direction", ["AtoB", "BtoA"])
def test_both_directions(effect, test_image_rgb, context, direction):
    result = effect.apply(test_image_rgb, {"direction": direction}, context)
    assert result.image.size == test_image_rgb.size


def test_works_with_tiny_image(effect, context):
    tiny = Image.new("RGB", (16, 16), color=(128, 64, 32))
    result = effect.apply(tiny, {}, context)
    assert result.image.size == (16, 16)


def test_metadata_contains_params(effect, test_image_rgb, context):
    result = effect.apply(test_image_rgb, {"model": "monet", "intensity": 0.5}, context)
    assert result.metadata["model"] == "monet"
    assert result.metadata["intensity"] == pytest.approx(0.5)
