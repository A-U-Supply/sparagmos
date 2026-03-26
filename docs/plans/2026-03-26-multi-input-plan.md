# Multi-Input Compositing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade sparagmos from single-image destruction to multi-input compositing — named-image registers, four compositing effects, 12 new recipes, full docs and tests.

**Architecture:** Pipeline maintains `dict[str, Image]` instead of single image. Each recipe step specifies which named image(s) it reads/writes. New `ComposeEffect` base class for multi-image operations. Existing single-image effects unchanged.

**Tech Stack:** Python 3.11, Pillow, NumPy, SciPy (Voronoi), OpenCV (edge detection), pytest

**Spec:** `docs/plans/2026-03-26-multi-input-design.md`

---

## File Map

**Create:**
- `sparagmos/effects/blend.py` — pixel-level blending ComposeEffect
- `sparagmos/effects/mask_composite.py` — mask-based image selection ComposeEffect
- `sparagmos/effects/collage.py` — spatial arrangement ComposeEffect
- `sparagmos/effects/fragment.py` — cut-and-reassemble ComposeEffect
- `tests/test_effects/test_blend.py`
- `tests/test_effects/test_mask_composite.py`
- `tests/test_effects/test_collage.py`
- `tests/test_effects/test_fragment.py`
- 12 new recipe YAML files in `recipes/`

**Modify:**
- `sparagmos/config.py` — RecipeStep gets `image`/`images`/`into`; Recipe gets `inputs`; loader accepts `steps:`
- `sparagmos/effects/__init__.py` — add `ComposeEffect` base class
- `sparagmos/pipeline.py` — named-image register execution model
- `sparagmos/state.py` — `source_file_ids` (plural), backward compat
- `sparagmos/slack_source.py` — `pick_random_images()` for N images
- `sparagmos/slack_post.py` — multi-source provenance formatting
- `sparagmos/cli.py` — `--input` accepts multiple files, recipe filtering
- `tests/conftest.py` — add multi-image fixtures
- `tests/test_config.py` — new schema fields
- `tests/test_pipeline.py` — multi-image pipeline routing
- `tests/test_state.py` — multi-source entries
- `tests/test_slack.py` — multi-image picking, multi-source provenance
- `tests/test_recipes.py` — validate new recipes
- `tests/test_integration.py` — end-to-end multi-input pipeline
- `README.md` — rewrite for multi-input
- `docs/effects.md` — compositing effects section
- `docs/recipes.md` — new schema docs
- `recipes/README.md` — updated recipe guide

## Parallelization

Tasks 4–7 (compositing effects) are independent — run in parallel.
Tasks 8–10 (state, slack source, slack post) are independent — run in parallel.
All other tasks are sequential.

---

## Task 1: Recipe Schema Changes

**Files:**
- Modify: `sparagmos/config.py`
- Modify: `tests/test_config.py`

- [ ] **Step 1: Write failing tests for new schema fields**

Add to `tests/test_config.py`:

```python
def test_load_recipe_with_inputs(tmp_path):
    """Recipe with inputs field loads correctly."""
    content = textwrap.dedent("""\
        name: Multi Input
        description: Uses multiple images.
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


def test_load_recipe_inputs_defaults_to_one(recipe_yaml):
    """Recipe without inputs field defaults to 1."""
    recipe = load_recipe(recipe_yaml)
    assert recipe.inputs == 1


def test_load_recipe_steps_alias(tmp_path):
    """'steps:' key is accepted as alias for 'effects:'."""
    content = textwrap.dedent("""\
        name: Steps Alias
        description: Uses steps key.
        steps:
          - type: dummy
            params: {}
    """)
    path = tmp_path / "steps.yaml"
    path.write_text(content)
    recipe = load_recipe(path)
    assert len(recipe.effects) == 1


def test_load_recipe_compose_step(tmp_path):
    """Recipe step with images/into fields loads correctly."""
    content = textwrap.dedent("""\
        name: Compose Test
        description: Has compose step.
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


def test_load_recipe_image_defaults_none(recipe_yaml):
    """Steps without image/images/into fields have None."""
    recipe = load_recipe(recipe_yaml)
    step = recipe.effects[0]
    assert step.image is None
    assert step.images is None
    assert step.into is None


def test_validate_recipe_compose_step_missing_into(tmp_path):
    """Compose step without 'into' is an error."""
    content = textwrap.dedent("""\
        name: Bad Compose
        description: Missing into.
        inputs: 2
        steps:
          - type: dummy
            images: [a, b]
            params: {}
    """)
    path = tmp_path / "bad-compose.yaml"
    path.write_text(content)
    recipe = load_recipe(path)
    errors = validate_recipe(recipe)
    assert any("into" in e.lower() for e in errors)


def test_validate_recipe_image_name_not_in_inputs(tmp_path):
    """Referencing image name beyond inputs count is an error."""
    content = textwrap.dedent("""\
        name: Bad Name
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_config.py -v -k "inputs or steps_alias or compose or image_defaults or missing_into or image_name_not"`
Expected: FAIL — `inputs` attribute not on Recipe, `image` not on RecipeStep, `steps:` key not parsed

- [ ] **Step 3: Update RecipeStep and Recipe dataclasses**

In `sparagmos/config.py`, update the dataclasses:

```python
@dataclass
class RecipeStep:
    """A single effect step in a recipe pipeline."""

    type: str
    params: dict[str, Any] = field(default_factory=dict)
    image: str | None = None
    images: list[str] | None = None
    into: str | None = None


@dataclass
class Recipe:
    """A complete recipe loaded from YAML."""

    name: str
    description: str
    effects: list[RecipeStep]
    vision: bool = False
    inputs: int = 1
    source_path: Path | None = None
```

- [ ] **Step 4: Update load_recipe to parse new fields**

In `sparagmos/config.py`, update `load_recipe`:

```python
def load_recipe(path: Path) -> Recipe:
    """Load a recipe from a YAML file."""
    with open(path) as f:
        data = yaml.safe_load(f)

    # Accept "steps:" as alias for "effects:"
    steps_data = data.get("steps") or data.get("effects", [])

    effects = []
    for step_data in steps_data:
        effects.append(
            RecipeStep(
                type=step_data["type"],
                params=step_data.get("params", {}),
                image=step_data.get("image"),
                images=step_data.get("images"),
                into=step_data.get("into"),
            )
        )

    return Recipe(
        name=data["name"],
        description=data.get("description", ""),
        effects=effects,
        vision=data.get("vision", False),
        inputs=data.get("inputs", 1),
        source_path=path,
    )
```

- [ ] **Step 5: Update validate_recipe for new fields**

Add these validation checks to the end of `validate_recipe` in `sparagmos/config.py`:

```python
    # Valid image names for this recipe's input count
    if recipe.inputs == 1:
        valid_names = {"canvas"}
    else:
        valid_names = set(chr(ord("a") + i) for i in range(recipe.inputs))
    valid_names.add("canvas")  # always valid as a target

    for i, step in enumerate(recipe.effects):
        step_label = f"effects[{i}] ({step.type})"

        # Validate image name references
        if step.image and step.image not in valid_names:
            errors.append(
                f"{step_label}: image {step.image!r} not valid for "
                f"inputs={recipe.inputs}. Valid: {sorted(valid_names)}"
            )

        if step.images:
            for img_name in step.images:
                if img_name not in valid_names:
                    errors.append(
                        f"{step_label}: images references {img_name!r} not valid for "
                        f"inputs={recipe.inputs}. Valid: {sorted(valid_names)}"
                    )
            if not step.into:
                errors.append(
                    f"{step_label}: compositing step (has 'images') must specify 'into'"
                )
```

Note: this block goes *inside* the existing loop, after the vision check. The `valid_names` calculation goes *before* the loop.

- [ ] **Step 6: Run tests to verify they pass**

Run: `pytest tests/test_config.py -v`
Expected: All tests PASS

- [ ] **Step 7: Commit**

```bash
git add sparagmos/config.py tests/test_config.py
git commit -m "feat: add multi-input recipe schema fields

Add inputs, image, images, and into fields to recipe schema.
Accept 'steps:' as alias for 'effects:' key in YAML.
Validate image name references against inputs count.
Backward compatible — existing recipes work unchanged."
```

---

## Task 2: ComposeEffect Base Class

**Files:**
- Modify: `sparagmos/effects/__init__.py`
- Modify: `tests/test_effects/conftest.py`
- Modify: `tests/test_pipeline.py`

- [ ] **Step 1: Write failing test for ComposeEffect**

Add to `tests/test_pipeline.py`:

```python
from sparagmos.effects import ComposeEffect

class MergeEffect(ComposeEffect):
    """Test compose effect that averages images."""

    name = "merge_test"
    description = "Averages multiple images"
    requires: list[str] = []

    def compose(self, images, params, context):
        import numpy as np
        arrays = [np.array(img, dtype=np.float32) for img in images]
        # Resize all to first image's size
        target_size = images[0].size
        resized = []
        for img in images:
            resized.append(np.array(img.resize(target_size), dtype=np.float32))
        avg = np.mean(resized, axis=0).astype(np.uint8)
        return EffectResult(image=Image.fromarray(avg), metadata={"count": len(images)})

    def validate_params(self, params):
        return params


def test_compose_effect_has_compose_method():
    effect = MergeEffect()
    assert hasattr(effect, "compose")
    assert callable(effect.compose)


def test_compose_effect_apply_fallback(test_image_rgb):
    """apply() falls back to compose() with single image."""
    effect = MergeEffect()
    ctx = EffectContext(vision=None, temp_dir=Path("/tmp"), seed=42, source_metadata={})
    result = effect.apply(test_image_rgb, {}, ctx)
    assert isinstance(result.image, Image.Image)
    assert result.metadata["count"] == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_pipeline.py -v -k "compose_effect"`
Expected: FAIL — `ComposeEffect` not importable

- [ ] **Step 3: Add ComposeEffect to effects/__init__.py**

Add after the `SubprocessEffect` class in `sparagmos/effects/__init__.py`:

```python
class ComposeEffect(Effect):
    """Base class for effects that combine multiple images.

    Compose effects take a list of images and produce one output.
    Used for collaging, blending, masking, and fragmenting.
    """

    @abstractmethod
    def compose(
        self, images: list[Image.Image], params: dict, context: EffectContext
    ) -> EffectResult:
        """Combine multiple images into one.

        Args:
            images: List of PIL Images to combine.
            params: Resolved recipe parameters.
            context: Shared pipeline context.

        Returns:
            EffectResult with combined image and metadata.
        """

    def apply(
        self, image: Image.Image, params: dict, context: EffectContext
    ) -> EffectResult:
        """Single-image fallback — delegates to compose with one image."""
        return self.compose([image], params, context)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_pipeline.py -v -k "compose_effect"`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add sparagmos/effects/__init__.py tests/test_pipeline.py
git commit -m "feat: add ComposeEffect base class for multi-image effects

Abstract base class that extends Effect with a compose() method
taking a list of images. apply() falls back to compose([image])
for single-image compatibility."
```

---

## Task 3: Pipeline Engine Multi-Image Support

**Files:**
- Modify: `sparagmos/pipeline.py`
- Modify: `tests/test_pipeline.py`

- [ ] **Step 1: Write failing tests for multi-image pipeline**

Add `MergeEffect` registration and new tests to `tests/test_pipeline.py`. The `MergeEffect` class from Task 2 is already in the file. Update the `register_test_effects` fixture:

```python
@pytest.fixture(autouse=True)
def register_test_effects():
    register_effect(InvertEffect())
    register_effect(ScaleEffect())
    register_effect(MergeEffect())
```

Add these tests:

```python
def test_run_pipeline_multi_image(test_image_rgb, tmp_path):
    """Pipeline with multiple named images routes correctly."""
    recipe = Recipe(
        name="multi",
        description="test",
        inputs=2,
        effects=[
            RecipeStep(type="invert_test", image="a", params={}),
            RecipeStep(type="scale_test", image="b", params={"factor": 0.5}),
            RecipeStep(type="merge_test", images=["a", "b"], into="canvas", params={}),
        ],
    )
    # Create a second test image
    img_b = Image.new("RGB", (64, 64), color=(200, 100, 50))

    result = run_pipeline(
        images={"a": test_image_rgb, "b": img_b},
        recipe=recipe,
        seed=42,
        temp_dir=tmp_path,
    )
    assert isinstance(result, PipelineResult)
    assert isinstance(result.image, Image.Image)
    assert len(result.steps) == 3
    assert result.steps[0]["effect"] == "invert_test"
    assert result.steps[1]["effect"] == "scale_test"
    assert result.steps[2]["effect"] == "merge_test"
    assert result.steps[2]["metadata"]["count"] == 2


def test_run_pipeline_single_image_backward_compat(test_image_rgb, tmp_path):
    """Old-style single image call still works."""
    recipe = Recipe(
        name="compat",
        description="test",
        effects=[RecipeStep(type="invert_test", params={})],
    )
    # Old signature: positional image
    result = run_pipeline(test_image_rgb, recipe, seed=42, temp_dir=tmp_path)
    assert isinstance(result.image, Image.Image)
    assert len(result.steps) == 1


