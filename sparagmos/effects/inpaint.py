"""Inpaint effect — mask regions and regenerate with OpenCV inpainting.

Uses cv2.inpaint() (INPAINT_TELEA or INPAINT_NS) to "heal" masked regions,
producing surreal smooth patches within otherwise detailed images. cv2 is
imported lazily so the module loads gracefully even if OpenCV is absent.
"""

from __future__ import annotations

import numpy as np
from PIL import Image

from sparagmos.effects import ConfigError, Effect, EffectContext, EffectResult, register_effect

_VALID_MASK_MODES = ("random_rect", "random_circle", "vision")
_VALID_METHODS = ("telea", "ns")


class InpaintEffect(Effect):
    name = "inpaint"
    description = "OpenCV inpainting — masks regions and regenerates them"
    requires: list[str] = []

    def validate_params(self, params: dict) -> dict:
        mask_mode = params.get("mask_mode", "random_rect")
        if mask_mode not in _VALID_MASK_MODES:
            raise ConfigError(
                f"mask_mode must be one of {_VALID_MASK_MODES}, got {mask_mode!r}",
                effect_name=self.name,
                param_name="mask_mode",
            )

        mask_size = float(params.get("mask_size", 0.2))
        mask_size = max(0.05, min(0.5, mask_size))

        method = params.get("method", "telea")
        if method not in _VALID_METHODS:
            raise ConfigError(
                f"method must be one of {_VALID_METHODS}, got {method!r}",
                effect_name=self.name,
                param_name="method",
            )

        num_masks = int(params.get("num_masks", 3))
        num_masks = max(1, min(10, num_masks))

        return {
            "mask_mode": mask_mode,
            "mask_size": mask_size,
            "method": method,
            "num_masks": num_masks,
        }

    def apply(self, image: Image.Image, params: dict, context: EffectContext) -> EffectResult:
        import cv2  # lazy import — raises ImportError if OpenCV not installed

        params = self.validate_params(params)
        mask_mode = params["mask_mode"]
        mask_size = params["mask_size"]
        method = params["method"]
        num_masks = params["num_masks"]

        rng = np.random.default_rng(context.seed)

        img_rgb = image.convert("RGB")
        arr = np.array(img_rgb)
        h, w = arr.shape[:2]

        # Build combined mask (uint8, 0=keep, 255=inpaint)
        mask = self._build_mask(mask_mode, mask_size, num_masks, h, w, rng, context)

        cv2_method = cv2.INPAINT_TELEA if method == "telea" else cv2.INPAINT_NS
        # inpaintRadius: controls how far neighbours are sampled
        inpaint_radius = max(3, int(mask_size * min(h, w) * 0.1))
        result_arr = cv2.inpaint(arr, mask, inpaintRadius=inpaint_radius, flags=cv2_method)

        return EffectResult(
            image=Image.fromarray(result_arr),
            metadata={
                "mask_mode": mask_mode,
                "mask_size": mask_size,
                "method": method,
                "num_masks": num_masks,
                "mask_coverage": float(mask.sum()) / (h * w * 255),
            },
        )

    def _build_mask(
        self,
        mask_mode: str,
        mask_size: float,
        num_masks: int,
        h: int,
        w: int,
        rng: np.random.Generator,
        context: EffectContext,
    ) -> np.ndarray:
        """Build a uint8 mask array (0=keep, 255=inpaint)."""
        mask = np.zeros((h, w), dtype=np.uint8)
        # region half-size in pixels
        half = max(1, int(mask_size * min(h, w) / 2))

        # "vision" mode falls back to random placement since vision is unstructured text
        use_rect = mask_mode in ("random_rect", "vision")

        for _ in range(num_masks):
            cx = int(rng.integers(0, w))
            cy = int(rng.integers(0, h))
            if use_rect:
                x1, x2 = max(0, cx - half), min(w, cx + half)
                y1, y2 = max(0, cy - half), min(h, cy + half)
                mask[y1:y2, x1:x2] = 255
            else:  # random_circle
                ys, xs = np.ogrid[:h, :w]
                dist = np.sqrt((xs - cx) ** 2 + (ys - cy) ** 2)
                mask[dist <= half] = 255

        return mask


register_effect(InpaintEffect())
