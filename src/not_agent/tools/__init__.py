"""Tools module - File operations, bash execution, web search, etc."""

from .ask_user import AskUserQuestionTool
from .base import BaseTool, ToolResult
from .bash import BashTool
from .edit import EditTool
from .glob_tool import GlobTool
from .grep import GrepTool
from .read import ReadTool
from .todo import TodoManager, TodoReadTool, TodoWriteTool
from .web_fetch import WebFetchTool
from .web_search import WebSearchTool
from .write import WriteTool

__all__ = [
    "AskUserQuestionTool",
    "BaseTool",
    "ToolResult",
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
    """Get instances of all available tools.

    Args:
        todo_manager: Optional TodoManager instance for Todo tools.
                     If not provided, Todo tools won't be included.
    """
    tools = [
        ReadTool(),
        WriteTool(),  # 단일 write 도구 (opencode 스타일, diff 표시 지원)
        EditTool(),
        GlobTool(),
        GrepTool(),
        BashTool(),
        WebSearchTool(),
        WebFetchTool(),
        AskUserQuestionTool(),
    ]

    # Todo 도구는 manager가 있을 때만 추가
    if todo_manager is not None:
        tools.extend([
            TodoWriteTool(todo_manager),
            TodoReadTool(todo_manager),
        ])

    return tools
