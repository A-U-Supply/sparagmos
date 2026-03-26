"""Collage compositing effect — spatial arrangement of multiple images."""

from __future__ import annotations

import math
import random

from PIL import Image

from sparagmos.effects import (
    ComposeEffect,
    ConfigError,
    EffectContext,
    EffectResult,
    register_effect,
)

VALID_LAYOUTS = {"grid", "scatter", "strips", "mosaic"}
VALID_CANVAS_SIZES = {"largest", "smallest", "fixed_1024"}


def _canvas_size(images: list[Image.Image], canvas_size: str) -> tuple[int, int]:
    """Compute the output canvas dimensions from the input images.

    Args:
        images: List of PIL Images (at least one).
        canvas_size: One of ``largest``, ``smallest``, ``fixed_1024``.

    Returns:
        ``(width, height)`` tuple.
    """
    if canvas_size == "fixed_1024":
        return (1024, 1024)
    widths = [img.width for img in images]
    heights = [img.height for img in images]
    if canvas_size == "largest":
        return (max(widths), max(heights))
    # smallest
    return (min(widths), min(heights))


def _layout_grid(
    canvas: Image.Image,
    images: list[Image.Image],
    overlap: float,
    rng: random.Random,
) -> None:
    """Place images in a grid, with optional overlap, onto *canvas* in-place.

    Args:
        canvas: Destination RGB canvas (modified in-place).
        images: Source images.
        overlap: Fractional overlap between cells [0.0, 0.5].
        rng: Seeded random generator for shuffle.
    """
    n = len(images)
    cols = math.ceil(math.sqrt(n))
    rows = math.ceil(n / cols)

    cw, ch = canvas.size

    # Cell dimensions before overlap reduction
    cell_w = cw / cols
    cell_h = ch / rows

    # Shift step accounts for overlap (pieces overlap by fraction of cell size)
    step_x = cell_w * (1.0 - overlap)
    step_y = cell_h * (1.0 - overlap)

    # Shuffle assignment order
    order = list(range(n))
    rng.shuffle(order)

    for idx, src_idx in enumerate(order):
        col = idx % cols
        row = idx // cols
        x = int(round(col * step_x))
        y = int(round(row * step_y))
        piece = images[src_idx].convert("RGB").resize(
            (int(math.ceil(cell_w)), int(math.ceil(cell_h))), Image.LANCZOS
        )
        canvas.paste(piece, (x, y))


