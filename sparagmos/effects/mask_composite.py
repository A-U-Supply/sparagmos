"""Mask composite effect — select between two images using a derived mask."""

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

VALID_MASK_SOURCES = {"luminance", "edges", "threshold", "noise", "gradient"}


def _build_mask(
    base_gray: np.ndarray,
    mask_source: str,
    threshold: int,
    seed: int,
) -> np.ndarray:
    """Build a uint8 mask (0 or 255) from the base image.

    Args:
        base_gray: Grayscale base image as uint8 numpy array, shape (H, W).
        mask_source: One of VALID_MASK_SOURCES.
        threshold: Cutoff value [0, 255] for binary masks.
        seed: RNG seed for noise mask.

    Returns:
        uint8 numpy array of shape (H, W) with values 0 or 255.
    """
    h, w = base_gray.shape

    if mask_source in ("luminance", "threshold"):
        mask = np.where(base_gray >= threshold, np.uint8(255), np.uint8(0)).astype(np.uint8)

    elif mask_source == "edges":
        edges = cv2.Canny(base_gray, threshold // 2, threshold)
        kernel = np.ones((3, 3), dtype=np.uint8)
        mask = cv2.dilate(edges, kernel, iterations=1)

    elif mask_source == "noise":
        rng = np.random.RandomState(seed)
        noise = (rng.rand(h, w) * 255).astype(np.uint8)
        mask = np.where(noise >= threshold, np.uint8(255), np.uint8(0)).astype(np.uint8)

    elif mask_source == "gradient":
        # Horizontal linear gradient: 0 on the left, 255 on the right
        row = np.linspace(0, 255, w, dtype=np.float32)
        gradient = np.tile(row, (h, 1)).astype(np.uint8)
        mask = np.where(gradient >= threshold, np.uint8(255), np.uint8(0)).astype(np.uint8)

    else:
        raise ConfigError(
            f"Unknown mask_source: {mask_source!r}. Valid sources: {sorted(VALID_MASK_SOURCES)}",
            effect_name="mask_composite",
            param_name="mask_source",
        )

    return mask


class MaskCompositeEffect(ComposeEffect):
    """Select between two images using a mask derived from the first image's features.

    The mask is built from the first (base) image and controls which image
    shows through: mask=255 reveals the base, mask=0 reveals the second image.

    Examples:
        >>> effect = MaskCompositeEffect()
        >>> result = effect.compose([base_img, reveal_img], {"mask_source": "edges"}, ctx)
    """

    name = "mask_composite"
    description = "Mask-based selection between two images"
    requires: list[str] = []

    def compose(
        self, images: list[Image.Image], params: dict, context: EffectContext
    ) -> EffectResult:
        """Composite two images using a feature-derived mask.

        Args:
            images: List of one or two PIL Images. The first image provides the
                base content and drives mask generation. The second image is the
                reveal layer (shown where the mask is 0). If only one image is
                provided it is returned as-is.
            params: Effect parameters (mask_source, threshold, feather, invert).
            context: Shared pipeline context (seed used for noise mask).

        Returns:
            EffectResult with composited image matching the first image's dimensions.
        """
        params = self.validate_params(params)
        mask_source: str = params["mask_source"]
        threshold: int = params["threshold"]
        feather: int = params["feather"]
        invert: bool = params["invert"]

        base_img = images[0].convert("RGB")

        # Single-image passthrough — nothing to composite against
        if len(images) < 2:
            return EffectResult(image=base_img, metadata={"mask_source": mask_source})

        reveal_img = images[1].convert("RGB")
        base_w, base_h = base_img.size

        # Resize reveal to match base if dimensions differ
        if reveal_img.size != base_img.size:
            reveal_img = reveal_img.resize((base_w, base_h), Image.LANCZOS)

        # Build grayscale version of base for mask generation
        base_gray = np.array(base_img.convert("L"), dtype=np.uint8)

        # Generate binary mask
        mask = _build_mask(base_gray, mask_source, threshold, context.seed)

        # Optionally invert before feathering
        if invert:
            mask = 255 - mask

        # Convert to PIL for feathering
        mask_pil = Image.fromarray(mask, mode="L")

        # Apply feathering (soft edges)
        if feather > 0:
            mask_pil = mask_pil.filter(ImageFilter.GaussianBlur(radius=feather))

        # Composite: mask=255 → base shows through, mask=0 → reveal shows through
        result_img = Image.composite(base_img, reveal_img, mask_pil)

        return EffectResult(
            image=result_img,
            metadata={
                "mask_source": mask_source,
                "threshold": threshold,
                "feather": feather,
                "invert": invert,
            },
        )

    def validate_params(self, params: dict) -> dict:
        """Validate and normalize mask_composite parameters.

        Args:
            params: Raw parameters dict.

        Returns:
            Normalized parameters with defaults applied.

        Raises:
            ConfigError: If mask_source is not a recognized value.
        """
        mask_source = params.get("mask_source", "luminance")
        if mask_source not in VALID_MASK_SOURCES:
            raise ConfigError(
                f"Unknown mask_source: {mask_source!r}. Valid sources: {sorted(VALID_MASK_SOURCES)}",
                effect_name="mask_composite",
                param_name="mask_source",
            )

        threshold = int(params.get("threshold", 128))
        threshold = max(0, min(255, threshold))

        feather = int(params.get("feather", 0))
        feather = max(0, min(50, feather))

        invert = bool(params.get("invert", False))

        return {
            "mask_source": mask_source,
            "threshold": threshold,
            "feather": feather,
            "invert": invert,
        }


register_effect(MaskCompositeEffect())
