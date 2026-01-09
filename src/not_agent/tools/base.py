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
