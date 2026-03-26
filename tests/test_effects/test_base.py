"""Tests for effect base classes and registry."""

from PIL import Image

from sparagmos.effects import (
    ConfigError,
    Effect,
    EffectContext,
    EffectResult,
    SubprocessEffect,
    get_effect,
    list_effects,
    register_effect,
)


def test_effect_result_has_image_and_metadata(test_image_rgb, effect_context, dummy_effect):
    result = dummy_effect.apply(test_image_rgb, {}, effect_context)
    assert isinstance(result.image, Image.Image)
    assert isinstance(result.metadata, dict)


def test_effect_context_fields(tmp_path):
    ctx = EffectContext(
        vision={"objects": ["face"]},
        temp_dir=tmp_path,
        seed=123,
        source_metadata={"file_id": "F123"},
    )
    assert ctx.vision == {"objects": ["face"]}
    assert ctx.seed == 123
    assert ctx.temp_dir == tmp_path


def test_register_and_get_effect(dummy_effect):
    register_effect(dummy_effect)
    retrieved = get_effect("dummy")
    assert retrieved.name == "dummy"


def test_get_unknown_effect_raises():
    try:
        get_effect("nonexistent_effect_xyz")
        assert False, "Should have raised"
    except KeyError:
        pass


def test_list_effects_returns_dict(dummy_effect):
    register_effect(dummy_effect)
    effects = list_effects()
    assert isinstance(effects, dict)
    assert "dummy" in effects


def test_config_error():
    err = ConfigError("bad param", effect_name="pixel_sort", param_name="threshold")
    assert "bad param" in str(err)
    assert err.effect_name == "pixel_sort"
