"""Shared fixtures for effect tests."""

import pytest

from sparagmos.effects import Effect, EffectContext, EffectResult


class DummyEffect(Effect):
    """Minimal effect implementation for testing."""

    name = "dummy"
    description = "A dummy effect for testing"
    requires: list[str] = []

    def apply(self, image, params, context):
        return EffectResult(image=image, metadata={"dummy": True})

    def validate_params(self, params):
        return params


@pytest.fixture
def dummy_effect():
    return DummyEffect()


@pytest.fixture
def effect_context(tmp_path):
    return EffectContext(
        vision=None,
        temp_dir=tmp_path,
        seed=42,
        source_metadata={},
    )
