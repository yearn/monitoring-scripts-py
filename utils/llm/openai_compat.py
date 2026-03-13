"""OpenAI-compatible LLM provider.

Works with any provider that implements the OpenAI chat completions API:
- Venice.ai (https://api.venice.ai/api/v1)
- OpenAI (https://api.openai.com/v1)
- Together AI, Groq, Ollama, etc.
"""

from openai import OpenAI

from utils.llm.base import LLMError, LLMProvider
from utils.logging import get_logger

logger = get_logger("utils.llm.openai_compat")


class OpenAICompatProvider(LLMProvider):
    """LLM provider for any OpenAI-compatible API."""

    def __init__(self, api_key: str, base_url: str, model: str) -> None:
        """Initialize the provider.

        Args:
            api_key: API key for the provider.
            base_url: Base URL for the API (e.g. https://api.venice.ai/api/v1).
            model: Model identifier (e.g. llama-3.3-70b, gpt-4o-mini).
        """
        self._model = model
        self._client = OpenAI(api_key=api_key, base_url=base_url)
        logger.info("Initialized OpenAI-compatible provider: base_url=%s model=%s", base_url, model)

    def complete(self, prompt: str, max_tokens: int = 300) -> str:
        """Generate a completion using the OpenAI chat completions API."""
        try:
            response = self._client.chat.completions.create(
                model=self._model,
                max_tokens=max_tokens,
                messages=[{"role": "user", "content": prompt}],
            )
            content = response.choices[0].message.content
            if not content:
                raise LLMError("Empty response from LLM")
            return content.strip()
        except LLMError:
            raise
        except Exception as e:
            raise LLMError(f"LLM API call failed: {e}") from e

    @property
    def model_name(self) -> str:
        """Return the model identifier."""
        return self._model
