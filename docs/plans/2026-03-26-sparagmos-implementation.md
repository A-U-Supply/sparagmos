# Sparagmos Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build sparagmos — a daily automated image destruction bot that scrapes random images from #image-gen on Slack, applies chained glitch/decay/neural effects via YAML recipes, and posts results to #img-junkyard.

**Architecture:** Plugin-based effect system with a unified `Effect` base class. YAML recipes chain effects into named pipelines. A central pipeline engine resolves params, runs effects in sequence, and collects provenance metadata. Slack integration handles source image scraping and single-message posting. Llama Vision (HF Inference API) provides optional image analysis for targeted destruction.

**Tech Stack:** Python 3.11, uv, pytest, Pillow, PyTorch, numpy, scipy, OpenCV, slack-sdk, huggingface-hub, PyYAML. System tools: ImageMagick, NetPBM, ffmpeg, potrace, primitive.

**Spec:** `~/au-supply/ausupply.github.io/docs/plans/2026-03-26-sparagmos-design.md`

---

## File Map

```
sparagmos/
├── sparagmos/
│   ├── __init__.py              # Version, package metadata
│   ├── __main__.py              # python -m sparagmos entry point
│   ├── cli.py                   # Argparse CLI
│   ├── config.py                # Recipe loading, YAML schema validation
│   ├── pipeline.py              # Effect chaining engine
│   ├── slack_source.py          # Scrape random image from #image-gen
│   ├── slack_post.py            # Post result to #img-junkyard
│   ├── vision.py                # Llama Vision via HF Inference API
│   ├── state.py                 # JSON state management
│   ├── effects/
│   │   ├── __init__.py          # Effect ABC, registry, SubprocessEffect, EffectContext, EffectResult
│   │   ├── byte_corrupt.py
│   │   ├── cellular.py
│   │   ├── channel_shift.py
│   │   ├── crt_vhs.py
│   │   ├── datamosh.py
│   │   ├── deepdream.py
│   │   ├── dither.py
│   │   ├── format_roundtrip.py
│   │   ├── fractal_blend.py
│   │   ├── imagemagick.py
│   │   ├── inpaint.py
│   │   ├── jpeg_destroy.py
│   │   ├── netpbm.py
│   │   ├── neural_doodle.py
│   │   ├── pca_decompose.py
│   │   ├── pix2pix.py
│   │   ├── pixel_sort.py
│   │   ├── primitive.py
│   │   ├── seam_carve.py
│   │   ├── sonify.py
│   │   ├── spectral.py
│   │   └── style_transfer.py
│   └── vendor/
│       └── README.md
├── recipes/                     # YAML recipe files (Task 16)
├── tests/
│   ├── conftest.py
│   ├── fixtures/                # Test images
│   ├── test_config.py
│   ├── test_pipeline.py
│   ├── test_state.py
│   ├── test_slack.py
│   ├── test_vision.py
│   ├── test_cli.py
│   ├── test_recipes.py          # Validates all YAML recipes
│   └── test_effects/
│       ├── conftest.py          # Shared effect test fixtures
│       ├── test_byte_corrupt.py
│       ├── test_cellular.py
│       ├── test_channel_shift.py
│       ├── test_crt_vhs.py
│       ├── test_datamosh.py
│       ├── test_deepdream.py
│       ├── test_dither.py
│       ├── test_format_roundtrip.py
│       ├── test_fractal_blend.py
│       ├── test_imagemagick.py
│       ├── test_inpaint.py
│       ├── test_jpeg_destroy.py
│       ├── test_netpbm.py
│       ├── test_neural_doodle.py
│       ├── test_pca_decompose.py
│       ├── test_pix2pix.py
│       ├── test_pixel_sort.py
│       ├── test_primitive.py
│       ├── test_seam_carve.py
│       ├── test_sonify.py
│       ├── test_spectral.py
│       └── test_style_transfer.py
├── docs/
│   ├── recipes.md
│   └── effects.md
├── state.json
├── pyproject.toml
├── requirements.txt
├── README.md
└── .github/
    └── workflows/
        └── sparagmos.yml
```

---

## Task 1: Project Scaffolding

**Files:**
- Create: `pyproject.toml`
- Create: `requirements.txt`
- Create: `sparagmos/__init__.py`
- Create: `sparagmos/__main__.py`
- Create: `sparagmos/vendor/README.md`
- Create: `state.json`
- Create: `tests/conftest.py`
- Create: `tests/fixtures/` (test images)

- [ ] **Step 1: Create pyproject.toml**

```toml
[project]
name = "sparagmos"
version = "0.1.0"
description = "σπαραγμός — Automated image destruction bot"
requires-python = ">=3.11"
dependencies = [
    "Pillow>=10.0",
    "PyYAML>=6.0",
    "numpy>=1.24",
    "scipy>=1.10",
    "opencv-python-headless>=4.8",
    "slack-sdk>=3.0",
    "requests>=2.28",
    "huggingface-hub>=0.19",
    "torch>=2.0",
    "torchvision>=0.15",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.0",
    "pytest-cov>=4.0",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.pytest.ini_options]
testpaths = ["tests"]
markers = [
    "slow: marks tests as slow (deselect with '-m \"not slow\"')",
    "requires_imagemagick: requires ImageMagick installed",
    "requires_netpbm: requires NetPBM installed",
    "requires_ffmpeg: requires ffmpeg installed",
    "requires_potrace: requires potrace installed",
    "requires_primitive: requires primitive installed",
    "requires_torch: requires PyTorch (neural effects)",
]
```

- [ ] **Step 2: Create requirements.txt**

```
Pillow>=10.0
PyYAML>=6.0
numpy>=1.24
scipy>=1.10
opencv-python-headless>=4.8
slack-sdk>=3.0
requests>=2.28
huggingface-hub>=0.19
torch>=2.0
torchvision>=0.15
pytest>=7.0
pytest-cov>=4.0
```

- [ ] **Step 3: Create sparagmos/__init__.py**

```python
"""σπαραγμός — Automated image destruction bot."""

__version__ = "0.1.0"
```

- [ ] **Step 4: Create sparagmos/__main__.py**

```python
"""Entry point for python -m sparagmos."""

from sparagmos.cli import main

main()
```

- [ ] **Step 5: Create vendor README**

```markdown
# Vendored Dependencies

This directory contains vendored (copied-in) dependencies that are either
unmaintained, abandoned, or too fragile to rely on as pip packages. Each
subdirectory documents its provenance.

## Provenance Format

Each vendored package includes:
- Source URL / repository
- Version or commit hash
- Date vendored
- Modifications made (if any) and why
- Original license
```

- [ ] **Step 6: Create empty state.json**

```json
{
  "processed": []
}
```

- [ ] **Step 7: Create test fixtures**

Create a small test image programmatically in `tests/conftest.py`:

```python
"""Shared test fixtures for sparagmos."""

import tempfile
from pathlib import Path

import pytest
from PIL import Image


@pytest.fixture
def test_image_rgb():
    """Create a small RGB test image (64x64) with varied content."""
    img = Image.new("RGB", (64, 64))
    pixels = img.load()
    for x in range(64):
        for y in range(64):
            pixels[x, y] = (
                (x * 4) % 256,
                (y * 4) % 256,
                ((x + y) * 2) % 256,
            )
    return img


@pytest.fixture
def test_image_rgba():
    """Create a small RGBA test image (64x64)."""
    img = Image.new("RGBA", (64, 64))
    pixels = img.load()
    for x in range(64):
        for y in range(64):
            pixels[x, y] = (
                (x * 4) % 256,
                (y * 4) % 256,
                ((x + y) * 2) % 256,
                200,
            )
    return img


@pytest.fixture
def test_image_grayscale():
    """Create a small grayscale test image (64x64)."""
    img = Image.new("L", (64, 64))
    pixels = img.load()
    for x in range(64):
        for y in range(64):
            pixels[x, y] = ((x + y) * 2) % 256
    return img


@pytest.fixture
def test_image_tiny():
    """Create a tiny 4x4 RGB image for edge case testing."""
    img = Image.new("RGB", (4, 4), color=(128, 64, 32))
    return img


@pytest.fixture
def tmp_dir():
    """Create a temporary directory for test output."""
    with tempfile.TemporaryDirectory() as d:
        yield Path(d)


@pytest.fixture
def test_image_file(test_image_rgb, tmp_dir):
    """Save a test image to disk and return the path."""
    path = tmp_dir / "test_input.png"
    test_image_rgb.save(path)
    return path
```

- [ ] **Step 8: Initialize uv and verify**

Run:
```bash
cd ~/au-supply/sparagmos
uv sync
uv run pytest --co -q
```
Expected: No errors, no tests collected yet (but pytest runs).

- [ ] **Step 9: Commit**

```bash
git add -A
git commit -m "feat: project scaffolding

pyproject.toml with all dependencies, test fixtures, empty state.json,
vendor README, package init. Ready for core infrastructure."
```

---

## Task 2: Effect Base Classes and Registry

**Files:**
- Create: `sparagmos/effects/__init__.py`
- Create: `tests/test_effects/conftest.py`

- [ ] **Step 1: Write tests for base classes**

Create `tests/test_effects/conftest.py`:

```python
"""Shared fixtures for effect tests."""

import pytest

from sparagmos.effects import Effect, EffectContext, EffectResult


class DummyEffect(Effect):
    """Minimal effect implementation for testing."""

    name = "dummy"
    description = "A dummy effect for testing"
    requires: list[str] = []

    def apply(self, image, params, context):
        return EffectResult(image=image, metadata={"dummy": True})

    def validate_params(self, params):
        return params


@pytest.fixture
def dummy_effect():
    return DummyEffect()


@pytest.fixture
def effect_context(tmp_path):
    return EffectContext(
        vision=None,
        temp_dir=tmp_path,
        seed=42,
        source_metadata={},
    )
```

Create `tests/test_effects/test_base.py`:

```python
"""Tests for effect base classes and registry."""

from PIL import Image

from sparagmos.effects import (
    ConfigError,
    Effect,
    EffectContext,
    EffectResult,
    SubprocessEffect,
    get_effect,
    list_effects,
    register_effect,
)


def test_effect_result_has_image_and_metadata(test_image_rgb, effect_context, dummy_effect):
    result = dummy_effect.apply(test_image_rgb, {}, effect_context)
    assert isinstance(result.image, Image.Image)
    assert isinstance(result.metadata, dict)


def test_effect_context_fields(tmp_path):
    ctx = EffectContext(
        vision={"objects": ["face"]},
        temp_dir=tmp_path,
        seed=123,
        source_metadata={"file_id": "F123"},
    )
    assert ctx.vision == {"objects": ["face"]}
    assert ctx.seed == 123
    assert ctx.temp_dir == tmp_path


def test_register_and_get_effect(dummy_effect):
    register_effect(dummy_effect)
    retrieved = get_effect("dummy")
    assert retrieved.name == "dummy"


def test_get_unknown_effect_raises():
    try:
        get_effect("nonexistent_effect_xyz")
        assert False, "Should have raised"
    except KeyError:
        pass


def test_list_effects_returns_dict(dummy_effect):
    register_effect(dummy_effect)
    effects = list_effects()
    assert isinstance(effects, dict)
    assert "dummy" in effects


def test_config_error():
    err = ConfigError("bad param", effect_name="pixel_sort", param_name="threshold")
    assert "bad param" in str(err)
    assert err.effect_name == "pixel_sort"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_effects/test_base.py -v`
