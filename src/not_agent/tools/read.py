"""Read tool - Read file contents."""

from pathlib import Path
from typing import Any

from .base import BaseTool, ToolResult
from .registry import register_tool


@register_tool
class ReadTool(BaseTool):
    """Tool for reading file contents."""

    name = "read"
    description = (
        "Read file contents with line numbers. "
        "Use when: user asks to read/show/view a file, or you need to understand code before editing."
    )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "file_path": {
                "type": "string",
                "description": "The absolute path to the file to read",
                "required": True,
            },
            "offset": {
                "type": "integer",
                "description": "Line number to start reading from (1-based)",
                "required": False,
            },
            "limit": {
                "type": "integer",
                "description": "Maximum number of lines to read",
                "required": False,
            },
        }

    def execute(
        self,
        file_path: str,
        offset: int | None = None,
        limit: int | None = None,
        **kwargs: Any,
    ) -> ToolResult:
        """Read file contents."""
        try:
            path = Path(file_path)

            if not path.exists():
                return ToolResult(
                    success=False,
                    output="",
                    error=f"File not found: {file_path}",
                )

            if not path.is_file():
                return ToolResult(
                    success=False,
                    output="",
                    error=f"Not a file: {file_path}",
                )

            with open(path, encoding="utf-8") as f:
                lines = f.readlines()

            # Apply offset and limit
            start = (offset - 1) if offset and offset > 0 else 0
            end = (start + limit) if limit else None
            selected_lines = lines[start:end]

            # Format with line numbers
            output_lines = []
            for i, line in enumerate(selected_lines, start=start + 1):
                output_lines.append(f"{i:6d}\t{line.rstrip()}")

            return ToolResult(
                success=True,
                output="\n".join(output_lines),
            )

        except PermissionError:
            return ToolResult(
                success=False,
                output="",
                error=f"Permission denied: {file_path}",
            )
        except UnicodeDecodeError:
            return ToolResult(
                success=False,
                output="",
                error=f"Cannot read file (binary or unknown encoding): {file_path}",
            )
        except Exception as e:
            return ToolResult(
                success=False,
                output="",
                error=f"Error reading file: {e}",
            )
