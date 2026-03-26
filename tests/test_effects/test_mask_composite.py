"""Tests for mask_composite compositing effect."""

from __future__ import annotations

import numpy as np
import pytest
from PIL import Image

from sparagmos.effects import ConfigError, EffectContext
from sparagmos.effects.mask_composite import MaskCompositeEffect


@pytest.fixture
def effect():
    return MaskCompositeEffect()


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
def gradient_image():
    """Horizontal gradient: left=black (0), right=white (255)."""
    arr = np.zeros((64, 64, 3), dtype=np.uint8)
    for x in range(64):
        val = int(x / 63 * 255)
        arr[:, x, :] = val
    return Image.fromarray(arr, mode="RGB")


def test_mask_luminance_threshold(effect, effect_context, gradient_image, white_image):
    """Gradient image as base + white image; luminance mask produces valid output."""
    result = effect.compose(
        [gradient_image, white_image],
        {"mask_source": "luminance", "threshold": 128, "feather": 0, "invert": False},
        effect_context,
    )
    arr = np.array(result.image)
    assert arr.shape == (64, 64, 3)
    assert arr.dtype == np.uint8
    # Left half of gradient < 128 → mask=0 → shows reveal (white=255)
    # Right half >= 128 → mask=255 → shows base (gradient values)
    left_mean = arr[:, :32, :].mean()
    right_mean = arr[:, 32:, :].mean()
    assert left_mean > right_mean, "Left (reveal=white) should be brighter than right (base=dark gradient)"


def test_mask_edges(effect, effect_context):
    """Image with sharp black/white edge + red image; edges mode produces valid output."""
    # Left half black, right half white — sharp vertical edge in the middle
    arr = np.zeros((64, 64, 3), dtype=np.uint8)
    arr[:, 32:, :] = 255
    edge_image = Image.fromarray(arr, mode="RGB")

    red_arr = np.zeros((64, 64, 3), dtype=np.uint8)
    red_arr[:, :, 0] = 255
    red_image = Image.fromarray(red_arr, mode="RGB")

    result = effect.compose(
        [edge_image, red_image],
        {"mask_source": "edges", "threshold": 100, "feather": 0, "invert": False},
        effect_context,
    )
    arr_out = np.array(result.image)
    assert arr_out.shape == (64, 64, 3)
    assert arr_out.dtype == np.uint8


def test_mask_noise(effect, effect_context, white_image, black_image):
    """White + black with noise mask; output should contain multiple unique values."""
    result = effect.compose(
        [white_image, black_image],
        {"mask_source": "noise", "threshold": 128, "feather": 0, "invert": False},
        effect_context,
    )
    arr = np.array(result.image)
    assert arr.shape == (64, 64, 3)
    # Noise mask selects between white (255) and black (0); should have both
    unique_vals = np.unique(arr)
    assert len(unique_vals) > 1, "Noise mask should produce a mix of values, not a solid image"


def test_mask_gradient(effect, effect_context, white_image, black_image):
    """Gradient mask source produces valid output."""
    result = effect.compose(
        [white_image, black_image],
        {"mask_source": "gradient", "threshold": 128, "feather": 0, "invert": False},
        effect_context,
    )
    arr = np.array(result.image)
    assert arr.shape == (64, 64, 3)
    assert arr.dtype == np.uint8


def test_mask_invert(effect, effect_context, gradient_image, white_image):
    """Inverted result should differ from non-inverted result."""
    params_normal = {"mask_source": "luminance", "threshold": 128, "feather": 0, "invert": False}
    params_inverted = {"mask_source": "luminance", "threshold": 128, "feather": 0, "invert": True}

    result_normal = effect.compose([gradient_image, white_image], params_normal, effect_context)
    result_inverted = effect.compose([gradient_image, white_image], params_inverted, effect_context)

    arr_normal = np.array(result_normal.image)
    arr_inverted = np.array(result_inverted.image)

    assert not np.array_equal(arr_normal, arr_inverted), "Inverted result should differ from normal"


def test_mask_feather(effect, effect_context, gradient_image, white_image):
    """feather=10 produces different result than feather=0."""
    params_no_feather = {"mask_source": "luminance", "threshold": 128, "feather": 0, "invert": False}
    params_feather = {"mask_source": "luminance", "threshold": 128, "feather": 10, "invert": False}

    result_no_feather = effect.compose([gradient_image, white_image], params_no_feather, effect_context)
    result_feather = effect.compose([gradient_image, white_image], params_feather, effect_context)

    arr_no_feather = np.array(result_no_feather.image)
    arr_feather = np.array(result_feather.image)

    assert not np.array_equal(arr_no_feather, arr_feather), "Feathered result should differ from sharp-edged"


def test_mask_mismatched_sizes(effect, effect_context):
    """First image 64x64, second 32x32 — output should match first image size."""
    base = Image.fromarray(np.full((64, 64, 3), 200, dtype=np.uint8), mode="RGB")
    small = Image.fromarray(np.zeros((32, 32, 3), dtype=np.uint8), mode="RGB")

    result = effect.compose(
        [base, small],
        {"mask_source": "luminance", "threshold": 128, "feather": 0, "invert": False},
        effect_context,
    )
    assert result.image.size == (64, 64), f"Output size should be (64, 64), got {result.image.size}"


def test_mask_validate_bad_source(effect):
    """Unknown mask_source should raise ConfigError."""
    with pytest.raises(ConfigError):
        effect.validate_params({"mask_source": "rainbow"})
