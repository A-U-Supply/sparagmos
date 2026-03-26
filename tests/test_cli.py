"""Tests for the CLI interface."""

import sys
from unittest.mock import patch, MagicMock

import pytest
from PIL import Image

from sparagmos.cli import build_parser


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