Expected: ImportError — `sparagmos.effects` has no members yet.

- [ ] **Step 3: Implement base classes and registry**

Create `sparagmos/effects/__init__.py`:

```python
"""Effect base classes, registry, and shared types."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from PIL import Image


class ConfigError(Exception):
    """Raised when effect parameters are invalid."""

    def __init__(self, message: str, effect_name: str = "", param_name: str = ""):
        self.effect_name = effect_name
        self.param_name = param_name
        super().__init__(message)


@dataclass
class EffectContext:
    """Shared state carried through the pipeline."""

    vision: dict[str, Any] | None
    temp_dir: Path
    seed: int
    source_metadata: dict[str, Any]


@dataclass
class EffectResult:
    """Result from applying an effect."""

    image: Image.Image
    metadata: dict[str, Any] = field(default_factory=dict)


class Effect(ABC):
    """Base class for all effects."""

    name: str
    description: str
    requires: list[str] = []

    @abstractmethod
    def apply(
        self, image: Image.Image, params: dict, context: EffectContext
    ) -> EffectResult:
        """Apply the effect to an image.

        Args:
            image: Input PIL Image (RGB or RGBA).
            params: Resolved recipe parameters (ranges already rolled).
            context: Shared pipeline context (vision, temp dir, seed, etc).

        Returns:
            EffectResult with processed image and metadata.
        """

    @abstractmethod
    def validate_params(self, params: dict) -> dict:
        """Validate and normalize parameters.

        Args:
            params: Raw parameters from recipe YAML.

        Returns:
            Normalized parameters dict.

        Raises:
            ConfigError: If parameters are invalid and cannot be auto-corrected.
        """

    def check_dependencies(self) -> list[str]:
        """Check if required system dependencies are available.

        Returns:
            List of missing dependency names (empty if all present).
        """
        missing = []
        for dep in self.requires:
            if shutil.which(dep) is None:
                missing.append(dep)
        return missing


class SubprocessEffect(Effect):
    """Base class for effects that shell out to external tools.

    Handles temp file creation, execution timeouts, and stderr capture.
    """

    timeout_seconds: int = 120

    def run_command(
        self, cmd: list[str], context: EffectContext, timeout: int | None = None
    ) -> subprocess.CompletedProcess:
        """Run a subprocess command with timeout and error handling.

        Args:
            cmd: Command and arguments.
            context: Effect context (uses temp_dir).
            timeout: Override timeout in seconds.

        Returns:
            CompletedProcess result.

        Raises:
            subprocess.TimeoutExpired: If command exceeds timeout.
            subprocess.CalledProcessError: If command returns non-zero.
        """
        timeout = timeout or self.timeout_seconds
        return subprocess.run(
            cmd,
            capture_output=True,
            timeout=timeout,
            check=True,
            cwd=context.temp_dir,
        )

    def save_temp_image(
        self, image: Image.Image, context: EffectContext, suffix: str = ".png"
    ) -> Path:
        """Save image to a temp file in context.temp_dir.

        Args:
            image: PIL Image to save.
            context: Effect context with temp_dir.
            suffix: File extension.

        Returns:
            Path to the saved temp file.
        """
        path = context.temp_dir / f"input{suffix}"
        image.save(path)
        return path

    def load_temp_image(self, path: Path) -> Image.Image:
        """Load an image from a temp file.

        Args:
            path: Path to image file.

        Returns:
            PIL Image in RGB mode.
        """
        return Image.open(path).convert("RGB")


# --- Effect Registry ---

_registry: dict[str, Effect] = {}


def register_effect(effect: Effect) -> None:
    """Register an effect instance in the global registry."""
    _registry[effect.name] = effect


def get_effect(name: str) -> Effect:
    """Get a registered effect by name.

    Raises:
        KeyError: If no effect with that name is registered.
    """
    if name not in _registry:
        raise KeyError(f"Unknown effect: {name!r}. Available: {sorted(_registry.keys())}")
    return _registry[name]


def list_effects() -> dict[str, Effect]:
    """Return a copy of the effect registry."""
    return dict(_registry)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_effects/test_base.py -v`
Expected: All 6 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add sparagmos/effects/__init__.py tests/test_effects/conftest.py tests/test_effects/test_base.py
git commit -m "feat: effect base classes, registry, and shared types

Effect ABC with apply/validate_params/check_dependencies.
SubprocessEffect for tools that shell out (ImageMagick, NetPBM, etc).
EffectContext/EffectResult dataclasses. Global registry with
register_effect/get_effect/list_effects. ConfigError for bad params."
```

---

## Task 3: Config and Recipe Loading

**Files:**
- Create: `sparagmos/config.py`
- Create: `tests/test_config.py`

- [ ] **Step 1: Write tests for config loading**

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_config.py -v`
Expected: ImportError — `sparagmos.config` doesn't exist yet.

- [ ] **Step 3: Implement config.py**

```python
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

        # Check params
        effect = known_effects[step.type]
        try:
            effect.validate_params(step.params)
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_config.py -v`
Expected: All 11 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add sparagmos/config.py tests/test_config.py
git commit -m "feat: recipe config loading, validation, and param resolution

Load YAML recipes into Recipe/RecipeStep dataclasses. Resolve param
ranges ([min, max]) deterministically via seeded RNG. Validate recipes
against registered effects. Detect vision params used without vision flag."
```

---

## Task 4: Pipeline Engine

**Files:**
- Create: `sparagmos/pipeline.py`
- Create: `tests/test_pipeline.py`

- [ ] **Step 1: Write tests for pipeline**

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_pipeline.py -v`
Expected: ImportError — `sparagmos.pipeline` doesn't exist.

- [ ] **Step 3: Implement pipeline.py**

```python
"""Effect chaining pipeline engine."""

from __future__ import annotations

import logging
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from PIL import Image

from sparagmos.config import Recipe, resolve_params
from sparagmos.effects import EffectContext, get_effect

logger = logging.getLogger(__name__)


@dataclass
class PipelineResult:
    """Result of running a complete recipe pipeline."""

    image: Image.Image
    recipe_name: str
    steps: list[dict[str, Any]] = field(default_factory=list)


def run_pipeline(
    image: Image.Image,
    recipe: Recipe,
    seed: int,
    temp_dir: Path | None = None,
    vision: dict[str, Any] | None = None,
    source_metadata: dict[str, Any] | None = None,
) -> PipelineResult:
    """Run a recipe's effect chain on an image.

    Args:
        image: Input PIL Image.
        recipe: Recipe defining the effect chain.
        seed: RNG seed for deterministic param resolution.
        temp_dir: Temp directory for subprocess effects. Created if None.
        vision: Llama Vision analysis results (if recipe uses vision).
        source_metadata: Source image metadata for context.

    Returns:
        PipelineResult with processed image and step metadata.
    """
    if source_metadata is None:
        source_metadata = {}

    cleanup_temp = False
    if temp_dir is None:
        temp_dir = Path(tempfile.mkdtemp(prefix="sparagmos_"))
        cleanup_temp = True

    context = EffectContext(
        vision=vision,
        temp_dir=temp_dir,
        seed=seed,
        source_metadata=source_metadata,
    )

    # Ensure image is RGB
    current_image = image.convert("RGB")
    steps = []

    try:
        for i, step in enumerate(recipe.effects):
            effect = get_effect(step.type)
            logger.info(
                "Step %d/%d: applying %s",
                i + 1,
                len(recipe.effects),
                effect.name,
            )

            # Resolve parameter ranges with a step-specific seed
            step_seed = seed + i
            resolved = resolve_params(step.params, seed=step_seed)

            # Apply the effect
            result = effect.apply(current_image, resolved, context)
            current_image = result.image.convert("RGB")

            steps.append({
                "effect": effect.name,
                "description": effect.description,
                "resolved_params": resolved,
                "metadata": result.metadata,
            })

            logger.info("Step %d complete: %s", i + 1, result.metadata)
    finally:
        if cleanup_temp:
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)

    return PipelineResult(
        image=current_image,
        recipe_name=recipe.name,
        steps=steps,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_pipeline.py -v`
Expected: All 5 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add sparagmos/pipeline.py tests/test_pipeline.py
git commit -m "feat: pipeline engine for chaining recipe effects

Runs a recipe's effect chain sequentially, resolving param ranges
per-step with deterministic seeding. Collects provenance metadata
(resolved params, effect metadata) for each step. Handles temp
directory lifecycle for subprocess effects."
```

---

## Task 5: State Management

**Files:**
- Create: `sparagmos/state.py`
- Create: `tests/test_state.py`

- [ ] **Step 1: Write tests**

```python
"""Tests for state management."""

import json
from pathlib import Path

import pytest

from sparagmos.state import State, ProcessedEntry


@pytest.fixture
def state_file(tmp_path):
    return tmp_path / "state.json"


@pytest.fixture
def empty_state(state_file):
    state_file.write_text(json.dumps({"processed": []}))
    return State(state_file)


def test_load_empty_state(empty_state):
    assert len(empty_state.processed) == 0


def test_load_missing_file_creates_empty(tmp_path):
    path = tmp_path / "missing.json"
    state = State(path)
    assert len(state.processed) == 0


def test_add_entry(empty_state):
    empty_state.add(
        source_file_id="F123",
        source_date="2026-01-15",
        source_user="U456",
        recipe="test-recipe",
        effects=["effect_a", "effect_b"],
        processed_date="2026-03-26",
        posted_ts="123.456",
    )
    assert len(empty_state.processed) == 1
    assert empty_state.processed[0].source_file_id == "F123"


def test_save_and_reload(empty_state, state_file):
    empty_state.add(
        source_file_id="F789",
        source_date="2026-02-01",
        source_user="U111",
        recipe="vhs-meltdown",
        effects=["crt_vhs"],
        processed_date="2026-03-26",
    )
    empty_state.save()

    reloaded = State(state_file)
    assert len(reloaded.processed) == 1
    assert reloaded.processed[0].recipe == "vhs-meltdown"


def test_is_processed_checks_file_and_recipe(empty_state):
    empty_state.add(
        source_file_id="F123",
        source_date="2026-01-15",
        source_user="U456",
        recipe="recipe-a",
        effects=["effect_a"],
        processed_date="2026-03-26",
    )
    assert empty_state.is_processed("F123", "recipe-a") is True
    assert empty_state.is_processed("F123", "recipe-b") is False
    assert empty_state.is_processed("F999", "recipe-a") is False


