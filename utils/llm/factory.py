"""Factory for creating LLM provider instances from environment configuration.

Environment variables:
    LLM_PROVIDER: Provider name (default: "venice"). Used for logging only;
                  all providers use the OpenAI-compatible client.
    LLM_API_KEY: API key for the provider (required).
    LLM_BASE_URL: Base URL for the API.
    LLM_MODEL: Model identifier to use.

Provider defaults:
    venice: base_url=https://api.venice.ai/api/v1, model=llama-3.3-70b
    openai: base_url=https://api.openai.com/v1, model=gpt-4o-mini
    Custom: Set LLM_BASE_URL and LLM_MODEL explicitly.
"""

import os

from utils.llm.base import LLMError, LLMProvider
from utils.llm.openai_compat import OpenAICompatProvider
from utils.logging import get_logger

logger = get_logger("utils.llm.factory")

# Default configurations per provider name
_PROVIDER_DEFAULTS: dict[str, dict[str, str]] = {
    "venice": {
        "base_url": "https://api.venice.ai/api/v1",
        "model": "llama-3.3-70b",
    },
    "openai": {
        "base_url": "https://api.openai.com/v1",
        "model": "gpt-4o-mini",
    },
}

# Cached singleton instance
_instance: LLMProvider | None = None


def get_llm_provider() -> LLMProvider:
    """Create or return the cached LLM provider based on environment variables.

    Returns:
        Configured LLMProvider instance.

    Raises:
        LLMError: If LLM_API_KEY is not set.
    """
    global _instance
    if _instance is not None:
        return _instance

    provider_name = os.getenv("LLM_PROVIDER", "venice").lower()
    api_key = os.getenv("LLM_API_KEY")
    if not api_key:
        raise LLMError("LLM_API_KEY environment variable is not set")

    defaults = _PROVIDER_DEFAULTS.get(provider_name, {})
    base_url = os.getenv("LLM_BASE_URL", defaults.get("base_url", ""))
    model = os.getenv("LLM_MODEL", defaults.get("model", ""))

    if not base_url or not model:
        raise LLMError(
            f"LLM_BASE_URL and LLM_MODEL must be set for provider '{provider_name}'. "
            f"Known providers with defaults: {list(_PROVIDER_DEFAULTS.keys())}"
        )

    logger.info("Creating LLM provider: %s (model=%s)", provider_name, model)
    _instance = OpenAICompatProvider(api_key=api_key, base_url=base_url, model=model)
    return _instance


def reset_provider() -> None:
    """Reset the cached provider instance. Useful for testing."""
    global _instance
    _instance = None
