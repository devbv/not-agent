"""Message parts and type-safe message system.

타입 안전한 메시지 파트 계층 구조를 정의합니다.
Anthropic API와 호환되면서도 확장 가능한 구조입니다.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Literal, Any, TypeVar


class MessagePart(ABC):
    """메시지 파트 추상 기본 클래스.

    모든 메시지 파트는 이 클래스를 상속해야 합니다.
    """

    @property
    @abstractmethod
    def part_type(self) -> str:
        """파트 타입 식별자."""
        pass

    @abstractmethod
    def to_api_format(self) -> dict[str, Any]:
        """Anthropic API 형식으로 변환."""
        pass

    @abstractmethod
    def to_dict(self) -> dict[str, Any]:
        """직렬화용 딕셔너리 변환."""
        pass

    @classmethod
    @abstractmethod
    def from_dict(cls, data: dict[str, Any]) -> "MessagePart":
        """딕셔너리에서 복원."""
        pass


@dataclass
class TextPart(MessagePart):
    """텍스트 메시지 파트."""

    text: str

    @property
    def part_type(self) -> Literal["text"]:
        return "text"

    def to_api_format(self) -> dict[str, Any]:
        return {"type": "text", "text": self.text}

    def to_dict(self) -> dict[str, Any]:
        return {"part_type": "text", "text": self.text}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TextPart":
        return cls(text=data["text"])


@dataclass
class ToolUsePart(MessagePart):
    """도구 호출 파트.

    LLM이 도구를 호출할 때 생성됩니다.
    """

    tool_id: str
    tool_name: str
    tool_input: dict[str, Any]

    @property
    def part_type(self) -> Literal["tool_use"]:
        return "tool_use"

    def to_api_format(self) -> dict[str, Any]:
        return {
            "type": "tool_use",
            "id": self.tool_id,
            "name": self.tool_name,
            "input": self.tool_input,
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "part_type": "tool_use",
            "tool_id": self.tool_id,
            "tool_name": self.tool_name,
            "tool_input": self.tool_input,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ToolUsePart":
        return cls(
            tool_id=data["tool_id"],
            tool_name=data["tool_name"],
            tool_input=data["tool_input"],
        )


@dataclass
class ToolResultPart(MessagePart):
    """도구 실행 결과 파트.

    도구 실행 결과를 담습니다.
    """

    tool_use_id: str
    content: str
    is_error: bool = False

    @property
    def part_type(self) -> Literal["tool_result"]:
        return "tool_result"

    def to_api_format(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "type": "tool_result",
            "tool_use_id": self.tool_use_id,
            "content": self.content,
        }
        if self.is_error:
            result["is_error"] = True
        return result

    def to_dict(self) -> dict[str, Any]:
        return {
            "part_type": "tool_result",
            "tool_use_id": self.tool_use_id,
            "content": self.content,
            "is_error": self.is_error,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ToolResultPart":
        return cls(
            tool_use_id=data["tool_use_id"],
            content=data["content"],
            is_error=data.get("is_error", False),
        )


# Part 타입 레지스트리
_PART_TYPES: dict[str, type[MessagePart]] = {
    "text": TextPart,
    "tool_use": ToolUsePart,
    "tool_result": ToolResultPart,
}


def register_part_type(part_type: str, cls: type[MessagePart]) -> None:
    """새 파트 타입 등록.

    Args:
        part_type: 파트 타입 식별자
        cls: MessagePart 서브클래스
    """
    _PART_TYPES[part_type] = cls


def part_from_dict(data: dict[str, Any]) -> MessagePart:
    """딕셔너리에서 적절한 Part 인스턴스 생성.

    Args:
        data: part_type 키를 포함한 딕셔너리

    Returns:
        해당 타입의 MessagePart 인스턴스

    Raises:
        ValueError: 알 수 없는 part_type
    """
    part_type = data.get("part_type")
    if part_type not in _PART_TYPES:
        raise ValueError(f"Unknown part type: {part_type}")
    return _PART_TYPES[part_type].from_dict(data)


def part_from_anthropic(block: Any) -> MessagePart:
    """Anthropic SDK 블록에서 MessagePart 변환.

    Args:
        block: Anthropic SDK 블록 (TextBlock, ToolUseBlock) 또는 dict

    Returns:
        변환된 MessagePart

    Raises:
        ValueError: 변환할 수 없는 블록
    """
    # Anthropic SDK 객체 (TextBlock, ToolUseBlock)
    if hasattr(block, "type"):
        if block.type == "text":
            return TextPart(text=block.text)
        elif block.type == "tool_use":
            return ToolUsePart(
                tool_id=block.id,
                tool_name=block.name,
                tool_input=dict(block.input) if block.input else {},
            )

    # dict 형태 (tool_result 또는 API 형식)
    if isinstance(block, dict):
        block_type = block.get("type")
        if block_type == "tool_result":
            return ToolResultPart(
                tool_use_id=block["tool_use_id"],
                content=block.get("content", ""),
                is_error=block.get("is_error", False),
            )
        elif block_type == "text":
            return TextPart(text=block.get("text", ""))
        elif block_type == "tool_use":
            return ToolUsePart(
                tool_id=block["id"],
                tool_name=block["name"],
                tool_input=block.get("input", {}),
            )

    raise ValueError(f"Cannot convert to MessagePart: {type(block)} - {block}")


def parts_from_content(content: list[Any] | str) -> list[MessagePart]:
    """content를 MessagePart 리스트로 변환.

    Args:
        content: 문자열 또는 블록 리스트

    Returns:
        MessagePart 리스트
    """
    if isinstance(content, str):
        return [TextPart(text=content)]

    parts = []
    for block in content:
        try:
            parts.append(part_from_anthropic(block))
        except ValueError:
            # 변환 실패 시 텍스트로 처리
            parts.append(TextPart(text=str(block)))
    return parts
