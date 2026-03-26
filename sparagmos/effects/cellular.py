"""Cellular automata effect — run Game of Life or Rule 110 on pixel brightness."""

from __future__ import annotations

import numpy as np
from PIL import Image

from sparagmos.effects import ConfigError, Effect, EffectContext, EffectResult, register_effect

_VALID_RULES = ("game_of_life", "rule_110")


def _threshold_to_grid(image: Image.Image, threshold: int) -> np.ndarray:
    """Convert image to binary grid via grayscale threshold."""
    gray = np.array(image.convert("L"))
    return (gray >= threshold).astype(np.uint8)


def _step_game_of_life(grid: np.ndarray) -> np.ndarray:
    """Apply one generation of Conway's Game of Life (B3/S23) using convolution."""
    # Count live neighbours with wrap-around padding
    padded = np.pad(grid, 1, mode="wrap")
    neighbours = (
        padded[:-2, :-2] + padded[:-2, 1:-1] + padded[:-2, 2:]
        + padded[1:-1, :-2]                   + padded[1:-1, 2:]
        + padded[2:, :-2] + padded[2:, 1:-1] + padded[2:, 2:]
    )
    birth = (grid == 0) & (neighbours == 3)
    survive = (grid == 1) & ((neighbours == 2) | (neighbours == 3))
    return (birth | survive).astype(np.uint8)


def _step_rule_110_row(row: np.ndarray) -> np.ndarray:
    """Apply Rule 110 to a single 1D row (wrap-around)."""
    left = np.roll(row, 1)
    right = np.roll(row, -1)
    # Rule 110 truth table encoded as integer lookup
    # pattern (left, center, right) as 3-bit int → new value
    # 111→0, 110→1, 101→1, 100→0, 011→1, 010→1, 001→1, 000→0
    rule110 = np.array([0, 1, 1, 1, 0, 1, 1, 0], dtype=np.uint8)
    idx = (left * 4 + row * 2 + right).astype(np.int32)
    return rule110[idx]


def _apply_rule_110(grid: np.ndarray, generations: int) -> np.ndarray:
    """Apply Rule 110 row-by-row: each row becomes the next generation of the previous."""
    result = grid.copy()
    for r in range(1, grid.shape[0]):
        result[r] = _step_rule_110_row(result[r - 1])
        # Track generation count for colorize (reuse array by computing in-place)
    return result


def _run_game_of_life(
    grid: np.ndarray,
    generations: int,
    colorize: bool,
) -> np.ndarray:
    """Run Game of Life for N generations; optionally track first-death/birth generation."""
    if colorize:
        # gen_map[y, x] = generation at which cell last changed state (0-based)
        gen_map = np.zeros(grid.shape, dtype=np.float32)
        current = grid.copy()
        for g in range(1, generations + 1):
            nxt = _step_game_of_life(current)
            changed = nxt != current
            gen_map[changed] = g
            current = nxt
        # Normalise to 0-255 float
        if gen_map.max() > 0:
            gen_map = gen_map / gen_map.max()
        return gen_map
    else:
        current = grid.copy()
        for _ in range(generations):
            current = _step_game_of_life(current)
        return current.astype(np.float32)


def _run_rule_110(
    grid: np.ndarray,
    generations: int,
    colorize: bool,
) -> np.ndarray:
    """Apply Rule 110 for N passes through the rows."""
    if colorize:
        # Run multiple passes and accumulate change counts
        gen_map = np.zeros(grid.shape, dtype=np.float32)
        current = grid.copy()
        for g in range(1, generations + 1):
            nxt = current.copy()
            for r in range(1, current.shape[0]):
                nxt[r] = _step_rule_110_row(current[r - 1])
            changed = nxt != current
            gen_map[changed] = g
            current = nxt
        if gen_map.max() > 0:
            gen_map = gen_map / gen_map.max()
        return gen_map
    else:
        current = grid.copy()
        for _ in range(generations):
            nxt = current.copy()
            for r in range(1, current.shape[0]):
                nxt[r] = _step_rule_110_row(current[r - 1])
            current = nxt
        return current.astype(np.float32)


def _apply_hot_colormap(data: np.ndarray) -> np.ndarray:
    """Map 0-1 float array to RGB via a 'hot' colormap (black→red→yellow→white)."""
    r = np.clip(data * 3.0, 0, 1)
    g = np.clip(data * 3.0 - 1.0, 0, 1)
    b = np.clip(data * 3.0 - 2.0, 0, 1)
    return np.stack([r, g, b], axis=-1)


class CellularEffect(Effect):
    """Run cellular automata (Game of Life or Rule 110) on pixel brightness."""

    name = "cellular"
    description = "Run cellular automata on pixel brightness data"
    requires: list[str] = []

    def apply(self, image: Image.Image, params: dict, context: EffectContext) -> EffectResult:
        params = self.validate_params(params)
        rule = params["rule"]
        generations = params["generations"]
        threshold = params["threshold"]
        colorize = params["colorize"]

        grid = _threshold_to_grid(image, threshold)

        if rule == "game_of_life":
            result_data = _run_game_of_life(grid, generations, colorize)
        else:
            result_data = _run_rule_110(grid, generations, colorize)

        if colorize:
            # result_data is float 0-1; apply hot colormap → RGB
            rgb = (_apply_hot_colormap(result_data) * 255).astype(np.uint8)
            out_image = Image.fromarray(rgb, mode="RGB")
        else:
            # Binary result: 0 or 1 → 0 or 255 grayscale, then convert to RGB
            gray = (result_data * 255).astype(np.uint8)
            out_image = Image.fromarray(gray, mode="L").convert("RGB")

        return EffectResult(
            image=out_image,
            metadata={
                "rule": rule,
                "generations": generations,
                "threshold": threshold,
                "colorize": colorize,
            },
        )

    def validate_params(self, params: dict) -> dict:
        rule = params.get("rule", "game_of_life")
        if rule not in _VALID_RULES:
            raise ConfigError(
                f"rule must be one of {_VALID_RULES}, got {rule!r}",
                effect_name=self.name,
                param_name="rule",
            )

        generations = int(params.get("generations", 10))
        generations = max(1, min(200, generations))

        threshold = int(params.get("threshold", 128))
        threshold = max(0, min(255, threshold))

        colorize = bool(params.get("colorize", False))

        return {
            "rule": rule,
            "generations": generations,
            "threshold": threshold,
            "colorize": colorize,
        }


register_effect(CellularEffect())
