"""Simple HTTP helper for fetching JSON from APIs."""

from typing import Any

import requests

from utils.config import Config
from utils.logging import get_logger

logger = get_logger("utils.http")


def fetch_json(
    url: str,
    method: str = "get",
    timeout: int | None = None,
    **kwargs: Any,
) -> dict | None:
    """Fetch JSON from a URL with error handling.

    Returns the parsed JSON dict on success, or None on failure.
    """
    if timeout is None:
        timeout = Config.get_request_timeout()
    try:
        resp = requests.request(method, url, timeout=timeout, **kwargs)
        if resp.status_code != 200:
            logger.error("HTTP %s for %s: %s", resp.status_code, url, resp.text[:200])
            return None
        return resp.json()
    except Exception as e:
        logger.error("Request failed for %s: %s", url, e)
        return None
