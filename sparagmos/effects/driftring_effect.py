"""Driftring effect — peripheral drift illusion (Kitaoka "Rotating Snakes").

Two-image compose, silhouette form: image A's Otsu silhouette is built
out of a hex field of small drift wheels — rings of wedge quads cycling
black -> dark -> white -> light, direction alternating ring to ring and
wheel to wheel — while image B, dimmed, is the ground the figure floats
on. The source survives structurally: you see A's shape, made of the
illusion; the color steps carry A's local palette.

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
from sparagmos.effects.tone_effect import _otsu_threshold

MAX_EDGE = 2048


class DriftringEffect(ComposeEffect):
    name = "driftring"
    description = "Peripheral drift illusion — A's silhouette built from drift wheels, floating on dimmed B"
    requires: list[str] = []

    def compose(self, images: list[Image.Image], params: dict, context: EffectContext) -> EffectResult:
        params = self.validate_params(params)
        figure_img = images[0].convert("RGB")
        ground_img = (images[1] if len(images) > 1 else images[0]).convert("RGB")
        if max(figure_img.size) > MAX_EDGE:
            figure_img = figure_img.copy()
            figure_img.thumbnail((MAX_EDGE, MAX_EDGE))
        if ground_img.size != figure_img.size:
            ground_img = ground_img.resize(figure_img.size, Image.LANCZOS)

        arr = np.array(figure_img)
        ground = np.array(ground_img).astype(np.float32)
        h, w = arr.shape[:2]

        # A's silhouette: the minority Otsu region, cleaned up a little
        gray = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)
        blur_g = cv2.GaussianBlur(gray, (0, 0), sigmaX=max(3, min(w, h) // 90))
        figure = blur_g > _otsu_threshold(blur_g)
        if figure.mean() > 0.5:
            figure = ~figure
        kernel = np.ones((7, 7), np.uint8)
        figure = cv2.morphologyEx(figure.astype(np.uint8), cv2.MORPH_CLOSE, kernel).astype(bool)

        # Local color steps from A (black/white poles stay global — they
        # carry the drift; the colored steps carry A's palette).
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

        # Hex grid of wheel centers, O(1) per-pixel assignment
        step = max(64.0, min(w, h) / float(params["wheels"]))
        row_step = step * 0.866
        yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
        grid_row = np.round(yy / row_step)
        x_off = np.where(grid_row % 2 == 1, step / 2.0, 0.0)
        grid_col = np.round((xx - x_off) / step)
        cx = grid_col * step + x_off
        cy = grid_row * row_step
        rel_x, rel_y = xx - cx, yy - cy
        r = np.hypot(rel_x, rel_y)
        theta = np.arctan2(rel_y, rel_x)

        wheel_r = step * 0.58
        rings = params["rings"]
        ring_w = max(6.0, wheel_r / rings)
        ring = (r / ring_w).astype(np.int32)
        nsub = params["segments"] * 4
        seg = np.floor((theta + np.pi) / (2.0 * np.pi) * nsub).astype(np.int32)
        wheel_parity = (grid_row + grid_col) % 2 == 0
        direction = np.where(ring % 2 == 0, 1, -1) * np.where(wheel_parity, 1, -1)
        idx = (seg * direction + ring) % 4

        in_wheel = figure & (r <= wheel_r)
        out = ground * 0.28  # dim B ground
        # Figure body outside the wheel discs stays near-black, keeping the
        # silhouette solid.
        body = figure & ~in_wheel
        out[body] = (12.0, 12.0, 14.0)
        sel = in_wheel & (idx == 0)
        out[sel] = (8.0, 8.0, 10.0)
        sel = in_wheel & (idx == 2)
        out[sel] = (250.0, 250.0, 248.0)
        sel = in_wheel & (idx == 1)
        out[sel] = dark_img[sel]
        sel = in_wheel & (idx == 3)
        out[sel] = light_img[sel]

        if params["texture"] > 0:
            t = params["texture"]
            out = out * (1 - t) + arr.astype(np.float32) * t

        return EffectResult(
            image=Image.fromarray(np.clip(out, 0, 255).astype(np.uint8)),
            metadata={**params, "figure_coverage": round(float(figure.mean()), 3), "size": (w, h)},
        )

    def apply(self, image: Image.Image, params: dict, context: EffectContext) -> EffectResult:
        return self.compose([image, image], params, context)

    def validate_params(self, params: dict) -> dict:
        return {
            "rings": max(3, min(24, int(params.get("rings", 6)))),
            "segments": max(8, min(48, int(params.get("segments", 20)))),
            "hue_spread": max(0.0, min(0.5, float(params.get("hue_spread", 0.12)))),
            "texture": max(0.0, min(0.4, float(params.get("texture", 0.0)))),
            "wheels": max(2, min(14, int(params.get("wheels", 6)))),
        }


register_effect(DriftringEffect())
