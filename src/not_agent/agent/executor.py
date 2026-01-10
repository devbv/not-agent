"""Tool executor - Handles tool calls from LLM."""

from typing import Any

from not_agent.tools import BaseTool, ToolResult, get_all_tools


class ToolExecutor:
    """Executes tools based on LLM requests."""

    def __init__(self, tools: list[BaseTool] | None = None) -> None:
        self.tools = {tool.name: tool for tool in (tools or get_all_tools())}
        self.require_approval_for_modifications = True
        self.conversation_history: list[dict[str, Any]] = []

    def get_tool_definitions(self) -> list[dict[str, Any]]:
        """Get tool definitions for Anthropic API."""
        return [tool.to_anthropic_tool() for tool in self.tools.values()]

    def set_conversation_history(self, messages: list[dict[str, Any]]) -> None:
        """Update conversation history for approval checking."""
        self.conversation_history = messages

    def _check_approval_given(self, tool_name: str, tool_input: dict[str, Any]) -> tuple[bool, str]:
        """Check if user approval was given for file modifications.

        Returns:
            (approved, reason) - True if approved, False otherwise with reason
        """
        # Only check for file modification tools
        if tool_name not in ["write", "edit"]:
            return (True, "")

        # Check last few messages for AskUserQuestion + approval
        recent_messages = self.conversation_history[-10:] if len(self.conversation_history) > 10 else self.conversation_history

        # Look for AskUserQuestion tool use followed by user approval
        found_ask_user = False
        found_approval = False

        for msg in recent_messages:
            content = msg.get("content", [])

            # Check for AskUserQuestion in assistant messages
            if msg.get("role") == "assistant" and isinstance(content, list):
                for item in content:
                    if isinstance(item, dict) and item.get("type") == "tool_use":
                        if item.get("name") == "AskUserQuestion":
                            found_ask_user = True
                    elif hasattr(item, "name") and item.name == "AskUserQuestion":
                        found_ask_user = True

            # Check for approval in tool results (user responses to AskUserQuestion)
            if msg.get("role") == "user" and isinstance(content, list):
                for item in content:
                    if isinstance(item, dict) and item.get("type") == "tool_result":
                        result_content = item.get("content", "")
                        result_lower = str(result_content).lower()

                        # Check if user approved (various approval keywords)
                        approval_keywords = [
                            "yes", "proceed", "확인", "진행", "네", "저장",
                            "create", "생성", "만들", "수정", "edit", "ok", "okay"
                        ]

                        # Also check for rejection keywords to be more explicit
                        rejection_keywords = ["no", "cancel", "아니", "취소", "don't"]

                        # If any rejection keyword found, definitely not approved
                        if any(keyword in result_lower for keyword in rejection_keywords):
                            found_approval = False
                            break

                        # If any approval keyword found, mark as approved
                        if any(keyword in result_lower for keyword in approval_keywords):
                            found_approval = True

        if found_ask_user and found_approval:
            return (True, "")

        if not found_ask_user:
            return (False,
                    f"POLICY VIOLATION: You must use AskUserQuestion before using {tool_name}. "
                    f"Ask user for approval first, then proceed based on their response.")

        return (False,
                f"POLICY VIOLATION: User did not approve the {tool_name} operation. "
                f"You asked via AskUserQuestion but user declined or did not approve.")

    def execute(self, tool_name: str, tool_input: dict[str, Any]) -> ToolResult:
        """Execute a tool by name with given input."""
        if tool_name not in self.tools:
            return ToolResult(
                success=False,
                output="",
                error=f"Unknown tool: {tool_name}",
            )

        # Check approval for file modification tools
        if self.require_approval_for_modifications:
            approved, reason = self._check_approval_given(tool_name, tool_input)
            if not approved:
                return ToolResult(
                    success=False,
                    output="",
                    error=reason,
                )

        tool = self.tools[tool_name]
        return tool.execute(**tool_input)
