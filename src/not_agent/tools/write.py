"""Write tool - Write content to a file."""

import difflib
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
                "description": (
                    "The content to write to the file"
                ),
                "required": True,
            },
        }

    def generate_diff(self, file_path: str, new_content: str) -> str | None:
        """기존 파일과 새 콘텐츠 비교 diff 생성

        Args:
            file_path: 대상 파일 경로
            new_content: 새로운 파일 내용

        Returns:
            diff 문자열 (기존 파일이 있을 경우) 또는 None (새 파일)
        """
        path = Path(file_path)
        if not path.exists():
            return None  # 새 파일은 diff 없음

        try:
            old_content = path.read_text(encoding="utf-8")
        except Exception:
            return None  # 읽기 실패 시 diff 생략

        # unified diff 생성
        diff_lines = list(difflib.unified_diff(
            old_content.splitlines(keepends=True),
            new_content.splitlines(keepends=True),
            fromfile=f"a/{path.name}",
            tofile=f"b/{path.name}",
        ))

        if not diff_lines:
            return None  # 변경사항 없음

        return "".join(diff_lines)

    def get_approval_description(self, file_path: str, content: str, **kwargs: Any) -> str:
        """WriteTool은 항상 승인 필요 - diff 포함"""
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