def test_run_pipeline_image_default_canvas(test_image_rgb, tmp_path):
    """Steps without image= default to 'canvas'."""
    recipe = Recipe(
        name="default",
        description="test",
        effects=[
            RecipeStep(type="invert_test", params={}),  # no image= → canvas
            RecipeStep(type="scale_test", params={"factor": 0.5}),  # no image= → canvas
        ],
    )
    result = run_pipeline(test_image_rgb, recipe, seed=42, temp_dir=tmp_path)
    assert result.image.width == 32  # scale applied to canvas


def test_run_pipeline_step_metadata_includes_image_names(test_image_rgb, tmp_path):
    """Step metadata records which images were used."""
    recipe = Recipe(
        name="meta",
        description="test",
        inputs=2,
        effects=[
            RecipeStep(type="invert_test", image="a", params={}),
            RecipeStep(type="merge_test", images=["a", "b"], into="canvas", params={}),
        ],
    )
    img_b = Image.new("RGB", (64, 64), color=(200, 100, 50))
    result = run_pipeline(
        images={"a": test_image_rgb, "b": img_b},
        recipe=recipe,
        seed=42,
        temp_dir=tmp_path,
    )
    assert result.steps[0].get("image") == "a"
    assert result.steps[1].get("images") == ["a", "b"]
    assert result.steps[1].get("into") == "canvas"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_pipeline.py -v -k "multi_image or backward_compat or image_default or image_names"`
Expected: FAIL — `run_pipeline` doesn't accept `images=` kwarg

- [ ] **Step 3: Rewrite pipeline.py for named-image registers**

Replace `sparagmos/pipeline.py` with:

```python
"""Effect chaining pipeline engine."""

from __future__ import annotations

import logging
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from PIL import Image

from sparagmos.config import Recipe, RecipeStep, resolve_params
from sparagmos.effects import ComposeEffect, EffectContext, get_effect

logger = logging.getLogger(__name__)

IMAGE_NAMES = ["a", "b", "c", "d", "e"]


@dataclass
class PipelineResult:
    """Result of running a complete recipe pipeline."""

    image: Image.Image
    recipe_name: str
    steps: list[dict[str, Any]] = field(default_factory=list)


def run_pipeline(
    image: Image.Image | None = None,
    recipe: Recipe | None = None,
    seed: int = 0,
    temp_dir: Path | None = None,
    vision: dict[str, Any] | None = None,
    source_metadata: dict[str, Any] | None = None,
    *,
    images: dict[str, Image.Image] | None = None,
) -> PipelineResult:
    """Run a recipe's effect chain on one or more images.

    Supports two calling conventions:
    - Single image: run_pipeline(image, recipe, seed, ...)
    - Multi image:  run_pipeline(images={...}, recipe=recipe, seed=seed, ...)

    The pipeline maintains a dict of named images. Each step specifies
    which image(s) it operates on. Output is always images["canvas"].

    Args:
        image: Single input PIL Image (backward compat). Loaded as "canvas".
        recipe: Recipe defining the effect chain.
        seed: RNG seed for deterministic param resolution.
        temp_dir: Temp directory for subprocess effects. Created if None.
        vision: Llama Vision analysis results (if recipe uses vision).
        source_metadata: Source image metadata for context.
        images: Dict of named images for multi-input recipes.

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

    # Build named image dict
    if images is not None:
        img_dict = {k: v.convert("RGB") for k, v in images.items()}
    elif image is not None:
        img_dict = {"canvas": image.convert("RGB")}
    else:
        raise ValueError("Must provide either image or images")

    steps = []

    try:
        for i, step in enumerate(recipe.effects):
            effect = get_effect(step.type)

            # Resolve parameter ranges with a step-specific seed
            step_seed = seed + i
            resolved = resolve_params(step.params, seed=step_seed)

            if step.images:
                # Compositing step: multiple inputs → one output
                source_imgs = [img_dict[name] for name in step.images]
                logger.info(
                    "Step %d/%d: composing %s via %s → %s",
                    i + 1, len(recipe.effects),
                    step.images, effect.name, step.into,
                )
                if isinstance(effect, ComposeEffect):
                    result = effect.compose(source_imgs, resolved, context)
                else:
                    result = effect.apply(source_imgs[0], resolved, context)
                img_dict[step.into] = result.image.convert("RGB")

                steps.append({
                    "effect": effect.name,
                    "description": effect.description,
                    "resolved_params": resolved,
                    "metadata": result.metadata,
                    "images": step.images,
                    "into": step.into,
                })
            else:
                # Single-image step
                target = step.image or "canvas"
                logger.info(
                    "Step %d/%d: applying %s to %s",
                    i + 1, len(recipe.effects),
                    effect.name, target,
                )
                result = effect.apply(img_dict[target], resolved, context)
                img_dict[target] = result.image.convert("RGB")

                steps.append({
                    "effect": effect.name,
                    "description": effect.description,
                    "resolved_params": resolved,
                    "metadata": result.metadata,
                    "image": target,
                })

            logger.info("Step %d complete: %s", i + 1, result.metadata)
    finally:
        if cleanup_temp:
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)

    if "canvas" not in img_dict:
        raise ValueError(
            "Pipeline did not produce a 'canvas' image. "
            "Multi-input recipes must include a compositing step with into: canvas"
        )

    return PipelineResult(
        image=img_dict["canvas"],
        recipe_name=recipe.name,
        steps=steps,
    )
```

- [ ] **Step 4: Run all pipeline tests to verify they pass**

Run: `pytest tests/test_pipeline.py -v`
Expected: All tests PASS (including old tests — backward compat)

- [ ] **Step 5: Commit**

```bash
git add sparagmos/pipeline.py tests/test_pipeline.py
git commit -m "feat: pipeline engine supports named-image registers

Replace single current_image with dict[str, Image]. Each step
specifies which image(s) it reads/writes. Compositing steps call
effect.compose() with multiple images. Single-image steps default
to 'canvas'. Output is always images['canvas'].

Backward compatible — old single-image calling convention works."
```

---

## Task 4: blend Compositing Effect

**Can run in parallel with Tasks 5, 6, 7.**

**Files:**
- Create: `sparagmos/effects/blend.py`
- Create: `tests/test_effects/test_blend.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_effects/test_blend.py`:

```python
"""Tests for the blend compositing effect."""

import numpy as np
import pytest
from PIL import Image

from sparagmos.effects import EffectContext, EffectResult, register_effect
from sparagmos.effects.blend import BlendEffect


@pytest.fixture(autouse=True)
def register_blend():
    register_effect(BlendEffect())


@pytest.fixture
def effect_context(tmp_path):
    return EffectContext(vision=None, temp_dir=tmp_path, seed=42, source_metadata={})


@pytest.fixture
def white_image():
    return Image.new("RGB", (64, 64), color=(255, 255, 255))


@pytest.fixture
def black_image():
    return Image.new("RGB", (64, 64), color=(0, 0, 0))


@pytest.fixture
def red_image():
    return Image.new("RGB", (64, 64), color=(255, 0, 0))


@pytest.fixture
def blue_image():
    return Image.new("RGB", (64, 64), color=(0, 0, 255))


def test_blend_opacity_50(white_image, black_image, effect_context):
    effect = BlendEffect()
    result = effect.compose(
        [white_image, black_image],
        {"mode": "opacity", "strength": 0.5},
        effect_context,
    )
    px = result.image.getpixel((32, 32))
    assert 120 <= px[0] <= 135  # ~127


def test_blend_opacity_zero_returns_first(white_image, black_image, effect_context):
    effect = BlendEffect()
    result = effect.compose(
        [white_image, black_image],
        {"mode": "opacity", "strength": 0.0},
        effect_context,
    )
    px = result.image.getpixel((32, 32))
    assert px == (255, 255, 255)


def test_blend_multiply(white_image, red_image, effect_context):
    effect = BlendEffect()
    result = effect.compose(
        [white_image, red_image],
        {"mode": "multiply", "strength": 1.0},
        effect_context,
    )
    px = result.image.getpixel((32, 32))
    assert px[0] == 255  # white * red = red
    assert px[1] == 0
    assert px[2] == 0


def test_blend_screen(black_image, red_image, effect_context):
    effect = BlendEffect()
    result = effect.compose(
        [black_image, red_image],
        {"mode": "screen", "strength": 1.0},
        effect_context,
    )
    px = result.image.getpixel((32, 32))
    assert px[0] == 255  # screen(0, 255) = 255


def test_blend_difference(red_image, red_image, effect_context):
    effect = BlendEffect()
    result = effect.compose(
        [red_image, red_image],
        {"mode": "difference", "strength": 1.0},
        effect_context,
    )
    px = result.image.getpixel((32, 32))
    assert px == (0, 0, 0)  # same image = zero difference


def test_blend_mismatched_sizes(effect_context):
    small = Image.new("RGB", (32, 32), color=(100, 100, 100))
    large = Image.new("RGB", (64, 64), color=(200, 200, 200))
    effect = BlendEffect()
    result = effect.compose(
        [large, small],
        {"mode": "opacity", "strength": 0.5},
        effect_context,
    )
    # Output should match first image's size
    assert result.image.size == (64, 64)


def test_blend_with_offset(white_image, black_image, effect_context):
    effect = BlendEffect()
    result = effect.compose(
        [white_image, black_image],
        {"mode": "opacity", "strength": 1.0, "offset_x": 0.5, "offset_y": 0.0},
        effect_context,
    )
    # Left half should be white (black is offset right), right half black
    left_px = result.image.getpixel((10, 32))
    right_px = result.image.getpixel((55, 32))
    assert left_px[0] == 255  # white (no overlap)
    assert right_px[0] == 0  # black (offset region)


def test_blend_validate_params():
    effect = BlendEffect()
    params = effect.validate_params({"mode": "screen", "strength": 0.5})
    assert params["mode"] == "screen"


def test_blend_validate_bad_mode():
    effect = BlendEffect()
    with pytest.raises(Exception):
        effect.validate_params({"mode": "nonexistent"})


def test_blend_overlay(effect_context):
    mid = Image.new("RGB", (64, 64), color=(128, 128, 128))
    bright = Image.new("RGB", (64, 64), color=(200, 200, 200))
    effect = BlendEffect()
    result = effect.compose(
        [mid, bright],
        {"mode": "overlay", "strength": 1.0},
        effect_context,
    )
    assert isinstance(result.image, Image.Image)
    assert result.image.size == (64, 64)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_effects/test_blend.py -v`
Expected: FAIL — cannot import `BlendEffect`

- [ ] **Step 3: Implement blend effect**

Create `sparagmos/effects/blend.py`:

```python
"""Pixel-level blending of two images."""

from __future__ import annotations

import numpy as np
from PIL import Image

from sparagmos.effects import (
    ComposeEffect,
    ConfigError,
    EffectContext,
    EffectResult,
    register_effect,
)

BLEND_MODES = {"opacity", "multiply", "screen", "overlay", "difference", "add", "subtract"}


class BlendEffect(ComposeEffect):
    """Combine two images through photographic blend modes."""

    name = "blend"
    description = "Pixel-level blending of two images"
    requires: list[str] = []

    def compose(
        self, images: list[Image.Image], params: dict, context: EffectContext
    ) -> EffectResult:
        mode = params.get("mode", "opacity")
        strength = params.get("strength", 0.5)
        offset_x = params.get("offset_x", 0.0)
        offset_y = params.get("offset_y", 0.0)

        base = images[0].convert("RGB")
        overlay_img = images[1].convert("RGB") if len(images) > 1 else base.copy()

        # Resize overlay to match base
        overlay_img = overlay_img.resize(base.size, Image.Resampling.LANCZOS)

        # Apply offset: shift overlay, fill exposed area with base
        if offset_x != 0.0 or offset_y != 0.0:
            dx = int(offset_x * base.width)
            dy = int(offset_y * base.height)
            shifted = Image.new("RGB", base.size, (0, 0, 0))
            shifted.paste(overlay_img, (dx, dy))
            # Create mask for shifted region
            mask = Image.new("L", base.size, 0)
            mask.paste(
                Image.new("L", overlay_img.size, 255),
                (dx, dy),
            )
            # Where mask is 0 (no overlay), use base
            overlay_img = Image.composite(shifted, base, mask)

        base_arr = np.array(base, dtype=np.float32)
        over_arr = np.array(overlay_img, dtype=np.float32)

        blended = _blend(base_arr, over_arr, mode)

        # Apply strength: lerp between base and blended
        result_arr = base_arr + strength * (blended - base_arr)
        result_arr = np.clip(result_arr, 0, 255).astype(np.uint8)

        return EffectResult(
            image=Image.fromarray(result_arr),
            metadata={"mode": mode, "strength": strength},
        )

    def validate_params(self, params: dict) -> dict:
        mode = params.get("mode", "opacity")
        if mode not in BLEND_MODES:
            raise ConfigError(
                f"Unknown blend mode {mode!r}. Available: {sorted(BLEND_MODES)}",
                effect_name=self.name,
                param_name="mode",
            )
        strength = params.get("strength", 0.5)
        if not (0.0 <= strength <= 1.0):
            params["strength"] = max(0.0, min(1.0, strength))
        return params


def _blend(base: np.ndarray, over: np.ndarray, mode: str) -> np.ndarray:
    """Apply blend mode to two float32 arrays (0-255 range)."""
    if mode == "opacity":
        return over
    elif mode == "multiply":
        return (base * over) / 255.0
    elif mode == "screen":
        return 255.0 - ((255.0 - base) * (255.0 - over)) / 255.0
    elif mode == "overlay":
        low = (2.0 * base * over) / 255.0
        high = 255.0 - (2.0 * (255.0 - base) * (255.0 - over)) / 255.0
        return np.where(base < 128, low, high)
    elif mode == "difference":
        return np.abs(base - over)
    elif mode == "add":
        return np.minimum(base + over, 255.0)
    elif mode == "subtract":
        return np.maximum(base - over, 0.0)
    else:
        return over


register_effect(BlendEffect())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_effects/test_blend.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add sparagmos/effects/blend.py tests/test_effects/test_blend.py
git commit -m "feat: add blend compositing effect

Seven blend modes: opacity, multiply, screen, overlay, difference,
add, subtract. Supports strength parameter and x/y offset.
Handles mismatched image sizes via resize."
```

---

## Task 5: mask_composite Compositing Effect

**Can run in parallel with Tasks 4, 6, 7.**

**Files:**
- Create: `sparagmos/effects/mask_composite.py`
- Create: `tests/test_effects/test_mask_composite.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_effects/test_mask_composite.py`:

```python
"""Tests for the mask_composite compositing effect."""

import numpy as np
import pytest
from PIL import Image

from sparagmos.effects import EffectContext, register_effect
from sparagmos.effects.mask_composite import MaskCompositeEffect


@pytest.fixture(autouse=True)
def register_mask():
    register_effect(MaskCompositeEffect())


@pytest.fixture
def effect_context(tmp_path):
    return EffectContext(vision=None, temp_dir=tmp_path, seed=42, source_metadata={})


@pytest.fixture
def white_image():
    return Image.new("RGB", (64, 64), color=(255, 255, 255))


@pytest.fixture
def black_image():
    return Image.new("RGB", (64, 64), color=(0, 0, 0))


@pytest.fixture
def gradient_image():
    """Image with horizontal gradient: black on left, white on right."""
    img = Image.new("RGB", (64, 64))
    pixels = img.load()
    for x in range(64):
        for y in range(64):
            v = int(x * 255 / 63)
            pixels[x, y] = (v, v, v)
    return img


def test_mask_luminance_threshold(gradient_image, white_image, effect_context):
    """Luminance mask: dark areas of first image → show second image."""
    effect = MaskCompositeEffect()
    result = effect.compose(
        [gradient_image, white_image],
        {"mask_source": "luminance", "threshold": 128, "feather": 0, "invert": False},
        effect_context,
    )
    # Left side (dark) should show gradient, right side (bright) should show gradient
    # Actually: luminance > threshold → first image, else → second image
    assert isinstance(result.image, Image.Image)
    assert result.image.size == (64, 64)


def test_mask_edges(effect_context):
    """Edge mask: edges of first image reveal second image."""
    # Create image with sharp edge
    img_with_edge = Image.new("RGB", (64, 64), color=(0, 0, 0))
    pixels = img_with_edge.load()
    for x in range(32, 64):
        for y in range(64):
            pixels[x, y] = (255, 255, 255)

    red = Image.new("RGB", (64, 64), color=(255, 0, 0))
    effect = MaskCompositeEffect()
    result = effect.compose(
        [img_with_edge, red],
        {"mask_source": "edges", "threshold": 50, "feather": 0},
        effect_context,
    )
    assert isinstance(result.image, Image.Image)


def test_mask_noise(white_image, black_image, effect_context):
    """Noise mask produces mix of both images."""
    effect = MaskCompositeEffect()
    result = effect.compose(
        [white_image, black_image],
        {"mask_source": "noise", "threshold": 128},
        effect_context,
    )
    arr = np.array(result.image)
    # Should have some white pixels and some black
    unique_vals = np.unique(arr)
    assert len(unique_vals) > 1


def test_mask_gradient(white_image, black_image, effect_context):
    """Gradient mask produces smooth transition."""
    effect = MaskCompositeEffect()
    result = effect.compose(
        [white_image, black_image],
        {"mask_source": "gradient", "feather": 0},
        effect_context,
    )
    assert isinstance(result.image, Image.Image)


def test_mask_invert(gradient_image, white_image, effect_context):
    """Invert flag flips which image shows through."""
    effect = MaskCompositeEffect()
    r1 = effect.compose(
        [gradient_image, white_image],
        {"mask_source": "luminance", "threshold": 128, "invert": False},
        effect_context,
    )
    r2 = effect.compose(
        [gradient_image, white_image],
        {"mask_source": "luminance", "threshold": 128, "invert": True},
        effect_context,
    )
    arr1 = np.array(r1.image)
    arr2 = np.array(r2.image)
    # Inverted result should be different
    assert not np.array_equal(arr1, arr2)


def test_mask_feather(gradient_image, white_image, effect_context):
    """Feather > 0 produces softer transitions than feather 0."""
    effect = MaskCompositeEffect()
    r_hard = effect.compose(
        [gradient_image, white_image],
        {"mask_source": "luminance", "threshold": 128, "feather": 0},
        effect_context,
    )
    r_soft = effect.compose(
        [gradient_image, white_image],
        {"mask_source": "luminance", "threshold": 128, "feather": 10},
        effect_context,
    )
    arr_hard = np.array(r_hard.image, dtype=np.float32)
    arr_soft = np.array(r_soft.image, dtype=np.float32)
    # Soft result should have more intermediate values
    assert not np.array_equal(arr_hard, arr_soft)


def test_mask_mismatched_sizes(effect_context):
    small = Image.new("RGB", (32, 32), color=(255, 255, 255))
    large = Image.new("RGB", (64, 64), color=(0, 0, 0))
    effect = MaskCompositeEffect()
    result = effect.compose(
        [large, small],
        {"mask_source": "noise"},
        effect_context,
    )
    assert result.image.size == (64, 64)


def test_mask_validate_bad_source():
    effect = MaskCompositeEffect()
    with pytest.raises(Exception):
        effect.validate_params({"mask_source": "nonexistent"})
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_effects/test_mask_composite.py -v`
Expected: FAIL — cannot import `MaskCompositeEffect`

- [ ] **Step 3: Implement mask_composite effect**

Create `sparagmos/effects/mask_composite.py`:

```python
"""Mask-based image compositing — use one image's features to select between two images."""

