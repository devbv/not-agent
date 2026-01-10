"""Tools module - File operations, bash execution, web search, etc."""

from .ask_user import AskUserQuestionTool
from .base import BaseTool, ToolResult
from .bash import BashTool
from .confirm_write import ConfirmWriteTool
from .draft_write import DraftWriteTool
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
    "ConfirmWriteTool",
    "DraftWriteTool",
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
        # WriteTool removed - use draft_write + auto-confirm instead
        DraftWriteTool(),
        # ConfirmWriteTool removed - auto-triggered by system, not LLM
        EditTool(),
        GlobTool(),
        GrepTool(),
        BashTool(),
        WebSearchTool(),
        WebFetchTool(),
        AskUserQuestionTool(),
    ]
