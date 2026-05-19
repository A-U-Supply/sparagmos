"""Oil spiral cells bleed (Voronoi + chrome fill effects) Compose effect.

Ported from collage-bot-repo/oilspiralcellsbleed_bot.py.
"""
import cv2
import numpy as np
from PIL import Image

from sparagmos.effects import ComposeEffect, EffectContext, EffectResult, register_effect
from sparagmos.effects.stencil_utils import preprocess_for_screen

PROC_MAX = 768


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
    img: Image.Image,
    frequency: int,
    warp_strength: float,
    n_peaks: int,
    topo_blend: float,
    bleed_strength: float,
):
    """Returns (mask PIL Image, smooth_angle ndarray) at original resolution."""
    raw_gray = np.array(img.convert("L"))
    enhanced = preprocess_for_screen(img)
    h, w = enhanced.shape

    scale = min(1.0, PROC_MAX / max(h, w))
    if scale < 1.0:
        ph, pw = int(h * scale), int(w * scale)
        enhanced = cv2.resize(enhanced, (pw, ph), interpolation=cv2.INTER_AREA)
        raw_gray = cv2.resize(raw_gray, (pw, ph), interpolation=cv2.INTER_AREA)
    else:
        ph, pw = h, w

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
    y_g, x_g = np.mgrid[0:ph, 0:pw].astype(np.float32)
    x_w = x_g + edge_weight * warp_pixels * np.cos(smooth_angle)
    y_w = y_g + edge_weight * warp_pixels * np.sin(smooth_angle)

    dist_maps = [np.sqrt((x_w - px) ** 2 + (y_w - py) ** 2) for px, py in peaks]
    dist_stack = np.stack(dist_maps, axis=0)
    cell_idx = np.argmin(dist_stack, axis=0)
    r_map = np.min(dist_stack, axis=0)

    theta_map = np.zeros((ph, pw), dtype=np.float32)
    r_max_map = np.zeros((ph, pw), dtype=np.float32)
    corners = [(0, 0), (pw, 0), (0, ph), (pw, ph)]
    for i, (px, py) in enumerate(peaks):
        m = (cell_idx == i)
        theta_map[m] = np.arctan2(y_w[m] - py, x_w[m] - px)
        r_max = max(np.sqrt((cx - px) ** 2 + (cy - py) ** 2) for cx, cy in corners)
        r_max_map[m] = max(r_max, 1.0)

    spiral_phase = r_map / frequency - theta_map / (2 * np.pi)
    topo_gray = cv2.GaussianBlur(raw_gray.astype(np.float32), (0, 0), sigmaX=10)
    topo_phase = topo_gray / 255.0 * (max(ph, pw) / frequency)
    screen = ((1 - topo_blend) * spiral_phase + topo_blend * topo_phase) % 1.0

    smoothed = cv2.GaussianBlur(enhanced, (0, 0), sigmaX=1.5)
    gray_01 = np.clip(smoothed.astype(np.float32) / 255.0, 0.1, 0.9)
    r_norm = r_map / (r_max_map + 1e-6)
    bleed_boost = bleed_strength * (1.0 - r_norm)
    gray_boosted = np.clip(gray_01 + bleed_boost, 0.0, 1.0)
    binary = (gray_boosted > screen).astype(np.uint8) * 255

    if scale < 1.0:
        binary = cv2.resize(binary, (w, h), interpolation=cv2.INTER_NEAREST)
        smooth_angle = cv2.resize(smooth_angle, (w, h), interpolation=cv2.INTER_LINEAR)

    return Image.fromarray(binary), smooth_angle


def _apply_fill_effects(
    img_arr: np.ndarray,
    smooth_angle: np.ndarray,
    chroma_shift: int,
    ripple_amplitude: int,
    ripple_wavelength: float,
) -> np.ndarray:
    h, w = img_arr.shape[:2]
    y_g, x_g = np.mgrid[0:h, 0:w].astype(np.float32)
    cos_a = np.cos(smooth_angle)
    sin_a = np.sin(smooth_angle)

    phase = x_g * cos_a + y_g * sin_a
    ripple = (ripple_amplitude * np.sin(2.0 * np.pi * phase / ripple_wavelength)).astype(np.float32)
    xs = np.clip(x_g + ripple * (-sin_a), 0, w - 1)
    ys = np.clip(y_g + ripple * cos_a, 0, h - 1)
    out = cv2.remap(img_arr, xs, ys, cv2.INTER_LINEAR)

    xs_r = np.clip(x_g + chroma_shift * cos_a, 0, w - 1)
    ys_r = np.clip(y_g + chroma_shift * sin_a, 0, h - 1)
    xs_b = np.clip(x_g - chroma_shift * cos_a, 0, w - 1)
    ys_b = np.clip(y_g - chroma_shift * sin_a, 0, h - 1)
    r_ch = cv2.remap(out[:, :, 0], xs_r, ys_r, cv2.INTER_LINEAR)
    b_ch = cv2.remap(out[:, :, 2], xs_b, ys_b, cv2.INTER_LINEAR)
    out = np.stack([r_ch, out[:, :, 1], b_ch], axis=2)

    lut = np.clip(128 + 128 * np.tanh((np.arange(256, dtype=np.float32) - 128) / 85.0), 0, 255).astype(np.uint8)
    return lut[out]


