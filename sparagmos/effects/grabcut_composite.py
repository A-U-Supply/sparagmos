"""GrabCut composite effect — segment foreground from multiple images and produce all permutations."""

from __future__ import annotations

from itertools import permutations

import cv2
import numpy as np
from PIL import Image
from scipy.ndimage import gaussian_filter, uniform_filter

from sparagmos.effects import (
    ComposeEffect,
    EffectContext,
    EffectResult,
    register_effect,
)


def _segment_grabcut(img_rgb: np.ndarray) -> np.ndarray:
    """GrabCut foreground segmentation with 10%-inset initialisation rect."""
    h, w = img_rgb.shape[:2]
    margin = int(min(h, w) * 0.10)
    rect = (margin, margin, w - 2 * margin, h - 2 * margin)
    mask = np.zeros((h, w), np.uint8)
    bgd = np.zeros((1, 65), np.float64)
    fgd = np.zeros((1, 65), np.float64)
    cv2.grabCut(img_rgb, mask, rect, bgd, fgd, 5, cv2.GC_INIT_WITH_RECT)
    return np.where(
        (mask == cv2.GC_FGD) | (mask == cv2.GC_PR_FGD), 1, 0
    ).astype(np.uint8)


def _segment_center(img_rgb: np.ndarray) -> np.ndarray:
    """Center-weighted Gaussian blob — centre is foreground, edges are background."""
    h, w = img_rgb.shape[:2]
    Y, X = np.ogrid[:h, :w]
    gauss = np.exp(
        -(
            (X - w / 2) ** 2 / (2 * (w * 0.35) ** 2)
            + (Y - h / 2) ** 2 / (2 * (h * 0.35) ** 2)
        )
    )
    return (gauss > 0.4).astype(np.uint8)


def _segment_spectral(img_rgb: np.ndarray) -> np.ndarray:
    """Spectral Residual saliency (Hou & Zhang 2007) via numpy FFT."""
    gray = img_rgb.mean(axis=2)
    small = cv2.resize(gray.astype(np.float32), (64, 64)) / 255.0
    F = np.fft.fft2(small)
    log_amp = np.log(np.abs(F) + 1e-8)
    residual = log_amp - uniform_filter(log_amp, size=3)
    sal_small = np.abs(np.fft.ifft2(np.exp(residual + 1j * np.angle(F)))) ** 2
    sal = cv2.resize(sal_small.real, (gray.shape[1], gray.shape[0]))
    sal = gaussian_filter(sal, sigma=min(gray.shape) * 0.05)
    sal = (sal - sal.min()) / (sal.max() - sal.min() + 1e-8)
    return (sal > 0.4).astype(np.uint8)


_SEG_METHODS = {
    "grabcut": _segment_grabcut,
    "center": _segment_center,
    "spectral": _segment_spectral,
}


class GrabCutCompositeEffect(ComposeEffect):
    """Segment foreground from each input image and composite all fg/bg permutations.

    Takes 2–5 images. For N images produces N*(N-1) outputs: every foreground
    on every other background. Hard binary mask — no feathering — the cut line
    is the aesthetic statement.

    Examples:
        >>> effect = GrabCutCompositeEffect()
        >>> result = effect.compose([img_a, img_b, img_c], {"seg_method": "grabcut"}, ctx)
        >>> len(result.images)  # 6 permutations for 3 inputs
        6
    """

    name = "grabcut_composite"
    description = "GrabCut fg/bg segmentation — composites all permutations of N images."
    requires: list[str] = []

    def compose(
        self, images: list[Image.Image], params: dict, context: EffectContext
    ) -> EffectResult:
        params = self.validate_params(params)
        seg_fn = _SEG_METHODS[params["seg_method"]]

        imgs = [np.array(img.convert("RGB")) for img in images]
        masks = [seg_fn(img) for img in imgs]

        outputs = []
        for fg_i, bg_i in permutations(range(len(imgs)), 2):
            h, w = imgs[fg_i].shape[:2]
            bg = cv2.resize(imgs[bg_i], (w, h))
            m = np.stack([masks[fg_i]] * 3, axis=2)
            result = imgs[fg_i] * m + bg * (1 - m)
            outputs.append(Image.fromarray(result.astype(np.uint8)))

        return EffectResult(
            image=outputs[0],
            images=outputs,
            metadata={"seg_method": params["seg_method"], "count": len(outputs)},
        )

    def validate_params(self, params: dict) -> dict:
        seg = params.get("seg_method", "grabcut")
        if seg not in _SEG_METHODS:
            seg = "grabcut"
        return {"seg_method": seg}


register_effect(GrabCutCompositeEffect())
