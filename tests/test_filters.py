"""Tests for image filtering and weighted sampling."""

from __future__ import annotations

import random
import time
from pathlib import Path
from unittest.mock import patch

import pytest

from sparagmos.slack_source import filter_images, weighted_sample
from sparagmos.state import State


# ── Helpers ──────────────────────────────────────────────────────────


def _make_images(n: int, base_ts: float = 1_700_000_000) -> list[dict]:
    """Create n fake image dicts with distinct IDs, users, timestamps."""
    return [
        {
            "id": f"F{i:03d}",
            "mimetype": "image/png",
            "url": f"https://files.slack.com/F{i:03d}.png",
            "permalink": f"https://example.slack.com/files/U{i:03d}/F{i:03d}/img.png",
            "name": f"img{i}.png",
            "user": f"U{i:03d}",
            "timestamp": base_ts + i * 86400,  # each image 1 day apart
        }
        for i in range(n)
    ]


def _make_state(tmp_path: Path, entries: list[dict] | None = None) -> State:
    """Create a State with pre-populated entries."""
    state = State(tmp_path / "state.json")
    if entries:
        for e in entries:
            state.add_multi(
                source_file_ids=e.get("file_ids", [e["file_id"]]),
                source_dates=e.get("dates", ["2026-01-01"]),
                source_users=e.get("users", ["U000"]),
                recipe=e["recipe"],
                effects=e.get("effects", ["invert"]),
                processed_date="2026-01-01",
            )
    return state


# ── No-filter passthrough ────────────────────────────────────────────


def test_no_filters_returns_all():
    images = _make_images(5)
    result = filter_images(images)
    assert len(result) == 5


def test_no_filters_does_not_mutate_input():
    images = _make_images(3)
    original_ids = [img["id"] for img in images]
    filter_images(images)
    assert [img["id"] for img in images] == original_ids


# ── Poster filter ────────────────────────────────────────────────────


def test_poster_filter_keeps_matching():
    images = _make_images(5)
    result = filter_images(images, poster="U002")
    assert len(result) == 1
    assert result[0]["id"] == "F002"


def test_poster_filter_no_match():
    images = _make_images(5)
    result = filter_images(images, poster="U999")
    assert result == []


# ── Age filters ──────────────────────────────────────────────────────


@pytest.fixture
def now():
    """Fixed 'now' for age tests — 2026-01-15 00:00:00 UTC."""
    return 1_736_899_200.0


def _images_with_ages(now: float) -> list[dict]:
    """Create images at specific ages relative to *now*."""
    day = 86400
    return [
        {"id": "F_12h", "user": "U1", "timestamp": now - 12 * 3600},
        {"id": "F_3d", "user": "U1", "timestamp": now - 3 * day},
        {"id": "F_10d", "user": "U1", "timestamp": now - 10 * day},
        {"id": "F_45d", "user": "U1", "timestamp": now - 45 * day},
        {"id": "F_100d", "user": "U1", "timestamp": now - 100 * day},
        {"id": "F_150d", "user": "U1", "timestamp": now - 150 * day},
        {"id": "F_250d", "user": "U1", "timestamp": now - 250 * day},
        {"id": "F_400d", "user": "U1", "timestamp": now - 400 * day},
        {"id": "F_800d", "user": "U1", "timestamp": now - 800 * day},
    ]


@patch("sparagmos.slack_source.time.time")
def test_age_24h(mock_time, now):
    mock_time.return_value = now
    images = _images_with_ages(now)
    result = filter_images(images, age="24h")
    assert [img["id"] for img in result] == ["F_12h"]


@patch("sparagmos.slack_source.time.time")
def test_age_7d(mock_time, now):
    mock_time.return_value = now
    images = _images_with_ages(now)
    result = filter_images(images, age="7d")
    assert set(img["id"] for img in result) == {"F_12h", "F_3d"}


@patch("sparagmos.slack_source.time.time")
def test_age_30d(mock_time, now):
    mock_time.return_value = now
    images = _images_with_ages(now)
    result = filter_images(images, age="30d")
    assert set(img["id"] for img in result) == {"F_12h", "F_3d", "F_10d"}


