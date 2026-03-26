"""Tests for the inpaint effect."""

from __future__ import annotations

import numpy as np
import pytest
from PIL import Image

try:
    import cv2
    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False

pytestmark = pytest.mark.skipif(not HAS_CV2, reason="OpenCV not installed")

from sparagmos.effects import ConfigError, EffectContext
from sparagmos.effects.inpaint import InpaintEffect


@pytest.fixture
def effect():
    return InpaintEffect()


@pytest.fixture
def context(tmp_path):
    return EffectContext(vision=None, temp_dir=tmp_path, seed=42, source_metadata={})


def test_apply_produces_valid_image(effect, test_image_rgb, context):
    result = effect.apply(test_image_rgb, {}, context)
    assert isinstance(result.image, Image.Image)
    assert result.image.mode == "RGB"
    assert result.image.size == test_image_rgb.size


def test_apply_modifies_image(effect, test_image_rgb, context):
    result = effect.apply(test_image_rgb, {"mask_size": 0.4, "num_masks": 5}, context)
    orig = np.array(test_image_rgb)
    out = np.array(result.image)
    assert not np.array_equal(orig, out)


def test_validate_params_defaults(effect):
    params = effect.validate_params({})
    assert params["mask_mode"] == "random_rect"
    assert params["mask_size"] == pytest.approx(0.2)
    assert params["method"] == "telea"
    assert params["num_masks"] == 3


def test_validate_params_invalid_mask_mode(effect):
    with pytest.raises(ConfigError):
        effect.validate_params({"mask_mode": "laser_guided"})


def test_validate_params_invalid_method(effect):
    with pytest.raises(ConfigError):
        effect.validate_params({"method": "magic"})


def test_validate_params_clamps_mask_size(effect):
    params = effect.validate_params({"mask_size": 0.0})
    assert params["mask_size"] == pytest.approx(0.05)

    params = effect.validate_params({"mask_size": 5.0})
    assert params["mask_size"] == pytest.approx(0.5)


def test_validate_params_clamps_num_masks(effect):
    params = effect.validate_params({"num_masks": 0})
    assert params["num_masks"] == 1

    params = effect.validate_params({"num_masks": 999})
    assert params["num_masks"] == 10


def test_works_with_tiny_image(effect, context):
    tiny = Image.new("RGB", (16, 16), color=(80, 160, 240))
    result = effect.apply(tiny, {"num_masks": 1, "mask_size": 0.1}, context)
    assert result.image.size == (16, 16)


@pytest.mark.parametrize("mask_mode", ["random_rect", "random_circle", "vision"])
def test_all_mask_modes(effect, test_image_rgb, context, mask_mode):
    result = effect.apply(test_image_rgb, {"mask_mode": mask_mode}, context)
    assert result.image.size == test_image_rgb.size


@pytest.mark.parametrize("method", ["telea", "ns"])
def test_both_methods(effect, test_image_rgb, context, method):
    result = effect.apply(test_image_rgb, {"method": method}, context)
    assert result.image.size == test_image_rgb.size


def test_metadata_contains_params(effect, test_image_rgb, context):
    result = effect.apply(test_image_rgb, {"method": "ns", "num_masks": 2}, context)
    assert result.metadata["method"] == "ns"
    assert result.metadata["num_masks"] == 2
    assert "mask_coverage" in result.metadata
