"""Oil spiral cells (Voronoi + topographic blend) Compose effect.

Ported from collage-bot-repo/oilspiralcells_bot.py.
"""
import cv2
import numpy as np
from PIL import Image

from sparagmos.effects import ComposeEffect, EffectContext, EffectResult, register_effect
from sparagmos.effects.stencil_utils import apply_stencil_permutations, preprocess_for_screen


def _find_peaks_raw(raw_gray: np.ndarray, n_peaks: int, min_dist_frac: float = 0.20) -> list:
    h, w = raw_gray.shape
    blurred = cv2.GaussianBlur(raw_gray.astype(np.float32), (0, 0), sigmaX=60)
    for frac in (min_dist_frac, min_dist_frac * 0.6, min_dist_frac * 0.3):
        radius = max(4, int(min(h, w) * frac))
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (radius * 2 + 1, radius * 2 + 1))
        dilated = cv2.dilate(blurred, kernel)
        local_max = (blurred >= dilated - 0.1) & (blurred > np.percentile(blurred, 60))
        ys, xs = np.where(local_max)
        if len(xs) >= 2:
            order = np.argsort(blurred[ys, xs])[::-1]
            return [(int(xs[i]), int(ys[i])) for i in order[:n_peaks]]
    cols, rows = 4, 4
    return [
        (int(w * (c + 0.5) / cols), int(h * (r + 0.5) / rows))
        for r in range(rows) for c in range(cols)
    ][:n_peaks]


def _make_stencil(
    img: Image.Image, frequency: int, warp_strength: float, n_peaks: int, topo_blend: float
) -> Image.Image:
    raw_gray = np.array(img.convert("L"))
    enhanced = preprocess_for_screen(img)
    h, w = enhanced.shape
    peaks = _find_peaks_raw(raw_gray, n_peaks)

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

    dist_maps = [np.sqrt((x_w - px) ** 2 + (y_w - py) ** 2) for px, py in peaks]
    dist_stack = np.stack(dist_maps, axis=0)
    cell_idx = np.argmin(dist_stack, axis=0)
    r_map = np.min(dist_stack, axis=0)

    theta_map = np.zeros((h, w), dtype=np.float32)
    r_max_map = np.zeros((h, w), dtype=np.float32)
    corners = [(0, 0), (w, 0), (0, h), (w, h)]
    for i, (px, py) in enumerate(peaks):
        mask = (cell_idx == i)
        theta_map[mask] = np.arctan2(y_w[mask] - py, x_w[mask] - px)
        r_max = max(np.sqrt((cx - px) ** 2 + (cy - py) ** 2) for cx, cy in corners)
        r_max_map[mask] = max(r_max, 1.0)

    spiral_phase = r_map ** 3 / (frequency * r_max_map ** 2 + 1e-6) - theta_map / (2 * np.pi)
    topo_gray = cv2.GaussianBlur(raw_gray.astype(np.float32), (0, 0), sigmaX=10)
    topo_phase = topo_gray / 255.0 * (max(h, w) / frequency)
    screen = ((1 - topo_blend) * spiral_phase + topo_blend * topo_phase) % 1.0

    smoothed = cv2.GaussianBlur(enhanced, (0, 0), sigmaX=1.5)
    gray_01 = np.clip(smoothed.astype(np.float32) / 255.0, 0.1, 0.9)
    return Image.fromarray((gray_01 > screen).astype(np.uint8) * 255)


class OilSpiralCellsEffect(ComposeEffect):
    name = "oilspiralcells"
    description = (
        "Voronoi spiral with brightness-contour (topographic) blending — "
        "lines follow both spiral rotation and iso-brightness contours. "
        "3 images → 6 permutation composites."
    )
    requires: list[str] = []

    def compose(self, images: list, params: dict, context: EffectContext) -> EffectResult:
        params = self.validate_params(params)
        masks = [
            _make_stencil(
                img, params["frequency"], params["warp_strength"],
                params["n_peaks"], params["topo_blend"]
            )
            for img in images
        ]
        outputs = apply_stencil_permutations(images, masks)
        return EffectResult(image=outputs[0], images=outputs, metadata=params)

    def validate_params(self, params: dict) -> dict:
        return {
            "frequency": int(params.get("frequency", 35)),
            "warp_strength": float(params.get("warp_strength", 2.0)),
            "n_peaks": int(params.get("n_peaks", 6)),
            "topo_blend": float(params.get("topo_blend", 0.2)),
        }


register_effect(OilSpiralCellsEffect())