@patch("sparagmos.slack_source.time.time")
def test_age_1_3mo(mock_time, now):
    mock_time.return_value = now
    images = _images_with_ages(now)
    result = filter_images(images, age="1-3mo")
    # 1-3 months = 30-90 days
    assert set(img["id"] for img in result) == {"F_45d"}


@patch("sparagmos.slack_source.time.time")
def test_age_3_6mo(mock_time, now):
    mock_time.return_value = now
    images = _images_with_ages(now)
    result = filter_images(images, age="3-6mo")
    # 3-6 months = 90-180 days
    assert set(img["id"] for img in result) == {"F_100d", "F_150d"}


@patch("sparagmos.slack_source.time.time")
def test_age_6_12mo(mock_time, now):
    mock_time.return_value = now
    images = _images_with_ages(now)
    result = filter_images(images, age="6-12mo")
    # 6-12 months = 180-360 days
    assert set(img["id"] for img in result) == {"F_250d"}


@patch("sparagmos.slack_source.time.time")
def test_age_1y_plus(mock_time, now):
    mock_time.return_value = now
    images = _images_with_ages(now)
    result = filter_images(images, age="1y+")
    # Older than 365 days
    assert set(img["id"] for img in result) == {"F_400d", "F_800d"}


@patch("sparagmos.slack_source.time.time")
def test_age_2y_plus(mock_time, now):
    mock_time.return_value = now
    images = _images_with_ages(now)
    result = filter_images(images, age="2y+")
    # Older than 730 days
    assert set(img["id"] for img in result) == {"F_800d"}


def test_age_oldest50():
    """oldest50 returns up to 50 oldest images regardless of time.time()."""
    images = _make_images(60)
    result = filter_images(images, age="oldest50")
    assert len(result) == 50
    # Should be sorted ascending by timestamp
    assert result[0]["id"] == "F000"
    assert result[-1]["id"] == "F049"


def test_age_oldest50_fewer_than_50():
    images = _make_images(10)
    result = filter_images(images, age="oldest50")
    assert len(result) == 10


# ── Freshness filters ────────────────────────────────────────────────


def test_freshness_prefer_fresh_recipe(tmp_path):
    images = _make_images(4)
    state = _make_state(tmp_path, [
        {"file_id": "F000", "recipe": "recipe-a"},
        {"file_id": "F001", "recipe": "recipe-a"},
    ])
    result = filter_images(
        images, freshness="prefer_fresh_recipe", recipe="recipe-a", state=state,
    )
    assert len(result) == 4  # no filtering, just weighting
    weights = {img["id"]: img["_weight"] for img in result}
    assert weights["F000"] == 1.0  # used with recipe-a
    assert weights["F001"] == 1.0
    assert weights["F002"] == 3.0  # fresh for recipe-a
    assert weights["F003"] == 3.0


def test_freshness_only_fresh_recipe(tmp_path):
    images = _make_images(4)
    state = _make_state(tmp_path, [
        {"file_id": "F000", "recipe": "recipe-a"},
        {"file_id": "F001", "recipe": "recipe-a"},
    ])
    result = filter_images(
        images, freshness="only_fresh_recipe", recipe="recipe-a", state=state,
    )
    assert set(img["id"] for img in result) == {"F002", "F003"}


def test_freshness_only_used_recipe(tmp_path):
    images = _make_images(4)
    state = _make_state(tmp_path, [
        {"file_id": "F000", "recipe": "recipe-a"},
        {"file_id": "F001", "recipe": "recipe-b"},
    ])
    result = filter_images(
        images, freshness="only_used_recipe", recipe="recipe-a", state=state,
    )
    assert [img["id"] for img in result] == ["F000"]


def test_freshness_prefer_untouched(tmp_path):
    images = _make_images(4)
    state = _make_state(tmp_path, [
        {"file_id": "F000", "recipe": "recipe-a"},
        {"file_id": "F002", "recipe": "recipe-b"},
    ])
    result = filter_images(
        images, freshness="prefer_untouched", state=state,
    )
    assert len(result) == 4
    weights = {img["id"]: img["_weight"] for img in result}
    assert weights["F000"] == 1.0  # used
    assert weights["F001"] == 3.0  # untouched
    assert weights["F002"] == 1.0  # used
    assert weights["F003"] == 3.0  # untouched


