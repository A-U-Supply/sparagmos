"""Effect chaining pipeline engine."""

from __future__ import annotations

import logging
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from PIL import Image

from sparagmos.config import Recipe, resolve_params
from sparagmos.effects import EffectContext, get_effect

logger = logging.getLogger(__name__)


@dataclass
class PipelineResult:
    """Result of running a complete recipe pipeline."""

    image: Image.Image
    recipe_name: str
    steps: list[dict[str, Any]] = field(default_factory=list)


def run_pipeline(
    image: Image.Image,
    recipe: Recipe,
    seed: int,
    temp_dir: Path | None = None,
    vision: dict[str, Any] | None = None,
    source_metadata: dict[str, Any] | None = None,
) -> PipelineResult:
    """Run a recipe's effect chain on an image.

    Args:
        image: Input PIL Image.
        recipe: Recipe defining the effect chain.
        seed: RNG seed for deterministic param resolution.
        temp_dir: Temp directory for subprocess effects. Created if None.
        vision: Llama Vision analysis results (if recipe uses vision).
        source_metadata: Source image metadata for context.

    Returns:
        PipelineResult with processed image and step metadata.
    """
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

    # Ensure image is RGB
    current_image = image.convert("RGB")
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

            # Apply the effect
            result = effect.apply(current_image, resolved, context)
            current_image = result.image.convert("RGB")

            steps.append({
                "effect": effect.name,
                "description": effect.description,
                "resolved_params": resolved,
                "metadata": result.metadata,
            })

            logger.info("Step %d complete: %s", i + 1, result.metadata)
    finally:
        if cleanup_temp:
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)

    return PipelineResult(
        image=current_image,
        recipe_name=recipe.name,
        steps=steps,
    )
