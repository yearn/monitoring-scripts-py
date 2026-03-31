"""LLM provider abstraction for AI-powered transaction explanations.

Supports multiple OpenAI-compatible providers (Venice.ai, OpenAI, etc.)
via a single interface. Configure through environment variables.
"""

from utils.llm.base import LLMProvider
from utils.llm.factory import get_llm_provider

__all__ = ["LLMProvider", "get_llm_provider"]
