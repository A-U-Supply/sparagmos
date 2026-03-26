"""Tests for collage compositing effect."""

from __future__ import annotations

import numpy as np
import pytest
from PIL import Image

from sparagmos.effects import ConfigError, EffectContext
from sparagmos.effects.collage import CollageEffect


@pytest.fixture
def effect():
    return CollageEffect()


@pytest.fixture
def effect_context(tmp_path):
    return EffectContext(vision=None, temp_dir=tmp_path, seed=42, source_metadata={})


@pytest.fixture
def colored_images():
    """Three solid-color 64x64 images: red, green, blue."""
    red = np.zeros((64, 64, 3), dtype=np.uint8)
    red[:, :, 0] = 255
    green = np.zeros((64, 64, 3), dtype=np.uint8)
    green[:, :, 1] = 255
    blue = np.zeros((64, 64, 3), dtype=np.uint8)
    blue[:, :, 2] = 255
    return [
        Image.fromarray(red, mode="RGB"),
        Image.fromarray(green, mode="RGB"),
        Image.fromarray(blue, mode="RGB"),
    ]


def _is_valid_rgb_image(result_image: Image.Image) -> None:
    """Assert that the image is a valid RGB PIL image with pixel data."""
    arr = np.array(result_image)
    assert arr.ndim == 3
    assert arr.shape[2] == 3
    assert arr.dtype == np.uint8


def test_collage_grid(effect, effect_context, colored_images):
    """Grid layout with 3 colored images produces valid output."""
    result = effect.compose(
        colored_images,
        {"layout": "grid"},
        effect_context,
    )
    _is_valid_rgb_image(result.image)
    assert result.image.width > 0
    assert result.image.height > 0


def test_collage_scatter(effect, effect_context, colored_images):
    """Scatter layout with rotation and scale_variance produces valid output."""
    result = effect.compose(
        colored_images,
        {"layout": "scatter", "rotation": 45, "scale_variance": 0.3},
        effect_context,
    )
    _is_valid_rgb_image(result.image)


def test_collage_strips(effect, effect_context, colored_images):
    """Strips layout with 3 colored images — output should contain pixels from all 3 colors."""
    result = effect.compose(
        colored_images,
        {"layout": "strips"},
        effect_context,
    )
    _is_valid_rgb_image(result.image)

    arr = np.array(result.image)
    # Check that at least two distinct dominant channels are present across the image
    # (red=0, green=1, blue=2 are all solid — each strip should be dominated by one channel)
    dominant_channels = set()
    h, w, _ = arr.shape
    for col in range(w):
        col_pixels = arr[:, col, :]
        mean_per_channel = col_pixels.mean(axis=0)
        dominant_channels.add(int(np.argmax(mean_per_channel)))
    # With 3 input colors divided into strips, we expect at least 2 distinct dominant channels
    assert len(dominant_channels) >= 2, (
        f"Expected pixels from multiple source colors, got dominant channels: {dominant_channels}"
    )


def test_collage_mosaic(effect, effect_context, colored_images):
    """Mosaic layout produces valid output."""
    result = effect.compose(
        colored_images,
        {"layout": "mosaic"},
        effect_context,
    )
    _is_valid_rgb_image(result.image)


def test_collage_single_image(effect, effect_context):
    """Single image input returns a copy of that image."""
    arr = np.full((64, 64, 3), 128, dtype=np.uint8)
    img = Image.fromarray(arr, mode="RGB")
    result = effect.compose([img], {}, effect_context)
    _is_valid_rgb_image(result.image)
    assert result.image.size == img.size


def test_collage_five_images(effect, effect_context):
    """Five images in grid layout produces valid output."""
    images = []
    for i in range(5):
        val = i * 50
        arr = np.full((64, 64, 3), val, dtype=np.uint8)
        images.append(Image.fromarray(arr, mode="RGB"))
    result = effect.compose(images, {"layout": "grid"}, effect_context)
    _is_valid_rgb_image(result.image)


def test_collage_mismatched_sizes(effect, effect_context):
    """Mixed-size inputs (32x32, 64x64, 100x50) produce valid output."""
    img1 = Image.fromarray(np.full((32, 32, 3), 80, dtype=np.uint8), mode="RGB")
    img2 = Image.fromarray(np.full((64, 64, 3), 160, dtype=np.uint8), mode="RGB")
    img3 = Image.fromarray(np.full((50, 100, 3), 240, dtype=np.uint8), mode="RGB")
    result = effect.compose([img1, img2, img3], {"layout": "grid"}, effect_context)
    _is_valid_rgb_image(result.image)
    assert result.image.width > 0
    assert result.image.height > 0


def test_collage_with_overlap(effect, effect_context, colored_images):
    """overlap=0.2 produces valid output without errors."""
    result = effect.compose(
        colored_images,
        {"layout": "grid", "overlap": 0.2},
        effect_context,
    )
    _is_valid_rgb_image(result.image)


def test_collage_deterministic(effect, colored_images, tmp_path):
    """Same seed produces identical output."""
    ctx_a = EffectContext(vision=None, temp_dir=tmp_path, seed=99, source_metadata={})
    ctx_b = EffectContext(vision=None, temp_dir=tmp_path, seed=99, source_metadata={})
    params = {"layout": "scatter", "rotation": 30, "scale_variance": 0.2}

    result_a = effect.compose(colored_images, params, ctx_a)
    result_b = effect.compose(colored_images, params, ctx_b)

    arr_a = np.array(result_a.image)
    arr_b = np.array(result_b.image)
    np.testing.assert_array_equal(arr_a, arr_b)


def test_collage_validate_bad_layout(effect):
    """Unknown layout value should raise ConfigError."""
    with pytest.raises(ConfigError):
        effect.validate_params({"layout": "pinwheel"})
