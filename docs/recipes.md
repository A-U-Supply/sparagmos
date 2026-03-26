# Recipe Guide

Recipes are YAML files in `recipes/` that define named pipelines of chained effects with parameters.

## Schema

### Single-input recipe (original / still supported)

```yaml
name: Human-Readable Recipe Name
description: >
  Multi-line description of what this recipe does and
  why these effects were chosen together.

# Whether to run Llama Vision analysis before processing.
# Effects can reference vision results via "vision" param values.
# Optional, defaults to false.
vision: false

effects:
  - type: effect_name          # Must match a registered effect's name
    params:
      param_name: value        # Fixed value — used as-is
      param_name: [min, max]   # Range — random value chosen per run
      param_name: "vision"     # Resolved from Llama Vision analysis
```

### Multi-input recipe

```yaml
name: Human-Readable Recipe Name
description: >
  What this recipe does.

inputs: 3      # How many source images to pull (integer)

steps:         # "steps" is an alias for "effects" — both work
  # Single-image step — operates on one named image in-place
  - type: effect_name
    image: a                   # which named image to transform
    params:
      param_name: value

  # Compositing step — combines two or more images
  - type: blend                # or: collage, mask_composite, fragment
    images: [a, b]             # source images (first is base)
    into: canvas               # write result to this name
    params:
      mode: screen
      strength: [0.6, 0.9]
```

## Named-Image Model

When a recipe declares `inputs: N`, the pipeline loads that many source images and assigns them names automatically:

| inputs | Names assigned |
|--------|---------------|
| 1 | `canvas` |
| 2 | `a`, `b` |
| 3 | `a`, `b`, `c` |
| 4 | `a`, `b`, `c`, `d` |
| N | `a` through the Nth letter |

Every step operates on named images:

- `image: a` — reads `a`, transforms it, writes back to `a`
- `images: [a, b]` + `into: canvas` — composites `a` and `b`, writes to `canvas`
- `image: canvas` — transforms the running composite

`canvas` is a conventional name for the primary output. Using it consistently makes it easy to follow the flow. You can name images anything — `canvas`, `a`, `base`, `overlay` — as long as the names are consistent between steps.

Single-image effects that don't specify `image:` default to `canvas` for backward compatibility.

## Parameter Types

### Fixed Values

```yaml
quality: 5
mode: "brightness"
```

Used as-is every run. Good for parameters where you want consistent behavior.

### Ranges

```yaml
quality: [1, 10]
scale: [0.3, 0.7]
```

A random value is chosen uniformly within the range each run. Integer ranges produce integers; float ranges produce floats. This gives each run variety while staying within artistic bounds.

### Vision Values

```yaml
protect_regions: "vision"
```

Resolved from Llama Vision analysis. Requires `vision: true` at the recipe level. The specific meaning depends on the effect.

## Per-Effect Parameter Reference

### channel_shift
| Param | Type | Range | Default | Description |
|-------|------|-------|---------|-------------|
| offset_r | int | -500 to 500 | 10 | Red channel horizontal offset in pixels |
| offset_g | int | -500 to 500 | 0 | Green channel horizontal offset |
| offset_b | int | -500 to 500 | -10 | Blue channel horizontal offset |

### jpeg_destroy
| Param | Type | Range | Default | Description |
|-------|------|-------|---------|-------------|
| quality | int | 1-95 | 5 | JPEG quality per iteration (lower = more destruction) |
| iterations | int | 1-100 | 10 | Number of save/reload cycles |

### pixel_sort
| Param | Type | Range | Default | Description |
|-------|------|-------|---------|-------------|
| mode | string | brightness/hue/saturation | brightness | Sort key |
| direction | string | horizontal/vertical | horizontal | Sort direction |
| threshold_low | float | 0.0-1.0 | 0.25 | Lower brightness threshold for segment detection |
| threshold_high | float | 0.0-1.0 | 0.75 | Upper brightness threshold |

### byte_corrupt
| Param | Type | Range | Default | Description |
|-------|------|-------|---------|-------------|
| num_flips | int | 1-10000 | 100 | Number of byte operations |
| skip_header | int | 0+ | 0 | Bytes to skip from start |
| mode | string | flip/inject/replace | flip | Corruption mode |

