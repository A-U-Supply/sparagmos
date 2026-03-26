"""Format roundtrip effect — chain of lossy format conversions."""

from __future__ import annotations

import io
import shutil
import warnings
from pathlib import Path

from PIL import Image

from sparagmos.effects import (
    ConfigError,
    EffectContext,
    EffectResult,
    SubprocessEffect,
    register_effect,
)

_VALID_FORMATS = {"jpeg", "bmp", "potrace"}


def _jpeg_roundtrip(image: Image.Image, quality: int) -> Image.Image:
    buf = io.BytesIO()
    image.convert("RGB").save(buf, format="JPEG", quality=quality)
    buf.seek(0)
    return Image.open(buf).convert("RGB")


def _bmp_roundtrip(image: Image.Image, tmp_dir: Path) -> Image.Image:
    path = tmp_dir / "roundtrip_bmp.bmp"
    image.convert("RGB").save(path, format="BMP")
    return Image.open(path).convert("RGB")


def _potrace_roundtrip(
    image: Image.Image, tmp_dir: Path, context: EffectContext
) -> Image.Image:
    """Convert to bitmap, trace with potrace, render back.

    Falls back to returning the thresholded image if potrace or cairosvg
    is not available.
    """
    # Threshold to 1-bit bitmap
    gray = image.convert("L")
    bw = gray.point(lambda p: 255 if p > 128 else 0, "1")

    pbm_path = tmp_dir / "potrace_input.pbm"
    svg_path = tmp_dir / "potrace_output.svg"
    bw.save(pbm_path)

    if shutil.which("potrace") is None:
        warnings.warn(
            "potrace not found — skipping potrace step in format_roundtrip",
            stacklevel=2,
        )
        return image.convert("RGB")

    import subprocess

    try:
        subprocess.run(
            ["potrace", "--svg", "-o", str(svg_path), str(pbm_path)],
            capture_output=True,
            check=True,
            timeout=30,
        )
    except subprocess.CalledProcessError as exc:
        warnings.warn(f"potrace failed: {exc.stderr.decode()[:200]}", stacklevel=2)
        return image.convert("RGB")

    # Try cairosvg to rasterize; fall back to convert (ImageMagick) or identity
    w, h = image.size
    try:
        import cairosvg

        png_bytes = cairosvg.svg2png(
            url=str(svg_path), output_width=w, output_height=h
        )
        return Image.open(io.BytesIO(png_bytes)).convert("RGB")
    except ImportError:
        pass

    # Try ImageMagick as fallback rasterizer
    if shutil.which("convert") is not None or shutil.which("magick") is not None:
        png_path = tmp_dir / "potrace_raster.png"
        cmd_base = ["magick", "convert"] if shutil.which("magick") else ["convert"]
        try:
            subprocess.run(
                cmd_base + [str(svg_path), str(png_path)],
                capture_output=True,
                check=True,
                timeout=30,
            )
            return Image.open(png_path).convert("RGB")
        except subprocess.CalledProcessError:
            pass

    warnings.warn(
        "No SVG rasterizer available (install cairosvg or ImageMagick) — "
        "returning thresholded image",
        stacklevel=2,
    )
    return bw.convert("RGB")


class FormatRoundtripEffect(SubprocessEffect):
    """Chain of lossy format conversions to introduce compression artefacts."""

    name = "format_roundtrip"
    description = "Chain lossy format conversions: JPEG, BMP, potrace"
    requires: list[str] = []

    def apply(self, image: Image.Image, params: dict, context: EffectContext) -> EffectResult:
        params = self.validate_params(params)
        current = image.convert("RGB")
        chain = params["chain"]
        jpeg_quality = params["jpeg_quality"]

        applied: list[str] = []
        for fmt in chain:
            if fmt == "jpeg":
                current = _jpeg_roundtrip(current, jpeg_quality)
                applied.append("jpeg")
            elif fmt == "bmp":
                current = _bmp_roundtrip(current, context.temp_dir)
                applied.append("bmp")
            elif fmt == "potrace":
                current = _potrace_roundtrip(current, context.temp_dir, context)
                applied.append("potrace")
            else:
                warnings.warn(f"Unknown format {fmt!r} in chain — skipping", stacklevel=2)

        return EffectResult(
            image=current,
            metadata={"chain_applied": applied, "jpeg_quality": jpeg_quality},
        )

    def validate_params(self, params: dict) -> dict:
        chain = list(params.get("chain", ["jpeg", "bmp", "jpeg"]))
        jpeg_quality = int(params.get("jpeg_quality", 10))
        jpeg_quality = max(1, min(95, jpeg_quality))

        for fmt in chain:
            if fmt not in _VALID_FORMATS:
                raise ConfigError(
                    f"Unknown format {fmt!r} in chain. Valid: {sorted(_VALID_FORMATS)}",
                    effect_name=self.name,
                    param_name="chain",
                )

        return {"chain": chain, "jpeg_quality": jpeg_quality}


register_effect(FormatRoundtripEffect())
