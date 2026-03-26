"""Llama Vision analysis via HF Inference API."""

from __future__ import annotations

import base64
import io
import logging
from typing import Any

from PIL import Image

logger = logging.getLogger(__name__)

VISION_MODEL = "meta-llama/Llama-3.2-11B-Vision-Instruct"

ANALYSIS_PROMPT = (
    "Analyze this image in detail. Describe:\n"
    "1. What objects, people, or creatures are present and where they are spatially\n"
    "2. The dominant colors and color palette\n"
    "3. The composition and visual structure\n"
    "4. Any text visible in the image\n"
    "5. The overall mood or aesthetic\n"
    "Be specific about spatial locations (top-left, center, bottom-right, etc)."
)


def analyze_image(
    image: Image.Image,
    token: str,
    model: str = VISION_MODEL,
) -> dict[str, Any]:
    """Analyze an image using Llama Vision via HF Inference API.

    Args:
        image: PIL Image to analyze.
        token: HuggingFace API token.
        model: Model ID to use.

    Returns:
        Dict with 'description' key containing the analysis text.
    """
    from huggingface_hub import InferenceClient

    # Encode image as base64
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    img_b64 = base64.b64encode(buffer.getvalue()).decode("utf-8")

    client = InferenceClient(token=token)

    response = client.chat_completion(
        model=model,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{img_b64}"},
                    },
                    {
                        "type": "text",
                        "text": ANALYSIS_PROMPT,
                    },
                ],
            }
        ],
        max_tokens=500,
    )

    raw_text = response.choices[0].message.content
    logger.info("Vision analysis: %s", raw_text[:200])

    return parse_vision_response(raw_text)


def parse_vision_response(raw: str) -> dict[str, Any]:
    """Parse the raw vision response into a structured dict.

    Currently stores the full text as 'description'. Future versions
    may extract structured spatial data for targeted effects.

    Args:
        raw: Raw text response from the vision model.

    Returns:
        Dict with parsed analysis data.
    """
    return {"description": raw}
