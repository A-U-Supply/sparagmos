# Sparagmos Multi-Input Compositing — Design Spec

**Date:** 2026-03-26
**Repo:** `~/au-supply/sparagmos`
**Status:** Approved, ready for implementation

## Problem

Single-image destruction is boring. One image through an effect chain produces predictable results. The interesting results come from unexpected combinations — multiple sources collaged, masked, layered, and then destroyed together.

## Solution

Upgrade the pipeline from single-image linear processing to a **named-image register model**. Recipes specify 2-5 input images. Each step operates on named images — processing them independently, compositing them together, destroying the composites, and optionally re-compositing. The pipeline maintains a `dict[str, Image]` instead of a single `current_image`.

## Architecture: Named-Image Registers

### Pipeline Engine

The pipeline maintains a dict of named images. Each recipe step specifies which image(s) it reads and writes.

```python
# pipeline.py — core loop
images: dict[str, Image.Image] = {}

# Load input images
if recipe.inputs == 1:
    images["canvas"] = primary.convert("RGB")
else:
    for name, img in zip(IMAGE_NAMES, input_images):
        images[name] = img.convert("RGB")

# Execute steps
for step in recipe.steps:
    effect = get_effect(step.type)
    resolved = resolve_params(step.params, seed=seed + i)

    if step.images:  # compositing step
        source_imgs = [images[name] for name in step.images]
        result = effect.compose(source_imgs, resolved, context)
        images[step.into] = result.image
    else:  # single-image step
        target = step.image or "canvas"
        result = effect.apply(images[target], resolved, context)
        images[target] = result.image

# Output is always "canvas"
return images["canvas"]
```

### Input Image Naming

- 1 input: loaded as `canvas`
- 2 inputs: loaded as `a`, `b`
- 3 inputs: `a`, `b`, `c`
- 4 inputs: `a`, `b`, `c`, `d`
- 5 inputs: `a`, `b`, `c`, `d`, `e`

For multi-input recipes, no image starts as `canvas` — a compositing step must create it. This forces recipes to be explicit about how images combine.

### Recipe Schema

```yaml
name: Human-Readable Name
description: >
  Multi-line description.

inputs: 3              # How many images to fetch (1-5, defaults to 1)
vision: false          # Optional, defaults to false

steps:                 # Replaces "effects:" (which is accepted as alias)
  # Single-image effect
  - type: effect_name
    image: a                    # Which named image to process (defaults to "canvas")
    params:
      param_name: value
      param_name: [min, max]

  # Compositing effect
  - type: compose_effect_name
    images: [a, b]              # Multiple input images
    into: canvas                # Output name
    params:
      param_name: value
```

### Backward Compatibility

Existing single-input recipes work unchanged:
- `inputs` defaults to 1 → single input loaded as `canvas`
- `effects:` accepted as alias for `steps:`
- `image` defaults to `canvas` on every step
- No `images:`/`into:` fields → all steps are single-image
- Zero migration required

### Effect Interface

Existing `Effect` base class is unchanged. New `ComposeEffect` subclass:

```python
class ComposeEffect(Effect):
    """Base class for effects that combine multiple images."""

    @abstractmethod
    def compose(
        self, images: list[Image.Image], params: dict, context: EffectContext
    ) -> EffectResult:
        """Combine multiple images into one."""

    def apply(self, image, params, context):
        return self.compose([image], params, context)
```

### RecipeStep Changes

```python
@dataclass
class RecipeStep:
    type: str
    params: dict[str, Any] = field(default_factory=dict)
    image: str | None = None       # NEW — target for single-image effects
    images: list[str] | None = None  # NEW — sources for compositing effects
    into: str | None = None        # NEW — output name for compositing effects
```

## Compositing Effects

Four new `ComposeEffect` subclasses.

### 1. `collage` — Spatial arrangement

Place multiple images onto a shared canvas.

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `layout` | string | `grid` | `grid`, `scatter`, `strips`, `mosaic` |
| `overlap` | float | 0.0 | [0.0, 0.5] — how much pieces overlap |
| `rotation` | int | 0 | [0, 360] — max random rotation per piece |
| `scale_variance` | float | 0.0 | [0.0, 1.0] — how much piece sizes vary |
| `canvas_size` | string | `largest` | `largest`, `smallest`, `fixed_1024` |

Layouts:
- `grid` — Even tile grid, randomized piece assignment
- `scatter` — Random position/rotation/scale, overlapping layers
- `strips` — Alternate horizontal or vertical strips from each source
- `mosaic` — Random-sized rectangles, each filled from a different source

