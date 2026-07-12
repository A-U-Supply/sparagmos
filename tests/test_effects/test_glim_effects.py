"""Tests for the glim-batch effects (iridesce, holofoil, prism, sequin,
bandsplit, chromostereo, driftring, stereogram)."""

import numpy as np
import pytest
from PIL import Image

from sparagmos.effects import ConfigError, EffectContext
from sparagmos.effects.bandsplit_effect import BandsplitEffect
from sparagmos.effects.chromostereo_effect import ChromostereoEffect
from sparagmos.effects.driftring_effect import DriftringEffect
from sparagmos.effects.holofoil_effect import HolofoilEffect
from sparagmos.effects.iridesce_effect import IridesceEffect
from sparagmos.effects.prism_effect import PrismEffect
from sparagmos.effects.sequin_effect import SequinEffect
from sparagmos.effects.stereogram_effect import StereogramEffect


@pytest.fixture
def context(tmp_path):
    return EffectContext(vision=None, temp_dir=tmp_path, seed=42, source_metadata={})


@pytest.fixture
def photo():
    """Structured test image: gradient + bright blob + dark square."""
    rng = np.random.default_rng(5)
    arr = np.tile(np.linspace(40, 200, 320, dtype=np.uint8), (240, 1))
    arr = np.stack([arr, arr // 2 + 60, 255 - arr], axis=2)
    arr[60:120, 40:100] = (20, 24, 30)
    yy, xx = np.mgrid[0:240, 0:320]
    blob = ((xx - 240) ** 2 + (yy - 80) ** 2) < 40**2
    arr[blob] = (245, 240, 230)
    arr = np.clip(arr + rng.integers(-8, 8, arr.shape), 0, 255).astype(np.uint8)
    return Image.fromarray(arr)


SINGLE_EFFECTS = [IridesceEffect, HolofoilEffect, PrismEffect, SequinEffect, ChromostereoEffect, DriftringEffect]


@pytest.mark.parametrize("cls", SINGLE_EFFECTS)
def test_single_image_effects_smoke(cls, photo, context):
    result = cls().apply(photo, {}, context)
    assert result.image.mode == "RGB"
    assert result.image.size == photo.size  # under MAX_EDGE caps
    assert not np.array_equal(np.array(result.image), np.array(photo))


@pytest.mark.parametrize("cls", SINGLE_EFFECTS)
def test_seeded_determinism(cls, photo, context):
    a = cls().apply(photo, {}, context)
    b = cls().apply(photo, {}, context)
    assert np.array_equal(np.array(a.image), np.array(b.image))


def test_iridesce_adds_color(photo, context):
    gray = photo.convert("L").convert("RGB")
    result = IridesceEffect().apply(gray, {"strength": 0.8}, context)
    arr = np.array(result.image).astype(int)
    chroma = np.abs(arr - arr.mean(axis=2, keepdims=True)).mean()
    assert chroma > 5.0  # monochrome input gains real color


def test_holofoil_ground_param(photo, context):
    dark = HolofoilEffect().apply(photo, {"ground": "dark", "glints": 0}, context)
    paper = HolofoilEffect().apply(photo, {"ground": "paper", "glints": 0}, context)
    assert np.array(dark.image).mean() < np.array(paper.image).mean()
    with pytest.raises(ConfigError):
        HolofoilEffect().validate_params({"ground": "velvet"})


def test_prism_fringes_monochrome(photo, context):
    gray = photo.convert("L").convert("RGB")
    result = PrismEffect().apply(gray, {"max_offset": 0.05, "keep_base": 0.2}, context)
    arr = np.array(result.image).astype(int)
    chroma = np.abs(arr - arr.mean(axis=2, keepdims=True)).mean()
    assert chroma > 5.0


def test_sequin_caps_oversize(context):
    big = Image.new("RGB", (4000, 3000), (120, 80, 160))
    result = SequinEffect().apply(big, {}, context)
    assert max(result.image.size) <= 2048


def test_bandsplit_identity_shift(photo, context):
    """Downscaled hybrid resembles A more than B; detail residual resembles B."""
    rng = np.random.default_rng(9)
    b_img = Image.fromarray(rng.integers(0, 255, (240, 320, 3), dtype=np.uint8))
    result = BandsplitEffect().compose([photo, b_img], {}, context)
    small = np.array(result.image.resize((32, 24), Image.LANCZOS)).astype(float)
    small_a = np.array(photo.resize((32, 24), Image.LANCZOS)).astype(float)
    small_b = np.array(b_img.resize((32, 24), Image.LANCZOS)).astype(float)
    assert np.abs(small - small_a).mean() < np.abs(small - small_b).mean()


def test_bandsplit_resizes_mismatched(photo, context):
    b_img = Image.new("RGB", (100, 77), (200, 40, 40))
    result = BandsplitEffect().compose([photo, b_img], {}, context)
    assert result.image.size == photo.size


def test_chromostereo_palette_is_pure(photo, context):
    result = ChromostereoEffect().apply(photo, {"bands": 3}, context)
    colors = {tuple(c) for c in np.unique(np.array(result.image).reshape(-1, 3), axis=0)}
    assert len(colors) <= 3


def test_driftring_uses_four_step_palette(photo, context):
    result = DriftringEffect().apply(photo, {"texture": 0.0}, context)
    colors = np.unique(np.array(result.image).reshape(-1, 3), axis=0)
    assert len(colors) <= 4
    lums = sorted(c.astype(int).mean() for c in colors)
    assert lums[0] < 30 and lums[-1] > 220  # black and white poles present


def test_stereogram_recovers_depth(context):
    """Cross-correlating the output against itself recovers the depth step."""
    depth = np.zeros((160, 360), dtype=np.uint8)
    depth[40:120, 140:260] = 255  # near square on far ground
    depth_img = Image.fromarray(depth)
    rng = np.random.default_rng(3)
    texture = Image.fromarray(rng.integers(0, 255, (80, 80, 3), dtype=np.uint8))
    strip, gain = 60, 0.3
    result = StereogramEffect().compose(
        [depth_img, texture], {"strip": strip, "depth_gain": gain, "mode": "dots"}, context
    )
    out = np.array(result.image.convert("L")).astype(np.float32)

    def best_shift(y, x0, x1):
        row = out[y]
        best, best_err = strip, 1e18
        for s in range(strip // 2, strip + 1):
            seg = row[x0:x1]
            err = float(np.abs(seg - row[x0 + s:x1 + s]).mean())
            if err < best_err:
                best, best_err = s, err
        return best

    far = np.mean([best_shift(y, 10, 60) for y in range(10, 30)])
    near = np.mean([best_shift(y, 160, 210) for y in range(70, 90)])
    assert near < far - 2  # near region repeats at a visibly shorter separation


def test_stereogram_mode_validation():
    with pytest.raises(ConfigError):
        StereogramEffect().validate_params({"mode": "hologram"})
