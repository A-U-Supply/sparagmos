"""Stereogram effect — Magic Eye autostereogram.

Image A's blurred luminance becomes a depth map; image B supplies the
repeating texture. Unfocus or cross your eyes and A's shapes float out
of the pattern. Classic constraint-linking algorithm (Thimbleby,
Inglis & Witten, "Displaying 3D Images").

Pattern-heavy output: rendered at a capped working scale so PNG byte
size stays in line with the rest of the corpus.
"""

from __future__ import annotations

import cv2
import numpy as np
from PIL import Image, ImageFilter

from sparagmos.effects import (
    ComposeEffect,
    ConfigError,
    EffectContext,
    EffectResult,
    register_effect,
)
from sparagmos.effects.tone_effect import _otsu_threshold

MAX_EDGE = 1800


class StereogramEffect(ComposeEffect):
    name = "stereogram"
    description = "Magic Eye autostereogram — A is the depth map, B the repeating texture; unfocus your eyes"
    requires: list[str] = []

    def compose(self, images: list[Image.Image], params: dict, context: EffectContext) -> EffectResult:
        params = self.validate_params(params)
        depth_src = images[0].convert("L")
        texture = (images[1] if len(images) > 1 else images[0]).convert("RGB")

        if max(depth_src.size) > MAX_EDGE:
            depth_src = depth_src.copy()
            depth_src.thumbnail((MAX_EDGE, MAX_EDGE))
        w, h = depth_src.size
        strip = params["strip"]

        # Depth map: a posterized SILHOUETTE, like real Magic Eye plates —
        # a crisp figure floating on one plane reads; continuous depth mush
        # doesn't. Otsu splits figure from ground; light blur rounds edges.
        depth_img = depth_src.filter(ImageFilter.GaussianBlur(radius=max(2, strip // 16)))
        depth = np.array(depth_img).astype(np.uint8)
        figure = (depth > _otsu_threshold(depth)).astype(np.float32)
        # The silhouette is the minority region, raised toward the viewer
        if figure.mean() > 0.5:
            figure = 1.0 - figure
        figure = cv2.GaussianBlur(figure, (0, 0), sigmaX=2.0)
        depth = 0.12 + 0.78 * figure

        # Texture strip: a strip-wide crop of B, tiled vertically to output height
        tex_h = max(strip, int(texture.height * strip / max(1, texture.width)))
        tile = np.array(texture.resize((strip, tex_h), Image.LANCZOS))
        tex = np.tile(tile, (h // tex_h + 1, 1, 1))[:h]

        if params["mode"] == "dots":
            rng = np.random.default_rng(context.seed)
            palette = np.array(texture.resize((16, 16))).reshape(-1, 3)
            tex = palette[rng.integers(0, len(palette), (h, strip))]

        out = np.zeros((h, w, 3), dtype=np.uint8)
        gain = params["depth_gain"]
        # separation shrinks for near (bright) pixels
        sep = np.round(strip * (1.0 - gain * depth)).astype(np.int32)
        sep = np.clip(sep, strip // 2, strip)

        for y in range(h):
            same = list(range(w))
            srow = sep[y]
            for x in range(w):
                s = int(srow[x])
                left = x - s // 2
                right = left + s
                if 0 <= left and right < w:
                    a = left
                    while same[a] != a:
                        a = same[a]
                    b = right
                    while same[b] != b:
                        b = same[b]
                    if a != b:
                        same[max(a, b)] = min(a, b)
            row = out[y]
            trow = tex[y]
            # Roots always point left, so a left-to-right pass can copy safely.
            for x in range(w):
                r = x
                while same[r] != r:
                    r = same[r]
                same[x] = r  # path compression
                row[x] = trow[x % strip] if r == x else row[r]

        return EffectResult(
            image=Image.fromarray(out),
            metadata={**params, "size": (w, h)},
        )

    def apply(self, image: Image.Image, params: dict, context: EffectContext) -> EffectResult:
        return self.compose([image, image], params, context)

    def validate_params(self, params: dict) -> dict:
        mode = params.get("mode", "texture")
        if mode not in ("texture", "dots"):
            raise ConfigError(f"Unknown mode {mode!r}, expected texture|dots", self.name, "mode")
        return {
            "strip": max(48, min(220, int(params.get("strip", 110)))),
            "depth_gain": max(0.02, min(0.4, float(params.get("depth_gain", 0.16)))),
            "mode": mode,
        }


register_effect(StereogramEffect())
