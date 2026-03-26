"""Recipe loading, validation, and parameter resolution."""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from sparagmos.effects import get_effect, list_effects


@dataclass
class RecipeStep:
    """A single effect step in a recipe pipeline."""

    type: str
    params: dict[str, Any] = field(default_factory=dict)


@dataclass
class Recipe:
    """A complete recipe loaded from YAML."""

    name: str
    description: str
    effects: list[RecipeStep]
    vision: bool = False
    source_path: Path | None = None


def load_recipe(path: Path) -> Recipe:
    """Load a recipe from a YAML file.

    Args:
        path: Path to the YAML recipe file.

    Returns:
        Parsed Recipe object.
    """
    with open(path) as f:
        data = yaml.safe_load(f)

    effects = []
    for step_data in data.get("effects", []):
        effects.append(
            RecipeStep(
                type=step_data["type"],
                params=step_data.get("params", {}),
            )
        )

    return Recipe(
        name=data["name"],
        description=data.get("description", ""),
        effects=effects,
        vision=data.get("vision", False),
        source_path=path,
    )


def load_all_recipes(recipes_dir: Path) -> dict[str, Recipe]:
    """Load all recipes from a directory.

    Args:
        recipes_dir: Path to the recipes directory.

    Returns:
        Dict mapping recipe slug (filename without extension) to Recipe.
    """
    recipes = {}
    for path in sorted(recipes_dir.glob("*.yaml")):
        recipe = load_recipe(path)
        slug = path.stem
        recipes[slug] = recipe
    return recipes


def resolve_params(params: dict[str, Any], seed: int) -> dict[str, Any]:
    """Resolve parameter ranges to concrete values.

    Fixed values pass through. Two-element lists [min, max] are treated as
    ranges — integers if both bounds are ints, floats otherwise. The string
    "vision" passes through for later resolution.

    Args:
        params: Raw parameters from recipe.
        seed: RNG seed for deterministic resolution.

    Returns:
        Dict with all ranges resolved to concrete values.
    """
    rng = random.Random(seed)
    resolved = {}

    for key, value in params.items():
        if isinstance(value, list) and len(value) == 2:
            low, high = value
            if isinstance(low, int) and isinstance(high, int):
                resolved[key] = rng.randint(low, high)
            else:
                resolved[key] = rng.uniform(float(low), float(high))
        else:
            resolved[key] = value

    return resolved


def validate_recipe(recipe: Recipe) -> list[str]:
    """Validate a recipe against registered effects.

    Checks:
    - All effect types reference registered effects
    - Parameters are valid for each effect (via validate_params)
    - Vision params only used when recipe has vision: true

    Args:
        recipe: Recipe to validate.

    Returns:
        List of error messages (empty if valid).
    """
    errors = []
    known_effects = list_effects()

    for i, step in enumerate(recipe.effects):
        step_label = f"effects[{i}] ({step.type})"

        # Check effect exists
        if step.type not in known_effects:
            errors.append(
                f"{step_label}: unknown effect {step.type!r}. "
                f"Available: {sorted(known_effects.keys())}"
            )
            continue

        # Check params (resolve ranges first so validate_params gets concrete values)
        effect = known_effects[step.type]
        try:
            resolved = resolve_params(step.params, seed=0)
            effect.validate_params(resolved)
        except Exception as e:
            errors.append(f"{step_label}: {e}")

        # Check vision params without vision flag
        if not recipe.vision:
            for key, val in step.params.items():
                if val == "vision":
                    errors.append(
                        f"{step_label}: param {key!r} uses 'vision' "
                        f"but recipe has vision: false"
                    )

    return errors
