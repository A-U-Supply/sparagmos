"""Tests for the primitive effect."""

from __future__ import annotations

import shutil

import pytest
from PIL import Image

from sparagmos.effects import ConfigError, EffectContext, register_effect
from sparagmos.effects.primitive import PrimitiveEffect

HAS_PRIMITIVE = shutil.which("primitive") is not None
pytestmark = pytest.mark.skipif(not HAS_PRIMITIVE, reason="primitive not installed")


@pytest.fixture
def effect():
    e = PrimitiveEffect()
    register_effect(e)
    return e


@pytest.fixture
def context(tmp_path):
    return EffectContext(vision=None, temp_dir=tmp_path, seed=42, source_metadata={})


def test_apply_produces_valid_image(effect, test_image_rgb, context):
    params = {"shapes": 10, "shape_type": "triangle", "alpha": 128}
    result = effect.apply(test_image_rgb, params, context)
    assert result.image.size == test_image_rgb.size
    assert result.image.mode == "RGB"


def test_validate_params_defaults(effect):
    params = effect.validate_params({})
    assert params["shapes"] == 50
    assert params["shape_type"] == "triangle"
    assert params["alpha"] == 128


def test_validate_params_invalid_shape_type_raises(effect):
    with pytest.raises(ConfigError):
        effect.validate_params({"shape_type": "hexagon"})


def test_validate_params_alpha_clamped(effect):
    params = effect.validate_params({"alpha": -10})
    assert params["alpha"] == 0
    params = effect.validate_params({"alpha": 999})
    assert params["alpha"] == 255


def test_validate_params_shapes_min(effect):
    with pytest.raises(ConfigError):
        effect.validate_params({"shapes": 0})


def test_works_with_tiny_image(effect, test_image_tiny, context):
    params = {"shapes": 5, "shape_type": "circle", "alpha": 200}
    result = effect.apply(test_image_tiny, params, context)
    assert result.image.mode == "RGB"


def test_shape_types(effect, test_image_rgb, context):
    for shape in ("triangle", "rectangle", "ellipse", "circle", "rotated_rect"):
        params = {"shapes": 5, "shape_type": shape, "alpha": 128}
        result = effect.apply(test_image_rgb, params, context)
        assert result.image.mode == "RGB"


def test_metadata_contains_shape_info(effect, test_image_rgb, context):
    params = {"shapes": 10, "shape_type": "ellipse", "alpha": 100}
    result = effect.apply(test_image_rgb, params, context)
    assert result.metadata["shapes"] == 10
    assert result.metadata["shape_type"] == "ellipse"
    assert result.metadata["alpha"] == 100
