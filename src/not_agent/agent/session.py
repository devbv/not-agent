"""세션 및 메시지 관리.

타입 안전한 메시지 시스템을 사용하는 세션 관리 모듈입니다.
"""

from dataclasses import dataclass, field
from typing import Literal, Any, TYPE_CHECKING
from uuid import uuid4

from .message import (
    MessagePart,
    TextPart,
    ToolUsePart,
    ToolResultPart,
    part_from_dict,
    part_from_anthropic,
    parts_from_content,
)


@dataclass
class Message:
    """타입 안전한 대화 메시지.

    모든 메시지 내용은 MessagePart로 구성됩니다.
    """

    role: Literal["user", "assistant"]
    parts: list[MessagePart] = field(default_factory=list)

    def add_part(self, part: MessagePart) -> None:
        """파트 추가."""
        self.parts.append(part)

    def get_parts_by_type(self, part_type: type[MessagePart]) -> list[MessagePart]:
        """특정 타입의 파트만 반환.

        Args:
            part_type: 필터링할 파트 타입

        Returns:
            해당 타입의 파트 리스트
        """
        return [p for p in self.parts if isinstance(p, part_type)]

    def get_text_content(self) -> str:
        """모든 텍스트 파트를 합쳐서 반환."""
        text_parts = self.get_parts_by_type(TextPart)
        return "\n".join(p.text for p in text_parts)  # type: ignore

    def get_tool_uses(self) -> list[ToolUsePart]:
        """모든 도구 호출 파트 반환."""
        return [p for p in self.parts if isinstance(p, ToolUsePart)]

    def to_api_format(self) -> dict[str, Any]:
        """Anthropic API 형식으로 변환."""
        content = [part.to_api_format() for part in self.parts]
        return {"role": self.role, "content": content}

    def to_dict(self) -> dict[str, Any]:
        """직렬화용 딕셔너리."""
        return {
            "role": self.role,
            "parts": [part.to_dict() for part in self.parts],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Message":
        """딕셔너리에서 복원."""
        parts = [part_from_dict(p) for p in data["parts"]]
        return cls(role=data["role"], parts=parts)

    @classmethod
    def from_anthropic_response(cls, role: str, content: list[Any]) -> "Message":
        """Anthropic 응답에서 Message 생성."""
        parts = [part_from_anthropic(block) for block in content]
        return cls(role=role, parts=parts)  # type: ignore

    # 하위 호환성: content 프로퍼티
    @property
    def content(self) -> list[Any]:
        """Legacy: API 형식의 content 반환."""
        return [part.to_api_format() for part in self.parts]


class Session:
    """타입 안전한 대화 세션 관리."""

    def __init__(self) -> None:
        self.id: str = str(uuid4())
        self.messages: list[Message] = []

    def add_user_message(self, content: str | list[MessagePart]) -> Message:
        """사용자 메시지 추가.

        Args:
            content: 문자열 또는 MessagePart 리스트

        Returns:
            추가된 Message
        """
        if isinstance(content, str):
            parts = [TextPart(text=content)]
        else:
            parts = content

        msg = Message(role="user", parts=parts)
        self.messages.append(msg)
        return msg

    def add_assistant_message(self, content: list[Any]) -> Message:
        """어시스턴트 메시지 추가 (Anthropic 응답에서).

        Args:
            content: Anthropic API 응답의 content 블록 리스트

        Returns:
            추가된 Message
        """
        parts = [part_from_anthropic(block) for block in content]
        msg = Message(role="assistant", parts=parts)
        self.messages.append(msg)
        return msg

    def add_tool_results(self, results: list[dict[str, Any]]) -> Message:
        """도구 결과를 사용자 메시지로 추가.

        Args:
            results: tool_result 딕셔너리 리스트

        Returns:
            추가된 Message
        """
        parts: list[MessagePart] = []
        for result in results:
            parts.append(
                ToolResultPart(
                    tool_use_id=result["tool_use_id"],
                    content=result.get("content", ""),
                    is_error=result.get("is_error", False),
                )
            )

        msg = Message(role="user", parts=parts)
        self.messages.append(msg)
        return msg

    def to_api_format(self) -> list[dict[str, Any]]:
        """API 호출용 형식으로 변환."""
        return [msg.to_api_format() for msg in self.messages]

    def to_dict(self) -> dict[str, Any]:
        """직렬화용 딕셔너리."""
        return {
            "id": self.id,
            "messages": [msg.to_dict() for msg in self.messages],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Session":
        """딕셔너리에서 복원."""
        session = cls()
        session.id = data["id"]
        session.messages = [Message.from_dict(m) for m in data["messages"]]
        return session

    # 하위 호환성 메서드들

    def get_messages(self) -> list[dict[str, Any]]:
        """Legacy: to_api_format 별칭."""
        return self.to_api_format()

    def set_messages(self, messages: list[dict[str, Any]]) -> None:
        """Legacy: API 형식에서 메시지 설정 (컴팩션 후 등).

        Args:
            messages: Anthropic API 형식의 메시지 리스트
        """
        self.messages = []
        for msg_dict in messages:
            role = msg_dict["role"]
            content = msg_dict["content"]

            # 문자열인 경우
            if isinstance(content, str):
                self.messages.append(
                    Message(role=role, parts=[TextPart(text=content)])  # type: ignore
                )
                continue

            # 리스트인 경우
            parts = parts_from_content(content)
            self.messages.append(Message(role=role, parts=parts))  # type: ignore

    def clear(self) -> None:
        """세션 초기화."""
        self.messages.clear()
        self.id = str(uuid4())

    def __len__(self) -> int:
        """메시지 수 반환."""
        return len(self.messages)
