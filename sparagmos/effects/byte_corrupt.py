"""Byte corruption effect — corrupt raw pixel data by flipping, injecting, or replacing bytes."""

from __future__ import annotations

import random
from typing import Literal

import numpy as np
from PIL import Image

from sparagmos.effects import ConfigError, Effect, EffectContext, EffectResult, register_effect

_MODES = ("flip", "inject", "replace")


class ByteCorruptEffect(Effect):
    name = "byte_corrupt"
    description = "Corrupt raw pixel bytes by flipping, injecting, or replacing"
    requires: list[str] = []

    def apply(self, image: Image.Image, params: dict, context: EffectContext) -> EffectResult:
        params = self.validate_params(params)
        num_flips: int = params["num_flips"]
        skip_header: int = params["skip_header"]
        mode: str = params["mode"]

        rng = random.Random(context.seed)

        img_rgb = image.convert("RGB")
        raw = bytearray(img_rgb.tobytes())
        n = len(raw)

        if skip_header >= n:
            # Nothing to corrupt — return as-is
            return EffectResult(
                image=img_rgb,
                metadata={"mode": mode, "num_flips": 0, "bytes_total": n},
            )

        work_region_len = n - skip_header

        if mode == "flip":
            for _ in range(num_flips):
                idx = skip_header + rng.randint(0, work_region_len - 1)
                raw[idx] ^= rng.randint(0, 255)

        elif mode == "inject":
            # Insert random bytes — to keep length constant, also remove bytes
            for _ in range(num_flips):
                insert_pos = skip_header + rng.randint(0, work_region_len - 1)
                raw.insert(insert_pos, rng.randint(0, 255))
                # Remove last byte to keep length stable
                if len(raw) > n:
                    raw.pop()

        elif mode == "replace":
            for _ in range(num_flips):
                start = skip_header + rng.randint(0, work_region_len - 1)
                length = rng.randint(1, max(1, work_region_len // 100))
                end = min(n, start + length)
                for i in range(start, end):
                    raw[i] = rng.randint(0, 255)

        # Ensure length matches (safety net for inject mode edge cases)
        if len(raw) != n:
            raw = raw[:n]

        out_arr = np.frombuffer(bytes(raw), dtype=np.uint8).reshape(img_rgb.height, img_rgb.width, 3)
        out_image = Image.fromarray(out_arr, mode="RGB")

        return EffectResult(
            image=out_image,
            metadata={"mode": mode, "num_flips": num_flips, "bytes_total": n},
        )

    def validate_params(self, params: dict) -> dict:
        num_flips = int(params.get("num_flips", 100))
        num_flips = max(0, min(10000, num_flips))

        skip_header = int(params.get("skip_header", 0))
        skip_header = max(0, skip_header)

        mode = params.get("mode", "flip")
        if mode not in _MODES:
            raise ConfigError(
                f"mode must be one of {_MODES!r}, got {mode!r}",
                effect_name=self.name,
                param_name="mode",
            )

        return {"num_flips": num_flips, "skip_header": skip_header, "mode": mode}


register_effect(ByteCorruptEffect())
