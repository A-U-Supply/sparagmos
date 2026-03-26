"""Sonify effect — interpret image data as audio, apply DSP, convert back."""

from __future__ import annotations

import numpy as np
from PIL import Image
from scipy import signal

from sparagmos.effects import ConfigError, Effect, EffectContext, EffectResult, register_effect

_VALID_EFFECTS = ("reverb", "echo", "distortion", "phaser")


class SonifyEffect(Effect):
    """Interpret image bytes as 16-bit PCM audio, apply DSP, convert back."""

    name = "sonify"
    description = "Treat image data as audio samples and apply DSP effects"
    requires: list[str] = []

    def apply(self, image: Image.Image, params: dict, context: EffectContext) -> EffectResult:
        params = self.validate_params(params)
        dsp_effect = params["effect"]
        intensity = params["intensity"]

        arr = np.array(image.convert("RGB"), dtype=np.uint8)
        original_shape = arr.shape
        flat = arr.flatten().astype(np.uint8)

        # Pad to even length so we can view as int16
        if len(flat) % 2 != 0:
            flat = np.append(flat, np.uint8(0))
            padded = True
        else:
            padded = False

        # Interpret raw bytes as 16-bit signed PCM
        samples = flat.view(np.int16).astype(np.float64)

        samples = self._apply_dsp(samples, dsp_effect, intensity, context.seed)

        # Clip to int16 range and convert back
        samples = np.clip(samples, -32768, 32767).astype(np.int16)
        result_bytes = samples.view(np.uint8)

        if padded:
            result_bytes = result_bytes[: len(flat) - 1]

        # Reshape back — may be shorter/longer due to convolution; trim or wrap
        needed = int(np.prod(original_shape))
        if len(result_bytes) >= needed:
            result_bytes = result_bytes[:needed]
        else:
            # Tile to fill
            repeats = (needed // len(result_bytes)) + 1
            result_bytes = np.tile(result_bytes, repeats)[:needed]

        result_arr = result_bytes.reshape(original_shape)
        return EffectResult(
            image=Image.fromarray(result_arr, mode="RGB"),
            metadata={"effect": dsp_effect, "intensity": intensity},
        )

    def _apply_dsp(
        self,
        samples: np.ndarray,
        dsp_effect: str,
        intensity: float,
        seed: int,
    ) -> np.ndarray:
        n = len(samples)

        if dsp_effect == "reverb":
            # Exponentially decaying impulse response
            decay_len = max(1, int(n * 0.05 * intensity))
            t = np.arange(decay_len, dtype=np.float64)
            ir = np.exp(-t / max(1.0, decay_len * 0.3)) * intensity
            ir[0] = 1.0
            # Use fftconvolve for speed; truncate to original length
            reverbed = signal.fftconvolve(samples, ir)[:n]
            return samples * (1.0 - intensity * 0.5) + reverbed * intensity * 0.5

        if dsp_effect == "echo":
            delay_samples = max(1, int(n * 0.1 * intensity))
            echo_amp = 0.5 * intensity
            echoed = np.zeros_like(samples)
            echoed[delay_samples:] = samples[: n - delay_samples] * echo_amp
            return samples + echoed

        if dsp_effect == "distortion":
            threshold = 32767.0 * (1.0 - intensity * 0.9)
            threshold = max(100.0, threshold)
            clipped = np.clip(samples, -threshold, threshold)
            # Amplify back towards full range
            gain = 32767.0 / threshold
            return clipped * gain

        if dsp_effect == "phaser":
            rng = np.random.default_rng(seed)
            lfo_freq = rng.uniform(0.5, 4.0)
            t = np.linspace(0, 1.0, n)
            lfo = np.sin(2.0 * np.pi * lfo_freq * t)
            # Phase shift by rolling, modulated by LFO
            shift = int(n * 0.01 * intensity)
            shifted = np.roll(samples, shift)
            return samples + shifted * lfo * intensity * 0.5

        return samples

    def validate_params(self, params: dict) -> dict:
        effect = params.get("effect", "reverb")
        if effect not in _VALID_EFFECTS:
            raise ConfigError(
                f"effect must be one of {_VALID_EFFECTS}, got {effect!r}",
                effect_name=self.name,
                param_name="effect",
            )
        intensity = float(params.get("intensity", 0.5))
        intensity = max(0.0, min(1.0, intensity))
        return {"effect": effect, "intensity": intensity}


register_effect(SonifyEffect())
