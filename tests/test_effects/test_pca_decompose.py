"""Tests for PCA/SVD decomposition effect."""

import numpy as np
import pytest
from PIL import Image

from sparagmos.effects import ConfigError, EffectContext, register_effect
from sparagmos.effects.pca_decompose import PcaDecomposeEffect


@pytest.fixture
def effect():
    e = PcaDecomposeEffect()
    register_effect(e)
    return e


@pytest.fixture
def context(tmp_path):
    return EffectContext(vision=None, temp_dir=tmp_path, seed=42, source_metadata={})


def test_apply_produces_valid_image(effect, test_image_rgb, context):
    params = {"n_components": 5, "mode": "top"}
    result = effect.apply(test_image_rgb, params, context)
    assert result.image.size == test_image_rgb.size
    assert result.image.mode == "RGB"


def test_apply_modifies_image_top(effect, test_image_rgb, context):
    params = {"n_components": 3, "mode": "top"}
    result = effect.apply(test_image_rgb, params, context)
    orig = np.array(test_image_rgb.convert("RGB"))
    out = np.array(result.image)
    assert not np.array_equal(orig, out)


def test_apply_modifies_image_bottom(effect, test_image_rgb, context):
    params = {"n_components": 3, "mode": "bottom"}
    result = effect.apply(test_image_rgb, params, context)
    orig = np.array(test_image_rgb.convert("RGB"))
    out = np.array(result.image)
    assert not np.array_equal(orig, out)


def test_validate_params_defaults(effect):
    params = effect.validate_params({})
    assert params["n_components"] == 5
    assert params["mode"] == "top"


def test_validate_params_clamps_n_components(effect):
    params = effect.validate_params({"n_components": 9999})
    assert params["n_components"] == 100

    params = effect.validate_params({"n_components": 0})
    assert params["n_components"] == 1


def test_validate_params_rejects_bad_mode(effect):
    with pytest.raises(ConfigError):
        effect.validate_params({"mode": "diagonal"})


def test_works_with_tiny_image(effect, test_image_tiny, context):
    params = {"n_components": 2, "mode": "top"}
    result = effect.apply(test_image_tiny, params, context)
    assert result.image.size == test_image_tiny.size


def test_bottom_mode_tiny_image(effect, test_image_tiny, context):
    params = {"n_components": 1, "mode": "bottom"}
    result = effect.apply(test_image_tiny, params, context)
    assert result.image.size == test_image_tiny.size
    assert result.image.mode == "RGB"


def test_top_full_rank_is_near_identity(effect, test_image_rgb, context):
    """Using all singular values should reproduce the original approximately."""
    # 64x64 image: min(64,64) = 64 singular values per channel
    params = {"n_components": 64, "mode": "top"}
    result = effect.apply(test_image_rgb, params, context)
    orig = np.array(test_image_rgb.convert("RGB"), dtype=np.float64)
    out = np.array(result.image, dtype=np.float64)
    # Allow small numerical difference from clipping
    assert np.mean(np.abs(orig - out)) < 2.0


def test_metadata_contains_params(effect, test_image_rgb, context):
    params = {"n_components": 7, "mode": "bottom"}
    result = effect.apply(test_image_rgb, params, context)
    assert result.metadata["n_components"] == 7
    assert result.metadata["mode"] == "bottom"
