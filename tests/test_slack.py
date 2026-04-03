"""Tests for Slack source scraping and posting."""

from unittest.mock import MagicMock, patch
import pytest
from PIL import Image

from sparagmos.slack_source import (
    find_channel_id,
    fetch_image_files,
    pick_random_image,
    pick_random_images,
    download_image,
    download_url,
)
from sparagmos.slack_post import post_result, format_main_comment, format_thread_reply, resolve_display_name
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


def test_pick_random_images_returns_n():
    files = [{"id": f"F{i}", "user": f"U{i}", "timestamp": i * 1000} for i in range(10)]
    result = pick_random_images(files, "recipe-a", 3, set(), seed=42)
    assert len(result) == 3
    ids = {f["id"] for f in result}
    assert len(ids) == 3  # all distinct


def test_pick_random_images_excludes_processed_combos():
    files = [
        {"id": "F1", "user": "U1", "timestamp": 1000},
        {"id": "F2", "user": "U2", "timestamp": 2000},
        {"id": "F3", "user": "U3", "timestamp": 3000},
    ]
    processed = {(frozenset(["F1", "F2"]), "recipe-a")}
    result = pick_random_images(files, "recipe-a", 2, processed, seed=42)
    if result is not None:
        ids = frozenset(f["id"] for f in result)
        assert ids != frozenset(["F1", "F2"])


def test_pick_random_images_not_enough_files():
    files = [{"id": "F1", "user": "U1", "timestamp": 1000}]
    result = pick_random_images(files, "recipe-a", 3, set(), seed=42)
    assert result is None


def test_pick_random_images_deterministic():
    files = [{"id": f"F{i}", "user": f"U{i}", "timestamp": i * 1000} for i in range(20)]
    r1 = pick_random_images(files, "recipe-a", 3, set(), seed=42)
    r2 = pick_random_images(files, "recipe-a", 3, set(), seed=42)
    assert [f["id"] for f in r1] == [f["id"] for f in r2]


# --- Slack posting tests ---


def test_post_result_uploads_with_main_comment_only(tmp_path):
    """Main message contains recipe + effects, no source info."""
    client = MagicMock()
    client.files_upload_v2.return_value = {
        "ok": True,
        "files": [{"id": "F999"}],
    }
    client.conversations_history.return_value = {
        "messages": [{"ts": "111.222", "files": [{"id": "F999"}]}],
    }
    client.users_info.return_value = {
        "user": {"profile": {"display_name": "brendan", "real_name": "Brendan"}}
    }

    img = Image.new("RGB", (64, 64))
    result = PipelineResult(
        image=img,
        recipe_name="Test Recipe",
        steps=[{"effect": "invert", "image": "a"}],
    )
    sources = [{"user": "U123", "date": "2026-01-15", "permalink": "https://link1"}]

    post_result(client, "C456", result, sources, "image-gen", tmp_path)

    call_kwargs = client.files_upload_v2.call_args[1]
    comment = call_kwargs["initial_comment"]
    assert "Test Recipe" in comment
    assert "invert" in comment
    # No source info in main comment
    assert "<@" not in comment
    assert "source" not in comment.lower()
    assert "http" not in comment


def test_post_result_matches_file_id_in_history(tmp_path):
    """Thread reply goes to the message matching our file ID, not just the latest."""
    client = MagicMock()
    client.files_upload_v2.return_value = {
        "ok": True,
        "files": [{"id": "F_OURS"}],
    }
    # Channel has other messages — ours is second, not first
    client.conversations_history.return_value = {
        "messages": [
            {"ts": "999.000", "text": "someone else's message"},
            {"ts": "888.000", "files": [{"id": "F_OURS"}]},
            {"ts": "777.000", "files": [{"id": "F_OLD"}]},
        ],
    }
    client.users_info.return_value = {
        "user": {"profile": {"display_name": "brendan", "real_name": "Brendan"}}
    }

    img = Image.new("RGB", (64, 64))
    result = PipelineResult(
        image=img,
        recipe_name="Test Recipe",
        steps=[{"effect": "invert", "image": "a"}],
    )
    sources = [{"user": "U123", "date": "2026-01-15", "permalink": "https://link1"}]

    post_result(client, "C456", result, sources, "image-gen", tmp_path)

    # History searched with limit=5
    client.conversations_history.assert_called_once_with(channel="C456", limit=5)

    # Thread reply goes to OUR message (888.000), not the latest (999.000)
    client.chat_postMessage.assert_called_once()
    reply_kwargs = client.chat_postMessage.call_args[1]
    assert reply_kwargs["thread_ts"] == "888.000"
    assert "brendan" in reply_kwargs["text"]
    assert "https://link1" in reply_kwargs["text"]


def test_post_result_no_thread_without_file_id(tmp_path):
    """If upload returns no file ID, skip the thread reply gracefully."""
    client = MagicMock()
    client.files_upload_v2.return_value = {"ok": True}
    client.users_info.return_value = {
        "user": {"profile": {"display_name": "brendan", "real_name": "Brendan"}}
    }

    img = Image.new("RGB", (64, 64))
    result = PipelineResult(
        image=img,
        recipe_name="Test Recipe",
        steps=[{"effect": "invert", "image": "a"}],
    )
    sources = [{"user": "U123", "date": "2026-01-15"}]

    post_result(client, "C456", result, sources, "image-gen", tmp_path)

    client.conversations_history.assert_not_called()
    client.chat_postMessage.assert_not_called()


# --- download_url tests ---


