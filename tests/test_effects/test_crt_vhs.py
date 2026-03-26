"""Tests for crt_vhs effect."""

import numpy as np
import pytest
from PIL import Image

from sparagmos.effects import ConfigError, EffectContext, register_effect
from sparagmos.effects.crt_vhs import CrtVhsEffect


@pytest.fixture
def effect():
    e = CrtVhsEffect()
    register_effect(e)
    return e


@pytest.fixture
def context(tmp_path):
    return EffectContext(vision=None, temp_dir=tmp_path, seed=42, source_metadata={})


def test_apply_produces_valid_image(effect, test_image_rgb, context):
    params = {
        "scan_line_density": 3,
        "jitter_amount": 2,
        "color_bleed": 1.5,
        "phosphor_glow": 0.1,
    }
    result = effect.apply(test_image_rgb, params, context)
    assert result.image.size == test_image_rgb.size
    assert result.image.mode == "RGB"


def test_apply_modifies_image(effect, test_image_rgb, context):
    params = {
        "scan_line_density": 3,
        "jitter_amount": 5,
        "color_bleed": 2.0,
        "phosphor_glow": 0.2,
    }
    result = effect.apply(test_image_rgb, params, context)
    orig = np.array(test_image_rgb)
    out = np.array(result.image)
    assert not np.array_equal(orig, out)


def test_validate_params_defaults(effect):
    params = effect.validate_params({})
    assert params["scan_line_density"] == 3
    assert params["jitter_amount"] == 2
    assert abs(params["color_bleed"] - 1.5) < 1e-6
    assert abs(params["phosphor_glow"] - 0.1) < 1e-6


def test_validate_params_clamps(effect):
    params = effect.validate_params({"phosphor_glow": 5.0, "scan_line_density": -1})
    assert params["phosphor_glow"] <= 1.0
    assert params["scan_line_density"] >= 0


def test_works_with_tiny_image(effect, test_image_tiny, context):
    params = {
        "scan_line_density": 2,
        "jitter_amount": 1,
        "color_bleed": 0.5,
        "phosphor_glow": 0.05,
    }
    result = effect.apply(test_image_tiny, params, context)
    assert result.image.size == test_image_tiny.size


def test_zero_params_is_near_identity(effect, test_image_rgb, context):
    """With all effects disabled, output should equal input (modulo float rounding)."""
    params = {
        "scan_line_density": 0,
        "jitter_amount": 0,
        "color_bleed": 0.0,
        "phosphor_glow": 0.0,
    }
    result = effect.apply(test_image_rgb, params, context)
    orig = np.array(test_image_rgb)
    out = np.array(result.image)
    np.testing.assert_array_equal(orig, out)


def test_metadata_contains_all_params(effect, test_image_rgb, context):
    params = {
        "scan_line_density": 4,
        "jitter_amount": 3,
        "color_bleed": 1.0,
        "phosphor_glow": 0.15,
    }
    result = effect.apply(test_image_rgb, params, context)
    assert "scan_line_density" in result.metadata
    assert "jitter_amount" in result.metadata
    assert "color_bleed" in result.metadata
    assert "phosphor_glow" in result.metadata
