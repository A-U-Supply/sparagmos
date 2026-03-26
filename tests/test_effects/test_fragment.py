"""Tests for fragment compositing effect."""

from __future__ import annotations

import numpy as np
import pytest
from PIL import Image

from sparagmos.effects import ConfigError, EffectContext
from sparagmos.effects.fragment import FragmentEffect


@pytest.fixture
def effect():
    return FragmentEffect()


@pytest.fixture
def effect_context(tmp_path):
    return EffectContext(vision=None, temp_dir=tmp_path, seed=42, source_metadata={})


@pytest.fixture
def colored_pair():
    """Red 64x64 and blue 64x64."""
    red = np.zeros((64, 64, 3), dtype=np.uint8)
    red[:, :, 0] = 255
    blue = np.zeros((64, 64, 3), dtype=np.uint8)
    blue[:, :, 2] = 255
    return [
        Image.fromarray(red, mode="RGB"),
        Image.fromarray(blue, mode="RGB"),
    ]


def _is_valid_rgb_image(img: Image.Image) -> None:
    arr = np.array(img)
    assert arr.ndim == 3
    assert arr.shape[2] == 3
    assert arr.dtype == np.uint8
    assert img.width > 0
    assert img.height > 0


def test_fragment_grid(effect, effect_context, colored_pair):
    """Grid mode with red+blue pair, pieces=16, mix_ratio=1.0 → output has both colors."""
    result = effect.compose(
        colored_pair,
        {"cut_mode": "grid", "pieces": 16, "mix_ratio": 1.0},
        effect_context,
    )
    _is_valid_rgb_image(result.image)
    arr = np.array(result.image)
    # Should have both red and blue pixels
    has_red = np.any((arr[:, :, 0] > 200) & (arr[:, :, 2] < 50))
    has_blue = np.any((arr[:, :, 2] > 200) & (arr[:, :, 0] < 50))
    assert has_red, "Expected red pixels from first image"
    assert has_blue, "Expected blue pixels from second image"


def test_fragment_voronoi(effect, effect_context, colored_pair):
    """Voronoi mode with 2 images, pieces=12 → valid output."""
    result = effect.compose(
        colored_pair,
        {"cut_mode": "voronoi", "pieces": 12},
        effect_context,
    )
    _is_valid_rgb_image(result.image)


def test_fragment_strips(effect, effect_context, colored_pair):
    """Strips mode with 2 images, pieces=8 → valid output."""
    result = effect.compose(
        colored_pair,
        {"cut_mode": "strips", "pieces": 8},
        effect_context,
    )
    _is_valid_rgb_image(result.image)


def test_fragment_shatter(effect, effect_context, colored_pair):
    """Shatter mode with 2 images, pieces=20 → valid output."""
    result = effect.compose(
        colored_pair,
        {"cut_mode": "shatter", "pieces": 20},
        effect_context,
    )
    _is_valid_rgb_image(result.image)


def test_fragment_mix_ratio_zero(effect, effect_context, colored_pair):
    """mix_ratio=0.0 → output is mostly the first image (red)."""
    result = effect.compose(
        colored_pair,
        {"cut_mode": "grid", "pieces": 16, "mix_ratio": 0.0},
        effect_context,
    )
    _is_valid_rgb_image(result.image)
    arr = np.array(result.image)
    # With mix_ratio=0 all pieces should come from first image
    red_pixels = np.sum((arr[:, :, 0] > 200) & (arr[:, :, 2] < 50))
    total_pixels = arr.shape[0] * arr.shape[1]
    assert red_pixels > total_pixels * 0.9, (
        f"Expected >90% red pixels with mix_ratio=0, got {red_pixels}/{total_pixels}"
    )


def test_fragment_gap(effect, effect_context, colored_pair):
    """gap=5 → output contains black pixels at cell boundaries."""
    result = effect.compose(
        colored_pair,
        {"cut_mode": "grid", "pieces": 16, "gap": 5},
        effect_context,
    )
    _is_valid_rgb_image(result.image)
    arr = np.array(result.image)
    black_pixels = np.sum(np.all(arr < 20, axis=2))
    assert black_pixels > 0, "Expected black gap pixels"


def test_fragment_three_images(effect, effect_context):
    """3 different color images, pieces=9 → output has at least 2 colors."""
    red = Image.fromarray(np.full((64, 64, 3), [255, 0, 0], dtype=np.uint8), mode="RGB")
    green = Image.fromarray(np.full((64, 64, 3), [0, 255, 0], dtype=np.uint8), mode="RGB")
    blue = Image.fromarray(np.full((64, 64, 3), [0, 0, 255], dtype=np.uint8), mode="RGB")

    result = effect.compose(
        [red, green, blue],
        {"cut_mode": "grid", "pieces": 9, "mix_ratio": 1.0},
        effect_context,
    )
    _is_valid_rgb_image(result.image)
    arr = np.array(result.image)

    # Count pixels dominated by each channel
    dominant = np.argmax(arr, axis=2)
    unique_dominants = set(np.unique(dominant))
    assert len(unique_dominants) >= 2, (
        f"Expected at least 2 dominant colors, got channels: {unique_dominants}"
    )


def test_fragment_mismatched_sizes(effect, effect_context):
    """32x32 + 64x64 inputs → valid output (sizes matched to first image)."""
    small = Image.fromarray(np.full((32, 32, 3), 128, dtype=np.uint8), mode="RGB")
    large = Image.fromarray(np.full((64, 64, 3), 200, dtype=np.uint8), mode="RGB")

    result = effect.compose(
        [small, large],
        {"cut_mode": "grid", "pieces": 4},
        effect_context,
    )
    _is_valid_rgb_image(result.image)
    # Output should match first image size
    assert result.image.size == small.size


def test_fragment_deterministic(effect, colored_pair, tmp_path):
    """Same seed → identical output."""
    ctx_a = EffectContext(vision=None, temp_dir=tmp_path, seed=77, source_metadata={})
    ctx_b = EffectContext(vision=None, temp_dir=tmp_path, seed=77, source_metadata={})
    params = {"cut_mode": "voronoi", "pieces": 10, "mix_ratio": 0.7}

    result_a = effect.compose(colored_pair, params, ctx_a)
    result_b = effect.compose(colored_pair, params, ctx_b)

    np.testing.assert_array_equal(np.array(result_a.image), np.array(result_b.image))


def test_fragment_validate_bad_mode(effect):
    """Unknown cut_mode raises ConfigError."""
    with pytest.raises(ConfigError):
        effect.validate_params({"cut_mode": "explode"})
