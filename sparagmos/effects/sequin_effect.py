"""Sequin effect — flip-sequin pillow.

Two-image compose: image A is the sequin fabric (each disc takes its
local A color, hue-jittered), and image B is what someone dragged their
hand across — wherever B is bright, discs render flipped to mirror
silver, so B's shapes appear drawn into A in flipped sequins.

Pattern-heavy output: rendered at a capped working scale so PNG byte
size stays in line with the rest of the corpus.
"""

from __future__ import annotations

import colorsys
import random

import numpy as np
from PIL import Image, ImageDraw

from sparagmos.effects import (
    ComposeEffect,
    ConfigError,
    EffectContext,
    EffectResult,
    register_effect,
)

MAX_EDGE = 2048
SILVER = (222, 226, 234)


class SequinEffect(ComposeEffect):
    name = "sequin"
    description = "Flip-sequin pillow — discs colored from A; where B is bright they flip to mirror silver"
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
        # Normalize B to [0,1] so the flip threshold is source-independent
        lo, hi = np.percentile(draw_arr, 2), np.percentile(draw_arr, 98)
        draw_arr = np.clip((draw_arr - lo) / max(1.0, hi - lo), 0.0, 1.0)
        flip_cut = params["flip_threshold"]

        out = Image.new("RGB", (w, h), (18, 16, 20))
        draw = ImageDraw.Draw(out)
        rad = disc / 2.0
        row_step = disc * 0.866  # hex packing
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
                        # Mirror side: silver disc, darker specular hollow
                        jig = rng.uniform(-14, 14)
                        fill = tuple(int(min(255, max(0, c + jig))) for c in SILVER)
                        draw.ellipse([x - rad + 1, y - rad + 1, x + rad - 1, y + rad - 1], fill=fill)
                        gx = x + rng.uniform(-0.3, 0.15) * rad
                        gy = y + rng.uniform(-0.3, 0.15) * rad
                        gr = max(1.5, rad * 0.24)
                        draw.ellipse([gx - gr, gy - gr, gx + gr, gy + gr], fill=(255, 255, 255))
                    else:
                        r, g, b = arr[y0:y1, x0:x1].reshape(-1, 3).mean(axis=0) / 255.0
                        hh, ll, ss = colorsys.rgb_to_hls(r, g, b)
                        hh = (hh + rng.uniform(-params["hue_jitter"], params["hue_jitter"]) * 0.5) % 1.0
                        ss = min(1.0, ss * 1.6 + 0.25)
                        ll = min(0.92, ll * 1.15 + 0.04)
                        fr, fg_, fb = colorsys.hls_to_rgb(hh, ll, ss)
                        fill = (int(fr * 255), int(fg_ * 255), int(fb * 255))
                        draw.ellipse([x - rad + 1, y - rad + 1, x + rad - 1, y + rad - 1], fill=fill)
                        if rng.random() < params["sparkle"]:
                            gx = x + rng.uniform(-0.35, 0.1) * rad
                            gy = y + rng.uniform(-0.35, 0.1) * rad
                            gr = max(1.5, rad * 0.22)
                            draw.ellipse([gx - gr, gy - gr, gx + gr, gy + gr], fill=(255, 255, 255))
                x += disc
            y += row_step
            row += 1

        return EffectResult(image=out, metadata={**params, "size": (w, h)})

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