def _layout_scatter(
    canvas: Image.Image,
    images: list[Image.Image],
    overlap: float,
    rotation: int,
    scale_variance: float,
    rng: random.Random,
) -> None:
    """Place images at random positions, rotations, and scales onto *canvas*.

    Args:
        canvas: Destination RGB canvas (modified in-place).
        images: Source images.
        overlap: Not directly used for scatter (all positions are random).
        rotation: Maximum rotation angle in degrees.
        scale_variance: Fractional variation in piece size.
        rng: Seeded random generator.
    """
    cw, ch = canvas.size
    n = len(images)
    base_scale = 1.0 / math.ceil(math.sqrt(n))

    for img in images:
        piece = img.convert("RGB")

        # Scale piece
        scale = base_scale + rng.uniform(-scale_variance, scale_variance) * base_scale
        scale = max(0.1, scale)
        new_w = max(1, int(piece.width * scale))
        new_h = max(1, int(piece.height * scale))
        piece = piece.resize((new_w, new_h), Image.LANCZOS)

        # Rotate with expand so corners aren't clipped
        if rotation > 0:
            angle = rng.uniform(-rotation, rotation)
            piece = piece.rotate(angle, expand=True, resample=Image.BICUBIC)

        # Random position — allow partial overlap/bleed
        max_x = cw - 1
        max_y = ch - 1
        x = rng.randint(-piece.width // 4, max_x)
        y = rng.randint(-piece.height // 4, max_y)

        canvas.paste(piece, (x, y))


def _layout_strips(
    canvas: Image.Image,
    images: list[Image.Image],
    rng: random.Random,
) -> None:
    """Divide canvas into N vertical strips, each from a different source image.

    Args:
        canvas: Destination RGB canvas (modified in-place).
        images: Source images.
        rng: Seeded random generator for strip ordering.
    """
    n = len(images)
    cw, ch = canvas.size

    order = list(range(n))
    rng.shuffle(order)

    strip_w = cw / n
    for i, src_idx in enumerate(order):
        x_start = int(round(i * strip_w))
        x_end = int(round((i + 1) * strip_w))
        strip_canvas_w = x_end - x_start
        if strip_canvas_w <= 0:
            continue

        src = images[src_idx].convert("RGB")
        # Scale source to fill the strip at canvas height
        scale = ch / src.height
        scaled_w = max(1, int(src.width * scale))
        src_scaled = src.resize((scaled_w, ch), Image.LANCZOS)

        # Crop or pad to the strip width
        if src_scaled.width >= strip_canvas_w:
            # Centre-crop
            crop_x = (src_scaled.width - strip_canvas_w) // 2
            strip = src_scaled.crop((crop_x, 0, crop_x + strip_canvas_w, ch))
        else:
            # Tile horizontally if source is too narrow
            strip = Image.new("RGB", (strip_canvas_w, ch))
            for tx in range(0, strip_canvas_w, src_scaled.width):
                strip.paste(src_scaled, (tx, 0))
            strip = strip.crop((0, 0, strip_canvas_w, ch))

        canvas.paste(strip, (x_start, 0))


def _layout_mosaic(
    canvas: Image.Image,
    images: list[Image.Image],
    rng: random.Random,
) -> None:
    """Fill canvas with many random rectangles sampled from source images.

    Generates at least ``max(n*4, 12)`` rectangles.

    Args:
        canvas: Destination RGB canvas (modified in-place).
        images: Source images.
        rng: Seeded random generator.
    """
    n = len(images)
    cw, ch = canvas.size
    num_rects = max(n * 4, 12)

    for _ in range(num_rects):
        src = images[rng.randrange(n)].convert("RGB")
        sw, sh = src.size

        # Random destination rectangle on canvas
        rx1 = rng.randint(0, cw - 1)
        ry1 = rng.randint(0, ch - 1)
        rect_w = rng.randint(max(1, cw // (n * 2)), max(2, cw // 2))
        rect_h = rng.randint(max(1, ch // (n * 2)), max(2, ch // 2))
        rx2 = min(cw, rx1 + rect_w)
        ry2 = min(ch, ry1 + rect_h)
        dst_w = rx2 - rx1
        dst_h = ry2 - ry1
        if dst_w <= 0 or dst_h <= 0:
            continue

        # Random source region
        sx1 = rng.randint(0, max(0, sw - dst_w))
        sy1 = rng.randint(0, max(0, sh - dst_h))
        sx2 = min(sw, sx1 + dst_w)
        sy2 = min(sh, sy1 + dst_h)
        region = src.crop((sx1, sy1, sx2, sy2))

        # Resize region to exactly fit dst rectangle
        if region.size != (dst_w, dst_h):
            region = region.resize((dst_w, dst_h), Image.LANCZOS)

        canvas.paste(region, (rx1, ry1))


class CollageEffect(ComposeEffect):
    """Arrange multiple images spatially on a shared canvas.

    Supports four layout modes: grid, scatter, strips, and mosaic.
    All randomness is seeded from ``context.seed`` for determinism.

    Examples:
        >>> effect = CollageEffect()
        >>> result = effect.compose(images, {"layout": "grid", "overlap": 0.1}, ctx)
    """

    name = "collage"
    description = "Spatial arrangement of multiple images"
    requires: list[str] = []

    def compose(
        self, images: list[Image.Image], params: dict, context: EffectContext
    ) -> EffectResult:
        """Arrange images into a collage.

        Args:
            images: Source images. If only one is provided, it is returned as a copy.
            params: Effect parameters (layout, overlap, rotation, scale_variance, canvas_size).
            context: Shared pipeline context (seed used for all randomness).

        Returns:
            EffectResult with the composed collage image.
        """
        params = self.validate_params(params)
        layout: str = params["layout"]
        overlap: float = params["overlap"]
        rotation: int = params["rotation"]
        scale_variance: float = params["scale_variance"]
        canvas_size_mode: str = params["canvas_size"]

        rgb_images = [img.convert("RGB") for img in images]

        # Single-image passthrough
        if len(rgb_images) == 1:
            return EffectResult(image=rgb_images[0].copy(), metadata={"layout": layout})

        rng = random.Random(context.seed)
        cw, ch = _canvas_size(rgb_images, canvas_size_mode)
        canvas = Image.new("RGB", (cw, ch), color=(0, 0, 0))

        if layout == "grid":
            _layout_grid(canvas, rgb_images, overlap, rng)
        elif layout == "scatter":
            _layout_scatter(canvas, rgb_images, overlap, rotation, scale_variance, rng)
        elif layout == "strips":
            _layout_strips(canvas, rgb_images, rng)
        elif layout == "mosaic":
            _layout_mosaic(canvas, rgb_images, rng)

        return EffectResult(
            image=canvas,
            metadata={
                "layout": layout,
                "overlap": overlap,
                "rotation": rotation,
                "scale_variance": scale_variance,
                "canvas_size": canvas_size_mode,
                "num_images": len(rgb_images),
            },
        )

    def validate_params(self, params: dict) -> dict:
        """Validate and normalize collage parameters.

        Args:
            params: Raw parameters dict.

        Returns:
            Normalized parameters with defaults applied.

        Raises:
            ConfigError: If ``layout`` or ``canvas_size`` is not a recognized value.
        """
        layout = params.get("layout", "grid")
        if layout not in VALID_LAYOUTS:
            raise ConfigError(
                f"Unknown layout: {layout!r}. Valid layouts: {sorted(VALID_LAYOUTS)}",
                effect_name="collage",
                param_name="layout",
            )

        canvas_size = params.get("canvas_size", "largest")
        if canvas_size not in VALID_CANVAS_SIZES:
            raise ConfigError(
                f"Unknown canvas_size: {canvas_size!r}. Valid values: {sorted(VALID_CANVAS_SIZES)}",
                effect_name="collage",
                param_name="canvas_size",
            )

        overlap = float(params.get("overlap", 0.0))
        overlap = max(0.0, min(0.5, overlap))

        rotation = int(params.get("rotation", 0))
        rotation = max(0, min(360, rotation))

        scale_variance = float(params.get("scale_variance", 0.0))
        scale_variance = max(0.0, min(1.0, scale_variance))

        return {
            "layout": layout,
            "overlap": overlap,
            "rotation": rotation,
            "scale_variance": scale_variance,
            "canvas_size": canvas_size,
        }


register_effect(CollageEffect())
