# Recipes

Each YAML file here defines a destruction pipeline — an ordered chain of effects with parameters.
The bot picks one at random each run. See [../docs/recipes.md](../docs/recipes.md) for the full
schema and per-effect parameter reference.

## Quick Reference

| Recipe | Chain | Vision |
|--------|-------|:------:|
| analog-burial | format_roundtrip &rarr; crt_vhs &rarr; byte_corrupt | |
| byte-liturgy | byte_corrupt &rarr; channel_shift &rarr; jpeg_destroy | |
| cellular-decay | cellular &rarr; fractal_blend &rarr; dither | |
| cga-nightmare | dither &rarr; pixel_sort &rarr; crt_vhs | |
| deep-fossil | deepdream &rarr; dither &rarr; jpeg_destroy | |
| dionysian-rite | deepdream &rarr; channel_shift &rarr; seam_carve &rarr; jpeg_destroy | yes |
| eigenface-requiem | pca_decompose &rarr; style_transfer &rarr; jpeg_destroy | |
| ocr-feedback-loop | imagemagick &rarr; pixel_sort &rarr; byte_corrupt &rarr; jpeg_destroy | |
| spectral-autopsy | spectral &rarr; sonify &rarr; channel_shift | |
| thermal-ghost | pca_decompose &rarr; dither &rarr; channel_shift | |
| turtle-oracle | primitive &rarr; pixel_sort &rarr; dither | |
| vhs-meltdown | crt_vhs &rarr; channel_shift &rarr; jpeg_destroy | |

## Recipe Details

### analog-burial
Lossy format round-trip (JPEG &rarr; BMP &rarr; JPEG at quality 3-10), CRT scan lines and jitter,
then raw byte flips. A digital artifact buried under format conversion and noise.

### byte-liturgy
Flips 100-500 raw bytes, shifts all three color channels apart, then 8-25 rounds of JPEG
compression at quality 1-4. Pure binary destruction.

### cellular-decay
Thresholds pixels into a Game of Life automaton (30-80 generations), blends in Mandelbrot fractals,
dithers to the Game Boy palette.

### cga-nightmare
CGA's 4-color palette crushes all subtlety, pixel sorting melts the remains into brightness streaks,
CRT scan lines complete the period-accurate 1981 horror.

### deep-fossil
DeepDream hallucination preserved in thermal-palette dithering and JPEG compression.
Neural phantoms fossilized in digital amber.

### dionysian-rite
The flagship recipe. DeepDream injects phantom forms, channel shifting fractures color,
vision-aware seam carving melts structure while protecting key regions, JPEG compression buries
the remains. Only recipe requiring Llama Vision (`vision: true`).

### eigenface-requiem
PCA decomposition keeps only the top 2-5 eigenvectors, style transfer enhances the ghostly
abstraction, JPEG compression adds entropic decay.

### ocr-feedback-loop
ImageMagick swirl (60-180 degrees), vertical hue-based pixel sorting, byte-level corruption,
then 10-30 rounds of JPEG compression at quality 1-3. Each step amplifies the previous damage.

### spectral-autopsy
Spectral shifting displaces spatial frequencies, sonification converts the image to audio and back
through reverb, channel shifting fractures the color planes.

### thermal-ghost
Extracts the *least* significant PCA components (the noise, not the signal), renders through a
thermal palette, adds subtle channel separation. The ghost of an image.

### turtle-oracle
Reconstructs the image from 30-80 triangles, pixel-sorts the shapes into streaks, dithers to the
16-color EGA palette.

### vhs-meltdown
VHS tape left in a hot car. CRT color bleeding and scan lines, chromatic aberration via channel
shifting, JPEG compression for digital rot on top of analog decay.

## Modifying Recipes

### Tuning parameters

Most params use `[min, max]` ranges — the bot picks a random value each run.

```yaml
offset_r: [5, 15]     # subtle
offset_r: [40, 120]   # extreme
offset_r: 60           # fixed, no randomness
```

Integer ranges produce integers, float ranges produce floats.

### Reordering effects

Order matters — each effect receives the previous step's output.

- **Neural effects first** — they need clean input to hallucinate on
- **Pixel-level effects in the middle** — sorting, shifting, dithering
- **Lossy compression last** — compounds everything before it

### Adding / removing effects

Add a `- type:` block anywhere in the `effects` list. Remove one by deleting its block.
Keep 2-4 effects per recipe — more than 5 tends to produce mud.

### Using vision

Set `vision: true` at the recipe level. Effects can then use `"vision"` as a param value:

```yaml
vision: true
effects:
  - type: seam_carve
    params:
      scale_x: [0.5, 0.7]
      protect_regions: "vision"
```

Only `seam_carve` currently supports vision-aware parameters.

### Creating a new recipe

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

```bash
python -m sparagmos --validate                                          # check syntax
python -m sparagmos --input test.jpg --output out.png --recipe my-recipe # test run
python -m sparagmos --list-recipes                                      # confirm it loads
```
