"""LLM provider base interface."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from not_agent.tools.base import BaseTool


@dataclass
class ProviderResponse:
    """Provider response standard format."""

    content: list[Any]  # TextBlock, ToolUseBlock, etc.
    stop_reason: str
    usage: dict[str, int] = field(default_factory=dict)  # input_tokens, output_tokens


class BaseProvider(ABC):
    """LLM provider abstract class."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name."""
        pass

    @abstractmethod
    def chat(
        self,
        messages: list[dict[str, Any]],
        system: str | None = None,
        tools: list[dict[str, Any]] | None = None,
        max_tokens: int = 16384,
    ) -> ProviderResponse:
        """
        Call LLM.

        Args:
            messages: Conversation message list
            system: System prompt
            tools: Tool definition list
            max_tokens: Max output tokens

        Returns:
            ProviderResponse: Standardized response
        """
        pass

    def format_tool(self, tool: "BaseTool") -> dict[str, Any]:
        """
        Convert tool to provider format.

        Default implementation uses Anthropic format.
        Override for other providers if needed.
        """
        return tool.to_anthropic_tool()
