"""Pixel sorting effect — sort rows/columns by brightness, hue, or saturation."""

from __future__ import annotations

import numpy as np
from PIL import Image

from sparagmos.effects import ConfigError, Effect, EffectContext, EffectResult, register_effect

VALID_MODES = ("brightness", "hue", "saturation")
VALID_DIRECTIONS = ("horizontal", "vertical")


def _get_sort_key(pixel_row: np.ndarray, mode: str) -> np.ndarray:
    """Compute sort key for a row of RGB pixels."""
    r, g, b = pixel_row[:, 0].astype(float), pixel_row[:, 1].astype(float), pixel_row[:, 2].astype(float)
    if mode == "brightness":
        return 0.299 * r + 0.587 * g + 0.114 * b
    elif mode == "hue":
        max_c = np.maximum(np.maximum(r, g), b)
        min_c = np.minimum(np.minimum(r, g), b)
        delta = max_c - min_c
        hue = np.zeros_like(delta)
        mask = delta > 0
        # Red dominant
        rm = mask & (max_c == r)
        hue[rm] = (60 * ((g[rm] - b[rm]) / delta[rm]) % 360)
        # Green dominant
        gm = mask & (max_c == g)
        hue[gm] = (60 * ((b[gm] - r[gm]) / delta[gm]) + 120)
        # Blue dominant
        bm = mask & (max_c == b)
        hue[bm] = (60 * ((r[bm] - g[bm]) / delta[bm]) + 240)
        return hue
    elif mode == "saturation":
        max_c = np.maximum(np.maximum(r, g), b)
        min_c = np.minimum(np.minimum(r, g), b)
        sat = np.zeros_like(max_c)
        mask = max_c > 0
        sat[mask] = (max_c[mask] - min_c[mask]) / max_c[mask]
        return sat
    return np.zeros(len(pixel_row))


def _sort_row(row: np.ndarray, mode: str, threshold_low: float, threshold_high: float) -> np.ndarray:
    """Sort a single row of pixels within threshold bounds."""
    keys = _get_sort_key(row, mode)
    key_max = keys.max() if keys.max() > 0 else 1.0
    normalized = keys / key_max

    result = row.copy()
    in_segment = False
    start = 0

    for i in range(len(normalized)):
        if threshold_low <= normalized[i] <= threshold_high:
            if not in_segment:
                start = i
                in_segment = True
        else:
            if in_segment:
                segment = result[start:i]
                seg_keys = keys[start:i]
                order = np.argsort(seg_keys)
                result[start:i] = segment[order]
                in_segment = False

    # Handle final segment
    if in_segment:
        segment = result[start:]
        seg_keys = keys[start:]
        order = np.argsort(seg_keys)
        result[start:] = segment[order]

    return result


class PixelSortEffect(Effect):
    name = "pixel_sort"
    description = "Sort pixel rows/columns by brightness, hue, or saturation"
    requires: list[str] = []

    def apply(self, image: Image.Image, params: dict, context: EffectContext) -> EffectResult:
        params = self.validate_params(params)
        arr = np.array(image.convert("RGB"))

        mode = params["mode"]
        direction = params["direction"]
        threshold_low = params["threshold_low"]
        threshold_high = params["threshold_high"]

        if direction == "vertical":
            arr = arr.transpose(1, 0, 2)

        for i in range(arr.shape[0]):
            arr[i] = _sort_row(arr[i], mode, threshold_low, threshold_high)

        if direction == "vertical":
            arr = arr.transpose(1, 0, 2)

        return EffectResult(
            image=Image.fromarray(arr),
            metadata={"mode": mode, "direction": direction},
        )

    def validate_params(self, params: dict) -> dict:
        mode = params.get("mode", "brightness")
        if mode not in VALID_MODES:
            raise ConfigError(
                f"Invalid mode {mode!r}. Must be one of {VALID_MODES}",
                effect_name=self.name,
                param_name="mode",
            )

        direction = params.get("direction", "horizontal")
        if direction not in VALID_DIRECTIONS:
            raise ConfigError(
                f"Invalid direction {direction!r}. Must be one of {VALID_DIRECTIONS}",
                effect_name=self.name,
                param_name="direction",
            )

        threshold_low = float(params.get("threshold_low", 0.25))
        threshold_high = float(params.get("threshold_high", 0.75))
        threshold_low = max(0.0, min(1.0, threshold_low))
        threshold_high = max(0.0, min(1.0, threshold_high))

        return {
            "mode": mode,
            "direction": direction,
            "threshold_low": threshold_low,
            "threshold_high": threshold_high,
        }


register_effect(PixelSortEffect())
