"""Provider registry."""

from typing import Type, TYPE_CHECKING

from .base import BaseProvider
from .claude import ClaudeProvider

if TYPE_CHECKING:
    from not_agent.config import Config


# Registered providers
PROVIDERS: dict[str, Type[BaseProvider]] = {
    "claude": ClaudeProvider,
}


def get_provider(name: str, config: "Config") -> BaseProvider:
    """
    Create provider instance by name.

    Args:
        name: Provider name (e.g., "claude")
        config: Configuration object

    Returns:
        BaseProvider: Provider instance

    Raises:
        ValueError: Unknown provider name
    """
    if name not in PROVIDERS:
        available = list(PROVIDERS.keys())
        raise ValueError(f"Unknown provider: {name}. Available: {available}")

    return PROVIDERS[name](config)


def register_provider(name: str, provider_class: Type[BaseProvider]) -> None:
    """
    Register provider (for extension).

    Args:
        name: Provider name
        provider_class: Class inheriting from BaseProvider
    """
    PROVIDERS[name] = provider_class


def list_providers() -> list[str]:
    """Return list of registered provider names."""
    return list(PROVIDERS.keys())
