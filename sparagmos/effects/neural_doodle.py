"""Neural doodle effect — simulated semantic style painting.

Simulates neural doodle by dividing the image into random regions (circles
and rectangles) and applying distinct style treatments to each, mimicking
the region-based style transfer approach without requiring neural inference.
"""

from __future__ import annotations

import numpy as np
from PIL import Image, ImageFilter

from sparagmos.effects import ConfigError, Effect, EffectContext, EffectResult, register_effect

_TRANSFORMS = ("hue_shift", "posterize", "blur", "sharpen", "invert")


class NeuralDoodleEffect(Effect):
    name = "neural_doodle"
    description = "Simulated semantic region-based style painting"
    requires: list[str] = []

    def validate_params(self, params: dict) -> dict:
        num_regions = int(params.get("num_regions", 5))
        num_regions = max(1, min(20, num_regions))

        region_size = float(params.get("region_size", 0.3))
        region_size = max(0.1, min(0.5, region_size))

        intensity = float(params.get("intensity", 0.8))
        intensity = max(0.0, min(1.0, intensity))

        return {
            "num_regions": num_regions,
            "region_size": region_size,
            "intensity": intensity,
        }

    def apply(self, image: Image.Image, params: dict, context: EffectContext) -> EffectResult:
        params = self.validate_params(params)
        num_regions = params["num_regions"]
        region_size = params["region_size"]
        intensity = params["intensity"]

        rng = np.random.default_rng(context.seed)

        img_rgb = image.convert("RGB")
        h, w = img_rgb.size[1], img_rgb.size[0]
        base = np.array(img_rgb, dtype=np.float32)
        composite = base.copy()

        # radius in pixels derived from region_size fraction
        radius = int(region_size * min(h, w) / 2)
        radius = max(radius, 2)

        for i in range(num_regions):
            # Choose shape: circle if even index, rectangle if odd
            use_circle = (i % 2 == 0)
            cx = int(rng.integers(0, w))
            cy = int(rng.integers(0, h))

            # Build mask
            mask = np.zeros((h, w), dtype=np.float32)
            if use_circle:
                ys, xs = np.ogrid[:h, :w]
                dist = np.sqrt((xs - cx) ** 2 + (ys - cy) ** 2)
                mask[dist <= radius] = 1.0
            else:
                x1 = max(0, cx - radius)
                x2 = min(w, cx + radius)
                y1 = max(0, cy - radius)
                y2 = min(h, cy + radius)
                mask[y1:y2, x1:x2] = 1.0

            if mask.sum() == 0:
                continue

            # Pick transform for this region
            transform = _TRANSFORMS[i % len(_TRANSFORMS)]
            transformed = self._apply_transform(img_rgb, transform, rng)
            t_arr = np.array(transformed, dtype=np.float32)

            # Blend transformed region into composite
            m3 = mask[:, :, np.newaxis] * intensity
            composite = composite * (1.0 - m3) + t_arr * m3

        result_arr = np.clip(composite, 0, 255).astype(np.uint8)
        return EffectResult(
            image=Image.fromarray(result_arr),
            metadata={
                "num_regions": num_regions,
                "region_size": region_size,
                "intensity": intensity,
            },
        )

    def _apply_transform(
        self, img: Image.Image, transform: str, rng: np.random.Generator
    ) -> Image.Image:
        """Apply one of the style transforms to the full image (masking done by caller)."""
        if transform == "hue_shift":
            return self._hue_shift(img, rng)
        elif transform == "posterize":
            return self._posterize(img, rng)
        elif transform == "blur":
            radius = float(rng.uniform(2.0, 6.0))
            return img.filter(ImageFilter.GaussianBlur(radius=radius))
        elif transform == "sharpen":
            # Multiple sharpen passes for a harsh glitch look
            result = img
            for _ in range(int(rng.integers(2, 5))):
                result = result.filter(ImageFilter.SHARPEN)
            return result
        else:  # invert
            arr = np.array(img, dtype=np.float32)
            return Image.fromarray((255.0 - arr).clip(0, 255).astype(np.uint8))

    def _hue_shift(self, img: Image.Image, rng: np.random.Generator) -> Image.Image:
        """Shift hue by rotating RGB channels with a random offset."""
        arr = np.array(img, dtype=np.float32)
        shift = float(rng.uniform(30.0, 120.0))
        # Rotate hue by mixing channels
        r, g, b = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2]
        t = shift / 120.0  # 0..1 over 120-degree steps
        new_r = np.clip(r * (1 - t) + g * t, 0, 255)
        new_g = np.clip(g * (1 - t) + b * t, 0, 255)
        new_b = np.clip(b * (1 - t) + r * t, 0, 255)
        result = np.stack([new_r, new_g, new_b], axis=2).astype(np.uint8)
        return Image.fromarray(result)

    def _posterize(self, img: Image.Image, rng: np.random.Generator) -> Image.Image:
        """Reduce color depth to simulate flat regions."""
        levels = int(rng.integers(2, 5))
        arr = np.array(img, dtype=np.float32)
        # Quantize each channel to `levels` steps
        step = 255.0 / (levels - 1) if levels > 1 else 255.0
        quantized = np.round(arr / step) * step
        return Image.fromarray(np.clip(quantized, 0, 255).astype(np.uint8))


register_effect(NeuralDoodleEffect())
