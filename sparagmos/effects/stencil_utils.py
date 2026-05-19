"""Shared preprocessing and compositing helpers for spiral/stencil effects."""
import cv2
import numpy as np
from PIL import Image

_SCURVE_LUT = np.interp(
    np.arange(256), [0, 64, 128, 192, 255], [0, 25, 128, 230, 255]
).astype(np.uint8)


def preprocess_for_screen(img: Image.Image) -> np.ndarray:
    gray = np.array(img.convert("L"))
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    return _SCURVE_LUT[clahe.apply(gray)]


def apply_stencil_permutations(images: list, masks: list) -> list:
    """For all 6 (s, a, b) permutations, composite images[a]/images[b] through masks[s]."""
    from sparagmos.vendor.collage_bot.stencil_transform import apply_stencil

    return [
        apply_stencil(masks[s], images[a], images[b])
        for s, a, b in [(0, 1, 2), (0, 2, 1), (1, 0, 2), (1, 2, 0), (2, 0, 1), (2, 1, 0)]
    ]
