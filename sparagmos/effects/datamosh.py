"""Datamosh effect — simulate video encoding corruption artifacts."""

from __future__ import annotations

import numpy as np
from PIL import Image

from sparagmos.effects import ConfigError, Effect, EffectContext, EffectResult, register_effect

_VALID_MODES = ("iframe_remove", "mv_swap")


class DatamoshEffect(Effect):
    """Simulate datamosh artifacts by corrupting macroblock data."""

    name = "datamosh"
    description = "Simulate datamosh video corruption: iframe removal, motion vector swap"
    requires: list[str] = []

    def apply(self, image: Image.Image, params: dict, context: EffectContext) -> EffectResult:
        params = self.validate_params(params)
        mode = params["mode"]
        corruption_amount = params["corruption_amount"]
        block_size = params["block_size"]

        arr = np.array(image.convert("RGB"), dtype=np.uint8)
        rng = np.random.default_rng(context.seed)

        if mode == "iframe_remove":
            result = self._iframe_remove(arr, corruption_amount, block_size, rng)
        else:
            result = self._mv_swap(arr, corruption_amount, block_size, rng)

        return EffectResult(
            image=Image.fromarray(result, mode="RGB"),
            metadata={"mode": mode, "corruption_amount": corruption_amount, "block_size": block_size},
        )

    def _iframe_remove(
        self,
        arr: np.ndarray,
        corruption_amount: float,
        block_size: int,
        rng: np.random.Generator,
    ) -> np.ndarray:
        """Shift random macroblocks as if predicted from wrong reference frame."""
        result = arr.copy()
        h, w = arr.shape[:2]

        blocks_y = max(1, h // block_size)
        blocks_x = max(1, w // block_size)
        n_blocks = blocks_y * blocks_x
        n_corrupt = max(1, int(n_blocks * corruption_amount))

        # Pick random blocks to corrupt
        block_indices = rng.choice(n_blocks, size=n_corrupt, replace=False)

        for idx in block_indices:
            by = idx // blocks_x
            bx = idx % blocks_x
            y0 = by * block_size
            x0 = bx * block_size
            y1 = min(y0 + block_size, h)
            x1 = min(x0 + block_size, w)

            # Random displacement (motion vector pointing somewhere else)
            dy = rng.integers(-h // 2, h // 2)
            dx = rng.integers(-w // 2, w // 2)
            src_y0 = int(np.clip(y0 + dy, 0, h - (y1 - y0)))
            src_x0 = int(np.clip(x0 + dx, 0, w - (x1 - x0)))
            src_y1 = src_y0 + (y1 - y0)
            src_x1 = src_x0 + (x1 - x0)

            result[y0:y1, x0:x1] = arr[src_y0:src_y1, src_x0:src_x1]

        return result

    def _mv_swap(
        self,
        arr: np.ndarray,
        corruption_amount: float,
        block_size: int,
        rng: np.random.Generator,
    ) -> np.ndarray:
        """Corrupt motion vectors — shift rectangular regions by random amounts."""
        result = arr.copy()
        h, w = arr.shape[:2]

        n_regions = max(1, int((h * w) / (block_size * block_size) * corruption_amount))

        for _ in range(n_regions):
            # Random region
            rh = rng.integers(block_size, max(block_size + 1, h // 2))
            rw = rng.integers(block_size, max(block_size + 1, w // 2))
            ry = rng.integers(0, max(1, h - rh))
            rx = rng.integers(0, max(1, w - rw))

            # Random shift
            sy = rng.integers(-h // 4, h // 4)
            sx = rng.integers(-w // 4, w // 4)

            dy = int(np.clip(ry + sy, 0, h - rh))
            dx = int(np.clip(rx + sx, 0, w - rw))

            result[ry : ry + rh, rx : rx + rw] = arr[dy : dy + rh, dx : dx + rw]

        return result

    def validate_params(self, params: dict) -> dict:
        mode = params.get("mode", "iframe_remove")
        if mode not in _VALID_MODES:
            raise ConfigError(
                f"mode must be one of {_VALID_MODES}, got {mode!r}",
                effect_name=self.name,
                param_name="mode",
            )
        corruption_amount = float(params.get("corruption_amount", 0.3))
        corruption_amount = max(0.0, min(1.0, corruption_amount))
        block_size = int(params.get("block_size", 16))
        block_size = max(1, block_size)
        return {"mode": mode, "corruption_amount": corruption_amount, "block_size": block_size}


register_effect(DatamoshEffect())
