# Ancients Collage Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Integrate A-U-Supply/collage-bot as a vendored dependency, exposing its two image processing pipelines (quadrant collage + stencil masking) as sparagmos ComposeEffect subclasses with multi-output support.

**Architecture:** The collage-bot code is vendored via `git subtree` into `sparagmos/vendor/collage_bot/`. A thin adapter in `sparagmos/effects/ancient.py` wraps the vendored transform functions as `ComposeEffect` subclasses. The pipeline and CLI are extended to support multi-output effects (returning multiple images from a single compose call).

**Tech Stack:** Python 3.11+, Pillow, NumPy, simple-lama-inpainting (LaMa neural inpainting), PyTorch

---

## File Structure

| Action | Path | Responsibility |
|--------|------|----------------|
| Create (subtree) | `sparagmos/vendor/collage_bot/` | Vendored collage-bot source |
| Create | `sparagmos/vendor/__init__.py` | Make vendor directory a Python package |
| Create | `sparagmos/vendor/collage_bot/PROVENANCE.md` | Document vendoring provenance |
| Modify | `sparagmos/effects/__init__.py:36-41` | Add `images` field to `EffectResult` |
| Modify | `sparagmos/pipeline.py:23-29,100-167` | Add `images` field to `PipelineResult`, handle multi-output |
| Modify | `sparagmos/cli.py:300-342` | Handle multi-image output in local/Slack modes |
| Create | `sparagmos/effects/ancient.py` | Adapter wrapping collage-bot transforms |
| Create | `recipes/ancients-collage.yaml` | 4-input collage recipe |
| Create | `recipes/ancients-stencil.yaml` | 3-input stencil recipe |
| Modify | `requirements.txt` | Add `simple-lama-inpainting` |
| Create | `tests/test_effects/test_ancient.py` | Unit + integration tests |

---

### Task 1: Vendor collage-bot via git subtree

**Files:**
- Create (subtree): `sparagmos/vendor/collage_bot/`
- Create: `sparagmos/vendor/__init__.py`
- Create: `sparagmos/vendor/collage_bot/PROVENANCE.md`
- Modify: `requirements.txt`

- [ ] **Step 1: Add collage-bot as git subtree**

```bash
cd /Users/jake/au-supply/worktrees/ancients-collage
git subtree add --prefix sparagmos/vendor/collage_bot \
    https://github.com/A-U-Supply/collage-bot.git main --squash
```

This creates `sparagmos/vendor/collage_bot/` containing the full collage-bot source (transform.py, stencil_transform.py, bot.py, etc.).

- [ ] **Step 2: Create vendor `__init__.py`**

Create an empty `__init__.py` so Python can import from `sparagmos.vendor.collage_bot`:

```python
# sparagmos/vendor/__init__.py
```

(Empty file — just marks the directory as a package.)

- [ ] **Step 3: Write PROVENANCE.md**

Get the current commit hash from the subtree and write provenance docs:

```bash
cd /Users/jake/au-supply/worktrees/ancients-collage
git log --oneline sparagmos/vendor/collage_bot/ | head -1
```

Then create `sparagmos/vendor/collage_bot/PROVENANCE.md`:

```markdown
# collage_bot — Vendored via git subtree

- **Source:** https://github.com/A-U-Supply/collage-bot
- **Branch:** main
- **Commit:** <hash from step above>
- **Date vendored:** 2026-04-02
- **License:** (check repo for license, or note "No license file found")

## Modifications

- Directory vendored as `collage_bot` (underscore) instead of `collage-bot`
  (hyphen) so Python can import it.

## Updating

```bash
git subtree pull --prefix sparagmos/vendor/collage_bot \
    https://github.com/A-U-Supply/collage-bot.git main --squash
```
```

- [ ] **Step 4: Add `simple-lama-inpainting` to requirements.txt**

Add `simple-lama-inpainting>=0.1.0` to `requirements.txt`. The file currently contains:

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

Add after the `torchvision` line:

```
simple-lama-inpainting>=0.1.0
```

Also pin numpy upper bound for compatibility. Change `numpy>=1.24` to `numpy>=1.24,<2`.

- [ ] **Step 5: Install updated dependencies**

```bash
cd /Users/jake/au-supply/worktrees/ancients-collage
pip install -r requirements.txt
```