def test_all_file_ids(empty_state):
    empty_state.add(
        source_file_id="F1",
        source_date="2026-01-01",
        source_user="U1",
        recipe="r1",
        effects=[],
        processed_date="2026-03-26",
    )
    empty_state.add(
        source_file_id="F2",
        source_date="2026-01-02",
        source_user="U2",
        recipe="r2",
        effects=[],
        processed_date="2026-03-26",
    )
    assert empty_state.all_file_ids() == {"F1", "F2"}


def test_processed_pairs(empty_state):
    empty_state.add(
        source_file_id="F1",
        source_date="2026-01-01",
        source_user="U1",
        recipe="r1",
        effects=[],
        processed_date="2026-03-26",
    )
    pairs = empty_state.processed_pairs()
    assert ("F1", "r1") in pairs
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_state.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement state.py**

```python
"""JSON state management for tracking processed images."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path


@dataclass
class ProcessedEntry:
    """Record of a processed image."""

    source_file_id: str
    source_date: str
    source_user: str
    recipe: str
    effects: list[str]
    processed_date: str
    posted_ts: str = ""


@dataclass
class State:
    """Manages the state.json file tracking processed images."""

    path: Path
    processed: list[ProcessedEntry] = field(default_factory=list)

    def __init__(self, path: Path):
        self.path = path
        self.processed = []
        if path.exists():
            data = json.loads(path.read_text())
            for entry in data.get("processed", []):
                self.processed.append(ProcessedEntry(**entry))

    def add(
        self,
        source_file_id: str,
        source_date: str,
        source_user: str,
        recipe: str,
        effects: list[str],
        processed_date: str,
        posted_ts: str = "",
    ) -> None:
        """Add a new processed entry."""
        self.processed.append(
            ProcessedEntry(
                source_file_id=source_file_id,
                source_date=source_date,
                source_user=source_user,
                recipe=recipe,
                effects=effects,
                processed_date=processed_date,
                posted_ts=posted_ts,
            )
        )

    def save(self) -> None:
        """Write state to disk."""
        data = {"processed": [asdict(e) for e in self.processed]}
        self.path.write_text(json.dumps(data, indent=2) + "\n")

    def is_processed(self, file_id: str, recipe: str) -> bool:
        """Check if a file+recipe pair has been processed."""
        return (file_id, recipe) in self.processed_pairs()

    def all_file_ids(self) -> set[str]:
        """Return all source file IDs that have been processed."""
        return {e.source_file_id for e in self.processed}

    def processed_pairs(self) -> set[tuple[str, str]]:
        """Return all (file_id, recipe) pairs that have been processed."""
        return {(e.source_file_id, e.recipe) for e in self.processed}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_state.py -v`
Expected: All 7 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add sparagmos/state.py tests/test_state.py
git commit -m "feat: state management for tracking processed images

JSON-backed state tracks (file_id, recipe) pairs to avoid repeats.
Supports exhaustion — same image can be reprocessed with different
recipe. Save/load roundtrip with ProcessedEntry dataclass."
```

---

## Task 6: Slack Source (Scrape #image-gen)

**Files:**
- Create: `sparagmos/slack_source.py`
- Create: `tests/test_slack.py`

- [ ] **Step 1: Write tests**

```python
"""Tests for Slack source scraping and posting."""

from unittest.mock import MagicMock, patch
import pytest

from sparagmos.slack_source import (
    find_channel_id,
    fetch_image_files,
    pick_random_image,
    download_image,
)


def _mock_conversations_list(channels, cursor=None):
    """Create a mock conversations_list response."""
    return {
        "channels": channels,
        "response_metadata": {"next_cursor": cursor or ""},
    }


def _mock_conversations_history(messages, cursor=None):
    """Create a mock conversations_history response."""
    return {
        "messages": messages,
        "response_metadata": {"next_cursor": cursor or ""},
    }


def test_find_channel_id():
    client = MagicMock()
    client.conversations_list.return_value = _mock_conversations_list(
        [{"name": "image-gen", "id": "C123"}]
    )
    assert find_channel_id(client, "image-gen") == "C123"


def test_find_channel_id_not_found():
    client = MagicMock()
    client.conversations_list.return_value = _mock_conversations_list(
        [{"name": "other", "id": "C999"}]
    )
    assert find_channel_id(client, "image-gen") is None


def test_fetch_image_files():
    client = MagicMock()
    client.conversations_history.return_value = _mock_conversations_history([
        {
            "ts": "1000.0",
            "user": "U123",
            "files": [
                {
                    "id": "F1",
                    "mimetype": "image/png",
                    "url_private_download": "https://files.slack.com/F1.png",
                    "name": "art.png",
                    "timestamp": 1000,
                },
            ],
        },
        {
            "ts": "2000.0",
            "user": "U456",
            "text": "just chatting, no files",
        },
        {
            "ts": "3000.0",
            "user": "U789",
            "files": [
                {
                    "id": "F2",
                    "mimetype": "application/pdf",
                    "url_private_download": "https://files.slack.com/F2.pdf",
                    "name": "doc.pdf",
                    "timestamp": 3000,
                },
            ],
        },
    ])
    files = fetch_image_files(client, "C123")
    # Should only include image files, not PDFs
    assert len(files) == 1
    assert files[0]["id"] == "F1"


def test_pick_random_image_excludes_processed():
    files = [
        {"id": "F1", "user": "U1", "timestamp": 1000},
        {"id": "F2", "user": "U2", "timestamp": 2000},
        {"id": "F3", "user": "U3", "timestamp": 3000},
    ]
    processed_pairs = {("F1", "recipe-a"), ("F2", "recipe-a")}
    result = pick_random_image(files, "recipe-a", processed_pairs, seed=42)
    assert result["id"] == "F3"


def test_pick_random_image_all_processed_with_recipe():
    files = [
        {"id": "F1", "user": "U1", "timestamp": 1000},
    ]
    processed_pairs = {("F1", "recipe-a")}
    result = pick_random_image(files, "recipe-a", processed_pairs, seed=42)
    assert result is None


def test_pick_random_image_allows_different_recipe():
    files = [
        {"id": "F1", "user": "U1", "timestamp": 1000},
    ]
    processed_pairs = {("F1", "recipe-a")}
    result = pick_random_image(files, "recipe-b", processed_pairs, seed=42)
    assert result["id"] == "F1"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_slack.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement slack_source.py**

```python
"""Scrape random images from a Slack channel."""

from __future__ import annotations

import logging
import random
from typing import Any

import requests
from slack_sdk import WebClient

logger = logging.getLogger(__name__)

IMAGE_MIMETYPES = {"image/png", "image/jpeg", "image/gif", "image/webp"}


def find_channel_id(client: WebClient, channel_name: str) -> str | None:
    """Find a Slack channel ID by name.

    Args:
        client: Slack WebClient.
        channel_name: Channel name (with or without #).

    Returns:
        Channel ID string, or None if not found.
    """
    name = channel_name.lstrip("#")
    cursor = None
    while True:
        kwargs: dict[str, Any] = {"types": "public_channel", "limit": 200}
        if cursor:
            kwargs["cursor"] = cursor
        resp = client.conversations_list(**kwargs)
        for ch in resp["channels"]:
            if ch["name"] == name:
                return ch["id"]
        cursor = resp.get("response_metadata", {}).get("next_cursor")
        if not cursor:
            return None


def fetch_image_files(client: WebClient, channel_id: str) -> list[dict[str, Any]]:
    """Fetch all image file attachments from a channel's history.

    Args:
        client: Slack WebClient.
        channel_id: Channel ID to scrape.

    Returns:
        List of file metadata dicts (id, mimetype, url, user, timestamp).
    """
    image_files = []
    cursor = None
    while True:
        kwargs: dict[str, Any] = {"channel": channel_id, "limit": 200}
        if cursor:
            kwargs["cursor"] = cursor
        resp = client.conversations_history(**kwargs)

        for msg in resp["messages"]:
            for file_info in msg.get("files", []):
                if file_info.get("mimetype", "") in IMAGE_MIMETYPES:
                    image_files.append({
                        "id": file_info["id"],
                        "mimetype": file_info["mimetype"],
                        "url": file_info.get("url_private_download", ""),
                        "name": file_info.get("name", ""),
                        "user": msg.get("user", "unknown"),
                        "timestamp": file_info.get("timestamp", 0),
                    })

        cursor = resp.get("response_metadata", {}).get("next_cursor")
        if not cursor:
            break

    logger.info("Found %d image files in channel", len(image_files))
    return image_files


def pick_random_image(
    files: list[dict[str, Any]],
    recipe_slug: str,
    processed_pairs: set[tuple[str, str]],
    seed: int,
) -> dict[str, Any] | None:
    """Pick a random image that hasn't been processed with this recipe.

    Args:
        files: List of file metadata dicts.
        recipe_slug: Current recipe slug to check against.
        processed_pairs: Set of (file_id, recipe) pairs already processed.
        seed: RNG seed.

    Returns:
        File metadata dict, or None if all files processed with this recipe.
    """
    available = [f for f in files if (f["id"], recipe_slug) not in processed_pairs]

    if not available:
        logger.warning("All %d images processed with recipe %s", len(files), recipe_slug)
        return None

    rng = random.Random(seed)
    return rng.choice(available)


def download_image(url: str, token: str, timeout: int = 30) -> bytes:
    """Download an image from Slack, preserving auth through redirects.

    Args:
        url: Slack file URL (url_private_download).
        token: Slack bot token.
        timeout: Request timeout in seconds.

    Returns:
        Image bytes.

    Raises:
        requests.HTTPError: On non-200 response.
        ValueError: If response is not an image.
    """
    headers = {"Authorization": f"Bearer {token}"}
    max_redirects = 5
    for _ in range(max_redirects):
        resp = requests.get(url, headers=headers, timeout=timeout, allow_redirects=False)
        if resp.status_code in (301, 302, 303, 307, 308):
            url = resp.headers["Location"]
            continue
        resp.raise_for_status()

        content_type = resp.headers.get("Content-Type", "")
        if not content_type.startswith("image/"):
            raise ValueError(
                f"Expected image content, got {content_type!r}. "
                "Slack may have returned a login page."
            )
        return resp.content

    raise requests.TooManyRedirects(f"Too many redirects downloading {url}")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_slack.py -v`
Expected: All 6 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add sparagmos/slack_source.py tests/test_slack.py
git commit -m "feat: Slack source scraping for #image-gen

Find channel by name, fetch all image files with pagination,
pick random unprocessed image (respects file+recipe pairs),
download with auth-preserving redirect following."
```

---

## Task 7: Slack Posting

**Files:**
- Create: `sparagmos/slack_post.py`
- Modify: `tests/test_slack.py` (add posting tests)

- [ ] **Step 1: Write tests**

Add to `tests/test_slack.py`:

```python
from sparagmos.slack_post import format_provenance, post_result
from sparagmos.pipeline import PipelineResult
from PIL import Image


