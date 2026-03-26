"""Tests that validate all recipe YAML files."""

from pathlib import Path

import pytest

from sparagmos.config import load_all_recipes, validate_recipe


def _get_recipes_dir() -> Path:
    """Find the recipes directory."""
    repo_root = Path(__file__).parent.parent
    return repo_root / "recipes"


@pytest.fixture
def recipes():
    """Load all recipes."""
    # Register all effects first
    from sparagmos.cli import _register_all_effects
    _register_all_effects()
    return load_all_recipes(_get_recipes_dir())


def test_recipes_directory_exists():
    assert _get_recipes_dir().is_dir()


def test_at_least_10_recipes(recipes):
    assert len(recipes) >= 10, f"Only {len(recipes)} recipes found, expected >= 10"


def test_all_recipes_valid(recipes):
    for slug, recipe in recipes.items():
        errors = validate_recipe(recipe)
        assert errors == [], f"Recipe {slug} has errors: {errors}"


def test_all_recipes_have_description(recipes):
    for slug, recipe in recipes.items():
        assert recipe.description.strip(), f"Recipe {slug} has no description"


def test_all_recipes_have_effects(recipes):
    for slug, recipe in recipes.items():
        assert len(recipe.effects) > 0, f"Recipe {slug} has no effects"