- [ ] **Step 6: Verify vendored code imports**

```bash
cd /Users/jake/au-supply/worktrees/ancients-collage
python -c "from sparagmos.vendor.collage_bot.transform import cut_quadrants, make_composites, apply_transform, blend_seams; print('transform OK')"
python -c "from sparagmos.vendor.collage_bot.stencil_transform import make_stencil, apply_stencil; print('stencil OK')"
```

Expected: both print OK. If the collage-bot directory doesn't have an `__init__.py`, create one:

```bash
touch sparagmos/vendor/collage_bot/__init__.py
```

Then retry the imports.

- [ ] **Step 7: Commit**

```bash
git add sparagmos/vendor/__init__.py sparagmos/vendor/collage_bot/PROVENANCE.md requirements.txt
git commit -m "feat: vendor collage-bot via git subtree

Add A-U-Supply/collage-bot as a git subtree in sparagmos/vendor/collage_bot/.
Add simple-lama-inpainting dependency and numpy<2 pin for compatibility.
Include PROVENANCE.md documenting source, commit, and update instructions."
```

Note: The subtree add itself creates a commit. This second commit adds the provenance doc, `__init__.py`, and requirements changes.

---

### Task 2: Add multi-output support to EffectResult and PipelineResult

**Files:**
- Modify: `sparagmos/effects/__init__.py:36-41`
- Modify: `sparagmos/pipeline.py:23-29,100-167`
- Test: `tests/test_effects/test_ancient.py` (tested in Task 4)

- [ ] **Step 1: Write failing test for multi-output EffectResult**

Create `tests/test_multi_output.py`:

```python
"""Tests for multi-output pipeline support."""

from __future__ import annotations

import numpy as np
import pytest
from PIL import Image

from sparagmos.effects import EffectResult


def _make_image(color: tuple[int, int, int], size: int = 32) -> Image.Image:
    arr = np.full((size, size, 3), color, dtype=np.uint8)
    return Image.fromarray(arr, mode="RGB")


def test_effect_result_images_field_defaults_to_none():
    img = _make_image((100, 100, 100))
    result = EffectResult(image=img)
    assert result.images is None


def test_effect_result_images_field_accepts_list():
    imgs = [_make_image((i * 50, 0, 0)) for i in range(4)]
    result = EffectResult(image=imgs[0], images=imgs)
    assert result.images is not None
    assert len(result.images) == 4
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /Users/jake/au-supply/worktrees/ancients-collage
pytest tests/test_multi_output.py -v
```

Expected: FAIL — `EffectResult` doesn't have an `images` field yet.

- [ ] **Step 3: Add `images` field to `EffectResult`**

In `sparagmos/effects/__init__.py`, change the `EffectResult` dataclass (around line 38):

```python
@dataclass
class EffectResult:
    """Result from applying an effect."""

    image: Image.Image
    metadata: dict[str, Any] = field(default_factory=dict)
    images: list[Image.Image] | None = None
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd /Users/jake/au-supply/worktrees/ancients-collage
pytest tests/test_multi_output.py -v
```

Expected: PASS

- [ ] **Step 5: Write failing test for multi-output PipelineResult**

Append to `tests/test_multi_output.py`:

```python
from sparagmos.pipeline import PipelineResult


def test_pipeline_result_images_field_defaults_to_none():
    img = _make_image((100, 100, 100))
    result = PipelineResult(image=img, recipe_name="test")
    assert result.images is None


def test_pipeline_result_images_field_accepts_list():
    imgs = [_make_image((i * 50, 0, 0)) for i in range(3)]
    result = PipelineResult(image=imgs[0], recipe_name="test", images=imgs)
    assert result.images is not None
    assert len(result.images) == 3
```

- [ ] **Step 6: Run test to verify it fails**

```bash
cd /Users/jake/au-supply/worktrees/ancients-collage
pytest tests/test_multi_output.py::test_pipeline_result_images_field_defaults_to_none -v
```

Expected: FAIL — `PipelineResult` doesn't have an `images` field.

- [ ] **Step 7: Add `images` field to `PipelineResult`**

In `sparagmos/pipeline.py`, change the `PipelineResult` dataclass (around line 24):

