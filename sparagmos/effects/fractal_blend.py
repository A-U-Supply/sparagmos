"""Fractal blend effect — Mandelbrot set derived from image histogram, blended with original."""

from __future__ import annotations

import numpy as np
from PIL import Image

from sparagmos.effects import ConfigError, Effect, EffectContext, EffectResult, register_effect

_VALID_COLORMAPS = ("hot", "cool", "grayscale")


def _image_histogram_stats(image: Image.Image) -> tuple[float, float, float, float]:
    """Extract histogram statistics from the image.

    Returns:
        (mean_hue, mean_brightness, hue_std, brightness_std) all in [0, 1].
    """
    hsv = image.convert("RGB").convert("HSV") if hasattr(Image, "HSV") else None
    rgb_arr = np.array(image.convert("RGB"), dtype=np.float32) / 255.0

    # Brightness = mean of V channel (max of R,G,B)
    brightness = np.max(rgb_arr, axis=2)
    mean_brightness = float(brightness.mean())
    brightness_std = float(brightness.std())

    # Hue approximation: use arctan2 of (G-B, R-G) in [0, 1]
    r, g, b = rgb_arr[:, :, 0], rgb_arr[:, :, 1], rgb_arr[:, :, 2]
    hue_angle = np.arctan2(g - b, r - g)  # range roughly -pi to pi
    mean_hue = float((hue_angle.mean() + np.pi) / (2 * np.pi))  # normalise to [0,1]
    hue_std = float(hue_angle.std() / np.pi)  # normalise std

    return mean_hue, mean_brightness, hue_std, brightness_std


def _generate_mandelbrot(
    width: int,
    height: int,
    center_real: float,
    center_imag: float,
    zoom: float,
    max_iter: int,
) -> np.ndarray:
    """Generate a Mandelbrot escape-count array.

    Args:
        width, height: Output dimensions.
        center_real: Real coordinate of viewport center.
        center_imag: Imaginary coordinate of viewport center.
        zoom: Pixels per unit in complex plane (higher = more zoomed in).
        max_iter: Maximum escape iterations.

    Returns:
        2D array of iteration counts (0..max_iter), float normalised to [0, 1].
    """
    zoom = max(zoom, 1e-10)  # guard against division by zero

    # Build coordinate grids
    half_w = width / 2.0
    half_h = height / 2.0
    real = np.linspace(center_real - half_w / zoom, center_real + half_w / zoom, width)
    imag = np.linspace(center_imag - half_h / zoom, center_imag + half_h / zoom, height)
    C = real[np.newaxis, :] + 1j * imag[:, np.newaxis]

    Z = np.zeros_like(C)
    count = np.zeros(C.shape, dtype=np.float32)
    active = np.ones(C.shape, dtype=bool)

    for _ in range(max_iter):
        Z[active] = Z[active] ** 2 + C[active]
        escaped = active & (np.abs(Z) > 2.0)
        count[escaped] += 1.0
        active[escaped] = False

    # Normalise to [0, 1]
    if count.max() > 0:
        count /= count.max()
    return count


def _apply_colormap(data: np.ndarray, colormap: str) -> np.ndarray:
    """Map a normalised 2D float array to an RGB uint8 array."""
    if colormap == "hot":
        r = np.clip(data * 3.0, 0, 1)
        g = np.clip(data * 3.0 - 1.0, 0, 1)
        b = np.clip(data * 3.0 - 2.0, 0, 1)
        rgb = np.stack([r, g, b], axis=-1)
    elif colormap == "cool":
        r = np.clip(1.0 - data, 0, 1)
        g = np.clip(data, 0, 1)
        b = np.ones_like(data)
        rgb = np.stack([r, g, b], axis=-1)
    else:  # grayscale
        rgb = np.stack([data, data, data], axis=-1)
    return (rgb * 255).astype(np.uint8)


class FractalBlendEffect(Effect):
    """Generate Mandelbrot set from image histogram statistics and blend with original."""

    name = "fractal_blend"
    description = "Mandelbrot fractal derived from image stats, blended with original"
    requires: list[str] = []

    def apply(self, image: Image.Image, params: dict, context: EffectContext) -> EffectResult:
        params = self.validate_params(params)
        opacity = params["opacity"]
        max_iter = params["iterations"]
        colormap = params["colormap"]

        rgb_image = image.convert("RGB")
        width, height = rgb_image.size

        mean_hue, mean_brightness, hue_std, brightness_std = _image_histogram_stats(rgb_image)

        # Map statistics to Mandelbrot viewport coordinates.
        # Classic Mandelbrot lives roughly in [-2.5, 1] x [-1.25, 1.25].
        # mean_hue (0-1) → real center in [-2.5, 1.0]
        center_real = -2.5 + mean_hue * 3.5
        # mean_brightness (0-1) → imaginary center in [-1.25, 1.25]
        center_imag = -1.25 + mean_brightness * 2.5
        # std dev → zoom (low std = more zoomed in to see detail)
        combined_std = (hue_std + brightness_std) / 2.0
        zoom = 200.0 / (combined_std + 0.05)

        counts = _generate_mandelbrot(width, height, center_real, center_imag, zoom, max_iter)
        fractal_rgb = _apply_colormap(counts, colormap)
        fractal_image = Image.fromarray(fractal_rgb, mode="RGB")

        # Blend: out = fractal * opacity + original * (1 - opacity)
        orig_arr = np.array(rgb_image, dtype=np.float32)
        frac_arr = fractal_rgb.astype(np.float32)
        blended = np.clip(frac_arr * opacity + orig_arr * (1.0 - opacity), 0, 255).astype(np.uint8)

        return EffectResult(
            image=Image.fromarray(blended, mode="RGB"),
            metadata={
                "opacity": opacity,
                "iterations": max_iter,
                "colormap": colormap,
                "center_real": center_real,
                "center_imag": center_imag,
                "zoom": zoom,
            },
        )

    def validate_params(self, params: dict) -> dict:
        colormap = params.get("colormap", "hot")
        if colormap not in _VALID_COLORMAPS:
            raise ConfigError(
                f"colormap must be one of {_VALID_COLORMAPS}, got {colormap!r}",
                effect_name=self.name,
                param_name="colormap",
            )

        opacity = float(params.get("opacity", 0.5))
        opacity = max(0.0, min(1.0, opacity))

        iterations = int(params.get("iterations", 100))
        iterations = max(1, min(500, iterations))

        return {"opacity": opacity, "iterations": iterations, "colormap": colormap}


register_effect(FractalBlendEffect())
