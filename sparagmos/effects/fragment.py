"""Fragment compositing effect — slice images into pieces and rebuild from mixed sources."""

from __future__ import annotations

import math
import random

import numpy as np
from PIL import Image, ImageDraw
from scipy.spatial import Delaunay, Voronoi

from sparagmos.effects import (
    ComposeEffect,
    ConfigError,
    EffectContext,
    EffectResult,
    register_effect,
)

VALID_CUT_MODES = {"grid", "voronoi", "strips", "shatter"}


def _pick_source(
    images: list[Image.Image],
    idx: int,
    mix_ratio: float,
    rng: random.Random,
) -> Image.Image:
    """Choose a source image for a given fragment index.

    Args:
        images: Available source images.
        idx: Fragment index (used for round-robin when mix_ratio is 0).
        mix_ratio: Probability of picking a random source instead of the index-based one.
            0.0 always returns the first image; 1.0 always picks at random.
        rng: Seeded random generator.

    Returns:
        The selected PIL Image (not yet converted or resized).
    """
    if mix_ratio <= 0.0:
        return images[0]
    if rng.random() < mix_ratio:
        return images[rng.randrange(len(images))]
    return images[idx % len(images)]


def _fragment_grid(
    canvas: np.ndarray,
    images: list[Image.Image],
    pieces: int,
    mix_ratio: float,
    gap: int,
    rng: random.Random,
) -> None:
    """Fill *canvas* by splitting it into a grid and copying cells from source images.

    Args:
        canvas: uint8 RGB array (H, W, 3) modified in-place.
        images: Resized source images (all same dimensions as canvas).
        pieces: Approximate number of cells (rows*cols ≈ pieces).
        mix_ratio: Source-selection randomness [0, 1].
        gap: Pixel gap (black) shrunk inward from each cell edge.
        rng: Seeded random generator.
    """
    h, w = canvas.shape[:2]
    cols = max(1, round(math.sqrt(pieces)))
    rows = max(1, math.ceil(pieces / cols))

    cell_w = w / cols
    cell_h = h / rows

    src_arrays = [np.array(img) for img in images]

    for row in range(rows):
        for col in range(cols):
            idx = row * cols + col
            x0 = int(round(col * cell_w))
            y0 = int(round(row * cell_h))
            x1 = int(round((col + 1) * cell_w))
            y1 = int(round((row + 1) * cell_h))

            # Apply gap by shrinking inward
            gx0 = min(x0 + gap, x1)
            gy0 = min(y0 + gap, y1)
            gx1 = max(x1 - gap, gx0)
            gy1 = max(y1 - gap, gy0)

            if gx1 <= gx0 or gy1 <= gy0:
                continue

            src = _pick_source(images, idx, mix_ratio, rng)
            src_arr = src_arrays[images.index(src)]
            canvas[gy0:gy1, gx0:gx1] = src_arr[gy0:gy1, gx0:gx1]