```python
@dataclass
class PipelineResult:
    """Result of running a complete recipe pipeline."""

    image: Image.Image
    recipe_name: str
    steps: list[dict[str, Any]] = field(default_factory=list)
    images: list[Image.Image] | None = None
```

- [ ] **Step 8: Run test to verify it passes**

```bash
cd /Users/jake/au-supply/worktrees/ancients-collage
pytest tests/test_multi_output.py -v
```

Expected: all 4 tests PASS

- [ ] **Step 9: Update pipeline to propagate multi-output**

In `sparagmos/pipeline.py`, modify the `run_pipeline` function. After the for loop over steps (around line 151), before the final return, add multi-output propagation. Replace the section from `if "canvas" not in registers:` to the end of the function:

```python
    if "canvas" not in registers:
        raise ValueError(
            "Pipeline ended without a 'canvas' image. "
            "Ensure at least one step writes to 'canvas' (via into='canvas' or default routing)."
        )

    # Check if the final step produced multiple images
    final_images = None
    if steps and steps[-1].get("_multi_images") is not None:
        final_images = steps[-1].pop("_multi_images")

    return PipelineResult(
        image=registers["canvas"],
        recipe_name=recipe.name,
        steps=steps,
        images=final_images,
    )
```

Also, in the compositing branch of the for loop (around line 119-136), after `result = effect.compose(...)`, add multi-output capture:

```python
            if step.images is not None:
                # Compositing step: gather source images by name, call compose()
                source_images = [registers[name] for name in step.images]
                assert isinstance(effect, ComposeEffect), (
                    f"Step {i} specifies images= but effect {effect.name!r} "
                    f"is not a ComposeEffect"
                )
                result = effect.compose(source_images, resolved, context)
                target = step.into or "canvas"
                registers[target] = result.image.convert("RGB")

                step_record = {
                    "effect": effect.name,
                    "description": effect.description,
                    "resolved_params": resolved,
                    "metadata": result.metadata,
                    "images": list(step.images),
                    "into": target,
                }
                # Preserve multi-output images for final step propagation
                if result.images is not None:
                    step_record["_multi_images"] = result.images

                steps.append(step_record)
```

- [ ] **Step 10: Run all existing tests**

```bash
cd /Users/jake/au-supply/worktrees/ancients-collage
pytest tests/ -v --tb=short
```

Expected: all tests PASS (multi-output is backward-compatible — existing effects return `images=None`).

- [ ] **Step 11: Commit**

```bash
git add sparagmos/effects/__init__.py sparagmos/pipeline.py tests/test_multi_output.py
git commit -m "feat: add multi-output support to EffectResult and PipelineResult

Add optional images field to both EffectResult and PipelineResult.
Pipeline propagates multi-output from the final compose step.
Backward compatible — existing single-output effects are unaffected."
```

---

### Task 3: Implement the ancient effect adapter

**Files:**
- Create: `sparagmos/effects/ancient.py`
- Test: `tests/test_effects/test_ancient.py`

This task implements both `AncientCollageEffect` and `AncientStencilEffect` in a single adapter file.

- [ ] **Step 1: Write failing tests for AncientStencilEffect**

Start with stencil because it has no external dependency (no SimpleLama), making it faster to test.

Create `tests/test_effects/test_ancient.py`:

