"""Tool executor - Handles tool calls from LLM."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from not_agent.tools import BaseTool, ToolResult, get_all_tools

if TYPE_CHECKING:
    from .approval import ApprovalManager
    from .permissions import PermissionManager


class ToolExecutor:
    """Executes tools based on LLM requests with optional permission management."""

    def __init__(
        self,
        tools: list[BaseTool] | None = None,
        permission_manager: PermissionManager | None = None,
        approval_manager: ApprovalManager | None = None,  # 하위 호환
    ) -> None:
        """
        Initialize tool executor.

        Args:
            tools: List of tools to make available (defaults to all tools)
            permission_manager: 규칙 기반 권한 관리자 (권장)
            approval_manager: 기존 승인 플러그인 (하위 호환용)
        """
        self.tools = {tool.name: tool for tool in (tools or get_all_tools())}

        # PermissionManager 우선 사용
        if permission_manager is not None:
            self.permission = permission_manager
        elif approval_manager is not None:
            # 기존 ApprovalManager의 내부 PermissionManager 사용
            self.permission = approval_manager._manager
        else:
            self.permission = None

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

        # === Plugin Hook: Permission Check ===
        if self.permission and self.permission.enabled:
            try:
                approval_desc = tool.get_approval_description(**tool_input)

                if approval_desc:  # Tool이 승인 필요하다고 함
                    # context 구성 (도구 입력 전체)
                    context = dict(tool_input)

                    # write 도구의 경우 diff 생성
                    diff = None
                    if tool.name == "write" and hasattr(tool, "generate_diff"):
                        diff = tool.generate_diff(
                            tool_input.get("file_path", ""),
                            tool_input.get("content", ""),
                        )

                    # 권한 확인 (자동 승인/거부/질의)
                    approved = self.permission.check(
                        tool.name, approval_desc, context, diff
                    )

                    if not approved:
                        return ToolResult(
                            success=False,
                            output="User denied permission for this action. "
                                   "Please ask what they would like to do instead.",
                            error=None,
                        )
            except Exception as e:
                # get_approval_description 실행 실패 시 안전하게 계속 진행
                print(f"[WARNING] Failed to check permission: {e}")

        # === 실제 도구 실행 ===
        try:
            return tool.execute(**tool_input)
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

        # Plugin Hook: Permission Check (sync version)
        if self.permission and self.permission.enabled:
            try:
                approval_desc = tool.get_approval_description(**tool_input)

                if approval_desc:
                    # context 구성 (도구 입력 전체)
                    context = dict(tool_input)

                    # write 도구의 경우 diff 생성
                    diff = None
                    if tool.name == "write" and hasattr(tool, "generate_diff"):
                        diff = tool.generate_diff(
                            tool_input.get("file_path", ""),
                            tool_input.get("content", ""),
                        )

                    # 권한 확인 (자동 승인/거부/질의)
                    approved = self.permission.check(
                        tool.name, approval_desc, context, diff
                    )

                    if not approved:
                        return ToolResult(
                            success=False,
                            output="User denied permission for this action. "
                                   "Please ask what they would like to do instead.",
                            error=None,
                        )
            except Exception as e:
                print(f"[WARNING] Failed to check permission: {e}")

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
