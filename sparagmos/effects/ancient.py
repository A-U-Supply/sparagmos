"""Ancient effects — adapter wrapping A-U-Supply/collage-bot transforms.

Vendored source: sparagmos/vendor/collage_bot/
Update: git subtree pull --prefix sparagmos/vendor/collage_bot \
    https://github.com/A-U-Supply/collage-bot.git main --squash

To add a new mode from collage-bot:
  1. Pull latest with the command above
  2. Add a new ComposeEffect subclass below (~20-30 lines)
  3. Add a new recipe YAML in recipes/ancients-<mode>.yaml
"""

from __future__ import annotations

import random
from itertools import permutations

from PIL import Image

from sparagmos.effects import (
    ComposeEffect,
    ConfigError,
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

VALID_OUTPUTS = {"all", "random"}


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
        output_mode: str = params["output"]
        rng = random.Random(context.seed)

        results: list[Image.Image] = []
        n = len(images)

        for i in range(n):
            mask = make_stencil(images[i])
            others = [images[j] for j in range(n) if j != i]
            for perm in permutations(others):
                composite = apply_stencil(mask, perm[0], perm[1])
                results.append(composite)

        if output_mode == "random":
            chosen = rng.choice(results)
            return EffectResult(
                image=chosen,
                images=[chosen],
                metadata={
                    "mode": "stencil",
                    "output": "random",
                    "total_variations": len(results),
                },
            )

        return EffectResult(
            image=results[0],
            images=results,
            metadata={
                "mode": "stencil",
                "output": "all",
                "total_variations": len(results),
            },
        )

    def validate_params(self, params: dict) -> dict:
        output = params.get("output", "all")
        if output not in VALID_OUTPUTS:
            raise ConfigError(
                f"Unknown output mode: {output!r}. Valid: {sorted(VALID_OUTPUTS)}",
                effect_name="ancient_stencil",
                param_name="output",
            )
        return {"output": output}


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
        output = params.get("output", "all")
        if output not in VALID_OUTPUTS:
            raise ConfigError(
                f"Unknown output mode: {output!r}. Valid: {sorted(VALID_OUTPUTS)}",
                effect_name="ancient_collage",
                param_name="output",
            )
        split = float(params.get("split", 0.25))
        split = max(0.05, min(0.45, split))
        blend_width = int(params.get("blend_width", 70))
        blend_width = max(1, min(200, blend_width))
        return {"output": output, "split": split, "blend_width": blend_width}


register_effect(AncientStencilEffect())
register_effect(AncientCollageEffect())
