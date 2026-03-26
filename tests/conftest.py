"""Shared test fixtures for sparagmos."""

import tempfile
from pathlib import Path

import pytest
from PIL import Image


@pytest.fixture
def test_image_rgb():
    """Create a small RGB test image (64x64) with varied content."""
    img = Image.new("RGB", (64, 64))
    pixels = img.load()
    for x in range(64):
        for y in range(64):
            pixels[x, y] = (
                (x * 4) % 256,
                (y * 4) % 256,
                ((x + y) * 2) % 256,
            )
    return img


@pytest.fixture
def test_image_rgba():
    """Create a small RGBA test image (64x64)."""
    img = Image.new("RGBA", (64, 64))
    pixels = img.load()
    for x in range(64):
        for y in range(64):
            pixels[x, y] = (
                (x * 4) % 256,
                (y * 4) % 256,
                ((x + y) * 2) % 256,
                200,
            )
    return img


@pytest.fixture
def test_image_grayscale():
    """Create a small grayscale test image (64x64)."""
    img = Image.new("L", (64, 64))
    pixels = img.load()
    for x in range(64):
        for y in range(64):
            pixels[x, y] = ((x + y) * 2) % 256
    return img


@pytest.fixture
def test_image_tiny():
    """Create a tiny 4x4 RGB image for edge case testing."""
    img = Image.new("RGB", (4, 4), color=(128, 64, 32))
    return img


@pytest.fixture
def tmp_dir():
    """Create a temporary directory for test output."""
    with tempfile.TemporaryDirectory() as d:
        yield Path(d)


@pytest.fixture
def test_image_file(test_image_rgb, tmp_dir):
    """Save a test image to disk and return the path."""
    path = tmp_dir / "test_input.png"
    test_image_rgb.save(path)
    return path


@pytest.fixture
def test_images_multi():
    """Create 5 distinct test images for multi-input testing."""
    colors = [
        (200, 50, 50),   # reddish
        (50, 200, 50),   # greenish
        (50, 50, 200),   # bluish
        (200, 200, 50),  # yellowish
        (200, 50, 200),  # magentaish
    ]
    imgs = []
    for i, color in enumerate(colors):
        img = Image.new("RGB", (64, 64))
        pixels = img.load()
        for x in range(64):
            for y in range(64):
                pixels[x, y] = (
                    (color[0] + x * 2) % 256,
                    (color[1] + y * 2) % 256,
                    (color[2] + (x + y)) % 256,
                )
        imgs.append(img)
    return imgs
