"""Sequin effect — flip-sequin pillow.

Two-image compose: image A is the sequin fabric (each disc takes its
local A color, hue-jittered), and image B is what someone dragged their
hand across — wherever B is bright, discs render flipped to mirror
silver, so B's shapes appear drawn into A in flipped sequins.

Each disc is shaded like a real tilted sequin: a linear light gradient
across a random axis, a specular hotspot near the bright edge, and
occasional star glints — glitter, not bathroom tile.

Pattern-heavy output: rendered at a capped working scale so PNG byte
size stays in line with the rest of the corpus.
"""

from __future__ import annotations

import colorsys
import random

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
SILVER = np.array([225.0, 229.0, 238.0])
BG = np.array([14.0, 12.0, 16.0])


class SequinEffect(ComposeEffect):
    name = "sequin"
    description = "Flip-sequin pillow — shaded, tilted discs from A; where B is bright they flip to mirror silver"
    requires: list[str] = []

    def compose(self, images: list[Image.Image], params: dict, context: EffectContext) -> EffectResult:
        params = self.validate_params(params)
        rng = random.Random(context.seed)
        fabric = images[0].convert("RGB")
        drawing = (images[1] if len(images) > 1 else images[0]).convert("L")
        if max(fabric.size) > MAX_EDGE:
            fabric = fabric.copy()
            fabric.thumbnail((MAX_EDGE, MAX_EDGE))
        if drawing.size != fabric.size:
            drawing = drawing.resize(fabric.size, Image.LANCZOS)

        w, h = fabric.size
        disc = params["disc"]
        arr = np.array(fabric).astype(np.float32)
        draw_arr = np.array(drawing).astype(np.float32)
        lo, hi = np.percentile(draw_arr, 2), np.percentile(draw_arr, 98)
        draw_arr = np.clip((draw_arr - lo) / max(1.0, hi - lo), 0.0, 1.0)
        flip_cut = params["flip_threshold"]

        out = np.empty((h, w, 3), dtype=np.float32)
        out[:] = BG

        # Per-diameter geometry cache: distance grid + circle mask
        d = int(disc)
        ys, xs = np.mgrid[0:d, 0:d].astype(np.float32)
        cx = cy = (d - 1) / 2.0
        dx, dy = (xs - cx) / (d / 2.0), (ys - cy) / (d / 2.0)
        rr = np.sqrt(dx * dx + dy * dy)
        circle = rr <= 0.96

        rad = disc / 2.0
        row_step = disc * 0.866
        y = rad
        row = 0
        while y - rad < h:
            x = rad + (rad if row % 2 else 0)
            while x - rad < w:
                x0, y0 = int(round(x - rad)), int(round(y - rad))
                x1, y1 = x0 + d, y0 + d
                px0, py0 = max(0, x0), max(0, y0)
                px1, py1 = min(w, x1), min(h, y1)
                if px1 > px0 and py1 > py0:
                    sx0, sy0 = px0 - x0, py0 - y0
                    sx1, sy1 = sx0 + (px1 - px0), sy0 + (py1 - py0)
                    region_mask = circle[sy0:sy1, sx0:sx1]

                    flipped = draw_arr[py0:py1, px0:px1].mean() > flip_cut
                    if flipped:
                        color = SILVER + rng.uniform(-12, 12)
                    else:
                        r_, g_, b_ = arr[py0:py1, px0:px1].reshape(-1, 3).mean(axis=0) / 255.0
                        hh, ll, ss = colorsys.rgb_to_hls(r_, g_, b_)
                        hh = (hh + rng.uniform(-params["hue_jitter"], params["hue_jitter"]) * 0.5) % 1.0
                        ss = min(1.0, ss * 1.7 + 0.3)
                        ll = min(0.9, ll * 1.1 + 0.05)
                        fr, fg_, fb = colorsys.hls_to_rgb(hh, ll, ss)
                        color = np.array([fr, fg_, fb]) * 255.0

                    # Tilted-sequin shading: linear light gradient across a
                    # random axis + rim falloff + specular hotspot.
                    theta = rng.uniform(0, 2 * np.pi)
                    grad = dx * np.cos(theta) + dy * np.sin(theta)  # -1..1
                    shade = 0.72 + 0.5 * (grad * 0.5 + 0.5)  # 0.72..1.22
                    shade -= 0.28 * np.clip(rr - 0.65, 0, 1) / 0.35  # dark rim
                    hot = np.exp(-((dx - 0.45 * np.cos(theta)) ** 2 + (dy - 0.45 * np.sin(theta)) ** 2) / 0.06)
                    disc_px = color[None, None, :] * shade[:, :, None] + 255.0 * (hot * params["sparkle"])[:, :, None]
                    if flipped:
                        disc_px += 255.0 * (hot * 0.35)[:, :, None]  # mirrors flare harder

                    patch = out[py0:py1, px0:px1]
                    patch[region_mask] = np.clip(disc_px[sy0:sy1, sx0:sx1], 0, 255)[region_mask]

                    # Occasional star glint on top
                    if rng.random() < 0.05:
                        gx, gy = int(x), int(y)
                        ray = int(rad * 1.1)
                        for ddx, ddy in ((1, 0), (0, 1)):
                            for t in range(-ray, ray + 1):
                                yy2, xx2 = gy + ddy * t, gx + ddx * t
                                if 0 <= yy2 < h and 0 <= xx2 < w:
                                    fade = 1.0 - abs(t) / (ray + 1)
                                    out[yy2, xx2] = np.clip(out[yy2, xx2] + 230 * fade, 0, 255)
                x += disc
            y += row_step
            row += 1

        return EffectResult(
            image=Image.fromarray(out.astype(np.uint8)),
            metadata={**params, "size": (w, h)},
        )

    def apply(self, image: Image.Image, params: dict, context: EffectContext) -> EffectResult:
        return self.compose([image, image], params, context)

    def validate_params(self, params: dict) -> dict:
        return {
            "disc": max(8, min(96, int(params.get("disc", 26)))),
            "hue_jitter": max(0.0, min(1.0, float(params.get("hue_jitter", 0.35)))),
            "sparkle": max(0.0, min(1.0, float(params.get("sparkle", 0.6)))),
            "flip_threshold": max(0.3, min(0.85, float(params.get("flip_threshold", 0.55)))),
        }


register_effect(SequinEffect())
