"""Ancient effects — adapter wrapping A-U-Supply/collage-bot transforms.

Vendored source: sparagmos/vendor/collage_bot/
Update: git subtree pull --prefix sparagmos/vendor/collage_bot \
    https://github.com/A-U-Supply/collage-bot.git main --squash

To add a new mode from collage-bot:
  1. Pull latest with the command above
  2. Add a new Effect/ComposeEffect subclass below
  3. Add a new recipe YAML in recipes/ancients-<mode>.yaml
"""

from __future__ import annotations

import random
from itertools import permutations

import numpy as np
from PIL import Image

from sparagmos.effects import (
    ComposeEffect,
    ConfigError,
    Effect,
    EffectContext,
    EffectResult,
    register_effect,
)
from sparagmos.vendor.collage_bot.stencil_transform import apply_stencil, make_stencil
from sparagmos.vendor.collage_bot.transform import (
    apply_transform,
    blend_seams,
    make_composites,
)

# Stencil mask variant imports
from sparagmos.vendor.collage_bot.halftone_bot import make_halftone_stencil
from sparagmos.vendor.collage_bot.linescreen_bot import (
    make_linescreen_stencil as make_linescreen_stencil_straight,
)
from sparagmos.vendor.collage_bot.curvylinescreen_bot import (
    make_linescreen_stencil as make_linescreen_stencil_curvy,
)
from sparagmos.vendor.collage_bot.reducedlinescreen_bot import (
    make_linescreen_stencil as make_linescreen_stencil_reduced,
)

# Tonal treatment imports
from sparagmos.vendor.collage_bot.cyanotype_bot import to_cyanotype
from sparagmos.vendor.collage_bot.silver_bot import to_silver_halation

# Edge / displacement imports
from sparagmos.vendor.collage_bot.halationedge_bot import blend_with_noisy_mask
from sparagmos.vendor.collage_bot.displacement_bot import (
    compute_displacement,
    compute_fill_envelope,
    displace_image,
)

# 3-level stencil import
from sparagmos.vendor.collage_bot.quad_transform import (
    apply_3level_stencil,
    make_3level_stencil,
)

# Single-image geometric imports
from sparagmos.vendor.collage_bot.bullseye_bot import apply_bullseye
from sparagmos.vendor.collage_bot.wobbleeye_bot import apply_wobbleeye
from sparagmos.vendor.collage_bot.sixshooter_bot import apply_six_shooter
from sparagmos.vendor.collage_bot.bullethole_bot import apply_bullet_holes
from sparagmos.vendor.collage_bot.kaleidoscope_bot import apply_kaleidoscope_bullseye
from sparagmos.vendor.collage_bot.lathe_bot import apply_lathe

