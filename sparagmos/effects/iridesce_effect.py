"""Iridesce effect — oil-slick / thin-film interference sheen.

Two-image compose: image A is the surface dipped in oil, image B is the
light — B's luminance gradient drives the interference film that plays
across A, so B's shapes are visible only as shifts in the sheen. With a
single image the film comes from the image's own gradient.
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


def _film_palette(t: np.ndarray) -> np.ndarray:
    """Cyclic thin-film palette: t in [0,1) -> float RGB in [0,255]."""
    two_pi = 2.0 * np.pi
    r = 0.5 + 0.5 * np.cos(two_pi * t)
    g = 0.5 + 0.5 * np.cos(two_pi * t - 2.1)
    b = 0.5 + 0.5 * np.cos(two_pi * t - 4.2)
    return np.stack([r, g, b], axis=-1) * 255.0


class IridesceEffect(ComposeEffect):
    name = "iridesce"
    description = "Oil-slick sheen on A driven by B's luminance gradient — B is the light on A's surface"
    requires: list[str] = []

    def compose(self, images: list[Image.Image], params: dict, context: EffectContext) -> EffectResult:
        params = self.validate_params(params)
        surface = images[0].convert("RGB")
        light = (images[1] if len(images) > 1 else images[0]).convert("RGB")
        if light.size != surface.size:
            light = light.resize(surface.size, Image.LANCZOS)

        arr = np.array(surface).astype(np.float32)
        gray = cv2.cvtColor(np.array(light), cv2.COLOR_RGB2GRAY).astype(np.float32)
        gray = cv2.GaussianBlur(gray, (0, 0), sigmaX=params["scale"])

        gx = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=5)
        gy = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=5)
        orientation = np.arctan2(gy, gx) / (2.0 * np.pi) + 0.5  # [0,1)
        magnitude = np.sqrt(gx * gx + gy * gy)
        mag_hi = np.percentile(magnitude, 98)
        if mag_hi < 1e-6:
            mag_hi = 1.0
        magnitude = np.clip(magnitude / mag_hi, 0.0, 1.0)

        # Film "thickness": B's gradient orientation sets the base color;
        # its magnitude and brightness sweep it through the cycle.
        t = (orientation + magnitude * 1.5 + gray / 255.0 * 0.75 + params["phase"]) % 1.0
        film = _film_palette(t)

        # Blend the film over A, weighted by strength and B's gradient
        # magnitude. Screen where the film is bright, multiply where dark,
        # so the slick reads as saturated color rather than a pale sheen.
        weight = (params["strength"] * (0.55 + 0.45 * magnitude))[:, :, None]
        screened = 255.0 - (255.0 - arr) * (255.0 - film) / 255.0
        overlaid = np.where(film > 128.0, screened, arr * film / 128.0)
        out = arr * (1.0 - weight) + overlaid * weight

        return EffectResult(
            image=Image.fromarray(np.clip(out, 0, 255).astype(np.uint8)),
            metadata=params,
        )

    def apply(self, image: Image.Image, params: dict, context: EffectContext) -> EffectResult:
        return self.compose([image, image], params, context)

    def validate_params(self, params: dict) -> dict:
        return {
            "strength": max(0.0, min(1.0, float(params.get("strength", 0.65)))),
            "scale": max(1.0, min(60.0, float(params.get("scale", 9.0)))),
            "phase": float(params.get("phase", 0.0)) % 1.0,
        }


register_effect(IridesceEffect())
