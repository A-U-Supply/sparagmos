"""Scrape random images from a Slack channel."""

from __future__ import annotations

import logging
import random
import re
import time
from collections import Counter
from urllib.parse import urlparse
from typing import TYPE_CHECKING, Any

import requests
from slack_sdk import WebClient

if TYPE_CHECKING:
    from sparagmos.state import State

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
                        "user": file_info.get("user") or msg.get("user", "unknown"),
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


def weighted_sample(
    images: list[dict[str, Any]],
    n: int,
    rng: random.Random,
    max_attempts: int = 200,
) -> list[dict[str, Any]]:
    """Sample n distinct images respecting ``_weight`` keys.

    Uses :func:`random.choices` (with replacement) then deduplicates,
    retrying until *n* distinct images are collected or *max_attempts*
    rounds are exhausted.

    Args:
        images: List of image dicts, each optionally carrying a ``_weight`` key.
        n: Number of distinct images to return.
        rng: Seeded random instance.
        max_attempts: Safety cap on retry rounds.

    Returns:
        List of *n* distinct image dicts (may be fewer if the pool is
        too small or attempts are exhausted).
    """
    weights = [img.get("_weight", 1.0) for img in images]
    selected: dict[str, dict[str, Any]] = {}

    for _ in range(max_attempts):
        if len(selected) >= n:
            break
        picks = rng.choices(images, weights=weights, k=n)
        for pick in picks:
            if pick["id"] not in selected:
                selected[pick["id"]] = pick
            if len(selected) >= n:
                break

    return list(selected.values())[:n]