def test_format_provenance():
    steps = [
        {"effect": "deepdream", "description": "Neural hallucination"},
        {"effect": "channel_shift", "description": "RGB offset"},
        {"effect": "jpeg_destroy", "description": "Generational loss"},
    ]
    result = PipelineResult(
        image=Image.new("RGB", (64, 64)),
        recipe_name="Dionysian Rite",
        steps=steps,
    )
    source = {"user": "U123", "date": "2026-01-15"}
    text = format_provenance(result, source, channel_name="image-gen")
    assert "Dionysian Rite" in text
    assert "deepdream" in text
    assert "channel_shift" in text
    assert "jpeg_destroy" in text
    assert "→" in text
    assert "#image-gen" in text


def test_post_result_calls_upload(tmp_path):
    client = MagicMock()
    client.files_upload_v2.return_value = {"ok": True}

    img = Image.new("RGB", (64, 64))
    result = PipelineResult(
        image=img,
        recipe_name="Test Recipe",
        steps=[{"effect": "dummy", "description": "test"}],
    )
    source = {"user": "U123", "date": "2026-01-15"}

    post_result(client, "C456", result, source, "image-gen", tmp_path)

    client.files_upload_v2.assert_called_once()
    call_kwargs = client.files_upload_v2.call_args[1]
    assert call_kwargs["channel"] == "C456"
    assert "initial_comment" in call_kwargs
    assert "Dionysian" not in call_kwargs["initial_comment"]  # wrong recipe
    assert "Test Recipe" in call_kwargs["initial_comment"]
```

- [ ] **Step 2: Run new tests to verify they fail**

Run: `uv run pytest tests/test_slack.py::test_format_provenance tests/test_slack.py::test_post_result_calls_upload -v`
Expected: ImportError.

- [ ] **Step 3: Implement slack_post.py**

```python
"""Post processed images to Slack."""

from __future__ import annotations

import logging
from pathlib import Path

from PIL import Image
from slack_sdk import WebClient

from sparagmos.pipeline import PipelineResult

logger = logging.getLogger(__name__)


def format_provenance(
    result: PipelineResult,
    source: dict,
    channel_name: str = "image-gen",
) -> str:
    """Format the provenance text for the Slack message.

    Args:
        result: Pipeline result with recipe name and step metadata.
        source: Source image metadata (user, date).
        channel_name: Source channel name for attribution.

    Returns:
        Formatted provenance string for initial_comment.
    """
    chain = " → ".join(step["effect"] for step in result.steps)
    user = source.get("user", "unknown")
    date = source.get("date", "unknown")

    return (
        f"⛧ {result.recipe_name}\n"
        f"{chain}\n"
        f"source: image by <@{user}> in #{channel_name} ({date})"
    )


def post_result(
    client: WebClient,
    channel_id: str,
    result: PipelineResult,
    source: dict,
    source_channel_name: str,
    temp_dir: Path,
) -> str:
    """Post a processed image to Slack as a single message.

    Uses files_upload_v2 with initial_comment to combine image and
    text in one message (no threads).

    Args:
        client: Slack WebClient.
        channel_id: Target channel ID (#img-junkyard).
        result: Pipeline result with image and metadata.
        source: Source image metadata.
        source_channel_name: Name of source channel for attribution.
        temp_dir: Temp directory for saving the image file.

    Returns:
        Message timestamp of the posted message.
    """
    comment = format_provenance(result, source, source_channel_name)

    # Save image to temp file for upload
    image_path = temp_dir / "sparagmos_output.png"
    result.image.save(image_path, "PNG")

    logger.info("Posting to channel %s with comment:\n%s", channel_id, comment)

    response = client.files_upload_v2(
        channel=channel_id,
        file=str(image_path),
        filename="sparagmos.png",
        initial_comment=comment,
    )

    return response.get("ts", "")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_slack.py -v`
Expected: All 8 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add sparagmos/slack_post.py tests/test_slack.py
git commit -m "feat: Slack posting with provenance in single message

Format recipe name, effect chain (→ separated), and source attribution.
Post via files_upload_v2 with initial_comment for image + text in one
message (no threads)."
```

---

## Task 8: Llama Vision Integration

**Files:**
- Create: `sparagmos/vision.py`
- Create: `tests/test_vision.py`

- [ ] **Step 1: Write tests**

```python
"""Tests for Llama Vision integration."""

from unittest.mock import MagicMock, patch
from PIL import Image
import pytest

from sparagmos.vision import analyze_image, parse_vision_response


def test_parse_vision_response_extracts_objects():
    raw = (
        "The image contains a face in the upper-left quadrant, "
        "a landscape with mountains in the background, "
        "and text overlay reading 'hello world' at the bottom."
    )
    parsed = parse_vision_response(raw)
    assert isinstance(parsed, dict)
    assert "description" in parsed
    assert parsed["description"] == raw


def test_parse_vision_response_empty():
    parsed = parse_vision_response("")
    assert parsed["description"] == ""


@patch("sparagmos.vision.InferenceClient")
def test_analyze_image_calls_api(mock_client_cls):
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client
    mock_client.chat_completion.return_value = MagicMock(
        choices=[MagicMock(message=MagicMock(content="A beautiful landscape"))]
    )

    img = Image.new("RGB", (64, 64))
    result = analyze_image(img, token="fake-token")

    assert result["description"] == "A beautiful landscape"
    mock_client.chat_completion.assert_called_once()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_vision.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement vision.py**

```python
"""Llama Vision analysis via HF Inference API."""

from __future__ import annotations

import base64
import io
import logging
from typing import Any

from PIL import Image

logger = logging.getLogger(__name__)

VISION_MODEL = "meta-llama/Llama-3.2-11B-Vision-Instruct"

ANALYSIS_PROMPT = (
    "Analyze this image in detail. Describe:\n"
    "1. What objects, people, or creatures are present and where they are spatially\n"
    "2. The dominant colors and color palette\n"
    "3. The composition and visual structure\n"
    "4. Any text visible in the image\n"
    "5. The overall mood or aesthetic\n"
    "Be specific about spatial locations (top-left, center, bottom-right, etc)."
)


def analyze_image(
    image: Image.Image,
    token: str,
    model: str = VISION_MODEL,
) -> dict[str, Any]:
    """Analyze an image using Llama Vision via HF Inference API.

    Args:
        image: PIL Image to analyze.
        token: HuggingFace API token.
        model: Model ID to use.

    Returns:
        Dict with 'description' key containing the analysis text.
    """
    from huggingface_hub import InferenceClient

    # Encode image as base64
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    img_b64 = base64.b64encode(buffer.getvalue()).decode("utf-8")

    client = InferenceClient(token=token)

    response = client.chat_completion(
        model=model,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{img_b64}"},
                    },
                    {
                        "type": "text",
                        "text": ANALYSIS_PROMPT,
                    },
                ],
            }
        ],
        max_tokens=500,
    )

    raw_text = response.choices[0].message.content
    logger.info("Vision analysis: %s", raw_text[:200])

    return parse_vision_response(raw_text)


def parse_vision_response(raw: str) -> dict[str, Any]:
    """Parse the raw vision response into a structured dict.

    Currently stores the full text as 'description'. Future versions
    may extract structured spatial data for targeted effects.

    Args:
        raw: Raw text response from the vision model.

    Returns:
        Dict with parsed analysis data.
    """
    return {"description": raw}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_vision.py -v`
Expected: All 3 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add sparagmos/vision.py tests/test_vision.py
git commit -m "feat: Llama Vision integration via HF Inference API

Analyze images using Llama 3.2 Vision for spatial understanding.
Provides targeting hints for vision-aware recipe effects. Uses
base64 encoding for image upload, structured prompt for consistent
analysis output."
```

---

## Task 9: CLI

**Files:**
- Create: `sparagmos/cli.py`
- Create: `tests/test_cli.py`

- [ ] **Step 1: Write tests**

```python
"""Tests for the CLI interface."""

import sys
from unittest.mock import patch, MagicMock

import pytest

from sparagmos.cli import build_parser


def test_parser_defaults():
    parser = build_parser()
    args = parser.parse_args([])
    assert args.recipe is None
    assert args.input is None
    assert args.output is None
    assert args.dry_run is False
    assert args.list_recipes is False
    assert args.list_effects is False
    assert args.validate is False


def test_parser_recipe():
    parser = build_parser()
    args = parser.parse_args(["--recipe", "vhs-meltdown"])
    assert args.recipe == "vhs-meltdown"


def test_parser_local_mode():
    parser = build_parser()
    args = parser.parse_args(["--input", "photo.jpg", "--output", "out.png"])
    assert args.input == "photo.jpg"
    assert args.output == "out.png"


def test_parser_dry_run():
    parser = build_parser()
    args = parser.parse_args(["--dry-run"])
    assert args.dry_run is True


def test_parser_list_flags():
    parser = build_parser()

    args = parser.parse_args(["--list-recipes"])
    assert args.list_recipes is True

    args = parser.parse_args(["--list-effects"])
    assert args.list_effects is True

    args = parser.parse_args(["--validate"])
    assert args.validate is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_cli.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement cli.py**

```python
"""CLI entry point for sparagmos."""

from __future__ import annotations

import argparse
import logging
import os
import random
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image

