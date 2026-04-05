"""Primitive effect — wraps the `primitive` Go binary for geometric reconstruction."""

from __future__ import annotations

from PIL import Image

from sparagmos.effects import (
    ConfigError,
    EffectContext,
    EffectResult,
    SubprocessEffect,
    register_effect,
)

_SHAPE_TYPES: dict[str, int] = {
    "triangle": 1,
    "rectangle": 2,
    "ellipse": 3,
    "circle": 4,
    "rotated_rect": 5,
}


class PrimitiveEffect(SubprocessEffect):
    """Reconstruct image using geometric shapes via the `primitive` binary."""

    name = "primitive"
    description = "Geometric shape reconstruction using the primitive Go tool"
    requires = ["primitive"]

    def apply(self, image: Image.Image, params: dict, context: EffectContext) -> EffectResult:
        params = self.validate_params(params)
        image = image.convert("RGB")

        input_path = self.save_temp_image(image, context, suffix=".png")
        output_path = context.temp_dir / "output_primitive.png"

        mode = _SHAPE_TYPES[params["shape_type"]]
        cmd = [
            "primitive",
            "-i", str(input_path),
            "-o", str(output_path),
            "-n", str(params["shapes"]),
            "-m", str(mode),
            "-a", str(params["alpha"]),
        ]
        self.run_command(cmd, context)
        result_image = self.load_temp_image(output_path)

        # primitive may output at a different size — resize to match input
        if result_image.size != image.size:
            result_image = result_image.resize(image.size, Image.LANCZOS)

        return EffectResult(
            image=result_image,
            metadata={
                "shapes": params["shapes"],
                "shape_type": params["shape_type"],
                "alpha": params["alpha"],
            },
        )

    def validate_params(self, params: dict) -> dict:
        shape_type = params.get("shape_type", "triangle")
        if shape_type not in _SHAPE_TYPES:
            raise ConfigError(
                f"Invalid shape_type {shape_type!r}. Must be one of {sorted(_SHAPE_TYPES)}",
                effect_name=self.name,
                param_name="shape_type",
            )
        shapes = int(params.get("shapes", 50))
        if shapes < 1:
            raise ConfigError(
                "shapes must be >= 1",
                effect_name=self.name,
                param_name="shapes",
            )
        alpha = int(params.get("alpha", 128))
        alpha = max(0, min(255, alpha))

        return {"shapes": shapes, "shape_type": shape_type, "alpha": alpha}


register_effect(PrimitiveEffect())
