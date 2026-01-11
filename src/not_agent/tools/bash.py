"""Bash tool - Execute shell commands."""

import subprocess
from typing import Any

from .base import BaseTool, ToolResult
from .registry import register_tool


@register_tool
class BashTool(BaseTool):
    """Tool for executing shell commands."""

    name = "bash"
    description = (
        "Execute a bash command (scripts, git, npm, etc.). "
        "Use when: user asks to run a command or execute something in terminal."
    )

    # Dangerous command patterns
    DANGEROUS_PATTERNS = [
        "rm ",
        "mv ",
        "dd ",
        "format",
        ">",  # Redirection
        ">>",  # Append redirection
        "|",  # Pipe (can be dangerous in some cases)
    ]

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
        """Request approval only for dangerous commands."""
        # Check for dangerous patterns
        for pattern in self.DANGEROUS_PATTERNS:
            if pattern in command:
                return f"Run command: {command}"

        # Safe commands don't need approval
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