logger = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser."""
    parser = argparse.ArgumentParser(
        prog="sparagmos",
        description="σπαραγμός — Automated image destruction bot",
    )
    parser.add_argument(
        "--recipe",
        help="Recipe name to use (default: random)",
    )
    parser.add_argument(
        "--input",
        help="Local image file to process (skips Slack scraping)",
    )
    parser.add_argument(
        "--output",
        help="Output file path (skips Slack posting)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Process image but don't post to Slack",
    )
    parser.add_argument(
        "--list-recipes",
        action="store_true",
        help="List available recipes and exit",
    )
    parser.add_argument(
        "--list-effects",
        action="store_true",
        help="List available effects and exit",
    )
    parser.add_argument(
        "--validate",
        action="store_true",
        help="Validate all recipes against effect schemas and exit",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="RNG seed for reproducibility",
    )
    parser.add_argument(
        "--recipes-dir",
        default=None,
        help="Path to recipes directory (default: recipes/ in repo root)",
    )
    return parser


def _find_repo_root() -> Path:
    """Find the repository root (where recipes/ lives)."""
    # Try relative to this file first
    pkg_dir = Path(__file__).parent
    repo_root = pkg_dir.parent
    if (repo_root / "recipes").is_dir():
        return repo_root
    # Fall back to cwd
    if (Path.cwd() / "recipes").is_dir():
        return Path.cwd()
    return repo_root


def main(argv: list[str] | None = None) -> None:
    """Main CLI entry point."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    parser = build_parser()
    args = parser.parse_args(argv)

    # Import here to allow effects to register on import
    from sparagmos.effects import list_effects
    from sparagmos.config import load_all_recipes, validate_recipe

    # Register all effects
    _register_all_effects()

    repo_root = _find_repo_root()
    recipes_dir = Path(args.recipes_dir) if args.recipes_dir else repo_root / "recipes"

    # Handle --list-effects
    if args.list_effects:
        effects = list_effects()
        if not effects:
            print("No effects registered.")
            return
        print(f"{'Effect':<20} {'Description':<50} {'Deps'}")
        print("-" * 80)
        for name, effect in sorted(effects.items()):
            deps = ", ".join(effect.requires) if effect.requires else "none"
            print(f"{name:<20} {effect.description:<50} {deps}")
        return

    # Handle --list-recipes
    if args.list_recipes:
        if not recipes_dir.is_dir():
            print(f"Recipes directory not found: {recipes_dir}")
            sys.exit(1)
        recipes = load_all_recipes(recipes_dir)
        if not recipes:
            print("No recipes found.")
            return
        for slug, recipe in sorted(recipes.items()):
            print(f"  {slug:<25} {recipe.name}")
            if recipe.description:
                desc = recipe.description.strip().split("\n")[0][:60]
                print(f"  {'':25} {desc}")
            print()
        return

    # Handle --validate
    if args.validate:
        if not recipes_dir.is_dir():
            print(f"Recipes directory not found: {recipes_dir}")
            sys.exit(1)
        recipes = load_all_recipes(recipes_dir)
        all_valid = True
        for slug, recipe in sorted(recipes.items()):
            errors = validate_recipe(recipe)
            if errors:
                all_valid = False
                print(f"FAIL {slug}:")
                for err in errors:
                    print(f"  - {err}")
            else:
                print(f"OK   {slug}")
        sys.exit(0 if all_valid else 1)

    # --- Main pipeline ---
    seed = args.seed if args.seed is not None else random.randint(0, 2**31)

    # Load recipes
    if not recipes_dir.is_dir():
        logger.error("Recipes directory not found: %s", recipes_dir)
        sys.exit(1)
    recipes = load_all_recipes(recipes_dir)
    if not recipes:
        logger.error("No recipes found in %s", recipes_dir)
        sys.exit(1)

    # Pick recipe
    if args.recipe:
        if args.recipe not in recipes:
            logger.error("Unknown recipe: %s. Available: %s", args.recipe, sorted(recipes.keys()))
            sys.exit(1)
        recipe_slug = args.recipe
    else:
        rng = random.Random(seed)
        recipe_slug = rng.choice(list(recipes.keys()))

    recipe = recipes[recipe_slug]
    logger.info("Using recipe: %s (%s)", recipe_slug, recipe.name)

    # Get source image
    if args.input:
        # Local mode
        source_image = Image.open(args.input).convert("RGB")
        source_metadata = {"user": "local", "date": "local"}
    else:
        # Slack mode
        from slack_sdk import WebClient
        from sparagmos.slack_source import (
            find_channel_id,
            fetch_image_files,
            pick_random_image,
            download_image,
        )
        from sparagmos.state import State
        import io

        token = os.environ.get("SLACK_BOT_TOKEN")
        if not token:
            logger.error("SLACK_BOT_TOKEN not set")
            sys.exit(1)

        client = WebClient(token=token)
        state = State(repo_root / "state.json")

        channel_id = find_channel_id(client, "image-gen")
        if not channel_id:
            logger.error("Channel #image-gen not found")
            sys.exit(1)

        files = fetch_image_files(client, channel_id)
        if not files:
            logger.error("No images found in #image-gen")
            sys.exit(1)

        selected = pick_random_image(files, recipe_slug, state.processed_pairs(), seed)
        if not selected:
            logger.warning("All images processed with recipe %s", recipe_slug)
            sys.exit(0)

        logger.info("Selected image: %s", selected["id"])
        image_bytes = download_image(selected["url"], token)
        source_image = Image.open(io.BytesIO(image_bytes)).convert("RGB")

        ts = selected.get("timestamp", 0)
        source_date = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d") if ts else "unknown"
        source_metadata = {"user": selected["user"], "date": source_date}

    # Vision analysis (if recipe needs it)
    vision_data = None
    if recipe.vision:
        hf_token = os.environ.get("HF_TOKEN")
        if not hf_token:
            logger.warning("HF_TOKEN not set, skipping vision analysis")
        else:
            from sparagmos.vision import analyze_image
            vision_data = analyze_image(source_image, token=hf_token)

    # Run pipeline
    from sparagmos.pipeline import run_pipeline

    with tempfile.TemporaryDirectory(prefix="sparagmos_") as tmp:
        result = run_pipeline(
            image=source_image,
            recipe=recipe,
            seed=seed,
            temp_dir=Path(tmp),
            vision=vision_data,
            source_metadata=source_metadata,
        )

        # Output
        if args.output:
            result.image.save(args.output, "PNG")
            logger.info("Saved output to %s", args.output)
        elif args.dry_run:
            logger.info("Dry run — not posting to Slack")
            logger.info("Recipe: %s", result.recipe_name)
            for step in result.steps:
                logger.info("  %s: %s", step["effect"], step["resolved_params"])
        else:
            # Post to Slack
            from sparagmos.slack_post import post_result

            junkyard_id = find_channel_id(client, "img-junkyard")
            if not junkyard_id:
                logger.error("Channel #img-junkyard not found")
                sys.exit(1)

            posted_ts = post_result(
                client, junkyard_id, result, source_metadata, "image-gen", Path(tmp)
            )

            # Update state
            today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            state.add(
                source_file_id=selected["id"],
                source_date=source_metadata["date"],
                source_user=source_metadata["user"],
                recipe=recipe_slug,
                effects=[s["effect"] for s in result.steps],
                processed_date=today,
                posted_ts=posted_ts,
            )
            state.save()
            logger.info("State saved. Done.")


def _register_all_effects():
    """Import all effect modules to trigger registration."""
    import importlib
    import pkgutil

    import sparagmos.effects as effects_pkg

    for importer, modname, ispkg in pkgutil.iter_modules(effects_pkg.__path__):
        try:
            importlib.import_module(f"sparagmos.effects.{modname}")
        except ImportError as e:
            logger.debug("Skipping effect %s: %s", modname, e)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_cli.py -v`
Expected: All 5 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add sparagmos/cli.py sparagmos/__main__.py tests/test_cli.py
git commit -m "feat: CLI with full daily run, local mode, and management commands

Argparse CLI: --recipe, --input/--output (local mode), --dry-run,
--list-recipes, --list-effects, --validate, --seed. Full daily
pipeline: Slack scrape → optional vision → recipe → pipeline → post.
Auto-discovers and registers all effect modules."
```

---

## Task 10: First Pure Python Effects — channel_shift, jpeg_destroy, pixel_sort

These three effects establish the pattern for pure Python effects. Each is self-contained and uses only Pillow/numpy.

**Files:**
- Create: `sparagmos/effects/channel_shift.py`
- Create: `sparagmos/effects/jpeg_destroy.py`
- Create: `sparagmos/effects/pixel_sort.py`
- Create: `tests/test_effects/test_channel_shift.py`
- Create: `tests/test_effects/test_jpeg_destroy.py`
- Create: `tests/test_effects/test_pixel_sort.py`

- [ ] **Step 1: Write tests for channel_shift**

```python
"""Tests for channel shift effect."""

import numpy as np
import pytest
from PIL import Image

from sparagmos.effects import EffectContext, register_effect
from sparagmos.effects.channel_shift import ChannelShiftEffect


@pytest.fixture
def effect():
    e = ChannelShiftEffect()
    register_effect(e)
    return e


@pytest.fixture
def context(tmp_path):
    return EffectContext(vision=None, temp_dir=tmp_path, seed=42, source_metadata={})


def test_apply_produces_valid_image(effect, test_image_rgb, context):
    params = {"offset_r": 10, "offset_g": 0, "offset_b": -10}
    result = effect.apply(test_image_rgb, params, context)
    assert result.image.size == test_image_rgb.size
    assert result.image.mode == "RGB"


def test_apply_actually_shifts_channels(effect, test_image_rgb, context):
    params = {"offset_r": 20, "offset_g": 0, "offset_b": 0}
    result = effect.apply(test_image_rgb, params, context)
    # The images should differ since we shifted a channel
    orig = np.array(test_image_rgb)
    shifted = np.array(result.image)
    assert not np.array_equal(orig, shifted)


def test_zero_offsets_is_identity(effect, test_image_rgb, context):
    params = {"offset_r": 0, "offset_g": 0, "offset_b": 0}
    result = effect.apply(test_image_rgb, params, context)
    orig = np.array(test_image_rgb)
    out = np.array(result.image)
    np.testing.assert_array_equal(orig, out)


def test_validate_params_defaults(effect):
    params = effect.validate_params({})
    assert "offset_r" in params
    assert "offset_g" in params
    assert "offset_b" in params


def test_validate_params_clamps(effect):
    params = effect.validate_params({"offset_r": 9999})
    assert params["offset_r"] <= 500


def test_works_with_tiny_image(effect, test_image_tiny, context):
    params = {"offset_r": 2, "offset_g": 0, "offset_b": -1}
    result = effect.apply(test_image_tiny, params, context)
    assert result.image.size == test_image_tiny.size
```

- [ ] **Step 2: Write tests for jpeg_destroy**

```python
"""Tests for JPEG destruction effect."""

import numpy as np
import pytest
from PIL import Image

from sparagmos.effects import EffectContext, register_effect
from sparagmos.effects.jpeg_destroy import JpegDestroyEffect


@pytest.fixture
def effect():
    e = JpegDestroyEffect()
    register_effect(e)
    return e


@pytest.fixture
def context(tmp_path):
    return EffectContext(vision=None, temp_dir=tmp_path, seed=42, source_metadata={})


def test_apply_produces_valid_image(effect, test_image_rgb, context):
    params = {"quality": 5, "iterations": 3}
    result = effect.apply(test_image_rgb, params, context)
    assert result.image.size == test_image_rgb.size
    assert result.image.mode == "RGB"


def test_low_quality_degrades_image(effect, test_image_rgb, context):
    params = {"quality": 1, "iterations": 10}
    result = effect.apply(test_image_rgb, params, context)
    orig = np.array(test_image_rgb)
    destroyed = np.array(result.image)
    # Should be significantly different
    diff = np.abs(orig.astype(float) - destroyed.astype(float)).mean()
    assert diff > 5  # Meaningful degradation


def test_metadata_records_params(effect, test_image_rgb, context):
    params = {"quality": 3, "iterations": 5}
    result = effect.apply(test_image_rgb, params, context)
    assert result.metadata["quality"] == 3
    assert result.metadata["iterations"] == 5


def test_validate_params_defaults(effect):
    params = effect.validate_params({})
    assert 1 <= params["quality"] <= 95
    assert params["iterations"] >= 1


def test_validate_params_clamps_quality(effect):
    params = effect.validate_params({"quality": 0})
    assert params["quality"] >= 1
    params = effect.validate_params({"quality": 100})
    assert params["quality"] <= 95
```

