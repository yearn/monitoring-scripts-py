"""Upload text to a paste service for temporary sharing.

Uses dpaste.org by default, with configurable expiry (default 7 days).
"""

import requests

from utils.logging import get_logger

logger = get_logger("utils.paste")

DPASTE_API_URL = "https://dpaste.org/api/"
DEFAULT_EXPIRY_DAYS = 7


def upload_to_paste(content: str, title: str = "", expiry_days: int = DEFAULT_EXPIRY_DAYS) -> str:
    """Upload text content to dpaste.org and return the URL.

    Args:
        content: The text content to upload.
        title: Optional title for the paste.
        expiry_days: Number of days before the paste expires (default 7).

    Returns:
        The URL of the created paste, or empty string on failure.
    """
    if not content:
        return ""

    payload: dict[str, str | int] = {
        "content": content,
        "expiry_days": expiry_days,
    }
    if title:
        payload["title"] = title

    try:
        response = requests.post(DPASTE_API_URL, data=payload, timeout=10)
        response.raise_for_status()
        url = response.text.strip().strip('"')
        logger.info("Uploaded paste to %s (expires in %d days)", url, expiry_days)
        return url
    except requests.RequestException as e:
        logger.warning("Failed to upload to paste service: %s", e)
        return ""
