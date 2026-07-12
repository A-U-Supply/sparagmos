"""Tests for tone effect."""

import numpy as np
import pytest
from PIL import Image

from sparagmos.effects import ConfigError, EffectContext
from sparagmos.effects.tone_effect import ToneEffect


@pytest.fixture
def effect():
    return ToneEffect()


@pytest.fixture
def context(tmp_path):
    return EffectContext(vision=None, temp_dir=tmp_path, seed=42, source_metadata={})


@pytest.fixture
def gradient_image():
    arr = np.tile(np.linspace(0, 255, 128, dtype=np.uint8), (64, 1))
    return Image.fromarray(np.stack([arr, arr, arr], axis=2))


@pytest.mark.parametrize("mode", ["none", "grayscale", "binary", "posterize", "normalize", "invert"])
def test_all_modes_produce_valid_image(effect, gradient_image, context, mode):
    result = effect.apply(gradient_image, {"mode": mode}, context)
    assert result.image.size == gradient_image.size
    assert result.image.mode == "RGB"


def test_binary_output_is_pure(effect, gradient_image, context):
    result = effect.apply(gradient_image, {"mode": "binary"}, context)
    values = np.unique(np.array(result.image))
    assert set(values.tolist()) <= {0, 255}


def test_binary_fixed_threshold(effect, gradient_image, context):
    result = effect.apply(gradient_image, {"mode": "binary", "threshold": 200}, context)
    arr = np.array(result.image)
    # Most of a linear 0-255 gradient sits below 200 -> mostly black
    assert (arr == 0).mean() > 0.6


def test_posterize_reduces_levels(effect, gradient_image, context):
    result = effect.apply(gradient_image, {"mode": "posterize", "levels": 3}, context)
    values = np.unique(np.array(result.image))
    assert len(values) <= 3


def test_normalize_stretches_range(effect, context):
    arr = np.full((64, 64, 3), 128, dtype=np.uint8)
    arr[:32] = 100
    arr[32:] = 156
    result = effect.apply(Image.fromarray(arr), {"mode": "normalize", "cutoff": 0.0}, context)
    out = np.array(result.image)
    assert out.min() < 20 and out.max() > 235


def test_invert(effect, gradient_image, context):
    result = effect.apply(gradient_image, {"mode": "invert"}, context)
    orig = np.array(gradient_image)
    assert np.array_equal(np.array(result.image), 255 - orig)


@pytest.mark.parametrize("tint", ["cyanotype", "silver", "sepia", "bronze", "ink"])
def test_tints_produce_valid_image(effect, gradient_image, context, tint):
    result = effect.apply(gradient_image, {"tint": tint}, context)
    assert result.image.size == gradient_image.size
    assert result.image.mode == "RGB"


def test_ink_choice_is_seeded_and_recorded(effect, gradient_image, context):
    r1 = effect.apply(gradient_image, {"tint": "ink"}, context)
    r2 = effect.apply(gradient_image, {"tint": "ink"}, context)
    assert r1.metadata["ink"] == r2.metadata["ink"]


def test_unknown_mode_raises(effect):
    with pytest.raises(ConfigError):
        effect.validate_params({"mode": "sparkle"})


def test_unknown_tint_raises(effect):
    with pytest.raises(ConfigError):
        effect.validate_params({"tint": "gold-leaf"})


def test_unknown_ink_raises(effect):
    with pytest.raises(ConfigError):
        effect.validate_params({"tint": "ink", "inks": ["crimson", "chartreuse"]})


def test_params_clamped(effect):
    validated = effect.validate_params({"levels": 99, "cutoff": 50, "threshold": 999})
    assert validated["levels"] == 8
    assert validated["cutoff"] == 5.0
    assert validated["threshold"] == 255
