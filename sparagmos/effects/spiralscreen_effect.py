"""Archimedean spiral screen Compose effect.

Ported from collage-bot-repo/spiralscreen_bot.py.
"""
import cv2
import numpy as np
from PIL import Image

from sparagmos.effects import ComposeEffect, EffectContext, EffectResult, register_effect
from sparagmos.effects.stencil_utils import apply_stencil_permutations, preprocess_for_screen


def _make_stencil(img: Image.Image, frequency: int, warp_strength: float) -> Image.Image:
    enhanced = preprocess_for_screen(img)
    h, w = enhanced.shape
    cx, cy = w / 2.0, h / 2.0

    blurred = cv2.GaussianBlur(enhanced, (0, 0), sigmaX=2.0)
    gx = cv2.Sobel(blurred, cv2.CV_32F, 1, 0, ksize=5)
    gy = cv2.Sobel(blurred, cv2.CV_32F, 0, 1, ksize=5)
    line_angle = np.arctan2(gy, gx) + np.pi / 2
    cos2 = cv2.GaussianBlur(np.cos(2 * line_angle), (0, 0), sigmaX=50)
    sin2 = cv2.GaussianBlur(np.sin(2 * line_angle), (0, 0), sigmaX=50)
    smooth_angle = np.arctan2(sin2, cos2) / 2

    mag = np.sqrt(gx ** 2 + gy ** 2)
    mag_thresh = np.percentile(mag, 85)
    edge_weight = cv2.GaussianBlur(
        np.clip(mag / (mag_thresh + 1e-6), 0, 1), (0, 0), sigmaX=30
    )
    edge_weight = np.clip(edge_weight * 3, 0, 1)

    warp_pixels = frequency * warp_strength
    y_g, x_g = np.mgrid[0:h, 0:w].astype(np.float32)
    x_w = x_g + edge_weight * warp_pixels * np.cos(smooth_angle)
    y_w = y_g + edge_weight * warp_pixels * np.sin(smooth_angle)

    r = np.sqrt((x_w - cx) ** 2 + (y_w - cy) ** 2)
    theta = np.arctan2(y_w - cy, x_w - cx)
    spiral_coord = r - (frequency / (2 * np.pi)) * theta
    screen = (spiral_coord % frequency) / frequency

    smoothed = cv2.GaussianBlur(enhanced, (0, 0), sigmaX=1.5)
    gray_01 = np.clip(smoothed.astype(np.float32) / 255.0, 0.1, 0.9)
    return Image.fromarray((gray_01 > screen).astype(np.uint8) * 255)


class SpiralScreenEffect(ComposeEffect):
    name = "spiralscreen"
    description = (
        "Archimedean spiral screen stencil — arms warp to follow image contours, "
        "line width varies with tone. 3 images → 6 permutation composites."
    )
    requires: list[str] = []

    def compose(self, images: list, params: dict, context: EffectContext) -> EffectResult:
        params = self.validate_params(params)
        masks = [_make_stencil(img, params["frequency"], params["warp_strength"]) for img in images]
        outputs = apply_stencil_permutations(images, masks)
        return EffectResult(image=outputs[0], images=outputs, metadata=params)

    def validate_params(self, params: dict) -> dict:
        return {
            "frequency": int(params.get("frequency", 80)),
            "warp_strength": float(params.get("warp_strength", 0.3)),
        }


register_effect(SpiralScreenEffect())
