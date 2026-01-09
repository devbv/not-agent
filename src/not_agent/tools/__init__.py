"""Tools module - File operations, bash execution, etc."""

from .base import BaseTool, ToolResult
from .bash import BashTool
from .edit import EditTool
from .glob_tool import GlobTool
from .grep import GrepTool
from .read import ReadTool
from .write import WriteTool

__all__ = [
    "BaseTool",
    "ToolResult",
    "BashTool",
    "EditTool",
    "GlobTool",
    "GrepTool",
    "ReadTool",
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
    ]
