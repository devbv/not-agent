"""LLM 프로바이더 기본 인터페이스."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from not_agent.tools.base import BaseTool


@dataclass
class ProviderResponse:
    """프로바이더 응답 표준 형식."""

    content: list[Any]  # TextBlock, ToolUseBlock 등
    stop_reason: str
    usage: dict[str, int] = field(default_factory=dict)  # input_tokens, output_tokens


class BaseProvider(ABC):
    """LLM 프로바이더 추상 클래스."""

    @property
    @abstractmethod
    def name(self) -> str:
        """프로바이더 이름."""
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
        LLM 호출.

        Args:
            messages: 대화 메시지 리스트
            system: 시스템 프롬프트
            tools: 도구 정의 리스트
            max_tokens: 최대 출력 토큰 수

        Returns:
            ProviderResponse: 표준화된 응답
        """
        pass

    def format_tool(self, tool: "BaseTool") -> dict[str, Any]:
        """
        도구를 프로바이더 형식으로 변환.

        기본 구현은 Anthropic 형식을 사용합니다.
        다른 프로바이더는 필요시 오버라이드하세요.
        """
        return tool.to_anthropic_tool()
