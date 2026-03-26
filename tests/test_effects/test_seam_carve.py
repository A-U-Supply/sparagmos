"""Tests for seam carving effect."""

import numpy as np
import pytest
from PIL import Image

from sparagmos.effects import EffectContext, register_effect
from sparagmos.effects.seam_carve import SeamCarveEffect


@pytest.fixture
def effect():
    e = SeamCarveEffect()
    register_effect(e)
    return e


@pytest.fixture
def context(tmp_path):
    return EffectContext(vision=None, temp_dir=tmp_path, seed=42, source_metadata={})


def test_apply_produces_valid_image(effect, test_image_rgb, context):
    params = {"scale_x": 0.9, "scale_y": 1.0, "protect_regions": "none"}
    result = effect.apply(test_image_rgb, params, context)
    assert isinstance(result.image, Image.Image)
    assert result.image.mode == "RGB"


def test_validate_params_defaults(effect):
    params = effect.validate_params({})
    assert params["scale_x"] == 0.7
    assert params["scale_y"] == 1.0
    assert params["protect_regions"] == "none"


def test_works_with_tiny_image(effect, context):
    tiny = Image.new("RGB", (8, 8), color=(200, 100, 50))
    params = {"scale_x": 0.75, "scale_y": 1.0, "protect_regions": "none"}
    result = effect.apply(tiny, params, context)
    assert isinstance(result.image, Image.Image)


def test_output_width_reduced(effect, context):
    img = Image.new("RGB", (64, 64))
    pixels = img.load()
    for x in range(64):
        for y in range(64):
            pixels[x, y] = ((x * 4) % 256, (y * 4) % 256, ((x + y) * 2) % 256)

    params = {"scale_x": 0.5, "scale_y": 1.0, "protect_regions": "none"}
    result = effect.apply(img, params, context)
    out_w, out_h = result.image.size
    assert out_w <= 35  # roughly half of 64, with some tolerance
    assert out_h == 64


def test_invert_mode(effect, context):
    img = Image.new("RGB", (32, 32))
    pixels = img.load()
    for x in range(32):
        for y in range(32):
            pixels[x, y] = ((x * 8) % 256, (y * 8) % 256, ((x + y) * 4) % 256)

    params_none = {"scale_x": 0.8, "scale_y": 1.0, "protect_regions": "none"}
    params_invert = {"scale_x": 0.8, "scale_y": 1.0, "protect_regions": "invert"}

    result_none = effect.apply(img, params_none, context)
    result_invert = effect.apply(img, params_invert, context)

    arr_none = np.array(result_none.image)
    arr_invert = np.array(result_invert.image)

    # Both should have same shape
    assert arr_none.shape == arr_invert.shape
    # But different pixel content (different seams removed)
    assert not np.array_equal(arr_none, arr_invert)


def test_validate_params_rejects_invalid_protect_mode(effect):
    with pytest.raises(Exception):
        effect.validate_params({"protect_regions": "magic"})


def test_validate_params_rejects_bad_scale(effect):
    with pytest.raises(Exception):
        effect.validate_params({"scale_x": 0.0})

    with pytest.raises(Exception):
        effect.validate_params({"scale_x": 1.5})

    with pytest.raises(Exception):
        effect.validate_params({"scale_y": -0.1})
