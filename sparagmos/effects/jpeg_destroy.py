"""JPEG destruction — multi-generation lossy compression."""

from __future__ import annotations

import io

from PIL import Image

from sparagmos.effects import Effect, EffectContext, EffectResult, register_effect


class JpegDestroyEffect(Effect):
    name = "jpeg_destroy"
    description = "Multi-generation JPEG compression — generational loss as art"
    requires: list[str] = []

    def apply(self, image: Image.Image, params: dict, context: EffectContext) -> EffectResult:
        params = self.validate_params(params)
        quality = params["quality"]
        iterations = params["iterations"]

        current = image.convert("RGB")
        for _ in range(iterations):
            buffer = io.BytesIO()
            current.save(buffer, format="JPEG", quality=quality)
            buffer.seek(0)
            current = Image.open(buffer).convert("RGB")
            # Force load so the buffer can be reused
            current.load()

        return EffectResult(
            image=current,
            metadata={"quality": quality, "iterations": iterations},
        )

    def validate_params(self, params: dict) -> dict:
        quality = params.get("quality", 5)
        quality = max(1, min(95, int(quality)))

        iterations = params.get("iterations", 10)
        iterations = max(1, min(100, int(iterations)))

        return {"quality": quality, "iterations": iterations}


register_effect(JpegDestroyEffect())