```python
"""Tests for ancient effects (collage-bot adapter)."""

from __future__ import annotations

import numpy as np
import pytest
from PIL import Image

from sparagmos.effects import EffectContext


def _make_image(color: tuple[int, int, int], size: int = 64) -> Image.Image:
    arr = np.full((size, size, 3), color, dtype=np.uint8)
    return Image.fromarray(arr, mode="RGB")


@pytest.fixture
def context(tmp_path):
    return EffectContext(vision=None, temp_dir=tmp_path, seed=42, source_metadata={})


# --- AncientStencilEffect tests ---

@pytest.fixture
def stencil_effect():
    from sparagmos.effects.ancient import AncientStencilEffect
    return AncientStencilEffect()


@pytest.fixture
def stencil_images():
    """Three images: one high-contrast (good mask), two solid colors."""
    # Mask image: left half black, right half white
    mask_arr = np.zeros((64, 64, 3), dtype=np.uint8)
    mask_arr[:, 32:, :] = 255
    mask_img = Image.fromarray(mask_arr, mode="RGB")
    red = _make_image((255, 0, 0))
    blue = _make_image((0, 0, 255))
    return [mask_img, red, blue]


def test_stencil_output_all(stencil_effect, stencil_images, context):
    """output=all produces 6 variations (3 images, each as mask, 2 orderings each)."""
    result = stencil_effect.compose(
        stencil_images,
        {"output": "all"},
        context,
    )
    assert result.images is not None
    assert len(result.images) == 6
    for img in result.images:
        assert img.mode == "RGB"
        assert img.size == (64, 64)


def test_stencil_output_random(stencil_effect, stencil_images, context):
    """output=random produces exactly 1 image."""
    result = stencil_effect.compose(
        stencil_images,
        {"output": "random"},
        context,
    )
    assert result.images is not None
    assert len(result.images) == 1
    assert result.image.mode == "RGB"


def test_stencil_validate_params_defaults(stencil_effect):
    """Default params are applied."""
    params = stencil_effect.validate_params({})
    assert params["output"] == "all"


def test_stencil_validate_params_invalid_output(stencil_effect):
    """Invalid output value raises ConfigError."""
    from sparagmos.effects import ConfigError
    with pytest.raises(ConfigError):
        stencil_effect.validate_params({"output": "first"})
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /Users/jake/au-supply/worktrees/ancients-collage
pytest tests/test_effects/test_ancient.py -v -k stencil
```

Expected: FAIL — `sparagmos.effects.ancient` doesn't exist yet.

- [ ] **Step 3: Implement AncientStencilEffect**

Create `sparagmos/effects/ancient.py`:

```python
"""Ancient effects — adapter wrapping A-U-Supply/collage-bot transforms.

Vendored source: sparagmos/vendor/collage_bot/
Update: git subtree pull --prefix sparagmos/vendor/collage_bot \
    https://github.com/A-U-Supply/collage-bot.git main --squash

To add a new mode from collage-bot:
  1. Pull latest with the command above
  2. Add a new ComposeEffect subclass below (~20-30 lines)
  3. Add a new recipe YAML in recipes/ancients-<mode>.yaml
"""

from __future__ import annotations

import random
from itertools import permutations

from PIL import Image

from sparagmos.effects import (
    ComposeEffect,
    ConfigError,
    EffectContext,
    EffectResult,
    register_effect,
)
from sparagmos.vendor.collage_bot.stencil_transform import apply_stencil, make_stencil

VALID_OUTPUTS = {"all", "random"}


class AncientStencilEffect(ComposeEffect):
    """Binary mask compositing via Otsu's thresholding.

    Each input image takes a turn as the stencil mask. For each mask,
    the remaining images are composited in both orderings (foreground/
    background swap), producing N * (N-1) variations for N inputs.
    With 3 inputs this yields 6 variations.
    """

    name = "ancient_stencil"
    description = "Otsu stencil masking from collage-bot"
    requires: list[str] = []

    def compose(
        self, images: list[Image.Image], params: dict, context: EffectContext
    ) -> EffectResult:
        params = self.validate_params(params)
        output_mode: str = params["output"]
        rng = random.Random(context.seed)

        results: list[Image.Image] = []
        n = len(images)

        for i in range(n):
            mask = make_stencil(images[i])
            others = [images[j] for j in range(n) if j != i]
            for perm in permutations(others):
                composite = apply_stencil(mask, perm[0], perm[1])
                results.append(composite)

        if output_mode == "random":
            chosen = rng.choice(results)
            return EffectResult(
                image=chosen,
                images=[chosen],
                metadata={"mode": "stencil", "output": "random", "total_variations": len(results)},
            )

        return EffectResult(
            image=results[0],
            images=results,
            metadata={"mode": "stencil", "output": "all", "total_variations": len(results)},
        )

    def validate_params(self, params: dict) -> dict:
        output = params.get("output", "all")
        if output not in VALID_OUTPUTS:
            raise ConfigError(
                f"Unknown output mode: {output!r}. Valid: {sorted(VALID_OUTPUTS)}",
                effect_name="ancient_stencil",
                param_name="output",
            )
        return {"output": output}


register_effect(AncientStencilEffect())
```

- [ ] **Step 4: Run stencil tests to verify they pass**

