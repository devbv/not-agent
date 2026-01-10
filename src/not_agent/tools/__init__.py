"""Tools module - File operations, bash execution, web search, etc."""

from .ask_user import AskUserQuestionTool
from .base import BaseTool, ToolResult
from .bash import BashTool
from .edit import EditTool
from .glob_tool import GlobTool
from .grep import GrepTool
from .read import ReadTool
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
    "WebFetchTool",
    "WebSearchTool",
    "WriteTool",
]


def get_all_tools() -> list[BaseTool]:
    """Get instances of all available tools."""
    return [
        ReadTool(),
        WriteTool(),
        EditTool(),
        GlobTool(),
        GrepTool(),
        BashTool(),
        WebSearchTool(),
        WebFetchTool(),
        AskUserQuestionTool(),
    ]
