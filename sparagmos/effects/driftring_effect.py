"""Driftring effect — peripheral drift illusion (Kitaoka "Rotating Snakes").

Rebuilds the image as concentric rings of wedge segments cycling through
the asymmetric 4-step luminance sequence black -> dark color -> white ->
light color. With the step order consistent around each ring and the
direction alternating ring to ring, the static image appears to rotate
in peripheral vision. Colors are drawn from the source image's palette;
ring centers follow its brightest region.

Pattern-heavy output: rendered at a capped working scale so PNG byte
size stays in line with the rest of the corpus.
"""

from __future__ import annotations

import colorsys

import cv2
import numpy as np
from PIL import Image

from sparagmos.effects import ConfigError, Effect, EffectContext, EffectResult, register_effect

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


class DriftringEffect(Effect):
    name = "driftring"
    description = "Peripheral drift illusion — Kitaoka-style rings in the source's palette that appear to rotate"
    requires: list[str] = []

    def apply(self, image: Image.Image, params: dict, context: EffectContext) -> EffectResult:
        params = self.validate_params(params)
        img = image.convert("RGB")
        if max(img.size) > MAX_EDGE:
            img = img.copy()
            img.thumbnail((MAX_EDGE, MAX_EDGE))
        arr = np.array(img)
        h, w = arr.shape[:2]

        # Palette: black / dark saturated / white / light pale, hues from the source.
        hue = _dominant_hue(arr)
        dark = colorsys.hls_to_rgb(hue, 0.32, 0.95)
        light = colorsys.hls_to_rgb((hue + params["hue_spread"]) % 1.0, 0.78, 0.85)
        # Perceived drift runs black -> dark -> white -> light; luminance order matters.
        palette = np.array(
            [
                (8, 8, 10),
                tuple(int(c * 255) for c in dark),
                (250, 250, 248),
                tuple(int(c * 255) for c in light),
            ],
            dtype=np.uint8,
        )

        # Center on the brightest smoothed region of the source.
        gray = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY).astype(np.float32)
        blur = cv2.GaussianBlur(gray, (0, 0), sigmaX=max(4, min(w, h) // 24))
        cy, cx = np.unravel_index(int(np.argmax(blur)), blur.shape)
        # Keep the center in the middle 60% so rings stay visible.
        cx = int(np.clip(cx, w * 0.2, w * 0.8))
        cy = int(np.clip(cy, h * 0.2, h * 0.8))

        yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
        r = np.hypot(xx - cx, yy - cy)
        theta = np.arctan2(yy - cy, xx - cx)  # [-pi, pi]

        ring_w = max(12.0, min(w, h) / (2.0 * params["rings"]))
        ring = (r / ring_w).astype(np.int32)
        # `segments` = repeating 4-step quads per ring; each quad is
        # black -> dark -> white -> light. The illusion needs many small
        # steps, so sub-wedges = quads * 4.
        nsub = params["segments"] * 4
        seg = np.floor((theta + np.pi) / (2.0 * np.pi) * nsub).astype(np.int32)

        # Alternate drift direction per ring; offset by ONE sub-step per ring
        # (even offsets re-align across rings and read as radial spokes).
        direction = np.where(ring % 2 == 0, 1, -1)
        idx = (seg * direction + ring) % 4

        out = palette[idx]

        # Optional: whisper of the source inside each color step (keeps it "of" the image)
        if params["texture"] > 0:
            t = params["texture"]
            out = (out.astype(np.float32) * (1 - t) + arr.astype(np.float32) * t).astype(np.uint8)

        return EffectResult(
            image=Image.fromarray(out),
            metadata={**params, "center": (int(cx), int(cy)), "hue": round(hue, 3), "size": (w, h)},
        )

    def validate_params(self, params: dict) -> dict:
        return {
            "rings": max(4, min(24, int(params.get("rings", 11)))),
            "segments": max(8, min(48, int(params.get("segments", 24)))),
            "hue_spread": max(0.0, min(0.5, float(params.get("hue_spread", 0.12)))),
            "texture": max(0.0, min(0.4, float(params.get("texture", 0.0)))),
        }


register_effect(DriftringEffect())
