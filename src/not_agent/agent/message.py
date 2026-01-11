"""Message parts and type-safe message system.

Defines a type-safe message part hierarchy.
Compatible with Anthropic API while remaining extensible.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Literal, Any, TypeVar


class MessagePart(ABC):
    """Abstract base class for message parts.

    All message parts must inherit from this class.
    """

    @property
    @abstractmethod
    def part_type(self) -> str:
        """Part type identifier."""
        pass

    @abstractmethod
    def to_api_format(self) -> dict[str, Any]:
        """Convert to Anthropic API format."""
        pass

    @abstractmethod
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        pass

    @classmethod
    @abstractmethod
    def from_dict(cls, data: dict[str, Any]) -> "MessagePart":
        """Restore from dictionary."""
        pass


@dataclass
class TextPart(MessagePart):
    """Text message part."""

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
    """Tool call part.

    Generated when LLM calls a tool.
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
    """Tool execution result part.

    Contains tool execution results.
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


# Part type registry
_PART_TYPES: dict[str, type[MessagePart]] = {
    "text": TextPart,
    "tool_use": ToolUsePart,
    "tool_result": ToolResultPart,
}


def register_part_type(part_type: str, cls: type[MessagePart]) -> None:
    """Register new part type.

    Args:
        part_type: Part type identifier
        cls: MessagePart subclass
    """
    _PART_TYPES[part_type] = cls


def part_from_dict(data: dict[str, Any]) -> MessagePart:
    """Create appropriate Part instance from dictionary.

    Args:
        data: Dictionary containing part_type key

    Returns:
        MessagePart instance of the appropriate type

    Raises:
        ValueError: Unknown part_type
    """
    part_type = data.get("part_type")
    if part_type not in _PART_TYPES:
        raise ValueError(f"Unknown part type: {part_type}")
    return _PART_TYPES[part_type].from_dict(data)


def part_from_anthropic(block: Any) -> MessagePart:
    """Convert Anthropic SDK block to MessagePart.

    Args:
        block: Anthropic SDK block (TextBlock, ToolUseBlock) or dict

    Returns:
        Converted MessagePart

    Raises:
        ValueError: Cannot convert block
    """
    # Anthropic SDK objects (TextBlock, ToolUseBlock)
    if hasattr(block, "type"):
        if block.type == "text":
            return TextPart(text=block.text)
        elif block.type == "tool_use":
            return ToolUsePart(
                tool_id=block.id,
                tool_name=block.name,
                tool_input=dict(block.input) if block.input else {},
            )

    # dict format (tool_result or API format)
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
    """Convert content to MessagePart list.

    Args:
        content: String or list of blocks

    Returns:
        List of MessageParts
    """
    if isinstance(content, str):
        return [TextPart(text=content)]

    parts = []
    for block in content:
        try:
            parts.append(part_from_anthropic(block))
        except ValueError:
            # On conversion failure, treat as text
            parts.append(TextPart(text=str(block)))
    return parts
