"""Chromostereo effect — chromostereopsis depth pop.

Quantizes the image to pure saturated red and deep blue (optionally with
a black mid-band). The eye focuses long and short wavelengths at
different depths, so red regions physically float in front of blue.
"""

from __future__ import annotations

import cv2
import numpy as np
from PIL import Image

from sparagmos.effects import ConfigError, Effect, EffectContext, EffectResult, register_effect


class ChromostereoEffect(Effect):
    name = "chromostereo"
    description = "Chromostereopsis — pure red vs deep blue quantization; red optically floats above blue"
    requires: list[str] = []

    def apply(self, image: Image.Image, params: dict, context: EffectContext) -> EffectResult:
        params = self.validate_params(params)
        arr = np.array(image.convert("RGB"))
        gray = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY).astype(np.float32)
        # Normalize so the band split follows this image's own range
        lo, hi = np.percentile(gray, 2), np.percentile(gray, 98)
        gray = np.clip((gray - lo) / max(1.0, hi - lo), 0.0, 1.0)

        s = params["saturation"]
        red = np.array([255.0 * s, 20.0 * (1 - s), 30.0 * (1 - s)])
        blue = np.array([15.0 * (1 - s), 20.0 * (1 - s), 200.0 * s + 55.0 * (1 - s)])
        black = np.array([4.0, 2.0, 8.0])

        out = np.empty_like(arr, dtype=np.float32)
        if params["bands"] == 2:
            hi, lo = gray >= 0.5, gray < 0.5
        else:
            hi, lo = gray >= 0.62, gray < 0.34
            out[~(hi | lo)] = black

        red_zone, blue_zone = (lo, hi) if params["invert"] else (hi, lo)
        out[red_zone] = red
        out[blue_zone] = blue

        return EffectResult(image=Image.fromarray(out.astype(np.uint8)), metadata=params)

    def validate_params(self, params: dict) -> dict:
        return {
            "bands": max(2, min(3, int(params.get("bands", 2)))),
            "invert": bool(params.get("invert", False)),
            "saturation": max(0.6, min(1.0, float(params.get("saturation", 1.0)))),
        }


register_effect(ChromostereoEffect())