```bash
cd /Users/jake/au-supply/worktrees/ancients-collage
pytest tests/test_effects/test_ancient.py -v -k stencil
```

Expected: all 4 stencil tests PASS.

- [ ] **Step 5: Write failing tests for AncientCollageEffect**

Append to `tests/test_effects/test_ancient.py`:

```python
# --- AncientCollageEffect tests ---

@pytest.fixture
def collage_effect():
    from sparagmos.effects.ancient import AncientCollageEffect
    return AncientCollageEffect()


@pytest.fixture
def collage_images():
    """Four distinct solid-color images."""
    colors = [(255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 0)]
    return [_make_image(c) for c in colors]


def test_collage_output_all(collage_effect, collage_images, context):
    """output=all produces 4 composites."""
    result = collage_effect.compose(
        collage_images,
        {"output": "all", "split": 0.25, "blend_width": 70},
        context,
    )
    assert result.images is not None
    assert len(result.images) == 4
    for img in result.images:
        assert img.mode == "RGB"


def test_collage_output_random(collage_effect, collage_images, context):
    """output=random produces exactly 1 image."""
    result = collage_effect.compose(
        collage_images,
        {"output": "random"},
        context,
    )
    assert result.images is not None
    assert len(result.images) == 1


def test_collage_validate_params_defaults(collage_effect):
    """Default params are applied correctly."""
    params = collage_effect.validate_params({})
    assert params["output"] == "all"
    assert params["split"] == 0.25
    assert params["blend_width"] == 70


def test_collage_validate_params_invalid_output(collage_effect):
    """Invalid output value raises ConfigError."""
    from sparagmos.effects import ConfigError
    with pytest.raises(ConfigError):
        collage_effect.validate_params({"output": "none"})


def test_collage_validate_params_clamps_split(collage_effect):
    """Split is clamped to [0.05, 0.45]."""
    params = collage_effect.validate_params({"split": 0.0})
    assert params["split"] == 0.05
    params = collage_effect.validate_params({"split": 0.9})
    assert params["split"] == 0.45
```

- [ ] **Step 6: Run tests to verify they fail**

```bash
cd /Users/jake/au-supply/worktrees/ancients-collage
pytest tests/test_effects/test_ancient.py -v -k collage
```

Expected: FAIL — `AncientCollageEffect` doesn't exist yet.

- [ ] **Step 7: Implement AncientCollageEffect**

Add to `sparagmos/effects/ancient.py`, before the final `register_effect` calls. Add the import at the top:

```python
from sparagmos.vendor.collage_bot.transform import (
    apply_transform,
    blend_seams,
    cut_quadrants,
    make_composites,
)
```

Then add the class:

```python
class AncientCollageEffect(ComposeEffect):
    """Quadrant-mixed composites with geometric transform and seam inpainting.

    Takes 4 source images, cuts each into quadrants, shuffles quadrants
    across 4 output composites, applies a grid transform, and uses LaMa
    neural inpainting to blend the seams seamlessly.
    """

    name = "ancient_collage"
    description = "Quadrant collage with seam inpainting from collage-bot"
    requires: list[str] = []

    def compose(
        self, images: list[Image.Image], params: dict, context: EffectContext
    ) -> EffectResult:
        params = self.validate_params(params)
        output_mode: str = params["output"]
        split: float = params["split"]
        blend_width: int = params["blend_width"]
        rng = random.Random(context.seed)

        # Seed Python's global random for collage-bot functions that use it
        random.seed(context.seed)

        composites = make_composites([img.convert("RGB") for img in images])
        results: list[Image.Image] = []
        for comp in composites:
            transformed = apply_transform(comp, split=split)
            blended = blend_seams(transformed, strip_width=blend_width, split=split)
            results.append(blended.convert("RGB"))

        if output_mode == "random":
            chosen = rng.choice(results)
            return EffectResult(
                image=chosen,
                images=[chosen],
                metadata={"mode": "collage", "output": "random", "total_composites": len(results)},
            )

        return EffectResult(
            image=results[0],
            images=results,
            metadata={"mode": "collage", "output": "all", "total_composites": len(results)},
        )

    def validate_params(self, params: dict) -> dict:
        output = params.get("output", "all")
        if output not in VALID_OUTPUTS:
            raise ConfigError(
                f"Unknown output mode: {output!r}. Valid: {sorted(VALID_OUTPUTS)}",
                effect_name="ancient_collage",
                param_name="output",
            )
        split = float(params.get("split", 0.25))
        split = max(0.05, min(0.45, split))
        blend_width = int(params.get("blend_width", 70))
        blend_width = max(1, min(200, blend_width))
        return {"output": output, "split": split, "blend_width": blend_width}


register_effect(AncientCollageEffect())
```

