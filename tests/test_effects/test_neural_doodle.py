"""Tests for the neural_doodle effect."""

from __future__ import annotations

import numpy as np
import pytest
from PIL import Image

from sparagmos.effects import ConfigError, EffectContext
from sparagmos.effects.neural_doodle import NeuralDoodleEffect


@pytest.fixture
def effect():
    return NeuralDoodleEffect()


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
    assert params["num_regions"] == 5
    assert params["region_size"] == pytest.approx(0.3)
    assert params["intensity"] == pytest.approx(0.8)


def test_validate_params_clamps_num_regions(effect):
    params = effect.validate_params({"num_regions": 100})
    assert params["num_regions"] == 20

    params = effect.validate_params({"num_regions": 0})
    assert params["num_regions"] == 1


def test_validate_params_clamps_region_size(effect):
    params = effect.validate_params({"region_size": 0.0})
    assert params["region_size"] == pytest.approx(0.1)

    params = effect.validate_params({"region_size": 2.0})
    assert params["region_size"] == pytest.approx(0.5)


def test_validate_params_clamps_intensity(effect):
    params = effect.validate_params({"intensity": -1.0})
    assert params["intensity"] == pytest.approx(0.0)

    params = effect.validate_params({"intensity": 10.0})
    assert params["intensity"] == pytest.approx(1.0)


def test_works_with_tiny_image(effect, context):
    tiny = Image.new("RGB", (16, 16), color=(100, 150, 200))
    result = effect.apply(tiny, {"num_regions": 2, "region_size": 0.2}, context)
    assert result.image.size == (16, 16)


def test_many_regions_does_not_crash(effect, test_image_rgb, context):
    result = effect.apply(test_image_rgb, {"num_regions": 20}, context)
    assert result.image.size == test_image_rgb.size


def test_metadata_contains_params(effect, test_image_rgb, context):
    result = effect.apply(test_image_rgb, {"num_regions": 7, "intensity": 0.5}, context)
    assert result.metadata["num_regions"] == 7
    assert result.metadata["intensity"] == pytest.approx(0.5)
