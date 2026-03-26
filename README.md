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

Automated image destruction bot. Scrapes random images from #image-gen on Slack, applies chained glitch/decay/neural effects via YAML recipes, posts results to #img-junkyard. Multi-input recipes pull several images and composite them together — fragmenting, masking, and blending across sources before destroying the result.

**Name origin:** σπαραγμός — the ritual dismemberment in Dionysian mystery rites. The ecstatic tearing apart of a body as a sacred act. Destruction is the worship.

─── ·  ✦  · ──────────────────────────────── ·  ✦  · ───

## What It Does

Every day, sparagmos picks one or more random images from the #image-gen Slack channel, selects a random destruction recipe, chains the effects together, and posts the result with full provenance. Multi-input recipes pull several images and composite them — fragmenting, masking, blending — before destroying the result. The same inputs through a different recipe produce a completely different piece.

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
| `collage` | — | Spatial arrangement of multiple images: grid, scatter, strips, mosaic | None |
| `blend` | — | Pixel-level blending of two images: opacity, multiply, screen, overlay, difference | None |
| `mask_composite` | — | Mask-based selection between two images driven by luminance, edges, or noise | None |
| `fragment` | — | Cut images into pieces (grid, voronoi, strips, shatter) and reassemble from mixed sources | None |

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

# Multi-input recipe — pass as many images as the recipe requires
python -m sparagmos --input a.jpg b.jpg c.jpg --output junked.png --recipe voronoi-chimera

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

| Recipe | Inputs | Key Compositing |
|--------|:------:|-----------------|
| double-exposure | 2 | blend (screen + multiply) |
| edge-ghosts | 3 | mask_composite ×2 (edges) |
| exquisite-corpse | 3 | fragment (strips) |
| feedback-loop | 2 | blend → fragment → blend |
| fossil-record | 3 | blend (opacity) ×2 |
| mosaic-dissolution | 5 | collage (mosaic) → fragment |
| neural-chimera | 3 | fragment (voronoi) + style_transfer |
| palimpsest | 4 | mask_composite ×3 (luminance) |
| signal-bleed | 3 | collage (strips) |
| spectral-merge | 2 | blend (difference) + mask_composite |
| tectonic-overlap | 4 | fragment (shatter) + collage (scatter) |
| voronoi-chimera | 3 | fragment (voronoi) + blend |

─── ·  ✦  · ──────────────────────────────── ·  ✦  · ───

## Architecture

```
#image-gen (Slack)
    │
    │ 1. Pick N random images (recipe declares how many)
    ▼
slack_source.py → download images, record in state.json
    │
    │ 2. Optionally analyze with Llama Vision
    ▼
vision.py (HF Inference API)
    │
    │ 3. Pick random recipe, resolve param ranges
    ▼
config.py → load YAML, validate, roll random values
    │
    │ 4. Execute effect chain via named-image register
    │      inputs loaded as: 1 img → "canvas"
    │                         2 imgs → "a", "b"
    │                         N imgs → "a" … Nth letter
    ▼
pipeline.py → effect₁ → effect₂ → ... → result ("canvas")
    │
    │ 5. Post to Slack (single message)
    ▼
#img-junkyard (Slack)
```

The pipeline maintains a **named-image register** — a dict mapping string names to PIL Images. Each step reads from and writes to named slots. Single-image steps transform a slot in place; compositing steps (`blend`, `fragment`, `collage`, `mask_composite`) read from multiple slots and write their output to a new slot.

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

Create a YAML file in `recipes/`. Single-input recipes use `effects:` and no `image:` keys. Multi-input recipes declare `inputs: N` and use `steps:`, with each step specifying `image:` (single) or `images:` + `into:` (compositing):

```yaml
name: My Recipe
description: What this recipe does and why.
inputs: 2         # omit for single-image

steps:            # alias for "effects"
  - type: channel_shift
    image: a      # operate on named input
    params:
      offset_r: [10, 50]    # range — random value each run
      offset_b: -20          # fixed value
  - type: blend
    images: [a, b]           # composite two images
    into: canvas
    params:
      mode: screen
      strength: [0.6, 0.9]
  - type: jpeg_destroy
    image: canvas
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
