"""Channel shift effect — offset/swap RGB channels."""

from __future__ import annotations

import numpy as np
from PIL import Image

from sparagmos.effects import ConfigError, Effect, EffectContext, EffectResult, register_effect


class ChannelShiftEffect(Effect):
    name = "channel_shift"
    description = "Offset/swap/separate RGB channels, chromatic aberration"
    requires: list[str] = []

    def apply(self, image: Image.Image, params: dict, context: EffectContext) -> EffectResult:
        params = self.validate_params(params)
        arr = np.array(image.convert("RGB"))

        offset_r = params["offset_r"]
        offset_g = params["offset_g"]
        offset_b = params["offset_b"]

        result = np.zeros_like(arr)
        result[:, :, 0] = np.roll(arr[:, :, 0], offset_r, axis=1)
        result[:, :, 1] = np.roll(arr[:, :, 1], offset_g, axis=1)
        result[:, :, 2] = np.roll(arr[:, :, 2], offset_b, axis=1)

        return EffectResult(
            image=Image.fromarray(result),
            metadata={"offset_r": offset_r, "offset_g": offset_g, "offset_b": offset_b},
        )

    def validate_params(self, params: dict) -> dict:
        validated = {
            "offset_r": params.get("offset_r", 10),
            "offset_g": params.get("offset_g", 0),
            "offset_b": params.get("offset_b", -10),
        }
        for key in ("offset_r", "offset_g", "offset_b"):
            validated[key] = max(-500, min(500, int(validated[key])))
        return validated


register_effect(ChannelShiftEffect())
