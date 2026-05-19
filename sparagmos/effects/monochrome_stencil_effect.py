"""Monochrome stencil Compose effect.

Ported from collage-bot-repo/monochrome_bot.py (vendored as vendor/collage_bot/monochrome_bot.py).
Stencil from original full-color images; fills converted to silver gelatin monochrome.
"""
from PIL import Image

from sparagmos.effects import ComposeEffect, EffectContext, EffectResult, register_effect
from sparagmos.effects.stencil_utils import apply_stencil_permutations
from sparagmos.vendor.collage_bot.monochrome_bot import to_silver_gelatin
from sparagmos.vendor.collage_bot.stencil_transform import make_stencil


class MonochromeStencilEffect(ComposeEffect):
    name = "monochrome_stencil"
    description = (
        "Stencil generated from each original image via Otsu threshold; "
        "fills converted to silver gelatin monochrome (CLAHE + unsharp mask). "
        "3 images → 6 permutation composites."
    )
    requires: list[str] = []

    def compose(self, images: list, params: dict, context: EffectContext) -> EffectResult:
        mono_images = [to_silver_gelatin(img) for img in images]
        masks = [make_stencil(img) for img in images]
        outputs = apply_stencil_permutations(mono_images, masks)
        return EffectResult(image=outputs[0], images=outputs, metadata={})

    def validate_params(self, params: dict) -> dict:
        return {}


register_effect(MonochromeStencilEffect())
