"""Agent loop - Main agent execution loop."""

import time
from typing import Any

from anthropic import Anthropic, RateLimitError, APIError
from anthropic.types import Message, ToolUseBlock, TextBlock

from not_agent.tools import ToolResult
from .executor import ToolExecutor


class AgentLoop:
    """Main agent loop that handles conversation and tool execution."""

    def __init__(
        self,
        model: str = "claude-haiku-4-5-20251001",
        max_turns: int = 20,
        max_output_length: int = 10_000,
        max_context_tokens: int = 50_000,
        compaction_threshold: float = 0.75,
        preserve_recent_messages: int = 4,
        enable_auto_compaction: bool = True,
    ) -> None:
        self.client = Anthropic()
        self.model = model
        self.max_turns = max_turns
        self.max_output_length = max_output_length
        self.max_context_tokens = max_context_tokens
        self.compaction_threshold = compaction_threshold
        self.preserve_recent_messages = preserve_recent_messages
        self.enable_auto_compaction = enable_auto_compaction
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
- AskUserQuestion: Ask the user for clarification or confirmation

RULES:
1. When asked to find/search something → USE the glob or grep tool immediately
2. When asked to read/show a file → USE the read tool immediately
3. When asked to create/modify a file → USE write or edit tool immediately
4. When asked to run a command → USE the bash tool immediately
5. When asked about recent/latest information → USE WebSearch immediately
6. When asked to fetch/read a URL or web page → USE WebFetch to get the text, then analyze it
7. NEVER explain methods or options - just take action
8. After using tools, summarize what you found/did

ASKING QUESTIONS:
- If you're UNSURE about requirements or approach → USE AskUserQuestion
- Before DANGEROUS operations (rm -rf, DROP TABLE, etc.) → USE AskUserQuestion to confirm
- When MULTIPLE VALID approaches exist → USE AskUserQuestion to let user choose
- Provide options array when possible (easier for user to select)
- Be specific and clear in your questions

FILE MODIFICATION POLICY (CRITICAL - ALWAYS FOLLOW):
BEFORE using write, edit, or file deletion commands (rm, git rm), you MUST:
1. Use AskUserQuestion to get user approval
2. Clearly describe what file will be created/modified/deleted and why
3. For new files: Show the file path and brief description of content
4. For edits: Show the file path and what will be changed
5. For deletions: Show which files will be deleted
6. Provide clear Yes/No options
7. ONLY exception: If user message explicitly contains approval keywords like:
   - "yes, proceed"
   - "go ahead"
   - "do it"
   - "confirmed"
   Then you may skip asking and proceed directly

EXAMPLE (Creating new file):
question: "I'm about to create a new file 'src/utils/helper.py' with utility functions for data processing. Should I proceed?"
options: [{"label": "Yes, create it", "description": "..."}, {"label": "No, don't create", "description": "..."}]

EXAMPLE (Editing file):
question: "I'm about to modify 'src/main.py' to add error handling in the parse() function. Should I proceed?"
options: [{"label": "Yes, modify it", "description": "..."}, {"label": "No, cancel", "description": "..."}]

SAFETY:
- Always read files before editing them
- Be careful with destructive bash commands
- NEVER modify files without user approval (via AskUserQuestion)
- Ask before deleting files or making irreversible changes"""

    def run(self, user_message: str, status_callback: Any = None) -> str:
        """Run the agent loop with a user message.

        Args:
            user_message: The user's input message
            status_callback: Optional callback to pause status/spinner (called before AskUserQuestion)
        """
        self.status_callback = status_callback
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

                # Pause spinner for AskUserQuestion
                if tool_use.name == "AskUserQuestion" and self.status_callback:
                    self.status_callback()

                # Update executor with current conversation history for approval checking
                self.executor.set_conversation_history(self.messages)

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

            # Check context size after each turn
            self._check_context_size()

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

        try:
            response = self.client.messages.create(**kwargs)
        except RateLimitError as e:
            print(f"\n{'='*60}")
            print(f"[API ERROR] Rate Limit Exceeded")
            print(f"{'='*60}")
            print(f"[ERROR] Claude API rate limit reached.")
            print(f"[ERROR] {str(e)}")
            print(f"\n[SUGGESTION] Please try one of the following:")
            print(f"  1. Wait a few moments and try again")
            print(f"  2. Use 'reset' to clear conversation history")
            print(f"  3. Reduce the size of your request")
            print(f"{'='*60}\n")
            raise
        except APIError as e:
            print(f"\n{'='*60}")
            print(f"[API ERROR] Claude API Error")
            print(f"{'='*60}")
            print(f"[ERROR] Failed to communicate with Claude API.")
            print(f"[ERROR] {str(e)}")
            print(f"\n[SUGGESTION] Please check:")
            print(f"  1. Your internet connection")
            print(f"  2. API key is valid (ANTHROPIC_API_KEY)")
            print(f"  3. Anthropic API status: https://status.anthropic.com")
            print(f"{'='*60}\n")
            raise
        except Exception as e:
            print(f"\n{'='*60}")
            print(f"[ERROR] Unexpected Error")
            print(f"{'='*60}")
            print(f"[ERROR] {str(e)}")
            print(f"{'='*60}\n")
            raise

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
            print(f"\n[WARNING] Context size ({token_count:,} tokens) exceeds limit ({self.max_context_tokens:,} tokens)")
            print(f"[WARNING] Consider using 'reset' command to clear history")
        elif token_count > self.max_context_tokens * 0.8:
            print(f"\n[INFO] Context size: {token_count:,} / {self.max_context_tokens:,} tokens (80%+)")

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
                max_tokens=2048,
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
            print(f"[ERROR] Failed to generate summary: {e}")
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
                    print(f"[INFO] Extended recent messages to preserve tool_use/tool_result pairs")

        # Create summary message
        summary_message = {
            "role": "user",
            "content": f"[Previous conversation summary]\n\n{summary}"
        }

        # Replace history
        self.messages = [summary_message] + recent_messages

    def _compact_context(self) -> None:
        """Perform context compaction by summarizing old messages."""
        print(f"\n{'='*60}")
        print(f"[CONTEXT COMPACTION] Starting...")
        print(f"{'='*60}")

        # Pre-compaction stats
        original_count = len(self.messages)
        original_tokens = self._count_messages_tokens()

        print(f"[INFO] Current state: {original_count} messages, {original_tokens:,} tokens")
        print(f"[INFO] Preserving recent {self.preserve_recent_messages} messages")

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
                    print(f"[INFO] Extended preserve count to {preserve_count} to keep tool pairs intact")

        # Split messages at safe point
        messages_to_summarize = self.messages[:-preserve_count]

        print(f"[INFO] Summarizing {len(messages_to_summarize)} older messages...")

        # Generate summary (clean messages without tool_result orphans)
        summary = self._generate_summary(messages_to_summarize)

        print(f"[INFO] Summary generated ({len(summary)} characters)")

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

        print(f"[SUCCESS] Compaction complete!")
        print(f"[SUCCESS] Messages: {original_count} → {new_count}")
        print(f"[SUCCESS] Tokens: {original_tokens:,} → {new_tokens:,} ({reduction:.1f}% reduction)")
        print(f"{'='*60}\n")
