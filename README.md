```
          .    *    .    ░    .         .    ░    .    *    .

                    ░▒▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▒░
               ░▒▓▓                                      ▓▓▒░
             ▒▓                                              ▓▒
            ▓  ▄██▀ █▀▀▄ ▄▀▀▄ █▀▀▄ ▄▀▀▄ ▄▀▀▀ █▄▄█ ▄▀▀▄ ▄██▀  ▓
            ▓  ▀▀▄█ █▀▀▀ █▀▀█ █▀▀▄ █▀▀█ █ ▀█ █ ▀ █ █  █ ▀▀▄█  ▓
            ▓  ▀▀▀  ▀    ▀  ▀ ▀  ▀ ▀  ▀ ▀▀▀  ▀   ▀ ▀▀▀  ▀▀▀   ▓
             ▒▓                                              ▓▒
               ░▒▓▓                                      ▓▓▒░
                    ░▒▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▒░

          .    ░    .         .    *    .         .    ░    .

                           σπαραγμός
                image transformation through chaos
```

Automated image destruction bot. Scrapes random images from #image-gen on Slack, applies chained glitch/decay/neural effects via YAML recipes, posts results to #img-junkyard.

**Name origin:** σπαραγμός — the ritual dismemberment in Dionysian mystery rites. The ecstatic tearing apart of a body as a sacred act. Destruction is the worship.

─── ·  ✦  · ──────────────────────────────── ·  ✦  · ───

## What It Does

Every day, sparagmos picks a random image from the #image-gen Slack channel, selects a random destruction recipe, chains the effects together, and posts the result with full provenance. The same image through a different recipe is a completely different piece.

─── ·  ✦  · ──────────────────────────────── ·  ✦  · ───

## Effects

| Effect | Era | What It Does | System Deps |
|--------|-----|-------------|-------------|
| `byte_corrupt` | 1980s+ | Flip/inject/replace raw bytes in image data, skip headers | None |
| `netpbm` | 1988 | Ancient Unix filters: moon craters, fractal planets, pixel spread | `netpbm` |
| `imagemagick` | 1990 | `-implode`, `-swirl`, `-fx` expressions, `-morphology`, `-distort` | `imagemagick` |
| `sonify` | 2000s | Import image as raw audio, apply DSP effects, export back | None |
| `format_roundtrip` | 2000s | Lossy conversion chains: bitmap → potrace vector → rasterize back | `potrace` |
| `pixel_sort` | 2010 | Sort pixel rows/columns by brightness, hue, or saturation | None |
| `datamosh` | 2010s | I-frame removal, motion vector swapping between images | None |
| `channel_shift` | 2010s | Offset/swap/separate RGB channels, chromatic aberration | None |
| `dither` | 2010s | Floyd-Steinberg, Bayer, Atkinson + retro palettes (CGA, EGA, Game Boy) | None |
| `seam_carve` | 2010s | Content-aware resize, intentionally broken — melt faces, bend buildings | None |
| `crt_vhs` | 2010s | Scan lines, tracking errors, color bleeding, phosphor glow, horizontal jitter | None |
| `jpeg_destroy` | 2010s | Save at quality 1, reopen, repeat N times — generational loss as art | None |
| `primitive` | 2016 | Reconstruct with geometric shapes (triangles, ellipses) at low iteration | `primitive` |
| `deepdream` | 2015 | Amplify neural net patterns — dogs, eyes, pagodas emerge from noise | None (PyTorch) |
| `style_transfer` | 2015 | Apply style of one image to content of another (Gatys algorithm) | None (PyTorch) |
| `neural_doodle` | 2016 | Semantic style painting with rough masks → surreal photorealism | None |
| `pix2pix` | 2016-17 | Image-to-image translation, domain transfer artifacts | None |
| `pca_decompose` | — | Reconstruct image from only top/bottom N PCA components | None |
| `cellular` | — | Game of Life / Rule 110 on pixel brightness, run N generations | None |
| `fractal_blend` | — | Mandelbrot at coordinates derived from image histogram, blend | None |
| `spectral` | — | Treat image as spectrogram, process with audio DSP, render back | None |
| `inpaint` | 2020s | Mask regions (random or Llama-targeted), regenerate with OpenCV | None (OpenCV) |

─── ·  ✦  · ──────────────────────────────── ·  ✦  · ───

## Quickstart

### Install Dependencies

```bash
# Python deps
pip install -r requirements.txt
# or with uv:
uv sync

# System deps (optional — needed for subprocess effects)
# macOS:
brew install imagemagick netpbm ffmpeg potrace
go install github.com/fogleman/primitive@latest
# Ubuntu:
sudo apt-get install imagemagick netpbm ffmpeg potrace
```

