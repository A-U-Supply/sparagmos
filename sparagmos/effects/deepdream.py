"""DeepDream effect — amplify neural network activations via gradient ascent."""

from __future__ import annotations

import numpy as np
from PIL import Image

from sparagmos.effects import ConfigError, Effect, EffectContext, EffectResult, register_effect


class DeepDreamEffect(Effect):
    """DeepDream using InceptionV3 gradient ascent, multi-octave."""

    name = "deepdream"
    description = "Amplify neural network feature activations via gradient ascent (DeepDream)"
    requires: list[str] = []

    def apply(self, image: Image.Image, params: dict, context: EffectContext) -> EffectResult:
        params = self.validate_params(params)

        try:
            import torch
            import torchvision.models as models
            import torchvision.transforms.functional as TF
        except ImportError as e:
            raise ImportError(
                "DeepDream requires PyTorch and torchvision. "
                "Install with: pip install torch torchvision"
            ) from e

        device = torch.device("cpu")
        img = image.convert("RGB")

        # Load InceptionV3 up to a mid-level layer
        model = models.inception_v3(weights=models.Inception_V3_Weights.DEFAULT)
        model.eval()
        model.to(device)

        # Use a hook to capture activations from Mixed_5d (a good dream layer)
        activation: dict[str, torch.Tensor] = {}

        def hook_fn(module: torch.nn.Module, _input: tuple, output: torch.Tensor) -> None:
            activation["value"] = output

        # Mixed_5d is an interesting mid-level feature layer in InceptionV3
        hook = model.Mixed_5d.register_forward_hook(hook_fn)

        def dream_step(
            img_tensor: torch.Tensor, lr: float, jitter: int
        ) -> torch.Tensor:
            """One gradient ascent step with jitter."""
            # Apply random jitter to reduce grid artifacts
            shift_x = int(np.random.randint(-jitter, jitter + 1))
            shift_y = int(np.random.randint(-jitter, jitter + 1))
            img_shifted = torch.roll(torch.roll(img_tensor, shift_x, dims=-1), shift_y, dims=-2)

            img_shifted = img_shifted.detach().requires_grad_(True)
            # Forward pass
            _ = model(img_shifted)
            loss = activation["value"].norm()
            loss.backward()

            grad = img_shifted.grad
            if grad is not None:
                # Normalize gradient
                grad = grad / (grad.abs().mean() + 1e-8)
                # Un-jitter and add gradient
                grad = torch.roll(torch.roll(grad, -shift_x, dims=-1), -shift_y, dims=-2)
                with torch.no_grad():
                    img_tensor = img_tensor + lr * grad

            return img_tensor.detach()

        def tensor_from_pil(pil_img: Image.Image) -> torch.Tensor:
            arr = np.array(pil_img).astype(np.float32) / 255.0
            t = torch.from_numpy(arr).permute(2, 0, 1).unsqueeze(0)
            # Normalize to InceptionV3 expected range
            mean = torch.tensor([0.485, 0.456, 0.406]).view(1, 3, 1, 1)
            std = torch.tensor([0.229, 0.224, 0.225]).view(1, 3, 1, 1)
            return (t - mean) / std

        def pil_from_tensor(t: torch.Tensor) -> Image.Image:
            mean = torch.tensor([0.485, 0.456, 0.406]).view(1, 3, 1, 1)
            std = torch.tensor([0.229, 0.224, 0.225]).view(1, 3, 1, 1)
            arr = (t * std + mean).squeeze(0).permute(1, 2, 0).detach().numpy()
            arr = np.clip(arr, 0.0, 1.0)
            return Image.fromarray((arr * 255).astype(np.uint8))

        iterations = params["iterations"]
        octave_scale = params["octave_scale"]
        jitter = params["jitter"]
        lr = params["learning_rate"]
        num_octaves = 3

        # InceptionV3 requires input >= 75x75; upscale if needed (scale back at end)
        MIN_DIM = 75
        proc_img = img
        if img.width < MIN_DIM or img.height < MIN_DIM:
            scale = max(MIN_DIM / img.width, MIN_DIM / img.height)
            new_w = max(MIN_DIM, int(img.width * scale))
            new_h = max(MIN_DIM, int(img.height * scale))
            proc_img = img.resize((new_w, new_h), Image.LANCZOS)

        # Build octave pyramid (smallest to largest)
        octave_imgs: list[Image.Image] = []
        cur = proc_img
        for _ in range(num_octaves - 1):
            w, h = cur.size
            small_w = max(MIN_DIM, int(w / octave_scale))
            small_h = max(MIN_DIM, int(h / octave_scale))
            octave_imgs.append(cur)
            cur = cur.resize((small_w, small_h), Image.LANCZOS)
        octave_imgs.append(cur)
        # Reverse: process smallest first
        octave_imgs = list(reversed(octave_imgs))

        dream_img = octave_imgs[0]
        for octave_idx, orig_at_scale in enumerate(octave_imgs):
            if octave_idx > 0:
                # Upscale dream result and add detail from original
                w, h = orig_at_scale.size
                dream_img = dream_img.resize((w, h), Image.LANCZOS)
                detail = np.array(orig_at_scale).astype(np.float32) - np.array(
                    dream_img.resize((w, h), Image.LANCZOS)
                ).astype(np.float32)
                dream_arr = np.clip(
                    np.array(dream_img).astype(np.float32) + detail, 0, 255
                ).astype(np.uint8)
                dream_img = Image.fromarray(dream_arr)

            t = tensor_from_pil(dream_img).to(device)
            for _ in range(iterations):
                t = dream_step(t, lr, jitter)
            dream_img = pil_from_tensor(t.cpu())

        hook.remove()

        return EffectResult(
            image=dream_img.resize(image.size, Image.LANCZOS),
            metadata={
                "iterations": iterations,
                "octave_scale": octave_scale,
                "jitter": jitter,
                "learning_rate": lr,
                "num_octaves": num_octaves,
            },
        )

    def validate_params(self, params: dict) -> dict:
        validated = {
            "iterations": int(params.get("iterations", 10)),
            "octave_scale": float(params.get("octave_scale", 1.4)),
            "jitter": int(params.get("jitter", 32)),
            "learning_rate": float(params.get("learning_rate", 0.01)),
        }
        if not (1 <= validated["iterations"] <= 50):
            raise ConfigError(
                f"iterations must be between 1 and 50, got {validated['iterations']}",
                effect_name=self.name,
                param_name="iterations",
            )
        if validated["octave_scale"] <= 1.0:
            raise ConfigError(
                f"octave_scale must be > 1.0, got {validated['octave_scale']}",
                effect_name=self.name,
                param_name="octave_scale",
            )
        if validated["jitter"] < 0:
            validated["jitter"] = 0
        if validated["learning_rate"] <= 0:
            raise ConfigError(
                f"learning_rate must be > 0, got {validated['learning_rate']}",
                effect_name=self.name,
                param_name="learning_rate",
            )
        return validated


register_effect(DeepDreamEffect())
