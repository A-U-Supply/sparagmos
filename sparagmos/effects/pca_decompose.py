"""PCA/SVD decomposition effect — reconstruct image channels from top/bottom singular values."""

from __future__ import annotations

import numpy as np
from PIL import Image

from sparagmos.effects import ConfigError, Effect, EffectContext, EffectResult, register_effect

_VALID_MODES = ("top", "bottom")


def _svd_reconstruct(channel: np.ndarray, n: int, mode: str) -> np.ndarray:
    """Reconstruct a 2D channel array using n singular values.

    Args:
        channel: 2D float array (height x width).
        n: Number of singular components to keep.
        mode: "top" keeps largest n; "bottom" keeps smallest n.

    Returns:
        Reconstructed 2D float array.
    """
    U, s, Vt = np.linalg.svd(channel, full_matrices=False)
    k = len(s)
    n = min(n, k)

    if mode == "top":
        mask = np.zeros(k)
        mask[:n] = 1.0
    else:
        # "bottom": keep the n smallest singular values
        mask = np.zeros(k)
        if n > 0:
            mask[k - n:] = 1.0

    s_masked = s * mask
    return (U * s_masked) @ Vt


class PcaDecomposeEffect(Effect):
    """Reconstruct image channels using SVD with top or bottom singular values."""

    name = "pca_decompose"
    description = "PCA/SVD reconstruction of image channels (ghostly or noisy)"
    requires: list[str] = []

    def apply(self, image: Image.Image, params: dict, context: EffectContext) -> EffectResult:
        params = self.validate_params(params)
        n_components = params["n_components"]
        mode = params["mode"]

        arr = np.array(image.convert("RGB"), dtype=np.float64)
        result = np.zeros_like(arr)

        for c in range(3):
            result[:, :, c] = _svd_reconstruct(arr[:, :, c], n_components, mode)

        result = np.clip(result, 0, 255).astype(np.uint8)

        return EffectResult(
            image=Image.fromarray(result, mode="RGB"),
            metadata={"n_components": n_components, "mode": mode},
        )

    def validate_params(self, params: dict) -> dict:
        mode = params.get("mode", "top")
        if mode not in _VALID_MODES:
            raise ConfigError(
                f"mode must be one of {_VALID_MODES}, got {mode!r}",
                effect_name=self.name,
                param_name="mode",
            )

        n_components = int(params.get("n_components", 5))
        n_components = max(1, min(100, n_components))

        return {"n_components": n_components, "mode": mode}


register_effect(PcaDecomposeEffect())
