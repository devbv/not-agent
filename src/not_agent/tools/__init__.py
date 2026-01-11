"""Tools module - File operations, bash execution, web search, etc."""

# Import registry first
from .registry import ToolRegistry, register_tool

# Import base classes
from .base import BaseTool, ToolResult

# Import all tools (this triggers @register_tool decorators)
from .ask_user import AskUserQuestionTool
from .bash import BashTool
from .edit import EditTool
from .glob_tool import GlobTool
from .grep import GrepTool
from .read import ReadTool
from .web_fetch import WebFetchTool
from .web_search import WebSearchTool
from .write import WriteTool

# Todo tools (not auto-registered - require TodoManager injection)
from .todo import TodoManager, TodoReadTool, TodoWriteTool

__all__ = [
    # Registry
    "ToolRegistry",
    "register_tool",
    # Base
    "BaseTool",
    "ToolResult",
    # Tools
    "AskUserQuestionTool",
    "BashTool",
    "EditTool",
    "GlobTool",
    "GrepTool",
    "ReadTool",
    "TodoManager",
    "TodoReadTool",
    "TodoWriteTool",
    "WebFetchTool",
    "WebSearchTool",
    "WriteTool",
]


def get_all_tools(todo_manager: TodoManager | None = None) -> list[BaseTool]:
    """
    Get instances of all available tools.

    Uses ToolRegistry for registered tools, then adds Todo tools if manager provided.

    Args:
        todo_manager: Optional TodoManager instance for Todo tools.
                     If not provided, Todo tools won't be included.

    Returns:
        List of tool instances.
    """
    # Get all registered tools from registry
    tools = [ToolRegistry.get(name) for name in ToolRegistry.list_tools()]

    # Todo 도구는 manager가 있을 때만 추가 (의존성 주입 필요)
    if todo_manager is not None:
        tools.extend([
            TodoWriteTool(todo_manager),
            TodoReadTool(todo_manager),
        ])

    return tools