VALID_OUTPUTS = {"all", "random"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _stencil_permutations(
    images: list[Image.Image],
    mask_fn,
    composite_fn,
    output_mode: str,
    rng: random.Random,
    metadata_extra: dict | None = None,
) -> EffectResult:
    """Run mask_fn/composite_fn over all stencil/fill permutations.

    mask_fn(image) -> PIL mask
    composite_fn(mask, fill_a, fill_b) -> PIL result
    """
    results: list[Image.Image] = []
    n = len(images)

    for i in range(n):
        mask = mask_fn(images[i])
        others = [images[j] for j in range(n) if j != i]
        for perm in permutations(others):
            results.append(composite_fn(mask, perm[0], perm[1]))

    meta = {"output": output_mode, "total_variations": len(results)}
    if metadata_extra:
        meta.update(metadata_extra)

    if output_mode == "random":
        chosen = rng.choice(results)
        return EffectResult(image=chosen, images=[chosen], metadata=meta)

    return EffectResult(image=results[0], images=results, metadata=meta)


def _displacement_composite(
    stencil: Image.Image,
    img_a: Image.Image,
    img_b: Image.Image,
    strength: float = 200.0,
    blur: float = 3.0,
    fill_falloff: float = 600.0,
) -> Image.Image:
    """Displacement stencil composite using properly imported make_stencil.

    Reimplements displacement_bot.apply_stencil_with_displacement to avoid
    the vendored module's broken lazy ``from stencil_transform import ...``.
    """
    w, h = stencil.size
    img_a = img_a.convert("RGB").resize((w, h), Image.LANCZOS)
    img_b = img_b.convert("RGB").resize((w, h), Image.LANCZOS)

    dx, dy = compute_displacement(stencil, strength=strength, blur=blur)

    warped_stencil = displace_image(stencil, dx * 0.5, dy * 0.5)
    mask = make_stencil(warped_stencil)
    mask_arr = np.array(mask)

    envelope = compute_fill_envelope(mask_arr, falloff=fill_falloff)
    dx_fill = dx * 2.0 * envelope
    dy_fill = dy * 2.0 * envelope

    warped_a = displace_image(img_a, -dx_fill, -dy_fill)
    warped_b = displace_image(img_b, dx_fill, dy_fill)

    a_arr = np.array(warped_a)
    b_arr = np.array(warped_b)
    composite = np.where(mask_arr[:, :, np.newaxis] > 0, a_arr, b_arr)
    return Image.fromarray(composite.astype(np.uint8))


def _validate_output(params: dict, effect_name: str) -> str:
    output = params.get("output", "all")
    if output not in VALID_OUTPUTS:
        raise ConfigError(
            f"Unknown output mode: {output!r}. Valid: {sorted(VALID_OUTPUTS)}",
            effect_name=effect_name,
            param_name="output",
        )
    return output


# ---------------------------------------------------------------------------
# Original effects: stencil + collage
# ---------------------------------------------------------------------------


class AncientStencilEffect(ComposeEffect):
    """Binary mask compositing via Otsu's thresholding.

    Each input image takes a turn as the stencil mask. For each mask,
    the remaining images are composited in both orderings (foreground/
    background swap), producing N * (N-1) variations for N inputs.
    With 3 inputs this yields 6 variations.
    """

    name = "ancient_stencil"
    description = "Otsu stencil masking from collage-bot"
    requires: list[str] = []

    def compose(
        self, images: list[Image.Image], params: dict, context: EffectContext
    ) -> EffectResult:
        params = self.validate_params(params)
        rng = random.Random(context.seed)
        return _stencil_permutations(
            images, make_stencil, apply_stencil, params["output"], rng,
            metadata_extra={"mode": "stencil"},
        )

    def validate_params(self, params: dict) -> dict:
        return {"output": _validate_output(params, "ancient_stencil")}


class AncientCollageEffect(ComposeEffect):
    """Quadrant-mixed composites with geometric transform and seam inpainting.

    Takes 4 source images, cuts each into quadrants, shuffles quadrants
    across 4 output composites, applies a grid transform, and uses LaMa
    neural inpainting to blend the seams seamlessly.
    """

    name = "ancient_collage"
    description = "Quadrant collage with seam inpainting from collage-bot"
    requires: list[str] = []

    def compose(
        self, images: list[Image.Image], params: dict, context: EffectContext
    ) -> EffectResult:
        params = self.validate_params(params)
        output_mode: str = params["output"]
        split: float = params["split"]
        blend_width: int = params["blend_width"]
        rng = random.Random(context.seed)

        # Seed Python's global random for collage-bot functions that use it
        random.seed(context.seed)

        composites = make_composites([img.convert("RGB") for img in images])
        results: list[Image.Image] = []
        for comp in composites:
            transformed = apply_transform(comp, split=split)
            blended = blend_seams(transformed, strip_width=blend_width, split=split)
            results.append(blended.convert("RGB"))

        if output_mode == "random":
            chosen = rng.choice(results)
            return EffectResult(
                image=chosen,
                images=[chosen],
                metadata={
                    "mode": "collage",
                    "output": "random",
                    "total_composites": len(results),
                },
            )

        return EffectResult(
            image=results[0],
            images=results,
            metadata={
                "mode": "collage",
                "output": "all",
                "total_composites": len(results),
            },
        )

    def validate_params(self, params: dict) -> dict:
        output = _validate_output(params, "ancient_collage")
        split = float(params.get("split", 0.25))
        split = max(0.05, min(0.45, split))
        blend_width = int(params.get("blend_width", 70))
        blend_width = max(1, min(200, blend_width))
        return {"output": output, "split": split, "blend_width": blend_width}


# ---------------------------------------------------------------------------
# Stencil mask variants (3 inputs)
# ---------------------------------------------------------------------------


class AncientHalftoneEffect(ComposeEffect):
    """AM halftone dot screen as stencil mask.

    Converts each stencil image to a cosine dot grid where dot size varies
    with tone. Bright areas produce white dots, dark areas produce black dots.
    """

    name = "ancient_halftone"
    description = "AM halftone dot screen stencil from collage-bot"
    requires: list[str] = []

    def compose(
        self, images: list[Image.Image], params: dict, context: EffectContext
    ) -> EffectResult:
        params = self.validate_params(params)
        rng = random.Random(context.seed)
        freq = params["frequency"]
        angle = params["angle"]

        def mask_fn(img):
            return make_halftone_stencil(img, frequency=freq, angle=angle)

        return _stencil_permutations(
            images, mask_fn, apply_stencil, params["output"], rng,
            metadata_extra={"mode": "halftone", "frequency": freq, "angle": angle},
        )

    def validate_params(self, params: dict) -> dict:
        output = _validate_output(params, "ancient_halftone")
        frequency = int(params.get("frequency", 14))
        frequency = max(4, min(60, frequency))
        angle = float(params.get("angle", 45.0))
        return {"output": output, "frequency": frequency, "angle": angle}


class AncientLinescreenEffect(ComposeEffect):
    """Fixed-angle parallel line screen as stencil mask.

    Line width varies with image tone — bright areas have thin lines,
    dark areas have thick lines. Like an engraving.
    """

    name = "ancient_linescreen"
    description = "Parallel line screen stencil from collage-bot"
    requires: list[str] = []

    def compose(
        self, images: list[Image.Image], params: dict, context: EffectContext
    ) -> EffectResult:
        params = self.validate_params(params)
        rng = random.Random(context.seed)
        freq = params["frequency"]
        angle = params["angle"]

        def mask_fn(img):
            return make_linescreen_stencil_straight(img, frequency=freq, angle=angle)

        return _stencil_permutations(
            images, mask_fn, apply_stencil, params["output"], rng,
            metadata_extra={"mode": "linescreen", "frequency": freq, "angle": angle},
        )

    def validate_params(self, params: dict) -> dict:
        output = _validate_output(params, "ancient_linescreen")
        frequency = int(params.get("frequency", 30))
        frequency = max(8, min(80, frequency))
        angle = float(params.get("angle", 0.0))
        return {"output": output, "frequency": frequency, "angle": angle}


class AncientCurvyLinescreenEffect(ComposeEffect):
    """Edge-following line screen as stencil mask.

    Lines curve along image contours using gradient direction field with
    double-angle smoothing. Falls back to default angle in flat regions.
    """

    name = "ancient_curvylinescreen"
    description = "Edge-following curvy line screen stencil from collage-bot"
    requires: list[str] = []

    def compose(
        self, images: list[Image.Image], params: dict, context: EffectContext
    ) -> EffectResult:
        params = self.validate_params(params)
        rng = random.Random(context.seed)
        freq = params["frequency"]
        angle = params["angle"]

        def mask_fn(img):
            return make_linescreen_stencil_curvy(img, frequency=freq, angle=angle)

        return _stencil_permutations(
            images, mask_fn, apply_stencil, params["output"], rng,
            metadata_extra={"mode": "curvylinescreen", "frequency": freq, "angle": angle},
        )

    def validate_params(self, params: dict) -> dict:
        output = _validate_output(params, "ancient_curvylinescreen")
        frequency = int(params.get("frequency", 30))
        frequency = max(8, min(80, frequency))
        angle = float(params.get("angle", 45.0))
        return {"output": output, "frequency": frequency, "angle": angle}


class AncientReducedLinescreenEffect(ComposeEffect):
    """Adaptive-frequency horizontal line screen as stencil mask.

    Finer lines in edge/text regions (detected via Laplacian), coarser
    lines in flat areas. Phase is integrated continuously so frequency
    transitions are seamless.
    """

    name = "ancient_reducedlinescreen"
    description = "Adaptive-frequency line screen stencil from collage-bot"
    requires: list[str] = []

    def compose(
        self, images: list[Image.Image], params: dict, context: EffectContext
    ) -> EffectResult:
        params = self.validate_params(params)
        rng = random.Random(context.seed)
        freq = params["frequency"]
        freq_fine = params["freq_fine"]

        def mask_fn(img):
            return make_linescreen_stencil_reduced(
                img, frequency=freq, freq_fine=freq_fine,
            )

        return _stencil_permutations(
            images, mask_fn, apply_stencil, params["output"], rng,
            metadata_extra={
                "mode": "reducedlinescreen",
                "frequency": freq,
                "freq_fine": freq_fine,
            },
        )

    def validate_params(self, params: dict) -> dict:
        output = _validate_output(params, "ancient_reducedlinescreen")
        frequency = int(params.get("frequency", 30))
        frequency = max(8, min(80, frequency))
        freq_fine = int(params.get("freq_fine", 12))
        freq_fine = max(4, min(frequency - 1, freq_fine))
        return {"output": output, "frequency": frequency, "freq_fine": freq_fine}


# ---------------------------------------------------------------------------
# Tonal treatment + stencil (3 inputs)
# ---------------------------------------------------------------------------


class AncientCyanotypeEffect(ComposeEffect):
    """Prussian blue cyanotype tonal treatment before stencil compositing.

    Fill images get cyanotype treatment (tonal curve + highlight bloom +
    blue LUT + paper grain). Stencil image remains full color for mask
    generation.
    """

    name = "ancient_cyanotype"
    description = "Cyanotype-toned stencil compositing from collage-bot"
    requires: list[str] = []

    def compose(
        self, images: list[Image.Image], params: dict, context: EffectContext
    ) -> EffectResult:
        params = self.validate_params(params)
        rng = random.Random(context.seed)
        cyan_images = [to_cyanotype(img) for img in images]

        results: list[Image.Image] = []
        n = len(images)
        for i in range(n):
            mask = make_stencil(images[i])
            others = [j for j in range(n) if j != i]
            for perm in permutations(others):
                results.append(apply_stencil(mask, cyan_images[perm[0]], cyan_images[perm[1]]))

        meta = {"mode": "cyanotype", "output": params["output"], "total_variations": len(results)}
        if params["output"] == "random":
            chosen = rng.choice(results)
            return EffectResult(image=chosen, images=[chosen], metadata=meta)
        return EffectResult(image=results[0], images=results, metadata=meta)

    def validate_params(self, params: dict) -> dict:
        return {"output": _validate_output(params, "ancient_cyanotype")}


class AncientSilverEffect(ComposeEffect):
    """Silver gelatin print treatment before stencil compositing.

    Fill images get silver halation treatment (tonal curve + halation +
    film grain + cool blue tint). Stencil image remains full color for
    mask generation.
    """

    name = "ancient_silver"
    description = "Silver gelatin stencil compositing from collage-bot"
    requires: list[str] = []

    def compose(
        self, images: list[Image.Image], params: dict, context: EffectContext
    ) -> EffectResult:
        params = self.validate_params(params)
        rng = random.Random(context.seed)
        silver_images = [to_silver_halation(img) for img in images]

        results: list[Image.Image] = []
        n = len(images)
        for i in range(n):
            mask = make_stencil(images[i])
            others = [j for j in range(n) if j != i]
            for perm in permutations(others):
                results.append(apply_stencil(mask, silver_images[perm[0]], silver_images[perm[1]]))

        meta = {"mode": "silver", "output": params["output"], "total_variations": len(results)}
        if params["output"] == "random":
            chosen = rng.choice(results)
            return EffectResult(image=chosen, images=[chosen], metadata=meta)
        return EffectResult(image=results[0], images=results, metadata=meta)

    def validate_params(self, params: dict) -> dict:
        return {"output": _validate_output(params, "ancient_silver")}


# ---------------------------------------------------------------------------
# Edge / displacement stencil variants (3 inputs)
# ---------------------------------------------------------------------------


class AncientHalationEdgeEffect(ComposeEffect):
    """Stencil compositing with organic grain at edge boundaries.

    Instead of a hard binary edge, the transition zone between fills is
    replaced with halftone noise — creating a grainy, organic boundary.
    """

    name = "ancient_halationedge"
    description = "Organic grain-edge stencil compositing from collage-bot"
    requires: list[str] = []

    def compose(
        self, images: list[Image.Image], params: dict, context: EffectContext
    ) -> EffectResult:
        params = self.validate_params(params)
        rng = random.Random(context.seed)
        width = params["width"]

        results: list[Image.Image] = []
        n = len(images)
        for i in range(n):
            mask = make_stencil(images[i])
            others = [images[j] for j in range(n) if j != i]
            for perm in permutations(others):
                arr = blend_with_noisy_mask(mask, perm[0], perm[1], width=width)
                results.append(Image.fromarray(arr))

        meta = {
            "mode": "halationedge", "output": params["output"],
            "width": width, "total_variations": len(results),
        }
        if params["output"] == "random":
            chosen = rng.choice(results)
            return EffectResult(image=chosen, images=[chosen], metadata=meta)
        return EffectResult(image=results[0], images=results, metadata=meta)

    def validate_params(self, params: dict) -> dict:
        output = _validate_output(params, "ancient_halationedge")
        width = int(params.get("width", 10))
        width = max(2, min(40, width))
        return {"output": output, "width": width}


class AncientDisplacementEffect(ComposeEffect):
    """Gradient-based displacement warps stencil boundary and fills.

    The stencil boundary distorts and fill images stretch near the seam,
    creating a tearing effect where the two images meet.
    """

    name = "ancient_displacement"
    description = "Displacement-warped stencil compositing from collage-bot"
    requires: list[str] = []

    def compose(
        self, images: list[Image.Image], params: dict, context: EffectContext
    ) -> EffectResult:
        params = self.validate_params(params)
        rng = random.Random(context.seed)
        strength = params["strength"]
        blur = params["blur"]
        fill_falloff = params["fill_falloff"]

        results: list[Image.Image] = []
        n = len(images)
        for i in range(n):
            others = [images[j] for j in range(n) if j != i]
            for perm in permutations(others):
                result = _displacement_composite(
                    images[i], perm[0], perm[1],
                    strength=strength, blur=blur, fill_falloff=fill_falloff,
                )
                results.append(result)

        meta = {
            "mode": "displacement", "output": params["output"],
            "strength": strength, "blur": blur, "fill_falloff": fill_falloff,
            "total_variations": len(results),
        }
        if params["output"] == "random":
            chosen = rng.choice(results)
            return EffectResult(image=chosen, images=[chosen], metadata=meta)
        return EffectResult(image=results[0], images=results, metadata=meta)

    def validate_params(self, params: dict) -> dict:
        output = _validate_output(params, "ancient_displacement")
        strength = float(params.get("strength", 200.0))
        strength = max(20.0, min(600.0, strength))
        blur = float(params.get("blur", 3.0))
        blur = max(0.5, min(20.0, blur))
        fill_falloff = float(params.get("fill_falloff", 600.0))
        fill_falloff = max(50.0, min(2000.0, fill_falloff))
        return {
            "output": output, "strength": strength,
            "blur": blur, "fill_falloff": fill_falloff,
        }


# ---------------------------------------------------------------------------
# 3-level stencil (4 inputs)
# ---------------------------------------------------------------------------


class AncientQuadEffect(ComposeEffect):
    """3-level stencil compositing with percentile thresholding.

    Splits the stencil image into three brightness bands (black/grey/white)
    and fills each zone with a different source image.
    """

    name = "ancient_quad"
    description = "3-level percentile stencil compositing from collage-bot"
    requires: list[str] = []

    def compose(
        self, images: list[Image.Image], params: dict, context: EffectContext
    ) -> EffectResult:
        params = self.validate_params(params)
        rng = random.Random(context.seed)

        results: list[Image.Image] = []
        n = len(images)
        for i in range(n):
            mask = make_3level_stencil(images[i])
            others = [images[j] for j in range(n) if j != i]
            for perm in permutations(others):
                result = apply_3level_stencil(mask, perm[0], perm[1], perm[2])
                results.append(result)

        meta = {"mode": "quad", "output": params["output"], "total_variations": len(results)}
        if params["output"] == "random":
            chosen = rng.choice(results)
            return EffectResult(image=chosen, images=[chosen], metadata=meta)
        return EffectResult(image=results[0], images=results, metadata=meta)

    def validate_params(self, params: dict) -> dict:
        return {"output": _validate_output(params, "ancient_quad")}


# ---------------------------------------------------------------------------
# Single-image geometric transforms
# ---------------------------------------------------------------------------


class AncientBullseyeEffect(Effect):
    """Concentric circle cut-and-rotate.

    Cuts three concentric rings from the image, rotates each independently,
    and pastes them back. Creates a bullseye target pattern.
    """

    name = "ancient_bullseye"
    description = "Concentric circle cut-and-rotate from collage-bot"
    requires: list[str] = []

    def apply(
        self, image: Image.Image, params: dict, context: EffectContext
    ) -> EffectResult:
        random.seed(context.seed)
        result = apply_bullseye(image.convert("RGB"))
        return EffectResult(image=result, metadata={"mode": "bullseye"})

    def validate_params(self, params: dict) -> dict:
        return {}


class AncientWobbleeyeEffect(Effect):
    """Off-axis concentric ring cut-and-rotate.

    Like bullseye but each successive ring drifts from the previous center,
    creating a wobbling, misregistered target pattern.
    """

    name = "ancient_wobbleeye"
    description = "Off-axis wobble ring cut-and-rotate from collage-bot"
    requires: list[str] = []

    def apply(
        self, image: Image.Image, params: dict, context: EffectContext
    ) -> EffectResult:
        params = self.validate_params(params)
        random.seed(context.seed)
        result = apply_wobbleeye(image.convert("RGB"), rings=params["rings"])
        return EffectResult(image=result, metadata={"mode": "wobbleeye", "rings": params["rings"]})

    def validate_params(self, params: dict) -> dict:
        rings = int(params.get("rings", 5))
        rings = max(3, min(15, rings))
        return {"rings": rings}


class AncientSixshooterEffect(Effect):
    """Six circular cut-and-rotate in grid or hexagonal layout.

    Adapts layout to image aspect ratio: grid for landscape/portrait,
    hexagonal for near-square. Shuffles crops between positions.
    """

    name = "ancient_sixshooter"
    description = "Six-circle grid/hex cut-and-rotate from collage-bot"
    requires: list[str] = []

    def apply(
        self, image: Image.Image, params: dict, context: EffectContext
    ) -> EffectResult:
        random.seed(context.seed)
        result = apply_six_shooter(image.convert("RGB"))
        return EffectResult(image=result, metadata={"mode": "sixshooter"})

    def validate_params(self, params: dict) -> dict:
        return {}


class AncientBulletholeEffect(Effect):
    """Random circular cut-and-rotate holes.

    A chaos parameter controls count and size inversely: low chaos = few
    large holes, high chaos = many small holes.
    """

    name = "ancient_bullethole"
    description = "Random circular punch cut-and-rotate from collage-bot"
    requires: list[str] = []

    def apply(
        self, image: Image.Image, params: dict, context: EffectContext
    ) -> EffectResult:
        params = self.validate_params(params)
        random.seed(context.seed)
        result = apply_bullet_holes(image.convert("RGB"), chaos=params["chaos"])
        return EffectResult(image=result, metadata={"mode": "bullethole", "chaos": params["chaos"]})

    def validate_params(self, params: dict) -> dict:
        chaos = float(params.get("chaos", 0.5))
        chaos = max(0.0, min(1.0, chaos))
        return {"chaos": chaos}


class AncientKaleidoscopeEffect(Effect):
    """N-fold radial symmetry applied to concentric bullseye rings.

    Each ring gets kaleidoscope folding, creating mandala patterns.
    """

    name = "ancient_kaleidoscope"
    description = "Kaleidoscope radial symmetry from collage-bot"
    requires: list[str] = []

    def apply(
        self, image: Image.Image, params: dict, context: EffectContext
    ) -> EffectResult:
        params = self.validate_params(params)
        random.seed(context.seed)
        result = apply_kaleidoscope_bullseye(image.convert("RGB"), folds=params["folds"])
        return EffectResult(image=result, metadata={"mode": "kaleidoscope", "folds": params["folds"]})

    def validate_params(self, params: dict) -> dict:
        folds = int(params.get("folds", 6))
        folds = max(3, min(16, folds))
        return {"folds": folds}


class AncientLatheEffect(Effect):
    """Many thin concentric ring bands, each independently rotated.

    Creates a sliced-wood / agate / lathe-turned appearance with dozens
    of narrow rings.
    """

    name = "ancient_lathe"
    description = "Thin concentric ring lathe effect from collage-bot"
    requires: list[str] = []

    def apply(
        self, image: Image.Image, params: dict, context: EffectContext
    ) -> EffectResult:
        params = self.validate_params(params)
        random.seed(context.seed)
        result = apply_lathe(image.convert("RGB"), rings=params["rings"])
        return EffectResult(image=result, metadata={"mode": "lathe", "rings": params["rings"]})

    def validate_params(self, params: dict) -> dict:
        rings = int(params.get("rings", 40))
        rings = max(10, min(120, rings))
        return {"rings": rings}


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

register_effect(AncientStencilEffect())
register_effect(AncientCollageEffect())
register_effect(AncientHalftoneEffect())
register_effect(AncientLinescreenEffect())
register_effect(AncientCurvyLinescreenEffect())
register_effect(AncientReducedLinescreenEffect())
register_effect(AncientCyanotypeEffect())
register_effect(AncientSilverEffect())
register_effect(AncientHalationEdgeEffect())
register_effect(AncientDisplacementEffect())
register_effect(AncientQuadEffect())
register_effect(AncientBullseyeEffect())
register_effect(AncientWobbleeyeEffect())
register_effect(AncientSixshooterEffect())
register_effect(AncientBulletholeEffect())
register_effect(AncientKaleidoscopeEffect())
register_effect(AncientLatheEffect())
