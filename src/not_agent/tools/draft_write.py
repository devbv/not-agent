"""Draft Write tool - Declare intention to write a file."""

from typing import Any

from .base import BaseTool, ToolResult


class DraftWriteTool(BaseTool):
    """Tool for declaring intent to write - STEP 1 of 2-step write process."""

    @property
    def name(self) -> str:
        return "draft_write"

    @property
    def description(self) -> str:
        return (
            "Declare your intention to write a file. "
            "After calling this, just output the complete content as TEXT in your NEXT turn. "
            "The system will automatically save your text to the file with user approval. "
            "You do NOT need to call any other tool to save."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "file_path": {
                "type": "string",
                "description": "The absolute path where the file will be written",
                "required": True,
            },
        }

    def execute(
        self,
        file_path: str,
        **kwargs: Any,
    ) -> ToolResult:
        """Store the intended file path for later use."""
        return ToolResult(
            success=True,
            output=(
                f"Draft registered for: {file_path}\n\n"
                "Please provide the COMPLETE content as text in your next response. "
                "The system will automatically save it to the file."
            ),
        )
