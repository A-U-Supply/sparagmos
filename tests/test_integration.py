"""End-to-end integration tests."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image

from sparagmos.cli import _register_all_effects
from sparagmos.config import load_recipe, Recipe, RecipeStep
from sparagmos.pipeline import run_pipeline, IMAGE_NAMES


@pytest.fixture(autouse=True)
def register_effects():
    _register_all_effects()


def _get_recipes_dir() -> Path:
    return Path(__file__).parent.parent / "recipes"


def _get_pure_python_recipes():
    """Get recipes that only use pure Python effects (no system deps)."""
    recipes_dir = _get_recipes_dir()
    if not recipes_dir.is_dir():
        return []

    # These recipes use subprocess effects that may not be installed
    subprocess_recipes = {"analog-burial", "turtle-oracle", "ocr-feedback-loop", "feedback-loop", "tectonic-overlap"}
    return [
        f for f in sorted(recipes_dir.glob("*.yaml"))
        if f.stem not in subprocess_recipes
    ]


@pytest.mark.parametrize(
    "recipe_file",
    _get_pure_python_recipes(),
    ids=lambda f: f.stem,
)
def test_recipe_produces_valid_output(recipe_file, test_image_rgb, tmp_path):
    """Run each recipe end-to-end on a test image."""
    recipe = load_recipe(recipe_file)
    num_inputs = recipe.inputs or 1
    if num_inputs > 1:
        images = {
            name: test_image_rgb.copy()
            for name in IMAGE_NAMES[:num_inputs]
        }
        result = run_pipeline(
            images=images,
            recipe=recipe,
            seed=42,
            temp_dir=tmp_path,
        )
    else:
        result = run_pipeline(
            image=test_image_rgb,
            recipe=recipe,
            seed=42,
            temp_dir=tmp_path,
        )
    assert isinstance(result.image, Image.Image)
    assert result.image.size[0] > 0
    assert result.image.size[1] > 0
    assert result.recipe_name == recipe.name
    assert len(result.steps) == len(recipe.effects)


def test_multi_input_pipeline_end_to_end(test_images_multi, tmp_path):
    """Full pipeline with a multi-input recipe using compositing effects."""
    # Import to trigger registration
    import sparagmos.effects.blend
    import sparagmos.effects.mask_composite
    import sparagmos.effects.collage
    import sparagmos.effects.fragment

    recipe = Recipe(
        name="Integration Test",
        description="test multi-input pipeline",
        inputs=3,
        effects=[
            RecipeStep(type="blend", images=["a", "b"], into="canvas",
                      params={"mode": "screen", "strength": 0.7}),
            RecipeStep(type="mask_composite", images=["canvas", "c"], into="canvas",
                      params={"mask_source": "edges", "threshold": 80, "feather": 5}),
        ],
    )

    images = dict(zip(IMAGE_NAMES[:3], test_images_multi[:3]))
    result = run_pipeline(
        images=images,
        recipe=recipe,
        seed=42,
        temp_dir=tmp_path,
    )
    assert result.image.size == (64, 64)
    assert len(result.steps) == 2
    assert result.steps[0]["effect"] == "blend"
    assert result.steps[1]["effect"] == "mask_composite"