- [ ] **Step 3: Write tests for pixel_sort**

```python
"""Tests for pixel sorting effect."""

import numpy as np
import pytest
from PIL import Image

from sparagmos.effects import EffectContext, register_effect
from sparagmos.effects.pixel_sort import PixelSortEffect


@pytest.fixture
def effect():
    e = PixelSortEffect()
    register_effect(e)
    return e


@pytest.fixture
def context(tmp_path):
    return EffectContext(vision=None, temp_dir=tmp_path, seed=42, source_metadata={})


def test_apply_produces_valid_image(effect, test_image_rgb, context):
    params = {"mode": "brightness", "direction": "horizontal", "threshold_low": 0.1, "threshold_high": 0.9}
    result = effect.apply(test_image_rgb, params, context)
    assert result.image.size == test_image_rgb.size
    assert result.image.mode == "RGB"


def test_apply_modifies_image(effect, test_image_rgb, context):
    params = {"mode": "brightness", "direction": "horizontal", "threshold_low": 0.1, "threshold_high": 0.9}
    result = effect.apply(test_image_rgb, params, context)
    orig = np.array(test_image_rgb)
    sorted_img = np.array(result.image)
    assert not np.array_equal(orig, sorted_img)


def test_vertical_sort(effect, test_image_rgb, context):
    params = {"mode": "brightness", "direction": "vertical", "threshold_low": 0.1, "threshold_high": 0.9}
    result = effect.apply(test_image_rgb, params, context)
    assert result.image.size == test_image_rgb.size


def test_hue_sort_mode(effect, test_image_rgb, context):
    params = {"mode": "hue", "direction": "horizontal", "threshold_low": 0.2, "threshold_high": 0.8}
    result = effect.apply(test_image_rgb, params, context)
    assert result.image.size == test_image_rgb.size


def test_validate_params_defaults(effect):
    params = effect.validate_params({})
    assert params["mode"] in ("brightness", "hue", "saturation")
    assert params["direction"] in ("horizontal", "vertical")


def test_validate_params_bad_mode(effect):
    from sparagmos.effects import ConfigError
    with pytest.raises(ConfigError):
        effect.validate_params({"mode": "invalid"})


def test_works_with_tiny_image(effect, test_image_tiny, context):
    params = {"mode": "brightness", "direction": "horizontal", "threshold_low": 0.1, "threshold_high": 0.9}
    result = effect.apply(test_image_tiny, params, context)
    assert result.image.size == (4, 4)
```

- [ ] **Step 4: Run all effect tests to verify they fail**

Run: `uv run pytest tests/test_effects/test_channel_shift.py tests/test_effects/test_jpeg_destroy.py tests/test_effects/test_pixel_sort.py -v`
Expected: ImportError for all three modules.

- [ ] **Step 5: Implement channel_shift.py**

```python
"""Channel shift effect — offset/swap RGB channels."""

from __future__ import annotations

import numpy as np
from PIL import Image

from sparagmos.effects import ConfigError, Effect, EffectContext, EffectResult, register_effect


class ChannelShiftEffect(Effect):
    name = "channel_shift"
    description = "Offset/swap/separate RGB channels, chromatic aberration"
    requires: list[str] = []

    def apply(self, image: Image.Image, params: dict, context: EffectContext) -> EffectResult:
        params = self.validate_params(params)
        arr = np.array(image.convert("RGB"))

        offset_r = params["offset_r"]
        offset_g = params["offset_g"]
        offset_b = params["offset_b"]

        result = np.zeros_like(arr)
        result[:, :, 0] = np.roll(arr[:, :, 0], offset_r, axis=1)
        result[:, :, 1] = np.roll(arr[:, :, 1], offset_g, axis=1)
        result[:, :, 2] = np.roll(arr[:, :, 2], offset_b, axis=1)

        return EffectResult(
            image=Image.fromarray(result),
            metadata={"offset_r": offset_r, "offset_g": offset_g, "offset_b": offset_b},
        )

    def validate_params(self, params: dict) -> dict:
        validated = {
            "offset_r": params.get("offset_r", 10),
            "offset_g": params.get("offset_g", 0),
            "offset_b": params.get("offset_b", -10),
        }
        for key in ("offset_r", "offset_g", "offset_b"):
            validated[key] = max(-500, min(500, int(validated[key])))
        return validated


register_effect(ChannelShiftEffect())
```

- [ ] **Step 6: Implement jpeg_destroy.py**

```python
"""JPEG destruction — multi-generation lossy compression."""

from __future__ import annotations

import io

from PIL import Image

from sparagmos.effects import Effect, EffectContext, EffectResult, register_effect


class JpegDestroyEffect(Effect):
    name = "jpeg_destroy"
    description = "Multi-generation JPEG compression — generational loss as art"
    requires: list[str] = []

    def apply(self, image: Image.Image, params: dict, context: EffectContext) -> EffectResult:
        params = self.validate_params(params)
        quality = params["quality"]
        iterations = params["iterations"]

        current = image.convert("RGB")
        for _ in range(iterations):
            buffer = io.BytesIO()
            current.save(buffer, format="JPEG", quality=quality)
            buffer.seek(0)
            current = Image.open(buffer).convert("RGB")
            # Force load so the buffer can be reused
            current.load()

        return EffectResult(
            image=current,
            metadata={"quality": quality, "iterations": iterations},
        )

    def validate_params(self, params: dict) -> dict:
        quality = params.get("quality", 5)
        quality = max(1, min(95, int(quality)))

        iterations = params.get("iterations", 10)
        iterations = max(1, min(100, int(iterations)))

        return {"quality": quality, "iterations": iterations}


register_effect(JpegDestroyEffect())
```

- [ ] **Step 7: Implement pixel_sort.py**

```python
"""Pixel sorting effect — sort rows/columns by brightness, hue, or saturation."""

from __future__ import annotations

import numpy as np
from PIL import Image

from sparagmos.effects import ConfigError, Effect, EffectContext, EffectResult, register_effect

VALID_MODES = ("brightness", "hue", "saturation")
VALID_DIRECTIONS = ("horizontal", "vertical")


def _get_sort_key(pixel_row: np.ndarray, mode: str) -> np.ndarray:
    """Compute sort key for a row of RGB pixels."""
    r, g, b = pixel_row[:, 0], pixel_row[:, 1], pixel_row[:, 2]
    if mode == "brightness":
        return 0.299 * r + 0.587 * g + 0.114 * b
    elif mode == "hue":
        # Simplified hue approximation
        max_c = np.maximum(np.maximum(r, g), b).astype(float)
        min_c = np.minimum(np.minimum(r, g), b).astype(float)
        delta = max_c - min_c
        hue = np.zeros_like(delta)
        mask = delta > 0
        # Red dominant
        rm = mask & (max_c == r)
        hue[rm] = (60 * ((g[rm] - b[rm]) / delta[rm]) % 360)
        # Green dominant
        gm = mask & (max_c == g)
        hue[gm] = (60 * ((b[gm] - r[gm]) / delta[gm]) + 120)
        # Blue dominant
        bm = mask & (max_c == b)
        hue[bm] = (60 * ((r[bm] - g[bm]) / delta[bm]) + 240)
        return hue
    elif mode == "saturation":
        max_c = np.maximum(np.maximum(r, g), b).astype(float)
        min_c = np.minimum(np.minimum(r, g), b).astype(float)
        sat = np.zeros_like(max_c)
        mask = max_c > 0
        sat[mask] = (max_c[mask] - min_c[mask]) / max_c[mask]
        return sat
    return np.zeros(len(pixel_row))


def _sort_row(row: np.ndarray, mode: str, threshold_low: float, threshold_high: float) -> np.ndarray:
    """Sort a single row of pixels within threshold bounds."""
    keys = _get_sort_key(row, mode)
    key_max = keys.max() if keys.max() > 0 else 1.0
    normalized = keys / key_max

    result = row.copy()
    in_segment = False
    start = 0

    for i in range(len(normalized)):
        if threshold_low <= normalized[i] <= threshold_high:
            if not in_segment:
                start = i
                in_segment = True
        else:
            if in_segment:
                segment = result[start:i]
                seg_keys = keys[start:i]
                order = np.argsort(seg_keys)
                result[start:i] = segment[order]
                in_segment = False

    # Handle final segment
    if in_segment:
        segment = result[start:]
        seg_keys = keys[start:]
        order = np.argsort(seg_keys)
        result[start:] = segment[order]

    return result


class PixelSortEffect(Effect):
    name = "pixel_sort"
    description = "Sort pixel rows/columns by brightness, hue, or saturation"
    requires: list[str] = []

    def apply(self, image: Image.Image, params: dict, context: EffectContext) -> EffectResult:
        params = self.validate_params(params)
        arr = np.array(image.convert("RGB"))

        mode = params["mode"]
        direction = params["direction"]
        threshold_low = params["threshold_low"]
        threshold_high = params["threshold_high"]

        if direction == "vertical":
            arr = arr.transpose(1, 0, 2)

        for i in range(arr.shape[0]):
            arr[i] = _sort_row(arr[i], mode, threshold_low, threshold_high)

        if direction == "vertical":
            arr = arr.transpose(1, 0, 2)

        return EffectResult(
            image=Image.fromarray(arr),
            metadata={"mode": mode, "direction": direction},
        )

    def validate_params(self, params: dict) -> dict:
        mode = params.get("mode", "brightness")
        if mode not in VALID_MODES:
            raise ConfigError(
                f"Invalid mode {mode!r}. Must be one of {VALID_MODES}",
                effect_name=self.name,
                param_name="mode",
            )

        direction = params.get("direction", "horizontal")
        if direction not in VALID_DIRECTIONS:
            raise ConfigError(
                f"Invalid direction {direction!r}. Must be one of {VALID_DIRECTIONS}",
                effect_name=self.name,
                param_name="direction",
            )

        threshold_low = float(params.get("threshold_low", 0.25))
        threshold_high = float(params.get("threshold_high", 0.75))
        threshold_low = max(0.0, min(1.0, threshold_low))
        threshold_high = max(0.0, min(1.0, threshold_high))

        return {
            "mode": mode,
            "direction": direction,
            "threshold_low": threshold_low,
            "threshold_high": threshold_high,
        }


register_effect(PixelSortEffect())
```

- [ ] **Step 8: Run tests to verify they pass**

Run: `uv run pytest tests/test_effects/test_channel_shift.py tests/test_effects/test_jpeg_destroy.py tests/test_effects/test_pixel_sort.py -v`
Expected: All 18 tests PASS.

- [ ] **Step 9: Commit**

