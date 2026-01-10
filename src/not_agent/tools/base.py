"""Base class for all tools."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class ToolResult:
    """Result returned by a tool execution."""

    success: bool
    output: str
    error: str | None = None


class BaseTool(ABC):
    """Abstract base class for all tools."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Tool name used in function calls."""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """Description of what the tool does."""
        pass

    @property
    @abstractmethod
    def parameters(self) -> dict[str, Any]:
        """JSON Schema for tool parameters."""
        pass

    @abstractmethod
    def execute(self, **kwargs: Any) -> ToolResult:
        """Execute the tool with given parameters."""
        pass

    def get_approval_description(self, **kwargs: Any) -> str | None:
        """
        승인 플러그인에게 제공할 설명.

        Args:
            **kwargs: Tool의 execute() 파라미터

        Returns:
            None: 이 도구는 승인 불필요
            str: 승인 필요 - 사용자에게 보여줄 설명
        """
        return None  # 기본값: 승인 불필요

    def to_anthropic_tool(self) -> dict[str, Any]:
        """Convert to Anthropic API tool format."""
        # Clean properties - remove 'required' key from each property
        clean_properties = {}
        required_fields = []
        for key, value in self.parameters.items():
            prop = {k: v for k, v in value.items() if k != "required"}
            clean_properties[key] = prop
            if value.get("required", False):
                required_fields.append(key)

        return {
            "name": self.name,
            "description": self.description,
            "input_schema": {
                "type": "object",
                "properties": clean_properties,
                "required": required_fields,
            },
        }
