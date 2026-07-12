"""Prism effect — spectral dispersion.

Splits the image into hue-rotated copies displaced progressively along a
light axis, so every edge fringes into a full rainbow — light through a
prism rather than VHS chromatic aberration.
"""

from __future__ import annotations

import cv2
import numpy as np
from PIL import Image

from sparagmos.effects import ConfigError, Effect, EffectContext, EffectResult, register_effect


def _hue_rgb(t: float) -> tuple[float, float, float]:
    """Pure hue t in [0,1] -> saturated RGB in [0,1]."""
    import colorsys

    return colorsys.hsv_to_rgb(t, 1.0, 1.0)


class PrismEffect(Effect):
    name = "prism"
    description = "Spectral dispersion — hue-rotated copies smeared along a light axis, edges fringe into rainbows"
    requires: list[str] = []

    def apply(self, image: Image.Image, params: dict, context: EffectContext) -> EffectResult:
        params = self.validate_params(params)
        arr = np.array(image.convert("RGB"))
        h, w = arr.shape[:2]
        copies = params["copies"]
        theta = np.deg2rad(params["axis"])
        dx, dy = np.cos(theta), np.sin(theta)
        # max_offset <= 1.0 means a fraction of the diagonal, else pixels
        max_off = params["max_offset"]
        if max_off <= 1.0:
            max_off *= float(np.hypot(w, h))

        # Tint the luminance with a pure spectral color per copy: works on
        # any source, including monochrome (hue rotation would be a no-op).
        gray = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY).astype(np.float32) / 255.0
        acc = np.zeros((h, w, 3), dtype=np.float32)
        for i in range(copies):
            frac = i / max(1, copies - 1)
            hue = frac * 0.83  # red -> violet, not wrapping back to red
            spectral = np.array(_hue_rgb(hue), dtype=np.float32) * 255.0
            copy = gray[:, :, None] * spectral[None, None, :]
            off = (frac - 0.5) * 2.0 * max_off
            m = np.float32([[1, 0, off * dx], [0, 1, off * dy]])
            copy = cv2.warpAffine(copy, m, (w, h), borderMode=cv2.BORDER_REFLECT)
            # Lighten-accumulate: keeps each spectral copy fully saturated
            falloff = 1.0 - 0.35 * abs(frac - 0.5) * 2.0
            acc = np.maximum(acc, copy * falloff)

        base = arr.astype(np.float32)
        out = base * params["keep_base"] + acc * (1.0 - params["keep_base"])
        return EffectResult(
            image=Image.fromarray(np.clip(out, 0, 255).astype(np.uint8)),
            metadata=params,
        )

    def validate_params(self, params: dict) -> dict:
        return {
            "copies": max(3, min(12, int(params.get("copies", 7)))),
            "max_offset": max(0.005, min(400.0, float(params.get("max_offset", 0.04)))),
            "axis": float(params.get("axis", 0.0)) % 360.0,
            "keep_base": max(0.0, min(1.0, float(params.get("keep_base", 0.35)))),
        }


register_effect(PrismEffect())
