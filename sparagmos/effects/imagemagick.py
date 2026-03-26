"""ImageMagick effect — wraps the `convert` command for various distortions."""

from __future__ import annotations

import shutil
from pathlib import Path

from PIL import Image

from sparagmos.effects import (
    ConfigError,
    EffectContext,
    EffectResult,
    SubprocessEffect,
    register_effect,
)

_VALID_PRESETS = {"implode", "swirl", "wave", "plasma_overlay", "fx_noise"}


def _find_convert() -> list[str]:
    """Return the convert command prefix, trying `magick convert` first."""
    if shutil.which("magick") is not None:
        return ["magick", "convert"]
    return ["convert"]


class ImageMagickEffect(SubprocessEffect):
    """Apply ImageMagick distortions via the `convert` CLI."""

    name = "imagemagick"
    description = "ImageMagick convert distortions: implode, swirl, wave, plasma_overlay, fx_noise"
    requires = ["convert"]

    def check_dependencies(self) -> list[str]:
        """Accept either `convert` or `magick` as satisfying the dependency."""
        if shutil.which("convert") is not None or shutil.which("magick") is not None:
            return []
        return ["convert"]

    def _build_flags(self, params: dict, w: int, h: int) -> list[str]:
        preset = params["preset"]
        if preset == "implode":
            return ["-implode", str(params["amount"])]
        if preset == "swirl":
            return ["-swirl", str(params["degrees"])]
        if preset == "wave":
            return ["-wave", f"{params['amplitude']}x{params['wavelength']}"]
        if preset == "plasma_overlay":
            return [
                "-size", f"{w}x{h}",
                "plasma:",
                "-compose", "overlay",
                "-composite",
            ]
        if preset == "fx_noise":
            return ["-fx", "p+0.1*rand()"]
        raise ConfigError(f"Unknown preset: {preset!r}", effect_name=self.name, param_name="preset")

    def apply(self, image: Image.Image, params: dict, context: EffectContext) -> EffectResult:
        params = self.validate_params(params)
        image = image.convert("RGB")
        w, h = image.size

        input_path = self.save_temp_image(image, context, suffix=".png")
        output_path = context.temp_dir / "output_imagemagick.png"

        flags = self._build_flags(params, w, h)
        base_cmd = _find_convert()

        if params["preset"] == "plasma_overlay":
            # plasma_overlay: input first, then size/plasma/compose/composite flags
            cmd = base_cmd + [str(input_path)] + flags + [str(output_path)]
        else:
            cmd = base_cmd + [str(input_path)] + flags + [str(output_path)]

        self.run_command(cmd, context)
        result_image = self.load_temp_image(output_path)
        return EffectResult(
            image=result_image,
            metadata={"preset": params["preset"]},
        )

    def validate_params(self, params: dict) -> dict:
        preset = params.get("preset", "swirl")
        if preset not in _VALID_PRESETS:
            raise ConfigError(
                f"Invalid preset {preset!r}. Must be one of {sorted(_VALID_PRESETS)}",
                effect_name=self.name,
                param_name="preset",
            )
        validated: dict = {"preset": preset}

        if preset == "implode":
            amount = float(params.get("amount", 0.5))
            validated["amount"] = amount
        elif preset == "swirl":
            degrees = float(params.get("degrees", 90))
            validated["degrees"] = degrees
        elif preset == "wave":
            validated["amplitude"] = int(params.get("amplitude", 10))
            validated["wavelength"] = int(params.get("wavelength", 50))
        elif preset == "plasma_overlay":
            pass  # no extra params
        elif preset == "fx_noise":
            pass  # no extra params

        return validated


register_effect(ImageMagickEffect())