### Run Locally

```bash
# Process a local image with a random recipe
python -m sparagmos --input photo.jpg --output junked.png

# Use a specific recipe
python -m sparagmos --input photo.jpg --output junked.png --recipe vhs-meltdown

# Dry run (process but don't post to Slack)
python -m sparagmos --dry-run
```

### CLI Reference

```
python -m sparagmos                          # Full daily run (random image, random recipe, post)
python -m sparagmos --recipe dionysian-rite  # Specific recipe
python -m sparagmos --input photo.jpg --output junked.png  # Local I/O
python -m sparagmos --dry-run                # Process but don't post
python -m sparagmos --list-recipes           # List available recipes
python -m sparagmos --list-effects           # List available effects with deps
python -m sparagmos --validate               # Validate all recipes
python -m sparagmos --seed 42                # Deterministic run
```

─── ·  ✦  · ──────────────────────────────── ·  ✦  · ───

## Recipes

Recipes are YAML files in `recipes/` that define named pipelines of chained effects. See [docs/recipes.md](docs/recipes.md) for the full reference.

### Included Recipes

| Recipe | Effects Chain |
|--------|-------------|
| vhs-meltdown | crt_vhs → channel_shift → jpeg_destroy |
| deep-fossil | deepdream → dither (thermal) → jpeg_destroy |
| cga-nightmare | dither (CGA) → pixel_sort → crt_vhs |
| dionysian-rite | deepdream → channel_shift → seam_carve → jpeg_destroy |
| analog-burial | format_roundtrip (potrace) → crt_vhs → byte_corrupt |
| byte-liturgy | byte_corrupt → channel_shift → jpeg_destroy |
| thermal-ghost | pca_decompose (bottom 5) → dither (thermal) → channel_shift |
| turtle-oracle | primitive (triangles) → pixel_sort → dither (EGA) |
| eigenface-requiem | pca_decompose (top 3) → style_transfer → jpeg_destroy |
| spectral-autopsy | spectral (shift) → sonify (reverb) → channel_shift |
| cellular-decay | cellular (game of life) → fractal_blend → dither |
| ocr-feedback-loop | imagemagick (swirl) → pixel_sort → byte_corrupt → jpeg_destroy |

─── ·  ✦  · ──────────────────────────────── ·  ✦  · ───

## Architecture

```
#image-gen (Slack)
    │
    │ 1. Pick random image (not previously processed)
    ▼
slack_source.py → download image, record in state.json
    │
    │ 2. Optionally analyze with Llama Vision
    ▼
vision.py (HF Inference API)
    │
    │ 3. Pick random recipe, resolve param ranges
    ▼
config.py → load YAML, validate, roll random values
    │
    │ 4. Execute effect chain
    ▼
pipeline.py → effect₁ → effect₂ → ... → result
    │
    │ 5. Post to Slack (single message)
    ▼
#img-junkyard (Slack)
```

─── ·  ✦  · ──────────────────────────────── ·  ✦  · ───

## Development

### Adding a New Effect

1. Create `sparagmos/effects/your_effect.py`
2. Inherit from `Effect` (or `SubprocessEffect` for CLI tools)
3. Implement `apply()` and `validate_params()`
4. Call `register_effect(YourEffect())` at module level
5. Add tests in `tests/test_effects/test_your_effect.py`
6. See [docs/effects.md](docs/effects.md) for the full guide

### Writing Recipes

Create a YAML file in `recipes/`:

```yaml
name: My Recipe
description: What this recipe does and why.
effects:
  - type: channel_shift
    params:
      offset_r: [10, 50]    # range — random value each run
      offset_b: -20          # fixed value
  - type: jpeg_destroy
    params:
      quality: [1, 5]
      iterations: [5, 20]
```

### Running Tests

```bash
# All tests
uv run pytest -v

# Skip slow neural tests
uv run pytest -v -m "not slow"

# Validate recipes
python -m sparagmos --validate
```

─── ·  ✦  · ──────────────────────────────── ·  ✦  · ───

## System Dependencies

| Package | macOS | Ubuntu | Used By |
|---------|-------|--------|---------|
| ImageMagick | `brew install imagemagick` | `apt install imagemagick` | imagemagick effect |
| NetPBM | `brew install netpbm` | `apt install netpbm` | netpbm effect |
| ffmpeg | `brew install ffmpeg` | `apt install ffmpeg` | datamosh effect |
| potrace | `brew install potrace` | `apt install potrace` | format_roundtrip effect |
| primitive | `go install github.com/fogleman/primitive@latest` | same | primitive effect |

Effects gracefully skip when their system deps are missing.
