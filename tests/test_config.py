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


# ── New schema field tests ────────────────────────────────────────────────────


def test_load_recipe_with_inputs(tmp_path):
    """Recipe with inputs: 3 and steps: key with image: fields loads correctly."""
    content = textwrap.dedent("""\
        name: Multi Input
        description: Recipe with multiple inputs.
        inputs: 3
        steps:
          - type: dummy
            image: a
            params: {}
          - type: dummy
            image: b
            params: {}
    """)
    path = tmp_path / "multi.yaml"
    path.write_text(content)
    recipe = load_recipe(path)
    assert recipe.inputs == 3
    assert len(recipe.effects) == 2
    assert recipe.effects[0].image == "a"
    assert recipe.effects[1].image == "b"


def test_load_recipe_inputs_defaults_to_one(tmp_path):
    """Recipe without inputs: defaults to 1."""
    content = textwrap.dedent("""\
        name: Default Inputs
        description: No inputs key.
        effects:
          - type: dummy
            params: {}
    """)
    path = tmp_path / "default.yaml"
    path.write_text(content)
    recipe = load_recipe(path)
    assert recipe.inputs == 1


def test_load_recipe_steps_alias(tmp_path):
    """steps: key accepted as alias for effects:."""
    content = textwrap.dedent("""\
        name: Steps Alias
        description: Uses steps instead of effects.
        steps:
          - type: dummy
            params: {}
    """)
    path = tmp_path / "steps.yaml"
    path.write_text(content)
    recipe = load_recipe(path)
    assert len(recipe.effects) == 1
    assert recipe.effects[0].type == "dummy"


def test_load_recipe_compose_step(tmp_path):
    """Step with images: [a, b] and into: canvas loads correctly."""
    content = textwrap.dedent("""\
        name: Compose Step
        description: A compositing step.
        inputs: 2
        steps:
          - type: dummy
            images: [a, b]
            into: canvas
            params: {}
    """)
    path = tmp_path / "compose.yaml"
    path.write_text(content)
    recipe = load_recipe(path)
    step = recipe.effects[0]
    assert step.images == ["a", "b"]
    assert step.into == "canvas"


def test_load_recipe_image_defaults_none(tmp_path):
    """Steps without image/images/into have None for those fields."""
    content = textwrap.dedent("""\
        name: No Image Fields
        description: Plain step.
        effects:
          - type: dummy
            params: {}
    """)
    path = tmp_path / "plain.yaml"
    path.write_text(content)
    recipe = load_recipe(path)
    step = recipe.effects[0]
    assert step.image is None
    assert step.images is None
    assert step.into is None


def test_validate_recipe_compose_step_missing_into(tmp_path):
    """Compose step (has images:) without into: is an error."""
    content = textwrap.dedent("""\
        name: Missing Into
        description: Compose step without into.
        inputs: 2
        steps:
          - type: dummy
            images: [a, b]
            params: {}
    """)
    path = tmp_path / "missing-into.yaml"
    path.write_text(content)
    recipe = load_recipe(path)
    errors = validate_recipe(recipe)
    assert any("into" in e.lower() for e in errors)


def test_validate_recipe_image_name_not_in_inputs(tmp_path):
    """Referencing image name beyond inputs count is an error."""
    content = textwrap.dedent("""\
        name: Bad Image Name
        description: References c but only 2 inputs.
        inputs: 2
        steps:
          - type: dummy
            image: c
            params: {}
    """)
    path = tmp_path / "bad-name.yaml"
    path.write_text(content)
    recipe = load_recipe(path)
    errors = validate_recipe(recipe)
    assert any("c" in e for e in errors)
