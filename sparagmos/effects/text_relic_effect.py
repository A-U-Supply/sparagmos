"""Text relic effect — OCR-guarded destruction.

Two-image compose: text detected in image A survives untouched (or
embossed) while everything around it is REPLACED by a destroyed image B
— A's words embedded in B's ruins. Born from the stacks survey:
surviving text was the single strongest predictor of a good sparagmos
output, but until now it only survived by luck.
"""

from __future__ import annotations

import random

import numpy as np
from PIL import Image, ImageFilter

from sparagmos.effects import (
    ComposeEffect,
    ConfigError,
    EffectContext,
    EffectResult,
    register_effect,
)

BACKGROUNDS = ("washout", "mosh", "sort", "random", "keep")
PRESERVE = ("sharp", "emboss")


class TextRelicEffect(ComposeEffect):
    name = "text_relic"
    description = "OCR finds A's text; it stays crisp, embedded in the destroyed remains of B"
    requires: list[str] = ["tesseract"]

    def compose(self, images: list[Image.Image], params: dict, context: EffectContext) -> EffectResult:
        params = self.validate_params(params)

        try:
            import pytesseract
        except ImportError as e:
            raise ImportError(
                "text_relic requires pytesseract. Install with: pip install pytesseract"
            ) from e

        img = images[0].convert("RGB")
        ruin_img = (images[1] if len(images) > 1 else images[0]).convert("RGB")
        if ruin_img.size != img.size:
            ruin_img = ruin_img.resize(img.size, Image.LANCZOS)
        arr = np.array(img)
        ruin = np.array(ruin_img)
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

        # keep: destroy nothing — stamp A's text regions onto B as-is.
        destroyed = ruin if background == "keep" else self._destroy(ruin, background, rng)

        fallback = None
        if not boxes and background != "keep":
            # Asemic fallback: no words found, so A's strongest marks survive
            # instead — dilated high-gradient contours, padded like word boxes.
            import cv2

            gray = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)
            gx = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
            gy = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
            mag = np.sqrt(gx * gx + gy * gy)
            strong = mag > np.percentile(mag, 96)
            kernel = np.ones((max(3, pad), max(3, pad)), np.uint8)
            mask = cv2.dilate(strong.astype(np.uint8), kernel).astype(bool)
            boxes = -1  # sentinel: asemic marks, not words
            fallback = "asemic"

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
            metadata={**params, "background_used": background, "text_boxes": boxes,
                      "fallback": fallback},
        )

    def apply(self, image: Image.Image, params: dict, context: EffectContext) -> EffectResult:
        return self.compose([image, image], params, context)

    def _destroy(self, arr: np.ndarray, background: str, rng: random.Random) -> np.ndarray:
        if background == "washout":
            return self._washout(arr)
        if background == "mosh":
            return self._mosh(arr, rng)
        return self._sort(arr, rng)

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
    def _sort(arr: np.ndarray, rng: random.Random) -> np.ndarray:
        """Column-sort pixels by brightness in BOUNDED segments — texture,
        not frame-length smears."""
        result = arr.copy()
        gray = arr.mean(axis=2)
        h = arr.shape[0]
        for x in range(arr.shape[1]):
            y = rng.randint(0, 60)
            while y < h - 12:
                seg = rng.randint(40, 120)
                y1 = min(h, y + seg)
                if rng.random() < 0.75:
                    order = np.argsort(gray[y:y1, x])
                    result[y:y1, x] = arr[y:y1, x][order]
                y = y1 + rng.randint(4, 40)
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
