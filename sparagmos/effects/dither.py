"""Dither effect — convert image to limited palette using quantization."""

from __future__ import annotations

from PIL import Image

from sparagmos.effects import ConfigError, Effect, EffectContext, EffectResult, register_effect

# Palette definitions: list of (R, G, B) tuples
_PALETTES: dict[str, list[tuple[int, int, int]]] = {
    "cga": [
        (0, 0, 0),        # black
        (0, 170, 170),    # cyan
        (170, 0, 170),    # magenta
        (170, 170, 170),  # white
    ],
    "ega": [
        (0, 0, 0),
        (0, 0, 170),
        (0, 170, 0),
        (0, 170, 170),
        (170, 0, 0),
        (170, 0, 170),
        (170, 85, 0),
        (170, 170, 170),
        (85, 85, 85),
        (85, 85, 255),
        (85, 255, 85),
        (85, 255, 255),
        (255, 85, 85),
        (255, 85, 255),
        (255, 255, 85),
        (255, 255, 255),
    ],
    "gameboy": [
        (15, 56, 15),
        (48, 98, 48),
        (139, 172, 15),
        (155, 188, 15),
    ],
    "thermal": [
        (0, 0, 0),
        (32, 0, 0),
        (80, 16, 0),
        (140, 40, 0),
        (200, 80, 0),
        (240, 140, 40),
        (255, 200, 120),
        (255, 255, 255),
    ],
}

_KNOWN_PALETTES = frozenset(_PALETTES.keys())


def _build_palette_image(colors: list[tuple[int, int, int]]) -> Image.Image:
    """Build a palette-mode Image from a list of RGB tuples for use with quantize()."""
    palette_img = Image.new("P", (1, 1))
    # PIL palette is a flat list of 768 ints (256 * 3); fill with zeros first
    flat: list[int] = []
    for color in colors:
        flat.extend(color)
    # Pad to 768 entries
    flat.extend([0] * (768 - len(flat)))
    palette_img.putpalette(flat)
    return palette_img


class DitherEffect(Effect):
    name = "dither"
    description = "Reduce to limited palette (CGA, EGA, Game Boy, thermal)"
    requires: list[str] = []

    def apply(self, image: Image.Image, params: dict, context: EffectContext) -> EffectResult:
        params = self.validate_params(params)
        palette_name: str = params["palette"]
        num_colors: int | None = params["num_colors"]

        img_rgb = image.convert("RGB")

        colors = _PALETTES[palette_name]
        if num_colors is not None:
            colors = colors[:num_colors]

        palette_img = _build_palette_image(colors)
        # quantize with dithering (dither=1 = Floyd-Steinberg)
        quantized = img_rgb.quantize(palette=palette_img, dither=1)
        out = quantized.convert("RGB")

        return EffectResult(
            image=out,
            metadata={"palette": palette_name, "num_colors": len(colors)},
        )

    def validate_params(self, params: dict) -> dict:
        palette = params.get("palette", "cga")
        if palette not in _KNOWN_PALETTES:
            raise ConfigError(
                f"palette must be one of {sorted(_KNOWN_PALETTES)!r}, got {palette!r}",
                effect_name=self.name,
                param_name="palette",
            )

        num_colors = params.get("num_colors", None)
        if num_colors is not None:
            num_colors = int(num_colors)
            max_colors = len(_PALETTES[palette])
            num_colors = max(1, min(max_colors, num_colors))

        return {"palette": palette, "num_colors": num_colors}


register_effect(DitherEffect())
