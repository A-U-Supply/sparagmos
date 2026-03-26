# Recipes

Each YAML file here defines a destruction pipeline — an ordered chain of effects with parameters. The bot picks one at random each run. See [../docs/recipes.md](../docs/recipes.md) for the full schema and per-effect parameter reference.

## Included Recipes

### Analog / Retro

**analog-burial** — Format-converts the image through lossy codecs (JPEG &rarr; BMP &rarr; JPEG), applies CRT scan lines and jitter, then flips raw bytes. A digital artifact buried under format conversion and noise.

**cga-nightmare** — Crushes the palette to CGA's 4 colors, pixel-sorts the remains into brightness streaks, and adds CRT scan lines. Period-accurate 1981 horror.

**vhs-meltdown** — Simulates a VHS tape left in a hot car. CRT color bleeding and scan lines, chromatic aberration via channel shifting, then JPEG compression for digital rot on top of analog decay.

### Binary / Compression

**byte-liturgy** — Flips 100-500 raw bytes, shifts all three color channels apart, then runs 8-25 rounds of aggressive JPEG compression (quality 1-4). Pure binary destruction.

**ocr-feedback-loop** — ImageMagick swirl distortion, vertical hue-based pixel sorting, byte-level corruption, and 10-30 rounds of near-zero-quality JPEG compression. Each step amplifies the previous damage.

### Neural / Generative

**deep-fossil** — DeepDream hallucination preserved in thermal-palette dithering and JPEG compression. Neural phantoms fossilized in digital amber.

**dionysian-rite** — The flagship recipe. DeepDream injects phantom forms, channel shifting fractures color, vision-aware seam carving melts structure while protecting key regions, and JPEG compression buries the remains. Requires Llama Vision (`vision: true`).

**eigenface-requiem** — PCA decomposition keeps only the 2-5 most significant eigenvectors, style transfer recursively enhances the ghostly abstraction, and JPEG compression adds entropic decay.

### Frequency / Audio

**spectral-autopsy** — Spectral shifting displaces spatial frequencies, sonification converts the image to audio, applies reverb, and converts back, then channel shifting fractures the color planes.

### Mathematical / Algorithmic

**cellular-decay** — Thresholds pixels into a Game of Life automaton that evolves for 30-80 generations, blends in Mandelbrot fractals, and dithers to the Game Boy palette.

**thermal-ghost** — Extracts the *least* significant PCA components (the noise, not the signal), renders them through a thermal imaging palette, and adds subtle channel separation. The ghost of an image.

**turtle-oracle** — Reconstructs the image from 30-80 triangles via the `primitive` algorithm, pixel-sorts the shapes into streaks, and dithers to the 16-color EGA palette.

## How to Modify a Recipe

### Tuning Parameters

Most params use `[min, max]` ranges — the bot picks a random value within the range each run. To make an effect more aggressive, widen the range or shift it:

```yaml
# Subtle channel shift
offset_r: [5, 15]

# Extreme channel shift
offset_r: [40, 120]

# Fixed (no randomness)
offset_r: 60
```

Integer ranges produce integers, float ranges produce floats.

### Reordering Effects

Order matters. Effects are applied sequentially — each one receives the output of the previous step. General principles:

- **Neural effects first** — they need clean input to hallucinate on
- **Pixel-level effects in the middle** — sorting, shifting, dithering
- **Lossy compression last** — it compounds everything before it, creating artifacts that interact with all previous distortions

Swapping order produces fundamentally different results. Experiment.

### Adding or Removing Effects

Add a new step anywhere in the `effects` list:

```yaml
effects:
  - type: existing_effect
    params: { ... }

  # New step — insert between existing effects
  - type: channel_shift
    params:
      offset_r: [10, 50]
      offset_b: [-30, -10]

  - type: jpeg_destroy
    params:
      quality: [2, 8]
      iterations: [5, 15]
```

Remove a step by deleting its `- type: ...` block. Keep 2-4 effects per recipe — more than 5 tends to produce mud.

### Using Vision

Set `vision: true` at the top level to enable Llama Vision analysis. Effects can then reference vision results:

```yaml
vision: true

effects:
  - type: seam_carve
    params:
      scale_x: [0.5, 0.7]
      protect_regions: "vision"   # AI-detected regions are protected from carving
```

Only `seam_carve` currently uses vision-aware parameters.

### Creating a New Recipe

1. Create a new `.yaml` file in this directory
2. Follow the schema (name, description, effects list)
3. Validate: `python -m sparagmos --validate`
4. Test: `python -m sparagmos --input test.jpg --output out.png --recipe your-recipe`

```yaml
name: Your Recipe Name
description: >
  What it does and why these effects work together.

effects:
  - type: effect_name
    params:
      param: value
      param: [min, max]
```

Run `python -m sparagmos --list-recipes` to confirm it loads, and see [../docs/recipes.md](../docs/recipes.md) for the full parameter reference for each effect.
