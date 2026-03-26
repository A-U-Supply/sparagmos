"""Pix2pix effect — simulated image-to-image translation artifacts.

Simulates the visual style of pix2pix/CycleGAN domain transfer without
requiring pretrained models. Produces checkerboard artifacts, color bleeding,
and patch-boundary effects characteristic of GAN-based translation.
"""

from __future__ import annotations

import numpy as np
from PIL import Image, ImageFilter

from sparagmos.effects import ConfigError, Effect, EffectContext, EffectResult, register_effect

_VALID_MODELS = ("zebra", "monet", "vangogh", "ukiyoe")
_VALID_DIRECTIONS = ("AtoB", "BtoA")


class Pix2PixEffect(Effect):
    name = "pix2pix"
    description = "Simulated pix2pix/CycleGAN domain transfer artifacts"
    requires: list[str] = []

    def validate_params(self, params: dict) -> dict:
        model = params.get("model", "zebra")
        if model not in _VALID_MODELS:
            raise ConfigError(
                f"model must be one of {_VALID_MODELS}, got {model!r}",
                effect_name=self.name,
                param_name="model",
            )
        direction = params.get("direction", "AtoB")
        if direction not in _VALID_DIRECTIONS:
            raise ConfigError(
                f"direction must be one of {_VALID_DIRECTIONS}, got {direction!r}",
                effect_name=self.name,
                param_name="direction",
            )
        intensity = float(params.get("intensity", 0.7))
        intensity = max(0.0, min(1.0, intensity))
        return {"model": model, "direction": direction, "intensity": intensity}

    def apply(self, image: Image.Image, params: dict, context: EffectContext) -> EffectResult:
        params = self.validate_params(params)
        model = params["model"]
        direction = params["direction"]
        intensity = params["intensity"]

        rng = np.random.default_rng(context.seed)

        img_rgb = image.convert("RGB")
        arr = np.array(img_rgb, dtype=np.float32)
        h, w = arr.shape[:2]

        # Edge detection via simple Sobel approximation in numpy
        gray = 0.299 * arr[:, :, 0] + 0.587 * arr[:, :, 1] + 0.114 * arr[:, :, 2]
        sobel_x = np.zeros_like(gray)
        sobel_y = np.zeros_like(gray)
        sobel_x[1:-1, 1:-1] = np.abs(gray[1:-1, 2:] - gray[1:-1, :-2])
        sobel_y[1:-1, 1:-1] = np.abs(gray[2:, 1:-1] - gray[:-2, 1:-1])
        edges = np.clip((sobel_x + sobel_y) / 2.0, 0.0, 255.0)
        edges_norm = edges / (edges.max() + 1e-8)

        # Build model-specific pattern layer
        pattern = self._build_pattern(model, direction, arr, edges_norm, rng, h, w)

        # Add checkerboard patch-boundary artifacts (GAN discriminator patch size ~70px)
        checkerboard = self._checkerboard_artifacts(h, w, patch_size=max(4, min(70, h // 4)), rng=rng)

        # Blend: original + pattern + checkerboard artifacts
        blended = arr * (1.0 - intensity) + pattern * intensity
        artifact_strength = intensity * 0.25
        blended = blended * (1.0 - artifact_strength) + checkerboard * artifact_strength

        # Color bleeding at edges: smear color in the direction of edges
        bleeding = self._color_bleed(blended, edges_norm, intensity)
        blended = blended * (1.0 - 0.3 * intensity) + bleeding * (0.3 * intensity)

        result_arr = np.clip(blended, 0, 255).astype(np.uint8)
        return EffectResult(
            image=Image.fromarray(result_arr),
            metadata={"model": model, "direction": direction, "intensity": intensity},
        )

    def _build_pattern(
        self,
        model: str,
        direction: str,
        arr: np.ndarray,
        edges_norm: np.ndarray,
        rng: np.random.Generator,
        h: int,
        w: int,
    ) -> np.ndarray:
        """Build the domain-transfer style pattern."""
        if model == "zebra":
            return self._zebra_pattern(arr, edges_norm, direction, h, w)
        elif model == "monet":
            return self._monet_pattern(arr, rng)
        elif model == "vangogh":
            return self._vangogh_pattern(arr, edges_norm, rng, h, w)
        else:  # ukiyoe
            return self._ukiyoe_pattern(arr, edges_norm, rng)

    def _zebra_pattern(
        self, arr: np.ndarray, edges_norm: np.ndarray, direction: str, h: int, w: int
    ) -> np.ndarray:
        """Black-and-white stripes overlaid on edge regions."""
        # Diagonal stripes
        x_coords = np.arange(w)[np.newaxis, :]
        y_coords = np.arange(h)[:, np.newaxis]
        stripe_freq = max(4, min(h, w) // 8)
        stripes = ((x_coords + y_coords) % stripe_freq) < (stripe_freq // 2)
        stripe_val = np.where(stripes, 230.0, 20.0)

        pattern = arr.copy()
        # Apply stripes more strongly where edges are detected
        edge_weight = np.clip(edges_norm * 3.0, 0.0, 1.0)[:, :, np.newaxis]
        bw = np.stack([stripe_val, stripe_val, stripe_val], axis=2)
        if direction == "BtoA":
            # BtoA: convert stripes back toward color — shift hue toward orange
            bw[:, :, 0] = np.clip(bw[:, :, 0] * 1.3, 0, 255)
            bw[:, :, 1] = np.clip(bw[:, :, 1] * 0.8, 0, 255)
        pattern = pattern * (1.0 - edge_weight) + bw * edge_weight
        return pattern

    def _monet_pattern(self, arr: np.ndarray, rng: np.random.Generator) -> np.ndarray:
        """Impressionist blur with boosted saturation."""
        pil = Image.fromarray(arr.astype(np.uint8))
        # Multiple blur passes of different radii simulate paint strokes
        blurred = np.array(
            pil.filter(ImageFilter.GaussianBlur(radius=3)), dtype=np.float32
        )
        # Boost saturation by amplifying deviation from gray
        gray = blurred.mean(axis=2, keepdims=True)
        saturated = gray + (blurred - gray) * 1.8
        # Warm tint
        saturated[:, :, 0] = np.clip(saturated[:, :, 0] * 1.1, 0, 255)
        saturated[:, :, 2] = np.clip(saturated[:, :, 2] * 0.85, 0, 255)
        return np.clip(saturated, 0, 255)

    def _vangogh_pattern(
        self, arr: np.ndarray, edges_norm: np.ndarray, rng: np.random.Generator, h: int, w: int
    ) -> np.ndarray:
        """Swirling, high-contrast painterly effect."""
        # Directional blur to simulate brush strokes
        pil = Image.fromarray(arr.astype(np.uint8))
        # Use rank filter as a texture-building step
        textured = np.array(pil.filter(ImageFilter.SMOOTH_MORE), dtype=np.float32)
        # High contrast via gamma compression
        textured = np.power(textured / 255.0, 0.6) * 255.0
        # Shift toward blue/yellow (van Gogh palette)
        textured[:, :, 2] = np.clip(textured[:, :, 2] * 1.3, 0, 255)
        textured[:, :, 1] = np.clip(textured[:, :, 1] * 1.15, 0, 255)
        # Add swirl-like offset using edge gradients as displacement
        edge_disp = (edges_norm * 6).astype(int)
        displaced = np.roll(textured, 3, axis=1)
        blend_mask = np.clip(edges_norm * 2, 0, 1)[:, :, np.newaxis]
        return textured * (1 - blend_mask) + displaced * blend_mask

    def _ukiyoe_pattern(
        self, arr: np.ndarray, edges_norm: np.ndarray, rng: np.random.Generator
    ) -> np.ndarray:
        """Flat color regions with bold outlines — woodblock print style."""
        pil = Image.fromarray(arr.astype(np.uint8))
        # Posterize to simulate flat color regions
        posterized = np.array(
            pil.filter(ImageFilter.ModeFilter(size=7)), dtype=np.float32
        )
        # Darken edges to simulate bold outlines
        dark_edges = (1.0 - np.clip(edges_norm * 5, 0, 1))[:, :, np.newaxis]
        result = posterized * dark_edges
        # Shift palette toward red/black ukiyoe tones
        result[:, :, 0] = np.clip(result[:, :, 0] * 1.2, 0, 255)
        result[:, :, 1] = np.clip(result[:, :, 1] * 0.8, 0, 255)
        return result

    def _checkerboard_artifacts(
        self, h: int, w: int, patch_size: int, rng: np.random.Generator
    ) -> np.ndarray:
        """GAN-style checkerboard patch boundary noise."""
        grid_h = (h + patch_size - 1) // patch_size
        grid_w = (w + patch_size - 1) // patch_size
        # Random offsets per patch cell
        offsets = rng.uniform(-30, 30, (grid_h, grid_w, 3)).astype(np.float32)
        # Upscale to image size (nearest neighbor)
        checker = np.repeat(np.repeat(offsets, patch_size, axis=0), patch_size, axis=1)
        checker = checker[:h, :w, :]
        # Center at 128 for neutral blending
        return np.clip(checker + 128.0, 0, 255)

    def _color_bleed(
        self, arr: np.ndarray, edges_norm: np.ndarray, intensity: float
    ) -> np.ndarray:
        """Smear colors horizontally at edge regions."""
        bleed_amount = max(1, int(intensity * 5))
        bled = np.roll(arr, bleed_amount, axis=1)
        return bled


register_effect(Pix2PixEffect())