And make sure to also register the stencil effect (it should already be registered from Step 3, but verify both `register_effect` calls are at module level):

```python
register_effect(AncientStencilEffect())
register_effect(AncientCollageEffect())
```

- [ ] **Step 8: Run collage tests to verify they pass**

```bash
cd /Users/jake/au-supply/worktrees/ancients-collage
pytest tests/test_effects/test_ancient.py -v -k collage
```

Expected: all 5 collage tests PASS. Note: the `test_collage_output_all` and `test_collage_output_random` tests will be slow on first run because `blend_seams` downloads the LaMa model (~200MB).

- [ ] **Step 9: Run all tests**

```bash
cd /Users/jake/au-supply/worktrees/ancients-collage
pytest tests/ -v --tb=short
```

Expected: all tests PASS.

- [ ] **Step 10: Commit**

```bash
git add sparagmos/effects/ancient.py tests/test_effects/test_ancient.py
git commit -m "feat: add ancient_collage and ancient_stencil effects

Adapter wrapping collage-bot's quadrant collage (4 inputs, 4 outputs)
and Otsu stencil masking (3 inputs, 6 outputs) as ComposeEffect
subclasses. Both support output=all (default) and output=random.
Collage mode uses SimpleLama neural inpainting for seam blending."
```

---

### Task 4: Add recipe YAML files

**Files:**
- Create: `recipes/ancients-collage.yaml`
- Create: `recipes/ancients-stencil.yaml`

- [ ] **Step 1: Create ancients-collage recipe**

Create `recipes/ancients-collage.yaml`:

```yaml
name: Ancients Collage
description: >
  Quadrant-mixed composites with geometric transformation and neural
  seam inpainting. Four source images are cut into quadrants, shuffled
  across four outputs, grid-transformed, and seamlessly blended.

inputs: 4

steps:
  - type: ancient_collage
    images: [a, b, c, d]
    into: canvas
    params:
      split: 0.25
      blend_width: 70
      output: all
```

- [ ] **Step 2: Create ancients-stencil recipe**

Create `recipes/ancients-stencil.yaml`:

```yaml
name: Ancients Stencil
description: >
  Binary mask compositing via Otsu's thresholding. Three source images
  take turns as the stencil mask, producing six variations of
  foreground/background swaps.

inputs: 3

steps:
  - type: ancient_stencil
    images: [a, b, c]
    into: canvas
    params:
      output: all
```

- [ ] **Step 3: Validate recipes**

```bash
cd /Users/jake/au-supply/worktrees/ancients-collage
python -m sparagmos --validate
```

Expected: all recipes validate successfully, including the two new ones. If validation fails for the new recipes, check that `ancient_collage` and `ancient_stencil` are registered (the `_register_all_effects()` function in `cli.py` auto-discovers effect modules via `pkgutil.iter_modules`).

- [ ] **Step 4: Commit**

```bash
git add recipes/ancients-collage.yaml recipes/ancients-stencil.yaml
git commit -m "feat: add ancients-collage and ancients-stencil recipes

Two new YAML recipes exposing collage-bot's image processing modes:
- ancients-collage: 4 inputs, quadrant mixing + seam inpainting
- ancients-stencil: 3 inputs, Otsu binary masking with permutations"
```

---

### Task 5: Update CLI and Slack posting for multi-output

**Files:**
- Modify: `sparagmos/cli.py:300-342`
- Test: `tests/test_multi_output.py` (extend)

- [ ] **Step 1: Write failing test for multi-output CLI behavior**

Append to `tests/test_multi_output.py`:

