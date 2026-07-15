"""Driftring effect — peripheral drift illusion (Kitaoka "Rotating Snakes").

Two-image compose, woven-field form: the whole frame is a hex field of
drift wheels whose wedges are sampled from *both* sources — the dark pole
of every wheel is image A crushed to its shadow tones, the light pole is
image B lifted to its highlights, with two midtone steps between. The
black -> dark -> white -> light march that drives the illusory motion is
preserved, but every wedge is now made of a real photo, so the two images
are woven into the crawling surface instead of a synthetic pattern floating
over a dimmed ground.

The image also shapes the *arrangement*: A's local detail sets each wheel's
radius and ring density (busy/subject regions grow tight energetic wheels,
flat regions open into big lazy ones, revealing the photo through the gaps),
and A's local brightness gradient sets each wheel's crawl direction.

Pattern-heavy output: rendered at a capped working scale so PNG byte
size stays in line with the rest of the corpus.
"""

from __future__ import annotations

import random

import cv2
import numpy as np
from PIL import Image

from sparagmos.effects import (
    ComposeEffect,
    EffectContext,
    EffectResult,
    register_effect,
)

MAX_EDGE = 2048


def _hsv_push(rgb: np.ndarray, vmul: float, vadd: float, smul: float = 1.0, sadd: float = 0.0) -> np.ndarray:
    """Push HSV value/saturation of an RGB image, hue preserved. Returns float RGB."""
    hsv = cv2.cvtColor(rgb.astype(np.uint8), cv2.COLOR_RGB2HSV).astype(np.float32)
    hsv[:, :, 1] = np.clip(hsv[:, :, 1] * smul + sadd, 0, 255)
    hsv[:, :, 2] = np.clip(hsv[:, :, 2] * vmul + vadd, 0, 255)
    return cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2RGB).astype(np.float32)


class DriftringEffect(ComposeEffect):
    name = "driftring"
    description = "Peripheral drift illusion — a woven hex field of drift wheels whose dark pole is A, light pole is B"
    requires: list[str] = []

    def compose(self, images: list[Image.Image], params: dict, context: EffectContext) -> EffectResult:
        params = self.validate_params(params)
        rng = random.Random(context.seed)

        a_img = images[0].convert("RGB")
        b_img = (images[1] if len(images) > 1 else images[0]).convert("RGB")
        # Half the batch swaps which source is the dark vs the light pole.
        if len(images) > 1 and rng.random() < 0.5:
            a_img, b_img = b_img, a_img
        if max(a_img.size) > MAX_EDGE:
            a_img = a_img.copy()
            a_img.thumbnail((MAX_EDGE, MAX_EDGE))
        if b_img.size != a_img.size:
            b_img = b_img.resize(a_img.size, Image.LANCZOS)

        A = np.array(a_img)
        B = np.array(b_img)
        h, w = A.shape[:2]

        blur_a = cv2.GaussianBlur(A, (0, 0), sigmaX=max(3, min(w, h) // 60))
        blur_b = cv2.GaussianBlur(B, (0, 0), sigmaX=max(3, min(w, h) // 60))

        # The four wedge fills, all sampled from the photos. A carries the
        # dark half of the drift march, B the light half.
        a_dark = _hsv_push(blur_a, 0.32, 4, smul=1.5, sadd=30)   # A crushed = the "black"
        a_mid = _hsv_push(blur_a, 0.80, 6, smul=1.25, sadd=15)   # A midtone
        b_light = _hsv_push(blur_b, 0.72, 92, smul=1.05, sadd=15)  # B lifted = the "white"
        b_mid = _hsv_push(blur_b, 1.05, 40, smul=1.0, sadd=8)    # B midtone, also the weave

        gray_a = cv2.cvtColor(A, cv2.COLOR_RGB2GRAY).astype(np.float32)
        gx = cv2.Sobel(cv2.GaussianBlur(gray_a, (0, 0), 9), cv2.CV_32F, 1, 0, ksize=5)

        # Local detail of A: sets each wheel's radius and ring density.
        step = max(64.0, min(w, h) / float(params["wheels"]))
        detail = np.abs(cv2.Laplacian(cv2.GaussianBlur(gray_a, (0, 0), 4), cv2.CV_32F))
        detail = cv2.GaussianBlur(detail, (0, 0), sigmaX=step / 2.0)
        lo, hi = np.percentile(detail, 20), np.percentile(detail, 90)
        detail = np.clip((detail - lo) / max(1e-3, hi - lo), 0.0, 1.0)

        # Hex grid of wheel centers, O(1) per-pixel assignment.
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

        cyc = np.clip(cy.astype(np.int32), 0, h - 1)
        cxc = np.clip(cx.astype(np.int32), 0, w - 1)
        d_center = detail[cyc, cxc]                       # per-wheel detail, 0..1
        wheel_r = step * (0.44 + 0.16 * d_center)         # busy -> fuller disc
        rings_map = np.round(params["rings"] + 2.0 * d_center)  # busy -> finer rings
        ring_w = np.maximum(6.0, wheel_r / np.maximum(2.0, rings_map))
        ring = (r / ring_w).astype(np.int32)
        nsub = params["segments"] * 4
        seg = np.floor((theta + np.pi) / (2.0 * np.pi) * nsub).astype(np.int32)

        # Crawl direction from A's local brightness gradient at each center.
        dir_center = np.sign(gx[cyc, cxc])
        dir_center[dir_center == 0] = 1
        direction = np.where(ring % 2 == 0, 1, -1) * dir_center
        idx = (seg * direction + ring) % 4

        # Weave: gaps between the wheel discs show B's midtone, so figure and
        # ground are the same two images rather than a pattern on dead space.
        out = b_mid.copy()
        in_wheel = r <= wheel_r
        for k, fill in ((0, a_dark), (1, a_mid), (2, b_light), (3, b_light * 0.5 + b_mid * 0.5)):
            sel = in_wheel & (idx == k)
            out[sel] = fill[sel]

        if params["texture"] > 0:
            t = params["texture"]
            out = out * (1 - t) + A.astype(np.float32) * t

        return EffectResult(
            image=Image.fromarray(np.clip(out, 0, 255).astype(np.uint8)),
            metadata={**params, "wheel_coverage": round(float(in_wheel.mean()), 3), "size": (w, h)},
        )

    def apply(self, image: Image.Image, params: dict, context: EffectContext) -> EffectResult:
        return self.compose([image, image], params, context)

    def validate_params(self, params: dict) -> dict:
        return {
            "rings": max(3, min(24, int(params.get("rings", 4)))),
            "segments": max(8, min(48, int(params.get("segments", 13)))),
            "hue_spread": max(0.0, min(0.5, float(params.get("hue_spread", 0.12)))),
            "texture": max(0.0, min(0.4, float(params.get("texture", 0.0)))),
            "wheels": max(2, min(14, int(params.get("wheels", 4)))),
        }


register_effect(DriftringEffect())
