"""Holofoil effect — holographic sticker with a latent second image.

Two-image compose: shapes are cut from image A's Otsu stencil and filled
with angle-swept rainbow foil; image B's blurred luminance phase-shifts
the foil, so B ghosts inside the hologram the way real holo stickers
hide a latent image. Starburst glints land on A's brightest points.
"""

from __future__ import annotations

import random

import cv2
import numpy as np
from PIL import Image

from sparagmos.effects import (
    ComposeEffect,
    ConfigError,
    EffectContext,
    EffectResult,
    register_effect,
)
from sparagmos.effects.tone_effect import _otsu_threshold

GROUNDS = {"dark": (14, 14, 22), "paper": (242, 238, 228)}
MAX_EDGE = 2048


def _rainbow(t: np.ndarray) -> np.ndarray:
    """t in [0,1) -> saturated spectral RGB float array."""
    h = (t % 1.0) * 6.0
    x = 1.0 - np.abs(h % 2.0 - 1.0)
    zeros = np.zeros_like(h)
    ones = np.ones_like(h)
    conds = [h < 1, h < 2, h < 3, h < 4, h < 5, h >= 5]
    r = np.select(conds, [ones, x, zeros, zeros, x, ones])
    g = np.select(conds, [x, ones, ones, x, zeros, zeros])
    b = np.select(conds, [zeros, zeros, x, ones, ones, x])
    return np.stack([r, g, b], axis=-1) * 255.0


class HolofoilEffect(ComposeEffect):
    name = "holofoil"
    description = "Holographic sticker — A's Otsu shapes in rainbow foil, B ghosting inside as the latent image"
    requires: list[str] = []

    def compose(self, images: list[Image.Image], params: dict, context: EffectContext) -> EffectResult:
        params = self.validate_params(params)
        rng = random.Random(context.seed)
        base = images[0].convert("RGB")
        latent_img = (images[1] if len(images) > 1 else images[0]).convert("RGB")
        if max(base.size) > MAX_EDGE:
            base = base.copy()
            base.thumbnail((MAX_EDGE, MAX_EDGE))
        if latent_img.size != base.size:
            latent_img = latent_img.resize(base.size, Image.LANCZOS)

        arr = np.array(base)
        h, w = arr.shape[:2]
        gray = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)

        thresh = _otsu_threshold(gray)
        fg = gray > thresh
        if params["invert"]:
            fg = ~fg

        theta = np.deg2rad(params["angle"])
        yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
        diag = float(np.hypot(w, h))
        sweep = (xx * np.cos(theta) + yy * np.sin(theta)) / diag
        shimmer = cv2.GaussianBlur(
            np.random.default_rng(context.seed).random((h, w)).astype(np.float32), (0, 0), 24
        )
        # The latent image: B's blurred luminance phase-shifts the foil.
        latent = cv2.cvtColor(np.array(latent_img), cv2.COLOR_RGB2GRAY).astype(np.float32)
        latent = cv2.GaussianBlur(latent, (0, 0), 6)
        # Full-range stretch so the latent image always embosses distinctly
        lo, hi = np.percentile(latent, 3), np.percentile(latent, 97)
        latent = np.clip((latent - lo) / max(1.0, hi - lo), 0.0, 1.0)
        foil = _rainbow(sweep * 2.0 + shimmer * 0.5 + latent * params["latent"])
        # Metallic base: mix the rainbow halfway toward silver so the sheen
        # reads as foil, not candy; then B also modulates BRIGHTNESS so the
        # latent image reads as an embossed ghost, not just a hue drift.
        silver = np.full_like(foil, 205.0)
        foil = foil * 0.5 + silver * 0.5
        foil = foil * (0.68 + 0.55 * latent)[:, :, None]
        sheen = (0.5 + 0.5 * np.cos(sweep * 12.0 * np.pi + shimmer * 4.0))[:, :, None]
        foil = foil * (0.75 + 0.25 * sheen) + 255.0 * 0.22 * sheen

        out = np.empty_like(arr, dtype=np.float32)
        out[:] = GROUNDS[params["ground"]]
        out[fg] = np.clip(foil, 0, 255)[fg]

        img = Image.fromarray(np.clip(out, 0, 255).astype(np.uint8))
        self._add_glints(img, gray, fg, params["glints"], rng)
        return EffectResult(image=img, metadata={**params, "threshold": thresh})

    def apply(self, image: Image.Image, params: dict, context: EffectContext) -> EffectResult:
        return self.compose([image, image], params, context)

    @staticmethod
    def _add_glints(img: Image.Image, gray: np.ndarray, fg: np.ndarray, n: int, rng: random.Random) -> None:
        if n <= 0:
            return
        from PIL import ImageDraw

        h, w = gray.shape
        min_dist = max(w, h) // 10
        masked = np.where(fg, gray, 0).astype(np.float32)
        masked = cv2.GaussianBlur(masked, (0, 0), 3)
        draw = ImageDraw.Draw(img, "RGBA")
        placed: list[tuple[int, int]] = []
        flat = masked.flatten()
        order = np.argsort(flat)[::-1]
        for idx in order[: n * 400]:
            y, x = divmod(int(idx), w)
            if any((x - px) ** 2 + (y - py) ** 2 < min_dist**2 for px, py in placed):
                continue
            placed.append((x, y))
            ray = max(6, min(w, h) // rng.randint(28, 44))
            for dx, dy, r in ((1, 0, ray), (0, 1, ray), (1, 1, ray * 0.45), (1, -1, ray * 0.45)):
                norm = (dx * dx + dy * dy) ** 0.5
                ex, ey = dx / norm * r, dy / norm * r
                draw.line([(x - ex, y - ey), (x + ex, y + ey)], fill=(255, 255, 255, 210), width=2)
            draw.ellipse([x - 3, y - 3, x + 3, y + 3], fill=(255, 255, 255, 255))
            if len(placed) >= n:
                break

    def validate_params(self, params: dict) -> dict:
        ground = params.get("ground", "dark")
        if ground not in GROUNDS:
            raise ConfigError(f"Unknown ground {ground!r}, expected one of {sorted(GROUNDS)}", self.name, "ground")
        return {
            "angle": float(params.get("angle", 30.0)) % 360.0,
            "glints": max(0, min(12, int(params.get("glints", 6)))),
            "invert": bool(params.get("invert", False)),
            "ground": ground,
            "latent": max(0.0, min(3.0, float(params.get("latent", 1.2)))),
        }


register_effect(HolofoilEffect())
