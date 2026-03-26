"""Tests for the NetPBM effect."""

from __future__ import annotations

import shutil

import pytest
from PIL import Image

from sparagmos.effects import ConfigError, EffectContext, register_effect
from sparagmos.effects.netpbm import NetPBMEffect

HAS_NETPBM = shutil.which("pnmtopng") is not None
pytestmark = pytest.mark.skipif(not HAS_NETPBM, reason="NetPBM not installed")


@pytest.fixture
def effect():
    e = NetPBMEffect()
    register_effect(e)
    return e


@pytest.fixture
def context(tmp_path):
    return EffectContext(vision=None, temp_dir=tmp_path, seed=42, source_metadata={})


def test_apply_produces_valid_image(effect, test_image_rgb, context):
    params = {"filter": "ppmspread", "amount": 5}
    result = effect.apply(test_image_rgb, params, context)
    assert result.image.size == test_image_rgb.size
    assert result.image.mode == "RGB"


def test_validate_params_defaults(effect):
    params = effect.validate_params({})
    assert params["filter"] == "ppmspread"
    assert params["amount"] == 10


def test_validate_params_invalid_filter_raises(effect):
    with pytest.raises(ConfigError):
        effect.validate_params({"filter": "notafilter"})


def test_validate_params_amount_clamped(effect):
    params = effect.validate_params({"amount": 0})
    assert params["amount"] >= 1


def test_works_with_tiny_image(effect, test_image_tiny, context):
    params = {"filter": "ppmspread", "amount": 1}
    result = effect.apply(test_image_tiny, params, context)
    assert result.image.mode == "RGB"


@pytest.mark.skipif(shutil.which("pgmbentley") is None, reason="pgmbentley not installed")
def test_pgmbentley_filter(effect, test_image_rgb, context):
    params = {"filter": "pgmbentley"}
    result = effect.apply(test_image_rgb, params, context)
    assert result.image.mode == "RGB"


@pytest.mark.skipif(shutil.which("pgmcrater") is None, reason="pgmcrater not installed")
def test_pgmcrater_filter(effect, test_image_rgb, context):
    params = {"filter": "pgmcrater"}
    result = effect.apply(test_image_rgb, params, context)
    assert result.image.mode == "RGB"


def test_metadata_contains_filter(effect, test_image_rgb, context):
    params = {"filter": "ppmspread", "amount": 5}
    result = effect.apply(test_image_rgb, params, context)
    assert result.metadata["filter"] == "ppmspread"
