"""Tests for the format roundtrip effect."""

from __future__ import annotations

import pytest
from PIL import Image

from sparagmos.effects import ConfigError, EffectContext, register_effect
from sparagmos.effects.format_roundtrip import FormatRoundtripEffect

# format_roundtrip has no hard system deps (JPEG/BMP are handled by Pillow)
pytestmark = pytest.mark.skipif(False, reason="always run")


@pytest.fixture
def effect():
    e = FormatRoundtripEffect()
    register_effect(e)
    return e


@pytest.fixture
def context(tmp_path):
    return EffectContext(vision=None, temp_dir=tmp_path, seed=42, source_metadata={})


def test_apply_produces_valid_image(effect, test_image_rgb, context):
    params = {"chain": ["jpeg", "bmp", "jpeg"], "jpeg_quality": 10}
    result = effect.apply(test_image_rgb, params, context)
    assert result.image.size == test_image_rgb.size
    assert result.image.mode == "RGB"


def test_validate_params_defaults(effect):
    params = effect.validate_params({})
    assert params["chain"] == ["jpeg", "bmp", "jpeg"]
    assert params["jpeg_quality"] == 10


def test_validate_params_jpeg_quality_clamped(effect):
    params = effect.validate_params({"jpeg_quality": 0})
    assert params["jpeg_quality"] >= 1
    params = effect.validate_params({"jpeg_quality": 999})
    assert params["jpeg_quality"] <= 95


def test_validate_params_invalid_format_raises(effect):
    with pytest.raises(ConfigError):
        effect.validate_params({"chain": ["jpeg", "notaformat"]})


def test_works_with_tiny_image(effect, test_image_tiny, context):
    params = {"chain": ["jpeg"], "jpeg_quality": 5}
    result = effect.apply(test_image_tiny, params, context)
    assert result.image.mode == "RGB"


def test_jpeg_only_chain(effect, test_image_rgb, context):
    params = {"chain": ["jpeg", "jpeg", "jpeg"], "jpeg_quality": 5}
    result = effect.apply(test_image_rgb, params, context)
    assert result.image.mode == "RGB"


def test_bmp_only_chain(effect, test_image_rgb, context):
    params = {"chain": ["bmp"], "jpeg_quality": 10}
    result = effect.apply(test_image_rgb, params, context)
    assert result.image.size == test_image_rgb.size


def test_metadata_chain_applied(effect, test_image_rgb, context):
    params = {"chain": ["jpeg", "bmp"], "jpeg_quality": 20}
    result = effect.apply(test_image_rgb, params, context)
    assert result.metadata["chain_applied"] == ["jpeg", "bmp"]


def test_jpeg_introduces_artifacts(effect, test_image_rgb, context):
    """Low quality JPEG should change pixel values."""
    import numpy as np

    params = {"chain": ["jpeg"], "jpeg_quality": 1}
    result = effect.apply(test_image_rgb, params, context)
    orig = np.array(test_image_rgb.convert("RGB"))
    out = np.array(result.image)
    assert not (orig == out).all(), "JPEG roundtrip should introduce differences"


def test_empty_chain(effect, test_image_rgb, context):
    params = {"chain": [], "jpeg_quality": 10}
    result = effect.apply(test_image_rgb, params, context)
    assert result.image.mode == "RGB"
