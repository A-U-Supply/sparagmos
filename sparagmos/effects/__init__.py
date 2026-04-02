"""Effect base classes, registry, and shared types."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from PIL import Image


class ConfigError(Exception):
    """Raised when effect parameters are invalid."""

    def __init__(self, message: str, effect_name: str = "", param_name: str = ""):
        self.effect_name = effect_name
        self.param_name = param_name
        super().__init__(message)


@dataclass
class EffectContext:
    """Shared state carried through the pipeline."""

    vision: dict[str, Any] | None
    temp_dir: Path
    seed: int
    source_metadata: dict[str, Any]


@dataclass
class EffectResult:
    """Result from applying an effect."""

    image: Image.Image
    metadata: dict[str, Any] = field(default_factory=dict)
    images: list[Image.Image] | None = None


class Effect(ABC):
    """Base class for all effects."""

    name: str
    description: str
    requires: list[str] = []

    @abstractmethod
    def apply(
        self, image: Image.Image, params: dict, context: EffectContext
    ) -> EffectResult:
        """Apply the effect to an image.

        Args:
            image: Input PIL Image (RGB or RGBA).
            params: Resolved recipe parameters (ranges already rolled).
            context: Shared pipeline context (vision, temp dir, seed, etc).

        Returns:
            EffectResult with processed image and metadata.
        """

    @abstractmethod
    def validate_params(self, params: dict) -> dict:
        """Validate and normalize parameters.

        Args:
            params: Raw parameters from recipe YAML.

        Returns:
            Normalized parameters dict.

        Raises:
            ConfigError: If parameters are invalid and cannot be auto-corrected.
        """

    def check_dependencies(self) -> list[str]:
        """Check if required system dependencies are available.

        Returns:
            List of missing dependency names (empty if all present).
        """
        missing = []
        for dep in self.requires:
            if shutil.which(dep) is None:
                missing.append(dep)
        return missing


class SubprocessEffect(Effect):
    """Base class for effects that shell out to external tools.

    Handles temp file creation, execution timeouts, and stderr capture.
    """

    timeout_seconds: int = 120

    def run_command(
        self, cmd: list[str], context: EffectContext, timeout: int | None = None
    ) -> subprocess.CompletedProcess:
        """Run a subprocess command with timeout and error handling.

        Args:
            cmd: Command and arguments.
            context: Effect context (uses temp_dir).
            timeout: Override timeout in seconds.

        Returns:
            CompletedProcess result.

        Raises:
            subprocess.TimeoutExpired: If command exceeds timeout.
            subprocess.CalledProcessError: If command returns non-zero.
        """
        timeout = timeout or self.timeout_seconds
        return subprocess.run(
            cmd,
            capture_output=True,
            timeout=timeout,
            check=True,
            cwd=context.temp_dir,
        )

    def save_temp_image(
        self, image: Image.Image, context: EffectContext, suffix: str = ".png"
    ) -> Path:
        """Save image to a temp file in context.temp_dir.

        Args:
            image: PIL Image to save.
            context: Effect context with temp_dir.
            suffix: File extension.

        Returns:
            Path to the saved temp file.
        """
        path = context.temp_dir / f"input{suffix}"
        image.save(path)
        return path

    def load_temp_image(self, path: Path) -> Image.Image:
        """Load an image from a temp file.

        Args:
            path: Path to image file.

        Returns:
            PIL Image in RGB mode.
        """
        return Image.open(path).convert("RGB")


class ComposeEffect(Effect):
    """Base class for effects that combine multiple images.

    Compose effects take a list of images and produce one output.
    Used for collaging, blending, masking, and fragmenting.
    """

    @abstractmethod
    def compose(
        self, images: list[Image.Image], params: dict, context: EffectContext
    ) -> EffectResult:
        """Combine multiple images into one."""

    def apply(
        self, image: Image.Image, params: dict, context: EffectContext
    ) -> EffectResult:
        """Single-image fallback — delegates to compose with one image."""
        return self.compose([image], params, context)


# --- Effect Registry ---

_registry: dict[str, Effect] = {}


def register_effect(effect: Effect) -> None:
    """Register an effect instance in the global registry."""
    _registry[effect.name] = effect


def get_effect(name: str) -> Effect:
    """Get a registered effect by name.

    Raises:
        KeyError: If no effect with that name is registered.
    """
    if name not in _registry:
        raise KeyError(f"Unknown effect: {name!r}. Available: {sorted(_registry.keys())}")
    return _registry[name]


def list_effects() -> dict[str, Effect]:
    """Return a copy of the effect registry."""
    return dict(_registry)