```bash
git add sparagmos/effects/channel_shift.py sparagmos/effects/jpeg_destroy.py sparagmos/effects/pixel_sort.py tests/test_effects/test_channel_shift.py tests/test_effects/test_jpeg_destroy.py tests/test_effects/test_pixel_sort.py
git commit -m "feat: first three effects — channel_shift, jpeg_destroy, pixel_sort

Pure Python effects using Pillow and numpy. Channel shift offsets RGB
channels independently. JPEG destroy applies multi-generation lossy
compression. Pixel sort sorts rows/columns by brightness/hue/saturation
within threshold bounds."
```

---

## Task 11: More Pure Python Effects — byte_corrupt, dither, crt_vhs, cellular, pca_decompose, fractal_blend

These follow the same pattern as Task 10. Each has tests, implementation, and self-registration.

**Files:**
- Create: `sparagmos/effects/byte_corrupt.py` + test
- Create: `sparagmos/effects/dither.py` + test
- Create: `sparagmos/effects/crt_vhs.py` + test
- Create: `sparagmos/effects/cellular.py` + test
- Create: `sparagmos/effects/pca_decompose.py` + test
- Create: `sparagmos/effects/fractal_blend.py` + test

Each effect follows the established pattern from Task 10:
1. Write failing tests (apply produces valid image, modifies image, validate_params defaults/clamps/rejects, edge cases)
2. Run tests to verify failure
3. Implement effect class with `apply()`, `validate_params()`, and `register_effect()` at module level
4. Run tests to verify passing
5. Commit

**Key implementation notes per effect:**

**byte_corrupt**: Read image as raw bytes (via PIL tobytes/frombytes). Flip random bytes (skip first N header bytes if operating on encoded format). Params: `num_flips` (int), `skip_header` (int, bytes to skip), `mode` (one of "flip", "inject", "replace").

**dither**: Convert to limited palette using PIL's `quantize()` with custom palettes. Built-in palettes: CGA (4 colors), EGA (16), Game Boy (4 greens), thermal (orange-white gradient). Params: `palette` (string), `algorithm` (one of "floyd_steinberg", "bayer", "atkinson"), `num_colors` (int, for custom).

**crt_vhs**: Composite effect: add scan lines (horizontal dark bars at regular intervals), optional horizontal jitter (shift random rows left/right), optional color bleeding (Gaussian blur on chroma channels in YCbCr space), phosphor glow (slight bloom). Params: `scan_line_density` (int), `jitter_amount` (int), `color_bleed` (float), `phosphor_glow` (float).

**cellular**: Convert to grayscale, threshold to binary, run Game of Life (or Rule 110 for 1D) for N generations, map result back to image. Params: `rule` (one of "game_of_life", "rule_110"), `generations` (int), `threshold` (int 0-255), `colorize` (bool — map generations to color gradient).

**pca_decompose**: Flatten image channels, compute PCA via numpy SVD, reconstruct with only top (or bottom) N components. Ghostly, abstract results. Params: `n_components` (int), `mode` (one of "top", "bottom" — keep best or worst components).

**fractal_blend**: Generate Mandelbrot set at coordinates derived from image histogram (mean hue → real center, mean brightness → imaginary center, std dev → zoom). Blend with original at given opacity. Params: `opacity` (float), `iterations` (int), `colormap` (string).

- [ ] **Step 1-5 for each effect:** Follow the TDD cycle from Task 10 for all six effects.

- [ ] **Step 6: Run all pure Python effect tests**

Run: `uv run pytest tests/test_effects/ -v -k "not deepdream and not style_transfer and not pix2pix and not neural_doodle and not inpaint"`
Expected: All tests PASS.

- [ ] **Step 7: Commit**

```bash
git add sparagmos/effects/ tests/test_effects/
git commit -m "feat: six more pure Python effects

byte_corrupt (raw byte manipulation), dither (Floyd-Steinberg/Bayer
with retro palettes — CGA, EGA, Game Boy, thermal), crt_vhs (scan
lines, jitter, color bleed, phosphor glow), cellular (Game of Life /
Rule 110 on pixel data), pca_decompose (PCA/SVD reconstruction with
top/bottom N components), fractal_blend (Mandelbrot at image-derived
coordinates)."
```

---

## Task 12: Subprocess Effects — imagemagick, netpbm, format_roundtrip, primitive

These effects shell out to system tools. They inherit from `SubprocessEffect`.

**Files:**
- Create: `sparagmos/effects/imagemagick.py` + test
- Create: `sparagmos/effects/netpbm.py` + test
- Create: `sparagmos/effects/format_roundtrip.py` + test
- Create: `sparagmos/effects/primitive.py` + test

Each test file uses `pytest.mark.skipif` for missing system deps:

```python
import shutil
import pytest

HAS_IMAGEMAGICK = shutil.which("convert") is not None
pytestmark = pytest.mark.skipif(not HAS_IMAGEMAGICK, reason="ImageMagick not installed")
```

**Key implementation notes:**

**imagemagick**: Wrapper around `convert` command. Params: `operations` (list of ImageMagick operations like `["-implode", "0.5"]`, `["-swirl", "90"]`), or named presets: `preset` (one of "implode", "swirl", "wave", "plasma_overlay", "fx_noise"). Each preset maps to specific `-convert` flags. Save temp input, run convert, load output.

**netpbm**: Wrapper around NetPBM tools. Convert input to PNM format, pipe through selected NetPBM filter, convert back to PNG. Params: `filter` (one of "pgmcrater", "ppmforge", "ppmspread", "pgmbentley"), plus filter-specific params. Uses `requires = ["pnmtopng"]` for dep check.

**format_roundtrip**: Chain of lossy format conversions. Params: `chain` (list of format names, e.g., `["jpeg", "bmp", "jpeg"]`), `jpeg_quality` (int for JPEG steps). For potrace roundtrip: convert to bitmap → run potrace → rasterize SVG back to PNG. Uses `requires = ["potrace"]` for potrace chain.

**primitive**: Wrapper around the `primitive` Go binary. Params: `shapes` (int — number of shapes), `shape_type` (one of "triangle", "rectangle", "ellipse", "circle", "rotated_rect"), `alpha` (int, shape opacity). Produces abstract geometric reconstructions. `requires = ["primitive"]`.

- [ ] **Step 1-5 for each effect:** Follow the TDD cycle. Skip tests when deps missing.

- [ ] **Step 6: Run subprocess effect tests (if deps installed)**

Run: `uv run pytest tests/test_effects/test_imagemagick.py tests/test_effects/test_netpbm.py tests/test_effects/test_format_roundtrip.py tests/test_effects/test_primitive.py -v`
Expected: Tests pass if deps installed, skip if not.

- [ ] **Step 7: Commit**

```bash
git add sparagmos/effects/ tests/test_effects/
git commit -m "feat: subprocess effects — imagemagick, netpbm, format_roundtrip, primitive

ImageMagick wrapper with named presets (implode, swirl, wave, plasma,
fx_noise). NetPBM wrapper for ancient Unix filters (pgmcrater, ppmforge,
ppmspread). Format roundtrip lossy conversion chains including potrace
bitmap→vector→raster. Primitive geometric shape reconstruction. All
skip gracefully when system deps missing."
```

---

## Task 13: Audio/Spectral Effects — sonify, spectral, datamosh

**Files:**
- Create: `sparagmos/effects/sonify.py` + test
- Create: `sparagmos/effects/spectral.py` + test
- Create: `sparagmos/effects/datamosh.py` + test

**Key implementation notes:**

**sonify**: Convert image to raw bytes, interpret as 16-bit PCM audio samples. Apply scipy audio DSP: reverb (convolve with decaying impulse), echo (add delayed copy), distortion (clip + amplify). Convert back to image bytes. Params: `effect` (one of "reverb", "echo", "distortion", "phaser"), `intensity` (float 0-1).

**spectral**: Treat image as spectrogram using scipy FFT. Apply spectral processing: frequency shift, band-pass filter, spectral blur. Inverse FFT back to image. Params: `operation` (one of "shift", "bandpass", "blur"), `amount` (float).

**datamosh**: Encode image as single-frame AVI with ffmpeg, manipulate the encoded bytes (swap P-frame data, corrupt motion vectors), decode back. Requires ffmpeg. Params: `corruption_amount` (float 0-1), `mode` (one of "iframe_remove", "mv_swap"). `requires = ["ffmpeg"]`.

- [ ] **Step 1-5 for each effect:** Follow TDD cycle.

- [ ] **Step 6: Commit**

```bash
git add sparagmos/effects/ tests/test_effects/
git commit -m "feat: audio/spectral effects — sonify, spectral, datamosh

Sonify treats pixels as audio samples, applies DSP (reverb, echo,
distortion, phaser). Spectral uses FFT for frequency-domain
manipulation. Datamosh encodes as video and corrupts motion vectors
via ffmpeg."
```

---

## Task 14: Neural Effects — deepdream, style_transfer, seam_carve

These use PyTorch and vendored implementations. Mark with `@pytest.mark.slow`.

**Files:**
- Create: `sparagmos/vendor/deepdream.py` (vendored implementation)
- Create: `sparagmos/vendor/style_transfer.py` (vendored implementation)
- Create: `sparagmos/effects/deepdream.py` + test
- Create: `sparagmos/effects/style_transfer.py` + test
- Create: `sparagmos/effects/seam_carve.py` + test

**Key implementation notes:**

**deepdream**: Vendored single-file PyTorch implementation. Uses pretrained InceptionV3 from torchvision. Forward pass to target layer, compute gradient of layer activations w.r.t. input, add gradient to input (amplify detected features). Multi-octave: process at multiple scales. Params: `layers` (list of layer names), `iterations` (int), `octave_scale` (float), `jitter` (int), `learning_rate` (float).

**style_transfer**: Vendored Gatys algorithm. Extract content features from one layer and style features (Gram matrices) from multiple layers. Optimize input image to minimize content loss + style loss. Uses VGG19 from torchvision. Params: `style_weight` (float), `content_weight` (float), `iterations` (int), `style_image` (string — path or "self" to use the same image as both content and style, producing a weird recursive effect).

**seam_carve**: Pure Python with numpy. Compute energy map (gradient magnitude), find minimum-energy seam (dynamic programming), remove seams. Intentionally misconfigure: remove too many seams, protect wrong regions, extreme aspect ratios. Params: `scale_x` (float, target width ratio), `scale_y` (float, target height ratio, default 1.0), `protect_regions` (string — "vision" for Llama-targeted, "none" to protect nothing, "invert" to remove the most interesting seams first). Vision-aware.

- [ ] **Step 1-5 for each effect:** Follow TDD cycle. Use `@pytest.mark.slow` and small test images.

- [ ] **Step 6: Commit**

```bash
git add sparagmos/vendor/ sparagmos/effects/ tests/test_effects/
git commit -m "feat: neural effects — deepdream, style_transfer, seam_carve

DeepDream via vendored PyTorch InceptionV3 implementation with
multi-octave processing. Neural style transfer via vendored Gatys
algorithm with VGG19. Seam carving with intentional misconfiguration
for melting/bending effects, vision-aware region targeting."
```

