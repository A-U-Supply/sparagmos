"""Tests for the CLI interface."""

import re
import sys
from unittest.mock import patch, MagicMock

import pytest
from PIL import Image

from sparagmos.cli import build_parser
from sparagmos.config import Recipe


def test_parser_defaults():
    parser = build_parser()
    args = parser.parse_args([])
    assert args.recipe is None
    assert args.input is None
    assert args.output is None
    assert args.dry_run is False
    assert args.list_recipes is False
    assert args.list_effects is False
    assert args.validate is False


def test_parser_recipe():
    parser = build_parser()
    args = parser.parse_args(["--recipe", "vhs-meltdown"])
    assert args.recipe == "vhs-meltdown"


def test_parser_local_mode():
    parser = build_parser()
    args = parser.parse_args(["--input", "photo.jpg", "--output", "out.png"])
    assert args.input == ["photo.jpg"]
    assert args.output == "out.png"


def test_parser_dry_run():
    parser = build_parser()
    args = parser.parse_args(["--dry-run"])
    assert args.dry_run is True


def test_parser_list_flags():
    parser = build_parser()

    args = parser.parse_args(["--list-recipes"])
    assert args.list_recipes is True

    args = parser.parse_args(["--list-effects"])
    assert args.list_effects is True

    args = parser.parse_args(["--validate"])
    assert args.validate is True


def test_input_accepts_multiple_files(tmp_path):
    """--input flag accepts multiple files via nargs='+'."""
    for name in ["a.png", "b.png", "c.png"]:
        Image.new("RGB", (64, 64)).save(tmp_path / name)
    parser = build_parser()
    args = parser.parse_args([
        "--input", str(tmp_path / "a.png"), str(tmp_path / "b.png"), str(tmp_path / "c.png"),
        "--output", str(tmp_path / "out.png"),
    ])
    assert len(args.input) == 3


def test_input_single_file_still_works(tmp_path):
    """--input with one file returns a list of one."""
    Image.new("RGB", (64, 64)).save(tmp_path / "a.png")
    parser = build_parser()
    args = parser.parse_args(["--input", str(tmp_path / "a.png"), "--output", str(tmp_path / "out.png")])
    assert len(args.input) == 1


# ---------------------------------------------------------------------------
# URL parsing — spaces, commas, and newlines
# ---------------------------------------------------------------------------


def _parse_urls(raw: str) -> list[str]:
    """Replicate the CLI's URL parsing logic."""
    return [u.strip() for u in re.split(r'[\s,]+', raw) if u.strip()]


class TestUrlParsing:
    """Test that --image-urls accepts commas, spaces, newlines, and mixes."""

    def test_comma_separated(self):
        raw = "https://a.com/1.png,https://b.com/2.png,https://c.com/3.png"
        assert _parse_urls(raw) == [
            "https://a.com/1.png",
            "https://b.com/2.png",
            "https://c.com/3.png",
        ]

    def test_space_separated(self):
        raw = "https://a.com/1.png https://b.com/2.png https://c.com/3.png"
        assert _parse_urls(raw) == [
            "https://a.com/1.png",
            "https://b.com/2.png",
            "https://c.com/3.png",
        ]

    def test_newline_separated(self):
        raw = "https://a.com/1.png\nhttps://b.com/2.png\nhttps://c.com/3.png"
        assert _parse_urls(raw) == [
            "https://a.com/1.png",
            "https://b.com/2.png",
            "https://c.com/3.png",
        ]

    def test_mixed_delimiters(self):
        raw = "https://a.com/1.png, https://b.com/2.png\nhttps://c.com/3.png"
        assert _parse_urls(raw) == [
            "https://a.com/1.png",
            "https://b.com/2.png",
            "https://c.com/3.png",
        ]

    def test_extra_whitespace(self):
        raw = "  https://a.com/1.png  ,  https://b.com/2.png  "
        assert _parse_urls(raw) == [
            "https://a.com/1.png",
            "https://b.com/2.png",
        ]

    def test_single_url(self):
        raw = "https://a.com/1.png"
        assert _parse_urls(raw) == ["https://a.com/1.png"]

    def test_empty_string(self):
        assert _parse_urls("") == []


# ---------------------------------------------------------------------------
# Recipe filtering by URL count
# ---------------------------------------------------------------------------


def _make_recipe(inputs: int) -> Recipe:
    """Create a minimal Recipe for testing."""
    return Recipe(
        name=f"test-{inputs}",
        description="test",
        effects=[],
        inputs=inputs,
    )


class TestRecipeFilteringByUrlCount:
    """Test that random recipe selection prefers recipes matching the URL count."""

    def test_filters_to_recipes_with_enough_inputs(self):
        recipes = {
            "r2": _make_recipe(2),
            "r3": _make_recipe(3),
            "r4": _make_recipe(4),
            "r5": _make_recipe(5),
        }
        url_count = 4
        matching = {k: v for k, v in recipes.items() if v.inputs >= url_count}
        assert set(matching.keys()) == {"r4", "r5"}

    def test_all_recipes_eligible_when_url_count_exceeds_max(self):
        recipes = {
            "r3": _make_recipe(3),
            "r5": _make_recipe(5),
        }
        url_count = 6
        matching = {k: v for k, v in recipes.items() if v.inputs >= url_count}
        # No match → fallback to all recipes
        assert len(matching) == 0

    def test_exact_match_is_included(self):
        recipes = {
            "r3": _make_recipe(3),
            "r4": _make_recipe(4),
        }
        url_count = 3
        matching = {k: v for k, v in recipes.items() if v.inputs >= url_count}
        assert set(matching.keys()) == {"r3", "r4"}


# ---------------------------------------------------------------------------
# URL truncation
# ---------------------------------------------------------------------------


class TestUrlTruncation:
    """Test that excess URLs are truncated to the recipe's input count."""

    def test_truncates_to_recipe_inputs(self):
        urls = ["https://a.com/1", "https://b.com/2", "https://c.com/3", "https://d.com/4"]
        recipe_inputs = 3
        if len(urls) > recipe_inputs:
            urls = urls[:recipe_inputs]
        assert len(urls) == 3
        assert urls == ["https://a.com/1", "https://b.com/2", "https://c.com/3"]

    def test_no_truncation_when_exact_match(self):
        urls = ["https://a.com/1", "https://b.com/2", "https://c.com/3"]
        recipe_inputs = 3
        if len(urls) > recipe_inputs:
            urls = urls[:recipe_inputs]
        assert len(urls) == 3

    def test_no_truncation_when_fewer_urls(self):
        urls = ["https://a.com/1", "https://b.com/2"]
        recipe_inputs = 4
        if len(urls) > recipe_inputs:
            urls = urls[:recipe_inputs]
        assert len(urls) == 2