def pick_random_images(
    files: list[dict[str, Any]],
    recipe_slug: str,
    n: int,
    processed_combos: set[tuple[frozenset[str], str]],
    seed: int,
    max_attempts: int = 100,
) -> list[dict[str, Any]] | None:
    """Pick n distinct random images whose combination hasn't been used.

    If images carry ``_weight`` keys (set by :func:`filter_images`),
    weighted sampling is used instead of uniform ``rng.sample``.

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
    has_weights = any("_weight" in f for f in files)

    for _ in range(max_attempts):
        if has_weights:
            selected = weighted_sample(files, n, rng)
        else:
            selected = rng.sample(files, n)
        combo = (frozenset(f["id"] for f in selected), recipe_slug)
        if combo not in processed_combos:
            return selected

    return None


# ── Age boundary helpers ─────────────────────────────────────────────

_AGE_SECONDS: dict[str, float] = {
    "24h": 24 * 3600,
    "7d": 7 * 24 * 3600,
    "30d": 30 * 24 * 3600,
    "1-3mo": -1,   # handled specially (range)
    "3-6mo": -1,
    "6-12mo": -1,
    "1y+": 365 * 24 * 3600,
    "2y+": 2 * 365 * 24 * 3600,
}


def _apply_age_filter(
    images: list[dict[str, Any]], age: str
) -> list[dict[str, Any]]:
    """Filter *images* by age bucket relative to ``time.time()``."""
    now = time.time()

    if age == "oldest50":
        return sorted(images, key=lambda img: img.get("timestamp", 0))[:50]

    # Simple "within last X" buckets
    if age in ("24h", "7d", "30d"):
        cutoff = now - _AGE_SECONDS[age]
        return [img for img in images if img.get("timestamp", 0) >= cutoff]

    # Range buckets
    day = 24 * 3600
    if age == "1-3mo":
        lo, hi = now - 3 * 30 * day, now - 1 * 30 * day
        return [img for img in images if lo <= img.get("timestamp", 0) <= hi]
    if age == "3-6mo":
        lo, hi = now - 6 * 30 * day, now - 3 * 30 * day
        return [img for img in images if lo <= img.get("timestamp", 0) <= hi]
    if age == "6-12mo":
        lo, hi = now - 12 * 30 * day, now - 6 * 30 * day
        return [img for img in images if lo <= img.get("timestamp", 0) <= hi]

    # "Older than" buckets
    if age == "1y+":
        cutoff = now - _AGE_SECONDS["1y+"]
        return [img for img in images if img.get("timestamp", 0) <= cutoff]
    if age == "2y+":
        cutoff = now - _AGE_SECONDS["2y+"]
        return [img for img in images if img.get("timestamp", 0) <= cutoff]

    logger.warning("Unknown age filter: %s — returning all images", age)
    return images


def _apply_freshness_filter(
    images: list[dict[str, Any]],
    freshness: str,
    recipe: str | None,
    state: "State | None",
) -> list[dict[str, Any]]:
    """Apply freshness filtering/weighting to *images*."""
    if state is None:
        logger.warning("Freshness filter requires state — returning unfiltered")
        return images

    if freshness == "prefer_fresh_recipe":
        if recipe is None:
            return images
        pairs = state.processed_pairs()
        for img in images:
            img["_weight"] = 1.0 if (img["id"], recipe) in pairs else 3.0
        return images

    if freshness == "only_fresh_recipe":
        if recipe is None:
            return images
        pairs = state.processed_pairs()
        return [img for img in images if (img["id"], recipe) not in pairs]

    if freshness == "only_used_recipe":
        if recipe is None:
            return images
        pairs = state.processed_pairs()
        return [img for img in images if (img["id"], recipe) in pairs]

    if freshness == "prefer_untouched":
        all_ids = state.all_file_ids()
        for img in images:
            img["_weight"] = 1.0 if img["id"] in all_ids else 3.0
        return images

    if freshness == "only_untouched":
        all_ids = state.all_file_ids()
        return [img for img in images if img["id"] not in all_ids]

    if freshness == "only_veterans":
        # Count distinct recipes per file_id
        recipe_counts: Counter[str] = Counter()
        for fid, _recipe in state.processed_pairs():
            recipe_counts[fid] += 1
        return [img for img in images if recipe_counts.get(img["id"], 0) >= 3]

    logger.warning("Unknown freshness filter: %s — returning all images", freshness)
    return images


def filter_images(
    images: list[dict[str, Any]],
    poster: str | None = None,
    age: str | None = None,
    freshness: str | None = None,
    recipe: str | None = None,
    state: "State | None" = None,
) -> list[dict[str, Any]]:
    """Filter source images by poster, age, and freshness.

    Filters are applied in order: poster → age → freshness.
    Some freshness modes (``prefer_*``) add a ``_weight`` key instead
    of removing images, for use with :func:`weighted_sample`.

    Args:
        images: List of image metadata dicts from :func:`fetch_image_files`.
        poster: If set, keep only images from this Slack user ID.
        age: Age bucket string (``24h``, ``7d``, ``30d``, ``1-3mo``,
            ``3-6mo``, ``6-12mo``, ``1y+``, ``2y+``, ``oldest50``).
        freshness: Freshness mode string (``prefer_fresh_recipe``,
            ``only_fresh_recipe``, ``only_used_recipe``,
            ``prefer_untouched``, ``only_untouched``, ``only_veterans``).
        recipe: Recipe slug (needed for recipe-aware freshness modes).
        state: State object for freshness lookups.

    Returns:
        Filtered (and possibly weighted) list of image dicts.
    """
    result = list(images)  # shallow copy to avoid mutating caller's list

    if poster is not None:
        result = [img for img in result if img.get("user") == poster]
        logger.info("Poster filter (%s): %d → %d images", poster, len(images), len(result))

    if age is not None:
        before = len(result)
        result = _apply_age_filter(result, age)
        logger.info("Age filter (%s): %d → %d images", age, before, len(result))

    if freshness is not None:
        before = len(result)
        result = _apply_freshness_filter(result, freshness, recipe, state)
        logger.info("Freshness filter (%s): %d → %d images", freshness, before, len(result))

    return result


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