---

## Task 15: Remaining Neural Effects — pix2pix, neural_doodle, inpaint

**Files:**
- Create: `sparagmos/vendor/pix2pix.py` (vendored inference code)
- Create: `sparagmos/vendor/neural_doodle.py` (vendored implementation)
- Create: `sparagmos/effects/pix2pix.py` + test
- Create: `sparagmos/effects/neural_doodle.py` + test
- Create: `sparagmos/effects/inpaint.py` + test

**Key implementation notes:**

**pix2pix**: Vendored CycleGAN inference code. Load pretrained generator (horse2zebra, monet2photo, etc — small models included or downloaded on first run). Pass input through generator. Weird domain-transfer artifacts are the point. Params: `model` (string — pretrained model name), `direction` (string — "AtoB" or "BtoA").

**neural_doodle**: Vendored semantic painting implementation. Generate random rough semantic masks (geometric shapes), use neural net to fill regions based on a style image. Params: `num_regions` (int), `style_source` (string — "self" uses the input image), `iterations` (int).

**inpaint**: Random or vision-targeted masking + regeneration. For diffusion-based inpainting, use a small model (SD-Turbo or LCM-LoRA) via the `diffusers` library (optional dep, skip if not installed). Fallback: PatchMatch-style inpainting via OpenCV `cv2.inpaint()`. Params: `mask_mode` (one of "random_rect", "random_circle", "vision"), `mask_size` (float 0-1, fraction of image), `method` (one of "diffusion", "patchmatch", "telea"). Vision-aware.

- [ ] **Step 1-5 for each effect:** Follow TDD cycle.

- [ ] **Step 6: Commit**

```bash
git add sparagmos/vendor/ sparagmos/effects/ tests/test_effects/
git commit -m "feat: remaining neural effects — pix2pix, neural_doodle, inpaint

pix2pix via vendored CycleGAN inference (horse2zebra, monet2photo).
Neural doodle with random semantic masks. Inpaint with diffusion
(SD-Turbo, optional) or OpenCV PatchMatch/Telea fallback. Vision-
aware masking for targeted regeneration."
```

---

## Task 16: Starter Recipes

**Files:**
- Create: 12 recipe YAML files in `recipes/`
- Create: `tests/test_recipes.py`

- [ ] **Step 1: Write recipe validation test**

```python
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
```

- [ ] **Step 2: Create recipe files**

Create all 12 recipes in `recipes/`. Each follows the schema from the spec. Here are the recipes with their effect chains:

**recipes/vhs-meltdown.yaml**: crt_vhs → channel_shift → jpeg_destroy
**recipes/deep-fossil.yaml**: deepdream → dither (thermal palette) → jpeg_destroy
**recipes/cga-nightmare.yaml**: dither (CGA) → pixel_sort → crt_vhs
**recipes/dionysian-rite.yaml**: deepdream → channel_shift → seam_carve (vision) → jpeg_destroy
**recipes/analog-burial.yaml**: format_roundtrip (potrace) → crt_vhs → byte_corrupt
**recipes/byte-liturgy.yaml**: byte_corrupt → channel_shift → jpeg_destroy
**recipes/thermal-ghost.yaml**: pca_decompose (bottom 5) → dither (thermal) → channel_shift
**recipes/turtle-oracle.yaml**: primitive (triangles, 50 shapes) → pixel_sort → dither (EGA)
**recipes/eigenface-requiem.yaml**: pca_decompose (top 3) → style_transfer (self) → jpeg_destroy
**recipes/spectral-autopsy.yaml**: spectral (shift) → sonify (reverb) → channel_shift
**recipes/cellular-decay.yaml**: cellular (game_of_life, 50 gens) → fractal_blend → dither
**recipes/ocr-feedback-loop.yaml**: imagemagick (swirl) → pixel_sort → byte_corrupt → jpeg_destroy

Each recipe has a `name`, `description`, `vision` (true/false), and `effects` list with params including ranges for variety.

- [ ] **Step 3: Run tests to verify they pass**

Run: `uv run pytest tests/test_recipes.py -v`
Expected: All tests PASS.

- [ ] **Step 4: Commit**

```bash
git add recipes/ tests/test_recipes.py
git commit -m "feat: 12 starter recipes covering all effect eras

vhs-meltdown, deep-fossil, cga-nightmare, dionysian-rite, analog-burial,
byte-liturgy, thermal-ghost, turtle-oracle, eigenface-requiem,
spectral-autopsy, cellular-decay, ocr-feedback-loop. Each tested
against effect schemas."
```

---

## Task 17: Documentation

**Files:**
- Create: `README.md`
- Create: `docs/recipes.md`
- Create: `docs/effects.md`

- [ ] **Step 1: Write README.md**

Include:
1. **Header** — Name, Greek, one-line description
2. **What it does** — 3-sentence overview
3. **Effects capability table** — full table from spec (effect, era, description, system deps)
4. **Quickstart** — install deps, `python -m sparagmos --input photo.jpg --output out.png`, `python -m sparagmos --dry-run`
5. **CLI reference** — all flags with descriptions
6. **Recipes** — link to docs/recipes.md, list of included recipes
7. **Architecture** — brief pipeline overview
8. **Development** — adding effects, writing recipes, running tests
9. **System dependencies** — brew/apt install commands

- [ ] **Step 2: Write docs/recipes.md**

Include:
1. **Creating recipes** — YAML schema, step-by-step guide
2. **Parameter types** — fixed, range, vision
3. **Per-effect parameter reference** — every effect, every param, type, range, default, description
4. **Example recipes with commentary** — 3-4 annotated recipes explaining design choices
5. **Tips** — effect ordering, combining eras, using vision

- [ ] **Step 3: Write docs/effects.md**

Include:
1. **Effect interface** — how effects work, the base class contract
2. **Adding a new effect** — step-by-step guide with code template
3. **Per-effect documentation** — grouped by era, each with description, params, examples, source/provenance for vendored code

- [ ] **Step 4: Commit**

```bash
git add README.md docs/
git commit -m "docs: README with effects table, recipe guide, effect reference

README has full effects capability table, quickstart, CLI reference.
docs/recipes.md has schema reference, per-effect params, annotated
examples, chaining tips. docs/effects.md has interface docs, how to
add new effects, per-effect documentation."
```

---

## Task 18: GitHub Actions Workflow

**Files:**
- Create: `.github/workflows/sparagmos.yml`
- Create: `.github/workflows/test.yml`

- [ ] **Step 1: Create daily bot workflow**

```yaml
name: Sparagmos

on:
  schedule:
    - cron: '0 12 * * *'
  workflow_dispatch:
    inputs:
      recipe:
        description: 'Recipe name (leave empty for random)'
        default: ''

jobs:
  sparagmos:
    runs-on: ubuntu-latest
    permissions:
      contents: write

    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - uses: actions/setup-go@v5
        with:
          go-version: '1.21'

      - name: Install system dependencies
        run: |
          sudo apt-get update
          sudo apt-get install -y imagemagick netpbm ffmpeg potrace

      - name: Install primitive
        run: go install github.com/fogleman/primitive@latest

      - name: Install Python dependencies
        run: pip install -r requirements.txt

      - name: Run sparagmos
        env:
          SLACK_BOT_TOKEN: ${{ secrets.SLACK_BOT_TOKEN }}
          HF_TOKEN: ${{ secrets.HF_TOKEN }}
        run: |
          if [ -n "${{ inputs.recipe }}" ]; then
            python -m sparagmos --recipe "${{ inputs.recipe }}"
          else
            python -m sparagmos
          fi

      - name: Commit state
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git add state.json
          if git diff --cached --quiet; then
            echo "No state changes."
          else
            git commit -m "chore: update state ($(date -u +%Y-%m-%d)) [skip ci]"
            git push
          fi
```

- [ ] **Step 2: Create test workflow**

```yaml
name: Tests

on:
  push:
    branches: [main]
  pull_request:

jobs:
  test:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - uses: actions/setup-go@v5
        with:
          go-version: '1.21'

      - name: Install system dependencies
        run: |
          sudo apt-get update
          sudo apt-get install -y imagemagick netpbm ffmpeg potrace

      - name: Install primitive
        run: go install github.com/fogleman/primitive@latest

      - name: Install Python dependencies
        run: pip install -r requirements.txt

      - name: Run tests
        run: pytest -v --tb=short

      - name: Validate recipes
        run: python -m sparagmos --validate
```

- [ ] **Step 3: Commit**

```bash
git add .github/
git commit -m "ci: daily bot workflow and test workflow

sparagmos.yml: daily at noon UTC, manual trigger with recipe input,
commits state changes. test.yml: runs on push/PR, installs all
system deps, runs pytest and recipe validation."
```

---

## Task 19: Vendor README and Final Integration Test

**Files:**
- Update: `sparagmos/vendor/README.md`
- Create: `tests/test_integration.py`

- [ ] **Step 1: Write integration test**

```python
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


@pytest.mark.slow
@pytest.mark.parametrize("recipe_file", list((_get_recipes_dir()).glob("*.yaml")) if _get_recipes_dir().is_dir() else [])
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
```

- [ ] **Step 2: Update vendor README with actual vendored packages**

Update `sparagmos/vendor/README.md` with actual provenance for each vendored dependency (fill in after vendoring in tasks 14-15).

- [ ] **Step 3: Run full test suite**

Run: `uv run pytest -v`
Expected: All tests PASS (slow tests may take a few minutes for neural effects).

- [ ] **Step 4: Commit**

```bash
git add tests/test_integration.py sparagmos/vendor/README.md
git commit -m "test: integration tests running all recipes end-to-end

Parametrized test runs every recipe YAML through the full pipeline
on a test image. Verifies valid output image, correct recipe name,
and expected number of steps."
```

---

## Summary

| Task | Description | Effect Count |
|------|-------------|-------------|
| 1 | Project scaffolding | — |
| 2 | Effect base classes + registry | — |
| 3 | Config + recipe loading | — |
| 4 | Pipeline engine | — |
| 5 | State management | — |
| 6 | Slack source scraping | — |
| 7 | Slack posting | — |
| 8 | Llama Vision integration | — |
| 9 | CLI | — |
| 10 | channel_shift, jpeg_destroy, pixel_sort | 3 |
| 11 | byte_corrupt, dither, crt_vhs, cellular, pca_decompose, fractal_blend | 6 |
| 12 | imagemagick, netpbm, format_roundtrip, primitive | 4 |
| 13 | sonify, spectral, datamosh | 3 |
| 14 | deepdream, style_transfer, seam_carve | 3 |
| 15 | pix2pix, neural_doodle, inpaint | 3 |
| 16 | 12 starter recipes | — |
| 17 | Documentation (README, recipes.md, effects.md) | — |
| 18 | GitHub Actions workflows | — |
| 19 | Integration tests + vendor finalization | — |
