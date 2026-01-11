"""세션 및 메시지 관리."""

from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4


@dataclass
class Message:
    """대화 메시지."""

    role: str  # "user" | "assistant"
    content: list[Any] | str  # TextBlock, ToolUseBlock, ToolResultBlock 등


class Session:
    """대화 세션 관리."""

    def __init__(self) -> None:
        self.id: str = str(uuid4())
        self.messages: list[Message] = []

    def add_user_message(self, content: str | list[Any]) -> None:
        """사용자 메시지 추가."""
        if isinstance(content, str):
            content = [{"type": "text", "text": content}]
        self.messages.append(Message(role="user", content=content))

    def add_assistant_message(self, content: list[Any]) -> None:
        """어시스턴트 메시지 추가."""
        self.messages.append(Message(role="assistant", content=content))

    def add_tool_results(self, results: list[dict[str, Any]]) -> None:
        """도구 결과를 사용자 메시지로 추가."""
        self.messages.append(Message(role="user", content=results))

    def to_api_format(self) -> list[dict[str, Any]]:
        """API 호출용 형식으로 변환."""
        return [
            {"role": msg.role, "content": msg.content}
            for msg in self.messages
        ]

    def get_messages(self) -> list[dict[str, Any]]:
        """메시지 리스트 반환 (to_api_format 별칭)."""
        return self.to_api_format()

    def set_messages(self, messages: list[dict[str, Any]]) -> None:
        """메시지 리스트 직접 설정 (컴팩션 후 등)."""
        self.messages = [
            Message(role=msg["role"], content=msg["content"])
            for msg in messages
        ]

    def clear(self) -> None:
        """세션 초기화."""
        self.messages.clear()
        self.id = str(uuid4())

    def __len__(self) -> int:
        """메시지 수 반환."""
        return len(self.messages)
