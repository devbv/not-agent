"""Write tool - Write content to a file."""

import difflib
from pathlib import Path
from typing import Any

from .base import BaseTool, ToolResult
from .registry import register_tool


@register_tool
class WriteTool(BaseTool):
    """Tool for writing content to files."""

    name = "write"
    description = (
        "Write content to a file (creates or overwrites). "
        "Use when: user asks to create a new file. "
        "CRITICAL: Provide BOTH file_path AND complete content in a single call."
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
                "description": (
                    "The content to write to the file"
                ),
                "required": True,
            },
        }

    def generate_diff(self, file_path: str, new_content: str) -> str | None:
        """Generate diff comparing existing file with new content.

        Args:
            file_path: Target file path
            new_content: New file content

        Returns:
            Diff string (if file exists) or None (new file)
        """
        path = Path(file_path)
        if not path.exists():
            return None  # No diff for new files

        try:
            old_content = path.read_text(encoding="utf-8")
        except Exception:
            return None  # Skip diff on read failure

        # Generate unified diff
        diff_lines = list(difflib.unified_diff(
            old_content.splitlines(keepends=True),
            new_content.splitlines(keepends=True),
            fromfile=f"a/{path.name}",
            tofile=f"b/{path.name}",
        ))

        if not diff_lines:
            return None  # No changes

        return "".join(diff_lines)

    def get_approval_description(self, file_path: str, content: str, **kwargs: Any) -> str:
        """WriteTool always requires approval - includes diff."""
        lines = len(content.split("\n"))
        path = Path(file_path)
        exists = path.exists()

        if exists:
            return f"Overwrite {file_path} ({lines} lines)"
        else:
            return f"Write {lines} lines to {file_path} (new file)"

    def execute(
        self,
        file_path: str,
        content: str = '',
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
                output=f"Successfully wrote to {file_path}",
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
