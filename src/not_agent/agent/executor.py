"""Tool executor - Handles tool calls from LLM."""

import asyncio
from typing import Any

from not_agent.tools import BaseTool, ToolResult, get_all_tools

from .approval import ApprovalManager


class ToolExecutor:
    """Executes tools based on LLM requests with optional approval plugin."""

    def __init__(
        self,
        tools: list[BaseTool] | None = None,
        approval_manager: ApprovalManager | None = None,
    ) -> None:
        """
        Initialize tool executor.

        Args:
            tools: List of tools to make available (defaults to all tools)
            approval_manager: Optional approval plugin for file modifications
        """
        self.tools = {tool.name: tool for tool in (tools or get_all_tools())}
        self.approval = approval_manager

    def get_tool_definitions(self) -> list[dict[str, Any]]:
        """Get tool definitions for Anthropic API."""
        return [tool.to_anthropic_tool() for tool in self.tools.values()]

    async def execute_async(self, tool_name: str, tool_input: dict[str, Any]) -> ToolResult:
        """Execute a tool by name with given input (async version)."""
        if tool_name not in self.tools:
            return ToolResult(
                success=False,
                output="",
                error=f"Unknown tool: {tool_name}",
            )

        tool = self.tools[tool_name]

        # === Plugin Hook: Approval ===
        if self.approval and self.approval.enabled:
            try:
                approval_desc = tool.get_approval_description(**tool_input)

                if approval_desc:  # Tool이 승인 필요하다고 함
                    approved = self.approval.request(tool.name, approval_desc)

                    if not approved:
                        return ToolResult(
                            success=False,
                            output="User denied permission for this action. "
                                   "Please ask what they would like to do instead.",
                            error=None,
                        )
            except Exception as e:
                # get_approval_description 실행 실패 시 안전하게 계속 진행
                print(f"[WARNING] Failed to check approval: {e}")

        # === 실제 도구 실행 ===
        try:
            return tool.execute(**tool_input)
        except TypeError as e:
            # Better error message for missing parameters
            error_msg = str(e)
            if "missing" in error_msg and "required" in error_msg:
                # Provide detailed guidance based on tool type
                guidance = ""
                if tool_name == "write":
                    guidance = (
                        "\n\nFor 'write' tool, you MUST provide:\n"
                        "- file_path: The path to the file\n"
                        "- content: The FULL content to write to the file\n\n"
                        "Example:\n"
                        "write(file_path='/path/to/file.md', content='Full content here...')\n\n"
                        "CRITICAL ERROR: You called write without the 'content' parameter.\n"
                        "This suggests you're trying to stream content, but that doesn't work with tools.\n\n"
                        "What you MUST do instead:\n"
                        "1. Compose the ENTIRE file content first (in your response text if needed)\n"
                        "2. Then make ONE write tool call with BOTH file_path AND complete content\n"
                        "3. The content parameter must contain the full text, not be empty or missing\n\n"
                        "Try again with the complete content included in the tool call."
                    )
                elif tool_name == "edit":
                    guidance = (
                        "\n\nFor 'edit' tool, you MUST provide:\n"
                        "- file_path: The path to the file\n"
                        "- old_string: The exact text to replace\n"
                        "- new_string: The replacement text"
                    )

                return ToolResult(
                    success=False,
                    output="",
                    error=f"Tool '{tool_name}' called with missing parameters: {error_msg}\n"
                    f"Provided parameters: {list(tool_input.keys())}\n"
                    f"Please make sure to provide all required parameters.{guidance}",
                )
            raise
        except Exception as e:
            return ToolResult(
                success=False,
                output="",
                error=f"Error executing {tool_name}: {e}",
            )

    def execute(self, tool_name: str, tool_input: dict[str, Any]) -> ToolResult:
        """Execute a tool by name with given input (sync wrapper)."""
        # Check if we're already in an event loop
        try:
            asyncio.get_running_loop()
            # Already in a loop - can't use run_until_complete
            # Use synchronous version instead
            return self._execute_sync(tool_name, tool_input)
        except RuntimeError:
            # No running loop - create one
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

            return loop.run_until_complete(self.execute_async(tool_name, tool_input))

    def _execute_sync(self, tool_name: str, tool_input: dict[str, Any]) -> ToolResult:
        """Synchronous version for when we're already in an event loop."""
        if tool_name not in self.tools:
            return ToolResult(
                success=False,
                output="",
                error=f"Unknown tool: {tool_name}",
            )

        tool = self.tools[tool_name]

        # Plugin Hook: Approval (sync version)
        if self.approval and self.approval.enabled:
            try:
                approval_desc = tool.get_approval_description(**tool_input)

                if approval_desc:
                    approved = self.approval.request(tool.name, approval_desc)

                    if not approved:
                        return ToolResult(
                            success=False,
                            output="User denied permission for this action. "
                                   "Please ask what they would like to do instead.",
                            error=None,
                        )
            except Exception as e:
                print(f"[WARNING] Failed to check approval: {e}")

        # Execute tool
        try:
            return tool.execute(**tool_input)
        except TypeError as e:
            error_msg = str(e)
            if "missing" in error_msg and "required" in error_msg:
                guidance = ""
                if tool_name == "write":
                    guidance = (
                        "\n\nFor 'write' tool, you MUST provide:\n"
                        "- file_path: The path to the file\n"
                        "- content: The FULL content to write to the file\n\n"
                        "Example:\n"
                        "write(file_path='/path/to/file.md', content='Full content here...')\n\n"
                        "CRITICAL ERROR: You called write without the 'content' parameter.\n"
                        "This suggests you're trying to stream content, but that doesn't work with tools.\n\n"
                        "What you MUST do instead:\n"
                        "1. Compose the ENTIRE file content first (in your response text if needed)\n"
                        "2. Then make ONE write tool call with BOTH file_path AND complete content\n"
                        "3. The content parameter must contain the full text, not be empty or missing\n\n"
                        "Try again with the complete content included in the tool call."
                    )
                elif tool_name == "edit":
                    guidance = (
                        "\n\nFor 'edit' tool, you MUST provide:\n"
                        "- file_path: The path to the file\n"
                        "- old_string: The exact text to replace\n"
                        "- new_string: The replacement text"
                    )

                return ToolResult(
                    success=False,
                    output="",
                    error=f"Tool '{tool_name}' called with missing parameters: {error_msg}\n"
                    f"Provided parameters: {list(tool_input.keys())}\n"
                    f"Please make sure to provide all required parameters.{guidance}",
                )
            raise
        except Exception as e:
            return ToolResult(
                success=False,
                output="",
                error=f"Error executing {tool_name}: {e}",
            )
