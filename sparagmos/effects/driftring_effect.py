"""Driftring effect — peripheral drift illusion (Kitaoka "Rotating Snakes").

Two-image compose: image B's brightest regions seed several wheel
centers (the canonical illusion is a field of many wheels, which drifts
harder than one); image A supplies the palette. Each wheel is concentric
rings of wedge quads cycling black -> dark color -> white -> light
color, direction alternating ring to ring and wheel to wheel.

Pattern-heavy output: rendered at a capped working scale so PNG byte
size stays in line with the rest of the corpus.
"""

from __future__ import annotations

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

MAX_EDGE = 2048


def _dominant_hue(arr: np.ndarray) -> float:
    """Dominant hue of the image in [0,1), from an HSV histogram of saturated pixels."""
    hsv = cv2.cvtColor(arr, cv2.COLOR_RGB2HSV)
    sat_mask = hsv[:, :, 1] > 60
    hues = hsv[:, :, 0][sat_mask]
    if hues.size < 100:
        return 0.6  # default: blue
    hist, _ = np.histogram(hues, bins=36, range=(0, 180))
    return (np.argmax(hist) * 5 + 2.5) / 180.0


def _wheel_centers(gray: np.ndarray, n: int) -> list[tuple[int, int]]:
    """Up to n well-separated bright peaks of a smoothed luminance field."""
    h, w = gray.shape
    blur = cv2.GaussianBlur(gray.astype(np.float32), (0, 0), sigmaX=max(4, min(w, h) // 20))
    min_dist = max(w, h) / (n * 0.9)
    centers: list[tuple[int, int]] = []
    order = np.argsort(blur.flatten())[::-1]
    for idx in order[:: max(1, len(order) // 5000)]:
        y, x = divmod(int(idx), w)
        if any((x - cx) ** 2 + (y - cy) ** 2 < min_dist**2 for cx, cy in centers):
            continue
        centers.append((x, y))
        if len(centers) >= n:
            break
    return centers or [(w // 2, h // 2)]


class DriftringEffect(ComposeEffect):
    name = "driftring"
    description = "Peripheral drift illusion — wheels seeded by B's bright points, painted in A's palette"
    requires: list[str] = []

    def compose(self, images: list[Image.Image], params: dict, context: EffectContext) -> EffectResult:
        params = self.validate_params(params)
        palette_img = images[0].convert("RGB")
        seed_img = (images[1] if len(images) > 1 else images[0]).convert("RGB")
        if max(palette_img.size) > MAX_EDGE:
            palette_img = palette_img.copy()
            palette_img.thumbnail((MAX_EDGE, MAX_EDGE))
        if seed_img.size != palette_img.size:
            seed_img = seed_img.resize(palette_img.size, Image.LANCZOS)

        arr = np.array(palette_img)
        h, w = arr.shape[:2]

        # LOCAL color steps so A's image emerges through the wheel field:
        # the black/white steps stay global (they carry the drift illusion),
        # while the dark and light steps take A's local color, darkened-
        # saturated and lightened respectively.
        blur = cv2.GaussianBlur(arr, (0, 0), sigmaX=max(3, min(w, h) // 60))
        hsv = cv2.cvtColor(blur, cv2.COLOR_RGB2HSV).astype(np.float32)
        dark_hsv = hsv.copy()
        dark_hsv[:, :, 1] = np.clip(dark_hsv[:, :, 1] * 2.2 + 90, 120, 255)
        dark_hsv[:, :, 2] = np.clip(dark_hsv[:, :, 2] * 0.4 + 25, 0, 140)
        dark_img = cv2.cvtColor(dark_hsv.astype(np.uint8), cv2.COLOR_HSV2RGB).astype(np.float32)
        light_hsv = hsv.copy()
        light_hsv[:, :, 1] = np.clip(light_hsv[:, :, 1] * 1.1 + 60, 70, 255)
        light_hsv[:, :, 2] = np.clip(light_hsv[:, :, 2] * 0.45 + 165, 130, 245)
        light_img = cv2.cvtColor(light_hsv.astype(np.uint8), cv2.COLOR_HSV2RGB).astype(np.float32)
        hue = _dominant_hue(arr)

        seed_gray = cv2.cvtColor(np.array(seed_img), cv2.COLOR_RGB2GRAY)
        centers = _wheel_centers(seed_gray, params["wheels"])

        yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
        # Each pixel belongs to its nearest wheel center (Voronoi tiling).
        dists = np.stack([np.hypot(xx - cx, yy - cy) for cx, cy in centers])
        owner = np.argmin(dists, axis=0)
        r = np.take_along_axis(dists, owner[None], axis=0)[0]

        nsub = params["segments"] * 4
        idx = np.zeros((h, w), dtype=np.int32)
        for wi, (cx, cy) in enumerate(centers):
            mask = owner == wi
            theta = np.arctan2(yy - cy, xx - cx)
            seg = np.floor((theta + np.pi) / (2.0 * np.pi) * nsub).astype(np.int32)
            ring_w = max(10.0, min(w, h) / (2.0 * params["rings"]))
            ring = (r / ring_w).astype(np.int32)
            # Alternate direction per ring AND per wheel; offset one sub-step
            # per ring so steps stagger instead of forming radial spokes.
            direction = np.where(ring % 2 == 0, 1, -1) * (1 if wi % 2 == 0 else -1)
            idx[mask] = ((seg * direction + ring) % 4)[mask]

        out = np.empty((h, w, 3), dtype=np.float32)
        out[idx == 0] = (8.0, 8.0, 10.0)
        out[idx == 2] = (250.0, 250.0, 248.0)
        out[idx == 1] = dark_img[idx == 1]
        out[idx == 3] = light_img[idx == 3]

        if params["texture"] > 0:
            t = params["texture"]
            out = out * (1 - t) + arr.astype(np.float32) * t
        out = out.astype(np.uint8)

        return EffectResult(
            image=Image.fromarray(out),
            metadata={**params, "centers": centers, "hue": round(hue, 3), "size": (w, h)},
        )

    def apply(self, image: Image.Image, params: dict, context: EffectContext) -> EffectResult:
        return self.compose([image, image], params, context)

    def validate_params(self, params: dict) -> dict:
        return {
            "rings": max(4, min(24, int(params.get("rings", 11)))),
            "segments": max(8, min(48, int(params.get("segments", 24)))),
            "hue_spread": max(0.0, min(0.5, float(params.get("hue_spread", 0.12)))),
            "texture": max(0.0, min(0.4, float(params.get("texture", 0.0)))),
            "wheels": max(1, min(9, int(params.get("wheels", 5)))),
        }


register_effect(DriftringEffect())