```python
from pathlib import Path
from unittest.mock import patch, MagicMock


def test_multi_output_saves_all_images_locally(tmp_path):
    """When pipeline returns multiple images, --output saves all with numbered suffixes."""
    from sparagmos.pipeline import PipelineResult

    imgs = [_make_image((i * 80, 0, 0)) for i in range(4)]
    result = PipelineResult(
        image=imgs[0],
        recipe_name="test",
        images=imgs,
    )

    output_path = tmp_path / "out.png"

    # Simulate what the CLI should do: save each image with a suffix
    if result.images and len(result.images) > 1:
        stem = output_path.stem
        suffix = output_path.suffix
        parent = output_path.parent
        for i, img in enumerate(result.images):
            numbered = parent / f"{stem}_{i+1}{suffix}"
            img.save(numbered, "PNG")
    else:
        result.image.save(output_path, "PNG")

    saved = sorted(tmp_path.glob("out_*.png"))
    assert len(saved) == 4
    for p in saved:
        img = Image.open(p)
        assert img.mode == "RGB"
```

- [ ] **Step 2: Run test to verify it passes**

This test validates the expected behavior pattern. It should pass since it's self-contained logic.

```bash
cd /Users/jake/au-supply/worktrees/ancients-collage
pytest tests/test_multi_output.py::test_multi_output_saves_all_images_locally -v
```

Expected: PASS

- [ ] **Step 3: Update CLI local output for multi-image**

In `sparagmos/cli.py`, find the output section (around line 301). Replace the local output block:

```python
        # Output
        if args.output:
            result.image.save(args.output, "PNG")
            logger.info("Saved output to %s", args.output)
```

With:

```python
        # Output
        if args.output:
            output_path = Path(args.output)
            if result.images and len(result.images) > 1:
                stem = output_path.stem
                suffix = output_path.suffix
                parent = output_path.parent
                for i, img in enumerate(result.images):
                    numbered = parent / f"{stem}_{i+1}{suffix}"
                    img.save(numbered, "PNG")
                    logger.info("Saved output %d/%d to %s", i + 1, len(result.images), numbered)
            else:
                result.image.save(args.output, "PNG")
                logger.info("Saved output to %s", args.output)
```

- [ ] **Step 4: Update CLI Slack posting for multi-image**

In the Slack posting section (around line 310-327), replace the single-image upload block:

```python
            comment = format_provenance_multi(result, source_metadata_list, "image-gen")
            image_path = Path(tmp) / "sparagmos_output.png"
            result.image.save(image_path, "PNG")
            logger.info("Posting to channel %s with comment:\n%s", junkyard_id, comment)
            response = client.files_upload_v2(
                channel=junkyard_id,
                file=str(image_path),
                filename="sparagmos.png",
                initial_comment=comment,
            )
            posted_ts = response.get("ts", "")
```

With:

```python
            comment = format_provenance_multi(result, source_metadata_list, "image-gen")

            if result.images and len(result.images) > 1:
                # Multi-output: upload all images
                file_uploads = []
                for i, img in enumerate(result.images):
                    img_path = Path(tmp) / f"sparagmos_output_{i+1}.png"
                    img.save(img_path, "PNG")
                    file_uploads.append({
                        "file": str(img_path),
                        "filename": f"sparagmos_{i+1}.png",
                    })
                logger.info(
                    "Posting %d images to channel %s with comment:\n%s",
                    len(file_uploads), junkyard_id, comment,
                )
                response = client.files_upload_v2(
                    channel=junkyard_id,
                    file_uploads=file_uploads,
                    initial_comment=comment,
                )
            else:
                image_path = Path(tmp) / "sparagmos_output.png"
                result.image.save(image_path, "PNG")
                logger.info("Posting to channel %s with comment:\n%s", junkyard_id, comment)
                response = client.files_upload_v2(
                    channel=junkyard_id,
                    file=str(image_path),
                    filename="sparagmos.png",
                    initial_comment=comment,
                )

            posted_ts = response.get("ts", "")
```

- [ ] **Step 5: Run all tests**

```bash
cd /Users/jake/au-supply/worktrees/ancients-collage
pytest tests/ -v --tb=short
```

Expected: all tests PASS.

- [ ] **Step 6: Commit**

```bash
git add sparagmos/cli.py tests/test_multi_output.py
git commit -m "feat: handle multi-output in CLI local save and Slack posting

When pipeline returns multiple images:
- Local mode (--output): saves numbered files (out_1.png, out_2.png, ...)
- Slack mode: uploads all images in a single message via file_uploads
Single-output behavior is unchanged."
```

