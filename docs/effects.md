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
