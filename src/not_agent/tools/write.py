"""Write tool - Write content to a file."""

from pathlib import Path
from typing import Any

from .base import BaseTool, ToolResult


class WriteTool(BaseTool):
    """Tool for writing content to files."""

    @property
    def name(self) -> str:
        return "write"

    @property
    def description(self) -> str:
        return (
            "Write content to a file. "
            "Creates the file if it doesn't exist, overwrites if it does."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "file_path": {
                "type": "string",
                "description": "The absolute path to the file to write",
                "required": True,
            },
            "content": {
                "type": "string",
                "description": "The content to write to the file",
                "required": True,
            },
        }

    def execute(
        self,
        file_path: str,
        content: str,
        **kwargs: Any,
    ) -> ToolResult:
        """Write content to a file."""
        try:
            path = Path(file_path)

            # Create parent directories if they don't exist
            path.parent.mkdir(parents=True, exist_ok=True)

            # Write the content
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)

            return ToolResult(
                success=True,
                output=f"Successfully wrote {len(content)} characters to {file_path}",
            )

        except PermissionError:
            return ToolResult(
                success=False,
                output="",
                error=f"Permission denied: {file_path}",
            )
        except Exception as e:
            return ToolResult(
                success=False,
                output="",
                error=f"Error writing file: {e}",
            )
