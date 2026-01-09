"""Claude API integration."""

import os
import sys

from anthropic import Anthropic


class ClaudeClient:
    """Claude API client wrapper."""

    def __init__(self, model: str = "claude-sonnet-4-20250514") -> None:
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            print(
                "[Error] ANTHROPIC_API_KEY 환경변수가 설정되지 않았습니다.\n"
                "다음 명령어로 설정하세요:\n"
                "  export ANTHROPIC_API_KEY='your-api-key'"
            )
            sys.exit(1)
        self.client = Anthropic(api_key=api_key)
        self.model = model

    def chat(self, message: str, system: str | None = None) -> str:
        """Send a message to Claude and get a response."""
        messages = [{"role": "user", "content": message}]

        response = self.client.messages.create(
            model=self.model,
            max_tokens=4096,
            system=system or "You are a helpful coding assistant.",
            messages=messages,
        )

        # Extract text from response
        text_content = [
            block.text for block in response.content if hasattr(block, "text")
        ]
        return "\n".join(text_content)
