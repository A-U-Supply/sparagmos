# Effects Reference

## Effect Interface

Every effect implements the same contract:

```python
class Effect(ABC):
    name: str                    # e.g. "pixel_sort"
    description: str             # Human-readable, used in Slack posts
    requires: list[str]          # System deps: ["imagemagick"], ["netpbm"], []

    def apply(self, image: Image, params: dict,
              context: EffectContext) -> EffectResult:
        """
        image:   PIL.Image (RGB/RGBA)
        params:  Resolved recipe params (ranges already rolled)
        context: Vision analysis, temp dir, RNG seed, source metadata
        Returns: EffectResult(image=PIL.Image, metadata=dict)
        """

    def validate_params(self, params: dict) -> dict:
        """Validate and normalize params. Raise ConfigError on bad input."""
```

### EffectContext

Carries shared state through the pipeline:
- `vision`: Llama Vision analysis results (dict or None)
- `temp_dir`: Path for temporary files (subprocess effects)
- `seed`: RNG seed for reproducibility
- `source_metadata`: Source image metadata

### EffectResult

- `image`: Processed PIL Image
- `metadata`: Dict of actual params used, intermediate values for provenance logging

### SubprocessEffect

Base class for effects that shell out to external tools. Provides:
- `run_command(cmd, context, timeout)` — run subprocess with timeout
- `save_temp_image(image, context, suffix)` — save to temp file
- `load_temp_image(path)` — load from temp file

## Adding a New Effect

### 1. Create the module

```python
# sparagmos/effects/my_effect.py
from sparagmos.effects import Effect, EffectContext, EffectResult, ConfigError, register_effect

class MyEffect(Effect):
    name = "my_effect"
    description = "What this effect does"
    requires: list[str] = []  # e.g. ["imagemagick"] for system deps

    def apply(self, image, params, context):
        params = self.validate_params(params)
        # ... transform image ...
        return EffectResult(image=result_image, metadata={"key": "value"})

    def validate_params(self, params):
        my_param = params.get("my_param", 10)
        my_param = max(1, min(100, int(my_param)))
        return {"my_param": my_param}

register_effect(MyEffect())
```

### 2. Write tests

```python
# tests/test_effects/test_my_effect.py
from sparagmos.effects import EffectContext, register_effect
from sparagmos.effects.my_effect import MyEffect

def test_apply_produces_valid_image(test_image_rgb, tmp_path):
    effect = MyEffect()
    ctx = EffectContext(vision=None, temp_dir=tmp_path, seed=42, source_metadata={})
    result = effect.apply(test_image_rgb, {}, ctx)
    assert result.image.size == test_image_rgb.size
```

### 3. Use in recipes

```yaml
effects:
  - type: my_effect
    params:
      my_param: [5, 15]
```

The effect is auto-discovered by the CLI's `_register_all_effects()` function — no manual registration needed beyond the `register_effect()` call at module level.

## Effects by Category

### Pure Python — Pixel Manipulation

**byte_corrupt** — Raw byte manipulation on pixel data. XOR, inject, or replace random bytes. Produces glitch artifacts: color inversions, shifted rows, corrupted regions. The `skip_header` param protects image structure while corrupting content.

**channel_shift** — Offsets RGB channels independently along the horizontal axis. Creates chromatic aberration — the hallmark of analog video decay. Simple but effective, especially when combined with scan line effects.

**pixel_sort** — Sorts pixel rows or columns by brightness, hue, or saturation within threshold bounds. Pixels outside the threshold range act as segment boundaries. Creates the distinctive "melting" effect popularized by Kim Asendorf.

**dither** — Reduces color palette using quantization. Built-in retro palettes: CGA (4 colors), EGA (16), Game Boy (4 greens), thermal imaging (orange-white). Maps high-color images to severely limited palettes.

**jpeg_destroy** — Multi-generation JPEG compression. Save at very low quality, reopen, repeat. Each cycle amplifies compression artifacts — blocking, ringing, color shift. The digital equivalent of photocopying a photocopy.

