"""Tests for Slack source scraping and posting."""

from unittest.mock import MagicMock, patch
import pytest
from PIL import Image

from sparagmos.slack_source import (
    find_channel_id,
    fetch_image_files,
    pick_random_image,
    download_image,
)
from sparagmos.slack_post import format_provenance, post_result
from sparagmos.pipeline import PipelineResult


def _mock_conversations_list(channels, cursor=None):
    """Create a mock conversations_list response."""
    return {
        "channels": channels,
        "response_metadata": {"next_cursor": cursor or ""},
    }


def _mock_conversations_history(messages, cursor=None):
    """Create a mock conversations_history response."""
    return {
        "messages": messages,
        "response_metadata": {"next_cursor": cursor or ""},
    }


def test_find_channel_id():
    client = MagicMock()
    client.conversations_list.return_value = _mock_conversations_list(
        [{"name": "image-gen", "id": "C123"}]
    )
    assert find_channel_id(client, "image-gen") == "C123"


def test_find_channel_id_not_found():
    client = MagicMock()
    client.conversations_list.return_value = _mock_conversations_list(
        [{"name": "other", "id": "C999"}]
    )
    assert find_channel_id(client, "image-gen") is None


def test_fetch_image_files():
    client = MagicMock()
    client.conversations_history.return_value = _mock_conversations_history([
        {
            "ts": "1000.0",
            "user": "U123",
            "files": [
                {
                    "id": "F1",
                    "mimetype": "image/png",
                    "url_private_download": "https://files.slack.com/F1.png",
                    "name": "art.png",
                    "timestamp": 1000,
                },
            ],
        },
        {
            "ts": "2000.0",
            "user": "U456",
            "text": "just chatting, no files",
        },
        {
            "ts": "3000.0",
            "user": "U789",
            "files": [
                {
                    "id": "F2",
                    "mimetype": "application/pdf",
                    "url_private_download": "https://files.slack.com/F2.pdf",
                    "name": "doc.pdf",
                    "timestamp": 3000,
                },
            ],
        },
    ])
    files = fetch_image_files(client, "C123")
    # Should only include image files, not PDFs
    assert len(files) == 1
    assert files[0]["id"] == "F1"


def test_pick_random_image_excludes_processed():
    files = [
        {"id": "F1", "user": "U1", "timestamp": 1000},
        {"id": "F2", "user": "U2", "timestamp": 2000},
        {"id": "F3", "user": "U3", "timestamp": 3000},
    ]
    processed_pairs = {("F1", "recipe-a"), ("F2", "recipe-a")}
    result = pick_random_image(files, "recipe-a", processed_pairs, seed=42)
    assert result["id"] == "F3"


def test_pick_random_image_all_processed_with_recipe():
    files = [
        {"id": "F1", "user": "U1", "timestamp": 1000},
    ]
    processed_pairs = {("F1", "recipe-a")}
    result = pick_random_image(files, "recipe-a", processed_pairs, seed=42)
    assert result is None


def test_pick_random_image_allows_different_recipe():
    files = [
        {"id": "F1", "user": "U1", "timestamp": 1000},
    ]
    processed_pairs = {("F1", "recipe-a")}
    result = pick_random_image(files, "recipe-b", processed_pairs, seed=42)
    assert result["id"] == "F1"


# --- Slack posting tests ---


def test_format_provenance():
    steps = [
        {"effect": "deepdream", "description": "Neural hallucination"},
        {"effect": "channel_shift", "description": "RGB offset"},
        {"effect": "jpeg_destroy", "description": "Generational loss"},
    ]
    result = PipelineResult(
        image=Image.new("RGB", (64, 64)),
        recipe_name="Dionysian Rite",
        steps=steps,
    )
    source = {"user": "U123", "date": "2026-01-15"}
    text = format_provenance(result, source, channel_name="image-gen")
    assert "Dionysian Rite" in text
    assert "deepdream" in text
    assert "channel_shift" in text
    assert "jpeg_destroy" in text
    assert "→" in text
    assert "#image-gen" in text


def test_post_result_calls_upload(tmp_path):
    client = MagicMock()
    client.files_upload_v2.return_value = {"ok": True}

    img = Image.new("RGB", (64, 64))
    result = PipelineResult(
        image=img,
        recipe_name="Test Recipe",
        steps=[{"effect": "dummy", "description": "test"}],
    )
    source = {"user": "U123", "date": "2026-01-15"}

    post_result(client, "C456", result, source, "image-gen", tmp_path)

    client.files_upload_v2.assert_called_once()
    call_kwargs = client.files_upload_v2.call_args[1]
    assert call_kwargs["channel"] == "C456"
    assert "initial_comment" in call_kwargs
    assert "Test Recipe" in call_kwargs["initial_comment"]
