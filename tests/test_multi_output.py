"""Tests for multi-output pipeline support."""

from __future__ import annotations

import numpy as np
from PIL import Image

from sparagmos.effects import EffectResult
from sparagmos.pipeline import PipelineResult


def _make_image(color: tuple[int, int, int], size: int = 32) -> Image.Image:
    arr = np.full((size, size, 3), color, dtype=np.uint8)
    return Image.fromarray(arr, mode="RGB")


def test_effect_result_images_field_defaults_to_none():
    img = _make_image((100, 100, 100))
    result = EffectResult(image=img)
    assert result.images is None


def test_effect_result_images_field_accepts_list():
    imgs = [_make_image((i * 50, 0, 0)) for i in range(4)]
    result = EffectResult(image=imgs[0], images=imgs)
    assert result.images is not None
    assert len(result.images) == 4


def test_pipeline_result_images_field_defaults_to_none():
    img = _make_image((100, 100, 100))
    result = PipelineResult(image=img, recipe_name="test")
    assert result.images is None


def test_pipeline_result_images_field_accepts_list():
    imgs = [_make_image((i * 50, 0, 0)) for i in range(3)]
    result = PipelineResult(image=imgs[0], recipe_name="test", images=imgs)
    assert result.images is not None
    assert len(result.images) == 3
