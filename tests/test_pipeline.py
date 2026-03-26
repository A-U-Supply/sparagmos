"""Tests for the effect pipeline engine."""

import random
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from PIL import Image

import numpy as np

from sparagmos.effects import (
    ComposeEffect,
    Effect,
    EffectContext,
    EffectResult,
    register_effect,
)
from sparagmos.config import Recipe, RecipeStep
from sparagmos.pipeline import PipelineResult, run_pipeline


class InvertEffect(Effect):
    """Test effect that inverts colors."""

    name = "invert_test"
    description = "Inverts image colors"
    requires: list[str] = []

    def apply(self, image, params, context):
        from PIL import ImageOps
        inverted = ImageOps.invert(image.convert("RGB"))
        return EffectResult(image=inverted, metadata={"inverted": True})

    def validate_params(self, params):
        return params


class ScaleEffect(Effect):
    """Test effect that scales the image."""

    name = "scale_test"
    description = "Scales image by factor"
    requires: list[str] = []

    def apply(self, image, params, context):
        factor = params.get("factor", 0.5)
        new_size = (int(image.width * factor), int(image.height * factor))
        scaled = image.resize(new_size)
        return EffectResult(image=scaled, metadata={"factor": factor})

    def validate_params(self, params):
        return params


class MergeEffect(ComposeEffect):
    """Test compose effect that averages multiple images using numpy."""

    name = "merge_test"
    description = "Averages multiple images"
    requires: list[str] = []

    def compose(self, images, params, context):
        arrays = [np.array(img.convert("RGB"), dtype=np.float32) for img in images]
        averaged = np.mean(arrays, axis=0).astype(np.uint8)
        return EffectResult(image=Image.fromarray(averaged), metadata={"merged": len(images)})

    def validate_params(self, params):
        return params


@pytest.fixture(autouse=True)
def register_test_effects():
    register_effect(InvertEffect())
    register_effect(ScaleEffect())
    register_effect(MergeEffect())


def test_run_pipeline_single_effect(test_image_rgb, tmp_path):
    recipe = Recipe(
        name="test",
        description="test",
        effects=[RecipeStep(type="invert_test", params={})],
    )
    result = run_pipeline(test_image_rgb, recipe, seed=42, temp_dir=tmp_path)
    assert isinstance(result, PipelineResult)
    assert isinstance(result.image, Image.Image)
    assert len(result.steps) == 1
    assert result.steps[0]["effect"] == "invert_test"
    assert result.steps[0]["metadata"]["inverted"] is True


def test_run_pipeline_chained_effects(test_image_rgb, tmp_path):
    recipe = Recipe(
        name="chain",
        description="test chain",
        effects=[
            RecipeStep(type="invert_test", params={}),
            RecipeStep(type="scale_test", params={"factor": 0.5}),
        ],
    )
    result = run_pipeline(test_image_rgb, recipe, seed=42, temp_dir=tmp_path)
    assert len(result.steps) == 2
    # Image should be half size after scale
    assert result.image.width == 32
    assert result.image.height == 32


def test_run_pipeline_records_recipe_name(test_image_rgb, tmp_path):
    recipe = Recipe(
        name="Named Recipe",
        description="desc",
        effects=[RecipeStep(type="invert_test", params={})],
    )
    result = run_pipeline(test_image_rgb, recipe, seed=42, temp_dir=tmp_path)
    assert result.recipe_name == "Named Recipe"


def test_run_pipeline_param_ranges_resolved(test_image_rgb, tmp_path):
    recipe = Recipe(
        name="ranges",
        description="test ranges",
        effects=[
            RecipeStep(type="scale_test", params={"factor": [0.3, 0.7]}),
        ],
    )
    result = run_pipeline(test_image_rgb, recipe, seed=42, temp_dir=tmp_path)
    factor = result.steps[0]["resolved_params"]["factor"]
    assert 0.3 <= factor <= 0.7


