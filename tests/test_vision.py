"""Tests for Llama Vision integration."""

from unittest.mock import MagicMock, patch
from PIL import Image
import pytest

from sparagmos.vision import analyze_image, parse_vision_response


def test_parse_vision_response_extracts_objects():
    raw = (
        "The image contains a face in the upper-left quadrant, "
        "a landscape with mountains in the background, "
        "and text overlay reading 'hello world' at the bottom."
    )
    parsed = parse_vision_response(raw)
    assert isinstance(parsed, dict)
    assert "description" in parsed
    assert parsed["description"] == raw


def test_parse_vision_response_empty():
    parsed = parse_vision_response("")
    assert parsed["description"] == ""


@patch("huggingface_hub.InferenceClient")
def test_analyze_image_calls_api(mock_client_cls):
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client
    mock_client.chat_completion.return_value = MagicMock(
        choices=[MagicMock(message=MagicMock(content="A beautiful landscape"))]
    )

    img = Image.new("RGB", (64, 64))
    result = analyze_image(img, token="fake-token")

    assert result["description"] == "A beautiful landscape"
    mock_client.chat_completion.assert_called_once()
