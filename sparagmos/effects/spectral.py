"""Spectral effect — FFT-based frequency domain manipulation."""

from __future__ import annotations

import numpy as np
from PIL import Image

from sparagmos.effects import ConfigError, Effect, EffectContext, EffectResult, register_effect

_VALID_OPERATIONS = ("shift", "bandpass", "blur")


class SpectralEffect(Effect):
    """Apply 2D FFT operations to each image channel independently."""

    name = "spectral"
    description = "FFT-based frequency domain manipulation: shift, bandpass, blur"
    requires: list[str] = []

    def apply(self, image: Image.Image, params: dict, context: EffectContext) -> EffectResult:
        params = self.validate_params(params)
        operation = params["operation"]
        amount = params["amount"]

        arr = np.array(image.convert("RGB"), dtype=np.float64)
        result = np.zeros_like(arr)

        for ch in range(3):
            channel = arr[:, :, ch]
            spectrum = np.fft.fft2(channel)
            spectrum = self._apply_operation(spectrum, operation, amount, channel.shape)
            spatial = np.fft.ifft2(spectrum).real
            result[:, :, ch] = spatial

        result = np.clip(result, 0, 255).astype(np.uint8)
        return EffectResult(
            image=Image.fromarray(result, mode="RGB"),
            metadata={"operation": operation, "amount": amount},
        )

    def _apply_operation(
        self,
        spectrum: np.ndarray,
        operation: str,
        amount: float,
        shape: tuple[int, int],
    ) -> np.ndarray:
        h, w = shape

        if operation == "shift":
            shift_y = int(h * amount * 0.5)
            shift_x = int(w * amount * 0.5)
            return np.roll(np.roll(spectrum, shift_y, axis=0), shift_x, axis=1)

        if operation == "bandpass":
            # Keep only a band of mid frequencies; zero out low and high
            shifted = np.fft.fftshift(spectrum)
            cy, cx = h // 2, w // 2
            # Band: inner radius to outer radius
            inner = min(cy, cx) * (1.0 - amount) * 0.5
            outer = min(cy, cx) * (0.5 + amount * 0.5)
            y_idx, x_idx = np.ogrid[:h, :w]
            dist = np.sqrt((y_idx - cy) ** 2 + (x_idx - cx) ** 2)
            mask = (dist >= inner) & (dist <= outer)
            shifted *= mask
            return np.fft.ifftshift(shifted)

        if operation == "blur":
            # Multiply by Gaussian low-pass envelope
            shifted = np.fft.fftshift(spectrum)
            cy, cx = h // 2, w // 2
            sigma_y = h * (1.0 - amount) * 0.5
            sigma_x = w * (1.0 - amount) * 0.5
            sigma_y = max(1.0, sigma_y)
            sigma_x = max(1.0, sigma_x)
            y_idx, x_idx = np.ogrid[:h, :w]
            gauss = np.exp(
                -0.5 * ((y_idx - cy) ** 2 / sigma_y**2 + (x_idx - cx) ** 2 / sigma_x**2)
            )
            shifted *= gauss
            return np.fft.ifftshift(shifted)

        return spectrum

    def validate_params(self, params: dict) -> dict:
        operation = params.get("operation", "shift")
        if operation not in _VALID_OPERATIONS:
            raise ConfigError(
                f"operation must be one of {_VALID_OPERATIONS}, got {operation!r}",
                effect_name=self.name,
                param_name="operation",
            )
        amount = float(params.get("amount", 0.3))
        amount = max(0.0, min(1.0, amount))
        return {"operation": operation, "amount": amount}


register_effect(SpectralEffect())
