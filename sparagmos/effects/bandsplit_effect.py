"""Bandsplit effect — hybrid image (the Einstein/Marilyn illusion).

Low spatial frequencies of image A + high frequencies of image B.
Seen small or squinted, the output IS A; seen full-size, B's detail
takes over. Slack thumbnails vs expanded view make this interactive.
"""

from __future__ import annotations

import cv2
import numpy as np
from PIL import Image

from sparagmos.effects import (
    ComposeEffect,
    ConfigError,
    EffectContext,
    EffectResult,
    register_effect,
)


MAX_EDGE = 2048


class BandsplitEffect(ComposeEffect):
    name = "bandsplit"
    description = "Hybrid image — lowpass of A + highpass of B; identity changes with viewing distance"
    requires: list[str] = []

    def compose(self, images: list[Image.Image], params: dict, context: EffectContext) -> EffectResult:
        params = self.validate_params(params)
        base = images[0].convert("RGB")
        detail = (images[1] if len(images) > 1 else images[0]).convert("RGB")
        if max(base.size) > MAX_EDGE:
            base = base.copy()
            base.thumbnail((MAX_EDGE, MAX_EDGE))
        if detail.size != base.size:
            detail = detail.resize(base.size, Image.LANCZOS)

        a = np.array(base).astype(np.float32)
        b = np.array(detail).astype(np.float32)

        low = cv2.GaussianBlur(a, (0, 0), sigmaX=params["sigma_low"])
        high = b - cv2.GaussianBlur(b, (0, 0), sigmaX=params["sigma_high"])
        out = low + high * params["high_gain"]

        # Gentle renormalize toward full range without crushing the lowpass
        out = np.clip(out, 0, 255)
        return EffectResult(image=Image.fromarray(out.astype(np.uint8)), metadata=params)

    def apply(self, image: Image.Image, params: dict, context: EffectContext) -> EffectResult:
        return self.compose([image, image], params, context)

    def validate_params(self, params: dict) -> dict:
        return {
            "sigma_low": max(4.0, min(48.0, float(params.get("sigma_low", 14.0)))),
            "sigma_high": max(0.8, min(12.0, float(params.get("sigma_high", 3.0)))),
            "high_gain": max(0.3, min(3.0, float(params.get("high_gain", 1.2)))),
        }


register_effect(BandsplitEffect())
