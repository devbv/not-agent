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
        model: str = "claude-haiku-4-5-20251001",
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
- WebSearch: Search the web for information
- WebFetch: Fetch URL content and convert HTML to plain text

RULES:
1. When asked to find/search something → USE the glob or grep tool immediately
2. When asked to read/show a file → USE the read tool immediately
3. When asked to create/modify a file → USE write or edit tool immediately
4. When asked to run a command → USE the bash tool immediately
5. When asked about recent/latest information → USE WebSearch immediately
6. When asked to fetch/read a URL or web page → USE WebFetch to get the text, then analyze it
7. NEVER explain methods or options - just take action
8. After using tools, summarize what you found/did

Always read files before editing them.
Be careful with destructive bash commands."""

    def run(self, user_message: str) -> str:
        """Run the agent loop with a user message."""
        self.messages.append({"role": "user", "content": user_message})

        print(f"\n{'='*60}")
        print(f"[AGENT LOOP] Starting with user message: {user_message[:100]}...")
        print(f"{'='*60}\n")

        for turn in range(self.max_turns):
            print(f"\n{'─'*60}")
            print(f"[TURN {turn + 1}/{self.max_turns}]")
            print(f"{'─'*60}")

            # Force tool use on first turn
            response = self._call_llm(force_tool=(turn == 0))

            # Check if there are tool calls
            tool_uses = [
                block for block in response.content if isinstance(block, ToolUseBlock)
            ]

            if not tool_uses:
                # No tool calls, return the text response
                print(f"\n[COMPLETE] No tool calls, returning text response")
                text_content = [
                    block.text
                    for block in response.content
                    if isinstance(block, TextBlock)
                ]
                return "\n".join(text_content)

            # Process tool calls
            self.messages.append({"role": "assistant", "content": response.content})

            print(f"\n[TOOL EXECUTION] Executing {len(tool_uses)} tool(s)...")

            tool_results = []
            for idx, tool_use in enumerate(tool_uses):
                print(f"\n  Tool {idx + 1}: {tool_use.name}")
                print(f"    Input: {str(tool_use.input)[:150]}...")

                result = self.executor.execute(tool_use.name, tool_use.input)

                print(f"    Success: {result.success}")
                if result.success:
                    print(f"    Output: {result.output[:200]}...")
                else:
                    print(f"    Error: {result.error}")

                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": tool_use.id,
                        "content": self._format_tool_result(result),
                    }
                )

            self.messages.append({"role": "user", "content": tool_results})
            print(f"\n[FEEDBACK] Tool results added to conversation")

        print(f"\n{'='*60}")
        print(f"[MAX TURNS] Reached maximum turns ({self.max_turns})")
        print(f"{'='*60}\n")
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

        # Show LLM request
        print(f"\n[LLM REQUEST]")
        for i, msg in enumerate(self.messages, 1):
            role = msg['role']
            content = msg['content']

            if isinstance(content, str):
                preview = content[:150] + "..." if len(content) > 150 else content
                print(f"  #{i} {role.upper()}: {preview}")
            elif isinstance(content, list):
                # Check if it's tool results or assistant content
                if all(isinstance(item, dict) and item.get('type') == 'tool_result' for item in content):
                    print(f"  #{i} {role.upper()}: [Tool Results x{len(content)}]")
                    for j, item in enumerate(content[:2], 1):  # Show first 2 tool results
                        result_preview = item['content'][:100] + "..." if len(item['content']) > 100 else item['content']
                        print(f"      Result {j}: {result_preview}")
                    if len(content) > 2:
                        print(f"      ... and {len(content) - 2} more")
                else:
                    # Assistant message with mixed content
                    for item in content:
                        if hasattr(item, 'type'):
                            if item.type == 'tool_use':
                                print(f"  #{i} {role.upper()}: Tool={item.name}, Input={str(item.input)[:80]}...")
                            elif item.type == 'text':
                                print(f"  #{i} {role.upper()}: {item.text[:100]}...")

        response = self.client.messages.create(**kwargs)

        # Show LLM response
        print(f"\n[LLM RESPONSE]")
        for i, block in enumerate(response.content, 1):
            if isinstance(block, ToolUseBlock):
                print(f"  #{i} ToolUse: {block.name}")
                print(f"      Input: {str(block.input)[:150]}...")
            elif isinstance(block, TextBlock):
                print(f"  #{i} Text: {block.text[:150]}...")

        return response

    def _format_tool_result(self, result: ToolResult) -> str:
        """Format a tool result for the LLM."""
        if result.success:
            return result.output
        else:
            return f"Error: {result.error}\n{result.output}".strip()

    def reset(self) -> None:
        """Reset the conversation history."""
        self.messages = []
