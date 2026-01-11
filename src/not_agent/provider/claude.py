"""Claude provider implementation."""

import os
import sys
from typing import Any, TYPE_CHECKING

from anthropic import Anthropic
from rich.console import Console

from .base import BaseProvider, ProviderResponse

if TYPE_CHECKING:
    from not_agent.config import Config

_console = Console(stderr=True)


class ClaudeProvider(BaseProvider):
    """Anthropic Claude API provider."""

    @property
    def name(self) -> str:
        return "claude"

    def __init__(self, config: "Config") -> None:
        self.config = config
        api_key = config.get("api_key") or os.environ.get("ANTHROPIC_API_KEY")

        if not api_key:
            _console.print(
                "[red][Error][/red] ANTHROPIC_API_KEY environment variable is not set.\n"
                "Set it with:\n"
                "  [cyan]export ANTHROPIC_API_KEY='your-api-key'[/cyan]"
            )
            sys.exit(1)

        self.client = Anthropic(api_key=api_key)
        self.model = config.get("model", "claude-sonnet-4-20250514")

    def chat(
        self,
        messages: list[dict[str, Any]],
        system: str | None = None,
        tools: list[dict[str, Any]] | None = None,
        max_tokens: int = 16384,
    ) -> ProviderResponse:
        """Call Claude API."""
        kwargs: dict[str, Any] = {
            "model": self.model,
            "max_tokens": max_tokens,
            "messages": messages,
        }

        if system:
            kwargs["system"] = system

        if tools:
            kwargs["tools"] = tools

        response = self.client.messages.create(**kwargs)

        return ProviderResponse(
            content=list(response.content),
            stop_reason=response.stop_reason,
            usage={
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
            },
        )

    def simple_chat(self, message: str, system: str | None = None) -> str:
        """
        Simple chat method (no tools).

        For legacy ClaudeClient.chat() compatibility.
        """
        messages = [{"role": "user", "content": message}]

        response = self.client.messages.create(
            model=self.model,
            max_tokens=self.config.get("max_tokens", 4096),
            system=system or "You are a helpful coding assistant.",
            messages=messages,
        )

        # Extract text from response
        text_content = [
            block.text for block in response.content if hasattr(block, "text")
        ]
        return "\n".join(text_content)
