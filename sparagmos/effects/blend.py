"""Blend compositing effect — pixel-level blending of two images."""

from __future__ import annotations

import numpy as np
from PIL import Image

from sparagmos.effects import (
    ComposeEffect,
    ConfigError,
    EffectContext,
    EffectResult,
    register_effect,
)

VALID_MODES = {"opacity", "multiply", "screen", "overlay", "difference", "add", "subtract"}


def _apply_blend_mode(base: np.ndarray, over: np.ndarray, mode: str) -> np.ndarray:
    """Apply blend mode math on float32 arrays in [0, 255] range.

    Args:
        base: Base image array, float32, shape (H, W, C), values [0, 255].
        over: Overlay image array, same shape and dtype as base.
        mode: One of the VALID_MODES strings.

    Returns:
        Blended float32 array in [0, 255] range, same shape as inputs.
    """
    if mode == "opacity":
        return over.copy()
    elif mode == "multiply":
        return base * over / 255.0
    elif mode == "screen":
        return 255.0 - (255.0 - base) * (255.0 - over) / 255.0
    elif mode == "overlay":
        result = np.where(
            base < 128,
            2.0 * base * over / 255.0,
            255.0 - 2.0 * (255.0 - base) * (255.0 - over) / 255.0,
        )
        return result
    elif mode == "difference":
        return np.abs(base - over)
    elif mode == "add":
        return np.minimum(base + over, 255.0)
    elif mode == "subtract":
        return np.maximum(base - over, 0.0)
    else:
        raise ConfigError(f"Unknown blend mode: {mode!r}", effect_name="blend", param_name="mode")


class BlendEffect(ComposeEffect):
    """Combine exactly two images through photographic blend modes.

    Examples:
        >>> effect = BlendEffect()
        >>> result = effect.compose([base_img, overlay_img], {"mode": "screen"}, ctx)
    """

    name = "blend"
    description = "Pixel-level blending of two images"
    requires: list[str] = []

    def compose(
        self, images: list[Image.Image], params: dict, context: EffectContext
    ) -> EffectResult:
        """Blend two images together using the specified mode.

        Args:
            images: List of exactly two PIL Images. The first is the base,
                the second is the overlay. If only one image is provided,
                it is returned as-is. If overlay is a different size, it
                is resized (LANCZOS) to match the base.
            params: Effect parameters (mode, strength, offset_x, offset_y).
            context: Shared pipeline context.

        Returns:
            EffectResult with blended image.
        """
        params = self.validate_params(params)
        mode: str = params["mode"]
        strength: float = params["strength"]
        offset_x: float = params["offset_x"]
        offset_y: float = params["offset_y"]

        base_img = images[0].convert("RGB")

        # Single-image passthrough
        if len(images) < 2:
            return EffectResult(image=base_img, metadata={"mode": mode})

        over_img = images[1].convert("RGB")
        base_w, base_h = base_img.size

        # Resize overlay to match base if needed
        if over_img.size != base_img.size:
            over_img = over_img.resize((base_w, base_h), Image.LANCZOS)

        base = np.array(base_img, dtype=np.float32)
        over_full = np.array(over_img, dtype=np.float32)

        # Compute pixel offsets
        shift_x = int(round(offset_x * base_w))
        shift_y = int(round(offset_y * base_h))

        # Build a canvas where the overlay is shifted; uncovered areas show base
        over_shifted = np.empty_like(base)
        over_shifted[:] = base  # default: base shows through where overlay absent

        # Compute source/dest slices for the overlay
        if shift_x >= 0:
            src_x_start, src_x_end = 0, base_w - shift_x
            dst_x_start, dst_x_end = shift_x, base_w
        else:
            src_x_start, src_x_end = -shift_x, base_w
            dst_x_start, dst_x_end = 0, base_w + shift_x

        if shift_y >= 0:
            src_y_start, src_y_end = 0, base_h - shift_y
            dst_y_start, dst_y_end = shift_y, base_h
        else:
            src_y_start, src_y_end = -shift_y, base_h
            dst_y_start, dst_y_end = 0, base_h + shift_y

        # Only copy if the slices are non-empty
        if (
            src_x_start < src_x_end
            and src_y_start < src_y_end
            and dst_x_start < dst_x_end
            and dst_y_start < dst_y_end
        ):
            over_shifted[dst_y_start:dst_y_end, dst_x_start:dst_x_end] = over_full[
                src_y_start:src_y_end, src_x_start:src_x_end
            ]

        # Build a blend mask: True where the overlay actually covers
        mask = np.zeros((base_h, base_w), dtype=bool)
        if (
            dst_x_start < dst_x_end
            and dst_y_start < dst_y_end
        ):
            mask[dst_y_start:dst_y_end, dst_x_start:dst_x_end] = True

        # Apply blend mode only where overlay covers
        blended_covered = _apply_blend_mode(
            base[dst_y_start:dst_y_end, dst_x_start:dst_x_end],
            over_full[src_y_start:src_y_end, src_x_start:src_x_end],
            mode,
        )

        # Compose result: start from base, apply blend where overlay covers
        result = base.copy()
        if mask.any():
            covered_base = base[dst_y_start:dst_y_end, dst_x_start:dst_x_end]
            result[dst_y_start:dst_y_end, dst_x_start:dst_x_end] = (
                covered_base + strength * (blended_covered - covered_base)
            )

        result = np.clip(result, 0, 255).astype(np.uint8)
        return EffectResult(
            image=Image.fromarray(result),
            metadata={"mode": mode, "strength": strength, "offset_x": offset_x, "offset_y": offset_y},
        )

    def validate_params(self, params: dict) -> dict:
        """Validate and normalize blend parameters.

        Args:
            params: Raw parameters dict.

        Returns:
            Normalized parameters with defaults applied.

        Raises:
            ConfigError: If mode is not a recognized blend mode.
        """
        mode = params.get("mode", "opacity")
        if mode not in VALID_MODES:
            raise ConfigError(
                f"Unknown blend mode: {mode!r}. Valid modes: {sorted(VALID_MODES)}",
                effect_name="blend",
                param_name="mode",
            )

        strength = float(params.get("strength", 0.5))
        strength = max(0.0, min(1.0, strength))

        offset_x = float(params.get("offset_x", 0.0))
        offset_x = max(-0.5, min(0.5, offset_x))

        offset_y = float(params.get("offset_y", 0.0))
        offset_y = max(-0.5, min(0.5, offset_y))

        return {
            "mode": mode,
            "strength": strength,
            "offset_x": offset_x,
            "offset_y": offset_y,
        }


register_effect(BlendEffect())
