"""Tests for the effect pipeline engine."""

import random
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from PIL import Image

from sparagmos.effects import (
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


@pytest.fixture(autouse=True)
def register_test_effects():
    register_effect(InvertEffect())
    register_effect(ScaleEffect())


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