from __future__ import annotations

import random

import cv2
import numpy as np
from PIL import Image, ImageFilter

from sparagmos.effects import (
    ComposeEffect,
    ConfigError,
    EffectContext,
    EffectResult,
    register_effect,
)

MASK_SOURCES = {"luminance", "edges", "threshold", "noise", "gradient"}


class MaskCompositeEffect(ComposeEffect):
    """Use derived features from one image as a mask to select between two images."""

    name = "mask_composite"
    description = "Mask-based selection between two images"
    requires: list[str] = []

    def compose(
        self, images: list[Image.Image], params: dict, context: EffectContext
    ) -> EffectResult:
        mask_source = params.get("mask_source", "luminance")
        threshold = params.get("threshold", 128)
        feather = params.get("feather", 0)
        invert = params.get("invert", False)

        base = images[0].convert("RGB")
        reveal = images[1].convert("RGB") if len(images) > 1 else base.copy()
        reveal = reveal.resize(base.size, Image.Resampling.LANCZOS)

        # Generate mask from first image
        mask = _generate_mask(base, mask_source, threshold, context.seed)

        if invert:
            mask = 255 - mask

        if feather > 0:
            mask_img = Image.fromarray(mask)
            mask_img = mask_img.filter(ImageFilter.GaussianBlur(radius=feather))
            mask = np.array(mask_img)

        mask_pil = Image.fromarray(mask).convert("L")
        result = Image.composite(base, reveal, mask_pil)

        return EffectResult(
            image=result,
            metadata={"mask_source": mask_source, "threshold": threshold},
        )

    def validate_params(self, params: dict) -> dict:
        source = params.get("mask_source", "luminance")
        if source not in MASK_SOURCES:
            raise ConfigError(
                f"Unknown mask_source {source!r}. Available: {sorted(MASK_SOURCES)}",
                effect_name=self.name,
                param_name="mask_source",
            )
        return params


