"""Edit tool - Edit file contents by replacing text."""

from pathlib import Path
from typing import Any

from .base import BaseTool, ToolResult


class EditTool(BaseTool):
    """Tool for editing files by replacing text."""

    @property
    def name(self) -> str:
        return "edit"

    @property
    def description(self) -> str:
        return (
            "Edit a file by replacing an exact string with new content. "
            "The old_string must match exactly (including whitespace)."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "file_path": {
                "type": "string",
                "description": "The absolute path to the file to edit",
                "required": True,
            },
            "old_string": {
                "type": "string",
                "description": "The exact string to replace",
                "required": True,
            },
            "new_string": {
                "type": "string",
                "description": "The string to replace it with",
                "required": True,
            },
            "replace_all": {
                "type": "boolean",
                "description": "Replace all occurrences (default: False)",
                "required": False,
            },
        }

    def execute(
        self,
        file_path: str,
        old_string: str,
        new_string: str,
        replace_all: bool = False,
        **kwargs: Any,
    ) -> ToolResult:
        """Edit file by replacing text."""
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

            # Read current content
            with open(path, encoding="utf-8") as f:
                content = f.read()

            # Check if old_string exists
            if old_string not in content:
                return ToolResult(
                    success=False,
                    output="",
                    error=f"String not found in file: {old_string[:50]}...",
                )

            # Count occurrences
            count = content.count(old_string)

            if count > 1 and not replace_all:
                return ToolResult(
                    success=False,
                    output="",
                    error=(
                        f"Found {count} occurrences of the string. "
                        "Use replace_all=True to replace all, or provide more context."
                    ),
                )

            # Perform replacement
            if replace_all:
                new_content = content.replace(old_string, new_string)
                replaced_count = count
            else:
                new_content = content.replace(old_string, new_string, 1)
                replaced_count = 1

            # Write back
            with open(path, "w", encoding="utf-8") as f:
                f.write(new_content)

            return ToolResult(
                success=True,
                output=f"Replaced {replaced_count} occurrence(s) in {file_path}",
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
                error=f"Error editing file: {e}",
            )
