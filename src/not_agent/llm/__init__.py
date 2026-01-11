"""LLM integration module (deprecated, use provider module instead)."""

# Re-export from provider for backward compatibility
from not_agent.provider import (
    BaseProvider,
    ClaudeProvider,
    get_provider,
)

__all__ = [
    "BaseProvider",
    "ClaudeProvider",
    "get_provider",
]
