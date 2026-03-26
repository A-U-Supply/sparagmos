"""Tests for cellular automata effect."""

import numpy as np
import pytest
from PIL import Image

from sparagmos.effects import ConfigError, EffectContext, register_effect
from sparagmos.effects.cellular import CellularEffect


@pytest.fixture
def effect():
    e = CellularEffect()
    register_effect(e)
    return e


@pytest.fixture
def context(tmp_path):
    return EffectContext(vision=None, temp_dir=tmp_path, seed=42, source_metadata={})


def test_apply_produces_valid_image(effect, test_image_rgb, context):
    params = {"rule": "game_of_life", "generations": 3, "threshold": 128, "colorize": False}
    result = effect.apply(test_image_rgb, params, context)
    assert result.image.size == test_image_rgb.size
    assert result.image.mode == "RGB"


def test_apply_modifies_image(effect, test_image_rgb, context):
    params = {"rule": "game_of_life", "generations": 5, "threshold": 128, "colorize": False}
    result = effect.apply(test_image_rgb, params, context)
    orig = np.array(test_image_rgb.convert("RGB"))
    out = np.array(result.image)
    assert not np.array_equal(orig, out)


def test_validate_params_defaults(effect):
    params = effect.validate_params({})
    assert params["rule"] == "game_of_life"
    assert params["generations"] == 10
    assert params["threshold"] == 128
    assert params["colorize"] is False


def test_validate_params_clamps_generations(effect):
    params = effect.validate_params({"generations": 9999})
    assert params["generations"] == 200

    params = effect.validate_params({"generations": -5})
    assert params["generations"] == 1


def test_validate_params_rejects_bad_rule(effect):
    with pytest.raises(ConfigError):
        effect.validate_params({"rule": "conway_3d"})


def test_validate_params_clamps_threshold(effect):
    params = effect.validate_params({"threshold": 999})
    assert params["threshold"] == 255

    params = effect.validate_params({"threshold": -10})
    assert params["threshold"] == 0


def test_works_with_tiny_image(effect, test_image_tiny, context):
    params = {"rule": "game_of_life", "generations": 2, "threshold": 128, "colorize": False}
    result = effect.apply(test_image_tiny, params, context)
    assert result.image.size == test_image_tiny.size


def test_rule_110_produces_valid_image(effect, test_image_rgb, context):
    params = {"rule": "rule_110", "generations": 3, "threshold": 128, "colorize": False}
    result = effect.apply(test_image_rgb, params, context)
    assert result.image.size == test_image_rgb.size
    assert result.image.mode == "RGB"


def test_colorize_produces_rgb(effect, test_image_rgb, context):
    params = {"rule": "game_of_life", "generations": 3, "threshold": 128, "colorize": True}
    result = effect.apply(test_image_rgb, params, context)
    assert result.image.mode == "RGB"
    assert result.image.size == test_image_rgb.size


def test_rule_110_tiny_image(effect, test_image_tiny, context):
    params = {"rule": "rule_110", "generations": 2, "threshold": 64, "colorize": False}
    result = effect.apply(test_image_tiny, params, context)
    assert result.image.size == test_image_tiny.size
