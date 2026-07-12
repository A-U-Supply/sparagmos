"""Chromostereo effect — two images at two optical depths.

Two-image compose: image A's bright shapes become the pure-red plane,
image B's bright shapes the deep-blue plane, everything else black.
Chromostereopsis makes the red plane physically float in front of the
blue — A hovers over B.
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


def _bright_mask(img: Image.Image, size: tuple[int, int], cutoff: float) -> np.ndarray:
    if img.size != size:
        img = img.resize(size, Image.LANCZOS)
    gray = cv2.cvtColor(np.array(img.convert("RGB")), cv2.COLOR_RGB2GRAY).astype(np.float32)
    lo, hi = np.percentile(gray, 2), np.percentile(gray, 98)
    gray = np.clip((gray - lo) / max(1.0, hi - lo), 0.0, 1.0)
    return gray >= cutoff


class ChromostereoEffect(ComposeEffect):
    name = "chromostereo"
    description = "Chromostereopsis — A's shapes on the red plane float in front of B's shapes on the blue plane"
    requires: list[str] = []

    def compose(self, images: list[Image.Image], params: dict, context: EffectContext) -> EffectResult:
        params = self.validate_params(params)
        front_img = images[0].convert("RGB")
        back_img = (images[1] if len(images) > 1 else images[0]).convert("RGB")
        if params["invert"]:
            front_img, back_img = back_img, front_img

        size = front_img.size
        front = _bright_mask(front_img, size, params["cutoff"])
        back = _bright_mask(back_img, size, params["cutoff"]) & ~front

        s = params["saturation"]
        red = np.array([255.0 * s, 20.0 * (1 - s), 30.0 * (1 - s)])
        blue = np.array([15.0 * (1 - s), 20.0 * (1 - s), 200.0 * s + 55.0 * (1 - s)])

        w, h = size
        out = np.empty((h, w, 3), dtype=np.float32)
        out[:] = (4.0, 2.0, 8.0)
        out[back] = blue
        out[front] = red

        return EffectResult(image=Image.fromarray(out.astype(np.uint8)), metadata=params)

    def apply(self, image: Image.Image, params: dict, context: EffectContext) -> EffectResult:
        return self.compose([image, image], params, context)

    def validate_params(self, params: dict) -> dict:
        return {
            "cutoff": max(0.3, min(0.8, float(params.get("cutoff", 0.55)))),
            "invert": bool(params.get("invert", False)),
            "saturation": max(0.6, min(1.0, float(params.get("saturation", 1.0)))),
        }


register_effect(ChromostereoEffect())
