"""Seam carving — content-aware resize via energy-based seam removal."""

from __future__ import annotations

import numpy as np
from PIL import Image

from sparagmos.effects import ConfigError, Effect, EffectContext, EffectResult, register_effect

_PROTECT_MODES = ("none", "vision", "invert")


class SeamCarveEffect(Effect):
    """Content-aware resize using seam carving.

    Removes minimum-energy vertical (and horizontal) seams to shrink the image.
    Intentionally misconfigured for artistic destruction: remove too many seams
    to produce extreme distortion.
    """

    name = "seam_carve"
    description = "Content-aware seam carving resize — destruction by intelligent removal"
    requires: list[str] = []

    # --- energy computation ---

    @staticmethod
    def _energy(arr: np.ndarray) -> np.ndarray:
        """Compute pixel energy as gradient magnitude (Sobel-like)."""
        gray = 0.299 * arr[:, :, 0] + 0.587 * arr[:, :, 1] + 0.114 * arr[:, :, 2]
        # Horizontal gradient: forward diff with wrap handling
        gx = np.abs(np.roll(gray, -1, axis=1) - gray)
        gy = np.abs(np.roll(gray, -1, axis=0) - gray)
        return gx + gy

    @staticmethod
    def _find_seam(energy: np.ndarray) -> np.ndarray:
        """Find minimum-energy vertical seam via dynamic programming.

        Returns an array of column indices, one per row.
        """
        h, w = energy.shape
        dp = energy.copy()
        backtrack = np.zeros_like(dp, dtype=np.int32)

        for row in range(1, h):
            for col in range(w):
                left = dp[row - 1, max(col - 1, 0)]
                mid = dp[row - 1, col]
                right = dp[row - 1, min(col + 1, w - 1)]
                min_prev = min(left, mid, right)
                dp[row, col] += min_prev
                if min_prev == left and col > 0:
                    backtrack[row, col] = col - 1
                elif min_prev == right and col < w - 1:
                    backtrack[row, col] = col + 1
                else:
                    backtrack[row, col] = col

        # Trace back from minimum in last row
        seam = np.zeros(h, dtype=np.int32)
        seam[-1] = int(np.argmin(dp[-1]))
        for row in range(h - 2, -1, -1):
            seam[row] = backtrack[row + 1, seam[row + 1]]

        return seam

    @staticmethod
    def _remove_seam(arr: np.ndarray, seam: np.ndarray) -> np.ndarray:
        """Remove a vertical seam from the image array."""
        h, w = arr.shape[:2]
        channels = arr.shape[2] if arr.ndim == 3 else 1
        out_shape = (h, w - 1, channels) if arr.ndim == 3 else (h, w - 1)
        out = np.zeros(out_shape, dtype=arr.dtype)

        for row in range(h):
            col = seam[row]
            if arr.ndim == 3:
                out[row] = np.concatenate([arr[row, :col], arr[row, col + 1:]], axis=0)
            else:
                out[row] = np.concatenate([arr[row, :col], arr[row, col + 1:]])

        return out

    def _carve_width(
        self, arr: np.ndarray, target_w: int, invert: bool
    ) -> np.ndarray:
        """Remove seams until width equals target_w."""
        while arr.shape[1] > target_w:
            energy = self._energy(arr)
            if invert:
                # Invert: remove high-energy seams first (maximum destruction)
                energy = energy.max() - energy
            seam = self._find_seam(energy)
            arr = self._remove_seam(arr, seam)
        return arr

    def _carve_height(
        self, arr: np.ndarray, target_h: int, invert: bool
    ) -> np.ndarray:
        """Remove seams in height dimension by transposing."""
        arr = arr.transpose(1, 0, 2)
        arr = self._carve_width(arr, target_h, invert)
        return arr.transpose(1, 0, 2)

    def apply(self, image: Image.Image, params: dict, context: EffectContext) -> EffectResult:
        params = self.validate_params(params)

        img = image.convert("RGB")
        arr = np.array(img)

        h, w = arr.shape[:2]
        target_w = max(1, int(w * params["scale_x"]))
        target_h = max(1, int(h * params["scale_y"]))

        protect = params["protect_regions"]
        # "vision" mode: passthrough for now (vision data is unstructured text)
        # "invert": invert energy map so interesting features are carved first
        invert = protect == "invert"

        if target_w < w:
            arr = self._carve_width(arr, target_w, invert)
        if target_h < h:
            arr = self._carve_height(arr, target_h, invert)

        result = Image.fromarray(arr.astype(np.uint8))

        return EffectResult(
            image=result,
            metadata={
                "scale_x": params["scale_x"],
                "scale_y": params["scale_y"],
                "protect_regions": protect,
                "original_size": (w, h),
                "output_size": result.size,
            },
        )

    def validate_params(self, params: dict) -> dict:
        validated = {
            "scale_x": float(params.get("scale_x", 0.7)),
            "scale_y": float(params.get("scale_y", 1.0)),
            "protect_regions": str(params.get("protect_regions", "none")),
        }
        if not (0.0 < validated["scale_x"] <= 1.0):
            raise ConfigError(
                f"scale_x must be in (0, 1], got {validated['scale_x']}",
                effect_name=self.name,
                param_name="scale_x",
            )
        if not (0.0 < validated["scale_y"] <= 1.0):
            raise ConfigError(
                f"scale_y must be in (0, 1], got {validated['scale_y']}",
                effect_name=self.name,
                param_name="scale_y",
            )
        if validated["protect_regions"] not in _PROTECT_MODES:
            raise ConfigError(
                f"protect_regions must be one of {_PROTECT_MODES}, "
                f"got {validated['protect_regions']!r}",
                effect_name=self.name,
                param_name="protect_regions",
            )
        return validated


register_effect(SeamCarveEffect())
