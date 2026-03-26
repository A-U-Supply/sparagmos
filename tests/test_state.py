"""Tests for state management."""

import json
from pathlib import Path

import pytest

from sparagmos.state import State, ProcessedEntry


@pytest.fixture
def state_file(tmp_path):
    return tmp_path / "state.json"


@pytest.fixture
def empty_state(state_file):
    state_file.write_text(json.dumps({"processed": []}))
    return State(state_file)


def test_load_empty_state(empty_state):
    assert len(empty_state.processed) == 0


def test_load_missing_file_creates_empty(tmp_path):
    path = tmp_path / "missing.json"
    state = State(path)
    assert len(state.processed) == 0


def test_add_entry(empty_state):
    empty_state.add(
        source_file_id="F123",
        source_date="2026-01-15",
        source_user="U456",
        recipe="test-recipe",
        effects=["effect_a", "effect_b"],
        processed_date="2026-03-26",
        posted_ts="123.456",
    )
    assert len(empty_state.processed) == 1
    assert empty_state.processed[0].source_file_id == "F123"


def test_save_and_reload(empty_state, state_file):
    empty_state.add(
        source_file_id="F789",
        source_date="2026-02-01",
        source_user="U111",
        recipe="vhs-meltdown",
        effects=["crt_vhs"],
        processed_date="2026-03-26",
    )
    empty_state.save()

    reloaded = State(state_file)
    assert len(reloaded.processed) == 1
    assert reloaded.processed[0].recipe == "vhs-meltdown"


def test_is_processed_checks_file_and_recipe(empty_state):
    empty_state.add(
        source_file_id="F123",
        source_date="2026-01-15",
        source_user="U456",
        recipe="recipe-a",
        effects=["effect_a"],
        processed_date="2026-03-26",
    )
    assert empty_state.is_processed("F123", "recipe-a") is True
    assert empty_state.is_processed("F123", "recipe-b") is False
    assert empty_state.is_processed("F999", "recipe-a") is False


def test_all_file_ids(empty_state):
    empty_state.add(
        source_file_id="F1",
        source_date="2026-01-01",
        source_user="U1",
        recipe="r1",
        effects=[],
        processed_date="2026-03-26",
    )
    empty_state.add(
        source_file_id="F2",
        source_date="2026-01-02",
        source_user="U2",
        recipe="r2",
        effects=[],
        processed_date="2026-03-26",
    )
    assert empty_state.all_file_ids() == {"F1", "F2"}


def test_processed_pairs(empty_state):
    empty_state.add(
        source_file_id="F1",
        source_date="2026-01-01",
        source_user="U1",
        recipe="r1",
        effects=[],
        processed_date="2026-03-26",
    )
    pairs = empty_state.processed_pairs()
    assert ("F1", "r1") in pairs