def test_run_pipeline_deterministic(test_image_rgb, tmp_path):
    recipe = Recipe(
        name="det",
        description="test",
        effects=[
            RecipeStep(type="scale_test", params={"factor": [0.3, 0.7]}),
        ],
    )
    r1 = run_pipeline(test_image_rgb, recipe, seed=42, temp_dir=tmp_path)
    r2 = run_pipeline(test_image_rgb, recipe, seed=42, temp_dir=tmp_path)
    assert r1.steps[0]["resolved_params"] == r2.steps[0]["resolved_params"]


def test_compose_effect_has_compose_method():
    """ComposeEffect subclasses must implement compose()."""
    effect = MergeEffect()
    assert hasattr(effect, "compose")
    assert callable(effect.compose)


def test_compose_effect_apply_fallback(test_image_rgb, tmp_path):
    """apply() on a ComposeEffect delegates to compose([image])."""
    effect = MergeEffect()
    context = EffectContext(
        vision=None,
        temp_dir=tmp_path,
        seed=0,
        source_metadata={},
    )
    result = effect.apply(test_image_rgb, {}, context)
    assert isinstance(result, EffectResult)
    assert result.metadata["merged"] == 1
    assert result.image.size == test_image_rgb.size


def test_run_pipeline_multi_image(tmp_path):
    """Pipeline with inputs=2 routes named images through steps and merges them."""
    img_a = Image.new("RGB", (64, 64), color=(200, 0, 0))
    img_b = Image.new("RGB", (64, 64), color=(0, 0, 200))

    recipe = Recipe(
        name="multi",
        description="multi-image test",
        inputs=2,
        effects=[
            RecipeStep(type="invert_test", params={}, image="a"),
            RecipeStep(type="invert_test", params={}, image="b"),
            RecipeStep(
                type="merge_test",
                params={},
                images=["a", "b"],
                into="canvas",
            ),
        ],
    )

    result = run_pipeline(
        recipe=recipe,
        seed=0,
        temp_dir=tmp_path,
        images={"a": img_a, "b": img_b},
    )

    assert isinstance(result, PipelineResult)
    assert isinstance(result.image, Image.Image)
    assert len(result.steps) == 3
    assert result.recipe_name == "multi"
    # Merge step metadata records that 2 images were merged
    assert result.steps[2]["metadata"]["merged"] == 2


def test_run_pipeline_single_image_backward_compat(test_image_rgb, tmp_path):
    """Old positional calling convention still works."""
    recipe = Recipe(
        name="compat",
        description="backward compat test",
        effects=[RecipeStep(type="invert_test", params={})],
    )
    result = run_pipeline(test_image_rgb, recipe, seed=42, temp_dir=tmp_path)
    assert isinstance(result, PipelineResult)
    assert isinstance(result.image, Image.Image)
    assert len(result.steps) == 1


def test_run_pipeline_image_default_canvas(test_image_rgb, tmp_path):
    """Steps without image= field default to operating on 'canvas'."""
    recipe = Recipe(
        name="default-canvas",
        description="test default canvas",
        effects=[
            RecipeStep(type="invert_test", params={}),  # no image= → canvas
        ],
    )
    result = run_pipeline(test_image_rgb, recipe, seed=0, temp_dir=tmp_path)
    assert isinstance(result, PipelineResult)
    assert result.steps[0]["metadata"]["inverted"] is True


def test_run_pipeline_step_metadata_includes_image_names(tmp_path):
    """Step metadata records image name for single-image steps and images/into for compositing."""
    img_a = Image.new("RGB", (64, 64), color=(100, 100, 100))
    img_b = Image.new("RGB", (64, 64), color=(200, 200, 200))

    recipe = Recipe(
        name="metadata-check",
        description="test step metadata",
        inputs=2,
        effects=[
            RecipeStep(type="invert_test", params={}, image="a"),
            RecipeStep(
                type="merge_test",
                params={},
                images=["a", "b"],
                into="canvas",
            ),
        ],
    )

    result = run_pipeline(
        recipe=recipe,
        seed=0,
        temp_dir=tmp_path,
        images={"a": img_a, "b": img_b},
    )

    # Single-image step records image name
    assert result.steps[0]["image"] == "a"

    # Compositing step records images list and into target
    assert result.steps[1]["images"] == ["a", "b"]
    assert result.steps[1]["into"] == "canvas"
