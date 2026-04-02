"""Tests for ancient effects (collage-bot adapter)."""

from __future__ import annotations

import numpy as np
import pytest
from PIL import Image

from sparagmos.effects import ConfigError, EffectContext


def _make_image(color: tuple[int, int, int], size: int = 64) -> Image.Image:
    arr = np.full((size, size, 3), color, dtype=np.uint8)
    return Image.fromarray(arr, mode="RGB")


@pytest.fixture
def context(tmp_path):
    return EffectContext(vision=None, temp_dir=tmp_path, seed=42, source_metadata={})


# --- AncientStencilEffect tests ---


@pytest.fixture
def stencil_effect():
    from sparagmos.effects.ancient import AncientStencilEffect

    return AncientStencilEffect()


@pytest.fixture
def stencil_images():
    """Three images: one high-contrast (good mask), two solid colors."""
    mask_arr = np.zeros((64, 64, 3), dtype=np.uint8)
    mask_arr[:, 32:, :] = 255
    mask_img = Image.fromarray(mask_arr, mode="RGB")
    red = _make_image((255, 0, 0))
    blue = _make_image((0, 0, 255))
    return [mask_img, red, blue]


def test_stencil_output_all(stencil_effect, stencil_images, context):
    result = stencil_effect.compose(stencil_images, {"output": "all"}, context)
    assert result.images is not None
    assert len(result.images) == 6
    for img in result.images:
        assert img.mode == "RGB"
        assert img.size == (64, 64)


def test_stencil_output_random(stencil_effect, stencil_images, context):
    result = stencil_effect.compose(stencil_images, {"output": "random"}, context)
    assert result.images is not None
    assert len(result.images) == 1
    assert result.image.mode == "RGB"


def test_stencil_validate_params_defaults(stencil_effect):
    params = stencil_effect.validate_params({})
    assert params["output"] == "all"


def test_stencil_validate_params_invalid_output(stencil_effect):
    with pytest.raises(ConfigError):
        stencil_effect.validate_params({"output": "first"})


# --- AncientCollageEffect tests ---


@pytest.fixture
def collage_effect():
    from sparagmos.effects.ancient import AncientCollageEffect

    return AncientCollageEffect()


@pytest.fixture
def collage_images():
    colors = [(255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 0)]
    return [_make_image(c) for c in colors]


@pytest.mark.slow
def test_collage_output_all(collage_effect, collage_images, context):
    result = collage_effect.compose(
        collage_images, {"output": "all", "split": 0.25, "blend_width": 70}, context
    )
    assert result.images is not None
    assert len(result.images) == 4
    for img in result.images:
        assert img.mode == "RGB"


@pytest.mark.slow
def test_collage_output_random(collage_effect, collage_images, context):
    result = collage_effect.compose(collage_images, {"output": "random"}, context)
    assert result.images is not None
    assert len(result.images) == 1


def test_collage_validate_params_defaults(collage_effect):
    params = collage_effect.validate_params({})
    assert params["output"] == "all"
    assert params["split"] == 0.25
    assert params["blend_width"] == 70


def test_collage_validate_params_invalid_output(collage_effect):
    with pytest.raises(ConfigError):
        collage_effect.validate_params({"output": "none"})


def test_collage_validate_params_clamps_split(collage_effect):
    params = collage_effect.validate_params({"split": 0.0})
    assert params["split"] == 0.05
    params = collage_effect.validate_params({"split": 0.9})
    assert params["split"] == 0.45
