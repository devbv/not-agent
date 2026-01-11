"""Claude client (deprecated, use provider module instead)."""

import warnings
from not_agent.config import Config
from not_agent.provider import ClaudeProvider


class ClaudeClient:
    """
    Legacy ClaudeClient for backward compatibility.

    Deprecated: Use ClaudeProvider from not_agent.provider instead.
    """

    def __init__(self, model: str = "claude-sonnet-4-20250514") -> None:
        warnings.warn(
            "ClaudeClient is deprecated. Use ClaudeProvider from not_agent.provider instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        config = Config()
        config.set("model", model)
        self._provider = ClaudeProvider(config)

    def chat(self, message: str, system: str | None = None) -> str:
        """
        Legacy chat method.

        Deprecated: Use ClaudeProvider.simple_chat() instead.
        """
        return self._provider.simple_chat(message, system)
