"""NetPBM effect — wraps NetPBM tools for pixel manipulation."""

from __future__ import annotations

import io
import subprocess
import warnings

from PIL import Image

from sparagmos.effects import (
    ConfigError,
    EffectContext,
    EffectResult,
    SubprocessEffect,
    register_effect,
)

_VALID_FILTERS = {"pgmcrater", "ppmspread", "pgmbentley"}


class NetPBMEffect(SubprocessEffect):
    """Apply NetPBM filter effects: pgmcrater, ppmspread, pgmbentley."""

    name = "netpbm"
    description = "NetPBM filters: crater generation, pixel spread, Bentley effect"
    requires = ["pnmtopng"]

    def _apply_ppmspread(
        self, image: Image.Image, params: dict, context: EffectContext
    ) -> Image.Image:
        amount = params["amount"]
        input_path = context.temp_dir / "netpbm_input.ppm"
        image.convert("RGB").save(input_path)

        result = self.run_command(
            ["ppmspread", str(amount), str(input_path)],
            context,
        )
        # ppmspread outputs raw PPM to stdout
        out_img = Image.open(io.BytesIO(result.stdout)).convert("RGB")
        return out_img

    def _apply_pgmbentley(
        self, image: Image.Image, params: dict, context: EffectContext
    ) -> Image.Image:
        input_path = context.temp_dir / "netpbm_input.pgm"
        image.convert("L").save(input_path)

        result = self.run_command(
            ["pgmbentley", str(input_path)],
            context,
        )
        out_img = Image.open(io.BytesIO(result.stdout)).convert("RGB")
        return out_img

    def _apply_pgmcrater(
        self, image: Image.Image, params: dict, context: EffectContext
    ) -> Image.Image:
        w, h = image.size
        # pgmcrater generates its own image; blend with original
        result = self.run_command(
            ["pgmcrater", "-width", str(w), "-height", str(h)],
            context,
        )
        crater_img = Image.open(io.BytesIO(result.stdout)).convert("L")
        # Convert crater grayscale to RGB for compositing
        crater_rgb = Image.merge("RGB", [crater_img, crater_img, crater_img])
        # Blend: 50/50 composite
        orig_rgb = image.convert("RGB")
        blended = Image.blend(orig_rgb, crater_rgb, alpha=0.5)
        return blended

    def run_command(self, cmd, context, timeout=None):
        """Override to capture stdout (NetPBM tools write to stdout)."""
        import subprocess as _sp

        timeout = timeout or self.timeout_seconds
        return _sp.run(
            cmd,
            capture_output=True,
            timeout=timeout,
            check=True,
            cwd=context.temp_dir,
        )

    def apply(self, image: Image.Image, params: dict, context: EffectContext) -> EffectResult:
        params = self.validate_params(params)
        filter_name = params["filter"]

        if filter_name == "ppmspread":
            result_image = self._apply_ppmspread(image, params, context)
        elif filter_name == "pgmbentley":
            result_image = self._apply_pgmbentley(image, params, context)
        elif filter_name == "pgmcrater":
            result_image = self._apply_pgmcrater(image, params, context)
        else:
            raise ConfigError(
                f"Unknown filter: {filter_name!r}",
                effect_name=self.name,
                param_name="filter",
            )

        return EffectResult(
            image=result_image,
            metadata={"filter": filter_name, "amount": params.get("amount", 10)},
        )

    def validate_params(self, params: dict) -> dict:
        filter_name = params.get("filter", "ppmspread")
        if filter_name not in _VALID_FILTERS:
            raise ConfigError(
                f"Invalid filter {filter_name!r}. Must be one of {sorted(_VALID_FILTERS)}",
                effect_name=self.name,
                param_name="filter",
            )
        amount = int(params.get("amount", 10))
        if amount < 1:
            amount = 1
        return {"filter": filter_name, "amount": amount}


register_effect(NetPBMEffect())
