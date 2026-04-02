"""Post processed images to Slack."""

from __future__ import annotations

import logging
from pathlib import Path

from PIL import Image
from slack_sdk import WebClient

from sparagmos.pipeline import PipelineResult

logger = logging.getLogger(__name__)


def _annotate_step(step: dict) -> str:
    """Return an annotated effect label for a single pipeline step.

    Examples:
        ``{"effect": "blend", "images": ["a", "b"], "into": "canvas"}``
        → ``"blend(a,b→canvas)"``

        ``{"effect": "deepdream", "image": "a"}``
        → ``"deepdream(a)"``

        ``{"effect": "jpeg_destroy"}``
        → ``"jpeg_destroy"``
    """
    effect = step["effect"]
    if "images" in step and "into" in step:
        inputs = ",".join(step["images"])
        return f"{effect}({inputs}→{step['into']})"
    if "image" in step:
        return f"{effect}({step['image']})"
    return effect


def format_main_comment(result: PipelineResult) -> str:
    """Format the main Slack message: recipe name + annotated effect chain.

    Source attribution is posted separately in a thread reply.
    """
    chain = " → ".join(_annotate_step(step) for step in result.steps)
    return f"~ {result.recipe_name}\n{chain}"


def format_thread_reply(
    sources: list[dict],
    channel_name: str = "image-gen",
) -> str:
    """Format the thread reply with source attribution and permalink links.

    Args:
        sources: List of source dicts with 'display_name', 'date', and
            optional 'permalink' keys.
        channel_name: Source channel name for attribution.

    Returns:
        Formatted string for the thread reply text.
    """
    source_label = "source" if len(sources) == 1 else "sources"
    attributions = ", ".join(
        f"{s['display_name']} ({s.get('date', 'unknown')})" for s in sources
    )
    lines = [f"{source_label}: {attributions} in #{channel_name}"]

    permalinks = [s.get("permalink", "") for s in sources if s.get("permalink")]
    if permalinks:
        link_label = "original" if len(permalinks) == 1 else "originals"
        links = " · ".join(f"<{url}|view>" for url in permalinks)
        lines.append(f"{link_label}: {links}")

    return "\n".join(lines)


def resolve_display_name(client: WebClient, user_id: str) -> str:
    """Resolve a Slack user ID to a plain display name.

    Falls back to real_name, then the raw user_id on failure.
    """
    try:
        resp = client.users_info(user=user_id)
        profile = resp["user"]["profile"]
        return profile.get("display_name") or profile.get("real_name") or user_id
    except Exception:
        logger.warning("Failed to resolve display name for %s", user_id)
        return user_id


def post_result(
    client: WebClient,
    channel_id: str,
    result: PipelineResult,
    sources: list[dict],
    source_channel_name: str,
    temp_dir: Path,
) -> str:
    """Post a processed image to Slack with source info in a thread reply.

    Uploads the output image with a main comment (recipe + effects only),
    then posts source attribution and permalink links as a thread reply.

    Args:
        client: Slack WebClient.
        channel_id: Target channel ID (#img-junkyard).
        result: Pipeline result with image and metadata.
        sources: List of source metadata dicts (user, date, permalink).
        source_channel_name: Name of source channel for attribution.
        temp_dir: Temp directory for saving the image file.

    Returns:
        Message timestamp of the posted message.
    """
    comment = format_main_comment(result)

    # Resolve display names for source attribution (without mutating input)
    resolved_sources = [
        {**s, "display_name": resolve_display_name(client, s["user"])}
        for s in sources
    ]

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

    # Extract posted message timestamp via files.info API
    # (files_upload_v2 returns completeUploadExternal response which lacks share data)
    posted_ts = ""
    file_obj = response.get("file") or {}
    if not file_obj:
        files_list = response.get("files") or []
        if files_list:
            file_obj = files_list[0]
    file_id = file_obj.get("id", "")
    if file_id:
        try:
            info_resp = client.files_info(file=file_id)
            shares = info_resp.get("file", {}).get("shares", {}).get("public", {})
            channel_shares = shares.get(channel_id, [])
            if channel_shares:
                posted_ts = channel_shares[0].get("ts", "")
        except Exception:
            logger.warning("Failed to get file info for timestamp, skipping thread reply")

    # Post source attribution as a thread reply
    if posted_ts:
        thread_text = format_thread_reply(resolved_sources, source_channel_name)
        try:
            client.chat_postMessage(
                channel=channel_id,
                thread_ts=posted_ts,
                text=thread_text,
            )
        except Exception:
            logger.warning("Failed to post thread reply, continuing")

    return posted_ts