def test_freshness_only_untouched(tmp_path):
    images = _make_images(4)
    state = _make_state(tmp_path, [
        {"file_id": "F000", "recipe": "recipe-a"},
        {"file_id": "F002", "recipe": "recipe-b"},
    ])
    result = filter_images(
        images, freshness="only_untouched", state=state,
    )
    assert set(img["id"] for img in result) == {"F001", "F003"}


def test_freshness_only_veterans(tmp_path):
    images = _make_images(4)
    # F000 used with 3 distinct recipes — qualifies as veteran
    # F001 used with 2 distinct recipes — does not qualify
    state = _make_state(tmp_path, [
        {"file_id": "F000", "recipe": "recipe-a"},
        {"file_id": "F000", "recipe": "recipe-b"},
        {"file_id": "F000", "recipe": "recipe-c"},
        {"file_id": "F001", "recipe": "recipe-a"},
        {"file_id": "F001", "recipe": "recipe-b"},
    ])
    result = filter_images(
        images, freshness="only_veterans", state=state,
    )
    assert [img["id"] for img in result] == ["F000"]


def test_only_veterans_fallback_to_weights(tmp_path):
    """When no images meet the veteran threshold, fall back to weighting."""
    images = _make_images(3)
    # F000 used with 2 recipes (below threshold), F001 with 1, F002 with 0
    state = _make_state(tmp_path, [
        {"file_id": "F000", "recipe": "recipe-a"},
        {"file_id": "F000", "recipe": "recipe-b"},
        {"file_id": "F001", "recipe": "recipe-a"},
    ])
    result = filter_images(images, freshness="only_veterans", state=state)
    # All images kept, but most-used gets highest weight
    assert len(result) == 3
    weights = {img["id"]: img["_weight"] for img in result}
    assert weights["F000"] > weights["F001"] > weights["F002"]


def test_only_fresh_recipe_fallback_to_weights(tmp_path):
    """When all images have been used with this recipe, fall back to weighting."""
    images = _make_images(2)
    state = _make_state(tmp_path, [
        {"file_id": "F000", "recipe": "recipe-a"},
        {"file_id": "F001", "recipe": "recipe-a"},
    ])
    result = filter_images(
        images, freshness="only_fresh_recipe", recipe="recipe-a", state=state,
    )
    # All kept (no fresh ones exist), but unused-with-recipe gets higher weight
    # Here both are used, so weights should still be assigned (all equal/low)
    assert len(result) == 2


def test_only_untouched_fallback_to_weights(tmp_path):
    """When all images have been used, fall back to weighting."""
    images = _make_images(2)
    state = _make_state(tmp_path, [
        {"file_id": "F000", "recipe": "recipe-a"},
        {"file_id": "F001", "recipe": "recipe-a"},
    ])
    result = filter_images(images, freshness="only_untouched", state=state)
    assert len(result) == 2


def test_only_used_recipe_fallback_to_weights(tmp_path):
    """When no images have been used with this recipe, fall back to weighting."""
    images = _make_images(2)
    state = _make_state(tmp_path, [
        {"file_id": "F000", "recipe": "recipe-b"},
    ])
    result = filter_images(
        images, freshness="only_used_recipe", recipe="recipe-a", state=state,
    )
    assert len(result) == 2


def test_freshness_without_state():
    """Freshness filters degrade gracefully when state is None."""
    images = _make_images(5)
    result = filter_images(images, freshness="only_untouched")
    assert len(result) == 5  # returns all unfiltered


def test_freshness_without_recipe():
    """Recipe-aware freshness modes return all when recipe is None."""
    images = _make_images(3)
    state = _make_state(Path("/nonexistent"))  # won't be used
    result = filter_images(images, freshness="only_fresh_recipe", state=state)
    assert len(result) == 3


# ── Filter composition ───────────────────────────────────────────────


