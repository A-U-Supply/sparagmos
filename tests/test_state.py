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
    assert empty_state.processed[0].source_file_ids == ["F123"]


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


# --- New multi-source tests ---


def test_add_multi_source_entry(empty_state):
    """add_multi with 3 file IDs stores them all."""
    empty_state.add_multi(
        source_file_ids=["F1", "F2", "F3"],
        source_dates=["2026-01-01", "2026-01-02", "2026-01-03"],
        source_users=["U1", "U2", "U3"],
        recipe="collage-recipe",
        effects=["blend", "distort"],
        processed_date="2026-03-26",
        posted_ts="999.000",
    )
    assert len(empty_state.processed) == 1
    entry = empty_state.processed[0]
    assert entry.source_file_ids == ["F1", "F2", "F3"]
    assert entry.source_dates == ["2026-01-01", "2026-01-02", "2026-01-03"]
    assert entry.source_users == ["U1", "U2", "U3"]
    assert entry.recipe == "collage-recipe"
    assert entry.posted_ts == "999.000"


def test_multi_source_save_reload(empty_state, state_file):
    """Saving and reloading preserves multi-source entry."""
    empty_state.add_multi(
        source_file_ids=["FA", "FB"],
        source_dates=["2026-02-01", "2026-02-02"],
        source_users=["UA", "UB"],
        recipe="dual-blend",
        effects=["overlay"],
        processed_date="2026-03-26",
    )
    empty_state.save()

    reloaded = State(state_file)
    assert len(reloaded.processed) == 1
    entry = reloaded.processed[0]
    assert entry.source_file_ids == ["FA", "FB"]
    assert entry.source_dates == ["2026-02-01", "2026-02-02"]
    assert entry.source_users == ["UA", "UB"]
    assert entry.recipe == "dual-blend"


def test_backward_compat_single_source(tmp_path):
    """Old state.json with singular source_file_id loads as a list."""
    old_data = {
        "processed": [
            {
                "source_file_id": "FOLD1",
                "source_date": "2025-12-01",
                "source_user": "UOLD",
                "recipe": "old-recipe",
                "effects": ["grain"],
                "processed_date": "2025-12-02",
                "posted_ts": "",
            }
        ]
    }
    path = tmp_path / "old_state.json"
    path.write_text(json.dumps(old_data))

    state = State(path)
    assert len(state.processed) == 1
    entry = state.processed[0]
    assert entry.source_file_ids == ["FOLD1"]
    assert entry.source_dates == ["2025-12-01"]
    assert entry.source_users == ["UOLD"]


def test_processed_combos(empty_state):
    """processed_combos() returns frozenset-based (file_ids, recipe) pairs."""
    empty_state.add_multi(
        source_file_ids=["F1", "F2"],
        source_dates=["2026-01-01", "2026-01-02"],
        source_users=["U1", "U2"],
        recipe="collage",
        effects=[],
        processed_date="2026-03-26",
    )
    combos = empty_state.processed_combos()
    assert (frozenset({"F1", "F2"}), "collage") in combos


def test_processed_combos_order_independent(empty_state):
    """(F1,F2) and (F2,F1) should resolve to the same combo."""
    empty_state.add_multi(
        source_file_ids=["F1", "F2"],
        source_dates=["2026-01-01", "2026-01-02"],
        source_users=["U1", "U2"],
        recipe="collage",
        effects=[],
        processed_date="2026-03-26",
    )
    combos = empty_state.processed_combos()
    # Both orderings should be the same frozenset key
    assert (frozenset({"F2", "F1"}), "collage") in combos
    assert len(combos) == 1


def test_old_add_still_works(empty_state):
    """Old add() with singular fields wraps to lists internally."""
    empty_state.add(
        source_file_id="F_LEGACY",
        source_date="2026-01-10",
        source_user="U_LEGACY",
        recipe="legacy-recipe",
        effects=["vhs"],
        processed_date="2026-03-26",
    )
    entry = empty_state.processed[0]
    assert entry.source_file_ids == ["F_LEGACY"]
    assert entry.source_dates == ["2026-01-10"]
    assert entry.source_users == ["U_LEGACY"]


def test_processed_pairs_backward_compat(empty_state):
    """processed_pairs() still works for single-source entries added via add()."""
    empty_state.add(
        source_file_id="F_SINGLE",
        source_date="2026-01-15",
        source_user="U_SINGLE",
        recipe="single-recipe",
        effects=[],
        processed_date="2026-03-26",
    )
    pairs = empty_state.processed_pairs()
    assert ("F_SINGLE", "single-recipe") in pairs