def _generate_mask(
    image: Image.Image, source: str, threshold: int, seed: int
) -> np.ndarray:
    """Generate a grayscale mask array from an image."""
    w, h = image.size

    if source == "luminance":
        gray = np.array(image.convert("L"))
        return np.where(gray >= threshold, 255, 0).astype(np.uint8)

    elif source == "edges":
        gray = np.array(image.convert("L"))
        edges = cv2.Canny(gray, threshold // 2, threshold)
        # Dilate edges to make them visible
        kernel = np.ones((3, 3), np.uint8)
        edges = cv2.dilate(edges, kernel, iterations=2)
        return edges

    elif source == "threshold":
        gray = np.array(image.convert("L"))
        return np.where(gray >= threshold, 255, 0).astype(np.uint8)

    elif source == "noise":
        rng = np.random.RandomState(seed)
        noise = rng.randint(0, 256, (h, w), dtype=np.uint8)
        return np.where(noise >= threshold, 255, 0).astype(np.uint8)

    elif source == "gradient":
        gradient = np.tile(
            np.linspace(0, 255, w, dtype=np.uint8), (h, 1)
        )
        return gradient

    return np.full((h, w), 128, dtype=np.uint8)


register_effect(MaskCompositeEffect())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_effects/test_mask_composite.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add sparagmos/effects/mask_composite.py tests/test_effects/test_mask_composite.py
git commit -m "feat: add mask_composite compositing effect

Five mask sources: luminance, edges, threshold, noise, gradient.
Uses first image's features as mask to select between two images.
Supports feather (Gaussian blur on mask) and invert."
```

---

## Task 6: collage Compositing Effect

**Can run in parallel with Tasks 4, 5, 7.**

**Files:**
- Create: `sparagmos/effects/collage.py`
- Create: `tests/test_effects/test_collage.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_effects/test_collage.py`:

```python
"""Tests for the collage compositing effect."""

import numpy as np
import pytest
from PIL import Image

from sparagmos.effects import EffectContext, register_effect
from sparagmos.effects.collage import CollageEffect


@pytest.fixture(autouse=True)
def register_collage():
    register_effect(CollageEffect())


@pytest.fixture
def effect_context(tmp_path):
    return EffectContext(vision=None, temp_dir=tmp_path, seed=42, source_metadata={})


@pytest.fixture
def colored_images():
    """Three distinctly colored 64x64 images."""
    return [
        Image.new("RGB", (64, 64), color=(255, 0, 0)),
        Image.new("RGB", (64, 64), color=(0, 255, 0)),
        Image.new("RGB", (64, 64), color=(0, 0, 255)),
    ]


def test_collage_grid(colored_images, effect_context):
    effect = CollageEffect()
    result = effect.compose(
        colored_images,
        {"layout": "grid"},
        effect_context,
    )
    assert isinstance(result.image, Image.Image)
    # Grid of 3 images should produce a rectangular output
    assert result.image.width > 0
    assert result.image.height > 0


def test_collage_scatter(colored_images, effect_context):
    effect = CollageEffect()
    result = effect.compose(
        colored_images,
        {"layout": "scatter", "rotation": 45, "scale_variance": 0.3},
        effect_context,
    )
    assert isinstance(result.image, Image.Image)


def test_collage_strips(colored_images, effect_context):
    effect = CollageEffect()
    result = effect.compose(
        colored_images,
        {"layout": "strips"},
        effect_context,
    )
    assert isinstance(result.image, Image.Image)
    # Strip layout should contain pixels from all three colors
    arr = np.array(result.image)
    has_red = np.any(arr[:, :, 0] > 200)
    has_green = np.any(arr[:, :, 1] > 200)
    has_blue = np.any(arr[:, :, 2] > 200)
    assert has_red and has_green and has_blue


def test_collage_mosaic(colored_images, effect_context):
    effect = CollageEffect()
    result = effect.compose(
        colored_images,
        {"layout": "mosaic"},
        effect_context,
    )
    assert isinstance(result.image, Image.Image)


def test_collage_single_image(effect_context):
    img = Image.new("RGB", (64, 64), color=(128, 128, 128))
    effect = CollageEffect()
    result = effect.compose([img], {"layout": "grid"}, effect_context)
    assert isinstance(result.image, Image.Image)


def test_collage_five_images(effect_context):
    imgs = [Image.new("RGB", (64, 64), color=(i * 50, 100, 200)) for i in range(5)]
    effect = CollageEffect()
    result = effect.compose(imgs, {"layout": "grid"}, effect_context)
    assert isinstance(result.image, Image.Image)


def test_collage_mismatched_sizes(effect_context):
    imgs = [
        Image.new("RGB", (32, 32), color=(255, 0, 0)),
        Image.new("RGB", (64, 64), color=(0, 255, 0)),
        Image.new("RGB", (100, 50), color=(0, 0, 255)),
    ]
    effect = CollageEffect()
    result = effect.compose(imgs, {"layout": "grid"}, effect_context)
    assert isinstance(result.image, Image.Image)


def test_collage_with_overlap(colored_images, effect_context):
    effect = CollageEffect()
    result = effect.compose(
        colored_images,
        {"layout": "grid", "overlap": 0.2},
        effect_context,
    )
    assert isinstance(result.image, Image.Image)


def test_collage_deterministic(colored_images, effect_context):
    effect = CollageEffect()
    r1 = effect.compose(colored_images, {"layout": "scatter"}, effect_context)
    r2 = effect.compose(colored_images, {"layout": "scatter"}, effect_context)
    assert np.array_equal(np.array(r1.image), np.array(r2.image))


def test_collage_validate_bad_layout():
    effect = CollageEffect()
    with pytest.raises(Exception):
        effect.validate_params({"layout": "nonexistent"})
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_effects/test_collage.py -v`
Expected: FAIL — cannot import `CollageEffect`

- [ ] **Step 3: Implement collage effect**

Create `sparagmos/effects/collage.py`:

```python
"""Spatial arrangement of multiple images into a collage."""

from __future__ import annotations

import math
import random

import numpy as np
from PIL import Image, ImageDraw

from sparagmos.effects import (
    ComposeEffect,
    ConfigError,
    EffectContext,
    EffectResult,
    register_effect,
)

LAYOUTS = {"grid", "scatter", "strips", "mosaic"}


class CollageEffect(ComposeEffect):
    """Arrange multiple images onto a shared canvas."""

    name = "collage"
    description = "Spatial arrangement of multiple images"
    requires: list[str] = []

    def compose(
        self, images: list[Image.Image], params: dict, context: EffectContext
    ) -> EffectResult:
        layout = params.get("layout", "grid")
        overlap = params.get("overlap", 0.0)
        rotation = params.get("rotation", 0)
        scale_variance = params.get("scale_variance", 0.0)
        canvas_size = params.get("canvas_size", "largest")

        rng = random.Random(context.seed)
        imgs = [img.convert("RGB") for img in images]

        if len(imgs) == 1:
            return EffectResult(image=imgs[0].copy(), metadata={"layout": layout})

        # Determine canvas dimensions
        if canvas_size == "smallest":
            w = min(img.width for img in imgs)
            h = min(img.height for img in imgs)
        elif canvas_size == "fixed_1024":
            w, h = 1024, 1024
        else:  # "largest"
            w = max(img.width for img in imgs)
            h = max(img.height for img in imgs)

        if layout == "grid":
            result = _grid(imgs, w, h, overlap, rng)
        elif layout == "scatter":
            result = _scatter(imgs, w, h, rotation, scale_variance, rng)
        elif layout == "strips":
            result = _strips(imgs, w, h, rng)
        elif layout == "mosaic":
            result = _mosaic(imgs, w, h, rng)
        else:
            result = _grid(imgs, w, h, overlap, rng)

        return EffectResult(
            image=result,
            metadata={"layout": layout, "count": len(imgs)},
        )

    def validate_params(self, params: dict) -> dict:
        layout = params.get("layout", "grid")
        if layout not in LAYOUTS:
            raise ConfigError(
                f"Unknown layout {layout!r}. Available: {sorted(LAYOUTS)}",
                effect_name=self.name,
                param_name="layout",
            )
        return params


def _grid(
    images: list[Image.Image], w: int, h: int, overlap: float, rng: random.Random
) -> Image.Image:
    """Tile images in a grid layout."""
    n = len(images)
    cols = math.ceil(math.sqrt(n))
    rows = math.ceil(n / cols)

    cell_w = w // cols
    cell_h = h // rows
    overlap_px_x = int(cell_w * overlap)
    overlap_px_y = int(cell_h * overlap)

    canvas = Image.new("RGB", (w, h), (0, 0, 0))
    shuffled = list(range(n))
    rng.shuffle(shuffled)

    for idx, img_idx in enumerate(shuffled):
        row, col = divmod(idx, cols)
        if img_idx >= len(images):
            continue
        piece = images[img_idx].resize(
            (cell_w + overlap_px_x, cell_h + overlap_px_y),
            Image.Resampling.LANCZOS,
        )
        x = col * cell_w - overlap_px_x // 2
        y = row * cell_h - overlap_px_y // 2
        canvas.paste(piece, (max(0, x), max(0, y)))

    return canvas


def _scatter(
    images: list[Image.Image],
    w: int,
    h: int,
    max_rotation: int,
    scale_variance: float,
    rng: random.Random,
) -> Image.Image:
    """Scatter images randomly on the canvas with rotation and scale."""
    canvas = Image.new("RGB", (w, h), (0, 0, 0))

    for img in images:
        scale = 1.0 + rng.uniform(-scale_variance, scale_variance)
        piece_w = int(img.width * scale)
        piece_h = int(img.height * scale)
        piece = img.resize((max(1, piece_w), max(1, piece_h)), Image.Resampling.LANCZOS)

        if max_rotation > 0:
            angle = rng.uniform(-max_rotation, max_rotation)
            piece = piece.rotate(angle, expand=True, fillcolor=(0, 0, 0))

        x = rng.randint(-piece.width // 4, w - piece.width * 3 // 4)
        y = rng.randint(-piece.height // 4, h - piece.height * 3 // 4)
        canvas.paste(piece, (x, y))

    return canvas


def _strips(
    images: list[Image.Image], w: int, h: int, rng: random.Random
) -> Image.Image:
    """Interleave vertical strips from each image."""
    canvas = Image.new("RGB", (w, h), (0, 0, 0))
    n = len(images)
    strip_w = w // n

    resized = [img.resize((w, h), Image.Resampling.LANCZOS) for img in images]
    order = list(range(n))
    rng.shuffle(order)

    for i, img_idx in enumerate(order):
        x_start = i * strip_w
        x_end = w if i == n - 1 else (i + 1) * strip_w
        strip = resized[img_idx].crop((x_start, 0, x_end, h))
        canvas.paste(strip, (x_start, 0))

    return canvas


def _mosaic(
    images: list[Image.Image], w: int, h: int, rng: random.Random
) -> Image.Image:
    """Fill canvas with random-sized rectangles from different sources."""
    canvas = Image.new("RGB", (w, h), (0, 0, 0))
    resized = [img.resize((w, h), Image.Resampling.LANCZOS) for img in images]

    # Generate random rectangles
    n_rects = max(len(images) * 4, 12)
    for _ in range(n_rects):
        rx = rng.randint(0, w - 1)
        ry = rng.randint(0, h - 1)
        rw = rng.randint(w // 8, w // 2)
        rh = rng.randint(h // 8, h // 2)

        src = rng.choice(resized)
        region = src.crop((
            max(0, rx),
            max(0, ry),
            min(w, rx + rw),
            min(h, ry + rh),
        ))
        canvas.paste(region, (max(0, rx), max(0, ry)))

    return canvas


register_effect(CollageEffect())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_effects/test_collage.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add sparagmos/effects/collage.py tests/test_effects/test_collage.py
git commit -m "feat: add collage compositing effect

Four layout modes: grid, scatter, strips, mosaic.
Supports overlap, rotation, scale variance, canvas sizing.
Handles mismatched image sizes and 1-5 inputs."
```

---

## Task 7: fragment Compositing Effect

**Can run in parallel with Tasks 4, 5, 6.**

**Files:**
- Create: `sparagmos/effects/fragment.py`
- Create: `tests/test_effects/test_fragment.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_effects/test_fragment.py`:

```python
"""Tests for the fragment compositing effect."""

import numpy as np
import pytest
from PIL import Image

from sparagmos.effects import EffectContext, register_effect
from sparagmos.effects.fragment import FragmentEffect


@pytest.fixture(autouse=True)
def register_fragment():
    register_effect(FragmentEffect())


@pytest.fixture
def effect_context(tmp_path):
    return EffectContext(vision=None, temp_dir=tmp_path, seed=42, source_metadata={})


@pytest.fixture
def colored_pair():
    return [
        Image.new("RGB", (64, 64), color=(255, 0, 0)),
        Image.new("RGB", (64, 64), color=(0, 0, 255)),
    ]


def test_fragment_grid(colored_pair, effect_context):
    effect = FragmentEffect()
    result = effect.compose(
        colored_pair,
        {"cut_mode": "grid", "pieces": 16, "mix_ratio": 1.0},
        effect_context,
    )
    assert isinstance(result.image, Image.Image)
    assert result.image.size == (64, 64)
    arr = np.array(result.image)
    # Should contain pixels from both images
    has_red = np.any(arr[:, :, 0] > 200)
    has_blue = np.any(arr[:, :, 2] > 200)
    assert has_red and has_blue


def test_fragment_voronoi(colored_pair, effect_context):
    effect = FragmentEffect()
    result = effect.compose(
        colored_pair,
        {"cut_mode": "voronoi", "pieces": 12},
        effect_context,
    )
    assert isinstance(result.image, Image.Image)
    assert result.image.size == (64, 64)


def test_fragment_strips(colored_pair, effect_context):
    effect = FragmentEffect()
    result = effect.compose(
        colored_pair,
        {"cut_mode": "strips", "pieces": 8},
        effect_context,
    )
    assert isinstance(result.image, Image.Image)


def test_fragment_shatter(colored_pair, effect_context):
    effect = FragmentEffect()
    result = effect.compose(
        colored_pair,
        {"cut_mode": "shatter", "pieces": 20},
        effect_context,
    )
    assert isinstance(result.image, Image.Image)


def test_fragment_mix_ratio_zero(colored_pair, effect_context):
    """mix_ratio 0 = all pieces from first image."""
    effect = FragmentEffect()
    result = effect.compose(
        colored_pair,
        {"cut_mode": "grid", "pieces": 16, "mix_ratio": 0.0},
        effect_context,
    )
    arr = np.array(result.image)
    # Should be mostly red (first image)
    assert np.mean(arr[:, :, 0]) > 200


def test_fragment_gap(colored_pair, effect_context):
    effect = FragmentEffect()
    result = effect.compose(
        colored_pair,
        {"cut_mode": "grid", "pieces": 16, "gap": 5},
        effect_context,
    )
    arr = np.array(result.image)
    # Gaps should be black
    has_black = np.any(np.all(arr == 0, axis=2))
    assert has_black


def test_fragment_three_images(effect_context):
    imgs = [
        Image.new("RGB", (64, 64), color=(255, 0, 0)),
        Image.new("RGB", (64, 64), color=(0, 255, 0)),
        Image.new("RGB", (64, 64), color=(0, 0, 255)),
    ]
    effect = FragmentEffect()
    result = effect.compose(
        imgs,
        {"cut_mode": "grid", "pieces": 9, "mix_ratio": 1.0},
        effect_context,
    )
    arr = np.array(result.image)
    has_red = np.any(arr[:, :, 0] > 200)
    has_green = np.any(arr[:, :, 1] > 200)
    has_blue = np.any(arr[:, :, 2] > 200)
    # With 3 images and full mix, should have all colors
    assert sum([has_red, has_green, has_blue]) >= 2


def test_fragment_mismatched_sizes(effect_context):
    imgs = [
        Image.new("RGB", (32, 32), color=(255, 0, 0)),
        Image.new("RGB", (64, 64), color=(0, 0, 255)),
    ]
    effect = FragmentEffect()
    result = effect.compose(
        imgs,
        {"cut_mode": "grid", "pieces": 4},
        effect_context,
    )
    assert isinstance(result.image, Image.Image)


def test_fragment_deterministic(colored_pair, effect_context):
    effect = FragmentEffect()
    r1 = effect.compose(colored_pair, {"cut_mode": "voronoi", "pieces": 12}, effect_context)
    r2 = effect.compose(colored_pair, {"cut_mode": "voronoi", "pieces": 12}, effect_context)
    assert np.array_equal(np.array(r1.image), np.array(r2.image))


def test_fragment_validate_bad_mode():
    effect = FragmentEffect()
    with pytest.raises(Exception):
        effect.validate_params({"cut_mode": "nonexistent"})
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_effects/test_fragment.py -v`
Expected: FAIL — cannot import `FragmentEffect`

- [ ] **Step 3: Implement fragment effect**

Create `sparagmos/effects/fragment.py`:

```python
"""Cut images into pieces and reassemble from mixed sources."""

from __future__ import annotations

import math
import random

import numpy as np
from PIL import Image, ImageDraw
from scipy.spatial import Voronoi

from sparagmos.effects import (
    ComposeEffect,
    ConfigError,
    EffectContext,
    EffectResult,
    register_effect,
)

CUT_MODES = {"grid", "voronoi", "strips", "shatter"}


class FragmentEffect(ComposeEffect):
    """Slice images into pieces and rebuild from mixed sources."""

    name = "fragment"
    description = "Cut and reassemble from mixed image sources"
    requires: list[str] = []

    def compose(
        self, images: list[Image.Image], params: dict, context: EffectContext
    ) -> EffectResult:
        cut_mode = params.get("cut_mode", "grid")
        pieces = params.get("pieces", 16)
        mix_ratio = params.get("mix_ratio", 0.5)
        gap = params.get("gap", 0)

        rng = random.Random(context.seed)

        # Resize all images to match first
        base_size = images[0].size
        imgs = [img.convert("RGB").resize(base_size, Image.Resampling.LANCZOS) for img in images]
        w, h = base_size

        if cut_mode == "grid":
            result = _grid_fragment(imgs, w, h, pieces, mix_ratio, gap, rng)
        elif cut_mode == "voronoi":
            result = _voronoi_fragment(imgs, w, h, pieces, mix_ratio, gap, rng)
        elif cut_mode == "strips":
            result = _strip_fragment(imgs, w, h, pieces, mix_ratio, rng)
        elif cut_mode == "shatter":
            result = _shatter_fragment(imgs, w, h, pieces, mix_ratio, gap, rng)
        else:
            result = _grid_fragment(imgs, w, h, pieces, mix_ratio, gap, rng)

        return EffectResult(
            image=result,
            metadata={"cut_mode": cut_mode, "pieces": pieces},
        )

    def validate_params(self, params: dict) -> dict:
        mode = params.get("cut_mode", "grid")
        if mode not in CUT_MODES:
            raise ConfigError(
                f"Unknown cut_mode {mode!r}. Available: {sorted(CUT_MODES)}",
                effect_name=self.name,
                param_name="cut_mode",
            )
        return params


def _pick_source(
    images: list[Image.Image],
    idx: int,
    mix_ratio: float,
    rng: random.Random,
) -> Image.Image:
    """Pick which source image to use for a fragment."""
    if mix_ratio <= 0.0:
        return images[0]
    if rng.random() < mix_ratio:
        return rng.choice(images)
    return images[idx % len(images)]


def _grid_fragment(
    images: list[Image.Image],
    w: int,
    h: int,
    pieces: int,
    mix_ratio: float,
    gap: int,
    rng: random.Random,
) -> Image.Image:
    cols = max(1, int(math.sqrt(pieces)))
    rows = max(1, math.ceil(pieces / cols))
    cell_w = w // cols
    cell_h = h // rows

    canvas = Image.new("RGB", (w, h), (0, 0, 0))
    idx = 0
    for row in range(rows):
        for col in range(cols):
            src = _pick_source(images, idx, mix_ratio, rng)
            x1 = col * cell_w + gap
            y1 = row * cell_h + gap
            x2 = (col + 1) * cell_w - gap
            y2 = (row + 1) * cell_h - gap
            if x2 <= x1 or y2 <= y1:
                continue
            region = src.crop((x1, y1, min(x2, w), min(y2, h)))
            canvas.paste(region, (x1, y1))
            idx += 1

    return canvas


def _voronoi_fragment(
    images: list[Image.Image],
    w: int,
    h: int,
    pieces: int,
    mix_ratio: float,
    gap: int,
    rng: random.Random,
) -> Image.Image:
    # Generate seed points
    np_rng = np.random.RandomState(rng.randint(0, 2**31))
    points = np_rng.rand(pieces, 2) * [w, h]

    # Add bounding points far outside to close all regions
    bounding = np.array([
        [-w, -h], [2 * w, -h], [-w, 2 * h], [2 * w, 2 * h],
    ])
    all_points = np.vstack([points, bounding])
    vor = Voronoi(all_points)

    # Convert images to arrays
    arrays = [np.array(img) for img in images]
    canvas = np.zeros((h, w, 3), dtype=np.uint8)

    # For each pixel, find nearest seed point, get source image
    yy, xx = np.mgrid[0:h, 0:w]
    coords = np.stack([xx.ravel(), yy.ravel()], axis=1).astype(np.float32)

    # Compute distances to each seed point
    dists = np.zeros((len(coords), pieces))
    for i in range(pieces):
        diff = coords - points[i]
        dists[:, i] = np.sum(diff * diff, axis=1)

    nearest = np.argmin(dists, axis=1)

    # Assign sources
    source_map = {}
    for i in range(pieces):
        source_map[i] = _pick_source(images, i, mix_ratio, rng)

    source_arrays = {i: np.array(source_map[i]) for i in range(pieces)}

    for i in range(pieces):
        mask = nearest == i
        if not np.any(mask):
            continue
        src_arr = source_arrays[i]
        pixel_indices = np.where(mask)[0]
        for pi in pixel_indices:
            x, y = int(coords[pi, 0]), int(coords[pi, 1])
            if 0 <= x < w and 0 <= y < h:
                canvas[y, x] = src_arr[y, x]

    # Apply gap by darkening edges between regions
    if gap > 0:
        from scipy.ndimage import uniform_filter
        nearest_2d = nearest.reshape(h, w).astype(np.float32)
        filtered = uniform_filter(nearest_2d, size=gap)
        edge_mask = np.abs(filtered - nearest_2d) > 0.01
        canvas[edge_mask] = 0

    return Image.fromarray(canvas)


def _strip_fragment(
    images: list[Image.Image],
    w: int,
    h: int,
    pieces: int,
    mix_ratio: float,
    rng: random.Random,
) -> Image.Image:
    canvas = Image.new("RGB", (w, h), (0, 0, 0))
    # Random strip widths
    widths = [rng.randint(1, 3) for _ in range(pieces)]
    total = sum(widths)
    widths = [max(1, int(ww * w / total)) for ww in widths]

    x = 0
    for i, strip_w in enumerate(widths):
        if x >= w:
            break
        src = _pick_source(images, i, mix_ratio, rng)
        actual_w = min(strip_w, w - x)
        strip = src.crop((x, 0, x + actual_w, h))
        canvas.paste(strip, (x, 0))
        x += actual_w

    return canvas


def _shatter_fragment(
    images: list[Image.Image],
    w: int,
    h: int,
    pieces: int,
    mix_ratio: float,
    gap: int,
    rng: random.Random,
) -> Image.Image:
    """Generate irregular polygons using random triangulation."""
    canvas = Image.new("RGB", (w, h), (0, 0, 0))
    arrays = [np.array(img) for img in images]

    # Generate random triangles via Delaunay
    np_rng = np.random.RandomState(rng.randint(0, 2**31))
    points = np_rng.rand(pieces, 2) * [w, h]

    # Add corners
    corners = np.array([[0, 0], [w, 0], [0, h], [w, h]], dtype=np.float64)
    all_points = np.vstack([points, corners])

    from scipy.spatial import Delaunay
    tri = Delaunay(all_points)

    for simplex in tri.simplices:
        verts = all_points[simplex]
        src_idx = rng.randint(0, len(images) - 1) if rng.random() < mix_ratio else 0

        # Draw filled triangle
        poly = [(int(v[0]), int(v[1])) for v in verts]
        mask = Image.new("L", (w, h), 0)
        draw = ImageDraw.Draw(mask)

        if gap > 0:
            # Shrink polygon slightly for gap effect
            cx = sum(v[0] for v in poly) / 3
            cy = sum(v[1] for v in poly) / 3
            poly = [
                (int(cx + (x - cx) * 0.9), int(cy + (y - cy) * 0.9))
                for x, y in poly
            ]

        draw.polygon(poly, fill=255)
        mask_arr = np.array(mask) > 0

        src_arr = arrays[src_idx]
        canvas_arr = np.array(canvas)
        canvas_arr[mask_arr] = src_arr[mask_arr]
        canvas = Image.fromarray(canvas_arr)

    return canvas


register_effect(FragmentEffect())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_effects/test_fragment.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add sparagmos/effects/fragment.py tests/test_effects/test_fragment.py
git commit -m "feat: add fragment compositing effect

Four cut modes: grid, voronoi, strips, shatter.
Voronoi uses scipy.spatial, shatter uses Delaunay triangulation.
Supports mix_ratio (source randomness) and gap between pieces."
```

---

## Task 8: State Tracking Multi-Source

**Can run in parallel with Tasks 9, 10.**

**Files:**
- Modify: `sparagmos/state.py`
- Modify: `tests/test_state.py`

- [ ] **Step 1: Write failing tests for multi-source state**

Add to `tests/test_state.py`:

```python
def test_add_multi_source_entry(empty_state):
    """Multi-source entries store lists of file IDs."""
    empty_state.add_multi(
        source_file_ids=["F1", "F2", "F3"],
        source_dates=["2026-01-01", "2026-01-02", "2026-01-03"],
        source_users=["U1", "U2", "U3"],
        recipe="multi-recipe",
        effects=["blend", "jpeg_destroy"],
        processed_date="2026-03-26",
        posted_ts="123.456",
    )
    assert len(empty_state.processed) == 1
    entry = empty_state.processed[0]
    assert entry.source_file_ids == ["F1", "F2", "F3"]
    assert entry.source_users == ["U1", "U2", "U3"]


def test_multi_source_save_reload(empty_state, state_file):
    """Multi-source entries survive save/reload cycle."""
    empty_state.add_multi(
        source_file_ids=["F1", "F2"],
        source_dates=["2026-01-01", "2026-01-02"],
        source_users=["U1", "U2"],
        recipe="test",
        effects=["blend"],
        processed_date="2026-03-26",
    )
    empty_state.save()

    reloaded = State(state_file)
    assert len(reloaded.processed) == 1
    assert reloaded.processed[0].source_file_ids == ["F1", "F2"]


def test_backward_compat_single_source(tmp_path):
    """Old state.json with source_file_id (singular) loads as list."""
    state_file = tmp_path / "state.json"
    old_data = {
        "processed": [
            {
                "source_file_id": "F_OLD",
                "source_date": "2025-12-01",
                "source_user": "U_OLD",
                "recipe": "old-recipe",
                "effects": ["pixel_sort"],
                "processed_date": "2026-01-01",
                "posted_ts": "999.0",
            }
        ]
    }
    state_file.write_text(json.dumps(old_data))
    state = State(state_file)
    assert len(state.processed) == 1
    assert state.processed[0].source_file_ids == ["F_OLD"]
    assert state.processed[0].source_users == ["U_OLD"]


def test_processed_combos(empty_state):
    """processed_combos returns frozenset-based keys."""
    empty_state.add_multi(
        source_file_ids=["F1", "F2"],
        source_dates=["2026-01-01", "2026-01-02"],
        source_users=["U1", "U2"],
        recipe="test",
        effects=[],
        processed_date="2026-03-26",
    )
    combos = empty_state.processed_combos()
    assert (frozenset(["F1", "F2"]), "test") in combos


def test_processed_combos_order_independent(empty_state):
    """(F1,F2) and (F2,F1) are the same combo."""
    empty_state.add_multi(
        source_file_ids=["F2", "F1"],
        source_dates=["d", "d"],
        source_users=["u", "u"],
        recipe="test",
        effects=[],
        processed_date="2026-03-26",
    )
    combos = empty_state.processed_combos()
    assert (frozenset(["F1", "F2"]), "test") in combos


def test_old_add_still_works(empty_state):
    """Old add() with singular fields still works for backward compat."""
    empty_state.add(
        source_file_id="F_COMPAT",
        source_date="2026-01-01",
        source_user="U_COMPAT",
        recipe="compat",
        effects=["dummy"],
        processed_date="2026-03-26",
    )
    assert len(empty_state.processed) == 1
    assert empty_state.processed[0].source_file_ids == ["F_COMPAT"]


def test_processed_pairs_backward_compat(empty_state):
    """Old processed_pairs() still works for single-source entries."""
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

Run: `pytest tests/test_state.py -v -k "multi_source or backward_compat or combos or old_add"`
Expected: FAIL — `add_multi` not found, `source_file_ids` not on ProcessedEntry

- [ ] **Step 3: Rewrite state.py for multi-source support**

Replace `sparagmos/state.py`:

```python
"""JSON state management for tracking processed images."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path


@dataclass
class ProcessedEntry:
    """Record of a processed image (supports multi-source)."""

    source_file_ids: list[str]
    source_dates: list[str]
    source_users: list[str]
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
                self.processed.append(_load_entry(entry))

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
        """Add a single-source entry (backward compat)."""
        self.add_multi(
            source_file_ids=[source_file_id],
            source_dates=[source_date],
            source_users=[source_user],
            recipe=recipe,
            effects=effects,
            processed_date=processed_date,
            posted_ts=posted_ts,
        )

    def add_multi(
        self,
        source_file_ids: list[str],
        source_dates: list[str],
        source_users: list[str],
        recipe: str,
        effects: list[str],
        processed_date: str,
        posted_ts: str = "",
    ) -> None:
        """Add a multi-source entry."""
        self.processed.append(
            ProcessedEntry(
                source_file_ids=source_file_ids,
                source_dates=source_dates,
                source_users=source_users,
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
        """Check if a single file+recipe pair has been processed (backward compat)."""
        return (file_id, recipe) in self.processed_pairs()

    def all_file_ids(self) -> set[str]:
        """Return all source file IDs that have been processed."""
        ids: set[str] = set()
        for e in self.processed:
            ids.update(e.source_file_ids)
        return ids

    def processed_pairs(self) -> set[tuple[str, str]]:
        """Return all (file_id, recipe) pairs (backward compat for single-source)."""
        pairs: set[tuple[str, str]] = set()
        for e in self.processed:
            for fid in e.source_file_ids:
                pairs.add((fid, e.recipe))
        return pairs

    def processed_combos(self) -> set[tuple[frozenset[str], str]]:
        """Return all (frozenset(file_ids), recipe) combos."""
        return {
            (frozenset(e.source_file_ids), e.recipe)
            for e in self.processed
        }


def _load_entry(data: dict) -> ProcessedEntry:
    """Load a ProcessedEntry from dict, handling old single-source format."""
    if "source_file_id" in data and "source_file_ids" not in data:
        # Old format: wrap singular fields in lists
        return ProcessedEntry(
            source_file_ids=[data["source_file_id"]],
            source_dates=[data["source_date"]],
            source_users=[data["source_user"]],
            recipe=data["recipe"],
            effects=data["effects"],
            processed_date=data["processed_date"],
            posted_ts=data.get("posted_ts", ""),
        )
    return ProcessedEntry(**data)
```

- [ ] **Step 4: Run all state tests**

Run: `pytest tests/test_state.py -v`
Expected: All tests PASS (old and new)

- [ ] **Step 5: Commit**

```bash
git add sparagmos/state.py tests/test_state.py
git commit -m "feat: state tracking supports multi-source entries

ProcessedEntry now stores lists: source_file_ids, source_dates,
source_users. New add_multi() method. Old add() wraps into list.
Backward compat: old state.json with singular fields loaded as lists.
New processed_combos() returns frozenset-based dedup keys."
```

---

## Task 9: Slack Source Multi-Image Fetching

**Can run in parallel with Tasks 8, 10.**

**Files:**
- Modify: `sparagmos/slack_source.py`
- Modify: `tests/test_slack.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_slack.py`:

```python
from sparagmos.slack_source import pick_random_images


def test_pick_random_images_returns_n():
    files = [
        {"id": f"F{i}", "user": f"U{i}", "timestamp": i * 1000}
        for i in range(10)
    ]
    result = pick_random_images(files, "recipe-a", 3, set(), seed=42)
    assert len(result) == 3
    ids = {f["id"] for f in result}
    assert len(ids) == 3  # all distinct


def test_pick_random_images_excludes_processed_combos():
    files = [
        {"id": "F1", "user": "U1", "timestamp": 1000},
        {"id": "F2", "user": "U2", "timestamp": 2000},
        {"id": "F3", "user": "U3", "timestamp": 3000},
    ]
    # Only combo F1+F2 has been processed
    processed = {(frozenset(["F1", "F2"]), "recipe-a")}
    result = pick_random_images(files, "recipe-a", 2, processed, seed=42)
    if result is not None:
        ids = frozenset(f["id"] for f in result)
        assert ids != frozenset(["F1", "F2"])


def test_pick_random_images_not_enough_files():
    files = [
        {"id": "F1", "user": "U1", "timestamp": 1000},
    ]
    result = pick_random_images(files, "recipe-a", 3, set(), seed=42)
    assert result is None


def test_pick_random_images_deterministic():
    files = [
        {"id": f"F{i}", "user": f"U{i}", "timestamp": i * 1000}
        for i in range(20)
    ]
    r1 = pick_random_images(files, "recipe-a", 3, set(), seed=42)
    r2 = pick_random_images(files, "recipe-a", 3, set(), seed=42)
    assert [f["id"] for f in r1] == [f["id"] for f in r2]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_slack.py -v -k "pick_random_images"`
Expected: FAIL — `pick_random_images` not importable

- [ ] **Step 3: Add pick_random_images to slack_source.py**

Add to the end of `sparagmos/slack_source.py` (before the last blank line):

```python
def pick_random_images(
    files: list[dict[str, Any]],
    recipe_slug: str,
    n: int,
    processed_combos: set[tuple[frozenset[str], str]],
    seed: int,
    max_attempts: int = 100,
) -> list[dict[str, Any]] | None:
    """Pick n distinct random images whose combination hasn't been used.

    Args:
        files: List of file metadata dicts.
        recipe_slug: Current recipe slug.
        n: Number of images to pick.
        processed_combos: Set of (frozenset(file_ids), recipe) already done.
        seed: RNG seed.
        max_attempts: Max random attempts before giving up.

    Returns:
        List of n file metadata dicts, or None if impossible.
    """
    if len(files) < n:
        logger.warning("Only %d images available, need %d", len(files), n)
        return None

    rng = random.Random(seed)

    for _ in range(max_attempts):
        selected = rng.sample(files, n)
        combo_key = frozenset(f["id"] for f in selected)
        if (combo_key, recipe_slug) not in processed_combos:
            return selected

    logger.warning("Could not find unused %d-image combo for %s after %d attempts",
                   n, recipe_slug, max_attempts)
    return None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_slack.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add sparagmos/slack_source.py tests/test_slack.py
git commit -m "feat: add pick_random_images for multi-input fetching

Picks n distinct images whose combination hasn't been used with the
given recipe. Checks against frozenset-based processed combos."
```

---

## Task 10: Slack Post Multi-Source Provenance

**Can run in parallel with Tasks 8, 9.**

**Files:**
- Modify: `sparagmos/slack_post.py`
- Modify: `tests/test_slack.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_slack.py`:

```python
from sparagmos.slack_post import format_provenance_multi


def test_format_provenance_multi():
    steps = [
        {"effect": "deepdream", "description": "d", "image": "a"},
        {"effect": "blend", "description": "d", "images": ["a", "b"], "into": "canvas"},
        {"effect": "jpeg_destroy", "description": "d", "image": "canvas"},
    ]
    result = PipelineResult(
        image=Image.new("RGB", (64, 64)),
        recipe_name="Voronoi Chimera",
        steps=steps,
    )
    sources = [
        {"user": "U1", "date": "2025-01-15", "permalink": "https://link1"},
        {"user": "U2", "date": "2025-02-20", "permalink": "https://link2"},
    ]
    text = format_provenance_multi(result, sources, channel_name="image-gen")
    assert "Voronoi Chimera" in text
    assert "deepdream(a)" in text
    assert "blend(a,b→canvas)" in text
    assert "jpeg_destroy(canvas)" in text
    assert "<@U1>" in text
    assert "<@U2>" in text
    assert "https://link1" in text
    assert "https://link2" in text


def test_format_provenance_multi_single_source():
    """Single-source recipes still format correctly with format_provenance_multi."""
    steps = [
        {"effect": "invert", "description": "d", "image": "canvas"},
    ]
    result = PipelineResult(
        image=Image.new("RGB", (64, 64)),
        recipe_name="Simple",
        steps=steps,
    )
    sources = [{"user": "U1", "date": "2025-01-01", "permalink": "https://link"}]
    text = format_provenance_multi(result, sources)
    assert "Simple" in text
    assert "<@U1>" in text
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_slack.py -v -k "provenance_multi"`
Expected: FAIL — `format_provenance_multi` not importable

- [ ] **Step 3: Add format_provenance_multi to slack_post.py**

Add to `sparagmos/slack_post.py`:

```python
def format_provenance_multi(
    result: PipelineResult,
    sources: list[dict],
    channel_name: str = "image-gen",
) -> str:
    """Format provenance for multi-source results.

    Args:
        result: Pipeline result with steps containing image/images metadata.
        sources: List of source metadata dicts (user, date, permalink).
        channel_name: Source channel name.

    Returns:
        Formatted provenance string.
    """
    # Build annotated effect chain
    chain_parts = []
    for step in result.steps:
        name = step["effect"]
        if "images" in step and step["images"]:
            into = step.get("into", "?")
            imgs = ",".join(step["images"])
            chain_parts.append(f"{name}({imgs}→{into})")
        elif "image" in step and step["image"]:
            chain_parts.append(f"{name}({step['image']})")
        else:
            chain_parts.append(name)
    chain = " → ".join(chain_parts)

    # Source attribution
    if len(sources) == 1:
        src = sources[0]
        source_line = f"source: image by <@{src.get('user', 'unknown')}> in #{channel_name} ({src.get('date', 'unknown')})"
    else:
        parts = [
            f"<@{s.get('user', 'unknown')}> ({s.get('date', 'unknown')})"
            for s in sources
        ]
        source_line = f"sources: {', '.join(parts)} in #{channel_name}"

    lines = [
        f"~ {result.recipe_name}",
        chain,
        source_line,
    ]

    # Original links
    permalinks = [s.get("permalink", "") for s in sources if s.get("permalink")]
    if permalinks:
        if len(permalinks) == 1:
            lines.append(f"original: <{permalinks[0]}|view>")
        else:
            link_parts = [f"<{p}|view>" for p in permalinks]
            lines.append(f"originals: {' · '.join(link_parts)}")

    return "\n".join(lines)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_slack.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add sparagmos/slack_post.py tests/test_slack.py
git commit -m "feat: multi-source provenance formatting

format_provenance_multi() builds annotated effect chains showing
image routing (e.g., 'blend(a,b→canvas)') and credits all sources."
```

---

## Task 11: CLI Multi-Input Support

**Depends on:** Tasks 1, 3, 8, 9, 10

**Files:**
- Modify: `sparagmos/cli.py`
- Modify: `tests/test_cli.py`

- [ ] **Step 1: Read existing test_cli.py**

Read `tests/test_cli.py` to understand the existing test patterns.

- [ ] **Step 2: Write failing tests for multi-input CLI**

Add to `tests/test_cli.py`:

```python
def test_input_accepts_multiple_files(tmp_path):
    """--input flag accepts multiple files via nargs='+'."""
    from sparagmos.cli import build_parser
    # Create test images
    for name in ["a.png", "b.png", "c.png"]:
        Image.new("RGB", (64, 64)).save(tmp_path / name)

    parser = build_parser()
    args = parser.parse_args([
        "--input", str(tmp_path / "a.png"), str(tmp_path / "b.png"), str(tmp_path / "c.png"),
        "--output", str(tmp_path / "out.png"),
    ])
    assert len(args.input) == 3


def test_input_single_file_still_works(tmp_path):
    """--input with one file returns a list of one."""
    from sparagmos.cli import build_parser
    Image.new("RGB", (64, 64)).save(tmp_path / "a.png")

    parser = build_parser()
    args = parser.parse_args([
        "--input", str(tmp_path / "a.png"),
        "--output", str(tmp_path / "out.png"),
    ])
    assert len(args.input) == 1
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/test_cli.py -v -k "input_accepts or input_single"`
Expected: FAIL — `args.input` is a string, not a list

- [ ] **Step 4: Update CLI argument parser**

In `sparagmos/cli.py`, change the `--input` argument:

```python
    parser.add_argument(
        "--input",
        nargs="+",
        help="Local image file(s) to process (skips Slack scraping)",
    )
```

- [ ] **Step 5: Update the main() function for multi-input**

The key changes to `main()` in `cli.py`:

1. When `--input` is provided: load all files, check count against recipe's `inputs`
2. When no `--input` (Slack mode): fetch N images based on recipe's `inputs`
3. Call `run_pipeline` with `images=` dict for multi-input, or single image for 1-input
4. Use `format_provenance_multi` and `state.add_multi` for multi-source

Replace the "Get source image" section and everything after it in `main()` with:

```python
    # Filter recipes by input count if using local files
    if args.input and not args.recipe:
        n_inputs = len(args.input)
        matching = {k: v for k, v in recipes.items() if v.inputs == n_inputs}
        if not matching:
            logger.error("No recipes with inputs=%d. Available input counts: %s",
                        n_inputs, sorted(set(r.inputs for r in recipes.values())))
            sys.exit(1)
        recipes = matching

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
    logger.info("Using recipe: %s (%s), inputs=%d", recipe_slug, recipe.name, recipe.inputs)

    # Get source images
    if args.input:
        # Local mode
        if len(args.input) != recipe.inputs:
            logger.error("Recipe %s requires %d inputs, got %d",
                        recipe_slug, recipe.inputs, len(args.input))
            sys.exit(1)

        source_images_list = [Image.open(f).convert("RGB") for f in args.input]
        sources_metadata = [{"user": "local", "date": "local"} for _ in args.input]
    else:
        # Slack mode
        from slack_sdk import WebClient
        from sparagmos.slack_source import (
            find_channel_id,
            fetch_image_files,
            pick_random_image,
            pick_random_images,
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

        if recipe.inputs == 1:
            selected_list = []
            sel = pick_random_image(files, recipe_slug, state.processed_pairs(), seed)
            if not sel:
                logger.warning("All images processed with recipe %s", recipe_slug)
                sys.exit(0)
            selected_list = [sel]
        else:
            selected_list = pick_random_images(
                files, recipe_slug, recipe.inputs, state.processed_combos(), seed,
            )
            if not selected_list:
                logger.warning("No unused %d-image combos for recipe %s",
                             recipe.inputs, recipe_slug)
                sys.exit(0)

        source_images_list = []
        sources_metadata = []
        for sel in selected_list:
            logger.info("Selected image: %s", sel["id"])
            image_bytes = download_image(sel["url"], token)
            source_images_list.append(Image.open(io.BytesIO(image_bytes)).convert("RGB"))

            ts = sel.get("timestamp", 0)
            source_date = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d") if ts else "unknown"
            sources_metadata.append({
                "user": sel["user"],
                "date": source_date,
                "permalink": sel.get("permalink", ""),
            })

    # Vision analysis (if recipe needs it)
    vision_data = None
    if recipe.vision:
        hf_token = os.environ.get("HF_TOKEN")
        if not hf_token:
            logger.warning("HF_TOKEN not set, skipping vision analysis")
        else:
            from sparagmos.vision import analyze_image
            vision_data = analyze_image(source_images_list[0], token=hf_token)

    # Build image dict
    from sparagmos.pipeline import run_pipeline, IMAGE_NAMES

    if recipe.inputs == 1:
        pipeline_images = None
        pipeline_image = source_images_list[0]
    else:
        pipeline_image = None
        pipeline_images = dict(zip(IMAGE_NAMES, source_images_list))

    # Run pipeline
    with tempfile.TemporaryDirectory(prefix="sparagmos_") as tmp:
        result = run_pipeline(
            image=pipeline_image,
            recipe=recipe,
            seed=seed,
            temp_dir=Path(tmp),
            vision=vision_data,
            source_metadata=sources_metadata[0] if len(sources_metadata) == 1 else {},
            images=pipeline_images,
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
            from sparagmos.slack_post import format_provenance_multi, post_result

            junkyard_id = find_channel_id(client, "img-junkyard")
            if not junkyard_id:
                logger.error("Channel #img-junkyard not found")
                sys.exit(1)

            posted_ts = post_result(
                client, junkyard_id, result, sources_metadata[0], "image-gen", Path(tmp),
            )

            # Update state
            today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            state.add_multi(
                source_file_ids=[s["id"] for s in selected_list],
                source_dates=[m["date"] for m in sources_metadata],
                source_users=[m["user"] for m in sources_metadata],
                recipe=recipe_slug,
                effects=[s["effect"] for s in result.steps],
                processed_date=today,
                posted_ts=posted_ts,
            )
            state.save()
            logger.info("State saved. Done.")
```

- [ ] **Step 6: Run tests**

Run: `pytest tests/test_cli.py -v`
Expected: All tests PASS

- [ ] **Step 7: Commit**

```bash
git add sparagmos/cli.py tests/test_cli.py
git commit -m "feat: CLI supports multi-input images

--input accepts multiple files (nargs='+'). Recipes filtered by
matching inputs count. Slack mode fetches N images based on recipe.
Uses add_multi for state tracking, format_provenance_multi for posting."
```

---

## Task 12: New Recipes

**Depends on:** Tasks 4–7 (compositing effects registered)

**Files:**
- Delete: all 12 existing recipe YAML files in `recipes/`
- Create: 12 new recipe YAML files in `recipes/`
- Modify: `tests/test_recipes.py`

- [ ] **Step 1: Delete existing recipes**

```bash
rm recipes/vhs-meltdown.yaml recipes/deep-fossil.yaml recipes/cga-nightmare.yaml \
   recipes/dionysian-rite.yaml recipes/analog-burial.yaml recipes/byte-liturgy.yaml \
   recipes/thermal-ghost.yaml recipes/turtle-oracle.yaml recipes/eigenface-requiem.yaml \
   recipes/spectral-autopsy.yaml recipes/cellular-decay.yaml recipes/ocr-feedback-loop.yaml
```

- [ ] **Step 2: Create voronoi-chimera.yaml**

```yaml
name: Voronoi Chimera
description: >
  Faces and forms fused at Voronoi cell boundaries. Each image gets a different
  neural/glitch treatment before being fragmented together. The Voronoi tessellation
  creates organic seams where images bleed into each other. Overlay blending
  intensifies the collisions, channel shift fractures the composite, and
  JPEG compression welds the seams permanently.

inputs: 3

steps:
  - type: deepdream
    image: a
    params:
      iterations: [5, 12]
      octave_scale: [1.3, 1.5]
      jitter: [24, 48]

  - type: pixel_sort
    image: b
    params:
      mode: hue
      threshold: [40, 100]

  - type: dither
    image: c
    params:
      method: bayer
      palette: cga

  - type: fragment
    images: [a, b, c]
    into: canvas
    params:
      cut_mode: voronoi
      pieces: [15, 35]
      mix_ratio: [0.6, 0.9]
      gap: [0, 3]

  - type: blend
    images: [canvas, a]
    into: canvas
    params:
      mode: overlay
      strength: [0.3, 0.5]

  - type: channel_shift
    image: canvas
    params:
      offset_r: [30, 80]
      offset_b: [-60, -20]

  - type: jpeg_destroy
    image: canvas
    params:
      quality: [1, 3]
      iterations: [15, 35]
```

- [ ] **Step 3: Create palimpsest.yaml**

```yaml
name: Palimpsest
description: >
  A manuscript overwritten and overwritten again. Each layer bleeds through
  based on luminance — dark regions of one image reveal the next beneath.
  Four images layered through progressively lower thresholds create a
  geological record of superimposed texts. Byte corruption ages the result,
  dithering reduces it to medieval dot patterns.

inputs: 4

steps:
  - type: pca_decompose
    image: a
    params:
      n_components: [3, 8]
      mode: top

  - type: channel_shift
    image: b
    params:
      offset_r: [10, 40]
      offset_b: [-30, -10]

  - type: crt_vhs
    image: c
    params:
      scan_line_density: [2, 3]
      jitter_amount: [3, 8]

  - type: pixel_sort
    image: d
    params:
      mode: brightness
      threshold: [60, 120]

  - type: mask_composite
    images: [a, b]
    into: canvas
    params:
      mask_source: luminance
      threshold: [80, 140]
      feather: [3, 10]

  - type: mask_composite
    images: [canvas, c]
    into: canvas
    params:
      mask_source: luminance
      threshold: [100, 170]
      feather: [5, 15]

  - type: mask_composite
    images: [canvas, d]
    into: canvas
    params:
      mask_source: luminance
      threshold: [140, 200]
      feather: [5, 20]

  - type: byte_corrupt
    image: canvas
    params:
      num_flips: [40, 100]
      mode: flip

  - type: dither
    image: canvas
    params:
      method: atkinson
      palette: thermal
```

- [ ] **Step 4: Create exquisite-corpse.yaml**

```yaml
name: Exquisite Corpse
description: >
  The surrealist parlor game. Three images divided into horizontal strips —
  head from one, torso from another, legs from a third. Each source gets
  different pre-processing to heighten the disjunction. Seam carving warps
  the joins, CRT effects add static to the seams, JPEG destroys the evidence.

inputs: 3

steps:
  - type: pixel_sort
    image: a
    params:
      mode: brightness
      threshold: [50, 100]

  - type: crt_vhs
    image: b
    params:
      jitter_amount: [5, 15]
      color_bleed: [2.0, 5.0]

  - type: channel_shift
    image: c
    params:
      offset_r: [15, 50]
      offset_g: [-20, 20]
      offset_b: [-40, -10]

  - type: fragment
    images: [a, b, c]
    into: canvas
    params:
      cut_mode: strips
      pieces: [3, 6]
      mix_ratio: [0.7, 1.0]

  - type: seam_carve
    image: canvas
    params:
      scale_x: [0.5, 0.7]

  - type: crt_vhs
    image: canvas
    params:
      scan_line_density: 2
      jitter_amount: [3, 8]

  - type: jpeg_destroy
    image: canvas
    params:
      quality: [1, 4]
      iterations: [10, 30]
```

- [ ] **Step 5: Create double-exposure.yaml**

```yaml
name: Double Exposure
description: >
  Two images burned onto the same film. Screen blending lets the light
  accumulate, multiply adds depth in the shadows. The double-exposed
  image is sonified — converted to audio, processed with echo and
  distortion, converted back. JPEG compression finalizes the photographic
  accident as a permanent artifact.

inputs: 2

steps:
  - type: spectral
    image: a
    params:
      mode: bandpass
      low_freq: [0.1, 0.3]
      high_freq: [0.6, 0.9]

  - type: sonify
    image: b
    params:
      effect: reverb
      intensity: [0.3, 0.5]

  - type: blend
    images: [a, b]
    into: canvas
    params:
      mode: screen
      strength: [0.6, 0.9]

  - type: blend
    images: [canvas, a]
    into: canvas
    params:
      mode: multiply
      strength: [0.3, 0.5]

  - type: sonify
    image: canvas
    params:
      effect: distortion
      intensity: [0.2, 0.5]

  - type: jpeg_destroy
    image: canvas
    params:
      quality: [1, 3]
      iterations: [12, 30]
```

- [ ] **Step 6: Create signal-bleed.yaml**

```yaml
name: Signal Bleed
description: >
  Three VHS signals bleeding into each other on a bad splitter. Each source
  gets its own flavor of analog decay — tracking errors, phosphor glow,
  scan lines at different densities. Vertical strip collage interleaves
  the signals. Channel shift and byte corruption simulate the crosstalk
  and signal degradation of cheap coaxial daisy-chaining.

inputs: 3

steps:
  - type: crt_vhs
    image: a
    params:
      scan_line_density: 2
      jitter_amount: [8, 20]
      color_bleed: [3.0, 6.0]

  - type: crt_vhs
    image: b
    params:
      scan_line_density: 3
      phosphor_glow: [0.15, 0.3]
      jitter_amount: [5, 12]

  - type: crt_vhs
    image: c
    params:
      scan_line_density: [2, 4]
      color_bleed: [4.0, 8.0]
      jitter_amount: [10, 25]

  - type: collage
    images: [a, b, c]
    into: canvas
    params:
      layout: strips

  - type: channel_shift
    image: canvas
    params:
      offset_r: [20, 70]
      offset_g: [5, 25]
      offset_b: [-60, -15]

  - type: byte_corrupt
    image: canvas
    params:
      num_flips: [50, 150]
      mode: flip

  - type: jpeg_destroy
    image: canvas
    params:
      quality: [2, 5]
      iterations: [8, 25]
```

- [ ] **Step 7: Create tectonic-overlap.yaml**

```yaml
name: Tectonic Overlap
description: >
  Continental plates of image data, shifted and overlapping. Four images
  shattered into irregular polygons via Delaunay triangulation, then
  scatter-collaged with rotation so the pieces overlap like geological
  strata. Seam carving warps the fault lines, JPEG compression compresses
  the geological record into stone.

inputs: 4

steps:
  - type: imagemagick
    image: a
    params:
      operation: swirl
      degrees: [30, 90]

  - type: deepdream
    image: b
    params:
      iterations: [3, 8]
      octave_scale: 1.4

  - type: sonify
    image: c
    params:
      effect: echo
      intensity: [0.3, 0.5]

  - type: dither
    image: d
    params:
      method: floyd_steinberg
      palette: ega

  - type: fragment
    images: [a, b, c, d]
    into: canvas
    params:
      cut_mode: shatter
      pieces: [20, 45]
      mix_ratio: [0.7, 1.0]
      gap: [2, 6]

  - type: collage
    images: [canvas, a]
    into: canvas
    params:
      layout: scatter
      rotation: [15, 60]
      scale_variance: [0.1, 0.3]

  - type: seam_carve
    image: canvas
    params:
      scale_x: [0.5, 0.7]

  - type: jpeg_destroy
    image: canvas
    params:
      quality: [1, 3]
      iterations: [15, 40]
```

- [ ] **Step 8: Create edge-ghosts.yaml**

```yaml
name: Edge Ghosts
description: >
  Phantom outlines from one image haunting another. Edge detection extracts
  the structural skeleton of each source — where one image's edges exist,
  another image bleeds through. Two rounds of edge-masking create layered
  ghosting. Spectral processing converts the haunted composite to frequency
  space, channel shift fractures the phantom light.

inputs: 3

steps:
  - type: spectral
    image: a
    params:
      mode: bandpass
      low_freq: [0.05, 0.2]
      high_freq: [0.7, 0.95]

  - type: pca_decompose
    image: b
    params:
      n_components: [5, 15]
      mode: top

  - type: channel_shift
    image: c
    params:
      offset_r: [20, 60]
      offset_b: [-50, -15]

  - type: mask_composite
    images: [a, b]
    into: canvas
    params:
      mask_source: edges
      threshold: [40, 100]
      feather: [5, 15]

  - type: mask_composite
    images: [canvas, c]
    into: canvas
    params:
      mask_source: edges
      threshold: [50, 120]
      feather: [3, 12]
      invert: true

  - type: spectral
    image: canvas
    params:
      mode: bandpass
      low_freq: [0.1, 0.3]
      high_freq: [0.6, 0.9]

  - type: channel_shift
    image: canvas
    params:
      offset_r: [30, 90]
      offset_g: [-15, 15]
      offset_b: [-70, -20]
```

- [ ] **Step 9: Create neural-chimera.yaml**

```yaml
name: Neural Chimera
description: >
  Three images deepdreamed at different neural layers — early layers see
  edges and textures, deep layers see dogs and pagodas. Voronoi-fragmented
  together so hallucinated regions from different layers merge at organic
  boundaries. Overlay blending intensifies, style transfer recursively
  re-hallucinates the composite, JPEG destroys the evidence.

inputs: 3

steps:
  - type: deepdream
    image: a
    params:
      iterations: [8, 15]
      octave_scale: 1.4
      learning_rate: [0.01, 0.02]

  - type: deepdream
    image: b
    params:
      iterations: [5, 10]
      octave_scale: [1.2, 1.4]
      learning_rate: [0.005, 0.015]

  - type: deepdream
    image: c
    params:
      iterations: [10, 20]
      octave_scale: 1.5
      learning_rate: [0.01, 0.025]

  - type: fragment
    images: [a, b, c]
    into: canvas
    params:
      cut_mode: voronoi
      pieces: [12, 30]
      mix_ratio: [0.6, 0.9]

  - type: blend
    images: [canvas, b]
    into: canvas
    params:
      mode: overlay
      strength: [0.3, 0.5]

  - type: style_transfer
    image: canvas
    params:
      style_weight: [500000, 1500000]
      content_weight: 1
      iterations: [10, 25]

  - type: jpeg_destroy
    image: canvas
    params:
      quality: [1, 3]
      iterations: [12, 30]
```

- [ ] **Step 10: Create spectral-merge.yaml**

```yaml
name: Spectral Merge
description: >
  Two signals in frequency space, destructively interfered. Each image is
  treated as a spectrogram and bandpass-filtered to different frequency
  ranges. Difference blending cancels shared frequencies, mask compositing
  selects the most extreme residuals. Dithering quantizes the interference
  pattern into discrete frequency bands.

inputs: 2

steps:
  - type: spectral
    image: a
    params:
      mode: bandpass
      low_freq: [0.1, 0.3]
      high_freq: [0.5, 0.7]

  - type: spectral
    image: b
    params:
      mode: bandpass
      low_freq: [0.3, 0.5]
      high_freq: [0.7, 0.95]

  - type: blend
    images: [a, b]
    into: canvas
    params:
      mode: difference
      strength: [0.7, 1.0]

  - type: mask_composite
    images: [canvas, a]
    into: canvas
    params:
      mask_source: luminance
      threshold: [80, 160]
      feather: [5, 15]

  - type: sonify
    image: canvas
    params:
      effect: echo
      intensity: [0.3, 0.6]

  - type: dither
    image: canvas
    params:
      method: floyd_steinberg
      palette: thermal
```

- [ ] **Step 11: Create mosaic-dissolution.yaml**

```yaml
name: Mosaic Dissolution
description: >
  Five sources tiled into a mosaic, then the mosaic itself is fragmented
  and pixel-sorted into dust. Maximum input count, maximum chaos. Random
  rectangles from each source fill the canvas, the mosaic is grid-fragmented
  and reassembled, pixel sorting melts vertical columns, JPEG and byte
  corruption reduce it to digital sediment.

inputs: 5

steps:
  - type: channel_shift
    image: a
    params:
      offset_r: [10, 40]

  - type: crt_vhs
    image: b
    params:
      jitter_amount: [5, 12]

  - type: dither
    image: c
    params:
      method: bayer
      palette: gameboy

  - type: pixel_sort
    image: d
    params:
      mode: saturation
      threshold: [40, 90]

  - type: pca_decompose
    image: e
    params:
      n_components: [3, 8]
      mode: bottom

  - type: collage
    images: [a, b, c, d, e]
    into: canvas
    params:
      layout: mosaic

  - type: fragment
    images: [canvas, a]
    into: canvas
    params:
      cut_mode: grid
      pieces: [16, 36]
      mix_ratio: [0.3, 0.6]

  - type: pixel_sort
    image: canvas
    params:
      mode: brightness
      threshold: [30, 80]

  - type: jpeg_destroy
    image: canvas
    params:
      quality: [1, 3]
      iterations: [15, 40]

  - type: byte_corrupt
    image: canvas
    params:
      num_flips: [60, 180]
      mode: flip
```

- [ ] **Step 12: Create fossil-record.yaml**

```yaml
name: Fossil Record
description: >
  Geological strata. Each image is PCA-decomposed to different component
  counts — deep reconstruction (few components) versus shallow (many).
  Opacity-blended as layers, like sedimentary rock compressed over eons.
  Dithering creates the granular texture of stone, channel shift adds
  mineral coloration to the strata.

inputs: 3

steps:
  - type: pca_decompose
    image: a
    params:
      n_components: [2, 5]
      mode: top

  - type: pca_decompose
    image: b
    params:
      n_components: [8, 15]
      mode: top

  - type: pca_decompose
    image: c
    params:
      n_components: [15, 30]
      mode: top

  - type: blend
    images: [a, b]
    into: canvas
    params:
      mode: opacity
      strength: [0.4, 0.6]

  - type: blend
    images: [canvas, c]
    into: canvas
    params:
      mode: opacity
      strength: [0.3, 0.5]

  - type: dither
    image: canvas
    params:
      method: floyd_steinberg
      palette: thermal

  - type: channel_shift
    image: canvas
    params:
      offset_r: [15, 50]
      offset_g: [-10, 10]
      offset_b: [-40, -10]

  - type: jpeg_destroy
    image: canvas
    params:
      quality: [2, 5]
      iterations: [8, 20]
```

- [ ] **Step 13: Create feedback-loop.yaml**

```yaml
name: Feedback Loop
description: >
  Compose, destroy, re-compose the wreckage, destroy again. Two images
  blended, then distorted with ImageMagick, then the wreckage is fragmented
  back together with the original images. Channel shift and JPEG compression
  each round — the output feeds conceptually back into itself, each pass
  compounding the damage.

inputs: 2

steps:
  - type: blend
    images: [a, b]
    into: canvas
    params:
      mode: screen
      strength: [0.5, 0.8]

  - type: imagemagick
    image: canvas
    params:
      operation: swirl
      degrees: [45, 120]

  - type: channel_shift
    image: canvas
    params:
      offset_r: [15, 50]
      offset_b: [-40, -10]

  - type: fragment
    images: [canvas, a, b]
    into: canvas
    params:
      cut_mode: grid
      pieces: [9, 20]
      mix_ratio: [0.5, 0.8]

  - type: blend
    images: [canvas, b]
    into: canvas
    params:
      mode: overlay
      strength: [0.3, 0.5]

  - type: channel_shift
    image: canvas
    params:
      offset_r: [20, 70]
      offset_g: [-15, 15]
      offset_b: [-60, -20]

  - type: jpeg_destroy
    image: canvas
    params:
      quality: [1, 3]
      iterations: [15, 35]
```

- [ ] **Step 14: Update test_recipes.py to validate all new recipes**

Read `tests/test_recipes.py` and ensure it validates all new YAML files. The existing test likely iterates over all YAML files in `recipes/` — it should work automatically. Run:

Run: `pytest tests/test_recipes.py -v`
Expected: All 12 recipes PASS validation

- [ ] **Step 15: Commit**

```bash
git add recipes/ tests/test_recipes.py
git commit -m "feat: replace all recipes with 12 multi-input recipes

New recipes: voronoi-chimera (3), palimpsest (4), exquisite-corpse (3),
double-exposure (2), signal-bleed (3), tectonic-overlap (4),
edge-ghosts (3), neural-chimera (3), spectral-merge (2),
mosaic-dissolution (5), fossil-record (3), feedback-loop (2).

Every recipe uses 2-5 inputs with compositing effects interleaved
with destruction effects."
```

---

## Task 13: Multi-Image Test Fixtures & Integration Tests

**Depends on:** All previous tasks

**Files:**
- Modify: `tests/conftest.py`
- Modify: `tests/test_integration.py`

- [ ] **Step 1: Add multi-image fixtures to conftest.py**

Add to `tests/conftest.py`:

```python
@pytest.fixture
def test_images_multi():
    """Create 5 distinct test images for multi-input testing."""
    colors = [
        (200, 50, 50),   # reddish
        (50, 200, 50),   # greenish
        (50, 50, 200),   # bluish
        (200, 200, 50),  # yellowish
        (200, 50, 200),  # magentaish
    ]
    imgs = []
    for i, color in enumerate(colors):
        img = Image.new("RGB", (64, 64))
        pixels = img.load()
        for x in range(64):
            for y in range(64):
                pixels[x, y] = (
                    (color[0] + x * 2) % 256,
                    (color[1] + y * 2) % 256,
                    (color[2] + (x + y)) % 256,
                )
        imgs.append(img)
    return imgs
```

- [ ] **Step 2: Write integration test for multi-input pipeline**

Add to `tests/test_integration.py`:

```python
from sparagmos.pipeline import run_pipeline, IMAGE_NAMES
from sparagmos.config import Recipe, RecipeStep, load_recipe, load_all_recipes


def test_multi_input_pipeline_end_to_end(test_images_multi, tmp_path):
    """Full pipeline with a multi-input recipe."""
    from sparagmos.effects.blend import BlendEffect
    from sparagmos.effects.fragment import FragmentEffect
    from sparagmos.effects.collage import CollageEffect
    from sparagmos.effects.mask_composite import MaskCompositeEffect

    # Register compositing effects (may already be registered)
    from sparagmos.effects import register_effect, list_effects
    for eff_cls in [BlendEffect, CollageEffect, MaskCompositeEffect, FragmentEffect]:
        if eff_cls().name not in list_effects():
            register_effect(eff_cls())

    recipe = Recipe(
        name="Integration Test",
        description="test",
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
```

- [ ] **Step 3: Run integration tests**

Run: `pytest tests/test_integration.py -v`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add tests/conftest.py tests/test_integration.py
git commit -m "test: add multi-image fixtures and integration tests

test_images_multi fixture provides 5 distinct colored test images.
Integration test verifies end-to-end multi-input pipeline with
blend and mask_composite compositing steps."
```

---

## Task 14: Documentation Updates

**Depends on:** All previous tasks

**Files:**
- Modify: `README.md`
- Modify: `docs/effects.md`
- Modify: `docs/recipes.md`
- Modify: `recipes/README.md`

- [ ] **Step 1: Read current documentation files**

Read `README.md`, `docs/effects.md`, `docs/recipes.md`, `recipes/README.md` to understand current content.

- [ ] **Step 2: Update docs/effects.md with compositing section**

Add a "Compositing Effects" section after the existing effects table, documenting all four compositing effects with their parameters, modes, and usage examples. Include the full parameter tables from the design spec.

- [ ] **Step 3: Rewrite docs/recipes.md for new schema**

Update with:
- New recipe schema showing `inputs:`, `steps:`, `image:`, `images:`, `into:` fields
- Named-image model explanation and naming convention
- Example multi-input recipe with commentary
- Tips on recipe design (pre-process → compose → destroy → re-compose patterns)
- Backward compatibility notes

- [ ] **Step 4: Update recipes/README.md**

Update with descriptions of all 12 new recipes, their input counts, and the compositing/destruction patterns they use.

- [ ] **Step 5: Update README.md**

Update the main README:
- Overview section: mention multi-input compositing
- Effects table: add compositing effects (collage, blend, mask_composite, fragment)
- Quickstart: show `--input a.jpg b.jpg c.jpg` usage
- Architecture: mention named-image register model

- [ ] **Step 6: Commit**

```bash
git add README.md docs/effects.md docs/recipes.md recipes/README.md
git commit -m "docs: update all documentation for multi-input compositing

Updated effects reference with compositing effects section.
Rewrote recipe schema docs for new multi-input fields.
Updated recipe guide with all 12 new recipes.
Updated README with multi-input architecture and quickstart."
```

---

## Task 15: CI Validation

**Depends on:** All previous tasks

- [ ] **Step 1: Push branch and check CI**

```bash
git push -u origin multi-input-compositing
```

- [ ] **Step 2: Monitor CI run**

Check the GitHub Actions test workflow. Verify all tests pass including:
- Unit tests for all 4 compositing effects
- Pipeline multi-image tests
- Config schema tests
- State multi-source tests
- Slack source/post tests
- Recipe validation tests
- Integration tests

- [ ] **Step 3: Fix any CI failures**

If tests fail in CI (e.g., missing scipy dependency for Voronoi), fix and push. Common issues:
- `scipy` may need to be added to `requirements.txt` if not already present
- `opencv-python` (`cv2`) may need to be in deps for `mask_composite` edge detection

- [ ] **Step 4: Verify all green, create PR**

Once CI is green, create a PR targeting `main`.