@patch("sparagmos.slack_source.time.time")
def test_poster_plus_age(mock_time, now):
    mock_time.return_value = now
    day = 86400
    images = [
        {"id": "F1", "user": "U_ALICE", "timestamp": now - 2 * day},
        {"id": "F2", "user": "U_ALICE", "timestamp": now - 40 * day},
        {"id": "F3", "user": "U_BOB", "timestamp": now - 2 * day},
    ]
    result = filter_images(images, poster="U_ALICE", age="7d")
    assert len(result) == 1
    assert result[0]["id"] == "F1"


@patch("sparagmos.slack_source.time.time")
def test_age_plus_freshness(mock_time, now, tmp_path):
    mock_time.return_value = now
    day = 86400
    images = [
        {"id": "F1", "user": "U1", "timestamp": now - 2 * day},
        {"id": "F2", "user": "U1", "timestamp": now - 3 * day},
        {"id": "F3", "user": "U1", "timestamp": now - 40 * day},  # outside 30d
    ]
    state = _make_state(tmp_path, [
        {"file_id": "F1", "recipe": "recipe-a"},
    ])
    result = filter_images(
        images, age="30d", freshness="only_fresh_recipe",
        recipe="recipe-a", state=state,
    )
    assert [img["id"] for img in result] == ["F2"]


@patch("sparagmos.slack_source.time.time")
def test_all_three_filters(mock_time, now, tmp_path):
    mock_time.return_value = now
    day = 86400
    images = [
        {"id": "F1", "user": "U_ALICE", "timestamp": now - 2 * day},
        {"id": "F2", "user": "U_ALICE", "timestamp": now - 5 * day},
        {"id": "F3", "user": "U_ALICE", "timestamp": now - 40 * day},
        {"id": "F4", "user": "U_BOB", "timestamp": now - 2 * day},
    ]
    state = _make_state(tmp_path, [
        {"file_id": "F1", "recipe": "recipe-x"},
    ])
    result = filter_images(
        images, poster="U_ALICE", age="30d",
        freshness="only_fresh_recipe", recipe="recipe-x", state=state,
    )
    assert [img["id"] for img in result] == ["F2"]


# ── Edge cases ───────────────────────────────────────────────────────


def test_oldest50_plus_only_veterans_rejected():
    """oldest50 selects least-processed images; only_veterans requires 3+ recipes.

    These filters are contradictory — oldest images are the least likely to
    have been reused across many recipes.  Reject early with a clear message.
    """
    images = _make_images(5)
    state = _make_state(Path("/unused"))
    with pytest.raises(ValueError, match="oldest50.*only_veterans"):
        filter_images(images, age="oldest50", freshness="only_veterans", state=state)


def test_empty_image_list():
    result = filter_images([])
    assert result == []


def test_empty_after_poster_filter():
    images = _make_images(3)
    result = filter_images(images, poster="NONEXISTENT")
    assert result == []


@patch("sparagmos.slack_source.time.time")
def test_missing_timestamp_treated_as_zero(mock_time, now):
    mock_time.return_value = now
    images = [{"id": "F1", "user": "U1"}]  # no timestamp key
    result = filter_images(images, age="1y+")
    # timestamp defaults to 0, which is > 1y old → included
    assert len(result) == 1


def test_unknown_age_returns_all():
    images = _make_images(3)
    result = filter_images(images, age="bogus")
    assert len(result) == 3


def test_unknown_freshness_returns_all():
    images = _make_images(3)
    result = filter_images(images, freshness="bogus")
    assert len(result) == 3


# ── weighted_sample ──────────────────────────────────────────────────


def test_weighted_sample_respects_weights():
    """Heavily-weighted image should be selected far more often."""
    images = [
        {"id": "heavy", "_weight": 100.0},
        {"id": "light", "_weight": 0.01},
    ]
    rng = random.Random(42)
    results = [weighted_sample(images, 1, rng)[0]["id"] for _ in range(100)]
    heavy_count = results.count("heavy")
    assert heavy_count > 80  # should dominate


def test_weighted_sample_returns_n_distinct():
    images = [{"id": f"F{i}", "_weight": 1.0} for i in range(20)]
    rng = random.Random(42)
    result = weighted_sample(images, 5, rng)
    assert len(result) == 5
    assert len(set(img["id"] for img in result)) == 5


