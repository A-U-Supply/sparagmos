"""Tests for text_relic effect."""

import shutil

import numpy as np
import pytest
from PIL import Image, ImageDraw

from sparagmos.effects import ConfigError, EffectContext
from sparagmos.effects.text_relic_effect import TextRelicEffect

needs_tesseract = pytest.mark.skipif(
    shutil.which("tesseract") is None, reason="tesseract binary not installed"
)


@pytest.fixture
def effect():
    return TextRelicEffect()


@pytest.fixture
def context(tmp_path):
    return EffectContext(vision=None, temp_dir=tmp_path, seed=42, source_metadata={})


@pytest.fixture
def text_image():
    """Mid-grey noise field with large legible black text on a white plate."""
    from PIL import ImageFont

    rng = np.random.default_rng(7)
    arr = rng.integers(90, 160, (400, 600, 3), dtype=np.uint8)
    img = Image.fromarray(arr)
    draw = ImageDraw.Draw(img)
    draw.rectangle([30, 30, 570, 140], fill=(255, 255, 255))
    font = ImageFont.load_default(size=52)
    draw.text((50, 55), "RELIC SURVIVES", fill=(0, 0, 0), font=font)
    return img


@pytest.fixture
def no_text_image():
    rng = np.random.default_rng(11)
    return Image.fromarray(rng.integers(60, 200, (200, 300, 3), dtype=np.uint8))


def test_validate_rejects_unknown_background(effect):
    with pytest.raises(ConfigError):
        effect.validate_params({"background": "vaporize"})


def test_validate_rejects_unknown_preserve(effect):
    with pytest.raises(ConfigError):
        effect.validate_params({"preserve": "amber"})


def test_validate_clamps(effect):
    validated = effect.validate_params({"pad": 500, "min_conf": -3})
    assert validated["pad"] == 60
    assert validated["min_conf"] == 0


@needs_tesseract
@pytest.mark.parametrize("background", ["washout", "mosh", "sort"])
def test_text_region_survives(effect, text_image, context, background):
    result = effect.apply(text_image, {"background": background, "pad": 4}, context)
    assert result.image.size == text_image.size
    assert result.metadata["text_boxes"] > 0
    orig = np.array(text_image)
    out = np.array(result.image)
    # The interior of a detected word box should be (near-)unchanged;
    # the noise field should not be.
    import pytesseract

    data = pytesseract.image_to_data(text_image, output_type=pytesseract.Output.DICT)
    boxes = [
        (data["left"][i], data["top"][i], data["width"][i], data["height"][i])
        for i in range(len(data["text"]))
        if data["text"][i].strip() and float(data["conf"][i]) >= 40
    ]
    assert boxes
    x, y, bw, bh = boxes[0]
    word = (slice(y + 2, y + bh - 2), slice(x + 2, x + bw - 2))
    assert np.abs(orig[word].astype(int) - out[word].astype(int)).mean() < 2
    field = (slice(200, 380), slice(0, 600))
    assert not np.array_equal(orig[field], out[field])


@needs_tesseract
def test_no_text_destroys_whole_frame(effect, no_text_image, context):
    result = effect.apply(no_text_image, {"background": "washout"}, context)
    assert result.metadata["text_boxes"] == 0
    assert not np.array_equal(np.array(no_text_image), np.array(result.image))
