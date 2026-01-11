"""Grep tool - Search file contents."""

import re
from pathlib import Path
from typing import Any

from .base import BaseTool, ToolResult
from .registry import register_tool


@register_tool
class GrepTool(BaseTool):
    """Tool for searching file contents with regex."""

    name = "grep"
    description = (
        "Search file contents with regex, returns matches with file:line. "
        "Use when: user asks to find code containing specific text/pattern."
    )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "pattern": {
                "type": "string",
                "description": "The regex pattern to search for",
                "required": True,
            },
            "path": {
                "type": "string",
                "description": "File or directory to search in",
                "required": False,
            },
            "glob": {
                "type": "string",
                "description": "Glob pattern to filter files (e.g., '*.py')",
                "required": False,
            },
            "case_insensitive": {
                "type": "boolean",
                "description": "Case insensitive search (default: False)",
                "required": False,
            },
        }

    def execute(
        self,
        pattern: str,
        path: str | None = None,
        glob: str | None = None,
        case_insensitive: bool = False,
        **kwargs: Any,
    ) -> ToolResult:
        """Search for pattern in files."""
        try:
            # Compile regex
            flags = re.IGNORECASE if case_insensitive else 0
            try:
                regex = re.compile(pattern, flags)
            except re.error as e:
                return ToolResult(
                    success=False,
                    output="",
                    error=f"Invalid regex pattern: {e}",
                )

            base_path = Path(path) if path else Path.cwd()

            if not base_path.exists():
                return ToolResult(
                    success=False,
                    output="",
                    error=f"Path not found: {base_path}",
                )

            # Get files to search
            if base_path.is_file():
                files = [base_path]
            else:
                glob_pattern = glob or "**/*"
                files = [f for f in base_path.glob(glob_pattern) if f.is_file()]

            matches = []
            for file_path in files:
                try:
                    with open(file_path, encoding="utf-8") as f:
                        for line_num, line in enumerate(f, 1):
                            if regex.search(line):
                                matches.append(f"{file_path}:{line_num}:{line.rstrip()}")
                except (UnicodeDecodeError, PermissionError):
                    # Skip binary files or files we can't read
                    continue

            if not matches:
                return ToolResult(
                    success=True,
                    output="No matches found.",
                )

            # Limit output
            max_matches = 100
            if len(matches) > max_matches:
                output = "\n".join(matches[:max_matches])
                output += f"\n... and {len(matches) - max_matches} more matches"
            else:
                output = "\n".join(matches)

            return ToolResult(
                success=True,
                output=output,
            )

        except Exception as e:
            return ToolResult(
                success=False,
                output="",
                error=f"Error searching: {e}",
            )
