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
    result = PrismEffect().apply(gray, {"max_offset": 0.05, "ground_dim": 0.25}, context)
    arr = np.array(result.image).astype(int)
    chroma = np.abs(arr - arr.mean(axis=2, keepdims=True)).mean()
    assert chroma > 3.0


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


def test_chromostereo_planes_dominate(photo, context):
    """Red/blue/near-black should dominate even with overlay + shadow cues."""
    result = ChromostereoEffect().apply(photo, {}, context)
    arr = np.array(result.image).astype(int)
    reddish = (arr[:, :, 0] > 150) & (arr[:, :, 2] < 120)
    bluish = (arr[:, :, 2] > 120) & (arr[:, :, 0] < 100)
    darkish = arr.sum(axis=2) < 120
    assert (reddish | bluish | darkish).mean() > 0.95


def test_chromostereo_two_planes(context):
    """A's bright shape lands on the red plane, B's on the blue plane."""
    a = np.zeros((120, 160, 3), dtype=np.uint8)
    a[20:60, 20:60] = 255
    b = np.zeros((120, 160, 3), dtype=np.uint8)
    b[70:110, 100:140] = 255
    result = ChromostereoEffect().compose(
        [Image.fromarray(a), Image.fromarray(b)], {"cutoff": 0.5}, context
    )
    out = np.array(result.image).astype(int)
    a_zone = out[30:50, 30:50]
    b_zone = out[80:100, 110:130]
    assert (a_zone[:, :, 0] > 200).mean() > 0.9  # red plane
    assert (b_zone[:, :, 2] > 150).mean() > 0.9  # blue plane
    assert (b_zone[:, :, 0] < 60).all()


def test_sequin_flip_regions(photo, context):
    """Discs under B's bright half flip to near-neutral silver."""
    b = np.zeros((photo.height, photo.width), dtype=np.uint8)
    b[:, photo.width // 2:] = 255
    result = SequinEffect().compose(
        [photo, Image.fromarray(b).convert("RGB")], {"disc": 20, "sparkle": 0.0}, context
    )
    out = np.array(result.image).astype(np.float32)
    right = out[:, photo.width // 2 + 20:]
    chroma = np.abs(right - right.mean(axis=2, keepdims=True)).mean()
    assert chroma < 8.0  # silver side is near-neutral
    assert right.mean() > 120  # and bright


def test_iridesce_film_driven_by_b(context):
    """A flat grey A gains structured color from B's gradient."""
    flat = Image.new("RGB", (160, 120), (128, 128, 128))
    grad = np.tile(np.linspace(0, 255, 160, dtype=np.uint8), (120, 1))
    b = Image.fromarray(np.stack([grad] * 3, axis=2))
    result = IridesceEffect().compose([flat, b], {"strength": 0.9}, context)
    arr = np.array(result.image).astype(int)
    chroma = np.abs(arr - arr.mean(axis=2, keepdims=True)).mean()
    assert chroma > 3.0


def test_prism_ground_is_b(context):
    """With a black A (no light), the output is just B dimmed."""
    black = Image.new("RGB", (160, 120), (0, 0, 0))
    rng = np.random.default_rng(2)
    b_arr = rng.integers(60, 220, (120, 160, 3), dtype=np.uint8)
    result = PrismEffect().compose(
        [black, Image.fromarray(b_arr)], {"ground_dim": 0.5}, context
    )
    out = np.array(result.image).astype(np.float32)
    assert np.abs(out - b_arr.astype(np.float32) * 0.5).mean() < 3.0


def test_driftring_wheels_seeded_by_b(photo, context):
    b = np.zeros((photo.height, photo.width), dtype=np.uint8)
    b[20:40, 20:40] = 255
    b[200:220, 280:300] = 255
    result = DriftringEffect().compose(
        [photo, Image.fromarray(b).convert("RGB")], {"wheels": 4}, context
    )
    assert len(result.metadata["centers"]) >= 2


def test_driftring_keeps_bw_poles_and_local_color(photo, context):
    result = DriftringEffect().apply(photo, {"texture": 0.0}, context)
    arr = np.array(result.image).astype(int)
    is_black = (np.abs(arr - np.array([8, 8, 10])) < 3).all(axis=2)
    is_white = (np.abs(arr - np.array([250, 250, 248])) < 3).all(axis=2)
    assert is_black.mean() > 0.1 and is_white.mean() > 0.1  # illusion poles
    colored = arr[~(is_black | is_white)]
    assert len(colored) > 0
    chroma = np.abs(colored - colored.mean(axis=1, keepdims=True)).mean()
    assert chroma > 4.0  # color steps carry A's local color


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
