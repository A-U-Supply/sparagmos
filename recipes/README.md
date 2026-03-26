# Recipes

Each YAML file here defines a destruction pipeline — an ordered chain of effects with parameters.
The bot picks one at random each run. See [../docs/recipes.md](../docs/recipes.md) for the full
schema and per-effect parameter reference.

## Quick Reference

| Recipe | Inputs | Chain |
|--------|:------:|-------|
| double-exposure | 2 | spectral/sonify pre-process → blend (screen + multiply) → sonify → jpeg_destroy |
| edge-ghosts | 3 | spectral/pca/channel_shift pre-process → mask_composite ×2 (edges) → spectral → channel_shift |
| exquisite-corpse | 3 | pixel_sort/crt_vhs/channel_shift pre-process → fragment (strips) → seam_carve → crt_vhs → jpeg_destroy |
| feedback-loop | 2 | blend (screen) → imagemagick/channel_shift → fragment → blend (overlay) → channel_shift → jpeg_destroy |
| fossil-record | 3 | pca_decompose ×3 → blend (opacity) ×2 → dither → channel_shift → jpeg_destroy |
| mosaic-dissolution | 5 | channel_shift/crt_vhs/dither/pixel_sort/pca pre-process → collage (mosaic) → fragment → pixel_sort → jpeg_destroy → byte_corrupt |
| neural-chimera | 3 | deepdream ×3 → fragment (voronoi) → blend (overlay) → style_transfer → jpeg_destroy |
| palimpsest | 4 | pca/channel_shift/crt_vhs/pixel_sort pre-process → mask_composite ×3 (luminance) → byte_corrupt → dither |
| signal-bleed | 3 | crt_vhs ×3 → collage (strips) → channel_shift → byte_corrupt → jpeg_destroy |
| spectral-merge | 2 | spectral ×2 → blend (difference) → mask_composite (luminance) → sonify → dither |
| tectonic-overlap | 4 | imagemagick/deepdream/sonify/dither pre-process → fragment (shatter) → collage (scatter) → seam_carve → jpeg_destroy |
| voronoi-chimera | 3 | deepdream/pixel_sort/dither pre-process → fragment (voronoi) → blend (overlay) → channel_shift → jpeg_destroy |

## Recipe Details

### double-exposure
Two images burned onto the same film. `a` is spectrally bandpassed, `b` is sonified with reverb.
Screen blending accumulates light from both; multiply deepens the shadows. The composite is
distorted then compressed into oblivion. Classic photographic accident as digital process.

### edge-ghosts
Phantom outlines from one image haunting another. `a` is spectrally filtered, `b` PCA-reduced,
`c` color-shifted. Two rounds of edge-mask compositing layer the ghosts. Spectral processing
and channel shift add ethereal decay to the final composite.

### exquisite-corpse
The surrealist parlor game. Three images divided into horizontal strips, each pre-processed
differently (pixel-sorted / VHS-blurred / channel-shifted) to heighten the disjunction at the
seams. Seam carving warps the joins, CRT static adds noise, JPEG destroys the evidence.

### feedback-loop
Compose, destroy, re-compose the wreckage, destroy again. Two images screen-blended, swirled,
channel-shifted, then re-fragmented with the originals back into the mix. Each pass compounds
the damage. The output feeds conceptually back into itself.

### fossil-record
Geological strata. Each of three inputs is PCA-decomposed to a different component count
(shallow / mid / deep structure). Opacity-blended as sedimentary layers. Dithering creates
stone texture, channel shift adds mineral coloration.

### mosaic-dissolution
Maximum inputs (5), maximum chaos. Each source gets a distinct pre-treatment — channel shift,
VHS blur, Game Boy dither, saturation sort, PCA noise extraction. All five tiled into a mosaic,
then the mosaic itself is grid-fragmented and pixel-sorted into dust.

### neural-chimera
Three images deepdreamed at different intensity levels, then Voronoi-fragmented together.
One original is overlay-blended back in for ghostly persistence. Style transfer
re-hallucinates the composite. JPEG destruction finalizes.

### palimpsest
A manuscript overwritten repeatedly. Four inputs pre-processed then layered through three
successive luminance-masked composites at escalating thresholds — each pass reveals more of
the newer layer while the previous bleeds through. Byte corruption ages the parchment, dithering
reduces it to medieval dot patterns.

### signal-bleed
Three VHS signals bleeding into each other on a bad splitter. Each source gets its own flavor
of analog decay at different jitter/bleed settings. Vertical strip collage interleaves the
signals side by side. Channel shift and byte corruption simulate crosstalk.

### spectral-merge
Two signals destructively interfered in frequency space. `a` and `b` are bandpassed to
complementary frequency ranges, then difference-blended to cancel their shared content.
A luminance mask re-introduces texture. Sonification and dithering quantize the interference
pattern.

### tectonic-overlap
Continental plates of image data. Four inputs get distinct treatments (swirl / deepdream / echo
/ EGA dither), shattered into irregular polygons, then scatter-collaged with rotation. Seam
carving warps the fault lines. JPEG compresses the geological record.

### voronoi-chimera
Faces and forms fused at Voronoi cell boundaries. Three inputs pre-processed with deepdream,
pixel sorting, and CGA dithering so each Voronoi region has a distinct aesthetic. Fragment
assembles the collisions, overlay blending re-introduces the neural source, channel shift
fractures the color planes, JPEG welds the seams.

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

- **Pre-process inputs independently** — give each named image its own aesthetic before compositing
- **Neural effects first** — they need clean input to hallucinate on
- **Compose in the middle** — merge, fragment, or mask-composite into `canvas`
- **Destroy after composing** — channel shift, seam carve, sonify on `canvas`
- **Lossy compression last** — compounds everything before it

### Adding / removing effects

Add a `- type:` block anywhere in the `steps` list. Remove one by deleting its block.
Keep 4-8 steps per recipe — more than 10 tends to produce undifferentiated mud.

### Creating a new recipe

```yaml
name: Your Recipe Name
description: >
  What it does and why these effects work together.

inputs: 2    # how many source images (omit or set 1 for single-image)

steps:
  - type: effect_name
    image: a              # single-image step
    params:
      param: value
      param: [min, max]

  - type: blend           # compositing step
    images: [a, b]
    into: canvas
    params:
      mode: screen
      strength: [0.5, 0.8]

  - type: jpeg_destroy    # destroy the composite
    image: canvas
    params:
      quality: [1, 5]
      iterations: [5, 20]
```

```bash
python -m sparagmos --validate                                           # check syntax
python -m sparagmos --input a.jpg b.jpg --output out.png --recipe my-recipe  # test run
python -m sparagmos --list-recipes                                       # confirm it loads
```

### Using vision

Set `vision: true` at the recipe level. Effects can then use `"vision"` as a param value:

```yaml
vision: true
steps:
  - type: seam_carve
    image: canvas
    params:
      scale_x: [0.5, 0.7]
      protect_regions: "vision"
```

Only `seam_carve` currently supports vision-aware parameters.
