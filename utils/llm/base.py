"""Abstract base class for LLM providers."""

from abc import ABC, abstractmethod


class LLMProvider(ABC):
    """Interface for LLM providers used to generate transaction explanations."""

    @abstractmethod
    def complete(self, prompt: str, max_tokens: int = 300) -> str:
        """Generate a completion for the given prompt.

        Args:
            prompt: The prompt to send to the LLM.
            max_tokens: Maximum tokens in the response.

        Returns:
            The generated text response.

        Raises:
            LLMError: If the API call fails.
        """

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Return the model identifier being used."""


class LLMError(Exception):
    """Exception raised for LLM API errors."""