def _apply_bulge_warp(img_arr: np.ndarray, mask_L: np.ndarray, bulge_strength: float) -> np.ndarray:
    h, w = img_arr.shape[:2]
    y_g, x_g = np.mgrid[0:h, 0:w].astype(np.float32)
    inside = (mask_L > 127).astype(np.uint8) * 255
    dist_in = cv2.distanceTransform(inside, cv2.DIST_L2, 5)
    nonzero = dist_in[dist_in > 0]
    scale = float(np.percentile(nonzero, 95)) if len(nonzero) else 1.0
    height = np.clip(dist_in / (scale + 1e-6), 0, 1).astype(np.float32)
    dist_smooth = cv2.GaussianBlur(dist_in, (0, 0), sigmaX=scale * 0.5)
    gx_h = cv2.Sobel(dist_smooth, cv2.CV_32F, 1, 0, ksize=5)
    gy_h = cv2.Sobel(dist_smooth, cv2.CV_32F, 0, 1, ksize=5)
    grad_mag = np.sqrt(gx_h ** 2 + gy_h ** 2) + 1e-6
    nx_h = gx_h / grad_mag
    ny_h = gy_h / grad_mag
    displacement = (bulge_strength * scale * (1.0 - height)).astype(np.float32)
    src_x = np.clip(x_g - displacement * nx_h, 0, w - 1)
    src_y = np.clip(y_g - displacement * ny_h, 0, h - 1)
    return cv2.remap(img_arr, src_x, src_y, cv2.INTER_LINEAR)


class OilSpiralCellsBleedEffect(ComposeEffect):
    name = "oilspiralcellsbleed"
    description = (
        "Voronoi spiral with chrome fill effects: sinusoidal ripple warp, "
        "chromatic aberration, and raised-rivulet bulge warp. "
        "3 images → 6 permutation composites."
    )
    requires: list[str] = []

    def compose(self, images: list, params: dict, context: EffectContext) -> EffectResult:
        params = self.validate_params(params)

        masks = []
        smooth_angles = []
        for img in images:
            mask, angle = _make_stencil(
                img,
                params["frequency"],
                params["warp_strength"],
                params["n_peaks"],
                params["topo_blend"],
                params["bleed_strength"],
            )
            masks.append(mask)
            smooth_angles.append(angle)

        target_w, target_h = max((img.size for img in images), key=lambda s: s[0] * s[1])
        res_scale = min(target_w, target_h) / 1024.0
        fx_kwargs = dict(
            chroma_shift=int(params["chroma_shift"] * res_scale),
            ripple_amplitude=int(params["ripple_amplitude"] * res_scale),
            ripple_wavelength=params["ripple_wavelength"] * res_scale,
        )

        outputs = []
        for s, a, b in [(0, 1, 2), (0, 2, 1), (1, 0, 2), (1, 2, 0), (2, 0, 1), (2, 1, 0)]:
            img_a = np.array(images[a].convert("RGB").resize((target_w, target_h), Image.LANCZOS))
            img_b = np.array(images[b].convert("RGB").resize((target_w, target_h), Image.LANCZOS))
            mask_l = np.array(masks[s].resize((target_w, target_h), Image.NEAREST).convert("L"))
            angle_a = cv2.resize(smooth_angles[s], (target_w, target_h), interpolation=cv2.INTER_LINEAR)
            angle_b = cv2.resize(smooth_angles[b], (target_w, target_h), interpolation=cv2.INTER_LINEAR)

            img_a = _apply_fill_effects(img_a, angle_a, **fx_kwargs)
            img_b = _apply_fill_effects(img_b, angle_b, **fx_kwargs)
            img_a = _apply_bulge_warp(img_a, mask_l, params["bulge_strength"])
            img_b = _apply_bulge_warp(img_b, mask_l, params["bulge_strength"])

            composite = np.where(
                mask_l[:, :, np.newaxis] > 127,
                img_a.astype(np.float32),
                img_b.astype(np.float32),
            ).astype(np.uint8)

            blurred = cv2.GaussianBlur(composite, (0, 0), sigmaX=2.0)
            sharp = cv2.addWeighted(composite, 1.8, blurred, -0.8, 0)
            outputs.append(Image.fromarray(sharp))

        return EffectResult(image=outputs[0], images=outputs, metadata=params)

    def validate_params(self, params: dict) -> dict:
        return {
            "frequency": int(params.get("frequency", 15)),
            "warp_strength": float(params.get("warp_strength", 4.0)),
            "n_peaks": int(params.get("n_peaks", 6)),
            "topo_blend": float(params.get("topo_blend", 0.2)),
            "bleed_strength": float(params.get("bleed_strength", 0.35)),
            "chroma_shift": int(params.get("chroma_shift", 10)),
            "ripple_amplitude": int(params.get("ripple_amplitude", 20)),
            "ripple_wavelength": float(params.get("ripple_wavelength", 40.0)),
            "bulge_strength": float(params.get("bulge_strength", 0.8)),
        }


register_effect(OilSpiralCellsBleedEffect())
