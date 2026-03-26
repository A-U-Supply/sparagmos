"""CRT/VHS composite effect — scan lines, horizontal jitter, color bleeding, phosphor glow."""

from __future__ import annotations

import random

import numpy as np
import scipy.ndimage
from PIL import Image

from sparagmos.effects import ConfigError, Effect, EffectContext, EffectResult, register_effect


class CrtVhsEffect(Effect):
    name = "crt_vhs"
    description = "Composite CRT/VHS effect: scan lines, jitter, color bleed, phosphor glow"
    requires: list[str] = []

    def apply(self, image: Image.Image, params: dict, context: EffectContext) -> EffectResult:
        params = self.validate_params(params)
        scan_line_density: int = params["scan_line_density"]
        jitter_amount: int = params["jitter_amount"]
        color_bleed: float = params["color_bleed"]
        phosphor_glow: float = params["phosphor_glow"]

        rng = random.Random(context.seed)

        arr = np.array(image.convert("RGB"), dtype=np.float32)
        h, w = arr.shape[:2]

        # --- Scan lines: darken every Nth row ---
        if scan_line_density > 0:
            for row in range(0, h, scan_line_density):
                arr[row] *= 0.4

        # --- Horizontal jitter: shift random rows left/right ---
        if jitter_amount > 0:
            num_jitter_rows = max(1, h // 10)
            for _ in range(num_jitter_rows):
                row = rng.randint(0, h - 1)
                shift = rng.randint(-jitter_amount, jitter_amount)
                if shift != 0:
                    arr[row] = np.roll(arr[row], shift, axis=0)

        # --- Color bleeding: blur Cb/Cr channels in YCbCr space ---
        if color_bleed > 0:
            # Convert float32 arr to uint8 for YCbCr conversion
            pil_tmp = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), "RGB")
            ycbcr = np.array(pil_tmp.convert("YCbCr"), dtype=np.float32)
            # Blur only Cb and Cr channels
            ycbcr[:, :, 1] = scipy.ndimage.gaussian_filter(ycbcr[:, :, 1], sigma=color_bleed)
            ycbcr[:, :, 2] = scipy.ndimage.gaussian_filter(ycbcr[:, :, 2], sigma=color_bleed)
            bleed_pil = Image.fromarray(np.clip(ycbcr, 0, 255).astype(np.uint8), "YCbCr")
            arr = np.array(bleed_pil.convert("RGB"), dtype=np.float32)

        # --- Phosphor glow: add blurred version at low opacity ---
        if phosphor_glow > 0:
            blurred = scipy.ndimage.gaussian_filter(arr, sigma=[2, 2, 0])
            arr = arr + blurred * phosphor_glow

        out = np.clip(arr, 0, 255).astype(np.uint8)
        return EffectResult(
            image=Image.fromarray(out, "RGB"),
            metadata={
                "scan_line_density": scan_line_density,
                "jitter_amount": jitter_amount,
                "color_bleed": color_bleed,
                "phosphor_glow": phosphor_glow,
            },
        )

    def validate_params(self, params: dict) -> dict:
        scan_line_density = int(params.get("scan_line_density", 3))
        scan_line_density = max(0, scan_line_density)

        jitter_amount = int(params.get("jitter_amount", 2))
        jitter_amount = max(0, jitter_amount)

        color_bleed = float(params.get("color_bleed", 1.5))
        color_bleed = max(0.0, color_bleed)

        phosphor_glow = float(params.get("phosphor_glow", 0.1))
        phosphor_glow = max(0.0, min(1.0, phosphor_glow))

        return {
            "scan_line_density": scan_line_density,
            "jitter_amount": jitter_amount,
            "color_bleed": color_bleed,
            "phosphor_glow": phosphor_glow,
        }


register_effect(CrtVhsEffect())
