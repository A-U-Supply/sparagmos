"""Effect chaining pipeline engine."""

from __future__ import annotations

import logging
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from PIL import Image

from sparagmos.config import Recipe, resolve_params
from sparagmos.effects import ComposeEffect, EffectContext, get_effect

logger = logging.getLogger(__name__)

# Canonical names for multi-image registers (inputs=2 → "a", "b"; inputs=3 → "a", "b", "c"; etc.)
IMAGE_NAMES = ["a", "b", "c", "d", "e"]


@dataclass
class PipelineResult:
    """Result of running a complete recipe pipeline."""

    image: Image.Image
    recipe_name: str
    steps: list[dict[str, Any]] = field(default_factory=list)
    images: list[Image.Image] | None = None


def run_pipeline(
    image: Image.Image | None = None,
    recipe: Recipe | None = None,
    seed: int = 0,
    temp_dir: Path | None = None,
    vision: dict[str, Any] | None = None,
    source_metadata: dict[str, Any] | None = None,
    *,
    images: dict[str, Image.Image] | None = None,
) -> PipelineResult:
    """Run a recipe's effect chain on one or more images.

    Supports two calling conventions:

    Single-image (backward compatible)::

        run_pipeline(image, recipe, seed=42, temp_dir=tmp)

    Multi-image::

        run_pipeline(recipe=recipe, seed=42, images={"a": img_a, "b": img_b})

    The pipeline maintains a dict of named image registers. Each step operates
    on a named image (defaulting to ``"canvas"``) or composes multiple named
    images via a ``ComposeEffect``.

    Args:
        image: Single input PIL Image (backward compat). Stored as ``"canvas"``.
        recipe: Recipe defining the effect chain.
        seed: RNG seed for deterministic param resolution.
        temp_dir: Temp directory for subprocess effects. Created if None.
        vision: Llama Vision analysis results (if recipe uses vision).
        source_metadata: Source image metadata for context.
        images: Multi-image input dict mapping name → PIL Image.

    Returns:
        PipelineResult with the ``"canvas"`` image and step metadata.

    Raises:
        ValueError: If ``recipe`` is not provided, or if the pipeline ends
            without a ``"canvas"`` register.
    """
    if recipe is None:
        raise ValueError("recipe must be provided")

    if source_metadata is None:
        source_metadata = {}

    cleanup_temp = False
    if temp_dir is None:
        temp_dir = Path(tempfile.mkdtemp(prefix="sparagmos_"))
        cleanup_temp = True

    context = EffectContext(
        vision=vision,
        temp_dir=temp_dir,
        seed=seed,
        source_metadata=source_metadata,
    )

    # Build the named-image register dict
    if images is not None:
        registers: dict[str, Image.Image] = {
            name: img.convert("RGB") for name, img in images.items()
        }
    elif image is not None:
        registers = {"canvas": image.convert("RGB")}
    else:
        raise ValueError("Either image or images must be provided")

    steps = []

    try:
        for i, step in enumerate(recipe.effects):
            effect = get_effect(step.type)

            logger.info(
                "Step %d/%d: applying %s",
                i + 1,
                len(recipe.effects),
                effect.name,
            )

            # Resolve parameter ranges with a step-specific seed
            step_seed = seed + i
            resolved = resolve_params(step.params, seed=step_seed)

            if step.images is not None:
                # Compositing step: gather source images by name, call compose()
                source_images = [registers[name] for name in step.images]
                assert isinstance(effect, ComposeEffect), (
                    f"Step {i} specifies images= but effect {effect.name!r} "
                    f"is not a ComposeEffect"
                )
                result = effect.compose(source_images, resolved, context)
                target = step.into or "canvas"
                registers[target] = result.image.convert("RGB")

                step_record = {
                    "effect": effect.name,
                    "description": effect.description,
                    "resolved_params": resolved,
                    "metadata": result.metadata,
                    "images": list(step.images),
                    "into": target,
                }
                if result.images is not None:
                    step_record["_multi_images"] = result.images
                steps.append(step_record)
            else:
                # Single-image step: default to "canvas"
                source_name = step.image or "canvas"
                result = effect.apply(registers[source_name], resolved, context)
                registers[source_name] = result.image.convert("RGB")

                steps.append({
                    "effect": effect.name,
                    "description": effect.description,
                    "resolved_params": resolved,
                    "metadata": result.metadata,
                    "image": source_name,
                })

            logger.info("Step %d complete: %s", i + 1, result.metadata)
    finally:
        if cleanup_temp:
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)

    if "canvas" not in registers:
        raise ValueError(
            "Pipeline ended without a 'canvas' image. "
            "Ensure at least one step writes to 'canvas' (via into='canvas' or default routing)."
        )

    # Check if the final step produced multiple images
    final_images = None
    if steps and steps[-1].get("_multi_images") is not None:
        final_images = steps[-1].pop("_multi_images")

    return PipelineResult(
        image=registers["canvas"],
        recipe_name=recipe.name,
        steps=steps,
        images=final_images,
    )
