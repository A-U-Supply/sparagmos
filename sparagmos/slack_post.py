"""Post processed images to Slack."""

from __future__ import annotations

import logging
from pathlib import Path

from PIL import Image
from slack_sdk import WebClient

from sparagmos.pipeline import PipelineResult

logger = logging.getLogger(__name__)


def format_provenance(
    result: PipelineResult,
    source: dict,
    channel_name: str = "image-gen",
) -> str:
    """Format the provenance text for the Slack message.

    Args:
        result: Pipeline result with recipe name and step metadata.
        source: Source image metadata (user, date).
        channel_name: Source channel name for attribution.

    Returns:
        Formatted provenance string for initial_comment.
    """
    chain = " → ".join(step["effect"] for step in result.steps)
    user = source.get("user", "unknown")
    date = source.get("date", "unknown")

    return (
        f"~ {result.recipe_name}\n"
        f"{chain}\n"
        f"source: image by <@{user}> in #{channel_name} ({date})"
    )


def post_result(
    client: WebClient,
    channel_id: str,
    result: PipelineResult,
    source: dict,
    source_channel_name: str,
    temp_dir: Path,
) -> str:
    """Post a processed image to Slack as a single message.

    Uses files_upload_v2 with initial_comment to combine image and
    text in one message (no threads).

    Args:
        client: Slack WebClient.
        channel_id: Target channel ID (#img-junkyard).
        result: Pipeline result with image and metadata.
        source: Source image metadata.
        source_channel_name: Name of source channel for attribution.
        temp_dir: Temp directory for saving the image file.

    Returns:
        Message timestamp of the posted message.
    """
    comment = format_provenance(result, source, source_channel_name)

    # Save image to temp file for upload
    image_path = temp_dir / "sparagmos_output.png"
    result.image.save(image_path, "PNG")

    logger.info("Posting to channel %s with comment:\n%s", channel_id, comment)

    response = client.files_upload_v2(
        channel=channel_id,
        file=str(image_path),
        filename="sparagmos.png",
        initial_comment=comment,
    )

    return response.get("ts", "")