### dither
| Param | Type | Range | Default | Description |
|-------|------|-------|---------|-------------|
| palette | string | cga/ega/gameboy/thermal | cga | Color palette |
| num_colors | int | 2-256 | None | Custom color count (overrides palette) |

### crt_vhs
| Param | Type | Range | Default | Description |
|-------|------|-------|---------|-------------|
| scan_line_density | int | 1-20 | 3 | Darken every Nth row |
| jitter_amount | int | 0-50 | 2 | Max horizontal jitter in pixels |
| color_bleed | float | 0-10 | 1.5 | Chroma blur sigma |
| phosphor_glow | float | 0-1 | 0.1 | Bloom blend opacity |

### cellular
| Param | Type | Range | Default | Description |
|-------|------|-------|---------|-------------|
| rule | string | game_of_life/rule_110 | game_of_life | Automaton rule |
| generations | int | 1-200 | 10 | Number of generations to simulate |
| threshold | int | 0-255 | 128 | Brightness threshold for binary conversion |
| colorize | bool | — | false | Map generation counts to color gradient |

### pca_decompose
| Param | Type | Range | Default | Description |
|-------|------|-------|---------|-------------|
| n_components | int | 1-100 | 5 | Number of components to keep |
| mode | string | top/bottom | top | Keep best or worst components |

### fractal_blend
| Param | Type | Range | Default | Description |
|-------|------|-------|---------|-------------|
| opacity | float | 0-1 | 0.5 | Fractal blend opacity |
| iterations | int | 1-500 | 100 | Mandelbrot iteration depth |
| colormap | string | hot/cool/grayscale | hot | Fractal colormap |

### imagemagick
| Param | Type | Range | Default | Description |
|-------|------|-------|---------|-------------|
| preset | string | implode/swirl/wave/plasma_overlay/fx_noise | swirl | Named operation |
| amount | float | — | 0.5 | Preset-specific intensity |
| degrees | int | — | 90 | Swirl degrees |

### seam_carve
| Param | Type | Range | Default | Description |
|-------|------|-------|---------|-------------|
| scale_x | float | 0.1-1.0 | 0.7 | Target width ratio |
| scale_y | float | 0.1-1.0 | 1.0 | Target height ratio |
| protect_regions | string | none/vision/invert | none | Region protection mode |

### sonify
| Param | Type | Range | Default | Description |
|-------|------|-------|---------|-------------|
| effect | string | reverb/echo/distortion/phaser | reverb | DSP effect |
| intensity | float | 0-1 | 0.5 | Effect intensity |

### spectral
| Param | Type | Range | Default | Description |
|-------|------|-------|---------|-------------|
| operation | string | shift/bandpass/blur | shift | Spectral operation |
| amount | float | 0-1 | 0.3 | Operation amount |

### deepdream
| Param | Type | Range | Default | Description |
|-------|------|-------|---------|-------------|
| iterations | int | 1-50 | 10 | Optimization iterations |
| octave_scale | float | 1.0-2.0 | 1.4 | Scale between octaves |
| jitter | int | 0-64 | 32 | Random shift per iteration |
| learning_rate | float | 0.001-0.1 | 0.01 | Gradient step size |

### style_transfer
| Param | Type | Range | Default | Description |
|-------|------|-------|---------|-------------|
| style_weight | float | — | 1e6 | Style loss weight |
| content_weight | float | — | 1 | Content loss weight |
| iterations | int | 1-200 | 50 | Optimization iterations |

## Example Recipes with Commentary

### Voronoi Chimera — Multi-input neural/glitch fusion

```yaml
name: Voronoi Chimera
description: >
  Faces and forms fused at Voronoi cell boundaries. Each image gets a
  different neural/glitch treatment before being fragmented together.

inputs: 3       # pull 3 source images; they become a, b, c

steps:
  # Pre-process each input independently
  - type: deepdream
    image: a    # hallucinate on the first image
    params:
      iterations: [5, 12]
      octave_scale: [1.3, 1.5]
      jitter: [24, 48]

  - type: pixel_sort
    image: b    # melt the second
    params:
      mode: hue
      threshold: [40, 100]

  - type: dither
    image: c    # flatten the third to 4 colors
    params:
      method: bayer
      palette: cga

  # Compose — cut all three into Voronoi cells, reassemble
  - type: fragment
    images: [a, b, c]    # three sources
    into: canvas          # write composite here
    params:
      cut_mode: voronoi
      pieces: [15, 35]
      mix_ratio: [0.6, 0.9]
      gap: [0, 3]

  # Re-destroy the composite
  - type: blend
    images: [canvas, a]  # overlay original neural input on composite
    into: canvas
    params:
      mode: overlay
      strength: [0.3, 0.5]

  - type: channel_shift
    image: canvas         # fracture color planes
    params:
      offset_r: [30, 80]
      offset_b: [-60, -20]

  - type: jpeg_destroy
    image: canvas
    params:
      quality: [1, 3]
      iterations: [15, 35]
```

