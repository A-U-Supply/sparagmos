"""Neural style transfer effect — Gatys algorithm, self-styled for weird recursion."""

from __future__ import annotations

import numpy as np
from PIL import Image

from sparagmos.effects import ConfigError, Effect, EffectContext, EffectResult, register_effect

# VGG19 layer names used for style and content
_STYLE_LAYERS = ["relu1_1", "relu2_1", "relu3_1", "relu4_1", "relu5_1"]
_CONTENT_LAYER = "relu4_2"


class StyleTransferEffect(Effect):
    """Gatys-style neural style transfer.

    Uses the input image as BOTH content and style source — a self-referential
    hallucination that recursively enhances its own features.
    """

    name = "style_transfer"
    description = "Gatys neural style transfer; self-styled for recursive destruction"
    requires: list[str] = []

    def apply(self, image: Image.Image, params: dict, context: EffectContext) -> EffectResult:
        params = self.validate_params(params)

        try:
            import torch
            import torch.nn as nn
            import torchvision.models as models
        except ImportError as e:
            raise ImportError(
                "style_transfer requires PyTorch and torchvision. "
                "Install with: pip install torch torchvision"
            ) from e

        device = torch.device("cpu")
        img = image.convert("RGB")

        def img_to_tensor(pil_img: Image.Image) -> torch.Tensor:
            arr = np.array(pil_img).astype(np.float32) / 255.0
            t = torch.from_numpy(arr).permute(2, 0, 1).unsqueeze(0)
            mean = torch.tensor([0.485, 0.456, 0.406]).view(1, 3, 1, 1)
            std = torch.tensor([0.229, 0.224, 0.225]).view(1, 3, 1, 1)
            return (t - mean) / std

        def tensor_to_img(t: torch.Tensor) -> Image.Image:
            mean = torch.tensor([0.485, 0.456, 0.406]).view(1, 3, 1, 1)
            std = torch.tensor([0.229, 0.224, 0.225]).view(1, 3, 1, 1)
            arr = (t.cpu() * std + mean).squeeze(0).permute(1, 2, 0).detach().numpy()
            arr = np.clip(arr, 0.0, 1.0)
            return Image.fromarray((arr * 255).astype(np.uint8))

        def gram_matrix(feat: torch.Tensor) -> torch.Tensor:
            b, c, h, w = feat.shape
            f = feat.view(b * c, h * w)
            return torch.mm(f, f.t()) / (b * c * h * w)

        # Build a feature extractor from VGG19 that captures our target layers
        vgg = models.vgg19(weights=models.VGG19_Weights.DEFAULT).features.to(device).eval()

        # Map readable layer names to VGG19 sequential indices
        # VGG19 features: conv-relu pairs, maxpool between blocks
        # relu1_1=1, relu1_2=3, pool1=4
        # relu2_1=6, relu2_2=8, pool2=9
        # relu3_1=11, relu3_2=13, relu3_3=15, relu3_4=17, pool3=18
        # relu4_1=20, relu4_2=22, relu4_3=24, relu4_4=26, pool4=27
        # relu5_1=29, ...
        layer_map = {
            "relu1_1": "1",
            "relu2_1": "6",
            "relu3_1": "11",
            "relu4_1": "20",
            "relu4_2": "22",
            "relu5_1": "29",
        }

        wanted_layers = set(_STYLE_LAYERS + [_CONTENT_LAYER])
        wanted_indices = {layer_map[l] for l in wanted_layers}

        features_cache: dict[str, torch.Tensor] = {}
        hooks = []

        for idx_str in wanted_indices:
            idx = int(idx_str)

            def make_hook(name: str):
                def hook(_mod: nn.Module, _inp: tuple, out: torch.Tensor) -> None:
                    features_cache[name] = out

                return hook

            hooks.append(vgg[idx].register_forward_hook(make_hook(idx_str)))

        def get_features(t: torch.Tensor) -> dict[str, torch.Tensor]:
            features_cache.clear()
            with torch.no_grad():
                vgg(t)
            return {
                readable: features_cache[idx_str]
                for readable, idx_str in layer_map.items()
                if readable in wanted_layers
            }

        # For a live input tensor (requires grad), we need a version that tracks grad
        def get_features_grad(t: torch.Tensor) -> dict[str, torch.Tensor]:
            features_cache.clear()
            vgg(t)
            return {
                readable: features_cache[idx_str]
                for readable, idx_str in layer_map.items()
                if readable in wanted_layers
            }

        # Source image is both content and style
        src_t = img_to_tensor(img).to(device)
        src_features = get_features(src_t)

        # Target gram matrices for style layers
        style_grams = {l: gram_matrix(src_features[l]) for l in _STYLE_LAYERS}
        content_feat = src_features[_CONTENT_LAYER].detach()

        # Optimise a copy of the source image
        opt_t = src_t.clone().requires_grad_(True)
        optimizer = torch.optim.Adam([opt_t], lr=0.05)

        style_weight = params["style_weight"]
        content_weight = params["content_weight"]
        iterations = params["iterations"]

        for _ in range(iterations):
            optimizer.zero_grad()
            feats = get_features_grad(opt_t)

            style_loss = sum(
                nn.functional.mse_loss(gram_matrix(feats[l]), style_grams[l])
                for l in _STYLE_LAYERS
            )
            content_loss = nn.functional.mse_loss(feats[_CONTENT_LAYER], content_feat)

            loss = style_weight * style_loss + content_weight * content_loss
            loss.backward()
            optimizer.step()

            # Clamp to reasonable range to avoid explosion
            with torch.no_grad():
                opt_t.clamp_(-3.0, 3.0)

        for h in hooks:
            h.remove()

        result_img = tensor_to_img(opt_t)

        return EffectResult(
            image=result_img,
            metadata={
                "style_weight": style_weight,
                "content_weight": content_weight,
                "iterations": iterations,
            },
        )

    def validate_params(self, params: dict) -> dict:
        validated = {
            "style_weight": float(params.get("style_weight", 1e6)),
            "content_weight": float(params.get("content_weight", 1.0)),
            "iterations": int(params.get("iterations", 50)),
        }
        if not (1 <= validated["iterations"] <= 200):
            raise ConfigError(
                f"iterations must be between 1 and 200, got {validated['iterations']}",
                effect_name=self.name,
                param_name="iterations",
            )
        if validated["style_weight"] < 0:
            raise ConfigError(
                f"style_weight must be >= 0, got {validated['style_weight']}",
                effect_name=self.name,
                param_name="style_weight",
            )
        if validated["content_weight"] < 0:
            raise ConfigError(
                f"content_weight must be >= 0, got {validated['content_weight']}",
                effect_name=self.name,
                param_name="content_weight",
            )
        return validated


register_effect(StyleTransferEffect())
