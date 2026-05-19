"""B&W stencil Compose effect.

Ported from collage-bot-repo/bw_bot.py (vendored as vendor/collage_bot/bw_bot.py).
All 3 images converted to Otsu B&W; stencil from B&W images; fills are B&W.
"""
from PIL import Image

from sparagmos.effects import ComposeEffect, EffectContext, EffectResult, register_effect
from sparagmos.effects.stencil_utils import apply_stencil_permutations
from sparagmos.vendor.collage_bot.stencil_transform import make_stencil


class BWStencilEffect(ComposeEffect):
    name = "bw_stencil"
    description = (
        "All 3 images thresholded to hard black-and-white via Otsu; "
        "stencil and fills are both B&W. "
        "3 images → 6 permutation composites."
    )
    requires: list[str] = []

    def compose(self, images: list, params: dict, context: EffectContext) -> EffectResult:
        bw_images = [make_stencil(img).convert("RGB") for img in images]
        masks = [make_stencil(bw) for bw in bw_images]
        outputs = apply_stencil_permutations(bw_images, masks)
        return EffectResult(image=outputs[0], images=outputs, metadata={})

    def validate_params(self, params: dict) -> dict:
        return {}


register_effect(BWStencilEffect())
