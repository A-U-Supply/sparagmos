"""Tone effect — levels, posterize, binarize, and photographic tints.

The missing tonal primitive: every other effect either embeds its own
normalization (mask_composite, stencil_utils) or has none at all. This one
exposes those moves directly so recipes can anchor contrast (the anti-mud
fix), crush to pure binary, quantize to spot-color inks, or tone a chain
with the vendored cyanotype/silver treatments.
"""

from __future__ import annotations

import random

import numpy as np
from PIL import Image

from sparagmos.effects import ConfigError, Effect, EffectContext, EffectResult, register_effect
from sparagmos.vendor.collage_bot.cyanotype_bot import to_cyanotype
from sparagmos.vendor.collage_bot.silver_bot import to_silver_halation

MODES = ("none", "grayscale", "binary", "posterize", "normalize", "invert")
TINTS = ("none", "cyanotype", "silver", "sepia", "bronze", "ink")

# Duotone endpoints: gray 0 maps to the first color, 255 to the second,
# with a midpoint to keep the ramp from going muddy.
_DUOTONES = {
    "sepia": ((26, 16, 8), (150, 108, 60), (244, 232, 208)),
    "bronze": ((20, 10, 4), (176, 118, 52), (248, 234, 200)),
}

# Riso-style spot inks: shadows take the ink, highlights take paper white.
_INKS = {
    "crimson": (196, 30, 58),
    "cobalt": (0, 71, 171),
    "vermilion": (217, 56, 30),
    "forest": (34, 90, 52),
    "violet": (86, 40, 140),
    "teal": (0, 110, 110),
}
_PAPER = (244, 240, 230)


def _duotone_lut(shadow: tuple, mid: tuple, highlight: tuple) -> np.ndarray:
    """Build a 256x3 LUT interpolating shadow -> mid -> highlight."""
    xs = [0, 128, 255]
    lut = np.zeros((256, 3), dtype=np.uint8)
    for ch in range(3):
        ys = [shadow[ch], mid[ch], highlight[ch]]
        lut[:, ch] = np.interp(np.arange(256), xs, ys).astype(np.uint8)
    return lut


def _apply_duotone(image: Image.Image, lut: np.ndarray) -> Image.Image:
    gray = np.array(image.convert("L"))
    return Image.fromarray(lut[gray])


def _otsu_threshold(gray: np.ndarray) -> int:
    hist, _ = np.histogram(gray, bins=256, range=(0, 256))
    total = gray.size
    best_t, best_var = 128, 0.0
    cum_count = np.cumsum(hist)
    cum_sum = np.cumsum(hist * np.arange(256))
    for t in range(1, 256):
        bg_count = cum_count[t - 1]
        fg_count = total - bg_count
        if bg_count == 0 or fg_count == 0:
            continue
        bg_mean = cum_sum[t - 1] / bg_count
        fg_mean = (cum_sum[255] - cum_sum[t - 1]) / fg_count
        var = bg_count * fg_count * (bg_mean - fg_mean) ** 2
        if var > best_var:
            best_var, best_t = var, t
    return best_t


def _normalize(arr: np.ndarray, cutoff: float) -> np.ndarray:
    """Percentile contrast stretch on luminance, applied uniformly to RGB."""
    gray = arr.mean(axis=2)
    low = np.percentile(gray, cutoff)
    high = np.percentile(gray, 100.0 - cutoff)
    if high - low < 1.0:
        return arr
    stretched = (arr.astype(np.float32) - low) * (255.0 / (high - low))
    return np.clip(stretched, 0, 255).astype(np.uint8)


class ToneEffect(Effect):
    name = "tone"
    description = "Levels/posterize/binary/normalize plus cyanotype/silver/duotone/ink tints"
    requires: list[str] = []

    def apply(self, image: Image.Image, params: dict, context: EffectContext) -> EffectResult:
        params = self.validate_params(params)
        img = image.convert("RGB")

        if params["max_edge"] and max(img.size) > params["max_edge"]:
            img = img.copy()
            img.thumbnail((params["max_edge"], params["max_edge"]))

        if params["normalize_first"] and params["mode"] != "normalize":
            img = Image.fromarray(_normalize(np.array(img), params["cutoff"]))

        mode = params["mode"]
        if mode == "grayscale":
            img = img.convert("L").convert("RGB")
        elif mode == "binary":
            gray = np.array(img.convert("L"))
            t = params["threshold"] if params["threshold"] >= 0 else _otsu_threshold(gray)
            img = Image.fromarray(((gray > t).astype(np.uint8) * 255)).convert("RGB")
        elif mode == "posterize":
            arr = np.array(img).astype(np.float32)
            levels = params["levels"]
            step = 255.0 / (levels - 1)
            arr = np.round(arr / step) * step
            img = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))
        elif mode == "normalize":
            img = Image.fromarray(_normalize(np.array(img), params["cutoff"]))
        elif mode == "invert":
            img = Image.fromarray(255 - np.array(img))

        tint = params["tint"]
        if tint == "cyanotype":
            img = to_cyanotype(img)
        elif tint == "silver":
            img = to_silver_halation(img)
        elif tint in _DUOTONES:
            img = _apply_duotone(img, _duotone_lut(*_DUOTONES[tint]))
        elif tint == "ink":
            rng = random.Random(context.seed)
            ink_name = rng.choice(params["inks"])
            ink = _INKS[ink_name]
            img = _apply_duotone(img, _duotone_lut(ink, tuple((i + p) // 2 for i, p in zip(ink, _PAPER)), _PAPER))
            return EffectResult(image=img, metadata={**params, "ink": ink_name})

        return EffectResult(image=img, metadata=params)

    def validate_params(self, params: dict) -> dict:
        mode = params.get("mode", "none")
        if mode not in MODES:
            raise ConfigError(f"Unknown tone mode {mode!r}, expected one of {MODES}", self.name, "mode")

        tint = params.get("tint", "none")
        if tint not in TINTS:
            raise ConfigError(f"Unknown tone tint {tint!r}, expected one of {TINTS}", self.name, "tint")

        inks = params.get("inks", list(_INKS.keys()))
        if isinstance(inks, str):
            inks = [inks]
        unknown = [i for i in inks if i not in _INKS]
        if unknown:
            raise ConfigError(f"Unknown ink(s) {unknown}, expected from {sorted(_INKS)}", self.name, "inks")

        threshold = params.get("threshold", -1)  # -1 = Otsu
        return {
            "mode": mode,
            "tint": tint,
            "inks": inks,
            "levels": max(2, min(8, int(params.get("levels", 3)))),
            "cutoff": max(0.0, min(5.0, float(params.get("cutoff", 1.0)))),
            "threshold": max(-1, min(255, int(threshold))),
            "normalize_first": bool(params.get("normalize_first", False)),
            "max_edge": max(0, min(8192, int(params.get("max_edge", 0)))),
        }


register_effect(ToneEffect())
