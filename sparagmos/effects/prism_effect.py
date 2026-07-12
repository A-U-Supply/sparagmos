"""Prism effect — A's light dispersed across B.

Two-image compose: image B is the ground; image A's luminance is split
into pure spectral copies displaced progressively along a light axis and
screened onto B — A's ghost lands on B as refracted rainbow light.
Works on monochrome sources (it colorizes rather than hue-rotates).
"""

from __future__ import annotations

import colorsys

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


def _hue_rgb(t: float) -> tuple[float, float, float]:
    """Pure hue t in [0,1] -> saturated RGB in [0,1]."""
    return colorsys.hsv_to_rgb(t, 1.0, 1.0)


class PrismEffect(ComposeEffect):
    name = "prism"
    description = "Spectral dispersion — A's light split into rainbow copies and screened across B"
    requires: list[str] = []

    def compose(self, images: list[Image.Image], params: dict, context: EffectContext) -> EffectResult:
        params = self.validate_params(params)
        light_img = images[0].convert("RGB")
        ground_img = (images[1] if len(images) > 1 else images[0]).convert("RGB")
        if ground_img.size != light_img.size:
            ground_img = ground_img.resize(light_img.size, Image.LANCZOS)

        arr = np.array(light_img)
        h, w = arr.shape[:2]
        copies = params["copies"]
        theta = np.deg2rad(params["axis"])
        dx, dy = np.cos(theta), np.sin(theta)
        max_off = params["max_offset"]
        if max_off <= 1.0:
            max_off *= float(np.hypot(w, h))

        gray = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY).astype(np.float32) / 255.0
        # Only A's brighter-than-median regions emit light, so uniformly
        # bright sources don't wash the whole frame into haze.
        floor = float(np.median(gray))
        gray = np.clip((gray - floor) / max(0.15, 1.0 - floor), 0.0, 1.0)
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

        # Screen A's dispersed light onto the dimmed ground B
        ground = np.array(ground_img).astype(np.float32) * params["ground_dim"]
        out = 255.0 - (255.0 - ground) * (255.0 - acc) / 255.0
        return EffectResult(
            image=Image.fromarray(np.clip(out, 0, 255).astype(np.uint8)),
            metadata=params,
        )

    def apply(self, image: Image.Image, params: dict, context: EffectContext) -> EffectResult:
        return self.compose([image, image], params, context)

    def validate_params(self, params: dict) -> dict:
        return {
            "copies": max(3, min(12, int(params.get("copies", 7)))),
            "max_offset": max(0.005, min(400.0, float(params.get("max_offset", 0.04)))),
            "axis": float(params.get("axis", 0.0)) % 360.0,
            "ground_dim": max(0.1, min(1.0, float(params.get("ground_dim", 0.55)))),
        }


register_effect(PrismEffect())
