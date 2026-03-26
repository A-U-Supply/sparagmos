"""Tests for the CLI interface."""

import sys
from unittest.mock import patch, MagicMock

import pytest

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
    assert args.input == "photo.jpg"
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
