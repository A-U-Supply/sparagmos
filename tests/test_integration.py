"""End-to-end integration tests."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image

from sparagmos.cli import _register_all_effects
from sparagmos.config import load_recipe
from sparagmos.pipeline import run_pipeline


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
    subprocess_recipes = {"analog-burial", "turtle-oracle", "ocr-feedback-loop"}
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
