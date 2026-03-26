"""Tests for blend compositing effect."""

from __future__ import annotations

import numpy as np
import pytest
from PIL import Image

from sparagmos.effects import ConfigError, EffectContext
from sparagmos.effects.blend import BlendEffect


@pytest.fixture
def effect():
    return BlendEffect()


@pytest.fixture
def effect_context(tmp_path):
    return EffectContext(vision=None, temp_dir=tmp_path, seed=42, source_metadata={})


@pytest.fixture
def white_image():
    arr = np.full((64, 64, 3), 255, dtype=np.uint8)
    return Image.fromarray(arr, mode="RGB")


@pytest.fixture
def black_image():
    arr = np.zeros((64, 64, 3), dtype=np.uint8)
    return Image.fromarray(arr, mode="RGB")


@pytest.fixture
def red_image():
    arr = np.zeros((64, 64, 3), dtype=np.uint8)
    arr[:, :, 0] = 255
    return Image.fromarray(arr, mode="RGB")


@pytest.fixture
def blue_image():
    arr = np.zeros((64, 64, 3), dtype=np.uint8)
    arr[:, :, 2] = 255
    return Image.fromarray(arr, mode="RGB")


def test_blend_opacity_50(effect, effect_context, white_image, black_image):
    """White + black at strength=0.5 should give ~127 gray."""
    result = effect.compose(
        [white_image, black_image],
        {"mode": "opacity", "strength": 0.5, "offset_x": 0.0, "offset_y": 0.0},
        effect_context,
    )
    arr = np.array(result.image)
    # base=255, blended=0, result = 255 + 0.5*(0-255) = 127.5 → 127
    assert arr.mean() == pytest.approx(127.5, abs=1.0)


def test_blend_opacity_zero_returns_first(effect, effect_context, white_image, black_image):
    """strength=0.0 should return the first image unchanged."""
    result = effect.compose(
        [white_image, black_image],
        {"mode": "opacity", "strength": 0.0, "offset_x": 0.0, "offset_y": 0.0},
        effect_context,
    )
    arr = np.array(result.image)
    np.testing.assert_array_equal(arr, np.array(white_image))


def test_blend_multiply(effect, effect_context, white_image, red_image):
    """white * red = red (white * color / 255 = color)."""
    result = effect.compose(
        [white_image, red_image],
        {"mode": "multiply", "strength": 1.0, "offset_x": 0.0, "offset_y": 0.0},
        effect_context,
    )
    arr = np.array(result.image)
    # base=white(255,255,255), over=red(255,0,0)
    # multiply: (255*255/255, 255*0/255, 255*0/255) = (255, 0, 0) = red
    np.testing.assert_array_equal(arr, np.array(red_image))


def test_blend_screen(effect, effect_context, black_image, red_image):
    """screen(black, red) = red."""
    result = effect.compose(
        [black_image, red_image],
        {"mode": "screen", "strength": 1.0, "offset_x": 0.0, "offset_y": 0.0},
        effect_context,
    )
    arr = np.array(result.image)
    # base=black(0,0,0), over=red(255,0,0)
    # screen: 255 - (255-0)*(255-255)/255 = 255 - 0 = 255 for R
    #         255 - (255-0)*(255-0)/255 = 255 - 255 = 0 for G, B
    np.testing.assert_array_equal(arr, np.array(red_image))


def test_blend_difference(effect, effect_context, white_image):
    """Same image differenced = black (zero)."""
    result = effect.compose(
        [white_image, white_image],
        {"mode": "difference", "strength": 1.0, "offset_x": 0.0, "offset_y": 0.0},
        effect_context,
    )
    arr = np.array(result.image)
    assert arr.max() == 0


def test_blend_mismatched_sizes(effect, effect_context):
    """Small overlay resized to match base dimensions."""
    base = Image.fromarray(np.full((64, 64, 3), 100, dtype=np.uint8), mode="RGB")
    small_over = Image.fromarray(np.full((32, 32, 3), 200, dtype=np.uint8), mode="RGB")
    result = effect.compose(
        [base, small_over],
        {"mode": "opacity", "strength": 1.0, "offset_x": 0.0, "offset_y": 0.0},
        effect_context,
    )
    assert result.image.size == base.size


def test_blend_with_offset(effect, effect_context, white_image, black_image):
    """offset_x=0.5 shifts overlay right by half width; left half shows base."""
    result = effect.compose(
        [white_image, black_image],
        {"mode": "opacity", "strength": 1.0, "offset_x": 0.5, "offset_y": 0.0},
        effect_context,
    )
    arr = np.array(result.image)
    w = white_image.width
    half = w // 2
    # Left half: overlay doesn't cover → shows base (white = 255)
    left_mean = arr[:, :half, :].mean()
    # Right half: overlay covers → shows black = 0
    right_mean = arr[:, half:, :].mean()
    assert left_mean > 200, f"Left half should be mostly white, got {left_mean}"
    assert right_mean < 55, f"Right half should be mostly black, got {right_mean}"


def test_blend_validate_bad_mode(effect):
    """Unknown blend mode should raise ConfigError."""
    with pytest.raises(ConfigError):
        effect.validate_params({"mode": "dissolve"})


def test_blend_overlay(effect, effect_context, white_image, black_image):
    """Overlay mode produces valid output without errors."""
    result = effect.compose(
        [white_image, black_image],
        {"mode": "overlay", "strength": 1.0, "offset_x": 0.0, "offset_y": 0.0},
        effect_context,
    )
    arr = np.array(result.image)
    assert arr.shape == (64, 64, 3)
    assert arr.dtype == np.uint8
