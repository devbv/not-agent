"""Tool executor - Handles tool calls from LLM."""

from typing import Any

from not_agent.tools import BaseTool, ToolResult, get_all_tools


class ToolExecutor:
    """Executes tools based on LLM requests."""

    def __init__(self, tools: list[BaseTool] | None = None) -> None:
        self.tools = {tool.name: tool for tool in (tools or get_all_tools())}

    def get_tool_definitions(self) -> list[dict[str, Any]]:
        """Get tool definitions for Anthropic API."""
        return [tool.to_anthropic_tool() for tool in self.tools.values()]

    def execute(self, tool_name: str, tool_input: dict[str, Any]) -> ToolResult:
        """Execute a tool by name with given input."""
        if tool_name not in self.tools:
            return ToolResult(
                success=False,
                output="",
                error=f"Unknown tool: {tool_name}",
            )

        tool = self.tools[tool_name]
        return tool.execute(**tool_input)