### 2. `blend` — Pixel-level blending

Combine exactly two images through blend modes.

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `mode` | string | `opacity` | `opacity`, `multiply`, `screen`, `overlay`, `difference`, `add`, `subtract` |
| `strength` | float | 0.5 | [0.0, 1.0] — blend strength |
| `offset_x` | float | 0.0 | [-0.5, 0.5] — horizontal offset as fraction of width |
| `offset_y` | float | 0.0 | [-0.5, 0.5] — vertical offset as fraction of height |

Takes exactly 2 images (validated at recipe load time). Images resized to match dimensions before blending. Offset allows misalignment.

### 3. `mask_composite` — Mask-based selection

Use derived features from one image as a mask to select between two images.

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `mask_source` | string | `luminance` | `luminance`, `edges`, `threshold`, `noise`, `gradient` |
| `threshold` | int | 128 | [0, 255] — cutoff for binary mask |
| `feather` | int | 0 | [0, 50] — Gaussian blur radius on mask |
| `invert` | bool | false | Flip which image shows through |

Takes exactly 2 images (validated at recipe load time). First image's features become the mask; mask selects between first and second image.

Mask sources:
- `luminance` — grayscale conversion, threshold to binary
- `edges` — Canny edge detection on first image, edges reveal second
- `threshold` — hard threshold on brightness
- `noise` — random noise mask (ignores first image's content)
- `gradient` — linear gradient mask (ignores first image's content)

### 4. `fragment` — Cut and reassemble

Slice images into pieces, rebuild from mixed sources.

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `cut_mode` | string | `grid` | `grid`, `voronoi`, `strips`, `shatter` |
| `pieces` | int | 16 | [4, 64] — number of pieces/cells |
| `mix_ratio` | float | 0.5 | [0.0, 1.0] — randomness of source assignment |
| `gap` | int | 0 | [0, 10] — pixel gap between fragments |

Cut modes:
- `grid` — regular rectangular grid
- `voronoi` — Voronoi diagram from random seed points
- `strips` — horizontal or vertical strips of varying width
- `shatter` — irregular random polygons (broken glass look)

## Slack Source Changes

### Fetching multiple images

New function:

```python
def pick_random_images(
    files: list[dict],
    recipe_slug: str,
    n: int,
    processed_combos: set[frozenset],
    seed: int,
) -> list[dict]:
    """Pick n distinct random images whose combination hasn't been used with this recipe."""
```

- All N images must be distinct file IDs
- The combination `(frozenset(file_ids), recipe)` is checked against state
- Same image can appear in different runs with different partners
- Exhaustion: when no new combinations exist, reset (same as current behavior)

Existing `pick_random_image()` (singular) stays for single-input recipes.

### Provenance formatting

Multi-input format:

```
~ Voronoi Chimera
deepdream(a) → dither(b) → fragment(a,b→canvas) → jpeg_destroy(canvas)
sources: @user1 (2025-01-15), @user2 (2025-02-20), @user3 (2025-03-01) in #image-gen
originals: <link1> · <link2> · <link3>
```

Effect chain line includes image annotations showing what flowed where.

## State Tracking Changes

### ProcessedEntry

```python
@dataclass
class ProcessedEntry:
    source_file_ids: list[str]     # was: source_file_id (str)
    source_dates: list[str]        # was: source_date (str)
    source_users: list[str]        # was: source_user (str)
    recipe: str
    effects: list[str]
    processed_date: str
    posted_ts: str
```

Deduplication key: `(frozenset(file_ids), recipe)` — order doesn't matter.

Backward compat: on load, old entries with singular `source_file_id` get wrapped in a one-element list. No migration needed.

## CLI Changes

`--input` accepts multiple files:

```
python -m sparagmos --input a.jpg b.jpg c.jpg --output junked.png
python -m sparagmos --input a.jpg b.jpg --recipe some-multi-recipe
```

- If recipe specifies `inputs: 3` but 2 files are passed, error
- If no `--recipe`, random selection filtered to recipes with matching `inputs:` count
- When fetching from Slack (no `--input`), the recipe's `inputs:` field determines how many images to fetch

## New Recipe Set

All 12 existing single-input recipes are replaced. Every new recipe uses 2-5 inputs with compositing.

### 1. voronoi-chimera (3 inputs)
Faces and forms fused at Voronoi cell boundaries. Pre-process each image with different neural/glitch effects, fragment together via Voronoi tessellation, blend overlay, then destroy with channel shift and JPEG compression.

### 2. palimpsest (4 inputs)
A manuscript overwritten and overwritten again — each layer bleeding through. Chain mask_composite three times, each masking with luminance at different thresholds, producing a layered palimpsest. Destroy with byte corruption and dithering.

### 3. exquisite-corpse (3 inputs)
The surrealist parlor game. Fragment into horizontal strips — head from one source, torso from another, legs from a third. Pre-process with pixel sort and CRT effects. Final destruction via seam carve and JPEG.

### 4. double-exposure (2 inputs)
Two images burned onto the same film. Blend with screen mode, then re-blend with multiply for contrast. Sonify the result, then JPEG destroy. Classic photographic accident, digitally decayed.

### 5. signal-bleed (3 inputs)
Three VHS signals bleeding into each other on a bad splitter. Apply CRT/VHS effects to each independently, collage as vertical strips, then channel shift and byte corrupt the composite.

### 6. tectonic-overlap (4 inputs)
Continental plates of image data, shifted and overlapping. Fragment with shatter mode, scatter-collage the pieces, seam carve to warp the seams, JPEG destroy to compress the geological record.

### 7. edge-ghosts (3 inputs)
Phantom outlines from one image haunting another. Apply mask_composite with edges mode twice in sequence — each source contributing ghost outlines to the composite. Spectral processing and channel shift for final ethereal destruction.

### 8. neural-chimera (3 inputs)
Three images deepdreamed with different neural layers, then Voronoi-fragmented together and blended. Style transfer on the composite, then JPEG destruction. Hallucinated parts fused into a hallucinated whole.

### 9. spectral-merge (2 inputs)
Two signals in frequency space, destructively interfered. Spectral-process each image differently, blend with difference mode, mask_composite to select the most extreme frequencies. Dither to quantize the result.

### 10. mosaic-dissolution (5 inputs)
Five sources tiled into a mosaic, then the mosaic itself is fragmented and pixel-sorted into dust. Maximum input count, maximum chaos. Collage as mosaic, fragment the mosaic, pixel sort, JPEG destroy, byte corrupt.

### 11. fossil-record (3 inputs)
Geological strata. PCA decompose each image to different component counts (deep/shallow reconstruction), blend as opacity layers, dither to quantize into rock-like bands, channel shift for mineral color.

### 12. feedback-loop (2 inputs)
Compose, destroy, re-compose the wreckage, destroy again. Blend two images, apply ImageMagick distortion, fragment the result back with the original images, channel shift, JPEG destroy. The output feeds conceptually back into itself.

## Documentation

### README.md
Rewrite to reflect multi-input architecture:
- Updated overview explaining multi-input compositing
- New effects table with compositing effects section
- Updated quickstart showing multi-input CLI usage (`--input a.jpg b.jpg c.jpg`)
- Updated architecture section with named-image register model

### docs/effects.md
Add compositing effects section:
- Full parameter reference for collage, blend, mask_composite, fragment
- All mode descriptions with examples
- Existing effect docs unchanged

### docs/recipes.md
Rewrite for new schema:
- Updated recipe schema: `inputs:`, `steps:`, `image:`, `images:`, `into:`
- Explanation of named-image model and image naming convention
- Example recipes with commentary on image flow
- Tips on multi-input recipe design
- Backward compatibility notes

### recipes/README.md
Updated recipes directory guide with new recipe descriptions.

## Testing

**All testing via GitHub Actions — no local runs.**

### New test files

| Test file | Covers |
|-----------|--------|
| `tests/test_effects/test_collage.py` | All 4 layout modes, 1-5 images, mismatched sizes |
| `tests/test_effects/test_blend.py` | All 7 blend modes, offset, strength range |
| `tests/test_effects/test_mask_composite.py` | All 5 mask sources, feather, invert |
| `tests/test_effects/test_fragment.py` | All 4 cut modes, piece counts, mix ratios |

### Extended test files

| Test file | New coverage |
|-----------|-------------|
| `tests/test_pipeline.py` | Multi-image pipeline, named image routing, canvas output |
| `tests/test_config.py` | `inputs:`, `steps:` vs `effects:`, `image:`/`images:`/`into:` validation |
| `tests/test_recipes.py` | Validate all 12 new recipes |
| `tests/test_state.py` | Multi-source entries, backward compat with old single-source entries |
| `tests/test_slack.py` | `pick_random_images()` (plural), multi-source provenance formatting |
| `tests/test_integration.py` | End-to-end: each new recipe on test fixture images |

### CI workflow

Existing `.github/workflows/` test workflow runs pytest with all system deps installed. No workflow changes needed.