def _make_image_response(status_code=200, content_type="image/png"):
    """Create a mock response that looks like an image download."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.headers = {"Content-Type": content_type}
    resp.content = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
    resp.raise_for_status = MagicMock()
    return resp


@patch("sparagmos.slack_source.requests.get")
def test_download_url_public(mock_get):
    """Public URLs use plain GET without auth."""
    mock_get.return_value = _make_image_response()
    result = download_url("https://example.com/photo.png")
    assert len(result) > 0
    mock_get.assert_called_once()
    call_kwargs = mock_get.call_args
    assert "Authorization" not in call_kwargs.kwargs.get("headers", {})


@patch("sparagmos.slack_source.download_image")
def test_download_url_slack_delegates(mock_download_image):
    """Slack file URLs delegate to download_image with token."""
    mock_download_image.return_value = b"\x89PNG" + b"\x00" * 50
    result = download_url(
        "https://files.slack.com/T123/F456/img.png",
        slack_token="xoxb-test-token",
    )
    assert len(result) > 0
    mock_download_image.assert_called_once_with(
        "https://files.slack.com/T123/F456/img.png",
        "xoxb-test-token",
        timeout=30,
    )


@patch("sparagmos.slack_source.download_image")
@patch("sparagmos.slack_source.WebClient")
def test_download_url_slack_permalink(mock_client_cls, mock_download_image):
    """Slack permalink URLs resolve file ID via API then download."""
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client
    mock_client.files_info.return_value = {
        "file": {"url_private_download": "https://files.slack.com/real-download-url"}
    }
    mock_download_image.return_value = b"\x89PNG" + b"\x00" * 50

    result = download_url(
        "https://au-supply.slack.com/files/U03TD7FSUAE/F0AQB5F4HHT/image.jpg",
        slack_token="xoxb-test-token",
    )
    assert len(result) > 0
    mock_client.files_info.assert_called_once_with(file="F0AQB5F4HHT")
    mock_download_image.assert_called_once_with(
        "https://files.slack.com/real-download-url",
        "xoxb-test-token",
        timeout=30,
    )


def test_download_url_slack_permalink_without_token():
    """Slack permalink URLs without a token raise ValueError."""
    with pytest.raises(ValueError, match="requires a bot token"):
        download_url("https://au-supply.slack.com/files/U123/F456/img.png")


def test_download_url_slack_without_token():
    """Slack direct file URLs without a token raise ValueError."""
    with pytest.raises(ValueError, match="requires a bot token"):
        download_url("https://files.slack.com/T123/img.png")


def test_download_url_bad_scheme():
    """Non-http(s) URLs raise ValueError."""
    with pytest.raises(ValueError, match="http or https"):
        download_url("ftp://example.com/img.png")


@patch("sparagmos.slack_source.requests.get")
def test_download_url_non_image_rejected(mock_get):
    """Non-image responses raise ValueError."""
    mock_get.return_value = _make_image_response(content_type="text/html")
    with pytest.raises(ValueError, match="Expected image"):
        download_url("https://example.com/page.html")


# --- format_main_comment tests ---


def test_format_main_comment():
    steps = [
        {"effect": "deepdream", "image": "a"},
        {"effect": "blend", "images": ["a", "b"], "into": "canvas"},
        {"effect": "jpeg_destroy"},
    ]
    result = PipelineResult(
        image=Image.new("RGB", (64, 64)),
        recipe_name="Mosaic Dissolution",
        steps=steps,
    )
    text = format_main_comment(result)
    assert text == "~ Mosaic Dissolution\ndeepdream(a) → blend(a,b→canvas) → jpeg_destroy"


def test_format_main_comment_no_source_info():
    """Main comment must not contain user mentions, dates, or links."""
    steps = [{"effect": "invert", "image": "a"}]
    result = PipelineResult(
        image=Image.new("RGB", (64, 64)),
        recipe_name="Simple",
        steps=steps,
    )
    text = format_main_comment(result)
    assert "<@" not in text
    assert "source" not in text.lower()
    assert "original" not in text.lower()
    assert "http" not in text


# --- format_thread_reply tests ---


def test_format_thread_reply_multi():
    sources = [
        {"display_name": "brendan", "date": "2026-04-01", "permalink": "https://link1"},
        {"display_name": "jake", "date": "2026-03-30", "permalink": "https://link2"},
    ]
    text = format_thread_reply(sources, "image-gen")
    assert "sources: brendan (2026-04-01), jake (2026-03-30) in #image-gen" in text
    assert "originals: <https://link1|view> · <https://link2|view>" in text
    assert "<@" not in text  # no mentions


def test_format_thread_reply_single():
    sources = [
        {"display_name": "brendan", "date": "2026-04-01", "permalink": "https://link1"},
    ]
    text = format_thread_reply(sources, "image-gen")
    assert "source: brendan (2026-04-01) in #image-gen" in text
    assert "original: <https://link1|view>" in text


def test_format_thread_reply_no_permalink():
    sources = [{"display_name": "brendan", "date": "2026-04-01"}]
    text = format_thread_reply(sources, "image-gen")
    assert "source: brendan (2026-04-01) in #image-gen" in text
    assert "original" not in text


def test_resolve_display_name_uses_display_name():
    client = MagicMock()
    client.users_info.return_value = {
        "user": {"profile": {"display_name": "brendan", "real_name": "Brendan Smith"}}
    }
    assert resolve_display_name(client, "U123") == "brendan"
    client.users_info.assert_called_once_with(user="U123")


def test_resolve_display_name_falls_back_to_real_name():
    client = MagicMock()
    client.users_info.return_value = {
        "user": {"profile": {"display_name": "", "real_name": "Brendan Smith"}}
    }
    assert resolve_display_name(client, "U123") == "Brendan Smith"


def test_resolve_display_name_falls_back_to_user_id():
    client = MagicMock()
    client.users_info.side_effect = Exception("API error")
    assert resolve_display_name(client, "U123") == "U123"
