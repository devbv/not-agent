"""Confirm Write tool - Write the content shown in previous turn."""

from pathlib import Path
from typing import Any

from .base import BaseTool, ToolResult


class ConfirmWriteTool(BaseTool):
    """Tool for confirming write - STEP 2 of 2-step write process."""

    # Class variable to store draft info across turns
    _pending_draft: dict[str, str] = {}

    @property
    def name(self) -> str:
        return "confirm_write"

    @property
    def description(self) -> str:
        return (
            "STEP 2: Confirm and execute the write operation. "
            "Use this AFTER you've called draft_write() and shown the complete content. "
            "This will write the content from your previous text response to the file."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "file_path": {
                "type": "string",
                "description": "The file path (must match the draft_write call)",
                "required": True,
            },
            "content": {
                "type": "string",
                "description": (
                    "The complete content to write. "
                    "OPTIONAL: If omitted, will use the text from your current response automatically."
                ),
                "required": False,
            },
        }

    def get_approval_description(self, file_path: str, content: str, **kwargs: Any) -> str:
        """ConfirmWriteTool은 항상 승인 필요"""
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
        content: str = "",  # Made optional with default
        **kwargs: Any,
    ) -> ToolResult:
        """Write the content to file."""
        # Validate content is not empty
        if not content or not content.strip():
            return ToolResult(
                success=False,
                output="",
                error=(
                    "Content is empty. Please provide content either:\n"
                    "1. In the content parameter, OR\n"
                    "2. As text in your current response (will be auto-filled)"
                ),
            )

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
