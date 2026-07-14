"""Sequin effect — flip-sequin pillow with faceted, angular sequins.

Two-image compose: image A is the sequin fabric (each sequin takes its
local A color, saturated, not washed), and image B is what someone
dragged their hand across — wherever B is bright, sequins flip to
mirror silver, so B's shapes appear drawn into A.

Each sequin is a hard-edged hexagon/octagon at a random rotation, split
into a bright face and a dark face along a hard chord — the "catching
the light" facet line — with a white specular wedge on the bright side.

Pattern-heavy output: rendered at a capped working scale so PNG byte
size stays in line with the rest of the corpus.
"""

from __future__ import annotations

import colorsys
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

MAX_EDGE = 2048
SILVER = np.array([228.0, 232.0, 242.0])
BG = np.array([10.0, 8.0, 12.0])


def _ngon(cx: float, cy: float, r: float, n: int, rot: float) -> np.ndarray:
    angles = rot + np.arange(n) * (2 * np.pi / n)
    pts = np.stack([cx + r * np.cos(angles), cy + r * np.sin(angles)], axis=1)
    return pts.astype(np.int32)


class SequinEffect(ComposeEffect):
    name = "sequin"
    description = "Flip-sequin pillow — faceted hexagon sequins from A; where B is bright they flip to mirror silver"
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
        # The silver (flipped) side is the DRAWN shape — always the minority.
        if (draw_arr > flip_cut).mean() > 0.5:
            draw_arr = 1.0 - draw_arr

        out = np.empty((h, w, 3), dtype=np.uint8)
        out[:] = BG.astype(np.uint8)

        rad = disc / 2.0
        row_step = disc * 0.866
        y = rad
        row = 0
        while y - rad < h:
            x = rad + (rad if row % 2 else 0)
            while x - rad < w:
                x0, y0 = int(max(0, x - rad)), int(max(0, y - rad))
                x1, y1 = int(min(w, x + rad)), int(min(h, y + rad))
                if x1 > x0 and y1 > y0:
                    flipped = draw_arr[y0:y1, x0:x1].mean() > flip_cut
                    if flipped:
                        base = SILVER + rng.uniform(-10, 10)
                    else:
                        r_, g_, b_ = arr[y0:y1, x0:x1].reshape(-1, 3).mean(axis=0) / 255.0
                        hh, ll, ss = colorsys.rgb_to_hls(r_, g_, b_)
                        hh = (hh + rng.uniform(-params["hue_jitter"], params["hue_jitter"]) * 0.5) % 1.0
                        ss = min(1.0, max(0.55, ss * 1.9))
                        ll = min(0.75, max(0.22, ll))
                        fr, fg_, fb = colorsys.hls_to_rgb(hh, ll, ss)
                        base = np.array([fr, fg_, fb]) * 255.0

                    n = rng.choice((6, 6, 8))  # mostly hexagons
                    rot = rng.uniform(0, 2 * np.pi)
                    poly = _ngon(x, y, rad * 0.98, n, rot)

                    # Dark face fills the whole sequin, bright face is the
                    # half-polygon beyond a hard chord through the center.
                    light_dir = rng.uniform(0, 2 * np.pi)
                    ldx, ldy = np.cos(light_dir), np.sin(light_dir)
                    dark = np.clip(base * 0.55, 0, 255)
                    bright = np.clip(base * 1.35 + 30, 0, 255)
                    cv2.fillConvexPoly(out, poly, dark.tolist())
                    side = (poly[:, 0] - x) * ldx + (poly[:, 1] - y) * ldy
                    keep = poly[side > -rad * 0.05]
                    if len(keep) >= 3:
                        chord = np.array(
                            [[x - ldy * rad, y + ldx * rad], [x + ldy * rad, y - ldx * rad]], dtype=np.int32
                        )
                        half = cv2.convexHull(np.vstack([keep, chord]))
                        cv2.fillConvexPoly(out, half, bright.tolist())
                    # Specular wedge near the bright edge
                    if rng.random() < params["sparkle"]:
                        sx = x + ldx * rad * 0.55
                        sy = y + ldy * rad * 0.55
                        spec = _ngon(sx, sy, rad * 0.28, 3, rot + rng.uniform(0, 2))
                        cv2.fillConvexPoly(out, spec, (255, 255, 255))

                    if rng.random() < 0.04:
                        ray = int(rad * 1.2)
                        cv2.line(out, (int(x - ray), int(y)), (int(x + ray), int(y)), (255, 255, 255), 1)
                        cv2.line(out, (int(x), int(y - ray)), (int(x), int(y + ray)), (255, 255, 255), 1)
                x += disc
            y += row_step
            row += 1

        return EffectResult(
            image=Image.fromarray(out),
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
