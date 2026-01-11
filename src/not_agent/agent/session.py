"""Session and message management.

Session management module using type-safe message system.
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
    """Type-safe conversation message.

    All message content consists of MessageParts.
    """

    role: Literal["user", "assistant"]
    parts: list[MessagePart] = field(default_factory=list)

    def add_part(self, part: MessagePart) -> None:
        """Add a part."""
        self.parts.append(part)

    def get_parts_by_type(self, part_type: type[MessagePart]) -> list[MessagePart]:
        """Return only parts of a specific type.

        Args:
            part_type: Part type to filter by

        Returns:
            List of parts of the specified type
        """
        return [p for p in self.parts if isinstance(p, part_type)]

    def get_text_content(self) -> str:
        """Join and return all text parts."""
        text_parts = self.get_parts_by_type(TextPart)
        return "\n".join(p.text for p in text_parts)  # type: ignore

    def get_tool_uses(self) -> list[ToolUsePart]:
        """Return all tool call parts."""
        return [p for p in self.parts if isinstance(p, ToolUsePart)]

    def to_api_format(self) -> dict[str, Any]:
        """Convert to Anthropic API format."""
        content = [part.to_api_format() for part in self.parts]
        return {"role": self.role, "content": content}

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "role": self.role,
            "parts": [part.to_dict() for part in self.parts],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Message":
        """Restore from dictionary."""
        parts = [part_from_dict(p) for p in data["parts"]]
        return cls(role=data["role"], parts=parts)

    @classmethod
    def from_anthropic_response(cls, role: str, content: list[Any]) -> "Message":
        """Create Message from Anthropic response."""
        parts = [part_from_anthropic(block) for block in content]
        return cls(role=role, parts=parts)  # type: ignore

    # Backward compatibility: content property
    @property
    def content(self) -> list[Any]:
        """Legacy: Return content in API format."""
        return [part.to_api_format() for part in self.parts]


class Session:
    """Type-safe conversation session management."""

    def __init__(self) -> None:
        self.id: str = str(uuid4())
        self.messages: list[Message] = []

    def add_user_message(self, content: str | list[MessagePart]) -> Message:
        """Add user message.

        Args:
            content: String or list of MessageParts

        Returns:
            Added Message
        """
        if isinstance(content, str):
            parts = [TextPart(text=content)]
        else:
            parts = content

        msg = Message(role="user", parts=parts)
        self.messages.append(msg)
        return msg

    def add_assistant_message(self, content: list[Any]) -> Message:
        """Add assistant message (from Anthropic response).

        Args:
            content: Content block list from Anthropic API response

        Returns:
            Added Message
        """
        parts = [part_from_anthropic(block) for block in content]
        msg = Message(role="assistant", parts=parts)
        self.messages.append(msg)
        return msg

    def add_tool_results(self, results: list[dict[str, Any]]) -> Message:
        """Add tool results as user message.

        Args:
            results: List of tool_result dictionaries

        Returns:
            Added Message
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
        """Convert to API call format."""
        return [msg.to_api_format() for msg in self.messages]

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "messages": [msg.to_dict() for msg in self.messages],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Session":
        """Restore from dictionary."""
        session = cls()
        session.id = data["id"]
        session.messages = [Message.from_dict(m) for m in data["messages"]]
        return session

    # Backward compatibility methods

    def get_messages(self) -> list[dict[str, Any]]:
        """Legacy: Alias for to_api_format."""
        return self.to_api_format()

    def set_messages(self, messages: list[dict[str, Any]]) -> None:
        """Legacy: Set messages from API format (after compaction, etc.).

        Args:
            messages: List of messages in Anthropic API format
        """
        self.messages = []
        for msg_dict in messages:
            role = msg_dict["role"]
            content = msg_dict["content"]

            # If string
            if isinstance(content, str):
                self.messages.append(
                    Message(role=role, parts=[TextPart(text=content)])  # type: ignore
                )
                continue

            # If list
            parts = parts_from_content(content)
            self.messages.append(Message(role=role, parts=parts))  # type: ignore

    def clear(self) -> None:
        """Clear session."""
        self.messages.clear()
        self.id = str(uuid4())

    def __len__(self) -> int:
        """Return message count."""
        return len(self.messages)
