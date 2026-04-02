# Ancients Collage Integration Design

**Date:** 2026-04-02
**Status:** Approved
**Source repo:** https://github.com/A-U-Supply/collage-bot

## Overview

Integrate the A-U-Supply/collage-bot repository into sparagmos as vendored
code, exposing its image processing pipelines as first-class sparagmos effects
with standard YAML recipes.

The collage-bot has two modes:

- **Collage**: Takes 4 images, cuts each into quadrants, mixes them across 4
  output composites, applies a geometric grid transform, and uses SimpleLama
  neural inpainting to blend the seams. Outputs 4 composites.
- **Stencil**: Takes 3 images, converts each to a binary mask via Otsu's
  thresholding, composites the other two through the mask. Generates 6
  variations by swapping mask/foreground/background assignments.

Each mode becomes a separate recipe (`ancients-collage`, `ancients-stencil`).
New modes added to collage-bot in the future require only a small adapter
entry and a new recipe YAML.

## Vendoring Strategy

Use `git subtree` to pull collage-bot into `sparagmos/vendor/collage_bot/`
(underscore, not hyphen, so Python can import it):

```bash
git subtree add --prefix sparagmos/vendor/collage_bot \
    https://github.com/A-U-Supply/collage-bot.git main --squash
```

Updates:

```bash
git subtree pull --prefix sparagmos/vendor/collage_bot \
    https://github.com/A-U-Supply/collage-bot.git main --squash
```

A `PROVENANCE.md` in `sparagmos/vendor/collage_bot/` documents:
- Source URL and branch
- Commit hash at time of vendoring
- Date vendored
- Original license

New dependency `simple-lama-inpainting` and `numpy<2` constraint added to
`requirements.txt`.

## Effect Adapter

A new file `sparagmos/effects/ancient.py` wraps the collage-bot transforms as
sparagmos ComposeEffect subclasses.

### AncientCollageEffect

- **Name:** `ancient_collage`
- **Inputs:** 4 images (from the named register: a, b, c, d)
- **Pipeline:** `cut_quadrants()` -> `make_composites()` -> `apply_transform()` -> `blend_seams()` on each composite
- **Params:**
  - `split` (float, default 0.25) — grid split ratio
  - `blend_width` (int, default 70) — seam inpainting strip width in pixels
  - `output` (`all` | `random`, default `all`) — emit all composites or pick one
- **Returns:** 4 composite images when `output: all`, 1 when `output: random`

### AncientStencilEffect

- **Name:** `ancient_stencil`
- **Inputs:** 3 images (from the named register: a, b, c)
- **Pipeline:** `make_stencil()` on each image, then `apply_stencil()` for all permutations
- **Params:**
  - `output` (`all` | `random`, default `all`) — emit all variations or pick one
- **Returns:** 6 variations when `output: all`, 1 when `output: random`

### Import Path

The `git subtree add` uses underscore prefix (`sparagmos/vendor/collage_bot/`)
so Python can import it directly. An `__init__.py` is added to
`sparagmos/vendor/` to make it a package (if not already present).

```python
from sparagmos.vendor.collage_bot.transform import (
    cut_quadrants, make_composites, apply_transform, blend_seams,
)
from sparagmos.vendor.collage_bot.stencil_transform import (
    make_stencil, apply_stencil,
)
```

## Multi-Output Pipeline Support

The current pipeline returns a single `PipelineResult.image`. To support
multi-output effects:

- Add optional `images: list[Image.Image] | None` field to `EffectResult`
- Add optional `images: list[Image.Image] | None` field to `PipelineResult`
- Pipeline checks if the final step's result has `.images` set; if so,
  populates `PipelineResult.images` (and sets `.image` to the first one for
  backward compat)
- CLI/Slack posting code checks for `pipeline_result.images` and posts all
- Mid-pipeline, if a multi-output effect isn't the last step, only `.image`
  (the first) feeds forward — multi-output is a terminal behavior

## Recipe YAML Files

### recipes/ancients-collage.yaml

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

### recipes/ancients-stencil.yaml

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

Both are standalone single-step pipelines but can be chained with other
effects in custom recipes (e.g. `ancient_collage` -> `pixel_sort` ->
`jpeg_destroy`). When chained, only `.image` (the first composite) feeds
forward to subsequent steps.

## Adding New Modes

When a new mode is added to collage-bot (e.g. `kaleidoscope_transform.py`):

1. `git subtree pull` to update the vendored code
2. Add a new `ComposeEffect` subclass in `sparagmos/effects/ancient.py`
   (~20-30 lines): import the transform functions, set the name
   (`ancient_kaleidoscope`), input count, and params, wire `compose()` to call
   the transform functions
3. Add a new recipe YAML (`recipes/ancients-kaleidoscope.yaml`)

Two files touched, one new file. No changes to pipeline, CLI, or Slack posting.

## Testing

### Unit Tests (`tests/test_ancient.py`)

- `AncientCollageEffect.compose()` with 4 synthetic images: verify 4 outputs
  with `output: all`, 1 with `output: random`
- `AncientStencilEffect.compose()` with 3 synthetic images: verify 6 outputs
  with `output: all`, 1 with `output: random`
- `validate_params()` for both effects: defaults, bounds, invalid values

### Recipe Validation

The existing `python -m sparagmos --validate` CI step catches YAML/schema
errors in the new recipes automatically.

### Integration Tests

Run each recipe end-to-end with synthetic solid-color images to confirm the
full pipeline (including SimpleLama seam blending) works without error. Marked
with `@pytest.mark.slow` since the lama model download takes time on first
run.
