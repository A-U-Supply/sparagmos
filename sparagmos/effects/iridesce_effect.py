"""Iridesce effect — oil-slick / thin-film interference sheen.

Maps a cyclic interference palette onto the image's luminance gradient,
so color shifts with surface "curvature" the way light does on a soap
bubble or a gasoline film. From the glim batch: the stacks survey found
nothing saturated or luminous in the corpus.
"""

from __future__ import annotations

import cv2
import numpy as np
from PIL import Image

from sparagmos.effects import ConfigError, Effect, EffectContext, EffectResult, register_effect


def _film_palette(t: np.ndarray) -> np.ndarray:
    """Cyclic thin-film palette: t in [0,1) -> float RGB in [0,255]."""
    two_pi = 2.0 * np.pi
    r = 0.5 + 0.5 * np.cos(two_pi * t)
    g = 0.5 + 0.5 * np.cos(two_pi * t - 2.1)
    b = 0.5 + 0.5 * np.cos(two_pi * t - 4.2)
    return np.stack([r, g, b], axis=-1) * 255.0


class IridesceEffect(Effect):
    name = "iridesce"
    description = "Oil-slick sheen — thin-film interference palette driven by the luminance gradient"
    requires: list[str] = []

    def apply(self, image: Image.Image, params: dict, context: EffectContext) -> EffectResult:
        params = self.validate_params(params)
        arr = np.array(image.convert("RGB")).astype(np.float32)
        gray = cv2.cvtColor(arr.astype(np.uint8), cv2.COLOR_RGB2GRAY).astype(np.float32)
        gray = cv2.GaussianBlur(gray, (0, 0), sigmaX=params["scale"])

        gx = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=5)
        gy = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=5)
        orientation = np.arctan2(gy, gx) / (2.0 * np.pi) + 0.5  # [0,1)
        magnitude = np.sqrt(gx * gx + gy * gy)
        mag_hi = np.percentile(magnitude, 98)
        if mag_hi < 1e-6:
            mag_hi = 1.0
        magnitude = np.clip(magnitude / mag_hi, 0.0, 1.0)

        # Film "thickness": orientation sets the base color, magnitude and
        # local brightness sweep it through the interference cycle.
        t = (orientation + magnitude * 1.5 + gray / 255.0 * 0.75 + params["phase"]) % 1.0
        film = _film_palette(t)

        # Blend the film over the original, weighted by strength and gradient
        # magnitude. Screen where the film is bright, multiply where dark, so
        # the slick reads as saturated color rather than a pale sheen.
        weight = (params["strength"] * (0.55 + 0.45 * magnitude))[:, :, None]
        screened = 255.0 - (255.0 - arr) * (255.0 - film) / 255.0
        overlaid = np.where(film > 128.0, screened, arr * film / 128.0)
        out = arr * (1.0 - weight) + overlaid * weight

        return EffectResult(
            image=Image.fromarray(np.clip(out, 0, 255).astype(np.uint8)),
            metadata=params,
        )

    def validate_params(self, params: dict) -> dict:
        return {
            "strength": max(0.0, min(1.0, float(params.get("strength", 0.65)))),
            "scale": max(1.0, min(60.0, float(params.get("scale", 9.0)))),
            "phase": float(params.get("phase", 0.0)) % 1.0,
        }


register_effect(IridesceEffect())