### Pure Python — Simulation

**crt_vhs** — Composite CRT/VHS simulation. Horizontal scan line darkening, random row jitter (tracking errors), chroma blur (color bleeding from analog signal degradation), phosphor glow (bloom from CRT phosphors).

**cellular** — Cellular automata on pixel data. Thresholds image to binary, runs Game of Life (2D) or Rule 110 (1D) for N generations. The evolution of cells maps back to pixel brightness, creating organic growth/decay patterns.

**pca_decompose** — PCA/SVD reconstruction using only top or bottom N components. "Top" mode keeps dominant structure (ghostly, smooth). "Bottom" mode keeps only noise and texture (abstract, impressionist). Reconstruction from limited eigenvalues.

**fractal_blend** — Generates Mandelbrot set at coordinates derived from the image's own histogram (mean hue → real axis, mean brightness → imaginary axis). Each image navigates to a unique location in the fractal. Blended with original at configurable opacity.

**seam_carve** — Content-aware resize via dynamic programming seam removal. Intentionally misconfigured for destruction: too many seams removed, wrong regions protected, inverted energy maps. Melts faces, bends buildings.

**sonify** — Treats pixel data as 16-bit PCM audio samples. Applies DSP effects (reverb, echo, distortion, phaser) to the "audio," then converts back to image. Cross-domain corruption.

**spectral** — 2D FFT on image channels. Manipulates frequency spectrum (shift, bandpass, blur) then inverse FFT back to spatial domain. Operates on image as a 2D signal.

**datamosh** — Simulates video datamosh artifacts (I-frame removal, motion vector corruption). Shifts image blocks as if they were predicted from wrong reference frames. Creates the characteristic "smearing" of corrupted video.

### Subprocess — External Tools

**imagemagick** — Wraps ImageMagick's `convert` with named presets: implode (pinch effect), swirl (rotation), wave (sinusoidal distortion), plasma overlay, noise injection via `-fx`. Requires ImageMagick installed.

**netpbm** — Wraps ancient Unix NetPBM tools (circa 1988). pgmcrater generates lunar crater textures, ppmspread scatters pixels, pgmbentley creates snowflake patterns. Requires NetPBM installed.

**format_roundtrip** — Chains of lossy format conversions. JPEG → BMP → JPEG loses precision at each step. Potrace chain: raster → bitmap → vector trace → raster introduces dramatic simplification. Requires potrace for vector chain.

**primitive** — Wraps the `primitive` Go binary. Reconstructs image using geometric shapes (triangles, rectangles, ellipses, circles). Low iteration counts produce abstract, painterly results. Requires primitive installed.

### Neural / AI

**deepdream** — Amplifies patterns detected by InceptionV3 neural network. Multi-octave processing at different scales. Produces the characteristic "dog-slug" hallucinations. Requires PyTorch.

**style_transfer** — Gatys neural style transfer using VGG19. When using "self" as style source (input image is both content and style), produces weird recursive self-enhancement. Requires PyTorch.

**pix2pix** — Simulates CycleGAN domain transfer artifacts. Edge-aware pattern generation mimics the characteristic checkerboard artifacts and color bleeding of pix2pix models.

**neural_doodle** — Simulated semantic style painting. Random geometric regions get different color/texture treatments, mimicking how neural doodle fills semantic regions with learned styles.

**inpaint** — Masks regions and regenerates using OpenCV's PatchMatch or Telea inpainting. Random or vision-targeted masking creates surreal smooth patches in otherwise detailed images.

## Compositing Effects

These effects take **multiple named images** as input. In multi-input recipes, each step specifies an `images:` list (source names) and an `into:` name for the output. See [recipes.md](recipes.md) for the named-image model.

**collage** — Spatial arrangement of multiple images on a canvas. Images are placed according to a layout algorithm; they can overlap, rotate, and scale independently.

