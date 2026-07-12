"""Sequin effect — mirrored-disc mosaic.

Rebuilds the image as hex-packed sequin discs: each takes its local
color, hue-jittered, with an off-center specular glint. From far away
it's the image; up close it's craft-supply glitter.

Pattern-heavy output: rendered at a capped working scale so PNG byte
size stays in line with the rest of the corpus.
"""

from __future__ import annotations

import colorsys
import random

import numpy as np
from PIL import Image, ImageDraw

from sparagmos.effects import ConfigError, Effect, EffectContext, EffectResult, register_effect

MAX_EDGE = 2048


class SequinEffect(Effect):
    name = "sequin"
    description = "Mirrored-disc mosaic — hex-packed hue-jittered sequins with specular glints"
    requires: list[str] = []

    def apply(self, image: Image.Image, params: dict, context: EffectContext) -> EffectResult:
        params = self.validate_params(params)
        rng = random.Random(context.seed)
        img = image.convert("RGB")
        if max(img.size) > MAX_EDGE:
            img = img.copy()
            img.thumbnail((MAX_EDGE, MAX_EDGE))
        w, h = img.size
        disc = params["disc"]
        arr = np.array(img).astype(np.float32)

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

    def validate_params(self, params: dict) -> dict:
        return {
            "disc": max(8, min(96, int(params.get("disc", 26)))),
            "hue_jitter": max(0.0, min(1.0, float(params.get("hue_jitter", 0.35)))),
            "sparkle": max(0.0, min(1.0, float(params.get("sparkle", 0.6)))),
        }


register_effect(SequinEffect())
