"""Claude 프로바이더 구현."""

import os
import sys
from typing import Any, TYPE_CHECKING

from anthropic import Anthropic

from .base import BaseProvider, ProviderResponse

if TYPE_CHECKING:
    from not_agent.config import Config


class ClaudeProvider(BaseProvider):
    """Anthropic Claude API 프로바이더."""

    @property
    def name(self) -> str:
        return "claude"

    def __init__(self, config: "Config") -> None:
        self.config = config
        api_key = config.get("api_key") or os.environ.get("ANTHROPIC_API_KEY")

        if not api_key:
            print(
                "[Error] ANTHROPIC_API_KEY 환경변수가 설정되지 않았습니다.\n"
                "다음 명령어로 설정하세요:\n"
                "  export ANTHROPIC_API_KEY='your-api-key'"
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
        """Claude API 호출."""
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
        단순 채팅용 메서드 (도구 없음).

        기존 ClaudeClient.chat() 호환용.
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
