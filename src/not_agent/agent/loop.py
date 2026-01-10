"""Agent loop - Main agent execution loop."""

import time
from typing import Any

from anthropic import Anthropic, RateLimitError, APIError
from anthropic.types import Message, ToolUseBlock, TextBlock
from rich.console import Console

from not_agent.tools import ToolResult, TodoManager, get_all_tools
from .executor import ToolExecutor

# Debug console (shared instance)
_debug_console = Console()


class AgentLoop:
    """Main agent loop that handles conversation and tool execution."""

    def __init__(
        self,
        model: str = "claude-haiku-4-5-20251001",
        max_turns: int = 20,
        max_output_length: int = 10_000,
        max_context_tokens: int = 100_000,
        compaction_threshold: float = 0.75,
        preserve_recent_messages: int = 3,
        enable_auto_compaction: bool = True,
        executor: ToolExecutor | None = None,
        todo_manager: TodoManager | None = None,
        debug: bool = False,
    ) -> None:
        self.client = Anthropic()
        self.model = model
        self.max_turns = max_turns
        self.max_output_length = max_output_length
        self.max_context_tokens = max_context_tokens
        self.compaction_threshold = compaction_threshold
        self.preserve_recent_messages = preserve_recent_messages
        self.enable_auto_compaction = enable_auto_compaction
        self.debug = debug

        # TodoManager 인스턴스 생성 (세션별 격리)
        self.todo_manager = todo_manager or TodoManager()

        # Executor 설정 - TodoManager 주입
        if executor:
            self.executor = executor
        else:
            tools = get_all_tools(todo_manager=self.todo_manager)
            self.executor = ToolExecutor(tools=tools)

        self.messages: list[dict[str, Any]] = []
        self.system_prompt = self._get_system_prompt()

    def _debug_log(self, message: str) -> None:
        """Print debug message in dim style if debug mode is enabled."""
        if self.debug:
            _debug_console.print(f"[dim]{message}[/dim]")

    def _get_system_prompt(self) -> str:
        """Get the system prompt for the agent."""
        return """You are a coding agent that takes action using tools.

IMPORTANT: You MUST use tools to complete tasks. Do NOT just explain how to do something - actually DO it using your tools.

WORKFLOW: You can use multiple turns:
- Turn 1: Use tools to gather information (read, glob, grep, etc.)
- Turn 2+: Use tools to take action (write, edit, bash, etc.)
- You are NOT required to use tools in every single turn if you need to process information first

Available tools:
- read: Read file contents
- write: Write content to a file (provide file_path and complete content)
- edit: Edit files by replacing text
- glob: Find files by pattern (e.g., "**/*.py")
- grep: Search file contents with regex
- bash: Execute shell commands
- WebSearch: Search the web for information
- WebFetch: Fetch URL content and convert HTML to plain text
- AskUserQuestion: Ask the user for clarification
- TodoWrite: Update todo list (replaces entire list)
- TodoRead: Read current todo list

RULES:
1. When asked to find/search something → USE the glob or grep tool immediately
2. When asked to read/show a file → USE the read tool immediately
3. When asked to create/write a file → USE write tool with file_path and COMPLETE content
4. When asked to modify a file → USE the edit tool immediately
5. When asked to run a command → USE the bash tool immediately
6. When asked about recent/latest information → USE WebSearch immediately
7. When asked to fetch/read a URL or web page → USE WebFetch to get the text, then analyze it
8. NEVER explain methods or options - just take action
9. After using tools, summarize what you found/did

CRITICAL for write tool:
- You MUST provide BOTH file_path AND content in a single call
- Generate the full content first, then call write with all text included
- Example: write(file_path="/path/to/file.txt", content="Complete content here...")

TODO TOOL USAGE:
Use TodoWrite to plan and track complex tasks (3+ steps).

When to use:
- Complex tasks with 3+ steps
- User requests multiple things at once
- Multi-file changes

When NOT to use:
- Single, simple tasks
- Tasks under 3 steps
- Pure conversation/information requests

Status values:
- pending: Not yet started
- in_progress: Currently working on (only ONE at a time!)
- completed: Finished

Mark tasks as completed IMMEDIATELY after finishing (don't batch).
"""

    def run(
        self,
        user_message: str,
        pause_spinner_callback: Any = None,
        resume_spinner_callback: Any = None,
        update_spinner_callback: Any = None,
    ) -> str:
        """Run the agent loop with a user message.

        Args:
            user_message: The user's input message
            pause_spinner_callback: Optional callback to pause spinner during user input
            resume_spinner_callback: Optional callback to resume spinner after user input
            update_spinner_callback: Optional callback to update spinner with new todo status
        """
        self.pause_spinner_callback = pause_spinner_callback
        self.resume_spinner_callback = resume_spinner_callback
        self.update_spinner_callback = update_spinner_callback
        self.messages.append({"role": "user", "content": user_message})

        self._debug_log(f"\n{'='*60}")
        self._debug_log(f"[AGENT LOOP] Starting with user message: {user_message[:100]}...")
        self._debug_log(f"{'='*60}\n")

        for turn in range(self.max_turns):
            self._debug_log(f"\n{'─'*60}")
            self._debug_log(f"[TURN {turn + 1}/{self.max_turns}]")
            self._debug_log(f"{'─'*60}")

            # Don't force tool use - let LLM decide when it's ready
            # Forcing tools can cause incomplete parameters (e.g., write without content)
            response = self._call_llm(force_tool=False)

            # Check if there are tool calls
            tool_uses = [
                block for block in response.content if isinstance(block, ToolUseBlock)
            ]

            if not tool_uses:
                # No tool calls - return text response
                text_content = [
                    block.text
                    for block in response.content
                    if isinstance(block, TextBlock)
                ]
                text_response = "\n".join(text_content)
                self._debug_log(f"\n[COMPLETE] No tool calls, returning text response")
                return text_response

            # Process tool calls
            self.messages.append({"role": "assistant", "content": response.content})

            self._debug_log(f"\n[TOOL EXECUTION] Executing {len(tool_uses)} tool(s)...")

            tool_results = []

            for idx, tool_use in enumerate(tool_uses):
                self._debug_log(f"\n  Tool {idx + 1}: {tool_use.name}")

                tool_input = dict(tool_use.input)

                # Show input for debugging
                input_str = str(tool_input)
                if len(input_str) > 150:
                    self._debug_log(f"    Input: {input_str[:150]}...")
                else:
                    self._debug_log(f"    Input: {input_str}")

                # Pause spinner for AskUserQuestion to allow clean user input
                if tool_use.name == "AskUserQuestion" and self.pause_spinner_callback:
                    self.pause_spinner_callback()

                result = self.executor.execute(tool_use.name, tool_input)

                # Resume spinner after AskUserQuestion
                if tool_use.name == "AskUserQuestion" and self.resume_spinner_callback:
                    self.resume_spinner_callback()

                self._debug_log(f"    Success: {result.success}")
                if result.success:
                    self._debug_log(f"    Output: {result.output[:200]}...")
                else:
                    self._debug_log(f"    Error: {result.error}")

                # Update spinner with new todo status (live display)
                if tool_use.name == "TodoWrite" and result.success:
                    if self.update_spinner_callback:
                        self.update_spinner_callback()

                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": tool_use.id,
                        "content": self._format_tool_result(result),
                    }
                )

            self.messages.append({"role": "user", "content": tool_results})
            self._debug_log(f"\n[FEEDBACK] Tool results added to conversation")

            # Check context size after each turn
            self._check_context_size()

        self._debug_log(f"\n{'='*60}")
        self._debug_log(f"[MAX TURNS] Reached maximum turns ({self.max_turns})")
        self._debug_log(f"{'='*60}\n")
        return "Max turns reached. Please continue with a new message."

    def _call_llm(self, force_tool: bool = False) -> Message:
        """Call the LLM with current messages."""
        kwargs: dict[str, Any] = {
            "model": self.model,
            "max_tokens": 16*1024,
            "system": self.system_prompt,
            "tools": self.executor.get_tool_definitions(),
            "messages": self.messages,
        }

        # Force tool use on first turn to encourage action
        if force_tool:
            kwargs["tool_choice"] = {"type": "any"}

        # Show LLM request
        self._debug_log(f"\n[LLM REQUEST]")
        for i, msg in enumerate(self.messages, 1):
            role = msg['role']
            content = msg['content']

            if isinstance(content, str):
                preview = content[:150] + "..." if len(content) > 150 else content
                self._debug_log(f"  #{i} {role.upper()}: {preview}")
            elif isinstance(content, list):
                # Check if it's tool results or assistant content
                if all(isinstance(item, dict) and item.get('type') == 'tool_result' for item in content):
                    self._debug_log(f"  #{i} {role.upper()}: [Tool Results x{len(content)}]")
                    for j, item in enumerate(content[:2], 1):  # Show first 2 tool results
                        result_preview = item['content'][:100] + "..." if len(item['content']) > 100 else item['content']
                        self._debug_log(f"      Result {j}: {result_preview}")
                    if len(content) > 2:
                        self._debug_log(f"      ... and {len(content) - 2} more")
                else:
                    # Assistant message with mixed content
                    for item in content:
                        if hasattr(item, 'type'):
                            if item.type == 'tool_use':
                                self._debug_log(f"  #{i} {role.upper()}: Tool={item.name}, Input={str(item.input)[:80]}...")
                            elif item.type == 'text':
                                self._debug_log(f"  #{i} {role.upper()}: {item.text[:100]}...")

        try:
            response = self.client.messages.create(**kwargs)
        except RateLimitError as e:
            self._debug_log(f"\n{'='*60}")
            self._debug_log(f"[API ERROR] Rate Limit Exceeded")
            self._debug_log(f"{'='*60}")
            self._debug_log(f"[ERROR] Claude API rate limit reached.")
            self._debug_log(f"[ERROR] {str(e)}")
            self._debug_log(f"\n[SUGGESTION] Please try one of the following:")
            self._debug_log(f"  1. Wait a few moments and try again")
            self._debug_log(f"  2. Use 'reset' to clear conversation history")
            self._debug_log(f"  3. Reduce the size of your request")
            self._debug_log(f"{'='*60}\n")
            raise
        except APIError as e:
            self._debug_log(f"\n{'='*60}")
            self._debug_log(f"[API ERROR] Claude API Error")
            self._debug_log(f"{'='*60}")
            self._debug_log(f"[ERROR] Failed to communicate with Claude API.")
            self._debug_log(f"[ERROR] {str(e)}")
            self._debug_log(f"\n[SUGGESTION] Please check:")
            self._debug_log(f"  1. Your internet connection")
            self._debug_log(f"  2. API key is valid (ANTHROPIC_API_KEY)")
            self._debug_log(f"  3. Anthropic API status: https://status.anthropic.com")
            self._debug_log(f"{'='*60}\n")
            raise
        except Exception as e:
            self._debug_log(f"\n{'='*60}")
            self._debug_log(f"[ERROR] Unexpected Error")
            self._debug_log(f"{'='*60}")
            self._debug_log(f"[ERROR] {str(e)}")
            self._debug_log(f"{'='*60}\n")
            raise

        # Show LLM response
        self._debug_log(f"\n[LLM RESPONSE] (stop_reason: {response.stop_reason})")
        for i, block in enumerate(response.content, 1):
            if isinstance(block, ToolUseBlock):
                self._debug_log(f"  #{i} ToolUse: {block.name}")
                input_str = str(block.input)
                self._debug_log(f"      Input: {input_str[:150]}...")
                # 특히 write 도구의 content가 비어있는지 체크
                if block.name == "write":
                    content = block.input.get("content", "")
                    if not content:
                        self._debug_log(f"      [ERROR] write tool called with EMPTY content!")
                    else:
                        self._debug_log(f"      Content length: {len(content)} chars")
            elif isinstance(block, TextBlock):
                self._debug_log(f"  #{i} Text: {block.text[:150]}...")

        return response

    def _format_tool_result(self, result: ToolResult) -> str:
        """Format a tool result for the LLM."""
        if result.success:
            output = result.output
            if len(output) > self.max_output_length:
                truncated_chars = len(output) - self.max_output_length
                output = (
                    output[: self.max_output_length]
                    + f"\n\n... (output truncated, {truncated_chars:,} characters omitted)"
                )
            return output
        else:
            error_output = f"Error: {result.error}\n{result.output}".strip()
            if len(error_output) > self.max_output_length:
                truncated_chars = len(error_output) - self.max_output_length
                error_output = (
                    error_output[: self.max_output_length]
                    + f"\n\n... (error output truncated, {truncated_chars:,} characters omitted)"
                )
            return error_output

    def _estimate_tokens(self, text: str) -> int:
        """Estimate token count for text (rough approximation)."""
        # Simple estimation: ~4 characters per token on average
        return len(text) // 4

    def _count_messages_tokens(self) -> int:
        """Count total tokens in message history."""
        total = 0

        for msg in self.messages:
            content = msg.get("content", "")

            if isinstance(content, str):
                total += self._estimate_tokens(content)
            elif isinstance(content, list):
                for item in content:
                    if isinstance(item, dict):
                        # Tool result or structured content
                        item_str = str(item.get("content", ""))
                        total += self._estimate_tokens(item_str)
                    elif hasattr(item, "text"):
                        # TextBlock
                        total += self._estimate_tokens(item.text)

        # Add system prompt tokens
        total += self._estimate_tokens(self.system_prompt)

        return total

    def _check_context_size(self) -> None:
        """Check and warn if context is getting large."""
        token_count = self._count_messages_tokens()

        # Auto-compact if threshold reached
        if self._should_compact():
            self._compact_context()
            return  # Exit after compaction

        # Warnings if not compacting
        if token_count > self.max_context_tokens:
            self._debug_log(f"\n[WARNING] Context size ({token_count:,} tokens) exceeds limit ({self.max_context_tokens:,} tokens)")
            self._debug_log(f"[WARNING] Consider using 'reset' command to clear history")
        elif token_count > self.max_context_tokens * 0.8:
            self._debug_log(f"\n[INFO] Context size: {token_count:,} / {self.max_context_tokens:,} tokens (80%+)")

    def get_context_usage(self) -> dict[str, any]:
        """Get current context usage information."""
        token_count = self._count_messages_tokens()
        percentage = (token_count / self.max_context_tokens) * 100

        return {
            "current": token_count,
            "max": self.max_context_tokens,
            "percentage": percentage,
            "messages": len(self.messages),
        }

    def reset(self) -> None:
        """Reset the conversation history."""
        self.messages = []

    def _should_compact(self) -> bool:
        """Check if context compaction is needed."""
        if not self.enable_auto_compaction:
            return False

        # Need at least preserve_recent_messages + 2 to have something to compact
        if len(self.messages) <= self.preserve_recent_messages + 2:
            return False

        token_count = self._count_messages_tokens()
        threshold = int(self.max_context_tokens * self.compaction_threshold)

        return token_count >= threshold

    def _generate_summary(self, messages_to_summarize: list[dict[str, Any]]) -> str:
        """Generate a summary of messages using AI."""
        summary_prompt = """You have been assisting the user but the conversation is getting long.
Create a concise summary that preserves essential information for continuing the work.

Include in your summary:

1. **Task Overview**
   - User's main request and goals
   - Any constraints or requirements

2. **Work Completed**
   - Files read, created, or modified (with exact paths)
   - Commands executed successfully
   - Key findings or outputs

3. **Important Context**
   - Variable names, function names, class names mentioned
   - Technical decisions made and reasons
   - Errors encountered and how they were resolved
   - User preferences or style requirements

4. **Current State**
   - What needs to be done next
   - Any blockers or open questions

Keep the summary concise (under 1000 words) but preserve ALL critical details.
Focus on facts, not process. Include specific names (files, variables, etc.).
Wrap your entire summary in <summary></summary> tags."""

        try:
            # Clean messages to remove tool content (only keep text for summary)
            # This avoids passing tool_use/tool_result to the summary API
            cleaned_messages = []
            for msg in messages_to_summarize:
                role = msg.get("role")
                content = msg.get("content")

                if isinstance(content, str):
                    # Simple text message - keep as is
                    cleaned_messages.append(msg)
                elif isinstance(content, list):
                    # Mixed content - extract only text parts
                    text_parts = []
                    for item in content:
                        if isinstance(item, dict):
                            if item.get("type") == "text":
                                text_parts.append(item.get("text", ""))
                            elif item.get("type") == "tool_use":
                                tool_name = item.get("name", "unknown")
                                tool_input = str(item.get("input", {}))[:100]
                                text_parts.append(f"[Used tool: {tool_name} with {tool_input}...]")
                            elif item.get("type") == "tool_result":
                                result = str(item.get("content", ""))[:200]
                                text_parts.append(f"[Tool result: {result}...]")
                        elif hasattr(item, "text"):
                            text_parts.append(item.text)

                    if text_parts:
                        cleaned_messages.append({
                            "role": role,
                            "content": "\n".join(text_parts)
                        })

            # Call Claude API for summarization
            response = self.client.messages.create(
                model=self.model,
                max_tokens=8*1024,
                system="You are a helpful assistant that creates concise summaries.",
                messages=cleaned_messages + [
                    {"role": "user", "content": summary_prompt}
                ],
            )

            # Extract text from response
            text = "".join(
                block.text for block in response.content if hasattr(block, "text")
            )

            # Extract summary from tags
            import re
            match = re.search(r"<summary>(.*?)</summary>", text, re.DOTALL)
            if match:
                return match.group(1).strip()
            else:
                return text.strip()

        except Exception as e:
            self._debug_log(f"[ERROR] Failed to generate summary: {e}")
            # Fallback: simple concatenation
            return "Previous conversation covered multiple topics. Context preserved."

    def _replace_with_summary(self, summary: str) -> None:
        """Replace old messages with summary."""
        # Extract recent messages
        recent_messages = self.messages[-self.preserve_recent_messages:]

        # IMPORTANT: Validate that we don't break tool_use/tool_result pairs
        # If the first recent message is a tool_result, we need to include the previous tool_use
        if recent_messages and recent_messages[0].get("role") == "user":
            content = recent_messages[0].get("content", [])
            # Check if content is a list of tool results
            if isinstance(content, list) and any(
                isinstance(item, dict) and item.get("type") == "tool_result"
                for item in content
            ):
                # Need to find the corresponding tool_use in the previous message
                # Include one more message (the assistant message with tool_use)
                if len(self.messages) > self.preserve_recent_messages:
                    recent_messages = self.messages[-(self.preserve_recent_messages + 1):]
                    self._debug_log(f"[INFO] Extended recent messages to preserve tool_use/tool_result pairs")

        # Create summary message
        summary_message = {
            "role": "user",
            "content": f"[Previous conversation summary]\n\n{summary}"
        }

        # Replace history
        self.messages = [summary_message] + recent_messages

    def _compact_context(self) -> None:
        """Perform context compaction by summarizing old messages."""
        self._debug_log(f"\n{'='*60}")
        self._debug_log(f"[CONTEXT COMPACTION] Starting...")
        self._debug_log(f"{'='*60}")

        # Pre-compaction stats
        original_count = len(self.messages)
        original_tokens = self._count_messages_tokens()

        self._debug_log(f"[INFO] Current state: {original_count} messages, {original_tokens:,} tokens")
        self._debug_log(f"[INFO] Preserving recent {self.preserve_recent_messages} messages")

        # Find safe split point (don't break tool_use/tool_result pairs)
        preserve_count = self.preserve_recent_messages

        # Check if we need to extend to preserve tool pairs
        if len(self.messages) > preserve_count:
            first_recent = self.messages[-preserve_count]

            # If first recent message is a tool_result, include the previous tool_use
            if first_recent.get("role") == "user":
                content = first_recent.get("content", [])
                if isinstance(content, list) and any(
                    isinstance(item, dict) and item.get("type") == "tool_result"
                    for item in content
                ):
                    preserve_count += 1
                    self._debug_log(f"[INFO] Extended preserve count to {preserve_count} to keep tool pairs intact")

        # Split messages at safe point
        messages_to_summarize = self.messages[:-preserve_count]

        self._debug_log(f"[INFO] Summarizing {len(messages_to_summarize)} older messages...")

        # Generate summary (clean messages without tool_result orphans)
        summary = self._generate_summary(messages_to_summarize)

        self._debug_log(f"[INFO] Summary generated ({len(summary)} characters)")

        # Replace history (using updated preserve_count)
        recent_messages = self.messages[-preserve_count:]
        summary_message = {
            "role": "user",
            "content": f"[Previous conversation summary]\n\n{summary}"
        }
        self.messages = [summary_message] + recent_messages

        # Post-compaction stats
        new_count = len(self.messages)
        new_tokens = self._count_messages_tokens()
        reduction = ((original_tokens - new_tokens) / original_tokens) * 100

        self._debug_log(f"[SUCCESS] Compaction complete!")
        self._debug_log(f"[SUCCESS] Messages: {original_count} → {new_count}")
        self._debug_log(f"[SUCCESS] Tokens: {original_tokens:,} → {new_tokens:,} ({reduction:.1f}% reduction)")
        self._debug_log(f"{'='*60}\n")