| Param | Description |
|-------|-------------|
| `layout` | Arrangement algorithm: `grid`, `scatter`, `strips`, `mosaic` |
| `overlap` | Fraction of image area that may overlap adjacent placements (0.0–1.0) |
| `rotation` | Max random rotation per image in degrees |
| `scale_variance` | How much images may vary in size relative to each other (0.0–1.0) |
| `canvas_size` | Output dimensions as `[width, height]`; defaults to largest input size |

**blend** — Pixel-level blending of two images. The first image in `images:` is treated as the base; the second is composited over it at the given `strength`.

| Param | Description |
|-------|-------------|
| `mode` | Blend algorithm: `opacity`, `multiply`, `screen`, `overlay`, `difference`, `add`, `subtract` |
| `strength` | Blend opacity (0.0–1.0); how much of the second image is mixed in |
| `offset_x` | Horizontal pixel offset of the top layer |
| `offset_y` | Vertical pixel offset of the top layer |

**mask_composite** — Selects between two images pixel-by-pixel using a computed mask. Where the mask is white, the second image shows; where black, the first. The mask is derived from one of the input images.

| Param | Description |
|-------|-------------|
| `mask_source` | What drives the mask: `luminance`, `edges`, `threshold`, `noise`, `gradient` |
| `threshold` | Cutoff value for binary mask generation (0–255) |
| `feather` | Gaussian blur radius applied to the mask for soft edges |
| `invert` | If true, swap which image shows through the mask |

**fragment** — Cuts images into pieces and reassembles them from mixed sources. Each piece is filled from one of the input images according to `mix_ratio`.

| Param | Description |
|-------|-------------|
| `cut_mode` | How the canvas is divided: `grid`, `voronoi`, `strips`, `shatter` |
| `pieces` | Number of fragments (int or `[min, max]` range) |
| `mix_ratio` | Fraction of pieces drawn from the primary vs. secondary sources (0.0–1.0) |
| `gap` | Gap in pixels between fragments (0 = flush) |

