"""Tool registry system."""

from typing import Type, TYPE_CHECKING

if TYPE_CHECKING:
    from .base import BaseTool


class ToolRegistry:
    """
    Tool registration and management.

    Uses singleton pattern for global registry management.
    """

    _tools: dict[str, Type["BaseTool"]] = {}
    _instances: dict[str, "BaseTool"] = {}
    _instance_kwargs: dict[str, dict] = {}  # Per-tool initialization arguments

    @classmethod
    def register(
        cls,
        tool_class: Type["BaseTool"],
        name: str | None = None,
    ) -> Type["BaseTool"]:
        """
        Register a tool class.

        Args:
            tool_class: Tool class to register
            name: Optional tool name (uses class's name attribute if not provided)

        Returns:
            Registered tool class (for decorator chaining)
        """
        tool_name = name or tool_class.name
        if not tool_name:
            raise ValueError(f"Tool class {tool_class.__name__} must have a 'name' attribute")

        cls._tools[tool_name] = tool_class
        return tool_class

    @classmethod
    def get(cls, name: str, **kwargs) -> "BaseTool":
        """
        Get tool instance by name.

        Args:
            name: Tool name
            **kwargs: Tool initialization arguments (needed for TodoTool, etc.)

        Returns:
            Tool instance
        """
        if name not in cls._tools:
            raise KeyError(f"Unknown tool: {name}. Available: {list(cls._tools.keys())}")

        # Cache key: name + kwargs hash
        cache_key = name
        if kwargs:
            # Create new instance if kwargs provided (e.g., TodoManager)
            return cls._tools[name](**kwargs)

        if cache_key not in cls._instances:
            cls._instances[cache_key] = cls._tools[name]()

        return cls._instances[cache_key]

    @classmethod
    def get_all(cls, **shared_kwargs) -> list["BaseTool"]:
        """
        Return all registered tool instances.

        Args:
            **shared_kwargs: Common arguments to pass to all tools

        Returns:
            List of tool instances
        """
        tools = []
        for name in cls._tools:
            try:
                tool = cls.get(name, **shared_kwargs)
                tools.append(tool)
            except TypeError:
                # Tool that doesn't need kwargs
                tool = cls.get(name)
                tools.append(tool)
        return tools

    @classmethod
    def get_tool_class(cls, name: str) -> Type["BaseTool"]:
        """Get tool class (without instantiation)."""
        if name not in cls._tools:
            raise KeyError(f"Unknown tool: {name}")
        return cls._tools[name]

    @classmethod
    def list_tools(cls) -> list[str]:
        """Return list of registered tool names."""
        return list(cls._tools.keys())

    @classmethod
    def clear(cls) -> None:
        """Clear registry (for testing)."""
        cls._tools.clear()
        cls._instances.clear()
        cls._instance_kwargs.clear()

    @classmethod
    def is_registered(cls, name: str) -> bool:
        """Check if tool is registered."""
        return name in cls._tools


def register_tool(cls: Type["BaseTool"]) -> Type["BaseTool"]:
    """
    Tool registration decorator.

    Usage:
        @register_tool
        class ReadTool(BaseTool):
            name = "read"
            ...
    """
    return ToolRegistry.register(cls)
