"""Text relic effect — OCR-guarded destruction.

Detected text regions survive untouched (or embossed) while everything
around them is destroyed. Born from the stacks survey: surviving text was
the single strongest predictor of a good sparagmos output, but until now
it only survived by luck.
"""

from __future__ import annotations

import random

import numpy as np
from PIL import Image, ImageFilter

from sparagmos.effects import ConfigError, Effect, EffectContext, EffectResult, register_effect

BACKGROUNDS = ("washout", "mosh", "sort", "random")
PRESERVE = ("sharp", "emboss")


class TextRelicEffect(Effect):
    name = "text_relic"
    description = "OCR finds text; text stays crisp while the rest of the image is destroyed"
    requires: list[str] = ["tesseract"]

    def apply(self, image: Image.Image, params: dict, context: EffectContext) -> EffectResult:
        params = self.validate_params(params)

        try:
            import pytesseract
        except ImportError as e:
            raise ImportError(
                "text_relic requires pytesseract. Install with: pip install pytesseract"
            ) from e

        img = image.convert("RGB")
        arr = np.array(img)
        h, w = arr.shape[:2]
        rng = random.Random(context.seed)

        data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
        pad = params["pad"]
        mask = np.zeros((h, w), dtype=bool)
        boxes = 0
        for i in range(len(data["text"])):
            txt = data["text"][i].strip()
            try:
                conf = float(data["conf"][i])
            except (TypeError, ValueError):
                continue
            if not txt or conf < params["min_conf"]:
                continue
            x, y = data["left"][i], data["top"][i]
            bw, bh = data["width"][i], data["height"][i]
            # Reject degenerate boxes (tesseract sometimes returns full-frame noise)
            if bw <= 2 or bh <= 2 or bw > w * 0.95 or bh > h * 0.5:
                continue
            x0, y0 = max(0, x - pad), max(0, y - pad)
            x1, y1 = min(w, x + bw + pad), min(h, y + bh + pad)
            mask[y0:y1, x0:x1] = True
            boxes += 1

        background = params["background"]
        if background == "random":
            background = rng.choice(("washout", "mosh", "sort"))

        destroyed = self._destroy(arr, background, rng)

        if boxes:
            relic = arr.copy()
            if params["preserve"] == "emboss":
                embossed = np.array(Image.fromarray(arr).filter(ImageFilter.EMBOSS).convert("RGB"))
                relic = ((arr.astype(np.float32) * 0.6) + (embossed.astype(np.float32) * 0.4)).astype(np.uint8)
            result = np.where(mask[:, :, None], relic, destroyed)
        else:
            result = destroyed

        return EffectResult(
            image=Image.fromarray(result),
            metadata={**params, "background_used": background, "text_boxes": boxes},
        )

    def _destroy(self, arr: np.ndarray, background: str, rng: random.Random) -> np.ndarray:
        if background == "washout":
            return self._washout(arr)
        if background == "mosh":
            return self._mosh(arr, rng)
        return self._sort(arr)

    @staticmethod
    def _washout(arr: np.ndarray) -> np.ndarray:
        """Posterize + desaturate + lift toward paper white."""
        gray = arr.mean(axis=2, keepdims=True)
        desat = arr.astype(np.float32) * 0.35 + gray * 0.65
        lifted = desat * 0.55 + 255.0 * 0.45
        step = 255.0 / 3
        posterized = np.round(lifted / step) * step
        return np.clip(posterized, 0, 255).astype(np.uint8)

    @staticmethod
    def _mosh(arr: np.ndarray, rng: random.Random) -> np.ndarray:
        """Shift macroblocks as if predicted from the wrong frame."""
        result = arr.copy()
        h, w = arr.shape[:2]
        block = max(8, min(h, w) // 24)
        for by in range(0, h - block, block):
            for bx in range(0, w - block, block):
                if rng.random() < 0.45:
                    dy = rng.randint(-3, 3) * block
                    dx = rng.randint(-3, 3) * block
                    sy = min(max(0, by + dy), h - block)
                    sx = min(max(0, bx + dx), w - block)
                    result[by:by + block, bx:bx + block] = arr[sy:sy + block, sx:sx + block]
        return result

    @staticmethod
    def _sort(arr: np.ndarray) -> np.ndarray:
        """Column-sort pixels by brightness in mid-tone spans."""
        result = arr.copy()
        gray = arr.mean(axis=2)
        span = (gray > 60) & (gray < 200)
        for x in range(arr.shape[1]):
            ys = np.where(span[:, x])[0]
            if len(ys) < 8:
                continue
            y0, y1 = ys[0], ys[-1] + 1
            order = np.argsort(gray[y0:y1, x])
            result[y0:y1, x] = arr[y0:y1, x][order]
        return result

    def validate_params(self, params: dict) -> dict:
        background = params.get("background", "random")
        if background not in BACKGROUNDS:
            raise ConfigError(
                f"Unknown background {background!r}, expected one of {BACKGROUNDS}", self.name, "background"
            )
        preserve = params.get("preserve", "sharp")
        if preserve not in PRESERVE:
            raise ConfigError(
                f"Unknown preserve {preserve!r}, expected one of {PRESERVE}", self.name, "preserve"
            )
        return {
            "background": background,
            "preserve": preserve,
            "pad": max(0, min(60, int(params.get("pad", 10)))),
            "min_conf": max(0, min(95, int(params.get("min_conf", 40)))),
        }


register_effect(TextRelicEffect())
