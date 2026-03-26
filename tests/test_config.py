"""Tests for recipe config loading and validation."""

import textwrap
from pathlib import Path

import pytest

from sparagmos.config import (
    Recipe,
    RecipeStep,
    load_recipe,
    load_all_recipes,
    resolve_params,
    validate_recipe,
)
from sparagmos.effects import ConfigError, register_effect

# Use the DummyEffect from conftest
from tests.test_effects.conftest import DummyEffect


@pytest.fixture(autouse=True)
def register_dummy():
    """Ensure dummy effect is registered for all tests."""
    register_effect(DummyEffect())


@pytest.fixture
def recipe_yaml(tmp_path):
    """Write a valid recipe YAML and return its path."""
    content = textwrap.dedent("""\
        name: Test Recipe
        description: A test recipe for unit tests.
        vision: false
        effects:
          - type: dummy
            params:
              fixed_val: 42
              range_val: [10, 20]
    """)
    path = tmp_path / "test-recipe.yaml"
    path.write_text(content)
    return path


@pytest.fixture
def recipe_dir(tmp_path):
    """Create a directory with multiple recipe files."""
    for name in ["recipe-a", "recipe-b"]:
        content = textwrap.dedent(f"""\
            name: {name}
            description: Test recipe {name}.
            effects:
              - type: dummy
                params: {{}}
        """)
        (tmp_path / f"{name}.yaml").write_text(content)
    return tmp_path


def test_load_recipe(recipe_yaml):
    recipe = load_recipe(recipe_yaml)
    assert recipe.name == "Test Recipe"
    assert recipe.vision is False
    assert len(recipe.effects) == 1
    assert recipe.effects[0].type == "dummy"


def test_load_recipe_params(recipe_yaml):
    recipe = load_recipe(recipe_yaml)
    params = recipe.effects[0].params
    assert params["fixed_val"] == 42
    assert params["range_val"] == [10, 20]


def test_resolve_params_fixed():
    params = {"quality": 5, "mode": "hard"}
    resolved = resolve_params(params, seed=42)
    assert resolved["quality"] == 5
    assert resolved["mode"] == "hard"


def test_resolve_params_range_int():
    params = {"quality": [1, 10]}
    resolved = resolve_params(params, seed=42)
    assert 1 <= resolved["quality"] <= 10
    assert isinstance(resolved["quality"], int)


def test_resolve_params_range_float():
    params = {"scale": [0.5, 1.5]}
    resolved = resolve_params(params, seed=42)
    assert 0.5 <= resolved["scale"] <= 1.5
    assert isinstance(resolved["scale"], float)


def test_resolve_params_deterministic():
    params = {"val": [1, 100]}
    r1 = resolve_params(params, seed=42)
    r2 = resolve_params(params, seed=42)
    assert r1 == r2


def test_resolve_params_vision_passthrough():
    params = {"region": "vision"}
    resolved = resolve_params(params, seed=42)
    assert resolved["region"] == "vision"


def test_load_all_recipes(recipe_dir):
    recipes = load_all_recipes(recipe_dir)
    assert len(recipes) == 2
    names = {r.name for r in recipes.values()}
    assert "recipe-a" in names
    assert "recipe-b" in names


def test_validate_recipe_valid(recipe_yaml):
    recipe = load_recipe(recipe_yaml)
    errors = validate_recipe(recipe)
    assert errors == []


def test_validate_recipe_unknown_effect(tmp_path):
    content = textwrap.dedent("""\
        name: Bad Recipe
        description: Uses unknown effect.
        effects:
          - type: nonexistent_effect
            params: {}
    """)
    path = tmp_path / "bad.yaml"
    path.write_text(content)
    recipe = load_recipe(path)
    errors = validate_recipe(recipe)
    assert len(errors) > 0
    assert "nonexistent_effect" in errors[0]


def test_validate_recipe_vision_without_flag(tmp_path):
    content = textwrap.dedent("""\
        name: Vision Without Flag
        description: Uses vision param but vision is false.
        effects:
          - type: dummy
            params:
              target: "vision"
    """)
    path = tmp_path / "no-vision.yaml"
    path.write_text(content)
    recipe = load_recipe(path)
    errors = validate_recipe(recipe)
    assert any("vision" in e.lower() for e in errors)