**ancient_collage** — Quadrant-mixed composites with geometric transformation and neural seam inpainting. Takes 4 images, cuts each into quadrants, shuffles them across 4 output composites, applies a grid transform, and uses LaMa inpainting to blend seams. Multi-output: produces 4 images. Vendored from [A-U-Supply/collage-bot](https://github.com/A-U-Supply/collage-bot).

| Param | Description |
|-------|-------------|
| `split` | Grid split ratio (0.05–0.45, default 0.25) |
| `blend_width` | Seam inpainting strip width in pixels (1–200, default 70) |
| `output` | `all` (default, 4 composites) or `random` (pick 1) |

**ancient_stencil** — Binary mask compositing via Otsu's thresholding. Takes 3 images; each takes a turn as the stencil mask, producing 6 variations by swapping foreground/background assignments. Multi-output: produces 6 images. Vendored from [A-U-Supply/collage-bot](https://github.com/A-U-Supply/collage-bot).

| Param | Description |
|-------|-------------|
| `output` | `all` (default, 6 variations) or `random` (pick 1) |

### Stencil Mask Variants (3 inputs)

All vendored from [A-U-Supply/collage-bot](https://github.com/A-U-Supply/collage-bot). Same permutation pattern as `ancient_stencil` but with different mask generation.

**ancient_halftone** — AM halftone dot screen as stencil mask. Cosine dot grid where dot size varies with tone.

| Param | Description |
|-------|-------------|
| `frequency` | Dot spacing in pixels (4–60, default 14) |
| `angle` | Screen rotation in degrees (default 45) |
| `output` | `all` or `random` |

**ancient_linescreen** — Fixed-angle parallel line screen stencil. Line width varies with tone — thick in shadows, thin in highlights.

| Param | Description |
|-------|-------------|
| `frequency` | Line spacing in pixels (8–80, default 30) |
| `angle` | Line angle in degrees (default 0) |
| `output` | `all` or `random` |

**ancient_curvylinescreen** — Edge-following line screen. Lines curve along image contours using gradient direction field with double-angle smoothing. Falls back to default angle in flat regions.

| Param | Description |
|-------|-------------|
| `frequency` | Line spacing in pixels (8–80, default 30) |
| `angle` | Fallback angle in degrees (default 45) |
| `output` | `all` or `random` |

**ancient_reducedlinescreen** — Adaptive-frequency horizontal line screen. Finer lines in edge/text regions (Laplacian-detected), coarser in flat areas. Phase integrates continuously.

| Param | Description |
|-------|-------------|
| `frequency` | Coarse line spacing in pixels (8–80, default 30) |
| `freq_fine` | Fine line spacing for detail regions (4–freq-1, default 12) |
| `output` | `all` or `random` |

### Tonal Treatment + Stencil (3 inputs)

**ancient_cyanotype** — Prussian blue cyanotype treatment on fills before Otsu stencil compositing. Tonal curve + highlight bloom + blue LUT + paper grain.

| Param | Description |
|-------|-------------|
| `output` | `all` or `random` |

**ancient_silver** — Silver gelatin print treatment on fills before Otsu stencil compositing. Tonal curve + halation + film grain + cool blue-grey tint.

| Param | Description |
|-------|-------------|
| `output` | `all` or `random` |

### Edge / Displacement Stencil (3 inputs)

**ancient_halationedge** — Stencil with organic grain at edge boundaries. The hard binary edge is replaced with halftone noise in the transition zone. Double edge bands (bright/dark) baked into mask before compositing.

| Param | Description |
|-------|-------------|
| `width` | Edge zone width in pixels (2–40, default 10) |
| `output` | `all` or `random` |

**ancient_displacement** — Gradient-based displacement warps both the stencil boundary and fill images. The stencil boundary tears and fills stretch near the seam, fading over a configurable falloff distance.

| Param | Description |
|-------|-------------|
| `strength` | Max displacement in pixels (20–600, default 200) |
| `blur` | Gradient smoothing sigma (0.5–20, default 3) |
| `fill_falloff` | Gaussian falloff distance in pixels (50–2000, default 600) |
| `output` | `all` or `random` |

### 3-Level Stencil (4 inputs)

**ancient_quad** — Splits stencil image into three brightness bands by percentile thresholding (black/grey/white) and fills each zone with a different source image.

| Param | Description |
|-------|-------------|
| `output` | `all` or `random` |

### Single-Image Geometric Transforms

All vendored from [A-U-Supply/collage-bot](https://github.com/A-U-Supply/collage-bot). These are single-image effects typically used as preprocessing before stencil compositing.

**ancient_bullseye** — Cuts three concentric rings, rotates each independently 30–330°, pastes back. Creates a bullseye target pattern.

**ancient_wobbleeye** — Like bullseye but each ring drifts from the previous center in a random direction.

| Param | Description |
|-------|-------------|
| `rings` | Number of rings (3–15, default 5) |

**ancient_sixshooter** — Six circular cut-and-rotate operations. Layout adapts to aspect ratio: grid for landscape/portrait, hexagonal for near-square. Crops shuffled between positions.

**ancient_bullethole** — Random circular cut-and-rotate holes. Count and size controlled by chaos parameter.

| Param | Description |
|-------|-------------|
| `chaos` | 0.0 = few large holes, 1.0 = many small holes (default 0.5) |

**ancient_kaleidoscope** — N-fold radial symmetry applied to concentric bullseye rings. Creates mandala/kaleidoscope patterns.

| Param | Description |
|-------|-------------|
| `folds` | Symmetry fold count (3–16, default 6) |

**ancient_lathe** — Many thin concentric ring bands, each independently rotated. Creates sliced-wood/agate/lathe-turned appearance.

| Param | Description |
|-------|-------------|
| `rings` | Number of ring bands (10–120, default 40) |