def test_weighted_sample_default_weight():
    """Images without _weight get weight 1.0."""
    images = [{"id": f"F{i}"} for i in range(10)]
    rng = random.Random(42)
    result = weighted_sample(images, 3, rng)
    assert len(result) == 3


def test_weighted_sample_more_than_available():
    """Requesting more than available returns what's possible."""
    images = [{"id": "F0", "_weight": 1.0}, {"id": "F1", "_weight": 1.0}]
    rng = random.Random(42)
    result = weighted_sample(images, 5, rng)
    assert len(result) == 2


# ── Rating-weighted recipe selection ─────────────────────────────────


def test_pick_weighted_recipe_with_ratings(tmp_path):
    from sparagmos.cli import _pick_weighted_recipe

    # Use the real nested dict format from ratings.json
    ratings_path = tmp_path / "ratings.json"
    ratings_path.write_text(
        '{"great": {"up": 10, "down": 2, "score": 8, "last_voted": "2026-04-03"},'
        ' "bad": {"up": 0, "down": 4, "score": -4, "last_voted": "2026-04-03"},'
        ' "ok": {"up": 1, "down": 1, "score": 0, "last_voted": "2026-04-03"}}'
    )

    counts: dict[str, int] = {"great": 0, "bad": 0, "ok": 0}
    for i in range(1000):
        rng = random.Random(i)
        slug = _pick_weighted_recipe(rng, ["great", "bad", "ok"], tmp_path)
        counts[slug] += 1

    # great: weight=13, bad: weight=1, ok: weight=5 → great should dominate
    assert counts["great"] > counts["ok"] > counts["bad"]


def test_pick_weighted_recipe_no_ratings_file(tmp_path):
    from sparagmos.cli import _pick_weighted_recipe

    rng = random.Random(42)
    slug = _pick_weighted_recipe(rng, ["a", "b", "c"], tmp_path)
    assert slug in {"a", "b", "c"}


def test_pick_weighted_recipe_empty_ratings(tmp_path):
    from sparagmos.cli import _pick_weighted_recipe

    (tmp_path / "ratings.json").write_text("{}")
    rng = random.Random(42)
    slug = _pick_weighted_recipe(rng, ["a", "b", "c"], tmp_path)
    assert slug in {"a", "b", "c"}


# ── Rating filter ──────────────────────────────────────────────────────


def test_filter_by_rating_top():
    from sparagmos.cli import _filter_by_rating

    ratings = {"a": 5, "b": 3, "c": 1, "d": -2}
    result = _filter_by_rating(["a", "b", "c", "d", "e"], "top", ratings)
    assert set(result) == {"a", "b"}


def test_filter_by_rating_positive():
    from sparagmos.cli import _filter_by_rating

    ratings = {"a": 5, "b": 3, "c": 1, "d": -2}
    result = _filter_by_rating(["a", "b", "c", "d", "e"], "positive", ratings)
    assert set(result) == {"a", "b", "c"}


def test_filter_by_rating_unrated():
    from sparagmos.cli import _filter_by_rating

    ratings = {"a": 5, "b": 0, "d": -2}
    result = _filter_by_rating(["a", "b", "c", "d"], "unrated", ratings)
    # b has score 0, c is absent from ratings → both unrated
    assert set(result) == {"b", "c"}


def test_filter_by_rating_underdogs():
    from sparagmos.cli import _filter_by_rating

    ratings = {"a": 5, "b": -1, "c": -3}
    result = _filter_by_rating(["a", "b", "c", "d"], "underdogs", ratings)
    assert set(result) == {"b", "c"}


def test_filter_by_rating_combined():
    from sparagmos.cli import _filter_by_rating

    ratings = {"a": 5, "b": -1, "c": 0}
    result = _filter_by_rating(["a", "b", "c", "d"], "top,underdogs", ratings)
    # top: a (5>=3), underdogs: b (-1<0)
    assert set(result) == {"a", "b"}


def test_filter_by_rating_empty_returns_all():
    from sparagmos.cli import _filter_by_rating

    ratings = {"a": 5}
    # If filter matches nothing, fall back to full list
    result = _filter_by_rating(["x", "y", "z"], "top", ratings)
    assert result == ["x", "y", "z"]
