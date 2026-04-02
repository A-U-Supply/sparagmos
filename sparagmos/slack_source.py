"""Scrape random images from a Slack channel."""

from __future__ import annotations

import logging
import random
import re
from urllib.parse import urlparse
from typing import Any

import requests
from slack_sdk import WebClient

logger = logging.getLogger(__name__)

IMAGE_MIMETYPES = {"image/png", "image/jpeg", "image/gif", "image/webp"}

SLACK_HOSTS = {"files.slack.com", "files-origin.slack.com"}

# Matches Slack permalink URLs like:
# https://WORKSPACE.slack.com/files/USER_ID/FILE_ID/filename.ext
_SLACK_PERMALINK_RE = re.compile(
    r"https?://[^/]+\.slack\.com/files/[^/]+/([A-Z0-9]+)"
)


def find_channel_id(client: WebClient, channel_name: str) -> str | None:
    """Find a Slack channel ID by name.

    Args:
        client: Slack WebClient.
        channel_name: Channel name (with or without #).

    Returns:
        Channel ID string, or None if not found.
    """
    name = channel_name.lstrip("#")
    cursor = None
    while True:
        kwargs: dict[str, Any] = {"types": "public_channel", "limit": 200}
        if cursor:
            kwargs["cursor"] = cursor
        resp = client.conversations_list(**kwargs)
        for ch in resp["channels"]:
            if ch["name"] == name:
                return ch["id"]
        cursor = resp.get("response_metadata", {}).get("next_cursor")
        if not cursor:
            return None


def fetch_image_files(client: WebClient, channel_id: str) -> list[dict[str, Any]]:
    """Fetch all image file attachments from a channel's history.

    Args:
        client: Slack WebClient.
        channel_id: Channel ID to scrape.

    Returns:
        List of file metadata dicts (id, mimetype, url, user, timestamp).
    """
    image_files = []
    cursor = None
    while True:
        kwargs: dict[str, Any] = {"channel": channel_id, "limit": 200}
        if cursor:
            kwargs["cursor"] = cursor
        resp = client.conversations_history(**kwargs)

        for msg in resp["messages"]:
            for file_info in msg.get("files", []):
                if file_info.get("mimetype", "") in IMAGE_MIMETYPES:
                    image_files.append({
                        "id": file_info["id"],
                        "mimetype": file_info["mimetype"],
                        "url": file_info.get("url_private_download", ""),
                        "permalink": file_info.get("permalink", ""),
                        "name": file_info.get("name", ""),
                        "user": msg.get("user", "unknown"),
                        "timestamp": file_info.get("timestamp", 0),
                    })

        cursor = resp.get("response_metadata", {}).get("next_cursor")
        if not cursor:
            break

    logger.info("Found %d image files in channel", len(image_files))
    return image_files


def pick_random_image(
    files: list[dict[str, Any]],
    recipe_slug: str,
    processed_pairs: set[tuple[str, str]],
    seed: int,
) -> dict[str, Any] | None:
    """Pick a random image that hasn't been processed with this recipe.

    Args:
        files: List of file metadata dicts.
        recipe_slug: Current recipe slug to check against.
        processed_pairs: Set of (file_id, recipe) pairs already processed.
        seed: RNG seed.

    Returns:
        File metadata dict, or None if all files processed with this recipe.
    """
    available = [f for f in files if (f["id"], recipe_slug) not in processed_pairs]

    if not available:
        logger.warning("All %d images processed with recipe %s", len(files), recipe_slug)
        return None

    rng = random.Random(seed)
    return rng.choice(available)


def pick_random_images(
    files: list[dict[str, Any]],
    recipe_slug: str,
    n: int,
    processed_combos: set[tuple[frozenset[str], str]],
    seed: int,
    max_attempts: int = 100,
) -> list[dict[str, Any]] | None:
    """Pick n distinct random images whose combination hasn't been used.

    Args:
        files: List of file metadata dicts.
        recipe_slug: Current recipe slug.
        n: Number of images to pick.
        processed_combos: Set of (frozenset(file_ids), recipe) already done.
        seed: RNG seed.
        max_attempts: Max random attempts before giving up.

    Returns:
        List of n file metadata dicts, or None if impossible.
    """
    if len(files) < n:
        return None

    rng = random.Random(seed)
    for _ in range(max_attempts):
        selected = rng.sample(files, n)
        combo = (frozenset(f["id"] for f in selected), recipe_slug)
        if combo not in processed_combos:
            return selected

    return None


def download_image(url: str, token: str, timeout: int = 30) -> bytes:
    """Download an image from Slack, preserving auth through redirects.

    Args:
        url: Slack file URL (url_private_download).
        token: Slack bot token.
        timeout: Request timeout in seconds.

    Returns:
        Image bytes.

    Raises:
        requests.HTTPError: On non-200 response.
        ValueError: If response is not an image.
    """
    headers = {"Authorization": f"Bearer {token}"}
    max_redirects = 5
    for _ in range(max_redirects):
        resp = requests.get(url, headers=headers, timeout=timeout, allow_redirects=False)
        if resp.status_code in (301, 302, 303, 307, 308):
            url = resp.headers["Location"]
            continue
        resp.raise_for_status()

        content_type = resp.headers.get("Content-Type", "")
        if not content_type.startswith("image/"):
            raise ValueError(
                f"Expected image content, got {content_type!r}. "
                "Slack may have returned a login page."
            )
        return resp.content

    raise requests.TooManyRedirects(f"Too many redirects downloading {url}")


def download_url(url: str, slack_token: str | None = None, timeout: int = 30) -> bytes:
    """Download an image from a URL.

    For Slack file URLs (files.slack.com), uses Bearer token auth via
    the existing download_image function. For all other URLs, makes a
    plain GET request.

    Args:
        url: Image URL to download.
        slack_token: Slack bot token (required for Slack file URLs).
        timeout: Request timeout in seconds.

    Returns:
        Image bytes.

    Raises:
        ValueError: If URL scheme is not http/https, response is not an
            image, or a Slack URL is given without a token.
        requests.HTTPError: On non-200 response.
    """
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"URL must be http or https, got {parsed.scheme!r}")

    # Slack permalink URLs (workspace.slack.com/files/USER/FILE_ID/name)
    # need to be resolved via the API to get the actual download URL
    permalink_match = _SLACK_PERMALINK_RE.match(url)
    if permalink_match:
        if not slack_token:
            raise ValueError(
                f"Slack permalink URL requires a bot token: {url}"
            )
        file_id = permalink_match.group(1)
        client = WebClient(token=slack_token)
        resp = client.files_info(file=file_id)
        download_url_str = resp["file"].get("url_private_download", "")
        if not download_url_str:
            raise ValueError(
                f"Could not get download URL for Slack file {file_id}"
            )
        logger.info("Resolved Slack permalink %s -> %s", file_id, download_url_str)
        return download_image(download_url_str, slack_token, timeout=timeout)

    # Direct Slack file URLs (files.slack.com) need Bearer token auth
    if parsed.hostname in SLACK_HOSTS:
        if not slack_token:
            raise ValueError(
                f"Slack file URL requires a bot token: {url}"
            )
        return download_image(url, slack_token, timeout=timeout)

    # Public URL — plain GET
    resp = requests.get(
        url,
        timeout=timeout,
        headers={"User-Agent": "sparagmos/1.0"},
    )
    resp.raise_for_status()

    content_type = resp.headers.get("Content-Type", "")
    if not content_type.startswith("image/"):
        raise ValueError(
            f"Expected image content from {url}, got {content_type!r}"
        )
    return resp.content
