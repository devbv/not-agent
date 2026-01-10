"""Bash tool - Execute shell commands."""

import subprocess
from typing import Any

from .base import BaseTool, ToolResult


class BashTool(BaseTool):
    """Tool for executing shell commands."""

    # 위험한 명령어 패턴
    DANGEROUS_PATTERNS = [
        "rm ",
        "mv ",
        "dd ",
        "format",
        ">",  # 리다이렉션
        ">>",  # 추가 리다이렉션
        "|",  # 파이프 (일부 위험할 수 있음)
    ]

    @property
    def name(self) -> str:
        return "bash"

    @property
    def description(self) -> str:
        return (
            "Execute a bash command. "
            "Use for running scripts, git commands, package managers, etc."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "command": {
                "type": "string",
                "description": "The bash command to execute",
                "required": True,
            },
            "timeout": {
                "type": "integer",
                "description": "Timeout in seconds (default: 120)",
                "required": False,
            },
            "cwd": {
                "type": "string",
                "description": "Working directory for the command",
                "required": False,
            },
        }

    def get_approval_description(
        self,
        command: str,
        timeout: int = 120,
        cwd: str | None = None,
        **kwargs: Any,
    ) -> str | None:
        """위험한 명령어만 승인 요청"""
        # 위험한 패턴 체크
        for pattern in self.DANGEROUS_PATTERNS:
            if pattern in command:
                return f"Run command: {command}"

        # 안전한 명령어는 승인 불필요
        return None

    def execute(
        self,
        command: str,
        timeout: int = 120,
        cwd: str | None = None,
        **kwargs: Any,
    ) -> ToolResult:
        """Execute a bash command."""
        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=cwd,
            )

            # Combine stdout and stderr
            output_parts = []
            if result.stdout:
                output_parts.append(result.stdout)
            if result.stderr:
                output_parts.append(f"[stderr]\n{result.stderr}")

            output = "\n".join(output_parts) if output_parts else "(no output)"

            # Truncate if too long
            max_length = 30000
            if len(output) > max_length:
                output = output[:max_length] + "\n... (output truncated)"

            if result.returncode != 0:
                return ToolResult(
                    success=False,
                    output=output,
                    error=f"Command exited with code {result.returncode}",
                )

            return ToolResult(
                success=True,
                output=output,
            )

        except subprocess.TimeoutExpired:
            return ToolResult(
                success=False,
                output="",
                error=f"Command timed out after {timeout} seconds",
            )
        except Exception as e:
            return ToolResult(
                success=False,
                output="",
                error=f"Error executing command: {e}",
            )
