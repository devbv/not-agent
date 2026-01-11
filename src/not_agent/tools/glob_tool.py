"""Glob tool - Find files by pattern."""

from pathlib import Path
from typing import Any

from .base import BaseTool, ToolResult
from .registry import register_tool


@register_tool
class GlobTool(BaseTool):
    """Tool for finding files by glob pattern."""

    name = "glob"
    description = (
        "Find files by glob pattern ('**/*.py', 'src/**/*.ts'). "
        "Use when: user asks to find/search for files by name or extension."
    )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "pattern": {
                "type": "string",
                "description": "The glob pattern to match files against",
                "required": True,
            },
            "path": {
                "type": "string",
                "description": "The directory to search in (default: current directory)",
                "required": False,
            },
        }

    def execute(
        self,
        pattern: str,
        path: str | None = None,
        **kwargs: Any,
    ) -> ToolResult:
        """Find files matching the glob pattern."""
        try:
            base_path = Path(path) if path else Path.cwd()

            if not base_path.exists():
                return ToolResult(
                    success=False,
                    output="",
                    error=f"Directory not found: {base_path}",
                )

            if not base_path.is_dir():
                return ToolResult(
                    success=False,
                    output="",
                    error=f"Not a directory: {base_path}",
                )

            # Find matching files
            matches = sorted(base_path.glob(pattern))

            # Filter out directories, keep only files
            files = [str(m) for m in matches if m.is_file()]

            if not files:
                return ToolResult(
                    success=True,
                    output="No files found matching pattern.",
                )

            # Sort by modification time (newest first)
            files_with_mtime = [(f, Path(f).stat().st_mtime) for f in files]
            files_with_mtime.sort(key=lambda x: x[1], reverse=True)
            sorted_files = [f[0] for f in files_with_mtime]

            return ToolResult(
                success=True,
                output="\n".join(sorted_files),
            )

        except Exception as e:
            return ToolResult(
                success=False,
                output="",
                error=f"Error searching files: {e}",
            )