**Flow:** Each input is pre-processed independently (deepdream / pixel_sort / dither), then all three are fragmented together via Voronoi tessellation into `canvas`. The composite is then further destroyed — overlay-blended with one of the originals, color-fractured, then JPEG compressed. The pre-processing step ensures each Voronoi cell region has a distinct visual character before they collide.

### VHS Meltdown — Analog decay simulation

```yaml
name: VHS Meltdown
description: >
  Simulates a VHS tape left in a hot car. CRT scan lines and color
  bleeding first, then chromatic aberration from channel shifting,
  finished with JPEG compression to add digital rot on top.

effects:
  # Start with the analog simulation — this sets the base aesthetic
  - type: crt_vhs
    params:
      scan_line_density: [2, 4]     # variety in line spacing
      jitter_amount: [3, 8]         # moderate to heavy jitter
      color_bleed: [1.0, 3.0]       # noticeable but not total
      phosphor_glow: [0.05, 0.15]   # subtle bloom

  # Channel shift adds chromatic aberration on top of the VHS look
  - type: channel_shift
    params:
      offset_r: [10, 40]
      offset_b: [-30, -10]

  # JPEG compression as the final step compounds everything
  - type: jpeg_destroy
    params:
      quality: [2, 8]
      iterations: [3, 10]
```

**Why this order matters:** CRT/VHS effects create the analog base, channel shifting adds color separation that interacts with the scan lines, and JPEG compression at the end adds artifacts that interact with all the previous distortions. Reversing the order would produce a very different (and less interesting) result.

### Dionysian Rite — Neural + analog fusion

```yaml
name: Dionysian Rite
description: >
  Ritual dismemberment through neural hallucination and analog decay.
  DeepDream injects phantom forms, channel shifting fractures color,
  seam carving melts structure, and JPEG compression buries the remains.

vision: true

effects:
  - type: deepdream
    params:
      iterations: [5, 15]
      octave_scale: 1.4
      jitter: 32

  - type: channel_shift
    params:
      offset_r: [20, 80]
      offset_b: [-60, -20]

  - type: seam_carve
    params:
      scale_x: [0.5, 0.7]
      protect_regions: "vision"

  - type: jpeg_destroy
    params:
      quality: [1, 5]
      iterations: [5, 20]
```

## Tips

### Effect ordering
- **Put lossy compression last** — it compounds everything before it
- **Channel shift before scan lines** makes the aberration visible in the lines
- **Neural effects first** gives them clean input to hallucinate on
- **2-4 effects per recipe** is the sweet spot; more than 5 tends to produce mud

### Multi-input design patterns

- **Pre-process → compose → destroy → re-compose** is the core loop: treat each input individually, smash them together, destroy the result, then optionally blend an original back in for spectral collision
- **Vary the pre-processing** across inputs — if all inputs get the same treatment the composition will look flat; give each one a different aesthetic (neural, dithered, pixel-sorted) so the cell boundaries carry meaning
- **Use `canvas` as your running state** — compositing steps write to `canvas`; single-image steps transform it further; you can always re-introduce a named input (`images: [canvas, a]`) to overlay the original back in
- **Layer mask_composite progressively** — for 3+ inputs, chain multiple `mask_composite` steps: `[a, b] → canvas`, then `[canvas, c] → canvas`. Varying the `threshold` at each layer creates geological strata
- **`into:` names are reusable** — you can write intermediate composites to names other than `canvas` (e.g. `into: mid`) and reference them later

### General
- **Use ranges liberally** — variety across runs is what makes each output unique
- **Vision-aware effects** (seam_carve, inpaint) need `vision: true` at recipe level
- **`steps:` and `effects:` are interchangeable** — both work as the step list key
