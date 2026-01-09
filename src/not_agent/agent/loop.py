"""Agent loop - Main agent execution loop."""

from typing import Any

from anthropic import Anthropic
from anthropic.types import Message, ToolUseBlock, TextBlock

from not_agent.tools import ToolResult
from .executor import ToolExecutor


class AgentLoop:
    """Main agent loop that handles conversation and tool execution."""

    def __init__(
        self,
        model: str = "claude-opus-4-5-20251101",
        max_turns: int = 20,
    ) -> None:
        self.client = Anthropic()
        self.model = model
        self.max_turns = max_turns
        self.executor = ToolExecutor()
        self.messages: list[dict[str, Any]] = []
        self.system_prompt = self._get_system_prompt()

    def _get_system_prompt(self) -> str:
        """Get the system prompt for the agent."""
        return """You are a coding agent that takes action using tools.

IMPORTANT: You MUST use tools to complete tasks. Do NOT just explain how to do something - actually DO it using your tools.

Available tools:
- read: Read file contents
- write: Write/create files
- edit: Edit files by replacing text
- glob: Find files by pattern (e.g., "**/*.py")
- grep: Search file contents with regex
- bash: Execute shell commands

RULES:
1. When asked to find/search something → USE the glob or grep tool immediately
2. When asked to read/show a file → USE the read tool immediately
3. When asked to create/modify a file → USE write or edit tool immediately
4. When asked to run a command → USE the bash tool immediately
5. NEVER explain methods or options - just take action
6. After using tools, summarize what you found/did

Always read files before editing them.
Be careful with destructive bash commands."""

    def run(self, user_message: str) -> str:
        """Run the agent loop with a user message."""
        self.messages.append({"role": "user", "content": user_message})

        for turn in range(self.max_turns):
            # Force tool use on first turn
            response = self._call_llm(force_tool=(turn == 0))

            # Check if there are tool calls
            tool_uses = [
                block for block in response.content if isinstance(block, ToolUseBlock)
            ]

            if not tool_uses:
                # No tool calls, return the text response
                text_content = [
                    block.text
                    for block in response.content
                    if isinstance(block, TextBlock)
                ]
                return "\n".join(text_content)

            # Process tool calls
            self.messages.append({"role": "assistant", "content": response.content})

            tool_results = []
            for tool_use in tool_uses:
                result = self.executor.execute(tool_use.name, tool_use.input)
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": tool_use.id,
                        "content": self._format_tool_result(result),
                    }
                )

            self.messages.append({"role": "user", "content": tool_results})

        return "Max turns reached. Please continue with a new message."

    def _call_llm(self, force_tool: bool = False) -> Message:
        """Call the LLM with current messages."""
        kwargs: dict[str, Any] = {
            "model": self.model,
            "max_tokens": 4096,
            "system": self.system_prompt,
            "tools": self.executor.get_tool_definitions(),
            "messages": self.messages,
        }

        # Force tool use on first turn to encourage action
        if force_tool:
            kwargs["tool_choice"] = {"type": "any"}

        return self.client.messages.create(**kwargs)

    def _format_tool_result(self, result: ToolResult) -> str:
        """Format a tool result for the LLM."""
        if result.success:
            return result.output
        else:
            return f"Error: {result.error}\n{result.output}".strip()

    def reset(self) -> None:
        """Reset the conversation history."""
        self.messages = []