def _fragment_voronoi(
    canvas: np.ndarray,
    images: list[Image.Image],
    pieces: int,
    mix_ratio: float,
    gap: int,
    seed: int,
) -> None:
    """Fill *canvas* using a Voronoi diagram; each cell copies from a source image.

    Args:
        canvas: uint8 RGB array (H, W, 3) modified in-place.
        images: Resized source images.
        pieces: Number of Voronoi seed points.
        mix_ratio: Source-selection randomness [0, 1].
        gap: Gap width in pixels; detected by checking if a pixel is near a cell boundary.
        seed: NumPy RNG seed.
    """
    h, w = canvas.shape[:2]
    np_rng = np.random.RandomState(seed)
    py_rng = random.Random(seed)

    # Generate random seed points
    points = np_rng.rand(pieces, 2) * np.array([w, h])

    # Assign a source image to each Voronoi cell
    cell_sources: list[int] = []
    for i in range(pieces):
        src_img = _pick_source(images, i, mix_ratio, py_rng)
        cell_sources.append(images.index(src_img))

    src_arrays = [np.array(img) for img in images]

    # Build pixel coordinate arrays
    ys, xs = np.mgrid[0:h, 0:w]
    coords = np.stack([xs.ravel(), ys.ravel()], axis=1).astype(np.float32)

    # Find nearest seed point for every pixel
    diffs = coords[:, np.newaxis, :] - points[np.newaxis, :, :]  # (N_pix, pieces, 2)
    dists_sq = (diffs ** 2).sum(axis=2)                          # (N_pix, pieces)
    nearest = np.argmin(dists_sq, axis=1)                        # (N_pix,)

    if gap > 0:
        # Detect boundary pixels: compare nearest cell with neighbors
        nearest_2d = nearest.reshape(h, w)
        # Shift by 1 in x and y; boundary where neighbor has different cell
        shifted_x = np.roll(nearest_2d, 1, axis=1)
        shifted_y = np.roll(nearest_2d, 1, axis=0)
        is_boundary = (nearest_2d != shifted_x) | (nearest_2d != shifted_y)

        # Dilate the boundary mask to achieve gap width
        if gap > 1:
            from scipy.ndimage import binary_dilation
            struct = np.ones((gap * 2 - 1, gap * 2 - 1), dtype=bool)
            is_boundary = binary_dilation(is_boundary, structure=struct)

        boundary_flat = is_boundary.ravel()

    for cell_idx in range(pieces):
        mask = nearest == cell_idx
        if not mask.any():
            continue

        if gap > 0:
            mask = mask & ~boundary_flat

        ys_cell = (np.where(mask)[0] // w)
        xs_cell = (np.where(mask)[0] % w)

        if len(ys_cell) == 0:
            continue

        src_arr = src_arrays[cell_sources[cell_idx]]
        canvas[ys_cell, xs_cell] = src_arr[ys_cell, xs_cell]


def _fragment_strips(
    canvas: np.ndarray,
    images: list[Image.Image],
    pieces: int,
    mix_ratio: float,
    rng: random.Random,
) -> None:
    """Fill *canvas* with vertical strips of random widths, each from a source image.

    Args:
        canvas: uint8 RGB array (H, W, 3) modified in-place.
        images: Resized source images.
        pieces: Number of strips.
        mix_ratio: Source-selection randomness [0, 1].
        rng: Seeded random generator.
    """
    h, w = canvas.shape[:2]
    src_arrays = [np.array(img) for img in images]

    # Generate random widths that sum to w
    raw_widths = [rng.random() for _ in range(pieces)]
    total = sum(raw_widths)
    widths = [max(1, int(round(rw / total * w))) for rw in raw_widths]

    # Adjust for rounding errors
    diff = w - sum(widths)
    widths[-1] = max(1, widths[-1] + diff)

    x = 0
    for i, strip_w in enumerate(widths):
        if strip_w <= 0 or x >= w:
            continue
        x1 = min(x + strip_w, w)
        src = _pick_source(images, i, mix_ratio, rng)
        src_arr = src_arrays[images.index(src)]
        canvas[:, x:x1] = src_arr[:, x:x1]
        x = x1


def _fragment_shatter(
    canvas: np.ndarray,
    images: list[Image.Image],
    pieces: int,
    mix_ratio: float,
    gap: int,
    seed: int,
) -> None:
    """Fill *canvas* using Delaunay triangulation; each triangle from a source image.

    Args:
        canvas: uint8 RGB array (H, W, 3) modified in-place.
        images: Resized source images.
        pieces: Approximate number of triangles (actual count depends on triangulation).
        mix_ratio: Source-selection randomness [0, 1].
        gap: Pixels to shrink each triangle toward its centroid (black border).
        seed: NumPy RNG seed.
    """
    h, w = canvas.shape[:2]
    np_rng = np.random.RandomState(seed)
    py_rng = random.Random(seed)

    src_arrays = [np.array(img) for img in images]

    # Random interior points + corners to cover the whole image
    n_interior = max(0, pieces - 4)
    interior = np_rng.rand(n_interior, 2) * np.array([w, h])
    corners = np.array([[0, 0], [w - 1, 0], [w - 1, h - 1], [0, h - 1]], dtype=float)
    points = np.vstack([corners, interior])

    tri = Delaunay(points)

    canvas_pil = Image.fromarray(canvas)
    draw = ImageDraw.Draw(canvas_pil)

    for tri_idx, simplex in enumerate(tri.simplices):
        verts = points[simplex]  # shape (3, 2): [[x,y], ...]

        src = _pick_source(images, tri_idx, mix_ratio, py_rng)
        src_arr = src_arrays[images.index(src)]

        if gap > 0:
            centroid = verts.mean(axis=0)
            shrink = gap / max(
                np.linalg.norm(verts - centroid, axis=1).max(), 1.0
            )
            shrink = min(shrink, 0.9)
            verts = centroid + (1.0 - shrink) * (verts - centroid)

        poly = [(float(x), float(y)) for x, y in verts]

        # Find bounding box to sample from source
        xs = [p[0] for p in poly]
        ys = [p[1] for p in poly]
        bx0, by0 = int(max(0, min(xs))), int(max(0, min(ys)))
        bx1, by1 = int(min(w - 1, max(xs))) + 1, int(min(h - 1, max(ys))) + 1

        if bx1 <= bx0 or by1 <= by0:
            continue

        # Create a mask for this triangle, then blit the source pixels
        mask = Image.new("L", (w, h), 0)
        mask_draw = ImageDraw.Draw(mask)
        mask_draw.polygon(poly, fill=255)
        mask_arr = np.array(mask)

        ys_px, xs_px = np.where(mask_arr > 0)
        if len(ys_px) == 0:
            continue
        canvas[ys_px, xs_px] = src_arr[ys_px, xs_px]

    # Copy back any draw operations (gap only affects centroid-shrunken polys)
    # canvas is already updated by direct numpy assignment above


class FragmentEffect(ComposeEffect):
    """Cut images into pieces and reassemble from mixed image sources.

    Supports four cut modes: grid, voronoi, strips, and shatter.
    All randomness is seeded from ``context.seed`` for determinism.

    Examples:
        >>> effect = FragmentEffect()
        >>> result = effect.compose(images, {"cut_mode": "grid", "pieces": 16}, ctx)
    """

    name = "fragment"
    description = "Cut and reassemble from mixed image sources"
    requires: list[str] = []

    def compose(
        self, images: list[Image.Image], params: dict, context: EffectContext
    ) -> EffectResult:
        """Fragment and reassemble images.

        Args:
            images: Source images. All are resized to match the first image's dimensions.
                If only one is provided, it is returned as a copy.
            params: Effect parameters (cut_mode, pieces, mix_ratio, gap).
            context: Shared pipeline context (seed used for all randomness).

        Returns:
            EffectResult with the fragmented composite image.
        """
        params = self.validate_params(params)
        cut_mode: str = params["cut_mode"]
        pieces: int = params["pieces"]
        mix_ratio: float = params["mix_ratio"]
        gap: int = params["gap"]

        # Normalize all images to first image's size and RGB mode
        base_img = images[0].convert("RGB")
        base_w, base_h = base_img.size
        rgb_images: list[Image.Image] = [base_img]
        for img in images[1:]:
            converted = img.convert("RGB")
            if converted.size != (base_w, base_h):
                converted = converted.resize((base_w, base_h), Image.LANCZOS)
            rgb_images.append(converted)

        # Single-image passthrough
        if len(rgb_images) == 1:
            return EffectResult(image=base_img.copy(), metadata={"cut_mode": cut_mode})

        # Black canvas to start (gaps remain black)
        canvas = np.zeros((base_h, base_w, 3), dtype=np.uint8)

        rng = random.Random(context.seed)

        if cut_mode == "grid":
            _fragment_grid(canvas, rgb_images, pieces, mix_ratio, gap, rng)
        elif cut_mode == "voronoi":
            _fragment_voronoi(canvas, rgb_images, pieces, mix_ratio, gap, context.seed)
        elif cut_mode == "strips":
            _fragment_strips(canvas, rgb_images, pieces, mix_ratio, rng)
        elif cut_mode == "shatter":
            _fragment_shatter(canvas, rgb_images, pieces, mix_ratio, gap, context.seed)

        return EffectResult(
            image=Image.fromarray(canvas),
            metadata={
                "cut_mode": cut_mode,
                "pieces": pieces,
                "mix_ratio": mix_ratio,
                "gap": gap,
                "num_images": len(rgb_images),
            },
        )

    def validate_params(self, params: dict) -> dict:
        """Validate and normalize fragment parameters.

        Args:
            params: Raw parameters dict.

        Returns:
            Normalized parameters with defaults applied.

        Raises:
            ConfigError: If ``cut_mode`` is not a recognized value.
        """
        cut_mode = params.get("cut_mode", "grid")
        if cut_mode not in VALID_CUT_MODES:
            raise ConfigError(
                f"Unknown cut_mode: {cut_mode!r}. Valid modes: {sorted(VALID_CUT_MODES)}",
                effect_name="fragment",
                param_name="cut_mode",
            )

        pieces = int(params.get("pieces", 16))
        pieces = max(4, min(64, pieces))

        mix_ratio = float(params.get("mix_ratio", 0.5))
        mix_ratio = max(0.0, min(1.0, mix_ratio))

        gap = int(params.get("gap", 0))
        gap = max(0, min(10, gap))

        return {
            "cut_mode": cut_mode,
            "pieces": pieces,
            "mix_ratio": mix_ratio,
            "gap": gap,
        }


register_effect(FragmentEffect())