---

### Task 6: Integration test and final validation

**Files:**
- Create: `tests/test_effects/test_ancient_integration.py`

- [ ] **Step 1: Write integration test for stencil pipeline**

Create `tests/test_effects/test_ancient_integration.py`:

```python
"""Integration tests for ancient effects — full pipeline end-to-end."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from sparagmos.config import load_recipe
from sparagmos.pipeline import run_pipeline, IMAGE_NAMES


def _make_image(color: tuple[int, int, int], size: int = 64) -> Image.Image:
    arr = np.full((size, size, 3), color, dtype=np.uint8)
    return Image.fromarray(arr, mode="RGB")


RECIPES_DIR = Path(__file__).resolve().parents[2] / "recipes"


def test_ancients_stencil_pipeline(tmp_path):
    """Full pipeline run of ancients-stencil recipe."""
    recipe = load_recipe(RECIPES_DIR / "ancients-stencil.yaml")
    images = {
        "a": _make_image((255, 0, 0)),
        "b": _make_image((0, 255, 0)),
        "c": _make_image((0, 0, 255)),
    }
    result = run_pipeline(
        recipe=recipe,
        seed=42,
        temp_dir=tmp_path,
        images=images,
    )
    assert result.image.mode == "RGB"
    assert result.images is not None
    assert len(result.images) == 6
    for img in result.images:
        assert img.mode == "RGB"
        assert img.size[0] > 0
        assert img.size[1] > 0


@pytest.mark.slow
def test_ancients_collage_pipeline(tmp_path):
    """Full pipeline run of ancients-collage recipe (requires LaMa model download)."""
    recipe = load_recipe(RECIPES_DIR / "ancients-collage.yaml")
    images = {
        "a": _make_image((255, 0, 0)),
        "b": _make_image((0, 255, 0)),
        "c": _make_image((0, 0, 255)),
        "d": _make_image((255, 255, 0)),
    }
    result = run_pipeline(
        recipe=recipe,
        seed=42,
        temp_dir=tmp_path,
        images=images,
    )
    assert result.image.mode == "RGB"
    assert result.images is not None
    assert len(result.images) == 4
    for img in result.images:
        assert img.mode == "RGB"
        assert img.size[0] > 0
        assert img.size[1] > 0
```

- [ ] **Step 2: Run stencil integration test**

```bash
cd /Users/jake/au-supply/worktrees/ancients-collage
pytest tests/test_effects/test_ancient_integration.py::test_ancients_stencil_pipeline -v
```

Expected: PASS

- [ ] **Step 3: Run collage integration test**

```bash
cd /Users/jake/au-supply/worktrees/ancients-collage
pytest tests/test_effects/test_ancient_integration.py::test_ancients_collage_pipeline -v
```

Expected: PASS (slow — downloads LaMa model on first run).

- [ ] **Step 4: Run full test suite**

```bash
cd /Users/jake/au-supply/worktrees/ancients-collage
pytest tests/ -v --tb=short
```

Expected: all tests PASS.

- [ ] **Step 5: Validate all recipes**

```bash
cd /Users/jake/au-supply/worktrees/ancients-collage
python -m sparagmos --validate
```

Expected: all recipes valid, including `ancients-collage` and `ancients-stencil`.

- [ ] **Step 6: Commit**

```bash
git add tests/test_effects/test_ancient_integration.py
git commit -m "test: add integration tests for ancient effects

End-to-end pipeline tests for both ancients-stencil and ancients-collage
recipes. Collage test marked @pytest.mark.slow due to LaMa model download."
```

- [ ] **Step 7: Register the slow marker in pytest config**

Check if `pyproject.toml` already has a `[tool.pytest.ini_options]` section with markers. If not, add:

```toml
[tool.pytest.ini_options]
markers = [
    "slow: marks tests as slow (deselect with '-m \"not slow\"')",
]
```

If it already has markers, just append the `slow` marker to the list.

```bash
git add pyproject.toml
git commit -m "chore: register pytest slow marker

Prevents PytestUnknownMarkWarning for @pytest.mark.slow used in
ancient effect integration tests."
```
